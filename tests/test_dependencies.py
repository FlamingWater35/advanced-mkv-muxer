import importlib.machinery
import subprocess
import sys
import unittest
from importlib.metadata import version

from tests import ROOT  # must run the test bootstrap before application imports

from PySide6.QtCore import Qt

from packages.Startup.MainApplication import MainApplication

# requirements.txt pins a few packages that only exist on one platform, and CI
# installs the same file with those lines removed (see .github/workflows).
# comtypes wraps the Windows taskbar API, so it is absent on Linux by design and
# asserting its version there would fail a correct install.
PLATFORM_ONLY_PACKAGES = {
    "comtypes": "win32",
}


def is_installed_on_this_platform(package):
    """False for a requirement that is deliberately absent on this platform."""
    required_on = PLATFORM_ONLY_PACKAGES.get(package.lower())
    return required_on is None or required_on == sys.platform


class DependencyTests(unittest.TestCase):
    def test_python_version(self):
        self.assertEqual(sys.version_info[:2], (3, 12))

    def test_requirements_are_installed(self):
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        expected_packages = {}
        for line in requirements.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "==" not in line:
                continue
            package, expected = (part.strip() for part in line.split("==", 1))
            if not is_installed_on_this_platform(package):
                continue
            expected_packages[package] = expected
        # Guards against a parser that silently matches nothing: the loop below
        # would then pass while checking no package at all. Only two of the three
        # pins apply on Linux, because comtypes is Windows-only.
        self.assertGreaterEqual(len(expected_packages), 2)
        for package, expected in expected_packages.items():
            self.assertEqual(version(package), expected,
                             f"{package} does not match requirements.txt")

    def test_required_modules_import(self):
        import psutil
        import PySide6

        self.assertTrue(PySide6.__version__)
        self.assertTrue(psutil.__version__)
        if sys.platform == "win32":
            import comtypes

            self.assertTrue(comtypes.__version__)

    def test_shiboken6_is_a_real_package_and_not_a_namespace_package(self):
        """Guards the start-up crash caused by an incomplete shiboken6 install.

        ``libshiboken``'s ``signature_bootstrap`` does
        ``Path(shiboken6.__file__).resolve().parent / "files.dir"``. When
        ``shiboken6/__init__.py`` is missing, Python treats the directory as an
        implicit namespace package, ``__file__`` is None, and the process dies
        with "argument should be a str or an os.PathLike object where
        __fspath__ returns a str, not 'NoneType'" followed by a fatal
        "libshiboken/signature: could not initialize part 2".
        """
        import shiboken6

        self.assertIsNotNone(
            shiboken6.__file__,
            "shiboken6 is being imported as a namespace package, which means "
            "shiboken6/__init__.py is missing from the environment. Reinstall "
            "the pinned PySide6 to repair it.",
        )
        self.assertFalse(
            isinstance(shiboken6.__spec__.loader, importlib.machinery.NamespaceLoader),
            "shiboken6 must be a regular package, not a namespace package.",
        )

    def test_shiboken6_reports_a_version(self):
        import shiboken6

        self.assertTrue(shiboken6.__version__)

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
