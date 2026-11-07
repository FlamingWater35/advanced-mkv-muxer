from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QGroupBox, QGridLayout, QLabel, QPushButton, QProgressBar

from packages.Startup.MainApplication import get_dark_palette, get_light_palette
from packages.Startup.Options import Options
from packages.Startup.Version import Version
from packages.Tabs.SettingTab.Widgets.PresetTabWidget import try_to_create_windows_vista_style
from packages.ToolUpdates import AppUpdateChecker
from packages.ToolUpdates.ToolsUpdateWorker import ToolsUpdateWorker


class AppUpdateGroupBox(QGroupBox):
    """Shows the installed application version and checks for a newer release."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Application Updates")
        self.setStyle(try_to_create_windows_vista_style())
        if Options.Dark_Mode:
            self.setPalette(get_dark_palette())
        else:
            self.setPalette(get_light_palette())

        self.installed_label = QLabel("Installed version:")
        self.installed_version_label = QLabel(str(Version))
        self.status_label = QLabel(
            'Click "Check for Updates" to look for a newer Advanced MKV Muxer release.'
        )
        self.status_label.setWordWrap(True)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.check_button = QPushButton("Check for Updates")
        self.release_button = QPushButton("Open Latest Release")
        self.release_button.setVisible(False)

        self.worker = None
        self.worker_factory = None
        self.current_version = str(Version)
        self.latest_version = None
        self.update_available = False
        self.release_url = None

        self.setup_layout()
        self.check_button.clicked.connect(self.start_check)
        self.release_button.clicked.connect(self.open_release_page)

    def setup_layout(self):
        self.main_layout = QGridLayout()
        self.main_layout.addWidget(self.installed_label, 0, 0)
        self.main_layout.addWidget(self.installed_version_label, 0, 1)
        self.main_layout.addWidget(self.status_label, 1, 0, 1, 4)
        self.main_layout.addWidget(self.progress_bar, 2, 0, 1, 4)
        self.main_layout.addWidget(self.check_button, 3, 2)
        self.main_layout.addWidget(self.release_button, 3, 3)
        self.main_layout.setColumnStretch(1, 1)
        self.main_layout.setColumnStretch(3, 1)
        self.setLayout(self.main_layout)

    # -- actions ----------------------------------------------------------

    def create_worker(self, action):
        if self.worker_factory is not None:
            return self.worker_factory(action, self.current_version)
        return ToolsUpdateWorker(
            action,
            self.current_version,
            None,
            check=AppUpdateChecker.check_for_app_update,
        )

    def start_check(self):
        if self.worker is not None:
            return
        self.set_busy(True)
        self.status_label.setText("Checking for updates…")
        self.worker = self.create_worker("check")
        self.worker.checked_signal.connect(self.apply_check_result)
        self.worker.error_signal.connect(self.apply_error)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.start()

    def open_release_page(self):
        if not self.release_url:
            return
        QDesktopServices.openUrl(QUrl(self.release_url))

    def apply_check_result(self, status):
        self.latest_version = status.latest
        self.update_available = bool(status.update_available)
        self.release_url = status.release_url or AppUpdateChecker.LATEST_RELEASE_PAGE_URL
        installed = status.current or self.current_version or "unknown"
        if self.update_available:
            self.status_label.setText(
                f"Version {status.latest} is available (installed: {installed})."
            )
        else:
            self.status_label.setText(
                f"Up to date (installed: {installed}, latest: {status.latest})."
            )
        self.release_button.setVisible(self.update_available)
        self.release_button.setEnabled(self.update_available)

    def apply_error(self, message):
        self.status_label.setText(f"Update check failed: {message}")
        self.release_button.setVisible(self.update_available)

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
            self.release_button.setEnabled(False)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.release_button.setEnabled(self.update_available)
