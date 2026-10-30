"""Regression tests for batch 5.

Covers the track menu sections (#139/#141/#138), relative destination folders
(#118), extra mkvmerge arguments plus stop-after-video-ends (#152/#111), the
chapter delay (#111), output name patterns (#111) and the automatic subtitle
font attachment (#160).
"""

import json
import os
import subprocess
import unittest
import wave
from pathlib import Path

import tests  # noqa: F401  (must run before application imports)

from packages.Startup import GlobalFiles
from packages.Tabs.AttachmentTab.Widgets.SubtitleFonts import (
    find_font_files_for_names,
    get_font_names_from_subtitle_file,
    get_font_names_from_subtitle_text,
    get_subtitle_font_attachments,
    normalize_font_key,
)
from packages.Tabs.GlobalSetting import (
    GlobalSetting,
    TRACK_SECTION_FORMAT,
    TRACK_SECTION_LANGUAGE,
    TRACK_SECTION_ORDER,
    TRACK_SECTION_TRACK_ID,
    TRACK_SECTION_TRACK_NAME,
    filter_track_menu_entries,
    get_track_id_from_menu_entry,
    get_track_order_from_menu_entry,
    is_track_menu_section,
    refresh_tracks,
)
from packages.Tabs.MuxSetting.MuxSetting import check_if_mkvpropedit_can_be_used
from packages.Tabs.MuxSetting.Widgets.ChapterDelay import (
    get_shifted_chapters_file_path,
    shift_chapter_text,
)
from packages.Tabs.MuxSetting.Widgets.GetJsonForMkvmergeJob import (
    GetJsonForMkvmergeJob,
    normalize_track_id_text,
    resolve_keep_list_by_format,
    resolve_keep_list_by_order,
    split_extra_arguments,
)
from packages.Tabs.MuxSetting.Widgets.JobOutputFiles import (
    get_output_file_name,
    get_output_file_path,
    get_output_folder_path,
    is_relative_destination_folder,
    uses_relative_destination,
)
from packages.Tabs.MuxSetting.Widgets import JobOutputFiles
from packages.Tabs.MuxSetting.Widgets.JobChangeDetection import job_has_nothing_to_do
from packages.Tabs.MuxSetting.Widgets.OutputNamePattern import (
    apply_output_name_pattern,
    get_unknown_pattern_variables,
    make_output_name_unique,
    remove_empty_brackets,
    sanitize_output_file_name,
)
from packages.Tabs.MuxSetting.Widgets.SingleJobData import SingleJobData
from packages.Widgets.SingleTrackData import SingleTrackData

GLOBAL_SETTING_KEYS = (
    "VIDEO_FILES_LIST",
    "VIDEO_FILES_ABSOLUTE_PATH_LIST",
    "OVERWRITE_SOURCE_FILES",
    "USE_MKVPROPEDIT",
    "DESTINATION_FOLDER_PATH",
    "MUX_SETTING_EXTRA_ARGUMENTS",
    "MUX_SETTING_STOP_AFTER_VIDEO_ENDS",
    "MUX_SETTING_OUTPUT_NAME_PATTERN",
    "MUX_SETTING_USED_OUTPUT_NAMES",
    "MUX_SETTING_ONLY_KEEP_THOSE_SUBTITLES_ENABLED",
    "MUX_SETTING_ONLY_KEEP_THOSE_SUBTITLES_TRACKS_IDS",
    "MUX_SETTING_ONLY_KEEP_THOSE_SUBTITLES_TRACKS_LANGUAGES",
    "MUX_SETTING_ONLY_KEEP_THOSE_SUBTITLES_TRACKS_NAMES",
    "MUX_SETTING_ONLY_KEEP_THOSE_SUBTITLES_TRACKS_ORDERS",
    "MUX_SETTING_ONLY_KEEP_THOSE_SUBTITLES_TRACKS_FORMATS",
    "MUX_SETTING_ONLY_KEEP_THOSE_AUDIOS_TRACKS_ORDERS",
    "MUX_SETTING_ONLY_KEEP_THOSE_AUDIOS_TRACKS_FORMATS",
    "ATTACHMENT_AUTO_DETECT_FONTS",
    "ATTACHMENT_SEARCH_FOLDERS",
    "CHAPTER_ENABLED",
    "CHAPTER_DISCARD_OLD",
    "CHAPTER_GENERATE_BY_INTERVAL",
    "CHAPTER_DELAY_MILLISECONDS",
    "VIDEO_SOURCE_MKV_ONLY",
)

