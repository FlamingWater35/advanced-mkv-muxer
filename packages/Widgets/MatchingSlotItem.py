from PySide6.QtWidgets import QTableWidgetItem

from packages.Tabs.GlobalSetting import EMPTY_MATCHING_SLOT_DISPLAY_NAME, is_empty_matching_slot


def create_matching_file_item(file_name, empty_slot_tool_tip):
    """Build a matching-table name cell.

    An empty slot is shown as an italic placeholder instead of a file name, so
    the user can see that this episode deliberately gets no attached file
    (#158, #120). Everything else keeps the historical " " prefix.
    """
    item = QTableWidgetItem()
    if is_empty_matching_slot(file_name):
        item.setText(" " + EMPTY_MATCHING_SLOT_DISPLAY_NAME)
        item.setToolTip(empty_slot_tool_tip)
        font = item.font()
        font.setItalic(True)
        item.setFont(font)
    else:
        item.setText(" " + file_name)
        item.setToolTip(file_name)
    return item
