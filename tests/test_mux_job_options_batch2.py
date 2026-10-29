"""Regression tests for the batch-2 muxing options.

Covers the generated mkvmerge command and, where it is observable, the muxed
result: title (#148), tag discarding (#126), timing repair (#149), chapter
generation (#172), M2TS input (#137) and the searchable language list (#122).
"""

import json
import subprocess
import unittest
import wave
from collections import defaultdict
from pathlib import Path

import tests  # noqa: F401  (must run before application imports)

from packages.Startup import GlobalFiles
from packages.Startup.PreDefined import AllVideosExtensions
from packages.Tabs.ChapterTab.Widgets.ChapterGenerateIntervalSpinBox import ChapterGenerateIntervalSpinBox
from packages.Tabs.ChapterTab.Widgets.GenerateChaptersCheckBox import GenerateChaptersCheckBox
from packages.Tabs.GlobalSetting import GlobalSetting
from packages.Tabs.MuxSetting.MuxSetting import check_if_mkvpropedit_can_be_used
from packages.Tabs.MuxSetting.Widgets.DiscardAllTagsCheckBox import DiscardAllTagsCheckBox
from packages.Tabs.MuxSetting.Widgets.GetJsonForMkvmergeJob import GetJsonForMkvmergeJob
from packages.Tabs.MuxSetting.Widgets.SetTitleToFileNameCheckBox import SetTitleToFileNameCheckBox
from packages.Tabs.MuxSetting.Widgets.SingleJobData import SingleJobData
from packages.Tabs.SettingTab.Widgets.LanguagesComboBox import LanguagesComboBox
from packages.Tabs.VideoTab.Widgets.FixBitstreamTimingCheckBox import FixBitstreamTimingCheckBox

SOURCE_NAME = "episode_01.mkv"
AUDIO_NAME = "episode_01.wav"

OLDER_CHAPTER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    "<Chapters><EditionEntry><ChapterAtom><ChapterTimeStart>00:00:00.000000000</ChapterTimeStart>"
    "<ChapterDisplay><ChapterString>Source Chapter</ChapterString></ChapterDisplay></ChapterAtom>"
    "</EditionEntry></Chapters>\n"
)

GLOBAL_TAGS = (
    '<?xml version="1.0"?>\n'
    "<Tags><Tag><Targets/><Simple><Name>MY_TAG</Name><String>kept</String></Simple></Tag></Tags>\n"
)

GLOBAL_SETTING_KEYS = (
    "MUX_SETTING_SET_TITLE_TO_FILE_NAME",
    "MUX_SETTING_DISCARD_ALL_TAGS",
    "VIDEO_FIX_BITSTREAM_TIMING_INFO",
    "VIDEO_DEFAULT_DURATION_FPS",
    "VIDEO_SOURCE_MKV_ONLY",
    "CHAPTER_ENABLED",
    "CHAPTER_DISCARD_OLD",
    "CHAPTER_GENERATE_BY_INTERVAL",
    "CHAPTER_GENERATE_INTERVAL_SECONDS",
    "OVERWRITE_SOURCE_FILES",
    "DESTINATION_FOLDER_PATH",
)


class Batch2TestCase(unittest.TestCase):
    def setUp(self):
        self._saved_values = {key: getattr(GlobalSetting, key) for key in GLOBAL_SETTING_KEYS}
        self._saved_subtitle_files = GlobalSetting.SUBTITLE_FILES_LIST
        self._saved_audio_files = GlobalSetting.AUDIO_FILES_LIST
        GlobalSetting.SUBTITLE_FILES_LIST = defaultdict(list)
        GlobalSetting.AUDIO_FILES_LIST = defaultdict(list)
        for key in GLOBAL_SETTING_KEYS:
            if isinstance(getattr(GlobalSetting, key), bool):
                setattr(GlobalSetting, key, False)
        GlobalSetting.VIDEO_DEFAULT_DURATION_FPS = ""
        GlobalSetting.CHAPTER_GENERATE_INTERVAL_SECONDS = 120
        GlobalSetting.DESTINATION_FOLDER_PATH = ""

    def tearDown(self):
        for key, value in self._saved_values.items():
            setattr(GlobalSetting, key, value)
        GlobalSetting.SUBTITLE_FILES_LIST = self._saved_subtitle_files
        GlobalSetting.AUDIO_FILES_LIST = self._saved_audio_files


