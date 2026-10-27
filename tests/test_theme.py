import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tests  # noqa: F401  (must run before application imports)

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette

from packages.Startup import ColorThems, SystemTheme
from packages.Startup.GlobalFiles import SettingJsonInfoFilePath
from packages.Startup.MainApplication import MainApplication
from packages.Startup.Options import Options, read_option_file, save_options
from packages.Startup.SetupThems import get_dark_palette, get_light_palette
from packages.Widgets.ThemeButton import ThemeButton
from tests import ROOT, TEMP_ROOT
from tests.support import read_settings, reset_options, write_settings


class _FakeStyleHints:
    def __init__(self, color_scheme):
        self._color_scheme = color_scheme

    def colorScheme(self):
        return self._color_scheme


class _FakeApp:
    def __init__(self, color_scheme):
        self._hints = _FakeStyleHints(color_scheme)

    def styleHints(self):
        return self._hints


class _FakeQGuiApplication:
    current = None

    @classmethod
    def instance(cls):
        return cls.current


class SystemThemeDetectionTests(unittest.TestCase):
    def test_qt_dark_scheme(self):
        with patch.object(SystemTheme, "QGuiApplication", _FakeQGuiApplication):
            _FakeQGuiApplication.current = _FakeApp(Qt.ColorScheme.Dark)
            self.assertTrue(SystemTheme.detect_system_dark_mode())

    def test_qt_light_scheme(self):
        with patch.object(SystemTheme, "QGuiApplication", _FakeQGuiApplication):
            _FakeQGuiApplication.current = _FakeApp(Qt.ColorScheme.Light)
            self.assertFalse(SystemTheme.detect_system_dark_mode())

    def test_unknown_qt_scheme_uses_registry_fallback(self):
        with patch.object(SystemTheme, "QGuiApplication", _FakeQGuiApplication), \
                patch.object(SystemTheme, "detect_windows_dark_mode", return_value=True):
            _FakeQGuiApplication.current = _FakeApp(Qt.ColorScheme.Unknown)
            self.assertTrue(SystemTheme.detect_system_dark_mode())

    def test_unknown_qt_scheme_falls_back_to_light(self):
        with patch.object(SystemTheme, "QGuiApplication", _FakeQGuiApplication), \
                patch.object(SystemTheme, "detect_windows_dark_mode", return_value=None):
            _FakeQGuiApplication.current = _FakeApp(Qt.ColorScheme.Unknown)
            self.assertFalse(SystemTheme.detect_system_dark_mode())

    def test_windows_registry_dark_value(self):
        with patch.object(SystemTheme.sys, "platform", "win32"), \
                patch.object(SystemTheme, "_read_windows_personalize_value", side_effect=[0]):
            self.assertTrue(SystemTheme.detect_windows_dark_mode())

    def test_windows_registry_light_value(self):
        with patch.object(SystemTheme.sys, "platform", "win32"), \
                patch.object(SystemTheme, "_read_windows_personalize_value", side_effect=[1]):
            self.assertFalse(SystemTheme.detect_windows_dark_mode())

    def test_windows_registry_prefers_apps_theme_then_system_theme(self):
        with patch.object(SystemTheme.sys, "platform", "win32"), \
                patch.object(SystemTheme, "_read_windows_personalize_value", side_effect=[None, 0]):
            self.assertTrue(SystemTheme.detect_windows_dark_mode())

    def test_windows_registry_unknown_values(self):
        with patch.object(SystemTheme.sys, "platform", "win32"), \
                patch.object(SystemTheme, "_read_windows_personalize_value", side_effect=[None, None]):
            self.assertIsNone(SystemTheme.detect_windows_dark_mode())

    def test_non_windows_has_no_registry_fallback(self):
        with patch.object(SystemTheme.sys, "platform", "linux"):
            self.assertIsNone(SystemTheme.detect_windows_dark_mode())

    def test_detection_returns_a_boolean(self):
        self.assertIn(SystemTheme.detect_system_dark_mode(), (True, False))


class PaletteTests(unittest.TestCase):
    def test_light_palette(self):
        palette = get_light_palette()
        self.assertEqual(palette.color(QPalette.Window).getRgb(), ColorThems.Light_Window_Color)
        self.assertEqual(palette.color(QPalette.Base).getRgb(), ColorThems.Light_Base_Color)
        self.assertEqual(palette.color(QPalette.WindowText).getRgb(), ColorThems.Light_WindowText_Color)

    def test_dark_palette(self):
        palette = get_dark_palette()
        self.assertEqual(palette.color(QPalette.Window).getRgb(), ColorThems.Dark_Window_Color)
        self.assertEqual(palette.color(QPalette.Base).getRgb(), ColorThems.Dark_Base_Color)
        self.assertEqual(palette.color(QPalette.WindowText).getRgb(), ColorThems.Dark_WindowText_Color)


