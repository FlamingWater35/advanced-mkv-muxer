"""Regression tests for the Linux packaging argument and the deferred start-up error."""

import re
import unittest
from pathlib import Path
from unittest import mock

import tests  # noqa: F401  (must run before application imports)

from packages.Startup import GlobalFiles
from tests import ROOT


class LinuxPackagingTests(unittest.TestCase):
    """The Linux build must ship the libraries the bundled tools link against.

    ``--include-data-dir`` silently skips shared libraries, so
    ``Resources/Tools/Linux/lib`` has to be added with ``--include-data-files``
    (the same trap the Windows build documents for its ``*.exe`` files).
    """

    def setUp(self):
        self.workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    def test_linux_tool_libraries_are_added_explicitly(self):
        self.assertIn("--include-data-files=Resources/Tools/Linux/lib/*", self.workflow)

    def test_libraries_exist_and_are_not_covered_by_the_data_dir_option(self):
        library_folder = ROOT / "Resources" / "Tools" / "Linux" / "lib"
        libraries = sorted(path.name for path in library_folder.iterdir() if path.is_file())
        self.assertGreater(len(libraries), 0, "no bundled Linux libraries to check")
        # Every one of them ends in a suffix that --include-data-dir ignores.
        for name in libraries:
            self.assertRegex(name, r"\.so(\.\d+)*$")

    def test_bundled_tools_are_still_included(self):
        self.assertIn("--include-data-dir=Resources/Tools/Linux=Resources/Tools/Linux", self.workflow)

    def test_windows_build_keeps_its_explicit_executables(self):
        script = (ROOT / "scripts" / "build_windows.py").read_text(encoding="utf-8")
        self.assertIn("--include-data-files={TOOLS_DIR}/mkvmerge.exe", script)
        self.assertIn("--include-data-files={TOOLS_DIR}/mkvpropedit.exe", script)


class LinuxStartupRegressionTests(unittest.TestCase):
    """Guards for the PySide6 SIGSEGV that broke every Linux build.

    ``libshiboken`` in PySide6 up to 6.7.0 imports the CPython *test* module
    ``xxsubtype`` while initialising. On Linux that module is a shared object
    Nuitka never bundles, so the import fails, the leftover exception makes
    ``PyType_FromSpecWithBases`` return NULL, and ``Shiboken::init()`` passes
    that NULL to ``PyType_Ready`` -> SIGSEGV before Qt even loads (PYSIDE-2747).
    Windows is unaffected because ``xxsubtype`` is a builtin there.
    """

    def setUp(self):
        self.workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

    def test_pyside6_is_new_enough_to_carry_the_upstream_fix(self):
        match = re.search(r"^PySide6==(\d+)\.(\d+)\.", self.requirements, re.MULTILINE)
        self.assertIsNotNone(match, "requirements.txt must pin PySide6")
        major, minor = int(match.group(1)), int(match.group(2))
        self.assertGreaterEqual(
            (major, minor), (6, 7),
            "PySide6 6.6.x and 6.7.0 import the CPython test module 'xxsubtype' "
            "from libshiboken; the Linux Nuitka build then segfaults at start-up.",
        )

    def test_ci_starts_the_linux_build_instead_of_only_inspecting_it(self):
        # A static "test -x" check cannot catch a start-up crash.
        self.assertIn("Smoke test the Linux build", self.workflow)
        self.assertIn("segmentation fault has occurred", self.workflow)

    def test_ci_smoke_test_verifies_the_profile_was_written(self):
        self.assertIn("setting.json", self.workflow)


