"""Keep only the subtitle files whose name carries this tab's language (#55).

Point every subtitle tab at the same folder and each tab picks the files that
belong to its own language instead of taking every file and relying on manual
reordering.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCheckBox

from packages.Tabs.GlobalSetting import GlobalSetting


class MatchLanguageByFileNameCheckBox(QCheckBox):
    match_language_option_changed_signal = Signal(bool)

    def __init__(self, tab_index):
        super().__init__()
        self.tab_index = tab_index
        self.setText("Match Language From File Name")
        self.setChecked(GlobalSetting.SUBTITLE_MATCH_LANGUAGE_BY_FILE_NAME[self.tab_index])
        self.setToolTip("Only load the subtitle files whose name contains this tab's language, for example\n"
                        "\"Show.S01E01.en.srt\", \"Show.S01E01.eng.srt\" or\n"
                        "\"Show.S01E01.English.srt\".\n"
                        "Give several subtitle tabs the same folder and each tab keeps its own language.")
        self.stateChanged.connect(self.state_changed)

    def state_changed(self, state):
        is_checked = state == Qt.CheckState.Checked.value
        GlobalSetting.SUBTITLE_MATCH_LANGUAGE_BY_FILE_NAME[self.tab_index] = is_checked
        self.match_language_option_changed_signal.emit(is_checked)