class ThemePreferenceTests(unittest.TestCase):
    def setUp(self):
        reset_options()

    def test_saved_dark_theme_is_used(self):
        write_settings({"Dark_Mode": True})
        with patch("packages.Startup.Options.detect_system_dark_mode", return_value=False) as detect:
            read_option_file(SettingJsonInfoFilePath)
            detect.assert_not_called()
        self.assertTrue(Options.Dark_Mode)

    def test_saved_light_theme_is_used(self):
        write_settings({"Dark_Mode": False})
        with patch("packages.Startup.Options.detect_system_dark_mode", return_value=True) as detect:
            read_option_file(SettingJsonInfoFilePath)
            detect.assert_not_called()
        self.assertFalse(Options.Dark_Mode)

    def test_missing_config_detects_system_theme(self):
        missing_file = TEMP_ROOT / "missing-settings.json"
        self.assertFalse(missing_file.exists())
        with patch("packages.Startup.Options.detect_system_dark_mode", return_value=True):
            read_option_file(str(missing_file))
        self.assertTrue(Options.Dark_Mode)
        self.assertTrue(Path(SettingJsonInfoFilePath).is_file())
        self.assertTrue(read_settings()["Dark_Mode"])

    def test_missing_config_falls_back_to_light(self):
        missing_file = TEMP_ROOT / "missing-settings-light.json"
        with patch("packages.Startup.Options.detect_system_dark_mode", return_value=False):
            read_option_file(str(missing_file))
        self.assertFalse(Options.Dark_Mode)
        self.assertFalse(read_settings()["Dark_Mode"])

    def test_config_without_theme_key_detects_system_theme(self):
        write_settings({"FavoritePresetId": 0})
        with patch("packages.Startup.Options.detect_system_dark_mode", return_value=True):
            read_option_file(SettingJsonInfoFilePath)
        self.assertTrue(Options.Dark_Mode)
        self.assertTrue(read_settings()["Dark_Mode"])

    def test_settings_file_with_utf8_bom_is_accepted(self):
        path = TEMP_ROOT / "bom-settings.json"
        path.write_bytes(b"\xef\xbb\xbf" + json.dumps({"Dark_Mode": True}).encode("utf-8"))
        read_option_file(str(path))
        self.assertTrue(Options.Dark_Mode)

    def test_save_options_persists_theme_choice(self):
        reset_options(dark_mode=True)
        save_options()
        self.assertTrue(read_settings()["Dark_Mode"])


class ThemeButtonTests(unittest.TestCase):
    def setUp(self):
        reset_options(dark_mode=False)
        write_settings({"Dark_Mode": False})
        self.button = ThemeButton()

    def tearDown(self):
        self.button.close()

    def test_initial_tooltip_matches_light_mode(self):
        self.assertEqual(self.button.toolTip(), "Switch To Dark Mode")

    def test_click_switches_to_dark_and_saves(self):
        emitted = []
        self.button.dark_mode_updated_signal.connect(lambda: emitted.append(True))
        self.button.click()
        self.assertTrue(Options.Dark_Mode)
        self.assertEqual(self.button.toolTip(), "Switch To Light Mode")
        self.assertEqual(len(emitted), 1)
        self.assertEqual(
            MainApplication.palette().color(QPalette.Window).getRgb(),
            ColorThems.Dark_Window_Color,
        )
        self.assertTrue(read_settings()["Dark_Mode"])

    def test_second_click_switches_back_to_light(self):
        self.button.click()
        self.button.click()
        self.assertFalse(Options.Dark_Mode)
        self.assertEqual(self.button.toolTip(), "Switch To Dark Mode")
        self.assertEqual(
            MainApplication.palette().color(QPalette.Window).getRgb(),
            ColorThems.Light_Window_Color,
        )
        self.assertFalse(read_settings()["Dark_Mode"])


class StartupThemeTests(unittest.TestCase):
    def _run_application(self, settings=None):
        home = Path(tempfile.mkdtemp(prefix="startup-", dir=TEMP_ROOT))
        appdata = home / "AppData" / "Roaming"
        config_folder = appdata / "Advanced MKV Muxer"
        config_folder.mkdir(parents=True)
        if settings is not None:
            write_settings(settings, config_folder / "setting.json")
        local_appdata = home / "AppData" / "Local"
        local_appdata.mkdir(parents=True)
        temp_folder = home / "tmp"
        temp_folder.mkdir()

        env = os.environ.copy()
        env.update({
            "USERPROFILE": str(home),
            "HOME": str(home),
            "APPDATA": str(appdata),
            "LOCALAPPDATA": str(local_appdata),
            "TMPDIR": str(temp_folder),
            "TEMP": str(temp_folder),
            "TMP": str(temp_folder),
            "QT_QPA_PLATFORM": "offscreen",
        })
        code = (
            "from packages.Startup.MainApplication import MainApplication;"
            "from packages.Startup.Options import Options;"
            "from PySide6.QtGui import QPalette;"
            "print(int(Options.Dark_Mode),"
            "MainApplication.palette().color(QPalette.Window).name())"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip().splitlines()[-1]

    def test_manual_dark_theme_survives_restart(self):
        self.assertEqual(self._run_application({"Dark_Mode": True}), "1 #353535")

    def test_manual_light_theme_survives_restart(self):
        self.assertEqual(self._run_application({"Dark_Mode": False}), "0 #f0f0f0")

    def test_first_startup_uses_system_theme(self):
        expected_dark = SystemTheme.detect_system_dark_mode()
        expected_window = "#353535" if expected_dark else "#f0f0f0"
        self.assertEqual(
            self._run_application(),
            f"{int(expected_dark)} {expected_window}",
        )
