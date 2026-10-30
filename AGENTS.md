# AGENTS.md

Instructions for coding agents working in this repository.

## Project

**Advanced MKV Muxer** is a PySide6 (Qt 6) desktop application that batch-muxes
video files with subtitles, audio tracks, chapters and attachments through
[MKVToolNix](https://mkvtoolnix.download/). It is a maintained fork of
[MKV Muxing Batch GUI](https://github.com/yaser01/mkv-muxing-batch-gui).

- Entry point: `main.py` → `MainApplication` (one `QApplication`) → `MainWindow`
  (Windows) or `MainWindowNonWindowsSystem` (Linux).
- Python **3.12** (enforced by the test suite), PySide6 **6.6.1**, psutil, and
  comtypes (Windows only). The legacy 32-bit/PySide2 variant lives on the
  `develop-PySide2` branch.
- Supported targets: Windows (release builds are x64) and Linux; macOS is not a
  supported target.
- License: GPL-2.0 (`LICENSE`). Preserve the upstream attribution and credits
  in the README.

## Setup

```powershell
python -m pip install -r requirements.txt
python main.py
```

The app needs a desktop session to open a window. `QT_QPA_PLATFORM=offscreen`
works for headless smoke runs and is what the tests use.

A ready-made local environment may exist at `.conda/` (Python 3.12 with the
requirements installed); use `.\.conda\python.exe` if present so the version
matches `requirements.txt`.

## Tests

```powershell
python -m unittest discover -s tests -t . -v
```

- Always run from the repository root. The suite has ~88 tests and takes a few
  seconds.
- `tests/__init__.py` is a bootstrap that **must run before any application
  import**: it creates an isolated profile under `tests/.tmp/<run>/`, redirects
  `HOME`/`APPDATA`/`LOCALAPPDATA`/`TEMP` there, forces
  `QT_QPA_PLATFORM=offscreen`, points `sys.argv[0]` at the repo's `main.py`
  (resources are resolved from it) and creates the shared `QApplication`. Every
  test module starts with `import tests  # noqa: F401`.
- Never let a test touch the real `%APPDATA%\Advanced MKV Muxer` profile. Use
  `tests.support.reset_options()`, `write_settings()` and `read_settings()`.
- `tests/test_application.py::test_every_module_imports` imports every module
  under `packages/`, so a broken import anywhere fails the suite.
- `tests/test_dependencies.py` asserts the exact versions from
  `requirements.txt`, Python 3.12 and `pip check` cleanliness.
- `tests/.tmp/` is gitignored and removed when the run ends.
- No linter or formatter is configured; match the surrounding style.

## Build and release

Windows artifacts (must run on Windows):

```powershell
python scripts/build_windows.py                      # portable + installer
python scripts/build_windows.py --variant portable   # single .exe (Nuitka onefile)
python scripts/build_windows.py --variant installer  # Inno Setup installer
python scripts/build_windows.py --skip-deps --smoke-test --clean
```

- Outputs land in `dist/`:
  `Advanced-MKV-Muxer-<version>-windows-x64-portable.exe` and
  `...-windows-x64-setup.exe`.
- Nuitka is pinned to `4.3.1` in the script and the workflow. The installer
  needs Inno Setup 6.3+ (`ISCC.exe`, auto-detected or `--iscc`); it installs
  per user into `%LOCALAPPDATA%\Programs\Advanced MKV Muxer` with no UAC.
- Bundled data is added with `--include-data-dir` for `Resources/{Fonts,Icons,
  Languages,DLL}`. Files that `--include-data-dir` silently skips (it treats
  them as code) must be added with `--include-data-files` instead: the Windows
  MKVToolNix `.exe` files, and `Resources/Tools/Linux/lib/*` on Linux, where
  the bundled tools link against those `.so` files. Omitting the Linux
  libraries makes the shipped build die at start-up with a SIGSEGV.
- CI (`.github/workflows/release.yml`) builds four assets — Windows portable,
  Windows installer, Linux tarball, Linux AppImage — for a tag `v*`/`[0-9]*`
  that is reachable from `main`, then creates a **draft** release. Linux
  packaging exists only in CI (Nuitka standalone + AppRun/AppImage); there is no
  local Linux build script.
- The release version comes from the tag. Bump `packages/Startup/Version.py`
  (`Version = "x.y.z"`, shown in the window title and About dialog) in the same
  change; CI only warns when it disagrees with the tag.

## Layout

```
main.py                     app bootstrap: logging, font, window, child cleanup
packages/
  Startup/                  app-wide singletons and constants
    GlobalFiles.py          resource paths, app-data dirs, tool discovery/versions
    MainApplication.py      the single QApplication (+ palette)
    Options.py              presets/settings state, save_options/read_option_file
    PreDefined.py           extensions, track ids, ISO-639 language tables
    Version.py              displayed application version
    ColorThems.py / SetupThems.py / SystemTheme.py / GlobalIcons.py
  Tabs/                     one package per tab, orchestrated by *Selection/*Manager
    VideoTab/ SubtitleTab/ AudioTab/ ChapterTab/ AttachmentTab/
    MuxSetting/             job queue + mkvmerge/mkvpropedit job generation
    SettingTab/             presets, defaults, tools update, About
    GlobalSetting.py        state shared between tabs (selected files, options)
    TabsManager.py          tab widget, signals, theme switching
  Widgets/                  shared widgets, dialogs, data classes
  ToolUpdates/              Qt-free MKVToolNix release check/download/install
Resources/                  Fonts, Icons, Languages, DLL (taskbar), Tools/<platform>
scripts/build_windows.py    Nuitka + Inno Setup build
installer/                  Inno Setup .iss and Linux AppRun/.desktop
tests/                      unittest suite
```

## How muxing works

`MuxSetting` builds a queue of `SingleJobData` jobs and `StartMuxingWorker`
runs them. For each job `GetJsonForMkvmergeJob` (and, when only metadata
changes, `GetJsonForMkvpropeditJob`) writes a MKVToolNix **JSON job file** into
the app-data folder; the tools are invoked as `mkvmerge @"<job>.json"` /
`mkvpropedit @"<job>.json"` (see `StartMuxingWorker.start_mkvmerge_muxing`).
Progress and errors are parsed from the tool log by the
`ReadFrom*LogWorker` classes; CRC calculation is optional per job.

| I want to… | Look at |
| --- | --- |
| add/change an mkvmerge option | `Tabs/MuxSetting/Widgets/GetJsonForMkvmergeJob.py` |
| change in-place metadata editing | `Tabs/MuxSetting/Widgets/GetJsonForMkvpropeditJob.py` |
| change queue/progress behaviour | `Tabs/MuxSetting/MuxSetting.py`, `StartMuxingWorker.py`, `StartMuxingProcessWorker.py` |
| change track discovery | `Tabs/GlobalSetting.py::refresh_tracks` (uses `mkvmerge -J`, cached in `MediaInfo/`) |
| add a persisted setting | `Startup/Options.py` (`save_options` + `read_option_file`) and `tests/support.py` |
| change the tool updater | `packages/ToolUpdates/` (keep it Qt-free) + `SettingTab/Widgets/ToolsUpdateGroupBox.py` |
| change theming | `Startup/ColorThems.py`, `SetupThems.py`, `SystemTheme.py` |
| change packaging | `scripts/build_windows.py`, `installer/`, `.github/workflows/release.yml` |

## Conventions

- Absolute imports only: `from packages.Startup.GlobalFiles import ...`.
  Modules import the shared singletons (`GlobalFiles`, `Options`,
  `GlobalSetting`) directly; module-level state is normal here.
- `packages/` mostly uses implicit namespace packages (no `__init__.py`). Don't
  rename or reshuffle packages; only `packages/ToolUpdates` and `tests` have
  `__init__.py`.
- Dialogs subclass `packages.Widgets.MyDialog.MyDialog`, build their widgets in
  `__init__`, and expose `execute()` for modal use (`self.exec()`), sometimes
  `execute_wth_no_block()`. Outcomes are stored on attributes (`self.result`,
  `chosen_index`, …) rather than returned.
- Windows-only code (taskbar integration, `comtypes`, `MainWindow`) must stay
  behind `sys.platform == "win32"`; the Linux build excludes those modules with
  `--nofollow-import-to`. Keep `packages/ToolUpdates` free of Qt imports.
- One widget per file, named after its role (`AudioDelayDoubleSpinBox`,
  `SubtitleLanguageComboBox`, `ConfirmUsingMkvpropedit`); tab-level containers
  live in `*Selection.py` / `*TabManager.py`.
- Style: 4-space indents, double quotes, `snake_case` functions/attributes,
  `CamelCase` classes. Type hints are rare outside `ToolUpdates/`.

## Gotchas

- **`GlobalFiles` has import-time side effects.** Importing anything under
  `packages/` creates the app-data folders, clears the MediaInfo cache, locates
  `mkvmerge`/`mkvpropedit`, and queries their versions. A missing tool is
  recorded in `GlobalFiles.StartupError` instead of raising, because a
  `QMessageBox` cannot be built before `QApplication` exists; `main.py` calls
  `GlobalFiles.show_startup_error_if_any()` right after creating the
  application to show `MissingFilesMessage`. This is why tests set up the
  environment before importing and why `sys.argv[0]` matters.
- Tool lookup order: `%APPDATA%\Advanced MKV Muxer\Tools\<Platform>` (written by
  the in-app updater) when both binaries exist → `Resources/Tools/<Platform>`
  → `PATH`. `refresh_tools()` re-resolves and re-queries after an update.
- Never hardcode resource paths; use the `GlobalFiles` constants. The bundle
  root comes from `sys.argv[0]`, or from Nuitka's `__compiled__` in frozen
  builds.
- `Resources/Tools/**` binaries are committed (mkvmerge, mkvpropedit and their
  licenses). Don't delete or rewrite them; replacing them is a bundled-tool
  version bump. User-installed updates go to the app-data folder, never into the
  repo.
- `setting.json` lives in the user's app data, not the repo. A new persisted
  field needs a default in `read_option_file()` and an entry in `save_options()`.
- Adding a dependency means updating the pin in `requirements.txt` and the
  environment, otherwise `tests/test_dependencies.py` fails.
- Commands are assembled as strings with the quoting helpers
  (`add_double_quotation`, `add_json_line` in `GetJsonForMkvmergeJob`); paths can
  contain spaces, so keep that quoting intact.

## Before finishing

Run `python -m unittest discover -s tests -t . -v` from the repository root and
make sure all tests pass. Leave `packages/Startup/Version.py` alone unless the
change is a release.
