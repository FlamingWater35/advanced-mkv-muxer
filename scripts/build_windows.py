#!/usr/bin/env python3
"""Build the Windows release artifacts the same way the CI workflow does.

Outputs (in ``dist/`` by default):

* ``Advanced-MKV-Muxer-<version>-windows-x64-portable.exe``
  Nuitka ``--mode=onefile`` build; no installation needed.
* ``Advanced-MKV-Muxer-<version>-windows-x64-setup.exe``
  Inno Setup installer wrapping the Nuitka ``--mode=standalone`` build.

The installer is installed per user, below
``%LOCALAPPDATA%\\Programs\\Advanced MKV Muxer`` (no administrator rights and
no UAC prompt).

The GitHub Actions workflow calls this script with ``--variant`` so that a
local run exercises exactly the same build code as a release run::

    python scripts/build_windows.py                    # portable + installer
    python scripts/build_windows.py --variant portable
    python scripts/build_windows.py --skip-deps --smoke-test

Run it with a Python 3.12 interpreter that has the project requirements
installed (or let the script install them).
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

APP_NAME = "Advanced MKV Muxer"
APP_SLUG = "Advanced-MKV-Muxer"
DEFAULT_NUITKA_VERSION = "4.3.3"

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "packages" / "Startup" / "Version.py"
ICON_FILE = ROOT / "Resources" / "Icons" / "App.ico"
INSTALLER_SCRIPT = ROOT / "installer" / "Advanced-MKV-Muxer.iss"
TOOLS_DIR = "Resources/Tools/Windows64"


def log(message: str) -> None:
    print(f"\n=== {message} ===", flush=True)


def run(command: list[object], *, cwd: Path = ROOT, env: dict | None = None) -> None:
    printable = subprocess.list2cmdline([str(part) for part in command])
    print(f"$ {printable}", flush=True)
    subprocess.run(
        [str(part) for part in command],
        cwd=str(cwd),
        env=env,
        check=True,
    )


def read_version(explicit: str | None) -> str:
    if explicit:
        version = explicit.strip()
    else:
        match = re.search(r'^Version\s*=\s*"([^"]+)"', VERSION_FILE.read_text(encoding="utf-8"), re.MULTILINE)
        if not match:
            raise SystemExit(f"Could not read the version from {VERSION_FILE}")
        version = match.group(1).strip()

    if not re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z._-]*", version):
        raise SystemExit(f"Unsupported version string: {version!r}")
    return version


def numeric_version(version: str) -> str:
    """Return an ``x.y.z.0`` version for the Windows file version resource."""
    core = version.split("-", 1)[0]
    parts = [part for part in core.split(".") if part.isdigit()][:3]
    while len(parts) < 3:
        parts.append("0")
    return ".".join(parts) + ".0"


def module_present(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def ensure_dependencies(args: argparse.Namespace) -> None:
    missing = [name for name in ("PySide6", "psutil", "nuitka") if not module_present(name)]
    if not missing:
        return

    install_command = (
        f'{sys.executable} -m pip install -r requirements.txt '
        f'"Nuitka[onefile]=={args.nuitka_version}"'
    )
    if args.skip_deps:
        raise SystemExit(
            "Missing required packages: " + ", ".join(missing) + "\n"
            "Install them with:\n  " + install_command + "\n"
            "or run this script without --skip-deps."
        )

    log("Installing missing Python packages: " + ", ".join(missing))
    run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
    run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    run([sys.executable, "-m", "pip", "install", f"Nuitka[onefile]=={args.nuitka_version}"])


def nuitka_command(mode: str, output_dir: Path, version: str, *, remove_output: bool) -> list[str]:
    file_version = numeric_version(version)
    command = [
        sys.executable,
        "-m",
        "nuitka",
        f"--mode={mode}",
        "--assume-yes-for-downloads",
        "--enable-plugin=pyside6",
        f"--output-dir={output_dir}",
        f"--output-filename={APP_SLUG}",
        f"--windows-icon-from-ico={ICON_FILE}",
        "--windows-console-mode=disable",
        f"--product-name={APP_NAME}",
        f"--file-description={APP_NAME}",
        f"--file-version={file_version}",
        f"--product-version={file_version}",
        "--include-data-dir=Resources/Fonts=Resources/Fonts",
        "--include-data-dir=Resources/Icons=Resources/Icons",
        "--include-data-dir=Resources/Languages=Resources/Languages",
        "--include-data-dir=Resources/DLL=Resources/DLL",
        # --include-data-dir skips *.exe files (Nuitka treats executables as
        # code), so the bundled MKVToolNix binaries are added explicitly.
        f"--include-data-files={TOOLS_DIR}/mkvmerge.exe={TOOLS_DIR}/mkvmerge.exe",
        f"--include-data-files={TOOLS_DIR}/mkvpropedit.exe={TOOLS_DIR}/mkvpropedit.exe",
        f"--include-data-files={TOOLS_DIR}/LICENSE={TOOLS_DIR}/LICENSE",
        f"--include-data-files={TOOLS_DIR}/README.md={TOOLS_DIR}/README.md",
    ]
    if remove_output:
        command.append("--remove-output")
    command.append("main.py")
    return command


def pick_executable(output_dir: Path) -> Path:
    for name in (f"{APP_SLUG}.exe", APP_SLUG, f"{APP_SLUG}.bin"):
        candidate = output_dir / name
        if candidate.is_file():
            return candidate
    candidates = sorted(path for path in output_dir.glob("*.exe") if path.is_file())
    if len(candidates) == 1:
        return candidates[0]
    raise SystemExit(f"Could not find the Nuitka executable in {output_dir}")


def build_portable(args: argparse.Namespace, version: str) -> Path:
    output_dir = ROOT / "build" / "portable"
    log("Building the portable executable (Nuitka --mode=onefile)")
    run(nuitka_command("onefile", output_dir, version, remove_output=True))

    binary = pick_executable(output_dir)
    target = args.output_dir / f"{APP_SLUG}-{version}-windows-x64-portable.exe"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(binary, target)
    require_size(target, minimum_mb=20)
    print(f"Portable build: {target} ({size_of(target)})", flush=True)

    if args.smoke_test:
        smoke_test(target, args.smoke_timeout)
    return target


def build_installer(args: argparse.Namespace, version: str) -> Path:
    output_dir = ROOT / "build" / "installer"
    log("Building the standalone application for the installer (Nuitka --mode=standalone)")
    run(nuitka_command("standalone", output_dir, version, remove_output=False))

    payload_dirs = sorted(path for path in output_dir.glob("*.dist") if path.is_dir())
    if len(payload_dirs) != 1:
        raise SystemExit(
            f"Expected exactly one .dist folder in {output_dir}, found {len(payload_dirs)}"
        )
    payload = payload_dirs[0]

    required = (
        f"{TOOLS_DIR}/mkvmerge.exe",
        f"{TOOLS_DIR}/mkvpropedit.exe",
        "Resources/Icons/App.ico",
        "Resources/Fonts/OpenSans.ttf",
        "Resources/Languages/iso639_language_list.json",
    )
    for relative in required:
        if not (payload / relative).is_file():
            raise SystemExit(f"The standalone build is missing {relative!r} in {payload}")
    print(f"Installer payload: {payload}", flush=True)

    if args.smoke_test:
        smoke_test(payload / f"{APP_SLUG}.exe", args.smoke_timeout)

    iscc = find_iscc(args.iscc)
    log(f"Compiling the installer with {iscc}")
    payload_relative = os.path.relpath(payload, INSTALLER_SCRIPT.parent)
    # Values are passed without quotes: ISCC turns each of them into a string
    # define itself, and embedded quotes would end up in the value.
    run(
        [
            iscc,
            INSTALLER_SCRIPT,
            f"/DDisplayVersion={version}",
            f"/DFileVersion={numeric_version(version)}",
            f"/DPayloadDir={payload_relative}",
            "/Qp",
        ]
    )

    produced = ROOT / "dist" / f"{APP_SLUG}-{version}-windows-x64-setup.exe"
    if not produced.is_file():
        raise SystemExit(f"Inno Setup did not produce {produced}")

    target = args.output_dir / produced.name
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.resolve() != produced.resolve():
        shutil.move(str(produced), str(target))
    require_size(target, minimum_mb=20)
    print(f"Installer build: {target} ({size_of(target)})", flush=True)
    return target


def find_iscc(explicit: str | None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    if os.environ.get("ISCC"):
        candidates.append(Path(os.environ["ISCC"]))
    for name in ("ISCC.exe", "iscc.exe"):
        located = shutil.which(name)
        if located:
            candidates.append(Path(located))

    candidates.extend(iscc_from_registry())

    for variable in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(variable)
        if base:
            candidates.extend(
                sorted(
                    Path(base).glob("Inno Setup*/ISCC.exe"),
                    key=path_version_key,
                    reverse=True,
                )
            )

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    raise SystemExit(
        "Could not locate ISCC.exe (the Inno Setup command-line compiler).\n"
        "Install Inno Setup from https://jrsoftware.org/isdl.php, or pass --iscc <path>."
    )


def path_version_key(path: Path) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", path.parent.name))


def iscc_from_registry() -> list[Path]:
    """Look up Inno Setup installations recorded in the uninstall registry keys."""
    if sys.platform != "win32":
        return []

    import winreg

    results: list[Path] = []
    locations = (
        (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_READ | winreg.KEY_WOW64_32KEY),
        (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_READ | winreg.KEY_WOW64_64KEY),
        (winreg.HKEY_CURRENT_USER, winreg.KEY_READ),
    )
    for hive, access in locations:
        try:
            uninstall = winreg.OpenKey(
                hive,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                0,
                access,
            )
        except OSError:
            continue

        with uninstall:
            index = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(uninstall, index)
                except OSError:
                    break
                index += 1

                try:
                    with winreg.OpenKey(uninstall, subkey_name, 0, access) as subkey:
                        try:
                            display_name = str(winreg.QueryValueEx(subkey, "DisplayName")[0])
                        except OSError:
                            continue
                        if not display_name.lower().startswith("inno setup"):
                            continue
                        try:
                            install_location = str(winreg.QueryValueEx(subkey, "InstallLocation")[0])
                        except OSError:
                            continue
                except OSError:
                    continue

                if install_location:
                    exe = Path(install_location) / "ISCC.exe"
                    if exe.is_file():
                        results.append(exe)
    return results


def smoke_test(binary: Path, timeout: int) -> None:
    """Launch the built application and verify the resources it ships with.

    The normal Windows platform plugin is used (not the offscreen one, which
    breaks the taskbar integration), so a window may appear briefly.
    """
    log("Smoke test: starting the application (a window may appear briefly)")
    profile = ROOT / "build" / "smoke-profile"
    shutil.rmtree(profile, ignore_errors=True)
    appdata = profile / "AppData" / "Roaming"
    temp_dir = profile / "Temp"
    appdata.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    environment = os.environ.copy()
    environment.pop("QT_QPA_PLATFORM", None)
    environment.update(
        {
            "USERPROFILE": str(profile),
            "HOME": str(profile),
            "APPDATA": str(appdata),
            "LOCALAPPDATA": str(profile / "AppData" / "Local"),
            "TEMP": str(temp_dir),
            "TMP": str(temp_dir),
        }
    )

    process = subprocess.Popen([str(binary)], cwd=str(binary.parent), env=environment)
    try:
        resources = wait_for_resources(process, binary, temp_dir, timeout)
        verify_bundled_tools(resources)

        # Let the GUI finish initialising; a crash here means the deployment is
        # not usable even though the files are present.
        time.sleep(5)
        exit_code = process.poll()
        if exit_code is not None:
            raise SystemExit(
                f"Smoke test failed: the application exited with code {exit_code} during startup.\n"
                "The bundled files and tools were verified, so this is a runtime/desktop problem.\n"
                "In sessions without a desktop (CI, services, sandboxes) the Windows taskbar "
                "integration can make the application exit; run this from a normal desktop "
                "session, or omit --smoke-test."
            )
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
        shutil.rmtree(profile, ignore_errors=True)

    log("Smoke test passed: bundled Resources and MKVToolNix binaries are usable")


def wait_for_resources(process: subprocess.Popen, binary: Path, temp_dir: Path, timeout: int) -> Path:
    """Return the folder holding Resources, waiting for a onefile extraction."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        exit_code = process.poll()
        if exit_code is not None:
            raise SystemExit(
                f"Smoke test failed: the application exited with code {exit_code} before "
                "its bundled files were available."
            )

        if (binary.parent / "Resources").is_dir():
            return binary.parent

        for candidate in temp_dir.glob("onefile_*"):
            if (candidate / "Resources").is_dir():
                return candidate

        time.sleep(0.5)

    raise SystemExit(
        f"Smoke test failed: bundled Resources were not found within {timeout}s "
        f"(looked in {binary.parent} and {temp_dir})."
    )


