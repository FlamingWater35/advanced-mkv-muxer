import unittest
from unittest import mock

import tests  # noqa: F401  (must run before application imports)

from packages.Startup import GlobalFiles
from packages.Startup.GlobalFiles import MKVMERGE_VERSION, MKVPROPEDIT_VERSION
from packages.Startup.Options import Options
from packages.Startup.Version import Version
from packages.Tabs.SettingTab.SettingDialog import SettingDialog
from packages.Tabs.SettingTab.Widgets.AboutDialog import AboutDialog
from packages.ToolUpdates import MkvToolNixUpdater
from packages.ToolUpdates.MkvToolNixUpdater import UpdateStatus
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


class ToolsUpdateSectionTests(unittest.TestCase):
    def setUp(self):
        reset_options(dark_mode=False)
        self.dialog = SettingDialog()
        self.section = self.dialog.tools_update_groupBox

    def tearDown(self):
        self.dialog.close()

    def test_shows_the_installed_versions(self):
        expected_merge = MkvToolNixUpdater.parse_version(GlobalFiles.MKVMERGE_VERSION) or "not found"
        expected_propedit = MkvToolNixUpdater.parse_version(GlobalFiles.MKVPROPEDIT_VERSION) or "not found"
        self.assertEqual(self.section.mkvmerge_version_label.text(), expected_merge)
        self.assertEqual(self.section.mkvpropedit_version_label.text(), expected_propedit)
        self.assertFalse(self.section.update_button.isEnabled())

    def test_update_available_enables_the_update_button(self):
        self.section.apply_check_result(
            UpdateStatus(current="81.0", latest="103.0", update_available=True)
        )
        self.assertIn("103.0", self.section.status_label.text())
        self.assertTrue(self.section.update_button.isEnabled())

    def test_up_to_date_disables_the_update_button(self):
        self.section.apply_check_result(
            UpdateStatus(current="103.0", latest="103.0", update_available=False)
        )
        self.assertIn("Up to date", self.section.status_label.text())
        self.assertFalse(self.section.update_button.isEnabled())

    def test_update_refreshes_the_version_labels(self):
        with mock.patch.object(GlobalFiles, "refresh_tools", lambda: None), \
                mock.patch.object(GlobalFiles, "MKVMERGE_VERSION", "mkvmerge v103.0 ('Milliontown') 64-bit"), \
                mock.patch.object(GlobalFiles, "MKVPROPEDIT_VERSION", "mkvpropedit v103.0 ('Milliontown') 64-bit"):
            self.section.apply_update_result("103.0")

        self.assertEqual(self.section.mkvmerge_version_label.text(), "103.0")
        self.assertEqual(self.section.mkvpropedit_version_label.text(), "103.0")
        self.assertIn("103.0", self.section.status_label.text())
        self.assertFalse(self.section.update_button.isEnabled())

    def test_errors_are_reported(self):
        self.section.current_action = "check"
        self.section.apply_error("network down")
        self.assertIn("network down", self.section.status_label.text())

    def test_window_cannot_be_closed_while_updating(self):
        self.section.worker = object()  # simulate a running update
        try:
            self.dialog.click_no()
            self.assertIn("Please wait", self.section.status_label.text())
        finally:
            self.section.worker = None
