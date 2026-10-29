from PySide6.QtWidgets import QLabel

from packages.Tabs.GlobalSetting import get_readable_filesize


class TotalSizeChangeLabel(QLabel):
    """Total source-vs-output size difference of the finished jobs (#142)."""

    def __init__(self):
        super().__init__(" Size Change: 0.00 B")
        self.setToolTip(
            "<nobr>Total size difference between the source files and the outputs of the finished jobs.<br>"
            "Failed jobs are not counted.")

    def update_total_size_change(self, change_bytes):
        if change_bytes == 0:
            text = "0.00 B"
        else:
            sign = "+" if change_bytes > 0 else "-"
            text = sign + get_readable_filesize(abs(change_bytes))
        self.setText(" Size Change: " + text)
