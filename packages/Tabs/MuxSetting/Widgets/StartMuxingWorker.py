import logging
import os
import time
import traceback

import shiboken6
from PySide6.QtCore import QObject, QThread, Signal

from packages.Startup import GlobalFiles
from packages.Tabs.GlobalSetting import GlobalSetting, write_to_log_file
from packages.Tabs.MuxSetting.Widgets.CalculateCRCProcessWorker import CalculateCRCProcessWorker
from packages.Tabs.MuxSetting.Widgets.GetJsonForMkvmergeJob import GetJsonForMkvmergeJob
from packages.Tabs.MuxSetting.Widgets.GetJsonForMkvpropeditJob import GetJsonForMkvpropeditJob
from packages.Tabs.MuxSetting.Widgets.JobOutputFiles import (
    apply_crc_to_output_name,
    finalize_muxing_output,
    get_file_size,
    get_output_size,
    record_failed_job_output,
)
from packages.Tabs.MuxSetting.Widgets.JobChangeDetection import job_has_nothing_to_do
from packages.Tabs.MuxSetting.Widgets.MuxingParams import MuxingParams
from packages.Tabs.MuxSetting.Widgets.ReadFromMkvmergeLogWorker import ReadFromMkvmergeLogWorker
from packages.Tabs.MuxSetting.Widgets.ReadFromMkvpropeditLogWorker import ReadFromMkvpropeditLogWorker
from packages.Tabs.MuxSetting.Widgets.SingleJobData import SingleJobData
from packages.Tabs.MuxSetting.Widgets.StartMuxingProcessWorker import StartMuxingProcessWorker

# Upper bound for stopping the helper threads. They only ever idle between
# jobs when a pause/cancel is evaluated, so this is a safety net, not a wait.
STOP_TIMEOUT_MS = 5000


def change_file_extension_to_mkv(file_name):
    file_extension_start_index = file_name.rfind(".")
    new_file_name_with_mkv_extension = file_name[:file_extension_start_index] + ".mkv"
    return new_file_name_with_mkv_extension


def get_time():
    t = time.time()
    return str(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t)))


def add_double_quotation(string):
    return "\"" + str(string) + "\""


