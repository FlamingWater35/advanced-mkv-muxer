from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCheckBox

from packages.Tabs.GlobalSetting import GlobalSetting


class IncludeSubfoldersCheckBox(QCheckBox):
    """Load files from the whole folder tree instead of one folder level.

    Off by default: a source folder may contain unrelated videos in nested
    folders (extras, samples), so scanning deep is something the user asks for.
    """

    subfolders_option_changed_signal = Signal(bool)

    def __init__(self):
        super().__init__()
        self.setText("Include Subfolders")
        self.setChecked(GlobalSetting.INCLUDE_SUBFOLDERS)
        self.setToolTip("Also load files from the subfolders of every source folder "
                        "(the folder structure is kept in the file list)")
        self.stateChanged.connect(self.state_changed)

    def state_changed(self, state):
        is_checked = state == Qt.CheckState.Checked.value
        GlobalSetting.INCLUDE_SUBFOLDERS = is_checked
        self.subfolders_option_changed_signal.emit(is_checked)
