"""Strategy A planning remains bounded, reproducible and read-only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

import test_python_module
from project_generator import migration_plan
from project_generator.plan import PathSafetyError


class MigrationPlan(unittest.TestCase):
    def setUp(self):
        test_python_module.PythonModule.setUp(self)
        self.source = self.base / "source"
        self.source.mkdir()
        self.write("src/app.py", "secret-value = 1\n")
        self.write("docs/guide.md", "guide\n")

    def write(self, name, content):
        path = self.source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def plan(self, files):
        return migration_plan.migration_plan(str(self.source), str(self.project), files, "0.1.0")

    def cli(self, *args):
        return subprocess.run([sys.executable, "-B", "-m", "project_generator", *args],
                              env=self.env, cwd=self.base, capture_output=True, text=True, encoding="utf-8")

    def test_deterministic_selection_and_nonexecutable_cli(self):
        first = self.plan(["src/app.py", "docs/guide.md"])
        self.assertEqual(first, self.plan(["docs/guide.md", "src/app.py"]))
        self.assertEqual([op["path"] for op in first["operations"]], ["docs/guide.md", "src/app.py"])
        self.assertFalse(first["executable"])
        self.assertNotIn("secret-value", json.dumps(first))
        self.write("src/app.py", "modified\n")
        self.assertNotEqual(first["plan_id"], self.plan(["src/app.py", "docs/guide.md"])["plan_id"])
        result = self.cli("migrate", str(self.source), "--destination", str(self.project),
                          "--file", "src/app.py", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(result.stdout)["operations"]), 1)
        self.plan_file.write_text(result.stdout, encoding="utf-8")
        refused = self.cli("apply", str(self.project), "--plan", str(self.plan_file),
                           "--confirm", json.loads(result.stdout)["plan_id"])
        self.assertNotEqual(refused.returncode, 0)

    def test_collision_and_incompatible_target(self):
        (self.project / "src").mkdir()
        (self.project / "src/app.py").write_text("existing", encoding="utf-8")
        report = self.plan(["src/app.py"])
        self.assertTrue(report["conflicts"])
        self.assertIsNotNone(report["operations"][0]["target"]["sha256"])
        (self.project / "scripts/check.py").write_text("changed", encoding="utf-8")
        self.assertTrue(any("Fähigkeiten" in c for c in self.plan(["docs/guide.md"])["conflicts"]))

    def test_unsafe_paths_and_bounds(self):
        for name in ("../x.py", "/x.py", "C:/x.py", ".git/x.py", "src/.env.py",
                     "node_modules/x.py", ".venv/x.py", "dist/x.py", "__pycache__/x.py",
                     "config/a.py", "requirements.txt", "settings.py", "src/a.exe"):
            with self.subTest(name=name), self.assertRaises(PathSafetyError):
                self.plan([name])
        with self.assertRaises(PathSafetyError):
            self.plan(["src/app.py"] * 33)
        with self.assertRaises(PathSafetyError):
            self.plan(["missing.py"])
        self.write("large.txt", "a" * (1024 * 1024 + 1))
        with self.assertRaises(PathSafetyError):
            self.plan(["large.txt"])
        (self.source / "binary.txt").write_bytes(b"\xff\x00")
        with self.assertRaises(PathSafetyError):
            self.plan(["binary.txt"])
        with self.assertRaises(PathSafetyError):
            migration_plan.migration_plan(str(self.source), str(self.source), ["src/app.py"], "0.1.0")
        with self.assertRaises(PathSafetyError):
            migration_plan.migration_plan(str(self.base), str(self.project), ["src/app.py"], "0.1.0")

    def test_symlink_file(self):
        link = self.source / "link.py"
        try:
            link.symlink_to(self.source / "src/app.py")
        except OSError:
            self.skipTest("Symlinks unavailable")
        with self.assertRaises(PathSafetyError):
            self.plan(["link.py"])

    def test_changed_file(self):
        actual = migration_plan._state
        calls = 0
        def changing(root, name, **kwargs):
            nonlocal calls
            calls += 1
            value = actual(root, name, **kwargs)
            if calls == 2:
                self.write("src/app.py", "changed\n")
            return value
        with mock.patch.object(migration_plan, "_state", side_effect=changing):
            with self.assertRaises(PathSafetyError):
                self.plan(["src/app.py"])

    def test_symlink_directory(self):
        try:
            (self.source / "alias").symlink_to(self.source / "src", target_is_directory=True)
        except OSError:
            self.skipTest("Directory symlinks unavailable")
        with self.assertRaises(PathSafetyError):
            self.plan(["alias/app.py"])

    @unittest.skipUnless(os.name == "nt", "Windows junction test")
    def test_windows_junction_rejected(self):
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(self.source / "alias"),
                                 str(self.source / "src")], capture_output=True)
        if result.returncode:
            self.skipTest("Junction creation unavailable")
        with self.assertRaises(PathSafetyError):
            self.plan(["alias/app.py"])

    def test_unreadable_source(self):
        real_open = os.open
        def deny_source(path, *args, **kwargs):
            if os.path.samefile(path, self.source / "src/app.py"):
                raise PermissionError
            return real_open(path, *args, **kwargs)
        with mock.patch.object(migration_plan.os, "open", side_effect=deny_source):
            with self.assertRaises(PermissionError):
                self.plan(["src/app.py"])

    def test_trees_and_git_index_unchanged(self):
        for root in (self.source, self.project):
            subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(root), "add", "."], check=True, capture_output=True)
        def snapshot(root):
            return {str(p.relative_to(root)): (p.stat().st_mtime_ns, p.read_bytes())
                    for p in root.rglob("*") if p.is_file()}
        before = [snapshot(root) for root in (self.source, self.project)]
        self.plan(["src/app.py", "docs/guide.md"])
        self.assertEqual(before, [snapshot(root) for root in (self.source, self.project)])
