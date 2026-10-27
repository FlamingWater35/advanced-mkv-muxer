import subprocess
import sys
import unittest
from importlib.metadata import version

from tests import ROOT  # must run the test bootstrap before application imports

from PySide6.QtCore import Qt

from packages.Startup.MainApplication import MainApplication


class DependencyTests(unittest.TestCase):
    def test_python_version(self):
        self.assertEqual(sys.version_info[:2], (3, 12))

    def test_requirements_are_installed(self):
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        checked = 0
        for line in requirements.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "==" not in line:
                continue
            package, expected = (part.strip() for part in line.split("==", 1))
            self.assertEqual(version(package), expected,
                             f"{package} does not match requirements.txt")
            checked += 1
        self.assertGreaterEqual(checked, 3)

    def test_required_modules_import(self):
        import comtypes
        import psutil
        import PySide6

        self.assertTrue(PySide6.__version__)
        self.assertTrue(psutil.__version__)
        self.assertTrue(comtypes.__version__)

    def test_pip_reports_no_broken_requirements(self):
        result = subprocess.run(
            [sys.executable, "-m", "pip", "check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No broken requirements found", result.stdout)

    def test_qt_exposes_color_scheme_api(self):
        hints = MainApplication.styleHints()
        self.assertTrue(hasattr(hints, "colorScheme"))
        self.assertNotEqual(Qt.ColorScheme.Dark, Qt.ColorScheme.Light)
