"""Regression tests for batch 3.

Covers the video-list actions (#161 select all, #140 open file), the queue
size-change footer (#142) and the configurable overwrite relay folder (#143).
"""

import json
import os
import subprocess
import unittest
import wave
from pathlib import Path
from unittest import mock

import tests  # noqa: F401  (must run before application imports)

from PySide6.QtGui import Qt

from packages.Startup import GlobalFiles
from packages.Tabs.GlobalSetting import GlobalSetting
from packages.Tabs.MuxSetting.MuxSetting import MuxSettingTab
from packages.Tabs.MuxSetting.Widgets import JobOutputFiles
from packages.Tabs.MuxSetting.Widgets.GetJsonForMkvmergeJob import GetJsonForMkvmergeJob
from packages.Tabs.MuxSetting.Widgets.JobQueueTable import JobQueueTable
from packages.Tabs.MuxSetting.Widgets.OverwriteFilesDialog import OverwriteFilesDialog
from packages.Tabs.MuxSetting.Widgets.SingleJobData import SingleJobData
from packages.Tabs.MuxSetting.Widgets.TotalSizeChangeLabel import TotalSizeChangeLabel
from packages.Tabs.VideoTab import VideoSelection as video_selection_module
from packages.Tabs.VideoTab.VideoSelection import VideoSelectionSetting
from packages.Tabs.VideoTab.Widgets.SelectAllVideosCheckBox import SelectAllVideosCheckBox
from packages.Tabs.VideoTab.Widgets.VideoTable import VideoTable

GLOBAL_SETTING_KEYS = (
    "OVERWRITE_SOURCE_FILES",
    "OVERWRITE_TEMP_FOLDER_PATH",
    "RANDOM_OUTPUT_SUFFIX",
    "DESTINATION_FOLDER_PATH",
    "JOB_QUEUE_EMPTY",
    "VIDEO_FILES_LIST",
    "VIDEO_FILES_ABSOLUTE_PATH_LIST",
    "VIDEO_FILES_SIZE_LIST",
    "VIDEO_SOURCE_PATHS",
    "VIDEO_SOURCE_MKV_ONLY",
)


class Batch3TestCase(unittest.TestCase):
    def setUp(self):
        self._saved_values = {key: getattr(GlobalSetting, key) for key in GLOBAL_SETTING_KEYS}
        self._work_dir = Path(tests.TEMP_ROOT) / self._testMethodName
        self._work_dir.mkdir(parents=True, exist_ok=True)
        GlobalSetting.OVERWRITE_SOURCE_FILES = False
        GlobalSetting.OVERWRITE_TEMP_FOLDER_PATH = ""
        GlobalSetting.RANDOM_OUTPUT_SUFFIX = ""

    def tearDown(self):
        for key, value in self._saved_values.items():
            setattr(GlobalSetting, key, value)


class SelectAllVideosTests(Batch3TestCase):
    def test_states_are_computed_without_emitting(self):
        checkbox = SelectAllVideosCheckBox()
        emitted = []
        checkbox.toggle_all_signal.connect(emitted.append)

        checkbox.set_state(0, 3)
        self.assertEqual(checkbox.checkState(), Qt.CheckState.Unchecked)
        checkbox.set_state(1, 3)
        self.assertEqual(checkbox.checkState(), Qt.CheckState.PartiallyChecked)
        checkbox.set_state(3, 3)
        self.assertEqual(checkbox.checkState(), Qt.CheckState.Checked)

        self.assertEqual(emitted, [])

    def test_clicking_a_partial_box_selects_everything(self):
        checkbox = SelectAllVideosCheckBox()
        emitted = []
        checkbox.toggle_all_signal.connect(emitted.append)
        checkbox.set_state(1, 3)

        checkbox.nextCheckState()

        self.assertEqual(checkbox.checkState(), Qt.CheckState.Checked)
        self.assertEqual(emitted, [True])

    def test_clicking_a_checked_box_deselects_everything(self):
        checkbox = SelectAllVideosCheckBox()
        emitted = []
        checkbox.toggle_all_signal.connect(emitted.append)
        checkbox.set_state(3, 3)

        checkbox.nextCheckState()

        self.assertEqual(checkbox.checkState(), Qt.CheckState.Unchecked)
        self.assertEqual(emitted, [False])


