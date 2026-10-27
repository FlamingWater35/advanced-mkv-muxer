import hashlib
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import tests  # noqa: F401  (must run before application imports)

from packages.ToolUpdates import MkvToolNixUpdater as updater
from packages.ToolUpdates.MkvToolNixUpdater import ReleaseAsset, UpdateError, UpdateStatus
from packages.ToolUpdates.ToolsUpdateWorker import ToolsUpdateWorker

DOWNLOADS_PAGE = """
<a href="windows/releases/103.0/mkvtoolnix-64-bit-103.0.7z">64 bit</a>
<a href="windows/releases/103.0/mkvtoolnix-32-bit-103.0.7z">32 bit</a>
<a href="appimage/MKVToolNix_GUI-77.0-x86_64.AppImage">old AppImage</a>
"""

CODEBERG_TAGS = json.dumps([
    {"name": "release-103.0"},
    {"name": "release-102.0"},
    {"name": "unrelated-tag"},
])


class VersionParsingTests(unittest.TestCase):
    def test_parses_tool_output(self):
        self.assertEqual(updater.parse_version("mkvmerge v81.0 ('Milliontown') 64-bit"), "81.0")
        self.assertEqual(updater.parse_version("mkvpropedit v103.0 ('Milliontown') 64-bit"), "103.0")
        self.assertEqual(updater.parse_version("103.0"), "103.0")

    def test_returns_none_without_version(self):
        self.assertIsNone(updater.parse_version("mkvmerge: not found!"))
        self.assertIsNone(updater.parse_version(""))
        self.assertIsNone(updater.parse_version(None))

    def test_compares_versions(self):
        self.assertTrue(updater.is_newer("103.0", "81.0"))
        self.assertTrue(updater.is_newer("81.10", "81.9"))
        self.assertTrue(updater.is_newer("103", "102.5"))
        self.assertFalse(updater.is_newer("81.0", "81.0"))
        self.assertFalse(updater.is_newer("80.0", "81.0"))
        self.assertFalse(updater.is_newer("103.0", None))
        self.assertFalse(updater.is_newer(None, "81.0"))


class ReleaseLookupTests(unittest.TestCase):
    def test_reads_newest_version_from_downloads_page(self):
        self.assertEqual(updater.version_from_downloads_page(DOWNLOADS_PAGE), "103.0")

    def test_reads_newest_version_from_tags(self):
        self.assertEqual(updater.version_from_codeberg_tags(CODEBERG_TAGS), "103.0")

    def test_latest_version_uses_downloads_page_first(self):
        requested = []

        def fetch(url):
            requested.append(url)
            return DOWNLOADS_PAGE

        self.assertEqual(updater.latest_version(fetch_text=fetch), "103.0")
        self.assertEqual(requested, [updater.DOWNLOADS_PAGE_URL])

    def test_latest_version_falls_back_to_tags(self):
        def fetch(url):
            if url == updater.DOWNLOADS_PAGE_URL:
                raise OSError("site unavailable")
            return CODEBERG_TAGS

        self.assertEqual(updater.latest_version(fetch_text=fetch), "103.0")

    def test_latest_version_reports_all_errors(self):
        def fetch(url):
            raise OSError("network down")

        with self.assertRaises(UpdateError) as context:
            updater.latest_version(fetch_text=fetch)
        self.assertIn("network down", str(context.exception))

    def test_check_for_update_detects_newer_release(self):
        status = updater.check_for_update("81.0", fetch_text=lambda url: DOWNLOADS_PAGE)
        self.assertEqual(status, UpdateStatus(current="81.0", latest="103.0", update_available=True))

    def test_check_for_update_reports_current_release(self):
        status = updater.check_for_update("103.0", fetch_text=lambda url: DOWNLOADS_PAGE)
        self.assertFalse(status.update_available)


class ReleaseAssetTests(unittest.TestCase):
    def test_windows_64_bit_asset(self):
        asset = updater.release_for_platform("103.0", system="win32", bits=64)
        self.assertEqual(asset.filename, "mkvtoolnix-64-bit-103.0.zip")
        self.assertEqual(asset.kind, "zip")
        self.assertEqual(
            asset.url,
            "https://mkvtoolnix.download/windows/releases/103.0/mkvtoolnix-64-bit-103.0.zip",
        )
        self.assertEqual(
            asset.checksums_url,
            "https://mkvtoolnix.download/windows/releases/103.0/sha256sums.txt",
        )

    def test_windows_32_bit_asset(self):
        asset = updater.release_for_platform("103.0", system="win32", bits=32)
        self.assertEqual(asset.filename, "mkvtoolnix-32-bit-103.0.zip")

    def test_linux_asset(self):
        asset = updater.release_for_platform("103.0", system="linux")
        self.assertEqual(asset.filename, "MKVToolNix_GUI-103.0-x86_64.AppImage")
        self.assertEqual(asset.kind, "appimage")
        self.assertIsNone(asset.checksums_url)

    def test_other_platforms_are_rejected(self):
        with self.assertRaises(UpdateError):
            updater.release_for_platform("103.0", system="darwin")