class PortablePackagingTests(unittest.TestCase):
    """The portable Windows build must stay a real, self-contained folder.

    A portable copy is a Nuitka standalone folder plus a marker file. The marker
    switches the application to a ``Data`` folder beside itself, so the folder
    can be moved between machines with its settings intact. The build script and
    ``GlobalFiles`` must agree on the marker name.
    """

    def setUp(self):
        self.script = (ROOT / "scripts" / "build_windows.py").read_text(encoding="utf-8")
        self.workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    def test_build_script_and_application_agree_on_the_marker_name(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "build_windows_for_test", ROOT / "scripts" / "build_windows.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(
            module.PORTABLE_MARKER_FILE_NAME,
            GlobalFiles.PORTABLE_MARKER_FILE_NAME,
        )

    def test_portable_build_is_a_zip_of_a_standalone_folder(self):
        # The portable variant must not fall back to a onefile executable: a
        # portable copy needs a real folder for its Data directory.
        self.assertNotIn('nuitka_command("onefile"', self.script)
        self.assertIn("-portable.zip", self.script)
        self.assertIn("--mode=standalone", self.script)

    def test_portable_archive_contains_the_marker(self):
        self.assertIn("write_portable_marker(portable_folder)", self.script)

    def test_ci_records_the_portable_zip_as_the_release_asset(self):
        self.assertIn("windows-x64-portable.zip", self.workflow)
        self.assertNotIn("windows-x64-portable.exe", self.workflow)

    def test_ci_still_expects_four_release_assets(self):
        self.assertIn("Expected 4 assets", self.workflow)


class PortableDataFolderTests(unittest.TestCase):
    """The marker decides where settings, logs and updated tools are stored."""

    def setUp(self):
        import tempfile

        self.temp_dir = Path(tempfile.mkdtemp(prefix="portable-"))

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_no_marker_means_the_user_profile_is_used(self):
        self.assertIsNone(GlobalFiles.get_portable_data_folder(self.temp_dir))

    def test_marker_next_to_the_executable_selects_the_data_folder(self):
        (self.temp_dir / GlobalFiles.PORTABLE_MARKER_FILE_NAME).write_text("", encoding="utf-8")
        expected = self.temp_dir / GlobalFiles.PORTABLE_DATA_FOLDER_NAME
        self.assertEqual(Path(GlobalFiles.get_portable_data_folder(self.temp_dir)), expected)

    def test_portable_data_folder_name_is_data(self):
        self.assertEqual(GlobalFiles.PORTABLE_DATA_FOLDER_NAME, "Data")


class DeferredStartupErrorTests(unittest.TestCase):
    """A start-up failure must be reported, never crash before QApplication exists."""

    def setUp(self):
        self.original_error = GlobalFiles.StartupError

    def tearDown(self):
        GlobalFiles.StartupError = self.original_error

    def test_healthy_startup_records_no_error(self):
        self.assertIsNone(self.original_error)

    def test_globalfiles_does_not_build_a_widget_at_import_time(self):
        source = (ROOT / "packages" / "Startup" / "GlobalFiles.py").read_text(encoding="utf-8")
        self.assertIn("StartupError = e", source)
        # The dialog must only be created inside the deferred reporter, because
        # a QMessageBox needs the QApplication that does not exist yet.
        before_reporter = source.split("def show_startup_error_if_any")[0]
        self.assertNotIn("MissingFilesMessage(", before_reporter)

    def test_main_reports_the_error_once_the_application_exists(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        create_application = source.split("def create_application")[1].split("def create_window")[0]
        self.assertIn("show_startup_error_if_any()", create_application)

    def test_show_startup_error_if_any_reports_the_recorded_error(self):
        GlobalFiles.StartupError = Exception("mkvmerge file! ")
        recorded = {}

        class Recorder:
            def __init__(self, error_message):
                recorded["error"] = error_message

            def execute(self):
                recorded["executed"] = True

        with mock.patch.object(GlobalFiles, "MissingFilesMessage", Recorder):
            GlobalFiles.show_startup_error_if_any()

        self.assertEqual(recorded["error"], "mkvmerge file! ")
        self.assertTrue(recorded["executed"])

    def test_show_startup_error_if_any_is_a_noop_on_success(self):
        GlobalFiles.StartupError = None
        with mock.patch.object(GlobalFiles, "MissingFilesMessage") as missing_files_message:
            GlobalFiles.show_startup_error_if_any()
        missing_files_message.assert_not_called()
