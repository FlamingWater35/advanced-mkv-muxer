import threading
import traceback

from PySide6.QtCore import QObject, QThread, Signal

from packages.Startup import GlobalFiles
from packages.Tabs.GlobalSetting import write_to_log_file
from packages.Tabs.MuxSetting.Widgets.MuxingParams import MuxingParams

IDLE_TIMEOUT = 0.05


def next_line(file, stop_event, process_finished_event, start_offset=0):
    """Yield new lines of the log, starting at start_offset.

    See ReadFromMkvmergeLogWorker.next_line: the offset and the two events make
    the reader immune to a fast tool and to a stop request.
    """
    file.seek(start_offset)
    while not stop_event.is_set():
        line = file.readline()
        if line:
            yield line
            continue
        if process_finished_event.is_set():
            line = file.readline()
            if line:
                yield line
                continue
            return
        stop_event.wait(IDLE_TIMEOUT)


class ReadFromMkvpropeditLogWorker(QObject):
    finished_job_signal = Signal()
    send_muxing_progress_data_signal = Signal(MuxingParams)

    def __init__(self):
        super().__init__()
        self.job_index = -1
        self._start_offset = 0
        self._job_ready = threading.Event()
        self._stop = threading.Event()
        self._process_finished = threading.Event()

    def start_reading(self, job_index, start_offset=0):
        self.job_index = job_index
        self._start_offset = start_offset
        self._process_finished.clear()
        self._job_ready.set()

    def notify_process_finished(self):
        self._process_finished.set()

    def stop(self):
        self._stop.set()
        self._job_ready.set()

    def run(self):
        try:
            while not self._stop.is_set():
                if not self._job_ready.wait(IDLE_TIMEOUT):
                    continue
                self._job_ready.clear()
                if self._stop.is_set():
                    break
                self._read_job()
        except Exception:  # noqa: BLE001 - a crashed worker must still end its thread
            write_to_log_file(traceback.format_exc())
        finally:
            QThread.currentThread().quit()

    def send_progress(self, progress=0, error=False, message=""):
        muxing_params = MuxingParams()
        muxing_params.index = self.job_index
        muxing_params.progress = progress
        muxing_params.error = error
        muxing_params.message = message
        self.send_muxing_progress_data_signal.emit(muxing_params)

    def _read_job(self):
        with open(GlobalFiles.MuxingLogFilePath, "a+", encoding="UTF-8") as log_file:
            for line in next_line(log_file, self._stop, self._process_finished, self._start_offset):
                if line.find('Done.') != -1 or line.find('No changes were made') != -1:
                    self.send_progress(progress=100)
                    break
                elif line.find('Error:') != -1:
                    self.send_progress(error=True, message=line)
                    break
        self.finished_job_signal.emit()