class ChecksumTests(unittest.TestCase):
    def test_parses_checksum_lines(self):
        text = (
            "abc123  mkvtoolnix-64-bit-103.0.zip\n"
            "def456 *mkvtoolnix-32-bit-103.0.zip\n"
        )
        self.assertEqual(updater.parse_checksum(text, "mkvtoolnix-64-bit-103.0.zip"), "abc123")
        self.assertEqual(updater.parse_checksum(text, "mkvtoolnix-32-bit-103.0.zip"), "def456")
        self.assertIsNone(updater.parse_checksum(text, "unknown.zip"))


class WindowsArchiveTests(unittest.TestCase):
    def make_archive(self, directory: Path) -> Path:
        archive_path = directory / "mkvtoolnix.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("mkvtoolnix/mkvmerge.exe", b"MZ mkvmerge")
            archive.writestr("mkvtoolnix/mkvpropedit.exe", b"MZ mkvpropedit")
            archive.writestr("mkvtoolnix/doc/README.txt", b"docs")
        return archive_path

    def test_extracts_only_the_tools(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            archive_path = self.make_archive(directory)

            extracted = updater.extract_windows_zip(archive_path, directory / "unpacked")

            self.assertEqual(set(extracted), {"mkvmerge.exe", "mkvpropedit.exe"})
            self.assertEqual(extracted["mkvmerge.exe"].read_bytes(), b"MZ mkvmerge")

    def test_reports_missing_tools(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            archive_path = directory / "broken.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("mkvtoolnix/mkvmerge.exe", b"MZ")

            with self.assertRaises(UpdateError) as context:
                updater.extract_windows_zip(archive_path, directory / "unpacked")
            self.assertIn("mkvpropedit.exe", str(context.exception))


class FakeCompletedProcess:
    def __init__(self, returncode=0, stderr=""):
        self.returncode = returncode
        self.stderr = stderr


class AppImageExtractionTests(unittest.TestCase):
    def test_extracts_tools_and_library_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            appimage = directory / "tools.AppImage"
            appimage.write_bytes(b"appimage")

            def runner(command, **kwargs):
                root = Path(kwargs["cwd"]) / "squashfs-root"
                (root / "usr/bin").mkdir(parents=True)
                (root / "usr/lib").mkdir(parents=True)
                (root / "usr/bin/mkvmerge").write_bytes(b"merge")
                (root / "usr/bin/mkvpropedit").write_bytes(b"propedit")
                return FakeCompletedProcess()

            tools, lib_dir = updater.extract_appimage(appimage, directory / "work", runner=runner)

            self.assertEqual(set(tools), {"mkvmerge", "mkvpropedit"})
            self.assertEqual(lib_dir, directory / "work" / "squashfs-root" / "usr" / "lib")

    def test_failed_extraction_is_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            appimage = directory / "tools.AppImage"
            appimage.write_bytes(b"appimage")

            with self.assertRaises(UpdateError) as context:
                updater.extract_appimage(
                    appimage,
                    directory / "work",
                    runner=lambda command, **kwargs: FakeCompletedProcess(1, "boom"),
                )
            self.assertIn("boom", str(context.exception))


class LibraryClosureTests(unittest.TestCase):
    def test_collects_transitive_bundled_libraries(self):
        with tempfile.TemporaryDirectory() as temporary:
            lib_dir = Path(temporary)
            for name in ("libfoo.so.1", "libbar.so.2", "libunused.so.3"):
                (lib_dir / name).write_bytes(b"lib")

            dependencies = {
                "mkvmerge": ["libfoo.so.1", "libc.so.6"],
                "libfoo.so.1": ["libbar.so.2"],
            }

            closure = updater.library_closure(
                {"mkvmerge": lib_dir / "mkvmerge"},
                lib_dir,
                needed_reader=lambda path: dependencies.get(Path(path).name, []),
            )

            self.assertEqual(set(closure), {"libfoo.so.1", "libbar.so.2"})


class InstallTests(unittest.TestCase):
    def test_installs_and_verifies(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            target = directory / "target"
            source = directory / "source"
            target.mkdir()
            source.mkdir()
            (source / "mkvmerge").write_text("new merge")
            (source / "mkvpropedit").write_text("new propedit")

            installed = updater.install_tools(
                {"mkvmerge": source / "mkvmerge", "mkvpropedit": source / "mkvpropedit"},
                target,
                "103.0",
                probe=lambda path: "103.0",
                backup_dir=directory / "backup",
            )

            self.assertEqual((target / "mkvmerge").read_text(), "new merge")
            self.assertEqual(set(installed), {"mkvmerge", "mkvpropedit"})

    def test_rolls_back_when_version_is_wrong(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            target = directory / "target"
            source = directory / "source"
            target.mkdir()
            source.mkdir()
            (target / "mkvmerge").write_text("old merge")
            (source / "mkvmerge").write_text("broken merge")
            (source / "mkvpropedit").write_text("broken propedit")

            with self.assertRaises(UpdateError):
                updater.install_tools(
                    {"mkvmerge": source / "mkvmerge", "mkvpropedit": source / "mkvpropedit"},
                    target,
                    "103.0",
                    probe=lambda path: "80.0",
                    backup_dir=directory / "backup",
                )

            self.assertEqual((target / "mkvmerge").read_text(), "old merge")
            self.assertFalse((target / "mkvpropedit").exists())

    def test_install_from_asset_checks_the_checksum(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            archive_path = directory / "mkvtoolnix-64-bit-103.0.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("mkvtoolnix/mkvmerge.exe", b"MZ merge")
                archive.writestr("mkvtoolnix/mkvpropedit.exe", b"MZ propedit")
            digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
            asset = ReleaseAsset(
                version="103.0",
                filename=archive_path.name,
                url="https://example.invalid/tools.zip",
                kind="zip",
                checksums_url="https://example.invalid/sha256sums.txt",
            )

            version = updater.install_from_asset(
                asset,
                directory / "target",
                download=lambda url, destination, progress=None: shutil.copy2(archive_path, destination),
                fetch_text=lambda url: f"{digest}  {archive_path.name}\n",
                probe=lambda path: "103.0",
            )

            self.assertEqual(version, "103.0")
            self.assertTrue((directory / "target" / "mkvmerge.exe").is_file())

    def test_install_from_asset_rejects_bad_checksum(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            archive_path = directory / "mkvtoolnix-64-bit-103.0.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("mkvtoolnix/mkvmerge.exe", b"MZ")
                archive.writestr("mkvtoolnix/mkvpropedit.exe", b"MZ")
            asset = ReleaseAsset(
                version="103.0",
                filename=archive_path.name,
                url="https://example.invalid/tools.zip",
                kind="zip",
                checksums_url="https://example.invalid/sha256sums.txt",
            )

            with self.assertRaises(UpdateError) as context:
                updater.install_from_asset(
                    asset,
                    directory / "target",
                    download=lambda url, destination, progress=None: shutil.copy2(archive_path, destination),
                    fetch_text=lambda url: "0" * 64 + "  " + archive_path.name + "\n",
                    probe=lambda path: "103.0",
                )
            self.assertIn("Checksum mismatch", str(context.exception))
            self.assertFalse((directory / "target" / "mkvmerge.exe").exists())


class ToolPathTests(unittest.TestCase):
    def test_user_tools_take_precedence_when_both_are_present(self):
        from packages.Startup import GlobalFiles

        with tempfile.TemporaryDirectory() as temporary:
            user_dir = Path(temporary) / "user"
            bundled_dir = Path(temporary) / "bundled"
            user_dir.mkdir()
            bundled_dir.mkdir()
            merge_name = GlobalFiles.get_tool_file_name("mkvmerge")
            propedit_name = GlobalFiles.get_tool_file_name("mkvpropedit")
            (bundled_dir / merge_name).write_text("bundled")
            (bundled_dir / propedit_name).write_text("bundled")

            with mock.patch.object(GlobalFiles, "UserToolsFolderPath", str(user_dir)), \
                    mock.patch.object(GlobalFiles, "ToolsFolderPath", str(bundled_dir)):
                self.assertEqual(
                    Path(GlobalFiles.get_tool_paths()[0]).parent,
                    bundled_dir,
                )

                (user_dir / merge_name).write_text("updated")
                (user_dir / propedit_name).write_text("updated")

                paths = GlobalFiles.get_tool_paths()
                self.assertEqual(Path(paths[0]).parent, user_dir)
                self.assertEqual(Path(paths[1]).parent, user_dir)


class WorkerTests(unittest.TestCase):
    def test_check_emits_status(self):
        status = UpdateStatus(current="81.0", latest="103.0", update_available=True)
        results = []
        worker = ToolsUpdateWorker("check", "81.0", None, check=lambda current: status)
        worker.checked_signal.connect(results.append)

        worker.run()

        self.assertEqual(results, [status])

    def test_errors_are_emitted(self):
        messages = []

        def failing_check(current):
            raise UpdateError("network down")

        worker = ToolsUpdateWorker("check", "81.0", None, check=failing_check)
        worker.error_signal.connect(messages.append)

        worker.run()

        self.assertEqual(messages, ["network down"])

    def test_update_reports_installed_version(self):
        versions = []
        worker = ToolsUpdateWorker(
            "update", "81.0", Path(tempfile.gettempdir()),
            install=lambda target, progress=None: "103.0",
        )
        worker.updated_signal.connect(versions.append)

        worker.run()

        self.assertEqual(versions, ["103.0"])
