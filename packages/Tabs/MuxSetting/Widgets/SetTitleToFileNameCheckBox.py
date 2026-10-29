from PySide6.QtWidgets import QCheckBox

from packages.Tabs.GlobalSetting import GlobalSetting


class SetTitleToFileNameCheckBox(QCheckBox):
    def __init__(self):
        super().__init__()
        self.setText("Set Title To File Name")
        self.setToolTip(
            "<nobr>Adds <b>--title</b> with the output file name (without its extension) to every "
            "file in the queue.")
        self.setChecked(GlobalSetting.MUX_SETTING_SET_TITLE_TO_FILE_NAME)
        self.toggled.connect(self.change_global_set_title_to_file_name)

    # noinspection PyMethodMayBeStatic
    def change_global_set_title_to_file_name(self, new_state):
        GlobalSetting.MUX_SETTING_SET_TITLE_TO_FILE_NAME = bool(new_state)
