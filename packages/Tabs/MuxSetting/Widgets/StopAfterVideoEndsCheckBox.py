from PySide6.QtWidgets import QCheckBox

from packages.Tabs.GlobalSetting import GlobalSetting


class StopAfterVideoEndsCheckBox(QCheckBox):
    def __init__(self):
        super().__init__()
        self.setText("Stop After Video Ends")
        self.setToolTip(
            "<nobr>Adds <b>--stop-after-video-ends</b>: the muxing stops when the primary video track "
            "ends, so a longer audio track does not extend the file.")
        self.setChecked(GlobalSetting.MUX_SETTING_STOP_AFTER_VIDEO_ENDS)
        self.toggled.connect(self.change_global_stop_after_video_ends)

    # noinspection PyMethodMayBeStatic
    def change_global_stop_after_video_ends(self, new_state):
        GlobalSetting.MUX_SETTING_STOP_AFTER_VIDEO_ENDS = bool(new_state)