SUBTITLE_CHAPTER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Chapters>
  <EditionEntry>
    <ChapterAtom>
      <ChapterTimeStart>00:00:00.000000000</ChapterTimeStart>
      <ChapterTimeEnd>00:00:05.000000000</ChapterTimeEnd>
      <ChapterDisplay><ChapterString>Intro</ChapterString></ChapterDisplay>
    </ChapterAtom>
    <ChapterAtom>
      <ChapterTimeStart>00:00:10.000000000</ChapterTimeStart>
      <ChapterTimeEnd>00:00:15.000000000</ChapterTimeEnd>
      <ChapterDisplay><ChapterString>Main</ChapterString></ChapterDisplay>
    </ChapterAtom>
  </EditionEntry>
</Chapters>
"""

ASS_SUBTITLE = """[Script Info]
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Open Sans,20,&H00FFFFFF,&H00000000,&H00000000,0,0,1,2,0,2,10,10,10,1
Style: Sign,Futura Bold,18,&H00FFFFFF,&H00000000,&H00000000,0,0,1,2,0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,{\\fnArial\\b1}Hello
"""


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


def write_json_job(command):
    Path(GlobalFiles.mkvmergeJsonJobFilePath).write_text(json.dumps(command), encoding="utf-8")


def run_json_job():
    return subprocess.run(
        [GlobalFiles.MKVMERGE_PATH, "@" + GlobalFiles.mkvmergeJsonJobFilePath],
        capture_output=True,
        text=True,
        env=GlobalFiles.ENVIRONMENT,
    )


class Batch5TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_dir = Path(tests.TEMP_ROOT) / "batch5_fixture"
        cls.fixture_dir.mkdir(parents=True, exist_ok=True)
        cls.audio = cls.fixture_dir / "audio.wav"
        with wave.open(str(cls.audio), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(8000)
            handle.writeframes(b"\x00\x00" * 8000)
        cls.english = cls.fixture_dir / "english.srt"
        cls.english.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
        cls.french = cls.fixture_dir / "french.srt"
        cls.french.write_text("1\n00:00:00,000 --> 00:00:02,000\nBonjour\n", encoding="utf-8")

    def setUp(self):
        self._saved_values = {key: getattr(GlobalSetting, key) for key in GLOBAL_SETTING_KEYS}
        for key in GLOBAL_SETTING_KEYS:
            if isinstance(getattr(GlobalSetting, key), list):
                setattr(GlobalSetting, key, [])
            elif isinstance(getattr(GlobalSetting, key), set):
                setattr(GlobalSetting, key, set())
        GlobalSetting.OVERWRITE_SOURCE_FILES = False
        GlobalSetting.USE_MKVPROPEDIT = False
        GlobalSetting.MUX_SETTING_EXTRA_ARGUMENTS = ""
        GlobalSetting.MUX_SETTING_STOP_AFTER_VIDEO_ENDS = False
        GlobalSetting.MUX_SETTING_OUTPUT_NAME_PATTERN = ""
        GlobalSetting.ATTACHMENT_AUTO_DETECT_FONTS = False
        GlobalSetting.CHAPTER_DELAY_MILLISECONDS = 0
        GlobalSetting.VIDEO_SOURCE_MKV_ONLY = False
        self._work_dir = Path(tests.TEMP_ROOT) / self._testMethodName
        self._work_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        for key, value in self._saved_values.items():
            setattr(GlobalSetting, key, value)

    def make_movie(self, folder, name="movie.mkv", subtitles=False):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        source = folder / name
        arguments = [GlobalFiles.MKVMERGE_PATH, "-o", str(source), str(self.audio)]
        if subtitles:
            arguments = [GlobalFiles.MKVMERGE_PATH, "-o", str(source),
                         "--language", "0:eng", str(self.english),
                         "--language", "0:fre", str(self.french),
                         str(self.audio)]
        result = subprocess.run(arguments, capture_output=True, text=True,
                                env=GlobalFiles.ENVIRONMENT)
        if result.returncode != 0:
            raise RuntimeError("could not build the fixture: " + result.stdout + result.stderr)
        cache = Path(GlobalFiles.MediaInfoFolderPath) / _media_info_name(source)
        cache.write_text(
            subprocess.run([GlobalFiles.MKVMERGE_PATH, "-J", str(source)], capture_output=True,
                           text=True, env=GlobalFiles.ENVIRONMENT).stdout,
            encoding="utf-8",
        )
        return source

    def make_job(self, source, queue_index=1):
        job = SingleJobData()
        job.video_name = os.path.basename(str(source))
        job.video_name_absolute = str(source)
        job.queue_index = queue_index
        return job

    def build_command(self, job):
        GetJsonForMkvmergeJob(job)
        return json.loads(Path(GlobalFiles.mkvmergeJsonJobFilePath).read_text(encoding="utf-8"))


def _media_info_name(file_path):
    import hashlib

    return hashlib.sha1(str(file_path).encode("utf-8")).hexdigest() + ".json"


class TrackMenuTests(Batch5TestCase):
    def setUp(self):
        super().setUp()
        self.movie = self.make_movie(self._work_dir / "library", subtitles=True)
        GlobalSetting.VIDEO_FILES_LIST = [self.movie.name]
        GlobalSetting.VIDEO_FILES_ABSOLUTE_PATH_LIST = [str(self.movie)]

    def test_menu_has_order_language_format_sections(self):
        menu = refresh_tracks("subtitles")
        self.assertEqual(menu[0], TRACK_SECTION_ORDER)
        self.assertIn("Order 1", menu)
        self.assertIn("Order 2", menu)
        self.assertIn(TRACK_SECTION_TRACK_ID, menu)
        self.assertIn("Track 02 - French", menu)
        self.assertIn(TRACK_SECTION_LANGUAGE, menu)
        self.assertIn("French", menu)
        self.assertIn(TRACK_SECTION_FORMAT, menu)
        self.assertIn("SubRip/SRT", menu)
        # Sections keep a stable order.
        self.assertLess(menu.index(TRACK_SECTION_ORDER), menu.index(TRACK_SECTION_TRACK_ID))
        self.assertLess(menu.index(TRACK_SECTION_TRACK_ID), menu.index(TRACK_SECTION_LANGUAGE))
        self.assertLess(menu.index(TRACK_SECTION_LANGUAGE), menu.index(TRACK_SECTION_FORMAT))

    def test_section_detection_and_entry_parsing(self):
        self.assertTrue(is_track_menu_section("---Format---"))
        self.assertFalse(is_track_menu_section("Order 1"))
        self.assertEqual(get_track_order_from_menu_entry("Order 2"), 2)
        self.assertIsNone(get_track_order_from_menu_entry("Track 02 - French"))
        self.assertEqual(get_track_id_from_menu_entry("Track 02 - French"), "02")
        self.assertIsNone(get_track_id_from_menu_entry("Order 2"))

    def test_filter_keeps_only_requested_sections(self):
        menu = refresh_tracks("subtitles")
        filtered = filter_track_menu_entries(
            menu, (TRACK_SECTION_TRACK_ID, TRACK_SECTION_LANGUAGE, TRACK_SECTION_TRACK_NAME))
        self.assertNotIn(TRACK_SECTION_ORDER, filtered)
        self.assertNotIn(TRACK_SECTION_FORMAT, filtered)
        self.assertNotIn("Order 1", filtered)
        self.assertIn("Track 02 - French", filtered)

    def test_order_and_format_resolution(self):
        # The resolver works on the track objects the job builder reads.
        tracks = []
        for track_id, codec in (("1", "SubRip/SRT"), ("2", "SubRip/SRT")):
            track = SingleTrackData()
            track.id = track_id
            track.codec = codec
            tracks.append(track)
        self.assertEqual(resolve_keep_list_by_order(["Order 2"], tracks), ["2"])
        self.assertEqual(resolve_keep_list_by_format(["SubRip/SRT"], tracks), ["1", "2"])
        self.assertEqual(normalize_track_id_text("02"), "2")
        self.assertEqual(normalize_track_id_text("2"), "2")

    def test_keep_only_second_subtitle_by_order(self):
        GlobalSetting.DESTINATION_FOLDER_PATH = str(self._work_dir / "out")
        GlobalSetting.MUX_SETTING_ONLY_KEEP_THOSE_SUBTITLES_ENABLED = True
        GlobalSetting.MUX_SETTING_ONLY_KEEP_THOSE_SUBTITLES_TRACKS_ORDERS = ["Order 2"]
        job = self.make_job(self.movie)
        command = self.build_command(job)
        self.assertIn("--subtitle-tracks", command)
        self.assertEqual(command[command.index("--subtitle-tracks") + 1], "2")
        self.assertNotIn("--no-subtitles", command)

        command[command.index("--output") + 1] = str(self._work_dir / "out" / "kept.mkv")
        write_json_job(command)
        result = run_json_job()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        output_tracks = read_media_info(self._work_dir / "out" / "kept.mkv")["tracks"]
        subtitles = [track for track in output_tracks if track["type"] == "subtitles"]
        self.assertEqual(len(subtitles), 1)
        self.assertEqual(subtitles[0]["properties"]["language"], "fre")

    def test_keep_by_format_writes_both_tracks(self):
        GlobalSetting.DESTINATION_FOLDER_PATH = str(self._work_dir / "out")
        GlobalSetting.MUX_SETTING_ONLY_KEEP_THOSE_SUBTITLES_ENABLED = True
        GlobalSetting.MUX_SETTING_ONLY_KEEP_THOSE_SUBTITLES_TRACKS_FORMATS = ["SubRip/SRT"]
        command = self.build_command(self.make_job(self.movie))
        self.assertEqual(command[command.index("--subtitle-tracks") + 1], "1,2")


class RelativeDestinationTests(Batch5TestCase):
    def test_relative_destination_detection(self):
        self.assertTrue(is_relative_destination_folder(".\\converted"))
        self.assertTrue(is_relative_destination_folder("converted"))
        self.assertTrue(is_relative_destination_folder("../out"))
        self.assertFalse(is_relative_destination_folder("C:\\out"))
        self.assertFalse(is_relative_destination_folder("C:converted"))
        self.assertFalse(is_relative_destination_folder(""))
        self.assertFalse(is_relative_destination_folder("   "))

    def test_output_paths_follow_each_source(self):
        first = self.make_movie(self._work_dir / "season1")
        second = self.make_movie(self._work_dir / "season2" / "extras")
        GlobalSetting.DESTINATION_FOLDER_PATH = ".\\converted"
        for source in (first, second):
            job = self.make_job(source)
            self.assertTrue(uses_relative_destination(job))
            self.assertEqual(get_output_folder_path(job),
                             os.path.join(os.path.dirname(str(source)), "converted"))
            self.assertEqual(get_output_file_path(job),
                             os.path.join(os.path.dirname(str(source)), "converted", "movie.mkv"))

    def test_absolute_destination_is_unchanged(self):
        source = self.make_movie(self._work_dir / "library")
        GlobalSetting.DESTINATION_FOLDER_PATH = str(self._work_dir / "out")
        job = self.make_job(source)
        self.assertFalse(uses_relative_destination(job))
        self.assertEqual(get_output_folder_path(job), str(self._work_dir / "out"))
        self.assertEqual(get_output_file_name(job), "movie.mkv")

    def test_muxing_writes_next_to_each_source(self):
        first = self.make_movie(self._work_dir / "season1")
        second = self.make_movie(self._work_dir / "season2")
        GlobalSetting.DESTINATION_FOLDER_PATH = ".\\converted"
        for source in (first, second):
            command = self.build_command(self.make_job(source))
            result = run_json_job()
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            expected = Path(os.path.dirname(str(source))) / "converted" / "movie.mkv"
            self.assertTrue(expected.exists(), "expected output at " + str(expected))
        # The old "one folder for the queue" behaviour is not used.
        self.assertFalse((self._work_dir / "converted").exists())


class ExtraArgumentsTests(Batch5TestCase):
    def test_tokenizer_drops_output_overrides(self):
        self.assertEqual(split_extra_arguments('--no-date --title "My Movie"'),
                         ["--no-date", "--title", "My Movie"])
        self.assertEqual(split_extra_arguments("-o out.mkv --keep-me"), ["--keep-me"])
        self.assertEqual(split_extra_arguments("--output=x.mkv --keep-me"), ["--keep-me"])
        self.assertEqual(split_extra_arguments("   "), [])

    def test_unbalanced_quote_does_not_abort_the_queue(self):
        """A half typed quote is a normal state of the field, not a crash."""
        self.assertEqual(split_extra_arguments('--no-date --title "My Movie'),
                         ["--no-date", "--title", '"My', "Movie"])
        self.assertEqual(split_extra_arguments("--no-date --title 'My Movie"),
                         ["--no-date", "--title", "'My", "Movie"])
        self.assertEqual(split_extra_arguments('-o out.mkv --title "x'), ["--title", '"x'])

    def test_extra_arguments_reach_the_job_json(self):
        movie = self.make_movie(self._work_dir / "library")
        GlobalSetting.DESTINATION_FOLDER_PATH = str(self._work_dir / "out")
        GlobalSetting.MUX_SETTING_EXTRA_ARGUMENTS = '--title "Chosen Title"'
        command = self.build_command(self.make_job(movie))
        self.assertIn("Chosen Title", command)
        self.assertIn(str(movie), command)
        self.assertLess(command.index("Chosen Title"), command.index(str(movie)))

        command[command.index("--output") + 1] = str(self._work_dir / "out" / "titled.mkv")
        write_json_job(command)
        result = run_json_job()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        info = read_media_info(self._work_dir / "out" / "titled.mkv")
        self.assertEqual(info["container"]["properties"]["title"], "Chosen Title")

    def test_stop_after_video_ends_flag(self):
        movie = self.make_movie(self._work_dir / "library")
        GlobalSetting.DESTINATION_FOLDER_PATH = str(self._work_dir / "out")
        GlobalSetting.MUX_SETTING_STOP_AFTER_VIDEO_ENDS = True
        command = self.build_command(self.make_job(movie))
        self.assertIn("--stop-after-video-ends", command)

    def test_new_options_disable_mkvpropedit(self):
        GlobalSetting.VIDEO_SOURCE_MKV_ONLY = True
        self.assertTrue(check_if_mkvpropedit_can_be_used())
        GlobalSetting.MUX_SETTING_EXTRA_ARGUMENTS = "--no-date"
        self.assertFalse(check_if_mkvpropedit_can_be_used())
        GlobalSetting.MUX_SETTING_EXTRA_ARGUMENTS = ""
        GlobalSetting.MUX_SETTING_STOP_AFTER_VIDEO_ENDS = True
        self.assertFalse(check_if_mkvpropedit_can_be_used())
        GlobalSetting.MUX_SETTING_STOP_AFTER_VIDEO_ENDS = False
        GlobalSetting.MUX_SETTING_OUTPUT_NAME_PATTERN = "%source% - x"
        self.assertFalse(check_if_mkvpropedit_can_be_used())

    def test_extra_arguments_skip_the_nothing_to_do_shortcut(self):
        movie = self.make_movie(self._work_dir / "library")
        GlobalSetting.OVERWRITE_SOURCE_FILES = True
        job = self.make_job(movie)
        self.assertTrue(job_has_nothing_to_do(job))
        GlobalSetting.MUX_SETTING_EXTRA_ARGUMENTS = "--no-date"
        self.assertFalse(job_has_nothing_to_do(job))

    def test_output_name_pattern_skips_the_nothing_to_do_shortcut(self):
        """A pattern renames the file, so the job is not a no-op (#111)."""
        movie = self.make_movie(self._work_dir / "library")
        GlobalSetting.OVERWRITE_SOURCE_FILES = True
        job = self.make_job(movie)
        self.assertTrue(job_has_nothing_to_do(job))
        GlobalSetting.MUX_SETTING_OUTPUT_NAME_PATTERN = "renamed"
        self.assertFalse(job_has_nothing_to_do(job))
        GlobalSetting.MUX_SETTING_OUTPUT_NAME_PATTERN = "   "
        self.assertTrue(job_has_nothing_to_do(job))


class ChapterDelayTests(Batch5TestCase):
    def test_first_chapter_is_pinned_others_shift(self):
        shifted = shift_chapter_text(SUBTITLE_CHAPTER_XML, 1001)
        self.assertIn("<ChapterTimeStart>00:00:00.000000000</ChapterTimeStart>", shifted)
        self.assertIn("<ChapterTimeStart>00:00:11.001000000</ChapterTimeStart>", shifted)
        self.assertIn("<ChapterTimeEnd>00:00:16.001000000</ChapterTimeEnd>", shifted)

    def test_zero_delay_changes_nothing(self):
        self.assertEqual(shift_chapter_text(SUBTITLE_CHAPTER_XML, 0), SUBTITLE_CHAPTER_XML)

    def test_negative_delay_is_clamped_at_zero(self):
        shifted = shift_chapter_text(SUBTITLE_CHAPTER_XML, -70000)
        self.assertNotIn("00:00:10.000000000", shifted)
        self.assertIn("<ChapterTimeStart>00:00:00.000000000</ChapterTimeStart>", shifted)
        self.assertIn("<ChapterTimeEnd>00:00:00.000000000</ChapterTimeEnd>", shifted)

    def test_ogm_chapters_keep_their_precision(self):
        ogm = "CHAPTER01=00:00:00.000\nCHAPTER01NAME=Intro\nCHAPTER02=00:01:00.000\nCHAPTER02NAME=Part\n"
        shifted = shift_chapter_text(ogm, 1500)
        self.assertIn("CHAPTER01=00:00:00.000", shifted)
        self.assertIn("CHAPTER02=00:01:01.500", shifted)

    def test_shifted_copy_is_separate_from_the_user_file(self):
        chapters = self._work_dir / "chapters.xml"
        chapters.write_text(SUBTITLE_CHAPTER_XML, encoding="utf-8")
        movie = self.make_movie(self._work_dir / "library")
        job = self.make_job(movie)
        job.chapter_found = True
        job.chapter_name = chapters.name
        job.chapter_name_absolute = str(chapters)

        shifted_path = get_shifted_chapters_file_path(job, 1001)
        self.assertNotEqual(shifted_path, "")
        self.assertNotEqual(os.path.normcase(shifted_path), os.path.normcase(str(chapters)))
        self.assertEqual(chapters.read_text(encoding="utf-8"), SUBTITLE_CHAPTER_XML)
        self.assertIn("00:00:11.001000000", Path(shifted_path).read_text(encoding="utf-8"))

    def test_job_uses_the_shifted_chapter_file(self):
        chapters = self._work_dir / "chapters.xml"
        chapters.write_text(SUBTITLE_CHAPTER_XML, encoding="utf-8")
        movie = self.make_movie(self._work_dir / "library")
        GlobalSetting.DESTINATION_FOLDER_PATH = str(self._work_dir / "out")
        GlobalSetting.CHAPTER_ENABLED = True
        GlobalSetting.CHAPTER_DISCARD_OLD = True
        GlobalSetting.CHAPTER_DELAY_MILLISECONDS = 1001
        job = self.make_job(movie)
        job.chapter_found = True
        job.chapter_name = chapters.name
        job.chapter_name_absolute = str(chapters)
        command = self.build_command(job)
        chapter_argument = command[command.index("--chapters") + 1].replace("\\\\", "\\")
        self.assertNotEqual(chapter_argument, str(chapters))
        self.assertIn("00:00:11.001000000", Path(chapter_argument).read_text(encoding="utf-8"))

        result = run_json_job()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        info = read_media_info(self._work_dir / "out" / "movie.mkv")
        chapters_info = info.get("chapters") or []
        if isinstance(chapters_info, list) and chapters_info:
            self.assertEqual(chapters_info[0]["num_entries"], 2)


class OutputNamePatternTests(Batch5TestCase):
    def test_pattern_matrix(self):
        movie = self.make_movie(self._work_dir / "library", name="Show.S01E03.mkv")
        job = self.make_job(movie, queue_index=3)
        self.assertEqual(apply_output_name_pattern(job, ""), "")
        self.assertEqual(apply_output_name_pattern(job, "%source% - converted"),
                         "Show.S01E03 - converted.mkv")
        self.assertEqual(
            apply_output_name_pattern(job, "Name - %episode% [%resolution%]", resolution="1920x1080"),
            "Name - 03 [1920x1080].mkv")
        # An unresolved variable must not leave empty brackets behind.
        self.assertEqual(apply_output_name_pattern(job, "%source% <%sublang%>"), "Show.S01E03.mkv")

    def test_invalid_characters_are_replaced(self):
        self.assertEqual(sanitize_output_file_name('a<b>c:d"e/f\\g|h?i*j'), "a_b_c_d_e_f_g_h_i_j")
        self.assertEqual(remove_empty_brackets("a [] b () c"), "a b c")

    def test_unknown_variables_are_reported(self):
        self.assertEqual(get_unknown_pattern_variables("%source% - x"), [])
        self.assertEqual(get_unknown_pattern_variables("%bogus% - %source%"), ["%bogus%"])

    def test_crc_placeholder_survives_for_the_crc_step(self):
        movie = self.make_movie(self._work_dir / "library", name="clip.mkv")
        job = self.make_job(movie)
        job.is_crc_calculating_required = True
        name = apply_output_name_pattern(job, "%source% [%crc%]", keep_crc_placeholder=True)
        self.assertEqual(name, "clip [%crc%].mkv")

    def test_constant_pattern_does_not_collide_in_one_run(self):
        movie = self.make_movie(self._work_dir / "library")
        first = self.make_job(movie, queue_index=1)
        second = self.make_job(movie, queue_index=2)
        GlobalSetting.MUX_SETTING_OUTPUT_NAME_PATTERN = "converted"
        GlobalSetting.MUX_SETTING_USED_OUTPUT_NAMES = set()
        names = []
        for job in (first, second):
            job.custom_output_name = apply_output_name_pattern(job, "converted")
            names.append(make_output_name_unique(job))
        self.assertEqual(names, ["converted.mkv", "converted (2).mkv"])

    def test_constant_pattern_does_not_collide_across_source_folders(self):
        """An absolute destination puts every job in the same folder, so two
        same-named episodes of different seasons must not overwrite each other."""
        first_movie = self.make_movie(self._work_dir / "season1")
        second_movie = self.make_movie(self._work_dir / "season2")
        GlobalSetting.DESTINATION_FOLDER_PATH = str(self._work_dir / "out")
        GlobalSetting.MUX_SETTING_USED_OUTPUT_NAMES = set()
        jobs = [self.make_job(first_movie, queue_index=1),
                self.make_job(second_movie, queue_index=2)]
        for job in jobs:
            job.custom_output_name = apply_output_name_pattern(job, "converted")
            make_output_name_unique(job)
        self.assertEqual([job.custom_output_name for job in jobs],
                         ["converted.mkv", "converted (2).mkv"])
        self.assertEqual(len({get_output_file_path(job) for job in jobs}), 2)

    def test_relative_destination_still_uses_one_name_per_folder(self):
        """The same name in two different output folders is not a collision."""
        first_movie = self.make_movie(self._work_dir / "season1")
        second_movie = self.make_movie(self._work_dir / "season2")
        GlobalSetting.DESTINATION_FOLDER_PATH = ".\\converted"
        GlobalSetting.MUX_SETTING_USED_OUTPUT_NAMES = set()
        jobs = [self.make_job(first_movie, queue_index=1),
                self.make_job(second_movie, queue_index=2)]
        for job in jobs:
            job.custom_output_name = apply_output_name_pattern(job, "converted")
            make_output_name_unique(job)
        self.assertEqual([job.custom_output_name for job in jobs],
                         ["converted.mkv", "converted.mkv"])
        self.assertEqual(len({get_output_file_path(job) for job in jobs}), 2)

    def test_failed_job_records_the_path_the_muxer_wrote(self):
        """record_failed_job_output() must match setup_output_video_command()."""
        movie = self.make_movie(self._work_dir / "library")
        job = self.make_job(movie)
        job.custom_output_name = "converted.mkv"
        GlobalSetting.DESTINATION_FOLDER_PATH = str(self._work_dir / "out")
        expected = get_output_file_path(job)

        recorded = JobOutputFiles.record_failed_job_output(job)

        self.assertEqual(os.path.normcase(recorded), os.path.normcase(expected))
        self.assertEqual(job.output_video_name, "converted.mkv")

    def test_muxing_honours_the_pattern(self):
        movie = self.make_movie(self._work_dir / "library", name="Show.S01E03.mkv")
        GlobalSetting.DESTINATION_FOLDER_PATH = str(self._work_dir / "out")
        GlobalSetting.MUX_SETTING_OUTPUT_NAME_PATTERN = "%source% - %episode%"
        GlobalSetting.MUX_SETTING_USED_OUTPUT_NAMES = set()
        command = self.build_command(self.make_job(movie, queue_index=4))
        output_argument = command[command.index("--output") + 1].replace("\\\\", "\\")
        self.assertEqual(os.path.basename(output_argument), "Show.S01E03 - 04.mkv")
        result = run_json_job()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self._work_dir / "out" / "Show.S01E03 - 04.mkv").exists())


