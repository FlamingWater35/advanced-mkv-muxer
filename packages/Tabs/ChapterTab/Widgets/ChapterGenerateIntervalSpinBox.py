from PySide6.QtWidgets import QSpinBox

from packages.Tabs.GlobalSetting import GlobalSetting


class ChapterGenerateIntervalSpinBox(QSpinBox):
    def __init__(self):
        super().__init__()
        self.setRange(1, 86400)
        self.setSuffix(" s")
        self.setToolTip("Interval between generated chapters, in seconds.")
        self.setValue(int(GlobalSetting.CHAPTER_GENERATE_INTERVAL_SECONDS))
        self.setEnabled(bool(GlobalSetting.CHAPTER_GENERATE_BY_INTERVAL))
        self.valueChanged.connect(self.change_global_generate_interval)

    # noinspection PyMethodMayBeStatic
    def change_global_generate_interval(self, new_value):
        GlobalSetting.CHAPTER_GENERATE_INTERVAL_SECONDS = int(new_value)
