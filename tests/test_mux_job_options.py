"""Regression tests for the muxing job options.

Covers the chapter/attachment discard bugs (#166, #128) end-to-end with the
bundled mkvmerge, and the per-track default/forced flags (#127, #162).
"""

import json
import subprocess
import unittest
from collections import defaultdict
from pathlib import Path
from unittest import mock

import tests  # noqa: F401  (must run before application imports)

from PySide6.QtGui import Qt

from packages.Startup import GlobalFiles
from packages.Tabs.AudioTab.Widgets.AudioSetDefaultCheckBox import AudioSetDefaultCheckBox
from packages.Tabs.AudioTab.Widgets.AudioSetForcedCheckBox import AudioSetForcedCheckBox
from packages.Tabs.GlobalSetting import GlobalSetting
from packages.Tabs.MuxSetting.Widgets import MakeThisAudioDefaultCheckBox as audio_option_module
from packages.Tabs.MuxSetting.Widgets import MakeThisSubtitleDefaultCheckBox as subtitle_option_module
from packages.Tabs.MuxSetting.Widgets.GetJsonForMkvmergeJob import GetJsonForMkvmergeJob
from packages.Tabs.MuxSetting.Widgets.SingleJobData import SingleJobData
from packages.Tabs.SubtitleTab.Widgets.SubtitleSetDefaultCheckBox import SubtitleSetDefaultCheckBox
from packages.Tabs.SubtitleTab.Widgets.SubtitleSetForcedCheckBox import SubtitleSetForcedCheckBox

SIMPLE_CHAPTER = """<?xml version="1.0" encoding="UTF-8"?>
<Chapters>
  <EditionEntry>
    <ChapterAtom>
      <ChapterTimeStart>{timestamp}</ChapterTimeStart>
      <ChapterDisplay><ChapterString>{name}</ChapterString></ChapterDisplay>
    </ChapterAtom>
  </EditionEntry>
</Chapters>
"""

GLOBAL_SETTING_KEYS = (
    "CHAPTER_ENABLED",
    "CHAPTER_DISCARD_OLD",
    "OVERWRITE_SOURCE_FILES",
    "DESTINATION_FOLDER_PATH",
    "VIDEO_SOURCE_MKV_ONLY",
    "VIDEO_DEFAULT_DURATION_FPS",
    "MUX_SETTING_ONLY_KEEP_THOSE_SUBTITLES_ENABLED",
    "MUX_SETTING_ONLY_KEEP_THOSE_AUDIOS_ENABLED",
    "MUX_SETTING_MAKE_THIS_SUBTITLE_DEFAULT_SEMI_ENABLED",
    "MUX_SETTING_MAKE_THIS_SUBTITLE_DEFAULT_FULL_ENABLED",
    "MUX_SETTING_MAKE_THIS_SUBTITLE_DEFAULT_TRACK",
    "MUX_SETTING_MAKE_THIS_AUDIO_DEFAULT_SEMI_ENABLED",
    "MUX_SETTING_MAKE_THIS_AUDIO_DEFAULT_FULL_ENABLED",
    "MUX_SETTING_MAKE_THIS_AUDIO_DEFAULT_TRACK",
    "VIDEO_OLD_TRACKS_VIDEOS_MODIFIED_ACTIVATED",
    "VIDEO_OLD_TRACKS_VIDEOS_REORDER_ACTIVATED",
    "VIDEO_OLD_TRACKS_VIDEOS_DELETED_ACTIVATED",
    "VIDEO_OLD_TRACKS_SUBTITLES_MODIFIED_ACTIVATED",
    "VIDEO_OLD_TRACKS_SUBTITLES_REORDER_ACTIVATED",
    "VIDEO_OLD_TRACKS_SUBTITLES_DELETED_ACTIVATED",
    "VIDEO_OLD_TRACKS_AUDIOS_MODIFIED_ACTIVATED",
    "VIDEO_OLD_TRACKS_AUDIOS_REORDER_ACTIVATED",
    "VIDEO_OLD_TRACKS_AUDIOS_DELETED_ACTIVATED",
    "SUBTITLE_SET_DEFAULT_DISABLED",
    "SUBTITLE_SET_FORCED_DISABLED",
    "AUDIO_SET_DEFAULT_DISABLED",
    "AUDIO_SET_FORCED_DISABLED",
)

