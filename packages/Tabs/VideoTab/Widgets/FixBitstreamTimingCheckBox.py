from PySide6.QtWidgets import QCheckBox

from packages.Tabs.GlobalSetting import GlobalSetting


class FixBitstreamTimingCheckBox(QCheckBox):
    def __init__(self):
        super().__init__()
        self.setText("Fix Timing")
        self.setToolTip(
            "<nobr>Adds <b>--fix-bitstream-timing-information 0:1</b> for the source file.<br>"
            "Use it when the video bitstream carries a wrong frame rate and you override it "
            "with Default Duration/FPS.")
        self.setChecked(GlobalSetting.VIDEO_FIX_BITSTREAM_TIMING_INFO)
        self.toggled.connect(self.change_global_fix_bitstream_timing_info)

    # noinspection PyMethodMayBeStatic
    def change_global_fix_bitstream_timing_info(self, new_state):
        GlobalSetting.VIDEO_FIX_BITSTREAM_TIMING_INFO = bool(new_state)
