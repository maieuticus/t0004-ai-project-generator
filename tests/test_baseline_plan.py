"""Strategy B stays read-only and fails closed."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from project_generator.baseline_plan import FILES, PACKAGE, baseline_plan
from project_generator.config import ConfigurationError, load_metadata
from project_generator.migrate import analyze
from project_generator.plan import PathSafetyError, assess


class BaselinePlanTests(unittest.TestCase):
    def setUp(self):
        if not shutil.which("git"):
            self.skipTest("Git unavailable")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "core.autocrlf", "false")
        (self.root / "README.md").write_text("# Existing\n", encoding="utf-8")
        self.git("add", "README.md")
        self.git("commit", "-qm", "initial")

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)

    def plan(self, confirmation=None):
        return baseline_plan(str(self.root), "0.1.0", confirmation)

    def test_manifest_schema_and_separate_confirmation(self):
        for name, (_, digest) in FILES.items():
            self.assertEqual(hashlib.sha256((PACKAGE / name).read_bytes()).hexdigest(), digest)
        content = (PACKAGE / "config/project.yaml").read_bytes()
        metadata = load_metadata(content)
        self.assertEqual(metadata["template_origin"], "migration")
        self.assertIsNone(metadata["template_release"])
        self.assertTrue(assess(content, "0.1.0", [])[1])
        no = self.plan()
        yes = self.plan(FILES["AGENTS.md"][1])
        self.assertTrue(no["conflicts"])
        self.assertFalse(yes["conflicts"])
        self.assertNotEqual(no["plan_id"], yes["plan_id"])
        self.assertEqual(yes, self.plan(FILES["AGENTS.md"][1]))
        self.assertFalse(yes["executable"])
        self.assertEqual((self.root / "README.md").read_text(), "# Existing\n")
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), [".git", "README.md"])

    def test_invalid_origins_and_legacy_schema(self):
        data = (PACKAGE / "config/project.yaml").read_bytes()
        for altered in (data.replace(b"origin: migration", b"origin: null"),
                        data.replace(b"release: null", b"release: 0.1.0"),
                        data.replace(b"base_commit: 6e8363", b"base_commit: 7e8363"),
                        data.replace(b"  origin: migration\n", b"")):
            with self.subTest(altered=altered), self.assertRaises(ConfigurationError):
                load_metadata(altered)
        legacy = data.replace(b"release: null", b"release: 0.1.0").replace(b"  origin: migration\n", b"")
        self.assertIsNone(load_metadata(legacy)["template_origin"])

    def test_existing_paths_dirty_git_and_classification(self):
        (self.root / "config").mkdir()
        path = self.root / "config/project.yaml"
        path.write_bytes((PACKAGE / "config/project.yaml").read_bytes())
        plan = self.plan(FILES["AGENTS.md"][1])
        self.assertTrue(any("config/project.yaml" in c for c in plan["conflicts"]))
        self.assertTrue(any("Git-Status" in c for c in plan["conflicts"]))
        self.assertEqual(analyze(str(self.root))["facts"]["t0003_metadata"], "recognized_migration_baseline")

    def test_public_cli_nonexecutable_plan_and_static_check(self):
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"),
                   PYTHONDONTWRITEBYTECODE="1")
        cmd = [sys.executable, "-B", "-m", "project_generator"]
        result = subprocess.run(cmd + ["migrate", str(self.root), "--baseline", "--confirm-agents",
                                       FILES["AGENTS.md"][1], "--json"],
                                env=env, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        report = json.loads(result.stdout)
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = Path(tmp) / "plan.json"
            plan_path.write_text(result.stdout, encoding="utf-8")
            apply = subprocess.run(cmd + ["apply", str(self.root), "--plan", str(plan_path),
                                          "--confirm", report["plan_id"]],
                                   env=env, capture_output=True, text=True, encoding="utf-8")
            self.assertNotEqual(apply.returncode, 0)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), [".git", "README.md"])
        for name in FILES:
            dest = self.root / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes((PACKAGE / name).read_bytes())
        check = subprocess.run([sys.executable, "-B", str(self.root / "scripts/check.py"), "--static-only"],
                               cwd=self.root, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(check.returncode, 0, check.stderr)

    def test_symlink_and_oversized_readme_are_refused(self):
        (self.root / "README.md").write_bytes(b"x" * (1024 * 1024 + 1))
        with self.assertRaises(PathSafetyError):
            self.plan()
        (self.root / "README.md").unlink()
        try:
            (self.root / "README.md").symlink_to(PACKAGE / "AGENTS.md")
        except OSError:
            self.skipTest("symlink unavailable")
        with self.assertRaises(PathSafetyError):
            self.plan()

    def test_ignored_target_and_case_collision_are_conflicts(self):
        (self.root / ".gitignore").write_text("config/\n", encoding="utf-8")
        self.git("add", ".gitignore")
        self.git("commit", "-qm", "ignore")
        (self.root / "config").mkdir()
        (self.root / "config/project.yaml").write_text("existing", encoding="utf-8")
        report = self.plan(FILES["AGENTS.md"][1])
        self.assertEqual(report["git"]["untracked"], 0)
        self.assertTrue(any("config/project.yaml" in c for c in report["conflicts"]))
        (self.root / "agents.MD").write_text("existing", encoding="utf-8")
        self.assertTrue(any("Portabler Pfadkonflikt" in c for c in self.plan()["conflicts"]))

    def test_tampered_package_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "baseline"
            shutil.copytree(PACKAGE, copy)
            (copy / "AGENTS.md").write_text("tampered", encoding="utf-8")
            with mock.patch("project_generator.baseline_plan.PACKAGE", copy):
                with self.assertRaises(PathSafetyError):
                    self.plan()


if __name__ == "__main__":
    unittest.main()
