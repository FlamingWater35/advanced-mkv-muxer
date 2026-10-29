from PySide6.QtWidgets import QLineEdit

from packages.Tabs.GlobalSetting import GlobalSetting
from packages.Tabs.MuxSetting.Widgets.OutputNamePattern import get_output_name_variables_tooltip, \
    get_unknown_pattern_variables


class OutputNamePatternLineEdit(QLineEdit):
    def __init__(self):
        super().__init__()
        self.setText(GlobalSetting.MUX_SETTING_OUTPUT_NAME_PATTERN)
        self.setPlaceholderText("[Empty]  example: %source% - %episode% [%resolution%]")
        self.setToolTip(get_output_name_variables_tooltip() +
                        "\n\nOnly used when a destination folder is set, the source name is kept "
                        "when the field is empty. Write the name without the .mkv extension.")
        self.setClearButtonEnabled(True)
        self.textChanged.connect(self.pattern_changed)

    def pattern_changed(self, new_text):
        GlobalSetting.MUX_SETTING_OUTPUT_NAME_PATTERN = new_text
        unknown_variables = get_unknown_pattern_variables(new_text)
        if len(unknown_variables) > 0:
            self.setStyleSheet("color: red;")
            self.setToolTip("Unknown variables: " + ", ".join(unknown_variables) +
                            "\n\n" + get_output_name_variables_tooltip())
        else:
            self.setStyleSheet("")
            self.setToolTip(get_output_name_variables_tooltip())