class VideoListActionTests(Batch3TestCase):
    @staticmethod
    def build_table():
        table = VideoTable()
        # Same guard VideoSelection uses while it rebuilds the rows.
        table.checking_row_updates = False
        table.show_files_list(files_names_list=["a.mkv", "b.mkv"],
                              files_names_checked_list=[True, True],
                              files_size_list=[" 1.00 KB", " 2.00 KB"])
        table.checking_row_updates = True
        return table

    def test_double_click_on_the_name_column_emits_the_row(self):
        table = self.build_table()
        opened = []
        table.open_video_file_signal.connect(opened.append)

        table.cell_double_clicked(1, table.column_ids["Name"])
        table.cell_double_clicked(0, table.column_ids["Size"])

        self.assertEqual(opened, [1])

    def test_enter_opens_the_current_row(self):
        table = self.build_table()
        opened = []
        table.open_video_file_signal.connect(opened.append)
        table.selectRow(1)

        class EnterKey:
            @staticmethod
            def key():
                return Qt.Key.Key_Return

        table.keyPressEvent(EnterKey())

        self.assertEqual(opened, [1])

    def test_open_video_file_uses_the_matching_absolute_path(self):
        selection = VideoSelectionSetting()
        selection.files_names_absolute_list = ["/videos/a.mkv", "/videos/b.mkv"]
        with mock.patch.object(video_selection_module, "open_local_file") as open_local_file:
            selection.open_video_file(1)
            selection.open_video_file(5)
        open_local_file.assert_called_once_with("/videos/b.mkv")

    def test_select_all_updates_the_list_and_the_checkbox(self):
        selection = VideoSelectionSetting()
        selection.files_names_list = ["a.mkv", "b.mkv"]
        selection.files_names_absolute_list = ["/videos/a.mkv", "/videos/b.mkv"]
        selection.files_size_list = [" 1.00 KB", " 2.00 KB"]
        selection.files_names_checked_list = [True, False]

        with mock.patch.object(video_selection_module, "update_global_videos_tracks_info"):
            selection.set_all_videos(False)

        self.assertEqual(selection.files_names_checked_list, [False, False])
        self.assertEqual(selection.select_all_videos_checkBox.checkState(), Qt.CheckState.Unchecked)
        with mock.patch.object(video_selection_module, "update_global_videos_tracks_info"):
            selection.set_all_videos(True)
        self.assertEqual(selection.files_names_checked_list, [True, True])
        self.assertEqual(selection.select_all_videos_checkBox.checkState(), Qt.CheckState.Checked)


class TotalSizeChangeTests(Batch3TestCase):
    def test_label_formatting(self):
        label = TotalSizeChangeLabel()

        label.update_total_size_change(0)
        self.assertEqual(label.text(), " Size Change: 0.00 B")
        label.update_total_size_change(1024)
        self.assertEqual(label.text(), " Size Change: +1.00 KB")
        label.update_total_size_change(-1024 * 1024)
        self.assertEqual(label.text(), " Size Change: -1.00 MB")

    def test_queue_accumulates_the_size_change_of_finished_jobs(self):
        first = self._work_dir / "first.mkv"
        second = self._work_dir / "second.mkv"
        first.write_bytes(b"a" * 100)
        second.write_bytes(b"b" * 200)
        GlobalSetting.VIDEO_FILES_LIST = [first.name, second.name]
        GlobalSetting.VIDEO_FILES_ABSOLUTE_PATH_LIST = [str(first), str(second)]
        GlobalSetting.VIDEO_FILES_SIZE_LIST = [" 100.00 B", " 200.00 B"]
        table = JobQueueTable()
        changes = []
        table.update_total_size_change_signal.connect(changes.append)

        table.setup_queue()
        self.assertEqual(table.data[0].size_before_muxing_bytes, 100)
        self.assertEqual(table.data[1].size_before_muxing_bytes, 200)

        table.new_job_started(0)
        table.job_done_successfully(0, 512)
        table.new_job_started(1)
        table.job_done_successfully(1, 256)

        self.assertEqual(changes[-2:], [412, 468])
        self.assertEqual(table.total_size_change_bytes, 468)

        table.clear_queue()
        self.assertEqual(changes[-1], 0)


