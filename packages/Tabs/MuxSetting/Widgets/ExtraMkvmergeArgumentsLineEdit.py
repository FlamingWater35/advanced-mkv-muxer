from PySide6.QtWidgets import QLineEdit

from packages.Tabs.GlobalSetting import GlobalSetting


class ExtraMkvmergeArgumentsLineEdit(QLineEdit):
    def __init__(self):
        super().__init__()
        self.setText(GlobalSetting.MUX_SETTING_EXTRA_ARGUMENTS)
        self.setPlaceholderText("[Empty]  example: --no-date")
        self.setToolTip("Extra mkvmerge arguments, inserted right before the input file.\n"
                        "Wrap a value that contains spaces in double quotes: --title \"My Movie\"\n"
                        "--output is ignored, the destination folder defines the output file.\n"
                        "A non empty value forces mkvmerge, so the queue is never edited in place with "
                        "mkvpropedit.")
        self.setClearButtonEnabled(True)
        self.textChanged.connect(self.arguments_changed)

    def arguments_changed(self, new_text):
        GlobalSetting.MUX_SETTING_EXTRA_ARGUMENTS = new_text
