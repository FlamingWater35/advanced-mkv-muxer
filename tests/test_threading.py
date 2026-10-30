"""Threading tests for the muxing pipeline.

These tests pin the contract that the GUI thread never performs muxing file
I/O: the worker hands finished jobs over by signal, the CRC/progress signals
are throttled, and the helper threads always stop and join.
"""

import json
import os
import sys
import time
import unittest
import zlib
from pathlib import Path
from unittest import mock

import tests  # noqa: F401  (must run before application imports)

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QApplication

from packages.Startup import GlobalFiles
from packages.Tabs.GlobalSetting import GlobalSetting
from packages.Tabs.MuxSetting.Widgets import JobOutputFiles
from packages.Tabs.MuxSetting.Widgets import StartMuxingWorker as start_muxing_worker_module
from packages.Tabs.MuxSetting.Widgets.CalculateCRCProcessWorker import CalculateCRCProcessWorker
from packages.Tabs.MuxSetting.Widgets.SingleJobData import SingleJobData
from packages.Tabs.MuxSetting.Widgets.StartMuxingProcessWorker import StartMuxingProcessWorker

FAKE_PAYLOAD = b"fake mkv payload"

FAKE_TOOL_SOURCE = '''\
import json
import sys
import time

job_path = sys.argv[1].strip()
if job_path.startswith("@"):
    job_path = job_path[1:]
if len(job_path) > 1 and job_path[0] == '"' and job_path[-1] == '"':
    job_path = job_path[1:-1]
output_path = ""
try:
    with open(job_path, encoding="utf-8") as job_file:
        job_command = json.load(job_file)
    if "--output" in job_command:
        output_path = job_command[job_command.index("--output") + 1]
except Exception:
    output_path = ""
slow = "--fast" not in sys.argv
print("mkvmerge v0.0.0 ('fake') 64-bit")
if "--fail" in sys.argv:
    print("Error: fake muxing failure")
    sys.stdout.flush()
    sys.exit(2)
for percent in (25, 50, 75, 100):
    print("Progress: %d%%" % percent)
    sys.stdout.flush()
    if slow:
        time.sleep(0.01)
if output_path:
    with open(output_path, "wb") as output_file:
        output_file.write(b"fake mkv payload")
print("Multiplexing took 00:00:01")
sys.stdout.flush()
'''

GLOBAL_SETTING_KEYS = (
    "VIDEO_SOURCE_MKV_ONLY",
    "OVERWRITE_SOURCE_FILES",
    "DESTINATION_FOLDER_PATH",
    "RANDOM_OUTPUT_SUFFIX",
    "USE_MKVPROPEDIT",
    "MUX_SETTING_ADD_CRC",
    "MUX_SETTING_REMOVE_OLD_CRC",
    "MUX_SETTING_ABORT_ON_ERRORS",
    "MUXING_ON",
)


def process_events_until(predicate, timeout=20.0):
    """Spin the shared event loop until predicate() is true or time runs out."""
    application = QApplication.instance()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        application.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    application.processEvents()
    return predicate()


class GlobalStateTestCase(unittest.TestCase):
    """Restores the shared GlobalSetting values each test may change."""

    def setUp(self):
        self._saved_globals = {key: getattr(GlobalSetting, key) for key in GLOBAL_SETTING_KEYS}
        self._saved_mkvmerge_path = GlobalFiles.MKVMERGE_PATH
        self._saved_log_path = GlobalFiles.MuxingLogFilePath
        self._work_dir = Path(tests.TEMP_ROOT) / self._testMethodName
        self._work_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        for key, value in self._saved_globals.items():
            setattr(GlobalSetting, key, value)
        GlobalFiles.MKVMERGE_PATH = self._saved_mkvmerge_path
        GlobalFiles.MuxingLogFilePath = self._saved_log_path


