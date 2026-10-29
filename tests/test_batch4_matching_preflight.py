"""Regression tests for batch 4.

Covers the subfolder scan (#136/#157), the empty matching slot (#158/#120), the
language-by-file-name filter (#55), the "nothing to change" skip (#145), the
zero-audio pre-flight (#144) and the persisted default/forced ticks plus the
folder watcher (#41).
"""

import json
import os
import unittest
from pathlib import Path

import tests  # noqa: F401  (must run before application imports)

from PySide6.QtTest import QTest

from packages.Startup import GlobalFiles
from packages.Startup.Options import Options, read_option_file, save_options
from packages.Tabs.GlobalSetting import (
    EMPTY_MATCHING_SLOT,
    GlobalSetting,
    get_matching_files_in_folder,
    insert_empty_matching_slot,
    is_empty_matching_slot,
)
from packages.Tabs.MuxSetting.Widgets import AudioPreFlight
from packages.Tabs.MuxSetting.Widgets.JobChangeDetection import job_has_nothing_to_do
from packages.Tabs.MuxSetting.Widgets.JobQueueTable import JobQueueTable
from packages.Tabs.MuxSetting.Widgets.SingleJobData import SingleJobData
from packages.Tabs.SubtitleTab.Widgets.SubtitleLanguageDetection import (
    detect_language_from_file_name,
    file_name_matches_language,
    is_language_detectable,
)
from packages.Tabs.SubtitleTab.Widgets.SubtitleSetDefaultCheckBox import (
    SubtitleSetDefaultCheckBox,
)
from packages.Widgets.FolderWatcher import FolderWatcher

from tests.support import read_settings, reset_options, write_settings

GLOBAL_SETTING_KEYS = (
    "VIDEO_FILES_LIST",
    "VIDEO_FILES_ABSOLUTE_PATH_LIST",
    "VIDEO_FILES_SIZE_LIST",
    "OVERWRITE_SOURCE_FILES",
    "USE_MKVPROPEDIT",
    "MUX_SETTING_ONLY_KEEP_THOSE_AUDIOS_ENABLED",
    "MUX_SETTING_ONLY_KEEP_THOSE_AUDIOS_TRACKS_IDS",
    "VIDEO_OLD_TRACKS_AUDIOS_DELETED_ACTIVATED",
    "MUX_SETTING_SET_TITLE_TO_FILE_NAME",
    "VIDEO_DEFAULT_DURATION_FPS",
    "INCLUDE_SUBFOLDERS",
    "JOB_QUEUE_EMPTY",
)

# Per-tab dictionaries: they are cleared (and then restored) so a test never
# sees the tabs that a previous test filled in.
GLOBAL_SETTING_DICTS = (
    "SUBTITLE_FILES_LIST",
    "SUBTITLE_FILES_ABSOLUTE_PATH_LIST",
    "SUBTITLE_SET_DEFAULT",
    "SUBTITLE_SET_FORCED",
    "AUDIO_FILES_LIST",
    "AUDIO_FILES_ABSOLUTE_PATH_LIST",
    "AUDIO_SET_DEFAULT",
    "AUDIO_SET_FORCED",
    "VIDEO_OLD_TRACKS_AUDIOS_BULK_SETTING",
)

OPTION_KEYS = (
    "Default_Subtitle_Set_Default",
    "Default_Subtitle_Set_Forced",
    "Default_Audio_Set_Default",
    "Default_Audio_Set_Forced",
)


class Batch4TestCase(unittest.TestCase):
    def setUp(self):
        self._saved_values = {key: getattr(GlobalSetting, key) for key in GLOBAL_SETTING_KEYS}
        self._saved_dicts = {key: dict(getattr(GlobalSetting, key)) for key in GLOBAL_SETTING_DICTS}
        self._saved_options = {key: getattr(Options, key) for key in OPTION_KEYS}
        reset_options()
        for key in GLOBAL_SETTING_DICTS:
            getattr(GlobalSetting, key).clear()
        GlobalSetting.VIDEO_OLD_TRACKS_AUDIOS_BULK_SETTING = {}
        GlobalSetting.OVERWRITE_SOURCE_FILES = False
        GlobalSetting.USE_MKVPROPEDIT = False
        GlobalSetting.MUX_SETTING_ONLY_KEEP_THOSE_AUDIOS_ENABLED = False
        GlobalSetting.MUX_SETTING_ONLY_KEEP_THOSE_AUDIOS_TRACKS_IDS = []
        GlobalSetting.VIDEO_OLD_TRACKS_AUDIOS_DELETED_ACTIVATED = False
        GlobalSetting.MUX_SETTING_SET_TITLE_TO_FILE_NAME = False
        GlobalSetting.VIDEO_DEFAULT_DURATION_FPS = "Default"
        GlobalSetting.INCLUDE_SUBFOLDERS = False
        self._work_dir = Path(tests.TEMP_ROOT) / self._testMethodName
        self._work_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        for key, value in self._saved_values.items():
            setattr(GlobalSetting, key, value)
        for key, value in self._saved_dicts.items():
            target = getattr(GlobalSetting, key)
            if not isinstance(target, dict):
                target = {}
                setattr(GlobalSetting, key, target)
            target.clear()
            target.update(value)
        for key, value in self._saved_options.items():
            setattr(Options, key, value)


