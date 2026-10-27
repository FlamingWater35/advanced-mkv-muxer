"""Test bootstrap for Advanced MKV Muxer.

Every test run gets an isolated profile inside ``tests/.tmp``.  The
environment is adjusted before any application module is imported because
``packages.Startup.GlobalFiles`` resolves the application data folder at
import time.
"""

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TESTS_DIR = Path(__file__).resolve().parent
TEMP_PARENT = TESTS_DIR / ".tmp"
TEMP_PARENT.mkdir(parents=True, exist_ok=True)
TEMP_ROOT = Path(tempfile.mkdtemp(prefix="run-", dir=TEMP_PARENT))
HOME = TEMP_ROOT / "home"
TMP = TEMP_ROOT / "tmp"

for folder in (
        HOME / "AppData" / "Roaming",
        HOME / "AppData" / "Local",
        TMP,
):
    folder.mkdir(parents=True, exist_ok=True)

os.environ["USERPROFILE"] = str(HOME)
os.environ["HOME"] = str(HOME)
os.environ["APPDATA"] = str(HOME / "AppData" / "Roaming")
os.environ["LOCALAPPDATA"] = str(HOME / "AppData" / "Local")
os.environ["TMPDIR"] = str(TMP)
os.environ["TEMP"] = str(TMP)
os.environ["TMP"] = str(TMP)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
tempfile.tempdir = str(TMP)

# GlobalFiles uses sys.argv[0] to find the Resources folder.
sys.argv[0] = str(ROOT / "main.py")

# MainApplication creates the single QApplication shared by all GUI tests.
from packages.Startup import MainApplication  # noqa: E402,F401


def _cleanup():
    try:
        MainApplication.quit()
    except Exception:
        pass
    shutil.rmtree(TEMP_ROOT, ignore_errors=True)
    try:
        TEMP_PARENT.rmdir()
    except OSError:
        pass


atexit.register(_cleanup)
