from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QCompleter

from packages.Startup.InitializeScreenResolution import screen_size


class LanguagesComboBox(QComboBox):
    """Language list that can be filtered by typing (#122).

    The line edit stays bound to a real item: unknown text is reverted to the
    last valid selection when editing finishes, so callers can keep reading
    ``currentText()`` safely.
    """

    def __init__(self, items_list, default_item):
        super().__init__()
        self.setMinimumWidth(screen_size.width() // 10)
        self.addItems(items_list)
        self.setCurrentIndex(items_list.index(default_item))
        self.setMaxVisibleItems(8)
        self.setStyleSheet("QComboBox { combobox-popup: 0; }")
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        completer = self.completer()
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.lineEdit().setPlaceholderText("Type to search a language")
        self.lineEdit().editingFinished.connect(self.restore_last_valid_language)
        self.currentIndexChanged.connect(self.remember_valid_index)
        self._last_valid_index = self.currentIndex()

    def addItems(self, texts):
        super().addItems(texts)
        for i in range(len(texts)):
            self.setItemData(i, texts[i], Qt.ItemDataRole.ToolTipRole)

    def remember_valid_index(self, index):
        if index >= 0:
            self._last_valid_index = index

    def restore_last_valid_language(self):
        index = self.findText(self.lineEdit().text(), Qt.MatchFlag.MatchFixedString)
        if index >= 0:
            self.setCurrentIndex(index)
            return
        if self._last_valid_index < 0:
            self._last_valid_index = 0
        self.setCurrentIndex(self._last_valid_index)
        self.lineEdit().setText(self.itemText(self._last_valid_index))