FLAG_MAPS = (
    "SUBTITLE_SET_DEFAULT",
    "SUBTITLE_SET_FORCED",
    "AUDIO_SET_DEFAULT",
    "AUDIO_SET_FORCED",
)


class GlobalStateTestCase(unittest.TestCase):
    """Snapshot and restore every global this module touches."""

    def setUp(self):
        self._saved_values = {key: getattr(GlobalSetting, key) for key in GLOBAL_SETTING_KEYS}
        self._saved_flags = {name: dict(getattr(GlobalSetting, name)) for name in FLAG_MAPS}
        for name in FLAG_MAPS:
            setattr(GlobalSetting, name, defaultdict(bool))
        for key in GLOBAL_SETTING_KEYS:
            if key.endswith("_ACTIVATED") or key.endswith("_ENABLED"):
                setattr(GlobalSetting, key, False)
        GlobalSetting.VIDEO_DEFAULT_DURATION_FPS = ""
        GlobalSetting.DESTINATION_FOLDER_PATH = ""

    def tearDown(self):
        for key, value in self._saved_values.items():
            setattr(GlobalSetting, key, value)
        for name, saved in self._saved_flags.items():
            setattr(GlobalSetting, name, defaultdict(bool, saved))


class MediaFixture:
    """A tiny MKV with one subtitle track, one chapter and one attachment."""

    work_dir = None
    base_mkv = None
    old_chapters = None
    new_chapters = None

    @classmethod
    def build(cls, work_dir):
        cls.work_dir = Path(work_dir)
        cls.work_dir.mkdir(parents=True, exist_ok=True)
        subtitle = cls.work_dir / "subs.srt"
        subtitle.write_text(
            "1\n00:00:01,000 --> 00:00:03,000\nHello\n\n"
            "2\n00:00:10,000 --> 00:00:12,000\nWorld\n",
            encoding="utf-8",
        )
        cls.old_chapters = cls.work_dir / "chapters_old.xml"
        cls.old_chapters.write_text(
            SIMPLE_CHAPTER.format(timestamp="00:00:00.000000000", name="Old Chapter"),
            encoding="utf-8",
        )
        cls.new_chapters = cls.work_dir / "chapters_new.xml"
        cls.new_chapters.write_text(
            SIMPLE_CHAPTER.format(timestamp="00:00:05.000000000", name="New Chapter"),
            encoding="utf-8",
        )
        font = cls.work_dir / "font.ttf"
        font.write_text("not a real font, mkvmerge only stores the bytes", encoding="utf-8")
        cls.base_mkv = cls.work_dir / "base.mkv"
        result = subprocess.run(
            [
                GlobalFiles.MKVMERGE_PATH,
                "-o", str(cls.base_mkv),
                "--chapters", str(cls.old_chapters),
                "--attach-file", str(font),
                "--attachment-mime-type", "application/x-truetype-font",
                str(subtitle),
            ],
            capture_output=True,
            text=True,
            env=GlobalFiles.ENVIRONMENT,
        )
        if result.returncode != 0:
            raise RuntimeError("could not build the mkv fixture: " + result.stdout + result.stderr)
        return cls


def read_media_info(file_path):
    result = subprocess.run(
        [GlobalFiles.MKVMERGE_PATH, "-J", str(file_path)],
        capture_output=True,
        text=True,
        env=GlobalFiles.ENVIRONMENT,
    )
    if result.returncode != 0:
        raise RuntimeError("mkvmerge -J failed: " + result.stdout + result.stderr)
    return json.loads(result.stdout)