class SubfolderScanTests(Batch4TestCase):
    def _build_tree(self):
        root = self._work_dir / "library"
        (root / "Season 1").mkdir(parents=True)
        (root / "Season 2").mkdir(parents=True)
        (root / "a.mkv").write_bytes(b"x")
        (root / "b.MKV").write_bytes(b"x")
        (root / "notes.txt").write_bytes(b"x")
        (root / "empty.mkv").write_bytes(b"")
        (root / "Season 1" / "c.mkv").write_bytes(b"x")
        (root / "Season 2" / "d.mkv").write_bytes(b"x")
        return root

    def test_single_level_scan_ignores_subfolders(self):
        root = self._build_tree()

        result = get_matching_files_in_folder(root, extensions=["mkv"], include_subfolders=False)

        self.assertEqual(result, ["a.mkv", "b.MKV"])

    def test_recursive_scan_keeps_the_relative_path(self):
        root = self._build_tree()

        result = get_matching_files_in_folder(root, extensions=["MKV"], include_subfolders=True)

        self.assertIn("a.mkv", result)
        self.assertIn("b.MKV", result)
        self.assertIn(os.path.join("Season 1", "c.mkv"), result)
        self.assertIn(os.path.join("Season 2", "d.mkv"), result)
        self.assertNotIn("notes.txt", result)
        self.assertNotIn("empty.mkv", result)

    def test_no_extension_filter_accepts_every_file(self):
        root = self._work_dir / "plain"
        root.mkdir()
        (root / "font.ttf").write_bytes(b"x")
        (root / "cover.jpg").write_bytes(b"x")

        self.assertEqual(get_matching_files_in_folder(root),
                         ["cover.jpg", "font.ttf"])


class EmptyMatchingSlotTests(Batch4TestCase):
    def test_insert_keeps_both_lists_in_sync(self):
        names = ["a.ass", "b.ass"]
        paths = ["C:/a.ass", "C:/b.ass"]

        insert_empty_matching_slot(names, paths, 1)

        self.assertEqual(names, ["a.ass", EMPTY_MATCHING_SLOT, "b.ass"])
        self.assertEqual(paths, ["C:/a.ass", "", "C:/b.ass"])
        self.assertTrue(is_empty_matching_slot(names[1]))
        self.assertFalse(is_empty_matching_slot(names[0]))

    def test_insert_clamps_the_index(self):
        names = ["a.ass"]
        paths = ["C:/a.ass"]

        insert_empty_matching_slot(names, paths, 99)
        self.assertEqual(names, ["a.ass", EMPTY_MATCHING_SLOT])

        insert_empty_matching_slot(names, paths, -5)
        self.assertEqual(names, [EMPTY_MATCHING_SLOT, "a.ass", EMPTY_MATCHING_SLOT])

    def test_queue_skips_the_empty_slot(self):
        first = self._work_dir / "one.mkv"
        second = self._work_dir / "two.mkv"
        first.write_bytes(b"x")
        second.write_bytes(b"y")
        GlobalSetting.VIDEO_FILES_LIST = [first.name, second.name]
        GlobalSetting.VIDEO_FILES_ABSOLUTE_PATH_LIST = [str(first), str(second)]
        GlobalSetting.VIDEO_FILES_SIZE_LIST = [" 1.00 B", " 1.00 B"]
        GlobalSetting.SUBTITLE_FILES_LIST[0] = [EMPTY_MATCHING_SLOT, "two.ass"]
        GlobalSetting.SUBTITLE_FILES_ABSOLUTE_PATH_LIST[0] = ["", str(self._work_dir / "two.ass")]

        table = JobQueueTable()
        table.setup_queue()

        self.assertFalse(table.data[0].subtitle_found)
        self.assertEqual(table.data[0].subtitle_name, [])
        self.assertTrue(table.data[1].subtitle_found)
        self.assertEqual(table.data[1].subtitle_name, ["two.ass"])
        table.clear_queue()