class StartMuxingWorker(QObject):
    """Drives the job queue on its own thread and never touches widgets.

    Every blocking call (muxing, log tailing, renaming, CRC, size queries)
    happens on a worker thread; the GUI only ever receives values through the
    signals below. The GUI thread used to perform the output renames itself,
    which froze the window for up to 25 seconds per locked file and raced with
    the CRC reader.
    """

    finished_all_jobs_signal = Signal()
    finished_paused_signal = Signal()
    cancel_signal = Signal()
    progress_signal = Signal(MuxingParams)
    crc_progress_signal = Signal(int)
    job_succeeded_signal = Signal(int, int)  # job index, output size in bytes
    job_failed_signal = Signal(int, int)  # job index, output size in bytes
    job_started_signal = Signal(int)
    pause_from_error_occurred_signal = Signal()

    def __init__(self, data):
        super().__init__()
        self.data = data  # type:list[SingleJobData]
        self.current_job = -1
        self.finished_read_log_and_muxing = 0
        self.log_start_offset = 0
        self.always_use_mkvpropedit = False
        self.always_use_mkvmerge = False
        self._pause_requested = False
        self._cancel_requested = False
        self._shutdown = False
        self.setup_worker_threads()

    # -- control from the GUI thread --------------------------------------

    def request_pause(self):
        """Ask the worker to pause at the next job boundary."""
        self._pause_requested = True

    def request_cancel(self):
        self._cancel_requested = True

    def request_stop(self):
        """Shut down: start no new job and do not finish the running one.

        Used when the application exits, where deleting/renaming a half written
        output would be worse than leaving the job unfinished.
        """
        self._shutdown = True
        self._cancel_requested = True

    def stop_all_threads(self, timeout_ms=STOP_TIMEOUT_MS):
        """Stop and join the helper threads.

        Joining from this thread guarantees the helper QThreads are finished
        before the GUI drops its reference to this worker; otherwise they could
        be destroyed while still running, which aborts the process.
        """
        workers = (
            self.read_log_mkvmerge_worker,
            self.read_log_mkvpropedit_worker,
            self.start_muxing_process_worker,
            self.start_crc_calculating_process_worker,
        )
        threads = (
            self.start_muxing_process_thread,
            self.read_log_mkvmerge_thread,
            self.read_log_mkvpropedit_thread,
            self.start_crc_calculating_process_thread,
        )
        for worker in workers:
            if shiboken6.isValid(worker):
                worker.stop()
        deadline = time.monotonic() + timeout_ms / 1000
        for thread in threads:
            if not shiboken6.isValid(thread) or not thread.isRunning():
                continue
            remaining_ms = max(0, int((deadline - time.monotonic()) * 1000))
            if not thread.wait(remaining_ms):
                write_to_log_file(f"Worker thread {thread} did not stop within {timeout_ms} ms")

    # -- queue ------------------------------------------------------------

    def run(self):
        # Names registered by the output name pattern belong to one run (#111).
        GlobalSetting.MUX_SETTING_USED_OUTPUT_NAMES = set()
        try:
            self.start_worker_threads()
            self.next_job()
        except Exception:  # noqa: BLE001 - keep the GUI usable instead of hanging
            write_to_log_file(traceback.format_exc())
            # Do not let a late helper signal finish/advance the job after the
            # threads were stopped below.
            self._shutdown = True
            self.stop_all_threads()
            GlobalSetting.MUXING_ON = False
            self.finished_paused_signal.emit()

    def next_job(self):
        if self._cancel_requested:
            self.stop_all_threads()
            self.cancel_signal.emit()
            return
        self.current_job += 1
        if self.current_job >= len(self.data):
            self.stop_all_threads()
            self.finished_all_jobs_signal.emit()
            return
        if self._pause_requested:
            self.stop_all_threads()
            self.finished_paused_signal.emit()
            return

        job = self.data[self.current_job]
        if not job.done or (job.error_occurred and job.muxing_message.find("There is not enough space") != -1):
            if job_has_nothing_to_do(job):
                self.skip_job_without_changes(job)
                return
            GetJsonForMkvmergeJob(job)
            if GlobalSetting.VIDEO_SOURCE_MKV_ONLY:
                GetJsonForMkvpropeditJob(job)
            else:
                self.always_use_mkvmerge = True
            if self.always_use_mkvpropedit:
                self.job_started_signal.emit(self.current_job)
                self.start_mkvpropedit_muxing()
            elif self.always_use_mkvmerge:
                self.job_started_signal.emit(self.current_job)
                self.start_mkvmerge_muxing()
            elif GlobalSetting.USE_MKVPROPEDIT:
                self.always_use_mkvpropedit = True
                self.job_started_signal.emit(self.current_job)
                self.start_mkvpropedit_muxing()
            else:
                self.always_use_mkvmerge = True
                self.job_started_signal.emit(self.current_job)
                self.start_mkvmerge_muxing()
        else:
            self.next_job()

    # -- muxing -----------------------------------------------------------

    def skip_job_without_changes(self, job: SingleJobData):
        """Mark a job that would be rewritten identically as done (#145).

        Nothing is started, so the file on disk is kept untouched and the
        queue moves on immediately.
        """
        job.done = True
        job.muxing_message = "Nothing to change, the job was skipped"
        logging.info("Skipped (nothing to change): %s", job.video_name)
        # The status cell is created by job_started_signal, and the success
        # handler expects it to exist.
        self.job_started_signal.emit(self.current_job)
        self.job_succeeded_signal.emit(self.current_job, job.size_before_muxing_bytes)
        self.next_job()

    # noinspection PyAttributeOutsideInit
    def start_mkvpropedit_muxing(self):
        job = self.data[self.current_job]
        job.used_mkvpropedit = True
        mux_command = add_double_quotation(GlobalFiles.MKVPROPEDIT_PATH) + " @" + add_double_quotation(
            GlobalFiles.mkvpropeditJsonJobFilePath)
        self.start_reading_log_file(self.read_log_mkvpropedit_worker, mux_command)

    def start_mkvmerge_muxing(self):
        mux_command = add_double_quotation(GlobalFiles.MKVMERGE_PATH) + " @" + add_double_quotation(
            GlobalFiles.mkvmergeJsonJobFilePath)
        self.start_reading_log_file(self.read_log_mkvmerge_worker, mux_command)

    def start_reading_log_file(self, log_worker, mux_command):
        # Remember where this job's output starts before writing its header, so
        # a fast tool cannot finish before the log reader has positioned itself.
        self.log_start_offset = get_file_size(GlobalFiles.MuxingLogFilePath)
        self.add_header_info_to_log_file()
        GlobalSetting.MUXING_ON = True
        log_worker.start_reading(self.current_job, self.log_start_offset)
        self.start_muxing_process_worker.request_command(mux_command)

    # -- job completion ---------------------------------------------------

    def finished_read_log(self):
        self.job_step_done()

    def finished_muxing_process(self, exit_code):
        job = self.data[self.current_job]
        if exit_code == 2:
            job.error_occurred = True
        if job.error_occurred and GlobalSetting.MUX_SETTING_ABORT_ON_ERRORS:
            self.request_pause()
        # The tool closed the log: let the readers drain the tail and finish.
        self.read_log_mkvmerge_worker.notify_process_finished()
        self.read_log_mkvpropedit_worker.notify_process_finished()
        self.job_step_done()

    def job_step_done(self):
        if self._shutdown:
            return
        self.finished_read_log_and_muxing += 1
        if self.finished_read_log_and_muxing < 2:  # the log reader and the tool
            return
        self.finished_read_log_and_muxing = 0
        self.add_footer_info_to_log_file()
        GlobalSetting.MUXING_ON = False
        job = self.data[self.current_job]
        if job.error_occurred:
            # Never touch the source of a failed job: only report what is there.
            record_failed_job_output(job)
            self.job_failed_signal.emit(self.current_job, get_output_size(job))
            self.next_job()
            return
        finalize_muxing_output(job)
        if job.error_occurred:
            # Replacing the source failed; the job must not be reported as done.
            self.job_failed_signal.emit(self.current_job, get_output_size(job))
            self.next_job()
            return
        output_size = get_output_size(job)
        if job.is_crc_calculating_required:
            self.start_crc_calculating(job)
        else:
            self.job_succeeded_signal.emit(self.current_job, output_size)
            self.next_job()

    def start_crc_calculating(self, job: SingleJobData):
        GlobalSetting.MUXING_ON = True
        self.start_crc_calculating_process_worker.start_calculating(job.output_video_absolute_path)

    def receive_muxing_progress_data(self, params: MuxingParams):
        if params.error:
            if GlobalSetting.MUX_SETTING_ABORT_ON_ERRORS:
                self.request_pause()
                self.pause_from_error_occurred_signal.emit()
        self.progress_signal.emit(params)

    def receive_crc_progress(self, progress: int):
        self.crc_progress_signal.emit(progress)

    def receive_crc_result(self, crc_string: str):
        job = self.data[self.current_job]
        job.new_crc = crc_string
        apply_crc_to_output_name(job)
        self.job_succeeded_signal.emit(self.current_job, get_output_size(job))
        GlobalSetting.MUXING_ON = False
        self.next_job()

    def receive_crc_failure(self, message: str):
        job = self.data[self.current_job]
        job.error_occurred = True
        job.muxing_message = message
        write_to_log_file(f"CRC calculation failed for '{job.video_name}': {message}")
        self.job_failed_signal.emit(self.current_job, get_output_size(job))
        GlobalSetting.MUXING_ON = False
        self.next_job()

    # -- log file ---------------------------------------------------------

    def add_header_info_to_log_file(self):
        with open(GlobalFiles.MuxingLogFilePath, "a+", encoding="UTF-8") as log_file:
            t = get_time()
            log_file.write(
                "\n[" + t + "] Start Muxing: ********* " + str(
                    self.data[self.current_job].video_name) + " *********\n\n")

    def add_footer_info_to_log_file(self):
        with open(GlobalFiles.MuxingLogFilePath, "a+", encoding="UTF-8") as log_file:
            t = get_time()
            log_file.write(
                "\n[" + t + "] Finish Muxing: ********* " + self.data[self.current_job].video_name + " *********\n")

    # -- worker threads ---------------------------------------------------

    def setup_worker_threads(self):
        # The helper QThreads/workers are deliberately not deleteLater()ed:
        # stop_all_threads() still reads their state to join them, and touching
        # a Qt object that was already deleted raises RuntimeError. They are
        # released together with this controller, after the join.
        self.setup_start_muxing_process_thread()
        self.setup_read_mkvmerge_log_thread()
        self.setup_read_mkvpropedit_log_thread()
        self.setup_calculate_crc_thread()

    def start_worker_threads(self):
        # Started from run(), i.e. after this controller was moved to its own
        # thread: the GUI thread does no thread set-up and cannot observe half
        # initialised workers.
        self.start_muxing_process_thread.start()
        self.read_log_mkvmerge_thread.start()
        self.read_log_mkvpropedit_thread.start()
        self.start_crc_calculating_process_thread.start()

    # noinspection PyAttributeOutsideInit
    def setup_start_muxing_process_thread(self):
        self.start_muxing_process_worker = StartMuxingProcessWorker()
        self.start_muxing_process_thread = QThread()
        self.start_muxing_process_worker.moveToThread(self.start_muxing_process_thread)
        self.start_muxing_process_thread.started.connect(self.start_muxing_process_worker.run)
        self.start_muxing_process_worker.finished_job_signal.connect(self.finished_muxing_process)

    # noinspection PyAttributeOutsideInit
    def setup_calculate_crc_thread(self):
        self.start_crc_calculating_process_worker = CalculateCRCProcessWorker()
        self.start_crc_calculating_process_thread = QThread()
        self.start_crc_calculating_process_worker.moveToThread(self.start_crc_calculating_process_thread)
        self.start_crc_calculating_process_thread.started.connect(self.start_crc_calculating_process_worker.run)
        self.start_crc_calculating_process_worker.crc_progress_signal.connect(self.receive_crc_progress)
        self.start_crc_calculating_process_worker.crc_result_signal.connect(self.receive_crc_result)
        self.start_crc_calculating_process_worker.crc_failed_signal.connect(self.receive_crc_failure)

    # noinspection PyAttributeOutsideInit
    def setup_read_mkvmerge_log_thread(self):
        self.read_log_mkvmerge_worker = ReadFromMkvmergeLogWorker()
        self.read_log_mkvmerge_thread = QThread()
        self.read_log_mkvmerge_worker.moveToThread(self.read_log_mkvmerge_thread)
        self.read_log_mkvmerge_thread.started.connect(self.read_log_mkvmerge_worker.run)
        self.read_log_mkvmerge_worker.finished_job_signal.connect(self.finished_read_log)
        self.read_log_mkvmerge_worker.send_muxing_progress_data_signal.connect(self.receive_muxing_progress_data)

    # noinspection PyAttributeOutsideInit
    def setup_read_mkvpropedit_log_thread(self):
        self.read_log_mkvpropedit_worker = ReadFromMkvpropeditLogWorker()
        self.read_log_mkvpropedit_thread = QThread()
        self.read_log_mkvpropedit_worker.moveToThread(self.read_log_mkvpropedit_thread)
        self.read_log_mkvpropedit_thread.started.connect(self.read_log_mkvpropedit_worker.run)
        self.read_log_mkvpropedit_worker.finished_job_signal.connect(self.finished_read_log)
        self.read_log_mkvpropedit_worker.send_muxing_progress_data_signal.connect(self.receive_muxing_progress_data)
