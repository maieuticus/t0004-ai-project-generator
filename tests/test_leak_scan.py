"""Tests for credential leak detection in acceptance artifacts."""

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class LeakScan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scan = load_script("leak_scan")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def test_detects_and_redacts_synthetic_credentials_in_all_acceptance_artifacts(self):
        token = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"
        locations = (
            self.base / "logs/run.log",
            self.base / ".git/config",
            self.base / "plan.json",
            self.base / "snapshot/manifest.json",
            self.base / "backups/backup.json",
        )
        for path in locations:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"credential={token}\n", encoding="utf-8")

        findings = self.scan.scan_paths([self.base])
        self.assertEqual({finding.path for finding in findings}, set(locations))
        for finding in findings:
            self.assertNotIn(token, finding.message)
            self.assertIn("REDACTED", finding.message)

    def test_clean_tree_passes(self):
        clean = self.base / "clean.txt"
        clean.write_text("nothing sensitive here\n", encoding="utf-8")
        self.assertEqual(self.scan.scan_paths([self.base]), [])


if __name__ == "__main__":
    unittest.main()