def verify_bundled_tools(resources: Path) -> None:
    """Run the bundled MKVToolNix binaries and check their version output."""
    tools = resources / "Resources" / "Tools" / "Windows64"
    output_file = ROOT / "build" / "smoke-tools.out.txt"

    for name, marker in (
        ("mkvmerge.exe", "mkvmerge v"),
        ("mkvpropedit.exe", "mkvpropedit v"),
    ):
        executable = tools / name
        if not executable.is_file():
            raise SystemExit(f"Smoke test failed: missing bundled tool {executable}")

        with output_file.open("wb") as handle:
            subprocess.run(
                [str(executable), "-V"],
                stdout=handle,
                stderr=subprocess.STDOUT,
                timeout=120,
                check=False,
            )
        output = output_file.read_text(encoding="utf-8", errors="replace")
        if marker not in output:
            raise SystemExit(
                f"Smoke test failed: {name} did not report its version.\n--- output ---\n{output}"
            )
        print(f"  {name}: {output.strip().splitlines()[0]}", flush=True)

    output_file.unlink(missing_ok=True)


def size_of(path: Path) -> str:
    return f"{path.stat().st_size / (1024 * 1024):.1f} MB"


def require_size(path: Path, *, minimum_mb: int) -> None:
    if not path.is_file():
        raise SystemExit(f"Expected artifact not found: {path}")
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb < minimum_mb:
        raise SystemExit(f"Artifact looks too small ({size_mb:.1f} MB): {path}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Windows portable executable and/or the Inno Setup installer.",
    )
    parser.add_argument(
        "--variant",
        choices=("portable", "installer", "all"),
        default="all",
        help="Which artifact(s) to build (default: all).",
    )
    parser.add_argument(
        "--version",
        help="Version to stamp on the artifacts (default: packages/Startup/Version.py).",
    )
    parser.add_argument(
        "--output-dir",
        default="dist",
        help="Directory for the final artifacts, relative to the repository root (default: dist).",
    )
    parser.add_argument(
        "--skip-deps",
        action="store_true",
        help="Do not install missing Python packages; fail instead.",
    )
    parser.add_argument(
        "--nuitka-version",
        default=DEFAULT_NUITKA_VERSION,
        help=f"Nuitka version to install when --skip-deps is not used (default: {DEFAULT_NUITKA_VERSION}).",
    )
    parser.add_argument(
        "--iscc",
        help="Path to ISCC.exe; detected automatically when omitted.",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Start each build (a window appears briefly) and verify its bundled resources and tools.",
    )
    parser.add_argument(
        "--smoke-timeout",
        type=int,
        default=120,
        help="Seconds to wait for the smoke test application to start (default: 120).",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete build/ before starting.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if sys.platform != "win32":
        raise SystemExit("This script builds the Windows artifacts and must run on Windows.")
    if not (ROOT / "main.py").is_file():
        raise SystemExit(f"Could not find main.py; expected the repository at {ROOT}")

    output_dir = Path(args.output_dir)
    args.output_dir = output_dir if output_dir.is_absolute() else ROOT / output_dir

    version = read_version(args.version)
    file_version = numeric_version(version)

    print(f"Python {platform.python_version()} ({sys.executable})", flush=True)
    print(f"Repository: {ROOT}", flush=True)
    print(f"Version: {version} (file version {file_version})", flush=True)
    if sys.version_info[:2] != (3, 12):
        print(
            "WARNING: the project targets Python 3.12; this interpreter may not match requirements.txt.",
            flush=True,
        )

    if args.clean:
        log("Removing build/")
        shutil.rmtree(ROOT / "build", ignore_errors=True)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    ensure_dependencies(args)

    artifacts: list[Path] = []
    if args.variant in ("portable", "all"):
        artifacts.append(build_portable(args, version))
    if args.variant in ("installer", "all"):
        artifacts.append(build_installer(args, version))

    print("\nBuilt artifacts:", flush=True)
    for artifact in artifacts:
        print(f"  {artifact} ({size_of(artifact)})", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
