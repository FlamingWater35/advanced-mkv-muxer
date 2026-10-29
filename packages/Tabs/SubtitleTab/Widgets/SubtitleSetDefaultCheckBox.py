from PySide6.QtGui import Qt
from PySide6.QtWidgets import QCheckBox

from packages.Startup.Options import Options, save_options
from packages.Tabs.GlobalSetting import GlobalSetting


class SubtitleSetDefaultCheckBox(QCheckBox):
    def __init__(self, tab_index):
        super().__init__()
        self.tab_index = tab_index
        self.hint_when_enabled = ""
        self.is_updating = False
        self.setText("Set Default")
        self.stateChanged.connect(self.change_global_subtitle_set_default)

    def change_global_subtitle_set_default(self):
        # Matroska allows several default tracks, so ticking one subtitle must
        # not clear the others (#162). The "Make this subtitle default" mux
        # option is the way to target one exclusive track.
        is_checked = self.checkState() == Qt.CheckState.Checked
        GlobalSetting.SUBTITLE_SET_DEFAULT[self.tab_index] = is_checked
        if not self.is_updating and Options.Default_Subtitle_Set_Default != is_checked:
            # Remember the tick so the next launch starts with it (#41).
            Options.Default_Subtitle_Set_Default = is_checked
            save_options()

    def update_check_state(self):
        self.set_checked_silently(bool(GlobalSetting.SUBTITLE_SET_DEFAULT[self.tab_index]))
        self.setDisabled(bool(GlobalSetting.SUBTITLE_SET_DEFAULT_DISABLED))

        if self.isEnabled():
            self.setToolTip("<nobr>set the new subtitle to be the default subtitle track "
                            "when play")
            self.setToolTipDuration(12000)
        else:
            self.setToolTip(
                "<nobr>set the new subtitle to be the default subtitle track when play<br><b>Disabled</b> because "
                "option "
                "<b>make this subtitle default</b> is enabled on mux setting tab ")
            self.setToolTipDuration(12000)

    def set_checked_silently(self, is_checked: bool):
        """Change the tick without treating it as a user preference (#41)."""
        self.is_updating = True
        try:
            self.setChecked(is_checked)
        finally:
            self.is_updating = False

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
