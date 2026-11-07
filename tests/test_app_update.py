import json
import unittest
from unittest import mock

import tests  # noqa: F401  (must run before application imports)

from packages.Startup.Version import Version
from packages.Tabs.SettingTab.SettingDialog import SettingDialog
from packages.ToolUpdates import AppUpdateChecker
from packages.ToolUpdates.AppUpdateChecker import AppUpdateStatus
from packages.ToolUpdates.MkvToolNixUpdater import UpdateError

API_PAYLOAD = json.dumps({
    "tag_name": "v2.7.0",
    "name": "Advanced MKV Muxer 2.7.0",
    "html_url": "https://github.com/FlamingWater35/advanced-mkv-muxer/releases/tag/v2.7.0",
    "body": "## Changes\n- Something new",
})

ATOM_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>tag:github.com,2008:Repository/1/v2.7.0</id>
    <link rel="alternate" type="text/html"
          href="https://github.com/FlamingWater35/advanced-mkv-muxer/releases/tag/v2.7.0"/>
    <title>Advanced MKV Muxer 2.7.0</title>
  </entry>
  <entry>
    <id>tag:github.com,2008:Repository/1/v2.6.9</id>
    <link rel="alternate" type="text/html"
          href="https://github.com/FlamingWater35/advanced-mkv-muxer/releases/tag/v2.6.9"/>
    <title>Advanced MKV Muxer 2.6.9</title>
  </entry>
</feed>
"""


class ReleaseParsingTests(unittest.TestCase):
    def test_reads_the_github_api_release(self):
        release = AppUpdateChecker.release_from_github_api(API_PAYLOAD)
        self.assertEqual(release.version, "2.7.0")
        self.assertEqual(
            release.url,
            "https://github.com/FlamingWater35/advanced-mkv-muxer/releases/tag/v2.7.0",
        )
        self.assertEqual(release.name, "Advanced MKV Muxer 2.7.0")

    def test_api_payload_without_a_version_is_ignored(self):
        self.assertIsNone(AppUpdateChecker.release_from_github_api(json.dumps({"tag_name": "nightly"})))

    def test_reads_the_newest_release_from_the_atom_feed(self):
        release = AppUpdateChecker.release_from_releases_atom(ATOM_FEED)
        self.assertEqual(release.version, "2.7.0")
        self.assertEqual(
            release.url,
            "https://github.com/FlamingWater35/advanced-mkv-muxer/releases/tag/v2.7.0",
        )

    def test_empty_atom_feed_returns_none(self):
        self.assertIsNone(AppUpdateChecker.release_from_releases_atom("<feed></feed>"))


class LatestReleaseTests(unittest.TestCase):
    def test_api_is_used_first(self):
        requested = []

        def fetch(url):
            requested.append(url)
            return API_PAYLOAD

        release = AppUpdateChecker.latest_release(fetch_text=fetch)
        self.assertEqual(release.version, "2.7.0")
        self.assertEqual(requested, [AppUpdateChecker.RELEASES_API_URL])

    def test_atom_feed_is_the_fallback(self):
        def fetch(url):
            if url == AppUpdateChecker.RELEASES_API_URL:
                raise OSError("rate limited")
            return ATOM_FEED

        self.assertEqual(AppUpdateChecker.latest_release(fetch_text=fetch).version, "2.7.0")

    def test_all_errors_are_reported(self):
        def fetch(url):
            raise OSError("network down")

        with self.assertRaises(UpdateError) as context:
            AppUpdateChecker.latest_release(fetch_text=fetch)
        self.assertIn("network down", str(context.exception))


class CheckForAppUpdateTests(unittest.TestCase):
    def test_newer_release_is_detected(self):
        status = AppUpdateChecker.check_for_app_update(
            "2.6.3", fetch_text=lambda url: API_PAYLOAD
        )
        self.assertTrue(status.update_available)
        self.assertEqual(status.latest, "2.7.0")
        self.assertEqual(
            status.release_url,
            "https://github.com/FlamingWater35/advanced-mkv-muxer/releases/tag/v2.7.0",
        )

    def test_current_release_is_reported_as_up_to_date(self):
        status = AppUpdateChecker.check_for_app_update(
            "2.7.0", fetch_text=lambda url: API_PAYLOAD
        )
        self.assertFalse(status.update_available)

    def test_older_published_release_is_not_an_update(self):
        status = AppUpdateChecker.check_for_app_update(
            "2.8.0", fetch_text=lambda url: API_PAYLOAD
        )
        self.assertFalse(status.update_available)


class AppUpdateSectionTests(unittest.TestCase):
    def setUp(self):
        from tests.support import reset_options

        reset_options(dark_mode=False)
        self.dialog = SettingDialog()
        self.section = self.dialog.app_update_groupBox

    def tearDown(self):
        self.dialog.close()

    def test_shows_the_installed_version(self):
        self.assertEqual(self.section.installed_version_label.text(), str(Version))
        self.assertTrue(self.section.release_button.isHidden())

    def test_update_shows_the_version_and_the_release_button(self):
        self.section.apply_check_result(AppUpdateStatus(
            current="2.6.3",
            latest="2.7.0",
            update_available=True,
            release_url="https://example.invalid/release",
        ))
        self.assertIn("2.7.0", self.section.status_label.text())
        self.assertFalse(self.section.release_button.isHidden())
        self.assertTrue(self.section.release_button.isEnabled())

    def test_up_to_date_hides_the_release_button(self):
        self.section.apply_check_result(AppUpdateStatus(
            current="2.7.0",
            latest="2.7.0",
            update_available=False,
            release_url="https://example.invalid/release",
        ))
        self.assertIn("Up to date", self.section.status_label.text())
        self.assertTrue(self.section.release_button.isHidden())

    def test_release_button_opens_the_release_page(self):
        self.section.apply_check_result(AppUpdateStatus(
            current="2.6.3",
            latest="2.7.0",
            update_available=True,
            release_url="https://example.invalid/release",
        ))
        with mock.patch(
            "packages.Tabs.SettingTab.Widgets.AppUpdateGroupBox.QDesktopServices.openUrl"
        ) as open_url:
            self.section.open_release_page()
        self.assertEqual(open_url.call_args.args[0].toString(), "https://example.invalid/release")

    def test_release_button_does_nothing_without_a_url(self):
        with mock.patch(
            "packages.Tabs.SettingTab.Widgets.AppUpdateGroupBox.QDesktopServices.openUrl"
        ) as open_url:
            self.section.open_release_page()
        open_url.assert_not_called()

    def test_errors_are_reported(self):
        self.section.apply_error("network down")
        self.assertIn("network down", self.section.status_label.text())

    def test_window_cannot_be_closed_while_checking(self):
        self.section.worker = object()  # simulate a running check
        try:
            self.dialog.click_no()
            self.assertIn("Please wait", self.section.status_label.text())
        finally:
            self.section.worker = None

    def test_check_uses_the_app_checker(self):
        statuses = []

        class FakeWorker:
            def __init__(self, action, current_version):
                self.checked_signal = mock.MagicMock()
                self.checked_signal.connect = statuses.append
                self.error_signal = mock.MagicMock()
                self.error_signal.connect = lambda function: None
                self.finished = mock.MagicMock()
                self.finished.connect = lambda function: None

            def start(self):
                pass

        self.section.worker_factory = FakeWorker
        self.section.start_check()
        try:
            self.assertIsInstance(self.section.worker, FakeWorker)
            self.assertFalse(self.section.check_button.isEnabled())
        finally:
            self.section.worker = None
            self.section.set_busy(False)
