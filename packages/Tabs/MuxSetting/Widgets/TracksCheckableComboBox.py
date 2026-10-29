from PySide6 import QtCore, QtGui
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QStyledItemDelegate, QComboBox

# noinspection SpellCheckingInspection
from packages.Tabs.GlobalSetting import (
    GlobalSetting,
    TRACK_SECTION_FORMAT,
    TRACK_SECTION_LANGUAGE,
    TRACK_SECTION_ORDER,
    TRACK_SECTION_TRACK_ID,
    TRACK_SECTION_TRACK_NAME,
    get_track_id_from_menu_entry,
    is_track_menu_section,
)


class TracksCheckableComboBox(QComboBox):
    # Subclass Delegate to increase item height
    closeList = QtCore.Signal()

    class Delegate(QStyledItemDelegate):
        def sizeHint(self, option, index):
            size = super().sizeHint(option, index)
            s = size.height() * 4 // 3
            size.setHeight(int(s))
            return size

    def __init__(self):
        super().__init__()
        # Make the combo editable to set a custom text, but readonly
        self.hint = ""
        self.current_list = []
        self.current_text = ""
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.lineEdit().selectionChanged.connect(self.disable_select)
        self.lineEdit().setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
        self.hint_when_enabled = ""
        self.empty_selection_string = "Discard All"
        self.empty_selection_hint_string = ""
        self.tracks_id = []
        self.tracks_language = []
        self.tracks_name = []
        self.tracks_order = []
        self.tracks_format = []

        # Use custom delegate
        self.setItemDelegate(TracksCheckableComboBox.Delegate())

        # Update the text when an item is toggled
        self.model().dataChanged.connect(self.updateText)

        # Hide and show popup when clicking the line edit
        self.lineEdit().installEventFilter(self)
        self.closeOnLineEditClick = False

        # Prevent popup from closing when clicking on an item
        self.view().viewport().installEventFilter(self)
        # self.check_if_nothing_selected()

    def disable_select(self):
        self.lineEdit().deselect()

    def resizeEvent(self, event):
        # Recompute text to elide as needed
        self.updateText()
        super().resizeEvent(event)
        self.update_shown_text()

    def update_state_of_select_all_check(self):
        counter_item_checked = 0
        counter_item_unchecked = 0
        for i in range(1, self.model().rowCount()):
            item = self.model().item(i)
            if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                if item.checkState() == Qt.CheckState.Checked:
                    counter_item_checked += 1
                else:
                    counter_item_unchecked += 1
        if counter_item_checked == 0:
            self.model().item(0).setCheckState(Qt.CheckState.Unchecked)
        elif counter_item_unchecked == 0:
            self.model().item(0).setCheckState(Qt.CheckState.Checked)
        else:
            self.model().item(0).setCheckState(Qt.CheckState.PartiallyChecked)

    def eventFilter(self, object, event):
        if str(event.__class__).find("Event") == -1:
            return False
        try:
            if self.isEnabled():
                if object == self.lineEdit():
                    if event.type() == QEvent.MouseButtonRelease:
                        if self.closeOnLineEditClick:
                            self.hidePopup()
                        else:
                            self.showPopup()
                        return True
                    return False

                if object == self.view().viewport():
                    if event.type() == QEvent.MouseButtonRelease:
                        index = self.view().indexAt(event.pos())
                        item = self.model().item(index.row())
                        if item.text().find("All Tracks") != -1:
                            if item.checkState() == Qt.CheckState.Checked or item.checkState() == Qt.CheckState.PartiallyChecked:
                                for i in range(0, self.model().rowCount()):
                                    item = self.model().item(i)
                                    if not is_track_menu_section(item.text()):
                                        item.setCheckState(Qt.CheckState.Unchecked)
                            else:
                                for i in range(0, self.model().rowCount()):
                                    item = self.model().item(i)
                                    if not is_track_menu_section(item.text()):
                                        item.setCheckState(Qt.CheckState.Checked)
                            return True
                        elif not is_track_menu_section(item.text()):
                            if item.checkState() == Qt.CheckState.Checked:
                                item.setCheckState(Qt.CheckState.Unchecked)
                                self.update_state_of_select_all_check()
                            else:
                                item.setCheckState(Qt.CheckState.Checked)
                                self.update_state_of_select_all_check()
                            return True
                        else:
                            return False
                return False
            else:
                return False
        except Exception as e:
            return False

    def showPopup(self):
        super().showPopup()
        # When the popup is displayed, a click on the lineedit should close it
        self.closeOnLineEditClick = True

    def hidePopup(self):
        super().hidePopup()
        # Used to prevent immediate reopening when clicking on the lineEdit
        self.startTimer(100)
        # Refresh the display text when closing
        self.updateText()
        # self.check_if_nothing_selected()
        self.closeList.emit()

    def timerEvent(self, event):
        # After timeout, kill timer, and reenable click on line edit
        self.killTimer(event.timerId())
        self.closeOnLineEditClick = False

    def updateText(self):
        # Every section keeps its own selection list; the summary text and the
        # tooltip name them one by one.
        checked_by_section = {
            TRACK_SECTION_ORDER: [],
            TRACK_SECTION_TRACK_ID: [],
            TRACK_SECTION_LANGUAGE: [],
            TRACK_SECTION_FORMAT: [],
            TRACK_SECTION_TRACK_NAME: [],
        }
        section_summary = {
            TRACK_SECTION_ORDER: "Orders",
            TRACK_SECTION_TRACK_ID: "Track Ids",
            TRACK_SECTION_LANGUAGE: "Languages",
            TRACK_SECTION_FORMAT: "Formats",
            TRACK_SECTION_TRACK_NAME: "Track Names",
        }
        current_section = ""
        for i in range(self.model().rowCount()):
            item_text = self.model().item(i).text()
            if is_track_menu_section(item_text):
                current_section = item_text
                continue
            if current_section not in checked_by_section:
                continue
            if self.model().item(i).checkState() != Qt.CheckState.Checked:
                continue
            if current_section == TRACK_SECTION_TRACK_ID:
                track_id = get_track_id_from_menu_entry(item_text)
                if track_id is None:
                    continue
                checked_by_section[current_section].append(track_id)
            else:
                checked_by_section[current_section].append(item_text)

        self.tracks_order = checked_by_section[TRACK_SECTION_ORDER]
        self.tracks_id = checked_by_section[TRACK_SECTION_TRACK_ID]
        self.tracks_language = checked_by_section[TRACK_SECTION_LANGUAGE]
        self.tracks_format = checked_by_section[TRACK_SECTION_FORMAT]
        self.tracks_name = checked_by_section[TRACK_SECTION_TRACK_NAME]

        text_parts = []
        hint_parts = []
        for section in (TRACK_SECTION_ORDER, TRACK_SECTION_TRACK_ID, TRACK_SECTION_LANGUAGE,
                        TRACK_SECTION_FORMAT, TRACK_SECTION_TRACK_NAME):
            values = checked_by_section[section]
            if len(values) == 0:
                continue
            text_parts.append(section_summary[section] + ": [" + ", ".join(values) + "]")
            hint_parts.append("-" + text_parts[-1])

        text = ",".join(text_parts)
        # Compute elided text (with "...")
        self.current_text = text
        if text != "":
            self.update_shown_text()
            self.hint = "<br>".join(hint_parts)
        else:
            italic_font = self.lineEdit().font()
            italic_font.setItalic(True)
            self.lineEdit().setFont(italic_font)
            self.lineEdit().setText(self.empty_selection_string)
            self.hint = self.empty_selection_hint_string
        self.setToolTip(self.hint)

    def addItem(self, text, data=None):
        item = QtGui.QStandardItem()
        item.setText(text)
        if data is None:
            item.setData(text)
        else:
            item.setData(data)
        if not is_track_menu_section(text) and text.find("All Tracks") == -1:
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            item.setData(Qt.CheckState.Unchecked, Qt.CheckStateRole)
            item.setData(text, Qt.ItemDataRole.ToolTipRole)
            self.model().appendRow(item)
        elif text.find("All Tracks") != -1:
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            item.setData(Qt.CheckState.Unchecked, Qt.CheckStateRole)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.model().appendRow(item)
        else:
            # bigger_font=self.lineEdit().font()
            # bigger_font.setPointSize(bigger_font.pointSize()+1)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            # item.setFont(bigger_font)
            item.setData(Qt.CheckState.Unchecked)
            self.model().appendRow(item)

    def addItems(self, texts: list, datalist=None):
        self.clear()
        self.addItem("All Tracks      ", None)
        for i, text in enumerate(texts):
            try:
                data = datalist[i]
            except (TypeError, IndexError):
                data = None
            self.addItem(text, data)
        self.current_list = texts.copy()

        self.show_discard_all_text()

    def show_discard_all_text(self):
        italic_font = self.lineEdit().font()
        italic_font.setItalic(True)
        self.lineEdit().setFont(italic_font)
        self.lineEdit().setText(self.empty_selection_string)
        self.hint = self.empty_selection_hint_string
        self.setToolTip(self.hint)

    def currentData(self):
        # Return the list of selected items data
        res = []
        for i in range(self.model().rowCount()):
            if self.model().item(i).checkState() == Qt.CheckState.Checked:
                res.append(self.model().item(i).data())
        return res

    def setData(self, texts):
        for i in range(self.model().rowCount()):
            if self.model().item(i).data() in texts:
                self.model().item(i).setCheckState(Qt.CheckState.Checked)
            else:
                self.model().item(i).setCheckState(Qt.CheckState.Unchecked)

    def set_tool_tip_hint(self):
        self.setToolTip(self.hint)
        self.setToolTipDuration(12000)

    def setEnabled(self, new_state: bool):
        super().setEnabled(new_state)
        if not new_state and not GlobalSetting.JOB_QUEUE_EMPTY:
            if self.hint_when_enabled != "":
                self.setToolTip("<nobr>" + self.hint_when_enabled + "<br>" + GlobalSetting.DISABLE_TOOLTIP)
            else:
                self.setToolTip("<nobr>" + GlobalSetting.DISABLE_TOOLTIP)
        else:
            self.setToolTip(self.hint_when_enabled)

    def setDisabled(self, new_state: bool):
        super().setDisabled(new_state)
        if new_state and not GlobalSetting.JOB_QUEUE_EMPTY:
            if self.hint_when_enabled != "":
                self.setToolTip("<nobr>" + self.hint_when_enabled + "<br>" + GlobalSetting.DISABLE_TOOLTIP)
            else:
                self.setToolTip("<nobr>" + GlobalSetting.DISABLE_TOOLTIP)
        else:
            self.setToolTip(self.hint_when_enabled)

    def setToolTip(self, new_tool_tip: str):
        if self.isEnabled() or GlobalSetting.JOB_QUEUE_EMPTY:
            self.hint_when_enabled = new_tool_tip
        super().setToolTip(new_tool_tip)

    def update_shown_text(self):
        if self.current_text != "":
            metrics = QFontMetrics(self.lineEdit().font())
            non_italic_font = self.lineEdit().font()
            non_italic_font.setItalic(False)
            self.lineEdit().setFont(non_italic_font)
            elided_text = metrics.elidedText(self.current_text, Qt.TextElideMode.ElideRight, self.lineEdit().width())
            self.lineEdit().setText(elided_text)
        else:
            italic_font = self.lineEdit().font()
            italic_font.setItalic(True)
            self.lineEdit().setFont(italic_font)
            self.lineEdit().setText(self.empty_selection_string)
            self.hint = self.empty_selection_hint_string
