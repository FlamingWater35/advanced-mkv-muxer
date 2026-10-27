import unittest

import tests  # noqa: F401  (must run before application imports)

from packages.Startup.GlobalFiles import MKVMERGE_VERSION, MKVPROPEDIT_VERSION
from packages.Startup.Options import Options
from packages.Startup.Version import Version
from packages.Tabs.SettingTab.SettingDialog import SettingDialog
from packages.Tabs.SettingTab.Widgets.AboutDialog import AboutDialog
from tests.support import read_settings, reset_options


class AboutDialogTests(unittest.TestCase):
    def setUp(self):
        reset_options()
        self.dialog = AboutDialog()

    def tearDown(self):
        self.dialog.close()

    def test_shows_current_versions(self):
        self.assertIn(str(Version), self.dialog.app_current_version.text())
        self.assertIn(str(MKVMERGE_VERSION), self.dialog.app_mkvmerge_current_version.text())
        self.assertIn(str(MKVPROPEDIT_VERSION), self.dialog.app_mkvpropedit_current_version.text())


class SettingDialogTests(unittest.TestCase):
    def setUp(self):
        reset_options(dark_mode=False)
        self.dialog = SettingDialog()

    def tearDown(self):
        self.dialog.close()

    def test_preset_controls_exist(self):
        self.assertGreaterEqual(self.dialog.preset_tab_comboBox.count(), 1)
        self.assertIsNotNone(self.dialog.preset_tab_delete_button)
        self.assertIsNotNone(self.dialog.preset_tab_rename_button)

    def test_cancel_does_not_save_ask_on_startup(self):
        self.dialog.preset_tab_ask_on_start_check_box.setChecked(True)
        self.dialog.click_no()
        self.assertFalse(Options.Choose_Preset_On_Startup)

    def test_ok_saves_ask_on_startup(self):
        self.dialog.preset_tab_ask_on_start_check_box.setChecked(True)
        self.dialog.click_yes()
        self.assertTrue(Options.Choose_Preset_On_Startup)
        self.assertTrue(read_settings()["Choose_Preset_On_Startup"])
