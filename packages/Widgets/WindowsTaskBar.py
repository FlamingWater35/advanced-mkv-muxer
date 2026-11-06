import ctypes
from ctypes import wintypes
import comtypes
import comtypes.client as cc
TaskBarGUID = "{56FDF344-FD6D-11d0-958A-006097C9A090}"
comtypes.CoInitializeEx()
from packages.Widgets.WindowsTaskBarLib import ITaskbarList3


def create_icon(icon_path):
    CreateIconFromResourceEx = ctypes.windll.user32.CreateIconFromResourceEx
    CreateIconFromResourceEx.restype = ctypes.wintypes.HICON
    size_x, size_y = 32, 32
    LR_DEFAULTCOLOR = 0
    LR_SHARED = 32768
    with open(icon_path, "rb") as f:
        png = f.read()
    hicon = CreateIconFromResourceEx(png, len(png), 1, 0x30000, size_x, size_y, LR_SHARED)
    return hicon


class WindowsTaskBar:
    """Thin wrapper around the Windows taskbar progress API.

    The taskbar is a convenience, never a requirement: it is unavailable in
    sessions without a shell (services, some sandboxes, RDP before logon) and
    ``ITaskbarList3`` refuses calls with E_ACCESSDENIED there. Every method
    therefore degrades to a no-op instead of raising, so a missing taskbar
    cannot stop the application from starting.
    """

    def __init__(self, hwnd):
        super().__init__()
        self.window_id = hwnd
        self.taskbar = None
        try:
            self.taskbar = cc.CreateObject(
                TaskBarGUID,
                interface=ITaskbarList3, clsctx=comtypes.CLSCTX_ALL)
            self.taskbar.HrInit()
        except Exception:
            self.taskbar = None

    @property
    def is_available(self):
        return self.taskbar is not None

    def _call(self, name, *args):
        if self.taskbar is None:
            return
        try:
            getattr(self.taskbar, name)(*args)
        except Exception:
            # A failing call means the shell went away (logoff, restart); stop
            # trying for the rest of the session rather than raising at every
            # progress update.
            self.taskbar = None

    def setState(self, value):
        if value == 'normal':
            self._call("SetProgressState", self.window_id, 0)

        elif value == 'warning':
            self._call("SetProgressState", self.window_id, 10)

        elif value == 'error':
            self._call("SetProgressState", self.window_id, 15)

        elif value == 'loading':
            self._call("SetProgressState", self.window_id, -15)

        elif value == 'done':
            try:
                ctypes.windll.user32.FlashWindow(self.window_id, True)
            except Exception:
                pass

    def setProgress(self, value: int):
        value = min(value, 100)
        value = max(0, value)
        self._call("setProgressValue", self.window_id, value, 100)

    def setOverlayIcon(self, icon_path):
        try:
            hicon = create_icon(icon_path=icon_path)
        except Exception:
            return
        self._call("SetOverlayIcon", self.window_id, hicon, "some_random_string")

    def clearOverlayIcon(self):
        self._call("SetOverlayIcon", self.window_id, 0, "some_random_string")
