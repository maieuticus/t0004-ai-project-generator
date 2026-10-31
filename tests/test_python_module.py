"""Public Python module planning, apply and recovery."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from project_generator import installed_version, python_compat, python_module, transaction

CI = b'''name: Template-Pr\xc3\xbcfung
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
      - if: github.repository == 'maieuticus/t0003-ai-project-template'
        run: python -m unittest discover -s .github/template-tests -v
'''


class PythonModule(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / "project"
        for directory in ("config", "docs", "scripts", ".github/workflows"):
            (self.project / directory).mkdir(parents=True, exist_ok=True)
        (self.project / "config/project.yaml").write_bytes((ROOT / "config/project.yaml").read_bytes())
        for name in ("README.md", "AGENTS.md", "docs/DV_KONZEPT.md", "docs/PROJECT_HANDOFF.md",
                     "docs/QUICKSTART.md", "docs/SDD_QUICKSTART.md"):
            (self.project / name).write_bytes(b"fixture\n")
        check = (ROOT / "scripts/check.py").read_bytes().replace(
            b'"docs/DV_KONZEPT.md", "docs/PROJECT_HANDOFF.md", "docs/GENERATOR_CONTRACT.md",\n'
            b'    "docs/SDD_QUICKSTART.md", "docs/QUICKSTART.md",',
            b'"docs/DV_KONZEPT.md", "docs/PROJECT_HANDOFF.md", "docs/SDD_QUICKSTART.md", "docs/QUICKSTART.md",',
        )
        parser = (ROOT / "src/project_generator/projectcfg.py").read_bytes().replace(
            b"parents[2]", b"parents[1]"
        )
        for name, content in {"scripts/check.py": check, "scripts/projectcfg.py": parser,
                              ".github/workflows/ci.yml": CI}.items():
            self.assertEqual(hashlib.sha256(content).hexdigest(), python_compat.VERIFIED_FILES[name])
            (self.project / name).write_bytes(content)
        self.env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONDONTWRITEBYTECODE="1",
                        T0004_BACKUP_HOME=str(self.base / "data"))
        self.plan_file = self.base / "plan.json"

    def cli(self, *args):
        return subprocess.run([sys.executable, "-B", "-m", "project_generator", *args],
                              cwd=self.project, env=self.env, capture_output=True, text=True,
                              encoding="utf-8")

    def plan(self, command="plan"):
        result = self.cli(command, "--module", "python", "--json")
        self.assertIn(result.returncode, (0, 1), result.stderr)
        return result, json.loads(result.stdout)

    def save_plan(self):
        result, plan = self.plan()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.plan_file.write_text(result.stdout, encoding="utf-8")
        return plan

    def apply(self, plan):
        return self.cli("apply", "--plan", str(self.plan_file), "--confirm", plan["plan_id"])

    def test_new_and_plan_apply_restore_and_noop(self):
        before = {path.relative_to(self.project): path.read_bytes()
                  for path in self.project.rglob("*") if path.is_file()}
        result, first = self.plan("new")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(first, self.save_plan())
        self.assertEqual(first["format"], 4)
        self.assertEqual(first["module"], "python")
        self.assertEqual(len(first["preconditions"]["files"]), 3)
        self.assertEqual(before, {path.relative_to(self.project): path.read_bytes()
                                  for path in self.project.rglob("*") if path.is_file()})
        applied = self.apply(first)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertEqual((self.project / "src/project_app/app.py").read_bytes(),
                         python_module.FILES["src/project_app/app.py"])
        self.assertIn('modules: ["python@0.1.0"]',
                      (self.project / "config/project.yaml").read_text(encoding="utf-8"))
        result, noop = self.plan()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(noop["operations"], [])
        self.assertIsNone(noop["backup"])
        restored = self.cli("restore", "--backup", first["backup"]["id"])
        self.assertEqual(restored.returncode, 0, restored.stderr)
        self.assertEqual(before, {path.relative_to(self.project): path.read_bytes()
                                  for path in self.project.rglob("*") if path.is_file()})

    def test_existing_or_changed_module_file_is_conflict(self):
        path = self.project / "pyproject.toml"
        path.write_text("foreign", encoding="utf-8")
        result, plan = self.plan()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(plan["operations"], [])
        self.assertIn("pyproject.toml", plan["conflicts"][0])
        self.assertEqual(path.read_text(encoding="utf-8"), "foreign")
        path.unlink()
        plan = self.save_plan()
        self.assertEqual(self.apply(plan).returncode, 0)
        path.write_text("user change", encoding="utf-8")
        result, plan = self.plan()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(plan["operations"], [])

    def test_changed_capability_rejects_stale_plan_without_writes(self):
        plan = self.save_plan()
        path = self.project / "scripts/check.py"
        path.write_bytes(path.read_bytes() + b"# user change\n")
        applied = self.apply(plan)
        self.assertEqual(applied.returncode, 1, applied.stderr)
        self.assertFalse((self.project / "pyproject.toml").exists())
        self.assertFalse((self.base / "data").exists())

    def test_snapshot_rechecks_capabilities_before_project_writes(self):
        patch = mock.patch.dict(os.environ, {"T0004_BACKUP_HOME": str(self.base / "data")})
        with patch:
            plan, changes = python_module.python_plan_target(str(self.project), installed_version())
            real_progress = transaction._multi_progress

            def edit_after_snapshot(backup, progress):
                real_progress(backup, progress)
                path = self.project / "scripts/projectcfg.py"
                path.write_bytes(path.read_bytes() + b"# user change\n")

            with mock.patch.object(transaction, "_multi_progress", side_effect=edit_after_snapshot):
                with self.assertRaisesRegex(transaction.TransactionError, "Ziel wurde nicht geschrieben"):
                    transaction.apply_multi(str(self.project), plan, plan["plan_id"], installed_version(),
                                            changes, module="python")
        self.assertFalse((self.project / "pyproject.toml").exists())

    def test_restore_refuses_foreign_change_to_any_generated_file(self):
        plan = self.save_plan()
        self.assertEqual(self.apply(plan).returncode, 0)
        path = self.project / "src/project_app/app.py"
        path.write_bytes(b"foreign")
        result = self.cli("restore", "--backup", plan["backup"]["id"])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(path.read_bytes(), b"foreign")
        self.assertTrue((self.project / "pyproject.toml").exists())


if __name__ == "__main__":
    unittest.main()
