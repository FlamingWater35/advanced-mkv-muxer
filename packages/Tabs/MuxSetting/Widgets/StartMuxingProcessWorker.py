import subprocess
import threading
import traceback

from PySide6.QtCore import QObject, QThread, Signal

from packages.Startup import GlobalFiles
from packages.Tabs.GlobalSetting import write_to_log_file

# How long an idle worker sleeps between checks for a stop request.
IDLE_TIMEOUT = 0.1


class StartMuxingProcessWorker(QObject):
    """Runs one MKVToolNix command per request on its own thread.

    The controller hands a command over with request_command(). A plain
    "wait" flag like the old implementation had is not enough: the worker
    thread could observe the flag before the command string was written and
    silently re-run the previous command. The event both publishes the command
    and wakes the worker.
    """

    finished_job_signal = Signal(int)

    def __init__(self, command=""):
        super().__init__()
        self.command = command
        self._command_ready = threading.Event()
        self._stop = threading.Event()

    def request_command(self, command):
        self.command = command
        self._command_ready.set()

    def stop(self):
        self._stop.set()
        # Wake a sleeping worker so it can notice the stop request.
        self._command_ready.set()

    def is_stopped(self):
        return self._stop.is_set()

    def run(self):
        try:
            while not self._stop.is_set():
                if not self._command_ready.wait(IDLE_TIMEOUT):
                    continue
                self._command_ready.clear()
                if self._stop.is_set():
                    break
                command = self.command
                with open(GlobalFiles.MuxingLogFilePath, "a+", encoding="UTF-8") as log_file:
                    mux_process = subprocess.run(command, shell=True, stdout=log_file,
                                                 env=GlobalFiles.ENVIRONMENT)
                self.finished_job_signal.emit(mux_process.returncode)
        except Exception:  # noqa: BLE001 - a crashed worker must still end its thread
            write_to_log_file(traceback.format_exc())
        finally:
            # Quit from inside the thread: waiting for a queued quit() call from
            # the GUI thread would depend on the GUI being responsive.
            QThread.currentThread().quit()
