from PySide6.QtWidgets import QSpinBox

from packages.Tabs.GlobalSetting import GlobalSetting


class ChapterDelaySpinBox(QSpinBox):
    MINIMUM_DELAY_MILLISECONDS = -3600000
    MAXIMUM_DELAY_MILLISECONDS = 3600000

    def __init__(self):
        super().__init__()
        self.setRange(self.MINIMUM_DELAY_MILLISECONDS, self.MAXIMUM_DELAY_MILLISECONDS)
        self.setSingleStep(1)
        self.setSuffix(" ms")
        self.setToolTip("Delay added to every chapter of the attached chapter file.\n"
                        "The first chapter is pinned at 00:00:00, so a positive delay never creates a "
                        "gap before chapter 1.\nA negative delay is clamped at 00:00:00.")
        self.setValue(GlobalSetting.CHAPTER_DELAY_MILLISECONDS)
        self.valueChanged.connect(self.value_changed)

    def value_changed(self, new_value):
        GlobalSetting.CHAPTER_DELAY_MILLISECONDS = int(new_value)
