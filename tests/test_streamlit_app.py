import importlib.util
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_entry_point():
    spec = importlib.util.spec_from_file_location("folioshift_entry", ROOT / "streamlit_app.py")
    module = importlib.util.module_from_spec(spec)
    with patch("runpy.run_path"), patch.dict(os.environ):
        spec.loader.exec_module(module)
    return module


class DropStaleModulesTest(unittest.TestCase):
    def setUp(self):
        self.entry = load_entry_point()
        self.folder = tempfile.TemporaryDirectory()
        self.package = Path(self.folder.name) / "pkg"
        self.package.mkdir()
        (self.package / "a.py").write_text("x = 1\n")

    def tearDown(self):
        self.folder.cleanup()

    def test_keeps_modules_when_the_code_did_not_change(self):
        stamp = self.entry.drop_stale_project_modules(self.package, {})
        modules = {"pkg": types.SimpleNamespace(_code_stamp=stamp), "pkg.a": object(), "other": object()}
        self.entry.drop_stale_project_modules(self.package, modules)
        self.assertEqual(set(modules), {"pkg", "pkg.a", "other"})

    def test_drops_project_modules_after_an_update(self):
        modules = {"pkg": types.SimpleNamespace(_code_stamp=1), "pkg.a": object(), "pkgextra": object(), "other": object()}
        self.entry.drop_stale_project_modules(self.package, modules)
        self.assertEqual(set(modules), {"pkgextra", "other"})

    def test_drops_modules_loaded_before_stamps_existed(self):
        modules = {"pkg": types.SimpleNamespace(), "pkg.a": object()}
        self.entry.drop_stale_project_modules(self.package, modules)
        self.assertEqual(modules, {})


if __name__ == "__main__":
    unittest.main()
