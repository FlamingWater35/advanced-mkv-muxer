from PySide6.QtWidgets import QCheckBox

from packages.Tabs.GlobalSetting import GlobalSetting


class GenerateChaptersCheckBox(QCheckBox):
    def __init__(self):
        super().__init__()
        self.setText("Generate Chapters")
        self.setToolTip(
            "<nobr>Adds <b>--generate-chapters interval:&lt;seconds&gt;s</b> and drops the chapters "
            "already stored in the source file.<br>"
            "Requires the source to have a video or audio track.")
        self.setChecked(GlobalSetting.CHAPTER_GENERATE_BY_INTERVAL)
        self.toggled.connect(self.change_global_generate_chapters)

    # noinspection PyMethodMayBeStatic
    def change_global_generate_chapters(self, new_state):
        GlobalSetting.CHAPTER_GENERATE_BY_INTERVAL = bool(new_state)
