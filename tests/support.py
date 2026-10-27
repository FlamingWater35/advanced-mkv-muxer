"""Shared helpers for the test suite."""

import json
from pathlib import Path

from packages.Startup.GlobalFiles import SettingJsonInfoFilePath
from packages.Startup.Options import Options
from packages.Widgets.SingleDefaultPresetsData import SingleDefaultPresetsData


def reset_options(dark_mode=False):
    """Put the global option state into a known, isolated state."""
    Options.DefaultPresets = [SingleDefaultPresetsData()]
    Options.CurrentPreset = SingleDefaultPresetsData()
    Options.FavoritePresetId = 0
    Options.Dark_Mode = dark_mode
    Options.Attachment_Expert_Mode_Info_Message_Show = True
    Options.Choose_Preset_On_Startup = False


def write_settings(data, path=None):
    path = Path(path or SettingJsonInfoFilePath)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def read_settings(path=None):
    path = Path(path or SettingJsonInfoFilePath)
    return json.loads(path.read_text(encoding="utf-8"))


class FakeTaskBarProgress:
    """A no-op replacement for the Windows taskbar integration."""

    def __init__(self, window_id):
        self.window_id = window_id

    def start_muxing(self):
        pass

    def update_progress(self, new_progress):
        pass

    def pause_progress(self):
        pass

    def hide_progress(self):
        pass