class OverwriteTempFolderTests(Batch3TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_dir = Path(tests.TEMP_ROOT) / "file_actions_fixture"
        cls.fixture_dir.mkdir(parents=True, exist_ok=True)
        audio = cls.fixture_dir / "audio.wav"
        with wave.open(str(audio), "wb") as audio_file:
            audio_file.setnchannels(1)
            audio_file.setsampwidth(2)
            audio_file.setframerate(8000)
            audio_file.writeframes(b"\x00\x00" * 8000)
        cls.source = cls.fixture_dir / "movie.mkv"
        result = subprocess.run(
            [GlobalFiles.MKVMERGE_PATH, "-o", str(cls.source), str(audio)],
            capture_output=True, text=True, env=GlobalFiles.ENVIRONMENT)
        if result.returncode != 0:
            raise RuntimeError("could not build the fixture: " + result.stdout + result.stderr)

    def test_temp_path_defaults_to_the_source_folder(self):
        job = SingleJobData()
        job.video_name = "movie.mkv"
        job.video_name_absolute = str(self.source)
        GlobalSetting.RANDOM_OUTPUT_SUFFIX = "999"

        temp_path = JobOutputFiles.get_overwrite_temp_path(job)

        self.assertEqual(os.path.dirname(temp_path), str(self.fixture_dir))
        self.assertTrue(os.path.basename(temp_path).startswith("movie#999.mkv"))

    def test_temp_path_uses_the_configured_folder(self):
        relay = self._work_dir / "relay"
        relay.mkdir()
        job = SingleJobData()
        job.video_name = "movie.mkv"
        job.video_name_absolute = str(self.source)
        GlobalSetting.RANDOM_OUTPUT_SUFFIX = "999"
        GlobalSetting.OVERWRITE_TEMP_FOLDER_PATH = str(relay)

        temp_path = JobOutputFiles.get_overwrite_temp_path(job)

        self.assertEqual(os.path.dirname(temp_path), str(relay))

    def test_job_json_writes_the_output_into_the_relay_folder(self):
        relay = self._work_dir / "relay"
        relay.mkdir()
        GlobalSetting.OVERWRITE_SOURCE_FILES = True
        GlobalSetting.RANDOM_OUTPUT_SUFFIX = "999"
        GlobalSetting.OVERWRITE_TEMP_FOLDER_PATH = str(relay)
        job = SingleJobData()
        job.video_name = "movie.mkv"
        job.video_name_absolute = str(self.source)

        GetJsonForMkvmergeJob(job)
        command = json.loads(Path(GlobalFiles.mkvmergeJsonJobFilePath).read_text(encoding="utf-8"))

        output_path = command[command.index("--output") + 1]
        self.assertEqual(os.path.dirname(output_path), str(relay))
        self.assertTrue(os.path.basename(output_path).startswith("movie#999.mkv"))

    def test_finalize_moves_the_relay_file_over_the_source(self):
        relay = self._work_dir / "relay"
        relay.mkdir()
        GlobalSetting.OVERWRITE_SOURCE_FILES = True
        GlobalSetting.RANDOM_OUTPUT_SUFFIX = "999"
        GlobalSetting.OVERWRITE_TEMP_FOLDER_PATH = str(relay)
        source = self._work_dir / "movie.mkv"
        source.write_bytes(b"old source")
        job = SingleJobData()
        job.video_name = "movie.mkv"
        job.video_name_absolute = str(source)
        temp_path = Path(JobOutputFiles.get_overwrite_temp_path(job))
        temp_path.write_bytes(b"new muxed file")

        output_path = JobOutputFiles.finalize_muxing_output(job)

        self.assertEqual(Path(output_path), source)
        self.assertEqual(source.read_bytes(), b"new muxed file")
        self.assertFalse(temp_path.exists())

    def test_overwrite_dialog_exposes_the_relay_folder(self):
        dialog = OverwriteFilesDialog()
        self.assertEqual(dialog.temp_folder_path, "")

        dialog.temp_folder_lineEdit.setText("  " + str(self._work_dir) + "  ")

        self.assertEqual(dialog.temp_folder_path, str(self._work_dir))

    def test_relay_folder_validation(self):
        tab = MuxSettingTab()
        relay = self._work_dir / "relay_check"

        self.assertTrue(tab.check_relay_folder(str(relay)))
        self.assertTrue(relay.is_dir())
