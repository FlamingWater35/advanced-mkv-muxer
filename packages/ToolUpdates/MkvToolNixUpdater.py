"""Checking for and installing new MKVToolNix releases.

The module is deliberately free of Qt imports so the release logic can be
tested without a GUI. Network access, archive extraction and the version probe
are injectable, which is what the unit tests use.
"""

import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

DOWNLOADS_PAGE_URL = "https://mkvtoolnix.download/downloads.html"
WINDOWS_RELEASES_URL = "https://mkvtoolnix.download/windows/releases"
APPIMAGE_URL = "https://mkvtoolnix.download/appimage"
CODEBERG_TAGS_URL = "https://codeberg.org/api/v1/repos/mbunkus/mkvtoolnix/tags?limit=100"
USER_AGENT = "Advanced-MKV-Muxer"

VERSION_PATTERN = re.compile(r"\bv?(\d+(?:\.\d+)+)\b")
TAG_PATTERN = re.compile(r"release-(\d+(?:\.\d+)+)")

WINDOWS_TOOL_NAMES = ("mkvmerge.exe", "mkvpropedit.exe")
LINUX_TOOL_NAMES = ("mkvmerge", "mkvpropedit")


class UpdateError(Exception):
    """Raised when the update cannot be checked for or installed."""


@dataclass(frozen=True)
class ReleaseAsset:
    version: str
    filename: str
    url: str
    kind: str  # "zip" or "appimage"
    checksums_url: str | None = None


@dataclass(frozen=True)
class UpdateStatus:
    current: str | None
    latest: str | None
    update_available: bool


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------

def parse_version(text: str | None) -> str | None:
    """Extract a version like ``81.0`` from tool output or a version string."""
    if not text:
        return None
    match = VERSION_PATTERN.search(text)
    return match.group(1) if match else None


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def is_newer(latest: str | None, current: str | None) -> bool:
    if not latest or not current:
        return False
    latest_key = version_key(latest)
    current_key = version_key(current)
    length = max(len(latest_key), len(current_key))
    latest_key += (0,) * (length - len(latest_key))
    current_key += (0,) * (length - len(current_key))
    return latest_key > current_key


# ---------------------------------------------------------------------------
# Latest release lookup
# ---------------------------------------------------------------------------

def version_from_downloads_page(html: str) -> str | None:
    versions = []
    for pattern in (
        r"windows/releases/(\d+(?:\.\d+)+)/mkvtoolnix-(?:32|64)-bit-\1\.(?:zip|7z)",
        r"windows/releases/(\d+(?:\.\d+)+)/mkvtoolnix-(?:32|64)-bit-\1-setup\.exe",
        r"appimage/MKVToolNix_GUI-(\d+(?:\.\d+)+)-x86_64\.AppImage",
    ):
        versions.extend(re.findall(pattern, html))
    return max(versions, key=version_key) if versions else None


def version_from_codeberg_tags(payload: str) -> str | None:
    data = json.loads(payload)
    versions = [match.group(1) for item in data
                if (match := TAG_PATTERN.fullmatch(str(item.get("name", ""))))]
    return max(versions, key=version_key) if versions else None


def fetch_url_text(url: str, timeout: int = 30) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, "replace")


def latest_version(fetch_text=fetch_url_text) -> str:
    """Return the newest published MKVToolNix version.

    The official downloads page is used first; the upstream repository tags are
    a fallback for when the page layout changes or the site is unreachable.
    """
    problems = []
    for url, parser in (
            (DOWNLOADS_PAGE_URL, version_from_downloads_page),
            (CODEBERG_TAGS_URL, version_from_codeberg_tags),
    ):
        try:
            found = parser(fetch_text(url))
        except Exception as exception:  # noqa: BLE001 - reported to the user
            problems.append(f"{url}: {exception}")
            continue
        if found:
            return found
        problems.append(f"{url}: no version information found")

    raise UpdateError("Could not determine the latest MKVToolNix version.\n" + "\n".join(problems))


def check_for_update(current_version: str | None, fetch_text=fetch_url_text) -> UpdateStatus:
    latest = latest_version(fetch_text=fetch_text)
    return UpdateStatus(
        current=current_version,
        latest=latest,
        update_available=is_newer(latest, current_version),
    )


# ---------------------------------------------------------------------------
# Release assets per platform
# ---------------------------------------------------------------------------

