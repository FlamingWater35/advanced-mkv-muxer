import threading
import traceback
import zlib
from os.path import getsize

from PySide6.QtCore import QObject, QThread, Signal

from packages.Tabs.GlobalSetting import write_to_log_file

IDLE_TIMEOUT = 0.1


class CalculateCRCProcessWorker(QObject):
    """Computes a CRC32 of the finished output on its own thread.

    The file name is handed over explicitly by the controller: the old version
    guessed an "#suffix.mkv" name while the GUI thread was renaming the very
    same file, which raced with the rename.
    """

    crc_progress_signal = Signal(int)
    crc_result_signal = Signal(str)
    crc_failed_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.file_name = ""
        self.chunk_size = 65536
        self._job_ready = threading.Event()
        self._stop = threading.Event()

    def start_calculating(self, file_name):
        self.file_name = file_name
        self._job_ready.set()

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
                self._calculate(self.file_name)
        except Exception:  # noqa: BLE001 - a crashed worker must still end its thread
            write_to_log_file(traceback.format_exc())
        finally:
            QThread.currentThread().quit()

    def _calculate(self, file_name):
        try:
            file_size = getsize(file_name)
            checksum = 0
            current_read = 0
            last_percent = -1
            with open(file_name, "rb") as f:
                while chunk := f.read(self.chunk_size):
                    if self._stop.is_set():
                        return
                    current_read += len(chunk)
                    current_percent = int(min(100 * current_read / file_size, 100)) if file_size else 100
                    # One signal per percent instead of one per 64 KiB chunk:
                    # a 20 GB file used to queue ~320k GUI events.
                    if current_percent != last_percent:
                        last_percent = current_percent
                        self.crc_progress_signal.emit(current_percent)
                    checksum = zlib.crc32(chunk, checksum)
            if last_percent != 100:
                self.crc_progress_signal.emit(100)
            crc_string = format(checksum & 0xFFFFFFFF, '08x').upper()
            self.crc_result_signal.emit(crc_string)
        except Exception as exception:  # noqa: BLE001 - reported to the controller
            write_to_log_file(traceback.format_exc())
            self.crc_failed_signal.emit(str(exception))