class LanguageDetectionTests(Batch4TestCase):
    def test_detects_common_name_forms(self):
        cases = {
            "Show.S01E01.en.srt": "English",
            "Show.S01E01.eng.ass": "English",
            "Show.S01E01.English.ass": "English",
            "Movie.deu.srt": "German",
            "Movie.fre.srt": "French",
            "Movie.CHI.srt": "Chinese",
            "Movie.zho.srt": "Chinese",
            "pt-BR.srt": "Portuguese",
            "japanese.srt": "Japanese",
            "arabic.ass": "Arabic",
        }
        for file_name, expected in cases.items():
            with self.subTest(file_name=file_name):
                self.assertEqual(detect_language_from_file_name(file_name), expected)

    def test_ambiguous_two_letter_words_are_ignored(self):
        self.assertIsNone(detect_language_from_file_name("Show.it.srt"))
        self.assertIsNone(detect_language_from_file_name("random.srt"))

    def test_matching_accepts_the_tab_language_only(self):
        self.assertTrue(file_name_matches_language("Show.en.srt", "English"))
        self.assertFalse(file_name_matches_language("Show.ar.srt", "English"))
        self.assertTrue(file_name_matches_language("Show.ar.srt", "Arabic"))

    def test_undetectable_language_never_hides_files(self):
        self.assertFalse(is_language_detectable("Dothraki"))
        self.assertTrue(file_name_matches_language("anything.srt", "Dothraki"))


class SkipUnchangedJobTests(Batch4TestCase):
    def _job(self, suffix=".mkv"):
        job = SingleJobData()
        job.video_name = "movie" + suffix
        job.video_name_absolute = str(self._work_dir / ("movie" + suffix))
        return job

    def test_plain_overwrite_is_skipped(self):
        GlobalSetting.OVERWRITE_SOURCE_FILES = True

        self.assertTrue(job_has_nothing_to_do(self._job()))

    def test_every_real_instruction_runs_the_job(self):
        GlobalSetting.OVERWRITE_SOURCE_FILES = True

        attached = self._job()
        attached.subtitle_found = True
        attached.subtitle_name = ["a.ass"]
        self.assertFalse(job_has_nothing_to_do(attached))

        crc = self._job()
        crc.is_crc_calculating_required = True
        self.assertFalse(job_has_nothing_to_do(crc))

        GlobalSetting.MUX_SETTING_SET_TITLE_TO_FILE_NAME = True
        self.assertFalse(job_has_nothing_to_do(self._job()))
        GlobalSetting.MUX_SETTING_SET_TITLE_TO_FILE_NAME = False

        GlobalSetting.VIDEO_DEFAULT_DURATION_FPS = "23.976"
        self.assertFalse(job_has_nothing_to_do(self._job()))

    def test_separate_output_folder_or_foreign_format_is_never_skipped(self):
        self.assertFalse(job_has_nothing_to_do(self._job()))
        GlobalSetting.OVERWRITE_SOURCE_FILES = True
        self.assertFalse(job_has_nothing_to_do(self._job(".mp4")))


class AudioPreFlightTests(Batch4TestCase):
    def _cache_tracks(self, video_path, track_types):
        cache_path = Path(AudioPreFlight.get_media_info_file_path(video_path))
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"tracks": [{"type": track_type} for track_type in track_types]}
        cache_path.write_text(json.dumps(payload), encoding="utf-8")

    def _queue_one_video(self, has_audio_track):
        video = self._work_dir / "movie.mkv"
        video.write_bytes(b"x")
        self._cache_tracks(str(video), ["video", "audio" if has_audio_track else "subtitles"])
        GlobalSetting.VIDEO_FILES_LIST = [video.name]
        GlobalSetting.VIDEO_FILES_ABSOLUTE_PATH_LIST = [str(video)]
        return video

    def test_warns_when_the_source_has_no_audio(self):
        self._queue_one_video(has_audio_track=False)

        self.assertTrue(AudioPreFlight.job_would_have_no_audio(0))
        self.assertEqual(AudioPreFlight.find_videos_without_audio(), ["movie.mkv"])

    def test_stays_quiet_when_the_source_has_audio(self):
        self._queue_one_video(has_audio_track=True)

        self.assertFalse(AudioPreFlight.job_would_have_no_audio(0))
        self.assertEqual(AudioPreFlight.find_videos_without_audio(), [])

    def test_missing_cache_never_warns(self):
        video = self._work_dir / "unknown.mkv"
        video.write_bytes(b"x")
        GlobalSetting.VIDEO_FILES_LIST = [video.name]
        GlobalSetting.VIDEO_FILES_ABSOLUTE_PATH_LIST = [str(video)]

        self.assertFalse(AudioPreFlight.job_would_have_no_audio(0))

    def test_attached_audio_wins_over_the_source_tracks(self):
        self._queue_one_video(has_audio_track=False)
        GlobalSetting.AUDIO_FILES_LIST[0] = ["extra.aac"]

        self.assertFalse(AudioPreFlight.job_would_have_no_audio(0))

    def test_an_empty_audio_slot_is_not_an_attached_file(self):
        self._queue_one_video(has_audio_track=False)
        GlobalSetting.AUDIO_FILES_LIST[0] = [EMPTY_MATCHING_SLOT]

        self.assertTrue(AudioPreFlight.job_would_have_no_audio(0))

    def test_mkvpropedit_only_muxing_never_warns(self):
        self._queue_one_video(has_audio_track=False)
        GlobalSetting.USE_MKVPROPEDIT = True

        self.assertEqual(AudioPreFlight.find_videos_without_audio(), [])


