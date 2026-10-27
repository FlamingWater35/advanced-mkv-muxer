"""Termination of the external tools (mkvmerge / mkvpropedit) this app started."""

import signal

import psutil


def kill_child_processes():
    """Terminate every child process of the application.

    Safe to call at any time: children that already exited or vanish meanwhile
    are ignored.
    """
    try:
        children = psutil.Process().children(recursive=True)
    except psutil.Error:
        return
    for child in children:
        try:
            child.send_signal(signal.SIGTERM)
        except psutil.Error:
            pass
