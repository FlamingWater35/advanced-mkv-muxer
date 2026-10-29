from PySide6.QtCore import Signal
from PySide6.QtGui import Qt
from PySide6.QtWidgets import QCheckBox


class SelectAllVideosCheckBox(QCheckBox):
    """Tri-state "Select All" box for the video list (#161).

    Programmatic updates (``set_state``) never trigger ``toggle_all_signal``;
    a click on a partially checked box selects everything on the first click.
    """

    toggle_all_signal = Signal(bool)

    def __init__(self):
        super().__init__()
        self.setText("Select All")
        self.setTristate(True)
        self.setToolTip(
            "<nobr>Check to select every video in the list, uncheck to deselect them all.<br>"
            "The box is partially checked while only some videos are selected.")
        self._updating = False
        self.stateChanged.connect(self.state_changed)

    def set_state(self, checked_count, total_count):
        self._updating = True
        if total_count == 0 or checked_count == 0:
            self.setCheckState(Qt.CheckState.Unchecked)
        elif checked_count == total_count:
            self.setCheckState(Qt.CheckState.Checked)
        else:
            self.setCheckState(Qt.CheckState.PartiallyChecked)
        self._updating = False

    def state_changed(self, state):
        if self._updating:
            return
        self.toggle_all_signal.emit(self.checkState() != Qt.CheckState.Unchecked)

    def nextCheckState(self):
        # Partial means "some selected"; the next click always selects all.
        if self.checkState() == Qt.CheckState.Checked:
            self.setCheckState(Qt.CheckState.Unchecked)
        else:
            self.setCheckState(Qt.CheckState.Checked)