class PersistedTrackFlagTests(Batch4TestCase):
    def test_ticking_the_box_is_saved_to_the_option_file(self):
        checkbox = SubtitleSetDefaultCheckBox(0)

        checkbox.setChecked(True)

        self.assertTrue(Options.Default_Subtitle_Set_Default)
        self.assertTrue(GlobalSetting.SUBTITLE_SET_DEFAULT[0])
        self.assertTrue(read_settings()["Default_Subtitle_Set_Default"])

    def test_silent_reset_does_not_touch_the_saved_preference(self):
        Options.Default_Subtitle_Set_Default = True
        checkbox = SubtitleSetDefaultCheckBox(0)

        checkbox.set_checked_silently(False)

        self.assertFalse(GlobalSetting.SUBTITLE_SET_DEFAULT[0])
        self.assertTrue(Options.Default_Subtitle_Set_Default)

    def test_option_file_round_trip_keeps_the_ticks(self):
        write_settings({
            "Presets": [],
            "FavoritePresetId": 0,
            "Dark_Mode": False,
            "Attachment_Expert_Mode_Info_Message_Show": True,
            "Choose_Preset_On_Startup": False,
            "Default_Subtitle_Set_Default": True,
            "Default_Subtitle_Set_Forced": False,
            "Default_Audio_Set_Default": False,
            "Default_Audio_Set_Forced": True,
        })

        read_option_file(GlobalFiles.SettingJsonInfoFilePath)

        self.assertTrue(Options.Default_Subtitle_Set_Default)
        self.assertFalse(Options.Default_Subtitle_Set_Forced)
        self.assertFalse(Options.Default_Audio_Set_Default)
        self.assertTrue(Options.Default_Audio_Set_Forced)

    def test_old_option_file_without_the_keys_still_loads(self):
        write_settings({"Presets": [], "FavoritePresetId": 0, "Dark_Mode": False})

        read_option_file(GlobalFiles.SettingJsonInfoFilePath)

        self.assertFalse(Options.Default_Subtitle_Set_Default)
        self.assertFalse(Options.Default_Subtitle_Set_Forced)
        self.assertFalse(Options.Default_Audio_Set_Default)
        self.assertFalse(Options.Default_Audio_Set_Forced)
        save_options()
        self.assertIn("Default_Audio_Set_Forced", read_settings())


class FolderWatcherTests(Batch4TestCase):
    def test_new_files_trigger_one_debounced_signal(self):
        folder = self._work_dir / "watched"
        folder.mkdir()
        watcher = FolderWatcher()
        watcher.debounce_timer.setInterval(10)
        emissions = []
        watcher.folder_changed_signal.connect(lambda: emissions.append(True))

        watcher.watch_folder(str(folder))
        self.assertEqual(watcher.current_folder_path, str(folder))

        (folder / "new.mkv").write_bytes(b"x")
        QTest.qWait(200)

        self.assertEqual(len(emissions), 1)

    def test_watching_the_same_folder_twice_is_a_no_op(self):
        folder = self._work_dir / "watched"
        folder.mkdir()
        watcher = FolderWatcher()

        watcher.watch_folder(str(folder))
        watcher.watch_folder(str(folder))

        self.assertEqual(watcher.file_system_watcher.directories(), [str(folder)])

    def test_clear_removes_the_watched_folders(self):
        folder = self._work_dir / "watched"
        folder.mkdir()
        watcher = FolderWatcher()
        watcher.watch_folder(str(folder))

        watcher.clear()

        self.assertEqual(watcher.file_system_watcher.directories(), [])
        self.assertEqual(watcher.current_folder_path, "")


if __name__ == "__main__":
    unittest.main()