class ChapterAttachmentJobTests(GlobalStateTestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = MediaFixture.build(Path(tests.TEMP_ROOT) / "mux_job_options")

    def setUp(self):
        super().setUp()
        GlobalSetting.CHAPTER_ENABLED = True
        GlobalSetting.CHAPTER_DISCARD_OLD = True
        GlobalSetting.OVERWRITE_SOURCE_FILES = False
        self.output_dir = self.fixture.work_dir / ("out_" + self._testMethodName)
        self.output_dir.mkdir(exist_ok=True)
        for stale in self.output_dir.iterdir():
            stale.unlink()
        GlobalSetting.DESTINATION_FOLDER_PATH = str(self.output_dir)

    def make_job(self, new_chapters=False, discard_attachments=False):
        job = SingleJobData()
        job.video_name = self.fixture.base_mkv.name
        job.video_name_absolute = str(self.fixture.base_mkv)
        job.discard_old_attachments = discard_attachments
        if new_chapters:
            job.chapter_found = True
            job.chapter_name = self.fixture.new_chapters.name
            job.chapter_name_absolute = str(self.fixture.new_chapters)
        return job

    def build_command(self, job):
        GetJsonForMkvmergeJob(job)
        return json.loads(Path(GlobalFiles.mkvmergeJsonJobFilePath).read_text(encoding="utf-8"))

    def mux(self, job):
        command = self.build_command(job)
        output_path = self.output_dir / self.fixture.base_mkv.name
        result = subprocess.run(
            [GlobalFiles.MKVMERGE_PATH, "@" + GlobalFiles.mkvmergeJsonJobFilePath],
            capture_output=True,
            text=True,
            env=GlobalFiles.ENVIRONMENT,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(output_path.exists(), "mkvmerge produced no output file")
        info = read_media_info(output_path)
        chapters = info.get("chapters") or []
        if isinstance(chapters, dict):  # older mkvmerge builds report an object
            chapters = [chapters]
        chapter_count = sum(entry.get("num_entries", 0) for entry in chapters)
        attachments = len(info.get("attachments") or [])
        return command, chapter_count, attachments

    def test_discarding_chapters_and_attachments_drops_both(self):
        job = self.make_job(new_chapters=False, discard_attachments=True)

        command, chapters, attachments = self.mux(job)

        self.assertIn("--no-chapters", command)
        self.assertIn("--no-attachments", command)
        self.assertEqual(chapters, 0)
        self.assertEqual(attachments, 0)

    def test_new_chapter_file_replaces_old_chapters_when_discarding(self):
        job = self.make_job(new_chapters=True, discard_attachments=False)

        command, chapters, attachments = self.mux(job)

        self.assertIn("--no-chapters", command)
        self.assertIn("--chapters", command)
        # Only the new chapter survives; the source chapter must not be merged.
        self.assertEqual(chapters, 1)
        self.assertEqual(attachments, 1)

    def test_discarding_chapters_alone_keeps_attachments(self):
        job = self.make_job(new_chapters=False, discard_attachments=False)

        command, chapters, attachments = self.mux(job)

        self.assertIn("--no-chapters", command)
        self.assertNotIn("--no-attachments", command)
        self.assertEqual(chapters, 0)
        self.assertEqual(attachments, 1)

    def test_old_chapters_are_kept_when_discarding_is_disabled(self):
        GlobalSetting.CHAPTER_DISCARD_OLD = False
        job = self.make_job(new_chapters=False, discard_attachments=False)

        command, chapters, attachments = self.mux(job)

        self.assertNotIn("--no-chapters", command)
        self.assertEqual(chapters, 1)
        self.assertEqual(attachments, 1)

    def test_no_chapter_command_without_the_chapter_tab(self):
        GlobalSetting.CHAPTER_ENABLED = False
        job = self.make_job(new_chapters=False, discard_attachments=False)

        command = self.build_command(job)

        self.assertNotIn("--no-chapters", command)
        self.assertNotIn("--chapters", command)


class DefaultForcedFlagTests(GlobalStateTestCase):
    def test_two_subtitles_can_be_default(self):
        first = SubtitleSetDefaultCheckBox(0)
        second = SubtitleSetDefaultCheckBox(1)

        first.setChecked(True)
        second.setChecked(True)

        self.assertTrue(GlobalSetting.SUBTITLE_SET_DEFAULT[0])
        self.assertTrue(GlobalSetting.SUBTITLE_SET_DEFAULT[1])

    def test_two_subtitles_can_be_forced(self):
        first = SubtitleSetForcedCheckBox(0)
        second = SubtitleSetForcedCheckBox(1)

        first.setChecked(True)
        second.setChecked(True)

        self.assertTrue(GlobalSetting.SUBTITLE_SET_FORCED[0])
        self.assertTrue(GlobalSetting.SUBTITLE_SET_FORCED[1])

    def test_two_audios_can_be_default(self):
        first = AudioSetDefaultCheckBox(0)
        second = AudioSetDefaultCheckBox(1)

        first.setChecked(True)
        second.setChecked(True)

        self.assertTrue(GlobalSetting.AUDIO_SET_DEFAULT[0])
        self.assertTrue(GlobalSetting.AUDIO_SET_DEFAULT[1])

    def test_two_audios_can_be_forced(self):
        first = AudioSetForcedCheckBox(0)
        second = AudioSetForcedCheckBox(1)

        first.setChecked(True)
        second.setChecked(True)

        self.assertTrue(GlobalSetting.AUDIO_SET_FORCED[0])
        self.assertTrue(GlobalSetting.AUDIO_SET_FORCED[1])

    def test_unchecking_one_track_leaves_the_others_untouched(self):
        first = SubtitleSetDefaultCheckBox(0)
        second = SubtitleSetDefaultCheckBox(1)
        first.setChecked(True)
        second.setChecked(True)

        first.setChecked(False)

        self.assertFalse(GlobalSetting.SUBTITLE_SET_DEFAULT[0])
        self.assertTrue(GlobalSetting.SUBTITLE_SET_DEFAULT[1])


class StubConfirmDialog:
    """Stands in for a modal confirmation; ``result`` decides the branch."""

    result = "Yes"

    def __init__(self, *args, **kwargs):
        pass

    def execute(self):
        pass


class MakeThisTrackDefaultOptionTests(GlobalStateTestCase):
    def test_subtitle_option_clears_every_per_file_default_and_forced(self):
        GlobalSetting.SUBTITLE_SET_DEFAULT[0] = True
        GlobalSetting.SUBTITLE_SET_DEFAULT[1] = True
        GlobalSetting.SUBTITLE_SET_FORCED[2] = True

        with mock.patch.object(subtitle_option_module,
                               "ConfirmCheckMakeThisTrackDefaultWithUnCheckOption", StubConfirmDialog):
            option = subtitle_option_module.MakeThisSubtitleDefaultCheckBox()
            option.setCheckState(Qt.CheckState.Checked)

        self.assertFalse(any(GlobalSetting.SUBTITLE_SET_DEFAULT.values()))
        self.assertFalse(any(GlobalSetting.SUBTITLE_SET_FORCED.values()))
        self.assertTrue(GlobalSetting.SUBTITLE_SET_DEFAULT_DISABLED)
        self.assertTrue(GlobalSetting.SUBTITLE_SET_FORCED_DISABLED)

    def test_audio_option_clears_every_per_file_default_and_forced(self):
        GlobalSetting.AUDIO_SET_DEFAULT[0] = True
        GlobalSetting.AUDIO_SET_DEFAULT[1] = True
        GlobalSetting.AUDIO_SET_FORCED[2] = True

        with mock.patch.object(audio_option_module,
                               "ConfirmCheckMakeThisTrackDefaultWithUnCheckOption", StubConfirmDialog):
            option = audio_option_module.MakeThisAudioDefaultCheckBox()
            option.setCheckState(Qt.CheckState.Checked)

        self.assertFalse(any(GlobalSetting.AUDIO_SET_DEFAULT.values()))
        self.assertFalse(any(GlobalSetting.AUDIO_SET_FORCED.values()))
        self.assertTrue(GlobalSetting.AUDIO_SET_DEFAULT_DISABLED)
        self.assertTrue(GlobalSetting.AUDIO_SET_FORCED_DISABLED)

    def test_cancelling_the_confirmation_keeps_the_flags(self):
        GlobalSetting.SUBTITLE_SET_DEFAULT[0] = True

        class CancelDialog(StubConfirmDialog):
            result = "Cancel"

        with mock.patch.object(subtitle_option_module,
                               "ConfirmCheckMakeThisTrackDefaultWithUnCheckOption", CancelDialog):
            option = subtitle_option_module.MakeThisSubtitleDefaultCheckBox()
            option.setCheckState(Qt.CheckState.Checked)

        self.assertTrue(GlobalSetting.SUBTITLE_SET_DEFAULT[0])
        self.assertFalse(GlobalSetting.SUBTITLE_SET_DEFAULT_DISABLED)