class OutputFinalizationTests(GlobalStateTestCase):
    def make_job(self, file_name="movie.mp4"):
        source = self._work_dir / file_name
        source.write_bytes(b"source")
        job = SingleJobData()
        job.video_name = file_name
        job.video_name_absolute = str(source)
        return job, source

    def test_output_goes_to_the_destination_folder(self):
        destination = self._work_dir / "dest"
        destination.mkdir()
        GlobalSetting.DESTINATION_FOLDER_PATH = str(destination)
        job, source = self.make_job()

        output_path = JobOutputFiles.finalize_muxing_output(job)

        self.assertEqual(Path(output_path), destination / "movie.mkv")
        self.assertEqual(job.output_video_name, "movie.mkv")
        self.assertEqual(job.output_video_absolute_path, str(destination / "movie.mkv"))
        self.assertTrue(source.exists())

    def test_overwrite_mode_replaces_the_source_file(self):
        GlobalSetting.OVERWRITE_SOURCE_FILES = True
        GlobalSetting.RANDOM_OUTPUT_SUFFIX = "12345"
        job, source = self.make_job()
        temporary_output = self._work_dir / JobOutputFiles.change_file_extension_to_mkv_with_random_suffix(
            job.video_name)
        temporary_output.write_bytes(b"muxed")

        output_path = JobOutputFiles.finalize_muxing_output(job)

        self.assertFalse(source.exists())
        self.assertEqual(Path(output_path).read_bytes(), b"muxed")
        self.assertEqual(Path(output_path).name, "movie.mkv")

    def test_crc_rename_moves_the_finished_file(self):
        destination = self._work_dir / "dest"
        destination.mkdir()
        GlobalSetting.DESTINATION_FOLDER_PATH = str(destination)
        job, _ = self.make_job()
        JobOutputFiles.finalize_muxing_output(job)
        Path(job.output_video_absolute_path).write_bytes(b"muxed")
        job.is_crc_calculating_required = True
        job.new_crc = "ABCD1234"

        output_path = JobOutputFiles.apply_crc_to_output_name(job)

        self.assertEqual(Path(output_path).name, "movie [ABCD1234].mkv")
        self.assertTrue(Path(output_path).exists())

    def test_size_of_an_empty_output_is_zero_and_the_file_is_removed(self):
        job, _ = self.make_job()
        empty_output = self._work_dir / "empty.mkv"
        empty_output.write_bytes(b"")
        job.output_video_absolute_path = str(empty_output)

        self.assertEqual(JobOutputFiles.get_output_size(job), 0)
        self.assertFalse(empty_output.exists())

    def test_rename_retry_gives_up_instead_of_blocking_forever(self):
        missing = self._work_dir / "missing.mkv"
        started = time.monotonic()
        renamed = JobOutputFiles.rename_file(str(missing), str(self._work_dir / "target.mkv"),
                                             attempts=3, delay=0.01)
        self.assertFalse(renamed)
        self.assertLess(time.monotonic() - started, 1.0)

    def test_a_failed_replace_restores_the_source_instead_of_losing_it(self):
        """The source is moved aside, not deleted, so a failed move can undo it."""
        GlobalSetting.OVERWRITE_SOURCE_FILES = True
        GlobalSetting.RANDOM_OUTPUT_SUFFIX = "12345"
        job, source = self.make_job()
        # The muxer never produced its output: the replace must not lose the source.
        job.output_video_absolute_path = ""

        output_path = JobOutputFiles.finalize_muxing_output(job)

        self.assertTrue(source.exists(), "the source file must survive a failed replace")
        self.assertEqual(source.read_bytes(), b"source")
        self.assertTrue(job.error_occurred)
        self.assertEqual(os.path.normcase(output_path),
                         os.path.normcase(JobOutputFiles.get_overwrite_temp_path(job)))
        self.assertFalse(Path(str(source) + ".amkv-old").exists())

    def test_a_successful_replace_removes_the_backup(self):
        GlobalSetting.OVERWRITE_SOURCE_FILES = True
        GlobalSetting.RANDOM_OUTPUT_SUFFIX = "12345"
        job, source = self.make_job()
        temporary_output = self._work_dir / JobOutputFiles.change_file_extension_to_mkv_with_random_suffix(
            job.video_name)
        temporary_output.write_bytes(b"muxed")

        output_path = JobOutputFiles.finalize_muxing_output(job)

        self.assertFalse(job.error_occurred)
        self.assertEqual(Path(output_path).read_bytes(), b"muxed")
        self.assertFalse(Path(str(source) + ".amkv-old").exists())

    def test_replace_refuses_to_lose_the_source_when_the_output_is_missing(self):
        source = self._work_dir / "original.mkv"
        source.write_bytes(b"ORIGINAL")

        replaced = JobOutputFiles.replace_source_with_output(
            str(source), str(self._work_dir / "not_there.mkv"), str(source))

        self.assertFalse(replaced)
        self.assertEqual(source.read_bytes(), b"ORIGINAL")


