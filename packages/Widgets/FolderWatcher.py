"""Watch the source folders so newly copied files show up without a refresh (#41).

``QFileSystemWatcher`` reports every write inside a folder, including the
temporary files that a copy or an encode produces, so the notification is
debounced: one signal after the folder has been quiet for a moment.
"""

from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer, Signal


class FolderWatcher(QObject):
    folder_changed_signal = Signal()

    DEBOUNCE_MILLISECONDS = 1000

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_folder_path = ""
        self.file_system_watcher = QFileSystemWatcher(self)
        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(self.DEBOUNCE_MILLISECONDS)
        self.file_system_watcher.directoryChanged.connect(self.schedule_folder_changed)
        self.debounce_timer.timeout.connect(self.folder_changed_signal.emit)

    def watch_folder(self, folder_path):
        if folder_path == self.current_folder_path:
            return
        self.clear()
        if not folder_path:
            return
        if self.file_system_watcher.addPath(folder_path):
            self.current_folder_path = folder_path

    def clear(self):
        self.debounce_timer.stop()
        if len(self.file_system_watcher.directories()) > 0:
            self.file_system_watcher.removePaths(self.file_system_watcher.directories())
        self.current_folder_path = ""

    def schedule_folder_changed(self, folder_path):
        # Some platforms stop reporting a directory after it fired once, so
        # re-register it on every notification.
        if folder_path != self.current_folder_path:
            self.watch_folder(folder_path)
        self.debounce_timer.start()
