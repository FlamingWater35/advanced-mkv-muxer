"""Regression tests for settings-file robustness.

``read_option_file`` runs at import time from ``MainApplication``, before any
window exists. An unreadable ``setting.json`` used to raise straight out of
``json.load`` and kill the process with a bare traceback:

    json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)

That is the signature of a zero-byte file, which ``save_options`` could leave
behind because it opened the real file with ``"w"`` (truncating it) before
writing. Saving is now atomic and reading tolerates a damaged file.
"""

import json
import tempfile
import unittest
from pathlib import Path

import tests  # noqa: F401  (must run before application imports)

from packages.Startup.Options import Options, read_option_file, save_options
from tests.support import read_settings, reset_options


class CorruptSettingsFileTests(unittest.TestCase):
    """A damaged settings file must never abort start-up."""

    def setUp(self):
        reset_options()
        self.temp_dir = Path(tempfile.mkdtemp(prefix="settings-"))

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_raw(self, raw, name="setting.json"):
        path = self.temp_dir / name
        path.write_bytes(raw)
        return path

    def test_zero_byte_file_is_recovered(self):
        """The reported failure: an empty file raised JSONDecodeError."""
        path = self._write_raw(b"")
        read_option_file(str(path))
        self.assertEqual(len(Options.DefaultPresets), 1)

    def test_truncated_file_is_recovered(self):
        path = self._write_raw(b'{"Dark_Mode": tr')
        read_option_file(str(path))
        self.assertEqual(len(Options.DefaultPresets), 1)

    def test_whitespace_only_file_is_recovered(self):
        path = self._write_raw(b"\n  \n")
        read_option_file(str(path))
        self.assertEqual(len(Options.DefaultPresets), 1)

    def test_bom_only_file_is_recovered(self):
        path = self._write_raw(b"\xef\xbb\xbf")
        read_option_file(str(path))
        self.assertEqual(len(Options.DefaultPresets), 1)

    def test_json_array_is_rejected_without_crashing(self):
        # Valid JSON, but not the expected object.
        path = self._write_raw(b"[1, 2, 3]")
        read_option_file(str(path))
        self.assertEqual(len(Options.DefaultPresets), 1)

    def test_recovered_file_uses_system_theme(self):
        from unittest import mock

        path = self._write_raw(b"")
        with mock.patch("packages.Startup.Options.detect_system_dark_mode", return_value=True):
            read_option_file(str(path))
        self.assertTrue(Options.Dark_Mode)

    def test_corrupt_file_is_quarantined_and_defaults_are_rewritten(self):
        """The damaged file is kept, and a fresh one is written in its place.

        ``read_option_file`` reads the path it is given, while ``save_options``
        writes to the configured location, so both are pointed at the same file
        here -- exactly as they are at start-up.
        """
        from unittest import mock

        path = self._write_raw(b"")
        with mock.patch("packages.Startup.Options.SettingJsonInfoFilePath", str(path)):
            read_option_file(str(path))

            # The unreadable file is kept for inspection instead of being lost.
            broken = path.with_name(path.name + ".corrupt")
            self.assertTrue(broken.is_file())
            self.assertEqual(broken.read_bytes(), b"")

            # A fresh, valid file replaced it, so the next start-up is clean.
            self.assertTrue(path.is_file())
            self.assertIn("Dark_Mode", read_settings(path))
            self.assertGreater(len(read_settings(path)["Presets"]), 0)

    def test_recovered_file_is_readable_on_the_next_start(self):
        """The rewritten file loads cleanly on the following start-up."""
        from unittest import mock

        path = self._write_raw(b"")
        with mock.patch("packages.Startup.Options.SettingJsonInfoFilePath", str(path)):
            read_option_file(str(path))
            self.assertTrue(path.is_file())

            # Second run must take the normal path, with no quarantine and no
            # new .corrupt file. The recovered file stores whatever theme the
            # first start-up detected, so the check is that reading the file
            # loads *its* value: forcing the opposite value first makes the
            # assertion independent of the theme of the machine running the
            # tests (it used to require a dark-mode host).
            stored_theme = read_settings(path)["Dark_Mode"]
            Options.Dark_Mode = not stored_theme
            read_option_file(str(path))
            self.assertEqual(Options.Dark_Mode, stored_theme)
            self.assertEqual(
                sorted(p.name for p in self.temp_dir.iterdir()),
                ["setting.json", "setting.json.corrupt"],
            )

    def test_valid_file_still_loads_its_values(self):
        path = self.temp_dir / "setting.json"
        path.write_text(json.dumps({"Dark_Mode": True, "FavoritePresetId": 0}), encoding="utf-8")
        read_option_file(str(path))
        self.assertTrue(Options.Dark_Mode)
        self.assertFalse(path.with_name(path.name + ".corrupt").exists())

    def test_utf8_bom_file_is_still_accepted(self):
        path = self._write_raw(b"\xef\xbb\xbf" + json.dumps({"Dark_Mode": True}).encode("utf-8"))
        read_option_file(str(path))
        self.assertTrue(Options.Dark_Mode)


