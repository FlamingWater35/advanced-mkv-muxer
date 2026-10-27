import logging

from PySide6.QtWidgets import QGroupBox, QGridLayout, QLabel, QPushButton, QProgressBar

from packages.Startup import GlobalFiles
from packages.Startup.MainApplication import get_dark_palette, get_light_palette
from packages.Startup.Options import Options
from packages.Tabs.SettingTab.Widgets.PresetTabWidget import try_to_create_windows_vista_style
from packages.ToolUpdates import MkvToolNixUpdater
from packages.ToolUpdates.ToolsUpdateWorker import ToolsUpdateWorker


class ToolsUpdateGroupBox(QGroupBox):
    """Shows the installed MKVToolNix versions and updates them on request."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("MKVToolNix Tools")
        self.setStyle(try_to_create_windows_vista_style())
        if Options.Dark_Mode:
            self.setPalette(get_dark_palette())
        else:
            self.setPalette(get_light_palette())

        self.mkvmerge_label = QLabel("mkvmerge:")
        self.mkvmerge_version_label = QLabel("not found")
        self.mkvpropedit_label = QLabel("mkvpropedit:")
        self.mkvpropedit_version_label = QLabel("not found")
        self.status_label = QLabel('Click "Check for Updates" to look for a newer MKVToolNix release.')
        self.status_label.setWordWrap(True)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.check_button = QPushButton("Check for Updates")
        self.update_button = QPushButton("Update")
        self.update_button.setEnabled(False)

        self.worker = None
        self.worker_factory = None
        self.current_action = "check"
        self.current_version = None
        self.latest_version = None
        self.update_available = False

        self.setup_layout()
        self.refresh_versions()
        self.check_button.clicked.connect(self.start_check)
        self.update_button.clicked.connect(self.start_update)

    def setup_layout(self):
        self.main_layout = QGridLayout()
        self.main_layout.addWidget(self.mkvmerge_label, 0, 0)
        self.main_layout.addWidget(self.mkvmerge_version_label, 0, 1)
        self.main_layout.addWidget(self.mkvpropedit_label, 0, 2)
        self.main_layout.addWidget(self.mkvpropedit_version_label, 0, 3)
        self.main_layout.addWidget(self.status_label, 1, 0, 1, 4)
        self.main_layout.addWidget(self.progress_bar, 2, 0, 1, 4)
        self.main_layout.addWidget(self.check_button, 3, 2)
        self.main_layout.addWidget(self.update_button, 3, 3)
        self.main_layout.setColumnStretch(1, 1)
        self.main_layout.setColumnStretch(3, 1)
        self.setLayout(self.main_layout)

    # -- versions ---------------------------------------------------------

    def refresh_versions(self):
        mkvmerge_version = MkvToolNixUpdater.parse_version(GlobalFiles.MKVMERGE_VERSION)
        mkvpropedit_version = MkvToolNixUpdater.parse_version(GlobalFiles.MKVPROPEDIT_VERSION)
        self.mkvmerge_version_label.setText(mkvmerge_version or "not found")
        self.mkvpropedit_version_label.setText(mkvpropedit_version or "not found")
        self.current_version = mkvmerge_version or mkvpropedit_version
        return self.current_version

    # -- actions ----------------------------------------------------------

    def create_worker(self, action):
        if self.worker_factory is not None:
            return self.worker_factory(action, self.current_version)
        return ToolsUpdateWorker(action, self.current_version, GlobalFiles.UserToolsFolderPath)

    def start_check(self):
        if self.worker is not None:
            return
        self.current_action = "check"
        self.set_busy(True)
        self.status_label.setText("Checking for updates…")
        self.worker = self.create_worker("check")
        self.worker.checked_signal.connect(self.apply_check_result)
        self.worker.error_signal.connect(self.apply_error)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.start()

    def start_update(self):
        if self.worker is not None or not self.update_available:
            return
        self.current_action = "update"
        self.set_busy(True)
        self.update_button.setEnabled(False)
        self.status_label.setText("Preparing the update…")
        self.worker = self.create_worker("update")
        self.worker.progress_signal.connect(self.on_progress)
        self.worker.updated_signal.connect(self.apply_update_result)
        self.worker.error_signal.connect(self.apply_error)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.start()

    def on_progress(self, message, percent):
        self.status_label.setText(message)
        if percent >= 0:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(min(percent, 100))
        else:
            self.progress_bar.setRange(0, 0)

    def apply_check_result(self, status):
        self.latest_version = status.latest
        self.update_available = bool(status.update_available)
        installed = status.current or self.current_version or "unknown"
        if self.update_available:
            self.status_label.setText(f"Update available: {status.latest} (installed: {installed})")
        else:
            self.status_label.setText(f"Up to date (installed: {installed}, latest: {status.latest})")
        self.update_button.setEnabled(self.update_available)

    def apply_update_result(self, version):
        self.latest_version = None
        self.update_available = False
        try:
            GlobalFiles.refresh_tools()
        except Exception as exception:  # noqa: BLE001 - the tools may need a restart
            logging.error("Could not refresh the MKVToolNix tools: %s", exception)
        self.refresh_versions()
        self.status_label.setText(f"MKVToolNix updated to version {version}.")
        self.update_button.setEnabled(False)
        self.progress_bar.setVisible(False)

    def apply_error(self, message):
        if self.current_action == "update":
            self.status_label.setText(f"Update failed: {message}")
        else:
            self.status_label.setText(f"Update check failed: {message}")
        self.update_button.setEnabled(self.update_available)

    def on_worker_finished(self):
        self.set_busy(False)
        self.worker = None

    def is_busy(self):
        return self.worker is not None

    def set_busy(self, busy):
        self.check_button.setEnabled(not busy)
        self.progress_bar.setVisible(busy)
        if busy:
            self.progress_bar.setRange(0, 0)
            self.update_button.setEnabled(False)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.update_button.setEnabled(self.update_available)
