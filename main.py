# -*- coding: utf-8 -*-
# import faulthandler
import logging
import sys
from traceback import format_exception

from packages.Startup.MainApplication import MainApplication
from packages.Startup import GlobalFiles
from packages.Startup import GlobalIcons
from packages.Startup.ChildProcesses import kill_child_processes
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication
from packages.Widgets.WarningDialog import WarningDialog

if sys.platform == "win32":
    import ctypes

    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Advanced.MKVMuxer")
    from packages.MainWindow import MainWindow
else:
    from packages.MainWindowNonWindowsSystem import MainWindowNonWindowsSystem as MainWindow

# faulthandler.enable()
window: MainWindow
app: QApplication


def setup_application_font():
    try:
        font_id = QFontDatabase.addApplicationFont(GlobalFiles.MyFontPath)
        font_name = QFontDatabase.applicationFontFamilies(font_id)[0]
        font = QFont(font_name, 10)
        app.setFont(font)
    except Exception as e:
        warning_dialog = WarningDialog(window_title="Missing Fonts", info_message="Can't find 'OpenSans' font at "
                                                                                  "../Resources/Fonts/OpenSans.ttf\n" +
                                                                                  "application will use default font")
        warning_dialog.execute()


def create_application():
    global app
    app = MainApplication
    app.setWindowIcon(GlobalIcons.AppIcon)
    # GlobalFiles can only record a start-up failure at import time, because a
    # QMessageBox needs the QApplication that is created right above.
    GlobalFiles.show_startup_error_if_any()


def create_window():
    global window
    window = MainWindow(sys.argv)


def run_application():
    app_execute = app.exec()
    # The window already stopped and joined its workers in closeEvent; this is
    # only a safety net for tools that outlived it.
    kill_child_processes()
    sys.exit(app_execute)


def logger_exception(exception_type, exception_value, exception_trace_back):
    for string in format_exception(exception_type, exception_value, exception_trace_back):
        logging.error(string)


def setup_logger():
    logging.basicConfig(
        format='(%(asctime)s): %(name)s [%(levelname)s]: %(message)s',
        datefmt='%m/%d/%Y %I:%M:%S %p',
        level=logging.DEBUG,
        handlers=[
            logging.FileHandler(filename=GlobalFiles.AppLogFilePath,
                                encoding='utf-8', mode='a+'),
            logging.StreamHandler()
        ]
    )
    sys.excepthook = logger_exception


if __name__ == "__main__":
    setup_logger()
    create_application()
    setup_application_font()
    create_window()
    run_application()
