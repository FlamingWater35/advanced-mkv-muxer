import importlib
import sys
import unittest
from pathlib import Path

import tests  # noqa: F401  (must run before application imports)

from packages.Startup.GlobalFiles import (
    AppDataFolderPath,
    AppLogFilePath,
    MKVMERGE_VERSION,
    MKVPROPEDIT_VERSION,
    create_app_data_folder,
)
from packages.Startup.Version import Version
from tests import ROOT, TEMP_ROOT
from tests.support import FakeTaskBarProgress, read_settings, reset_options

# Modules that only exist on Windows: they import comtypes, which wraps the
# Windows taskbar COM API, and one of them is a generated file encoded as mbcs,
# which is not a codec on Linux. The release build excludes exactly these with
# --nofollow-import-to (see .github/workflows/release.yml), so importing them
# unconditionally made this test fail on a correct Linux install.
WINDOWS_ONLY_MODULES = {
    "packages.MainWindow",
    "packages.Widgets.TaskBarProgress",
    "packages.Widgets.WindowsTaskBar",
    "packages.Widgets.WindowsTaskBarLib",
}


def is_available_on_this_platform(module_name):
    if sys.platform == "win32":
        return True
    return module_name not in WINDOWS_ONLY_MODULES


class ApplicationStartupTests(unittest.TestCase):
    def test_config_folder_exists(self):
        config_path = Path(AppDataFolderPath)
        self.assertTrue(config_path.is_dir())
        self.assertTrue(config_path.is_relative_to(TEMP_ROOT))
        self.assertTrue(Path(AppLogFilePath).is_relative_to(config_path))

    def test_config_subfolders_and_setting_file_exist(self):
        config_path = Path(AppDataFolderPath)
        self.assertTrue((config_path / "Logs").is_dir())
        self.assertTrue((config_path / "MediaInfo").is_dir())
        self.assertTrue((config_path / "setting.json").is_file())

    def test_create_app_data_folder_returns_config_location(self):
        self.assertEqual(Path(create_app_data_folder()), Path(AppDataFolderPath))

    def test_setting_file_contains_theme_preference(self):
        self.assertIn("Dark_Mode", read_settings())

    def test_portable_mkvtoolnix_is_detected(self):
        self.assertIn("mkvmerge", MKVMERGE_VERSION.lower())
        self.assertIn("mkvpropedit", MKVPROPEDIT_VERSION.lower())

    def test_version_format(self):
        self.assertRegex(Version, r"^\d+\.\d+\.\d+$")

    def test_every_module_imports(self):
        failures = []
        for path in sorted((ROOT / "packages").rglob("*.py")):
            relative = path.relative_to(ROOT).with_suffix("")
            if path.name == "__init__.py":
                module_name = ".".join(relative.parts[:-1])
            else:
                module_name = ".".join(relative.parts)
            if not is_available_on_this_platform(module_name):
                continue
            try:
                importlib.import_module(module_name)
            except Exception as exc:  # pragma: no cover - reported below
                failures.append(f"{module_name}: {exc!r}")
        self.assertEqual(failures, [])


class MainWindowTests(unittest.TestCase):
    def setUp(self):
        reset_options(dark_mode=True)

    def test_main_window_constructs_with_expected_ui(self):
        # The two window classes differ only in the taskbar integration and the
        # platform title bar, so the same UI expectations apply to both.
        if sys.platform == "win32":
            import packages.MainWindow as main_window_module

            window_class = main_window_module.MainWindow
            original_task_bar = main_window_module.TaskBarProgress
            main_window_module.TaskBarProgress = FakeTaskBarProgress
        else:
            import packages.MainWindowNonWindowsSystem as main_window_module

            window_class = main_window_module.MainWindowNonWindowsSystem
            original_task_bar = None
        try:
            window = window_class([str(ROOT / "main.py")])
            try:
                self.assertEqual(window.windowTitle(), f"Advanced MKV Muxer v{Version}")
                self.assertTrue(window.isVisible())
                self.assertEqual(window.tabs.count(), 6)
                self.assertEqual(
                    [window.tabs.tabText(index) for index in range(6)],
                    ["Videos", "Subtitles", "Audios", "Chapters", "Attachments", "Mux Setting"],
                )
                self.assertEqual(window.tabs.theme_button.toolTip(), "Switch To Light Mode")
            finally:
                window.close()
        finally:
            if original_task_bar is not None:
                main_window_module.TaskBarProgress = original_task_bar