class AudioFixture:
    """12 s of silence with one chapter, one global tag and a font attachment."""

    work_dir = None
    base_mkv = None
    font_file = None

    @classmethod
    def build(cls, work_dir):
        cls.work_dir = Path(work_dir)
        cls.work_dir.mkdir(parents=True, exist_ok=True)
        source = cls.work_dir / AUDIO_NAME
        with wave.open(str(source), "wb") as audio_file:
            audio_file.setnchannels(1)
            audio_file.setsampwidth(2)
            audio_file.setframerate(8000)
            audio_file.writeframes(b"\x00\x00" * (8000 * 12))
        chapters = cls.work_dir / "chapters.xml"
        chapters.write_text(OLDER_CHAPTER, encoding="utf-8")
        tags = cls.work_dir / "tags.xml"
        tags.write_text(GLOBAL_TAGS, encoding="utf-8")
        cls.font_file = cls.work_dir / "subtitle_font.ttf"
        cls.font_file.write_text("not a real font, mkvmerge only stores the bytes", encoding="utf-8")
        cls.base_mkv = cls.work_dir / SOURCE_NAME
        result = subprocess.run(
            [
                GlobalFiles.MKVMERGE_PATH,
                "-o", str(cls.base_mkv),
                "--chapters", str(chapters),
                "--global-tags", str(tags),
                "--attach-file", str(cls.font_file),
                str(source),
            ],
            capture_output=True,
            text=True,
            env=GlobalFiles.ENVIRONMENT,
        )
        if result.returncode != 0:
            raise RuntimeError("could not build the audio fixture: " + result.stdout + result.stderr)
        return cls


def media_info(file_path):
    result = subprocess.run(
        [GlobalFiles.MKVMERGE_PATH, "-J", str(file_path)],
        capture_output=True,
        text=True,
        env=GlobalFiles.ENVIRONMENT,
    )
    if result.returncode != 0:
        raise RuntimeError("mkvmerge -J failed: " + result.stdout + result.stderr)
    return json.loads(result.stdout)


def chapter_count(info):
    chapters = info.get("chapters") or []
    if isinstance(chapters, dict):
        chapters = [chapters]
    return sum(entry.get("num_entries", 0) for entry in chapters)


