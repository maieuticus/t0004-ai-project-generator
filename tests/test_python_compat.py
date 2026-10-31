"""Capability verification for the Python module's t0003 baseline."""

import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from project_generator import python_compat
from project_generator.plan import PathSafetyError


class PythonCompatibility(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.contents = {name: (name + "\n").encode() for name in python_compat.VERIFIED_FILES}
        for name, content in self.contents.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        digests = {name: hashlib.sha256(content).hexdigest() for name, content in self.contents.items()}
        patch = mock.patch.dict(python_compat.VERIFIED_FILES, digests, clear=True)
        patch.start()
        self.addCleanup(patch.stop)

    def test_verified_files_return_bound_states(self):
        result = python_compat.python_capabilities(str(self.root))
        self.assertEqual(result["conflicts"], [])
        self.assertEqual([state["path"] for state in result["files"]], list(self.contents))
        self.assertTrue(all(state["sha256"] and state["attributes"] for state in result["files"]))
        self.assertTrue(all(state["before_attributes"] for state in result["directories"]))
        (self.root / "scripts/check.py").write_bytes(b"changed")
        changed = python_compat.python_capabilities(str(self.root))
        self.assertNotEqual(result["files"], changed["files"])
        self.assertIn("scripts/check.py", changed["conflicts"][0])

    def test_missing_and_unverified_files_are_conflicts(self):
        (self.root / "scripts/projectcfg.py").unlink()
        result = python_compat.python_capabilities(str(self.root))
        self.assertIsNone(result["files"][1]["sha256"])
        self.assertIn("scripts/projectcfg.py", result["conflicts"][0])

    def test_original_release_ci_is_not_accepted(self):
        old_ci = b"""name: Template-Pr\xc3\xbcfung
on:
  push:
    branches: ["**"]
    tags: ["v*"]
  pull_request:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  template:
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, windows-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - uses: actions/setup-node@v4
        with:
          node-version: "24"
      - run: python scripts/check.py
      - run: python -m unittest discover -s .github/template-tests -v
"""
        self.assertEqual(hashlib.sha256(old_ci).hexdigest(),
                         "18a51ef1b44f6b7bb2347c289b2195a4e3744f910a40f3a0378cf03b2c8c0a21")
        (self.root / ".github/workflows/ci.yml").write_bytes(old_ci)
        result = python_compat.python_capabilities(str(self.root))
        self.assertEqual(len(result["conflicts"]), 1)
        self.assertIn(".github/workflows/ci.yml", result["conflicts"][0])

    def test_linked_directory_is_rejected(self):
        path = self.root / "scripts"
        renamed = self.root / "scripts-original"
        path.rename(renamed)
        try:
            path.symlink_to(renamed, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks not available on this platform")
        with self.assertRaises(PathSafetyError):
            python_compat.python_capabilities(str(self.root))

    @unittest.skipIf(os.name == "nt", "POSIX mode test")
    def test_permission_change_changes_fingerprint(self):
        result = python_compat.python_capabilities(str(self.root))
        path = self.root / "scripts/check.py"
        path.chmod(path.stat().st_mode ^ 0o100)
        changed = python_compat.python_capabilities(str(self.root))
        self.assertNotEqual(result["files"][0]["attributes"], changed["files"][0]["attributes"])


if __name__ == "__main__":
    unittest.main()
