"""Detect the operating system's current light/dark theme."""

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication


def _read_windows_personalize_value(value_name):
    """Return a Windows Personalize DWORD, or None when it is unavailable."""
    try:
        import winreg
    except ImportError:
        return None
    try:
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _ = winreg.QueryValueEx(key, value_name)
        return int(value)
    except (OSError, TypeError, ValueError):
        return None


def detect_windows_dark_mode():
    """Return True for a dark Windows app theme, False for light, None if unknown."""
    if sys.platform != "win32":
        return None
    for value_name in ("AppsUseLightTheme", "SystemUsesLightTheme"):
        value = _read_windows_personalize_value(value_name)
        if value is not None:
            return value == 0
    return None


def detect_system_dark_mode():
    """Return True when the system currently uses its dark theme."""
    app = QGuiApplication.instance()
    if app is not None:
        try:
            color_scheme = app.styleHints().colorScheme()
            if color_scheme == Qt.ColorScheme.Dark:
                return True
            if color_scheme == Qt.ColorScheme.Light:
                return False
        except (AttributeError, RuntimeError):
            pass

    windows_result = detect_windows_dark_mode()
    if windows_result is not None:
        return windows_result

    return False
