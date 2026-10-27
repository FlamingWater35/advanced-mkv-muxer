import unittest

import tests  # noqa: F401  (must run before application imports)

from packages.Startup.PreDefined import ISO_639_2_LANGUAGES, generate_track_ids
from packages.Tabs.GlobalSetting import (
    convert_string_integer_to_two_digit_string,
    get_readable_filesize,
    sort_names_like_windows,
)
from packages.Tabs.MuxSetting.Widgets.GetJsonForMkvmergeJob import (
    add_double_quotation,
    add_json_line,
    add_two_spaces,
    change_file_extension_to_mkv,
    check_type_of_track_chosen,
    delete_trailing_zero_string,
)
from packages.Tabs.MuxSetting.Widgets.MuxingParams import MuxingParams
from packages.Tabs.MuxSetting.Widgets.SingleJobData import SingleJobData
from packages.Widgets.SingleTrackData import SingleTrackData


class CoreHelperTests(unittest.TestCase):
    def test_track_id_generation(self):
        self.assertEqual(generate_track_ids(3), ["Track 01", "Track 02", "Track 03"])

    def test_language_data_is_loaded(self):
        self.assertGreater(len(ISO_639_2_LANGUAGES), 0)
        self.assertIn("English", ISO_639_2_LANGUAGES)

    def test_json_line_helpers(self):
        self.assertEqual(add_two_spaces(), "  ")
        self.assertEqual(add_double_quotation("value"), '  "value"')
        self.assertEqual(add_json_line("value"), '\n  "value",')

    def test_trailing_zero_removal(self):
        self.assertEqual(delete_trailing_zero_string("03"), "3")
        self.assertEqual(delete_trailing_zero_string("24"), "24")

    def test_extension_change(self):
        self.assertEqual(change_file_extension_to_mkv("movie.mp4"), "movie.mkv")
        self.assertEqual(change_file_extension_to_mkv("show.S01E01.mkv"), "show.S01E01.mkv")

    def test_track_type_parsing(self):
        self.assertEqual(check_type_of_track_chosen("Track Id: [3]"), ("id", "3"))
        self.assertEqual(check_type_of_track_chosen("Language: [eng]"), ("lang", "eng"))
        self.assertEqual(check_type_of_track_chosen("Track Name: [Main]"), ("name", "Main"))
        self.assertIsNone(check_type_of_track_chosen("unknown"))

    def test_two_digit_conversion(self):
        self.assertEqual(convert_string_integer_to_two_digit_string(3), "03")
        self.assertEqual(convert_string_integer_to_two_digit_string(12), "12")

    def test_readable_file_size(self):
        self.assertEqual(get_readable_filesize(1024), "1.00 KB")
        self.assertEqual(get_readable_filesize(1024 * 1024), "1.00 MB")

    def test_windows_style_sort(self):
        self.assertEqual(
            sort_names_like_windows(["file10.mkv", "file2.mkv", "file1.mkv"]),
            ["file1.mkv", "file2.mkv", "file10.mkv"],
        )


class DataContainerTests(unittest.TestCase):
    def test_single_job_data_defaults(self):
        job = SingleJobData()
        self.assertEqual(job.video_name, "")
        self.assertFalse(job.subtitle_found)
        self.assertFalse(job.audio_found)
        self.assertEqual(job.attachments_absolute_path, [])
        self.assertFalse(job.done)

    def test_muxing_params_defaults(self):
        params = MuxingParams()
        self.assertEqual(params.index, 0)
        self.assertEqual(params.progress, 0)
        self.assertFalse(params.error)
        self.assertEqual(params.message, "Muxing Done Successfully")

    def test_single_track_data_defaults(self):
        track = SingleTrackData()
        self.assertEqual(track.codec, "")
        self.assertEqual(track.id, "")
        self.assertEqual(track.language, "")
