from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton

from packages.Startup import GlobalIcons
from packages.Tabs.GlobalSetting import GlobalSetting


class InsertEmptySubtitleButton(QPushButton):
    """Insert an empty subtitle slot so later files keep their own row (#158)."""

    insert_empty_slot_signal = Signal(int)

    def __init__(self):
        super().__init__()
        self.current_index = -1
        self.max_index = -1
        self.hint_when_enabled = ""
        self.setText("Leave Empty")
        self.setIcon(GlobalIcons.RedDashIcon)
        self.setup_tool_tip_hint()
        self.clicked.connect(self.clicked_button)

    def clicked_button(self):
        if self.current_index == -1:
            # Nothing selected: append at the end, that is always well defined.
            self.insert_empty_slot_signal.emit(max(self.max_index + 1, 0))
            return
        self.insert_empty_slot_signal.emit(self.current_index)

    def setup_tool_tip_hint(self):
        self.setToolTip("Insert an empty slot above the selected row (no subtitle for that video)")
        self.setToolTipDuration(3000)

    def setEnabled(self, new_state: bool):
        super().setEnabled(new_state)
        if not new_state and not GlobalSetting.JOB_QUEUE_EMPTY:
            if self.hint_when_enabled != "":
                self.setToolTip("<nobr>" + self.hint_when_enabled + "<br>" + GlobalSetting.DISABLE_TOOLTIP)
            else:
                self.setToolTip("<nobr>" + GlobalSetting.DISABLE_TOOLTIP)
        else:
            self.setToolTip(self.hint_when_enabled)

    def setDisabled(self, new_state: bool):
        super().setDisabled(new_state)
        if new_state and not GlobalSetting.JOB_QUEUE_EMPTY:
            if self.hint_when_enabled != "":
                self.setToolTip("<nobr>" + self.hint_when_enabled + "<br>" + GlobalSetting.DISABLE_TOOLTIP)
            else:
                self.setToolTip("<nobr>" + GlobalSetting.DISABLE_TOOLTIP)
        else:
            self.setToolTip(self.hint_when_enabled)

    def setToolTip(self, new_tool_tip: str):
        if self.isEnabled() or GlobalSetting.JOB_QUEUE_EMPTY:
            self.hint_when_enabled = new_tool_tip
        super().setToolTip(new_tool_tip)
