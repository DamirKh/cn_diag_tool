"""Tests for the remembered Excel export directory."""
import os
import tempfile
import unittest

from PyQt6.QtCore import QCoreApplication, QSettings

import export_paths


class ExportPathsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = QSettings(os.path.join(self.tmp.name, "s.ini"), QSettings.Format.IniFormat)
        self.config_dir = os.path.join(self.tmp.name, "CN_diag_tool")
        self.default = export_paths.default_dir(self.config_dir)

    def tearDown(self):
        self.settings.clear()
        self.settings.sync()
        self.tmp.cleanup()

    def test_default_is_sites_subdirectory(self):
        self.assertEqual(self.default, os.path.join(self.config_dir, "sites"))

    def test_unset_falls_back_to_default(self):
        self.assertEqual(export_paths.current_dir(self.settings, self.default), self.default)

    def test_remember_stores_directory(self):
        target_dir = os.path.join(self.tmp.name, "reports")
        os.makedirs(target_dir)
        filename = os.path.join(target_dir, "report.xlsx")
        self.assertEqual(export_paths.remember(self.settings, filename), target_dir)
        self.assertEqual(export_paths.current_dir(self.settings, self.default), target_dir)

    def test_reset_returns_to_default(self):
        target_dir = os.path.join(self.tmp.name, "reports")
        os.makedirs(target_dir)
        export_paths.remember(self.settings, os.path.join(target_dir, "report.xlsx"))
        export_paths.reset(self.settings)
        self.assertEqual(export_paths.current_dir(self.settings, self.default), self.default)

    def test_missing_stored_directory_falls_back(self):
        self.settings.setValue(export_paths.EXPORT_DIR_KEY, os.path.join(self.tmp.name, "gone"))
        self.settings.sync()
        self.assertEqual(export_paths.current_dir(self.settings, self.default), self.default)


def setUpModule():
    global _app
    _app = QCoreApplication.instance() or QCoreApplication([])


if __name__ == "__main__":
    unittest.main()
