from PySide6.QtWidgets import QCheckBox

from packages.Tabs.GlobalSetting import GlobalSetting


class AutoDetectFontsCheckBox(QCheckBox):
    def __init__(self):
        super().__init__()
        self.setText("Attach Subtitle Fonts")
        self.setToolTip("Reads the fonts the attached subtitles ask for (ASS/SSA styles and\n"
                        "inline \\fn overrides) and attaches the matching font files from the\n"
                        "folder of each subtitle, the folder of the video and the attachment folder.")
        self.setChecked(GlobalSetting.ATTACHMENT_AUTO_DETECT_FONTS)
        self.toggled.connect(self.change_global_auto_detect_fonts)

    # noinspection PyMethodMayBeStatic
    def change_global_auto_detect_fonts(self, new_state):
        GlobalSetting.ATTACHMENT_AUTO_DETECT_FONTS = bool(new_state)