class SubtitleFontTests(Batch5TestCase):
    def test_font_names_are_read_from_every_format(self):
        self.assertEqual(sorted(get_font_names_from_subtitle_text(ASS_SUBTITLE)),
                         ["Arial", "Futura Bold", "Open Sans"])
        self.assertEqual(
            sorted(get_font_names_from_subtitle_text(
                '1\n00:00:01,000 --> 00:00:02,000\n<font face="Verdana">Hi</font>\n')),
            ["Verdana"])

    def test_font_keys_ignore_spacing_and_case(self):
        self.assertEqual(normalize_font_key("Open Sans-Bold"), "opensansbold")
        self.assertEqual(normalize_font_key("opensansbold.ttf"), "opensansboldttf")

    def test_matching_finds_the_font_files(self):
        fonts = self._work_dir / "fonts"
        fonts.mkdir(parents=True)
        for name in ("OpenSans-Regular.ttf", "FuturaBold.otf", "Unrelated.ttc"):
            (fonts / name).write_bytes(b"font")
        matches = [os.path.basename(path) for path in
                   find_font_files_for_names({"Open Sans", "Futura Bold"}, [str(fonts)])]
        self.assertIn("OpenSans-Regular.ttf", matches)
        self.assertIn("FuturaBold.otf", matches)
        self.assertNotIn("Unrelated.ttc", matches)

    def test_job_attaches_the_fonts_of_its_subtitles(self):
        fonts = self._work_dir / "fonts"
        fonts.mkdir(parents=True)
        for name in ("OpenSans-Regular.ttf", "FuturaBold.otf"):
            (fonts / name).write_bytes(b"font")
        subtitle = self._work_dir / "episode.ass"
        subtitle.write_text(ASS_SUBTITLE, encoding="utf-8")
        movie = self.make_movie(self._work_dir / "library")
        self.assertIn("Open Sans", get_font_names_from_subtitle_file(str(subtitle)))

        job = self.make_job(movie)
        job.subtitle_found = True
        job.subtitle_name = [subtitle.name]
        job.subtitle_name_absolute = [str(subtitle)]
        job.subtitle_language = ["eng"]
        job.subtitle_track_name = [""]
        job.subtitle_delay = [0.0]
        job.subtitle_set_default = [False]
        job.subtitle_set_forced = [False]
        job.subtitle_set_at_top = [-1]

        GlobalSetting.ATTACHMENT_SEARCH_FOLDERS = [str(fonts)]
        GlobalSetting.ATTACHMENT_AUTO_DETECT_FONTS = True
        attached = [os.path.basename(path) for path in get_subtitle_font_attachments(job)]
        self.assertIn("OpenSans-Regular.ttf", attached)
        self.assertIn("FuturaBold.otf", attached)

    def test_muxing_attaches_the_detected_fonts(self):
        fonts = self._work_dir / "fonts"
        fonts.mkdir(parents=True)
        for name in ("OpenSans-Regular.ttf", "FuturaBold.otf"):
            (fonts / name).write_bytes(b"font")
        subtitle = self._work_dir / "episode.ass"
        subtitle.write_text(ASS_SUBTITLE, encoding="utf-8")
        movie = self.make_movie(self._work_dir / "library")
        GlobalSetting.DESTINATION_FOLDER_PATH = str(self._work_dir / "out")
        GlobalSetting.ATTACHMENT_SEARCH_FOLDERS = [str(fonts)]
        GlobalSetting.ATTACHMENT_AUTO_DETECT_FONTS = True

        job = self.make_job(movie)
        job.subtitle_found = True
        job.subtitle_name = [subtitle.name]
        job.subtitle_name_absolute = [str(subtitle)]
        job.subtitle_language = ["eng"]
        job.subtitle_track_name = [""]
        job.subtitle_delay = [0.0]
        job.subtitle_set_default = [False]
        job.subtitle_set_forced = [False]
        job.subtitle_set_at_top = [-1]
        command = self.build_command(job)
        attached = [command[index + 1] for index, argument in enumerate(command)
                    if argument == "--attach-file"]
        self.assertEqual(len(attached), 2)

        result = run_json_job()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        info = read_media_info(self._work_dir / "out" / "movie.mkv")
        names = [item["file_name"] for item in info.get("attachments", [])]
        self.assertIn("OpenSans-Regular.ttf", names)
        self.assertIn("FuturaBold.otf", names)


if __name__ == "__main__":
    unittest.main()