class MalformedValueTests(unittest.TestCase):
    """Structurally valid JSON with the wrong value types must not abort start-up."""

    def setUp(self):
        reset_options()
        self.temp_dir = Path(tempfile.mkdtemp(prefix="malformed-"))
        self.path = self.temp_dir / "setting.json"

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _load(self, payload):
        self.path.write_text(json.dumps(payload), encoding="utf-8")
        read_option_file(str(self.path))

    def test_presets_null(self):
        self._load({"Presets": None})
        self.assertEqual(len(Options.DefaultPresets), 1)

    def test_presets_number(self):
        self._load({"Presets": 5})
        self.assertEqual(len(Options.DefaultPresets), 1)

    def test_presets_string(self):
        self._load({"Presets": "abc"})
        self.assertEqual(len(Options.DefaultPresets), 1)

    def test_presets_object(self):
        self._load({"Presets": {"a": 1}})
        self.assertEqual(len(Options.DefaultPresets), 1)

    def test_presets_list_of_non_objects(self):
        self._load({"Presets": [1, 2]})
        self.assertEqual(len(Options.DefaultPresets), 2)

    def test_empty_preset_list_keeps_one_preset(self):
        """Start-up indexes preset 0, so the list must never be empty."""
        self._load({"Presets": []})
        self.assertEqual(len(Options.DefaultPresets), 1)

    def test_out_of_range_favorite_preset_is_reset(self):
        self._load({"Presets": [], "FavoritePresetId": 99})
        self.assertEqual(Options.FavoritePresetId, 0)
        # The value is used as an index, so it must stay valid.
        self.assertIsNotNone(Options.DefaultPresets[Options.FavoritePresetId])

    def test_non_integer_favorite_preset_is_reset(self):
        self._load({"Presets": [], "FavoritePresetId": "first"})
        self.assertEqual(Options.FavoritePresetId, 0)

    def test_negative_favorite_preset_is_reset(self):
        self._load({"Presets": [], "FavoritePresetId": -3})
        self.assertEqual(Options.FavoritePresetId, 0)

    def test_valid_favorite_preset_is_kept(self):
        self._load({"Presets": [{"Preset_Name": "A"}, {"Preset_Name": "B"}], "FavoritePresetId": 1})
        self.assertEqual(Options.FavoritePresetId, 1)
        self.assertEqual(Options.DefaultPresets[1].Preset_Name, "B")

    def test_preset_values_keep_their_defaults_when_missing(self):
        self._load({"Presets": [{}]})
        preset = Options.DefaultPresets[0]
        self.assertEqual(preset.Preset_Name, "Preset #1")
        self.assertEqual(preset.Default_Video_Extensions, ["MKV"])
        self.assertEqual(preset.Default_Subtitle_Extensions, ["ASS"])
        self.assertEqual(preset.Default_Audio_Extensions, ["AAC"])
        self.assertEqual(preset.Default_Chapter_Extensions, ["XML"])


class AtomicSaveTests(unittest.TestCase):
    """``save_options`` must never leave a truncated file behind."""

    def setUp(self):
        reset_options()
        self.temp_dir = Path(tempfile.mkdtemp(prefix="atomic-"))

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_leaves_no_temporary_file(self):
        from unittest import mock

        target = self.temp_dir / "setting.json"
        with mock.patch("packages.Startup.Options.SettingJsonInfoFilePath", str(target)):
            save_options()
        self.assertTrue(target.is_file())
        leftovers = sorted(path.name for path in self.temp_dir.iterdir())
        self.assertEqual(leftovers, ["setting.json"])

    def test_saved_file_is_complete_json(self):
        from unittest import mock

        target = self.temp_dir / "setting.json"
        with mock.patch("packages.Startup.Options.SettingJsonInfoFilePath", str(target)):
            save_options()
        data = json.loads(target.read_text(encoding="utf-8"))
        self.assertIn("Presets", data)
        self.assertIn("Dark_Mode", data)

    def test_failed_save_keeps_the_previous_file_intact(self):
        """A write error must not destroy the settings that were already there."""
        from unittest import mock

        target = self.temp_dir / "setting.json"
        target.write_text(json.dumps({"Dark_Mode": True}), encoding="utf-8")

        with mock.patch("packages.Startup.Options.SettingJsonInfoFilePath", str(target)), \
                mock.patch("packages.Startup.Options.json.dump", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                save_options()

        # The old content is still there and still valid.
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"Dark_Mode": True})
        # No half-written temporary file was left behind.
        self.assertEqual(sorted(path.name for path in self.temp_dir.iterdir()), ["setting.json"])