class MkvmergeOptionFlagTests(Batch2TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = AudioFixture.build(Path(tests.TEMP_ROOT) / "mux_options_batch2")

    def setUp(self):
        super().setUp()
        self.output_dir = self.fixture.work_dir / ("out_" + self._testMethodName)
        self.output_dir.mkdir(exist_ok=True)
        for stale in self.output_dir.iterdir():
            stale.unlink()
        GlobalSetting.DESTINATION_FOLDER_PATH = str(self.output_dir)

    def make_job(self):
        job = SingleJobData()
        job.video_name = SOURCE_NAME
        job.video_name_absolute = str(self.fixture.base_mkv)
        return job

    def build_command(self, job):
        GetJsonForMkvmergeJob(job)
        return json.loads(Path(GlobalFiles.mkvmergeJsonJobFilePath).read_text(encoding="utf-8"))

    def mux(self, job):
        command = self.build_command(job)
        result = subprocess.run(
            [GlobalFiles.MKVMERGE_PATH, "@" + GlobalFiles.mkvmergeJsonJobFilePath],
            capture_output=True,
            text=True,
            env=GlobalFiles.ENVIRONMENT,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        output_path = self.output_dir / "episode_01.mkv"
        self.assertTrue(output_path.exists(), "mkvmerge produced no output file")
        return command, media_info(output_path)

    def assert_before_input(self, command, option):
        self.assertIn(option, command)
        self.assertLess(command.index(option), command.index("("))

    def test_title_is_set_to_the_file_name(self):
        GlobalSetting.MUX_SETTING_SET_TITLE_TO_FILE_NAME = True
        job = self.make_job()

        command, info = self.mux(job)

        self.assertIn("--title", command)
        self.assertEqual(command[command.index("--title") + 1], "episode_01")
        self.assertEqual(info["container"]["properties"]["title"], "episode_01")

    def test_title_is_left_alone_by_default(self):
        command, info = self.mux(self.make_job())

        self.assertNotIn("--title", command)
        self.assertNotIn("title", info["container"]["properties"])

    def test_tags_are_discarded(self):
        job = self.make_job()
        _, info_before = self.mux(job)
        self.assertTrue(info_before.get("global_tags"), "fixture should carry a global tag")

        GlobalSetting.MUX_SETTING_DISCARD_ALL_TAGS = True
        command, info_after = self.mux(job)

        self.assert_before_input(command, "--no-global-tags")
        self.assert_before_input(command, "--no-track-tags")
        self.assertEqual(info_after.get("global_tags") or [], [])
        self.assertEqual(info_after.get("track_tags") or [], [])

    def test_fix_bitstream_timing_flag(self):
        GlobalSetting.VIDEO_FIX_BITSTREAM_TIMING_INFO = True
        GlobalSetting.VIDEO_DEFAULT_DURATION_FPS = "24p"
        job = self.make_job()

        command = self.build_command(job)

        self.assert_before_input(command, "--fix-bitstream-timing-information")
        self.assertEqual(command[command.index("--fix-bitstream-timing-information") + 1], "0:1")
        self.assertIn("--default-duration", command)
        GlobalSetting.VIDEO_FIX_BITSTREAM_TIMING_INFO = False
        self.assertNotIn("--fix-bitstream-timing-information", self.build_command(job))

    def test_generated_chapters_replace_the_source_chapters(self):
        GlobalSetting.CHAPTER_ENABLED = True
        job = self.make_job()
        _, info_before = self.mux(job)
        self.assertEqual(chapter_count(info_before), 1)

        GlobalSetting.CHAPTER_GENERATE_BY_INTERVAL = True
        GlobalSetting.CHAPTER_GENERATE_INTERVAL_SECONDS = 5
        command, info_after = self.mux(job)

        self.assert_before_input(command, "--generate-chapters")
        self.assertEqual(command[command.index("--generate-chapters") + 1], "interval:5s")
        self.assertIn("--no-chapters", command)
        # 12 s at a 5 s interval: chapters at 0, 5 and 10 seconds.
        self.assertEqual(chapter_count(info_after), 3)

    def test_generation_is_ignored_when_the_chapter_tab_is_disabled(self):
        GlobalSetting.CHAPTER_ENABLED = False
        GlobalSetting.CHAPTER_GENERATE_BY_INTERVAL = True

        command = self.build_command(self.make_job())

        self.assertNotIn("--generate-chapters", command)
        self.assertNotIn("--no-chapters", command)

    def test_options_that_mkvpropedit_cannot_do_force_mkvmerge(self):
        GlobalSetting.VIDEO_SOURCE_MKV_ONLY = True
        self.assertTrue(check_if_mkvpropedit_can_be_used())

        GlobalSetting.CHAPTER_ENABLED = True
        GlobalSetting.CHAPTER_GENERATE_BY_INTERVAL = True
        self.assertFalse(check_if_mkvpropedit_can_be_used())

        GlobalSetting.CHAPTER_GENERATE_BY_INTERVAL = False
        GlobalSetting.MUX_SETTING_SET_TITLE_TO_FILE_NAME = True
        self.assertFalse(check_if_mkvpropedit_can_be_used())

        GlobalSetting.MUX_SETTING_SET_TITLE_TO_FILE_NAME = False
        GlobalSetting.MUX_SETTING_DISCARD_ALL_TAGS = True
        self.assertFalse(check_if_mkvpropedit_can_be_used())


class Batch2WidgetTests(Batch2TestCase):
    def test_m2ts_and_mts_are_video_extensions(self):
        self.assertIn("M2TS", AllVideosExtensions)
        self.assertIn("MTS", AllVideosExtensions)
        self.assertIn("MKV", AllVideosExtensions)

    def test_checkboxes_write_their_global(self):
        cases = (
            (FixBitstreamTimingCheckBox, "VIDEO_FIX_BITSTREAM_TIMING_INFO"),
            (SetTitleToFileNameCheckBox, "MUX_SETTING_SET_TITLE_TO_FILE_NAME"),
            (DiscardAllTagsCheckBox, "MUX_SETTING_DISCARD_ALL_TAGS"),
            (GenerateChaptersCheckBox, "CHAPTER_GENERATE_BY_INTERVAL"),
        )
        for checkbox_class, global_name in cases:
            with self.subTest(checkbox=checkbox_class.__name__):
                checkbox = checkbox_class()
                checkbox.setChecked(True)
                self.assertTrue(getattr(GlobalSetting, global_name))
                checkbox.setChecked(False)
                self.assertFalse(getattr(GlobalSetting, global_name))

    def test_chapter_interval_spin_box_writes_the_global(self):
        spin_box = ChapterGenerateIntervalSpinBox()

        spin_box.setValue(300)

        self.assertEqual(GlobalSetting.CHAPTER_GENERATE_INTERVAL_SECONDS, 300)

    def test_language_combo_filters_and_restores(self):
        combo = LanguagesComboBox(["English", "German", "French"], "English")
        completer = combo.completer()

        completer.setCompletionPrefix("ger")
        self.assertEqual(completer.completionCount(), 1)
        self.assertEqual(completer.currentCompletion(), "German")

        combo.lineEdit().setText("French")
        combo.restore_last_valid_language()
        self.assertEqual(combo.currentText(), "French")

        combo.lineEdit().setText("Ger")
        combo.restore_last_valid_language()
        self.assertEqual(combo.currentText(), "French", "unknown text must fall back to the last valid item")