class CrcWorkerTests(GlobalStateTestCase):
    def run_crc_worker(self, file_path):
        worker = CalculateCRCProcessWorker()
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        results = []
        failures = []
        progress = []
        worker.crc_result_signal.connect(results.append)
        worker.crc_failed_signal.connect(failures.append)
        worker.crc_progress_signal.connect(progress.append)
        thread.start()
        try:
            worker.start_calculating(str(file_path))
            finished = process_events_until(lambda: bool(results) or bool(failures), timeout=20)
            self.assertTrue(finished, "CRC worker produced no signal")
        finally:
            worker.stop()
            self.assertTrue(thread.wait(5000), "CRC worker thread did not stop")
        return results, failures, progress

    def test_crc_matches_zlib_and_progress_is_throttled(self):
        payload = os.urandom(200 * 1024)
        file_path = self._work_dir / "output.mkv"
        file_path.write_bytes(payload)

        results, failures, progress = self.run_crc_worker(file_path)

        expected = format(zlib.crc32(payload) & 0xFFFFFFFF, "08x").upper()
        self.assertEqual(failures, [])
        self.assertEqual(results, [expected])
        # One update per percent, not one per 64 KiB chunk.
        self.assertLessEqual(len(progress), 101)
        self.assertEqual(progress, sorted(progress))
        self.assertEqual(progress[-1], 100)

    def test_missing_output_is_reported_instead_of_hanging(self):
        results, failures, _ = self.run_crc_worker(self._work_dir / "not_there.mkv")

        self.assertEqual(results, [])
        self.assertEqual(len(failures), 1)
        self.assertTrue(failures[0])


class ProcessWorkerTests(GlobalStateTestCase):
    def test_runs_one_command_then_stops(self):
        log_path = self._work_dir / "muxing.log"
        log_path.write_text("", encoding="utf-8")
        GlobalFiles.MuxingLogFilePath = str(log_path)
        marker = self._work_dir / "ran.txt"
        script = self._work_dir / "make_marker.py"
        script.write_text(
            "from pathlib import Path\nPath(r'{0}').write_text('ok')\n".format(marker),
            encoding="utf-8",
        )

        worker = StartMuxingProcessWorker()
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        exit_codes = []
        worker.finished_job_signal.connect(exit_codes.append)
        thread.start()
        try:
            worker.request_command('"{0}" "{1}"'.format(sys.executable, script))
            finished = process_events_until(lambda: bool(exit_codes), timeout=20)
            self.assertTrue(finished, "the command never ran")
            self.assertEqual(exit_codes, [0])
            self.assertTrue(marker.exists())
        finally:
            worker.stop()
            self.assertTrue(thread.wait(5000), "process worker thread did not stop")


class SignalRecorder(QObject):
    """Receives the worker signals on the GUI thread, like the job queue does."""

    def __init__(self):
        super().__init__()
        self.succeeded = []
        self.failed = []
        self.started = []
        self.finished_all = False
        self.finished_paused = False

    def on_succeeded(self, job_index, output_size):
        self.succeeded.append((job_index, output_size))

    def on_failed(self, job_index, output_size):
        self.failed.append((job_index, output_size))

    def on_started(self, job_index):
        self.started.append(job_index)

    def on_finished_all(self):
        self.finished_all = True

    def on_finished_paused(self):
        self.finished_paused = True