def release_for_platform(version: str, system: str | None = None, bits: int | None = None) -> ReleaseAsset:
    system = system or sys.platform
    if system == "win32":
        bits = bits or struct.calcsize("P") * 8
        flavour = "32" if bits == 32 else "64"
        filename = f"mkvtoolnix-{flavour}-bit-{version}.zip"
        base = f"{WINDOWS_RELEASES_URL}/{version}"
        return ReleaseAsset(
            version=version,
            filename=filename,
            url=f"{base}/{filename}",
            kind="zip",
            checksums_url=f"{base}/sha256sums.txt",
        )
    if system in ("linux", "linux2"):
        filename = f"MKVToolNix_GUI-{version}-x86_64.AppImage"
        return ReleaseAsset(
            version=version,
            filename=filename,
            url=f"{APPIMAGE_URL}/{filename}",
            kind="appimage",
        )
    raise UpdateError("Automatic MKVToolNix updates are not supported on this platform.")


# ---------------------------------------------------------------------------
# Download and verification
# ---------------------------------------------------------------------------

def download_file(url: str, destination: Path, progress=None, timeout: int = 120) -> Path:
    """Download ``url`` to ``destination``; ``progress`` gets (done, total)."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    destination = Path(destination)
    with urllib.request.urlopen(request, timeout=timeout) as response, destination.open("wb") as handle:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = response.read(256 * 1024)
            if not chunk:
                break
            handle.write(chunk)
            done += len(chunk)
            if progress is not None:
                progress(done, total)
    return destination


def parse_checksum(checksums_text: str, filename: str) -> str | None:
    for line in checksums_text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[-1].lstrip("*") == filename:
            return parts[0].lower()
    return None


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Archive extraction
# ---------------------------------------------------------------------------

def extract_windows_zip(archive_path: Path, work_dir: Path) -> dict[str, Path]:
    """Extract mkvmerge.exe and mkvpropedit.exe from the official zip."""
    archive_path = Path(archive_path)
    work_dir = Path(work_dir)
    target_names = set(WINDOWS_TOOL_NAMES)

    with zipfile.ZipFile(archive_path) as archive:
        members = []
        found = set()
        for info in archive.infolist():
            name = PurePosixPath(info.filename.replace("\\", "/")).name
            if name in target_names:
                members.append(info)
                found.add(name)
        missing = target_names - found
        if missing:
            raise UpdateError("The downloaded archive is missing: " + ", ".join(sorted(missing)))
        archive.extractall(path=work_dir, members=members)

    extracted = {}
    for name in target_names:
        matches = list(work_dir.rglob(name))
        if not matches:
            raise UpdateError(f"Could not extract {name} from {archive_path.name}.")
        extracted[name] = matches[0]
    return extracted


def extract_appimage(archive_path: Path, work_dir: Path, runner=subprocess.run) -> tuple[dict[str, Path], Path]:
    """Unpack the AppImage and return its CLI tools plus library directory."""
    archive_path = Path(archive_path)
    work_dir = Path(work_dir)
    archive_path.chmod(archive_path.stat().st_mode | 0o111)

    environment = os.environ.copy()
    environment.pop("APPIMAGE_EXTRACT_AND_RUN", None)
    result = runner(
        [str(archive_path), "--appimage-extract"],
        cwd=str(work_dir),
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=300,
    )
    if getattr(result, "returncode", 0) != 0:
        raise UpdateError(
            "Could not extract the AppImage"
            + (f": {result.stderr.strip()}" if getattr(result, "stderr", "") else ".")
        )

    root = work_dir / "squashfs-root"
    binary_dir = root / "usr" / "bin"
    tools = {}
    for name in LINUX_TOOL_NAMES:
        candidate = binary_dir / name
        if not candidate.is_file():
            raise UpdateError(f"The AppImage does not contain usr/bin/{name}.")
        tools[name] = candidate

    for lib_dir in (root / "usr" / "lib", root / "lib"):
        if lib_dir.is_dir():
            return tools, lib_dir
    raise UpdateError("The AppImage does not contain a library directory.")


# ---------------------------------------------------------------------------
# ELF dependencies (Linux)
# ---------------------------------------------------------------------------

def elf_needed_libraries(path: Path) -> list[str]:
    """Return the DT_NEEDED entries of a 64-bit little-endian ELF file."""
    path = Path(path)
    data = path.read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        return []

    program_offset, = struct.unpack_from("<Q", data, 0x20)
    entry_size, entry_count = struct.unpack_from("<HH", data, 0x36)
    loads = []
    dynamic = None
    for index in range(entry_count):
        offset = program_offset + index * entry_size
        (segment_type, _flags, file_offset, virtual_address,
         _physical, file_size, _memory, _align) = struct.unpack_from("<IIQQQQQQ", data, offset)
        if segment_type == 1:  # PT_LOAD
            loads.append((virtual_address, file_offset, file_size))
        elif segment_type == 2:  # PT_DYNAMIC
            dynamic = (file_offset, file_size)
    if dynamic is None:
        return []

    dynamic_offset, dynamic_size = dynamic
    entries = []
    for offset in range(dynamic_offset, dynamic_offset + dynamic_size, 16):
        tag, value = struct.unpack_from("<qQ", data, offset)
        if tag == 0:
            break
        entries.append((tag, value))

    string_table = next((value for tag, value in entries if tag == 5), None)
    if not string_table:
        return []

    def virtual_to_file(address: int) -> int:
        for virtual_address, file_offset, file_size in loads:
            if virtual_address <= address < virtual_address + file_size:
                return file_offset + (address - virtual_address)
        raise ValueError(f"Address {address:#x} is not mapped in {path}")

    strings_offset = virtual_to_file(string_table)
    needed = []
    for tag, value in entries:
        if tag != 1:
            continue
        start = strings_offset + value
        end = data.index(b"\0", start)
        needed.append(data[start:end].decode("utf-8", "replace"))
    return needed


def library_closure(tools: dict[str, Path], lib_dir: Path, needed_reader=elf_needed_libraries) -> dict[str, Path]:
    """Collect the shared libraries the tools need that ship with the AppImage."""
    lib_dir = Path(lib_dir)
    available = {path.name: path for path in lib_dir.iterdir() if path.is_file()}
    queue = []
    for tool in tools.values():
        queue.extend(needed_reader(tool))

    closure = {}
    seen = set()
    while queue:
        soname = queue.pop()
        if soname in seen:
            continue
        seen.add(soname)
        library = available.get(soname)
        if library is None:
            continue  # Provided by the system (glibc, libstdc++, ...).
        closure[soname] = library
        queue.extend(needed_reader(library))
    return closure


# ---------------------------------------------------------------------------
# Installation
# ---------------------------------------------------------------------------

def probe_version(tool: Path, environment: dict | None = None) -> str | None:
    """Run ``<tool> -V`` and return its version, or None."""
    try:
        result = subprocess.run(
            [str(tool), "-V"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=60,
            check=False,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_version(result.stdout)


def _install_files(files: dict[str, Path], target_dir: Path) -> dict[str, Path]:
    """Copy files into ``target_dir`` with a backup that allows a rollback."""
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    installed = {}
    for name, source in files.items():
        destination = target_dir / name
        temporary = destination.with_name(destination.name + ".new")
        shutil.copy2(source, temporary)
        if os.name != "nt":
            temporary.chmod(0o755)
        installed[name] = (temporary, destination)
    return installed


def _commit_files(installed: dict[str, tuple[Path, Path]]) -> dict[str, Path]:
    committed = {}
    for name, (temporary, destination) in installed.items():
        os.replace(temporary, destination)
        committed[name] = destination
    return committed


def _discard_files(installed: dict[str, tuple[Path, Path]]) -> None:
    for temporary, _destination in installed.values():
        try:
            temporary.unlink()
        except OSError:
            pass


def install_tools(
        files: dict[str, Path],
        target_dir: Path,
        version: str,
        *,
        probe=probe_version,
        probe_environment: dict | None = None,
        backup_dir: Path | None = None,
) -> dict[str, Path]:
    """Install ``files`` and verify that they report ``version``.

    The previous files are kept in ``backup_dir`` so they can be restored when
    the new binaries do not work.
    """
    target_dir = Path(target_dir)
    backup_dir = Path(backup_dir) if backup_dir else None
    if backup_dir:
        backup_dir.mkdir(parents=True, exist_ok=True)

    backups = {}
    for name in files:
        destination = target_dir / name
        if destination.is_file():
            backup = (backup_dir / name) if backup_dir else destination.with_name(destination.name + ".bak")
            shutil.copy2(destination, backup)
            backups[name] = backup

    installed = _install_files(files, target_dir)
    try:
        try:
            committed = _commit_files(installed)
        except OSError as exception:
            raise UpdateError(
                f"Could not replace the MKVToolNix tools ({exception.strerror or exception}). "
                "Close any running muxing job and try again."
            ) from exception
        for name, path in committed.items():
            found = probe(path, probe_environment) if probe_environment is not None else probe(path)
            if found != version:
                raise UpdateError(
                    f"{name} reports version {found or 'unknown'} after the update, expected {version}."
                )
    except BaseException:
        _discard_files(installed)
        for name, destination in ((name, target_dir / name) for name in files):
            backup = backups.get(name)
            try:
                if backup is not None:
                    shutil.copy2(backup, destination)
                elif destination.exists():
                    destination.unlink()
            except OSError:
                pass
        raise
    return committed


def install_from_asset(
        asset: ReleaseAsset,
        target_dir: Path,
        *,
        download=download_file,
        fetch_text=fetch_url_text,
        probe=probe_version,
        progress=None,
        runner=subprocess.run,
        needed_reader=elf_needed_libraries,
) -> str:
    """Download, verify, extract and install the tools for ``asset``."""
    def report(message, percent=-1):
        if progress is not None:
            progress(message, percent)

    target_dir = Path(target_dir)
    work_dir = Path(tempfile.mkdtemp(prefix="amkv-tools-update-"))
    try:
        archive_path = work_dir / asset.filename

        report(f"Downloading {asset.filename}…")
        download(asset.url, archive_path, progress=lambda done, total: report(
            f"Downloading {asset.filename}…",
            int(done * 100 / total) if total else -1,
        ))

        if asset.checksums_url:
            report("Verifying the download…")
            expected = parse_checksum(fetch_text(asset.checksums_url), asset.filename)
            if not expected:
                raise UpdateError(f"No published checksum for {asset.filename}.")
            actual = sha256_of(archive_path)
            if actual != expected:
                raise UpdateError(
                    f"Checksum mismatch for {asset.filename} (expected {expected}, got {actual})."
                )

        report("Extracting the tools…")
        probe_environment = None
        if asset.kind == "zip":
            extracted = extract_windows_zip(archive_path, work_dir / "unpacked")
            files = {name: path for name, path in extracted.items()}
        else:
            tools, lib_dir = extract_appimage(archive_path, work_dir, runner=runner)
            closure = library_closure(tools, lib_dir, needed_reader=needed_reader)
            files = {name: path for name, path in tools.items()}
            library_dir = target_dir / "lib"
            if closure:
                report(f"Installing {len(closure)} libraries…")
                library_dir.mkdir(parents=True, exist_ok=True)
                for soname, source in closure.items():
                    shutil.copy2(source, library_dir / soname)
                    (library_dir / soname).chmod(0o644)
            # The AppImage binaries have no usable RPATH, so the probe has to
            # see the libraries before they are installed.
            probe_environment = os.environ.copy()
            search_path = str(lib_dir)
            if os.environ.get("LD_LIBRARY_PATH"):
                search_path += ":" + os.environ["LD_LIBRARY_PATH"]
            probe_environment["LD_LIBRARY_PATH"] = search_path

        report("Installing the tools…")
        installed = install_tools(
            files,
            target_dir,
            asset.version,
            probe=probe,
            probe_environment=probe_environment,
            backup_dir=work_dir / "backup",
        )
    finally:
        # Cleanup problems (locked files, sandboxes) must not hide the result.
        shutil.rmtree(work_dir, ignore_errors=True)

    return asset.version


def install_update(
        target_dir: Path,
        version: str | None = None,
        *,
        fetch_text=fetch_url_text,
        download=download_file,
        probe=probe_version,
        progress=None,
        runner=subprocess.run,
        needed_reader=elf_needed_libraries,
) -> str:
    """Check (when needed) and install the newest release into ``target_dir``."""
    version = version or latest_version(fetch_text=fetch_text)
    asset = release_for_platform(version)
    return install_from_asset(
        asset,
        target_dir,
        download=download,
        fetch_text=fetch_text,
        probe=probe,
        progress=progress,
        runner=runner,
        needed_reader=needed_reader,
    )
