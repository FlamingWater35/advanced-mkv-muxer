from PySide6.QtWidgets import QCheckBox

from packages.Tabs.GlobalSetting import GlobalSetting


class DiscardAllTagsCheckBox(QCheckBox):
    def __init__(self):
        super().__init__()
        self.setText("Discard Tags")
        self.setToolTip(
            "<nobr>Adds <b>--no-global-tags</b> and <b>--no-track-tags</b> for the source file, "
            "so its tags are not copied to the output.")
        self.setChecked(GlobalSetting.MUX_SETTING_DISCARD_ALL_TAGS)
        self.toggled.connect(self.change_global_discard_all_tags)

    # noinspection PyMethodMayBeStatic
    def change_global_discard_all_tags(self, new_state):
        GlobalSetting.MUX_SETTING_DISCARD_ALL_TAGS = bool(new_state)