class MuxingControllerTests(GlobalStateTestCase):
    def install_fake_tool(self, fast=False, fail=False):
        tool_dir = self._work_dir / "tool"
        tool_dir.mkdir(exist_ok=True)
        script = tool_dir / "fake_mkvmerge.py"
        script.write_text(FAKE_TOOL_SOURCE, encoding="utf-8")
        arguments = []
        if fast:
            arguments.append("--fast")
        if fail:
            arguments.append("--fail")
        extra_arguments = "".join(" " + argument for argument in arguments)
        if sys.platform == "win32":
            wrapper = tool_dir / "fake_mkvmerge.bat"
            wrapper.write_text('@echo off\r\n"{0}" -u "{1}" %*{2}\r\n'.format(
                sys.executable, script, extra_arguments), encoding="utf-8")
        else:
            wrapper = tool_dir / "fake_mkvmerge.sh"
            wrapper.write_text('#!/bin/sh\nexec "{0}" -u "{1}" "$@" {2}\n'.format(
                sys.executable, script, extra_arguments), encoding="utf-8")
            wrapper.chmod(0o755)
        GlobalFiles.MKVMERGE_PATH = str(wrapper)

    @staticmethod
    def write_job_json(job):
        """Stands in for GetJsonForMkvmergeJob: only the output matters here."""
        if GlobalSetting.OVERWRITE_SOURCE_FILES:
            folder_path = os.path.dirname(job.video_name_absolute)
            file_name = JobOutputFiles.change_file_extension_to_mkv_with_random_suffix(job.video_name)
        else:
            folder_path = GlobalSetting.DESTINATION_FOLDER_PATH
            file_name = JobOutputFiles.get_file_name_with_mkv_extension(job.video_name)
        with open(GlobalFiles.mkvmergeJsonJobFilePath, "w", encoding="utf-8") as job_file:
            json.dump(["--output", os.path.join(folder_path, file_name)], job_file)

    def make_jobs(self, names):
        jobs = []
        for name in names:
            source = self._work_dir / name
            source.write_bytes(b"source")
            job = SingleJobData()
            job.video_name = name
            job.video_name_absolute = str(source)
            jobs.append(job)
        return jobs

    def start_queue(self, jobs, pause_before_start=False):
        worker = start_muxing_worker_module.StartMuxingWorker(jobs)
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        recorder = SignalRecorder()
        worker.job_succeeded_signal.connect(recorder.on_succeeded)
        worker.job_failed_signal.connect(recorder.on_failed)
        worker.job_started_signal.connect(recorder.on_started)
        worker.finished_all_jobs_signal.connect(recorder.on_finished_all)
        worker.finished_paused_signal.connect(recorder.on_finished_paused)
        if pause_before_start:
            worker.request_pause()
        thread.start()
        return worker, thread, recorder

    def stop_queue(self, worker, thread):
        worker.stop_all_threads()
        thread.quit()
        self.assertTrue(thread.wait(5000), "the muxing controller thread did not stop")

    def test_queue_muxes_every_job_and_reports_sizes_off_the_gui_thread(self):
        self.install_fake_tool()
        destination = self._work_dir / "dest"
        destination.mkdir()
        GlobalSetting.DESTINATION_FOLDER_PATH = str(destination)
        jobs = self.make_jobs(["first.mp4", "second.mp4"])

        with mock.patch.object(start_muxing_worker_module, "GetJsonForMkvmergeJob", self.write_job_json):
            worker, thread, recorder = self.start_queue(jobs)
            try:
                finished = process_events_until(lambda: recorder.finished_all or recorder.finished_paused)
            finally:
                self.stop_queue(worker, thread)

        self.assertTrue(finished, "the queue never finished")
        self.assertFalse(recorder.finished_paused)
        self.assertEqual(recorder.started, [0, 1])
        self.assertEqual(recorder.failed, [])
        self.assertEqual(recorder.succeeded, [(0, len(FAKE_PAYLOAD)), (1, len(FAKE_PAYLOAD))])
        for name in ("first.mkv", "second.mkv"):
            self.assertTrue((destination / name).exists(), name)

    def test_fast_tool_that_ends_before_the_reader_starts_does_not_hang(self):
        self.install_fake_tool(fast=True)
        destination = self._work_dir / "dest"
        destination.mkdir()
        GlobalSetting.DESTINATION_FOLDER_PATH = str(destination)
        jobs = self.make_jobs(["quick.mp4"])

        with mock.patch.object(start_muxing_worker_module, "GetJsonForMkvmergeJob", self.write_job_json):
            worker, thread, recorder = self.start_queue(jobs)
            try:
                finished = process_events_until(lambda: recorder.finished_all or recorder.finished_paused,
                                                timeout=30)
            finally:
                self.stop_queue(worker, thread)

        self.assertTrue(finished, "a fast tool left the queue waiting forever")
        self.assertEqual(recorder.failed, [])
        self.assertEqual(recorder.succeeded, [(0, len(FAKE_PAYLOAD))])

    def test_overwrite_with_crc_finalizes_in_order(self):
        self.install_fake_tool()
        GlobalSetting.OVERWRITE_SOURCE_FILES = True
        GlobalSetting.RANDOM_OUTPUT_SUFFIX = "12345"
        jobs = self.make_jobs(["movie.mp4"])
        jobs[0].is_crc_calculating_required = True

        with mock.patch.object(start_muxing_worker_module, "GetJsonForMkvmergeJob", self.write_job_json):
            worker, thread, recorder = self.start_queue(jobs)
            try:
                finished = process_events_until(lambda: recorder.finished_all or recorder.finished_paused)
            finally:
                self.stop_queue(worker, thread)

        self.assertTrue(finished)
        self.assertEqual(recorder.failed, [])
        expected_crc = format(zlib.crc32(FAKE_PAYLOAD) & 0xFFFFFFFF, "08x").upper()
        expected_output = self._work_dir / "movie [{0}].mkv".format(expected_crc)
        self.assertEqual(recorder.succeeded, [(0, len(FAKE_PAYLOAD))])
        self.assertFalse((self._work_dir / "movie.mp4").exists())
        self.assertTrue(expected_output.exists())
        self.assertEqual(expected_output.read_bytes(), FAKE_PAYLOAD)

    def test_failed_job_keeps_the_source_file(self):
        self.install_fake_tool(fail=True)
        GlobalSetting.OVERWRITE_SOURCE_FILES = True
        GlobalSetting.RANDOM_OUTPUT_SUFFIX = "12345"
        jobs = self.make_jobs(["movie.mp4"])

        with mock.patch.object(start_muxing_worker_module, "GetJsonForMkvmergeJob", self.write_job_json):
            worker, thread, recorder = self.start_queue(jobs)
            try:
                finished = process_events_until(lambda: recorder.finished_all or recorder.finished_paused)
            finally:
                self.stop_queue(worker, thread)

        self.assertTrue(finished)
        self.assertEqual(recorder.succeeded, [])
        self.assertEqual(recorder.failed, [(0, 0)])
        # A failed mux must never delete the source file it was reading.
        self.assertTrue((self._work_dir / "movie.mp4").exists())
        self.assertFalse((self._work_dir / "movie.mkv").exists())

    def test_pause_stops_and_joins_the_helper_threads(self):
        self.install_fake_tool()
        destination = self._work_dir / "dest"
        destination.mkdir()
        GlobalSetting.DESTINATION_FOLDER_PATH = str(destination)
        jobs = self.make_jobs(["first.mp4", "second.mp4", "third.mp4"])

        with mock.patch.object(start_muxing_worker_module, "GetJsonForMkvmergeJob", self.write_job_json):
            worker, thread, recorder = self.start_queue(jobs, pause_before_start=True)
            try:
                # Requested before the queue starts so the test is deterministic:
                # the controller must stop and join every helper thread.
                paused = process_events_until(lambda: recorder.finished_paused or recorder.finished_all)
            finally:
                self.stop_queue(worker, thread)

        self.assertTrue(paused)
        self.assertTrue(recorder.finished_paused)
        self.assertEqual(recorder.started, [])
        self.assertFalse(worker.start_muxing_process_thread.isRunning())
        self.assertFalse(worker.read_log_mkvmerge_thread.isRunning())
        self.assertFalse(worker.read_log_mkvpropedit_thread.isRunning())
        self.assertFalse(worker.start_crc_calculating_process_thread.isRunning())
