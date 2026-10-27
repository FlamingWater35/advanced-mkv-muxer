import logging

from PySide6.QtCore import QThread, Signal

from packages.ToolUpdates import MkvToolNixUpdater


class ToolsUpdateWorker(QThread):
    """Runs the (network bound) update check or installation off the UI thread."""

    checked_signal = Signal(object)  # MkvToolNixUpdater.UpdateStatus
    updated_signal = Signal(str)  # installed version
    progress_signal = Signal(str, int)  # message, percentage (-1 = unknown)
    error_signal = Signal(str)

    def __init__(self, action, current_version, target_dir, parent=None,
                 check=None, install=None):
        super().__init__(parent)
        self.action = action
        self.current_version = current_version
        self.target_dir = target_dir
        self.check_function = check or MkvToolNixUpdater.check_for_update
        self.install_function = install or MkvToolNixUpdater.install_update

    def run(self):
        try:
            if self.action == "check":
                self.checked_signal.emit(self.check_function(self.current_version))
            else:
                version = self.install_function(self.target_dir, progress=self.emit_progress)
                self.updated_signal.emit(version)
        except Exception as exception:  # noqa: BLE001 - shown in the dialog
            logging.error("MKVToolNix update failed: %s", exception)
            self.error_signal.emit(str(exception))

    def emit_progress(self, message, percent=-1):
        self.progress_signal.emit(str(message), int(percent))
