"""Installed CLI integration against two immutable public t0003 commits."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import sysconfig
import tempfile
import unittest


SOURCE = "https://github.com/maieuticus/t0003-ai-project-template.git"
COMPATIBLE = "6e8363a7ac7d99220d743eea077dcd5cefda9042"
RELEASE = "964de8538d19cefcb483faff38f10124615a9783"
ROOT = Path(__file__).resolve().parents[1]


class T0003Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="t0004-integration-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.base = Path(cls.temp.name)
        cls.git_env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1",
                           GIT_CONFIG_GLOBAL=os.devnull)
        for key in ("GIT_CONFIG_COUNT", "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
                    "GIT_ASKPASS", "SSH_ASKPASS", "GH_TOKEN", "GITHUB_TOKEN", "T0004_REPO_TOKEN"):
            cls.git_env.pop(key, None)
        mirror = os.environ.get("T0004_T0003_MIRROR")
        source = SOURCE
        if mirror:
            path = Path(mirror)
            if not path.is_absolute() or not path.is_dir():
                raise ValueError("T0004_T0003_MIRROR must be an absolute local Git repository path")
            source = str(path.resolve())
        cls.source = cls.base / "source.git"
        cls.git("init", "--quiet", "--bare", str(cls.source), cwd=cls.base)
        cls.git("-C", str(cls.source), "fetch", "--quiet", "--no-tags", "--depth=1", source,
                f"{COMPATIBLE}:refs/heads/compatible", f"{RELEASE}:refs/heads/release",
                cwd=cls.base)
        for commit in (COMPATIBLE, RELEASE):
            resolved = cls.git("-C", str(cls.source), "rev-parse", f"{commit}^{{commit}}",
                               cwd=cls.base).stdout.strip()
            if resolved != commit:
                raise AssertionError("Fetched t0003 commit does not match the pinned commit")
        executable = "t0004-generator.exe" if os.name == "nt" else "t0004-generator"
        cls.cli_path = Path(sysconfig.get_path("scripts")) / executable
        if not cls.cli_path.is_file():
            raise RuntimeError("Install the generator into the test Python environment first")

    @classmethod
    def git(cls, *args, cwd):
        return subprocess.run(["git", *args], cwd=cwd, env=cls.git_env, check=True,
                              capture_output=True, text=True, encoding="utf-8")

    def setUp(self):
        self.temp_project = tempfile.TemporaryDirectory(prefix="case-", dir=self.base)
        self.addCleanup(self.temp_project.cleanup)
        self.case = Path(self.temp_project.name)
        self.project = self.case / "project"
        self.data = self.case / "private-data"
        self.plan_file = self.case / "plan.json"
        self.env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1",
                        T0004_BACKUP_HOME=str(self.data))
        for key in ("PYTHONPATH", "PYTHONHOME", "GH_TOKEN", "GITHUB_TOKEN", "T0004_REPO_TOKEN"):
            self.env.pop(key, None)
        self.checkout(COMPATIBLE)

    def checkout(self, commit):
        self.git("-c", "core.autocrlf=false", "clone", "--quiet", "--no-checkout",
                 "--no-hardlinks", str(self.source), str(self.project), cwd=self.case)
        self.git("-c", "core.autocrlf=false", "checkout", "--quiet", "--detach", commit,
                 cwd=self.project)
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=self.project).stdout.strip(), commit)
        self.assertEqual(self.git("status", "--porcelain", cwd=self.project).stdout, "")

    def run_command(self, command, *, cwd=None, env=None, expected=0):
        result = subprocess.run(command, cwd=cwd or self.project, env=env or self.env,
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def cli(self, *args, expected=0):
        return self.run_command([str(self.cli_path), *args], expected=expected)

    def files(self):
        return {p.relative_to(self.project).as_posix(): p.read_bytes()
                for p in self.project.rglob("*")
                if p.is_file() and ".git" not in p.relative_to(self.project).parts}

    def file_states(self):
        return {name: (content, (self.project / name).stat().st_mtime_ns,
                       stat.S_IMODE((self.project / name).stat().st_mode))
                for name, content in self.files().items()}

    def plan(self, *, module=True, expected=0):
        args = ["new"]
        if module:
            args.extend(["--module", "python"])
        result = self.cli(*args, "--json", expected=expected)
        plan = json.loads(result.stdout)
        self.plan_file.write_text(result.stdout, encoding="utf-8")
        return plan

    def apply(self, plan, *, expected=0, confirm=None):
        return self.cli("apply", "--plan", str(self.plan_file),
                        "--confirm", confirm or plan["plan_id"], expected=expected)

    def snapshot(self, plan, before):
        backup = self.data / "t0004-generator" / "backups" / (".t0004-backup-" + plan["backup"]["id"])
        self.assertTrue(backup.is_dir())
        self.assertFalse(backup.is_relative_to(self.project))
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o700)
        manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest, {"format": 3, "plan": plan})
        for index, operation in enumerate(plan["operations"]):
            original = backup / f"original-{index:02d}"
            if operation["action"] == "modify":
                self.assertEqual(original.read_bytes(), before[operation["path"]])
                if os.name != "nt":
                    self.assertEqual(stat.S_IMODE(original.stat().st_mode), 0o600)
            else:
                self.assertNotIn(operation["path"], before)
                self.assertFalse(original.exists())
        return backup

    def test_complete_installed_cli_cycle(self):
        before = self.files()
        before_states = self.file_states()
        self.assertEqual(self.cli("version").stdout.strip(), (ROOT / "VERSION").read_text().strip())
        plan = self.plan()
        self.assertEqual(before_states, self.file_states())
        self.assertEqual(plan["format"], 4)
        self.assertEqual(plan["module"], "python")
        self.assertEqual(plan["conflicts"], [])
        self.assertRegex(plan["plan_id"], r"^[0-9a-f]{64}$")
        identity = {k: v for k, v in plan.items() if k not in {"plan_id", "read_only"}}
        encoded = json.dumps(identity, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")
        self.assertEqual(plan["plan_id"], hashlib.sha256(encoded).hexdigest())
        self.apply(plan, expected=1, confirm="0" * 64)
        self.assertEqual(before, self.files())
        self.assertFalse(self.data.exists())
        applied = self.apply(plan)
        self.assertIn(plan["backup"]["id"], applied.stdout)
        expected_paths = {"pyproject.toml", "src/project_app/__init__.py",
                          "src/project_app/__main__.py", "src/project_app/app.py",
                          "tests/test_project_app.py", "docs/PYTHON.md"}
        self.assertTrue(expected_paths.issubset(self.files()))
        self.assertEqual({item["path"] for item in plan["operations"]},
                         expected_paths | {"config/project.yaml", ".github/workflows/ci.yml"})
        backup = self.snapshot(plan, before)

        app_env = dict(self.env, PYTHONPATH=str(self.project / "src"))
        app = self.run_command([sys.executable, "-m", "project_app"], env=app_env)
        self.assertEqual(app.stdout.strip(), "Hello from project_app!")
        tests = self.run_command([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
        self.assertIn("test_main", tests.stderr)
        checked = self.run_command([sys.executable, "scripts/check.py"])
        self.assertIn("test_main", checked.stderr)
        self.assertIn("Dokumentlinks", checked.stdout)

        # Install from a copy so build artifacts cannot mask the byte-exact restore.
        install_source = self.case / "install-source"
        shutil.copytree(self.project, install_source, ignore=shutil.ignore_patterns(".git"))
        installed = self.case / "installed"
        self.run_command([sys.executable, "-m", "pip", "install", "--no-deps", "--target",
                          str(installed), "."], cwd=install_source)
        installed_app = self.run_command([sys.executable, "-m", "project_app"], cwd=self.case,
                                         env=dict(self.env, PYTHONPATH=str(installed)))
        self.assertEqual(installed_app.stdout.strip(), "Hello from project_app!")

        after = self.files()
        noop = self.plan()
        self.assertEqual(noop["operations"], [])
        self.assertIsNone(noop["backup"])
        self.assertEqual(after, self.files())
        self.assertEqual([p for p in backup.parent.iterdir()], [backup])
        self.cli("restore", "--backup", plan["backup"]["id"])
        self.assertEqual(before, self.files())
        for name in expected_paths:
            self.assertFalse((self.project / name).exists())
        self.assertEqual(self.git("status", "--porcelain", "--untracked-files=all", cwd=self.project).stdout, "")
        again = self.plan()
        self.assertTrue(again["operations"])
        self.assertEqual(before, self.files())

    def test_stale_plan_refuses_changed_config_and_new_application(self):
        plan = self.plan()
        config = self.project / "config/project.yaml"
        original = config.read_bytes()
        config.write_bytes(original + b"\n# unrelated edit\n")
        before = self.files()
        self.apply(plan, expected=1)
        self.assertEqual(before, self.files())
        self.assertFalse(self.data.exists())
        config.write_bytes(original)
        plan = self.plan()
        application = self.project / "src/project_app/app.py"
        application.parent.mkdir(parents=True)
        application.write_bytes(b"existing application\n")
        before = self.files()
        self.apply(plan, expected=1)
        self.assertEqual(before, self.files())
        self.assertFalse(self.data.exists())

    def test_original_release_is_rejected(self):
        other = self.case / "old-project"
        self.project = other
        self.checkout(RELEASE)
        before = self.files()
        plan = self.plan(expected=1)
        self.assertEqual(plan["operations"], [])
        self.assertTrue(any("t0003" in item or "CI" in item for item in plan["conflicts"]))
        self.assertEqual(before, self.files())
        self.assertFalse(self.data.exists())

    def test_changed_contract_is_rejected_before_and_after_planning(self):
        for name in (".github/workflows/ci.yml", "scripts/check.py", "scripts/projectcfg.py"):
            with self.subTest(path=name):
                path = self.project / name
                original = path.read_bytes()
                plan = self.plan()
                path.write_bytes(original + b"\n# modified\n")
                changed = self.files()
                self.apply(plan, expected=1)
                self.assertEqual(changed, self.files())
                conflict = self.plan(expected=1)
                self.assertEqual(conflict["operations"], [])
                self.assertTrue(any(name in item for item in conflict["conflicts"]))
                self.assertFalse(self.data.exists())
                path.write_bytes(original)

    def test_tampered_plan_and_existing_application_are_rejected(self):
        before = self.files()
        plan = self.plan()
        modified = dict(plan)
        modified["operations"] = [dict(item) for item in plan["operations"]]
        modified["operations"][0]["after_sha256"] = "0" * 64
        self.plan_file.write_text(json.dumps(modified), encoding="utf-8")
        self.apply(plan, expected=1)
        self.assertEqual(before, self.files())
        application = self.project / "src/project_app/app.py"
        application.parent.mkdir(parents=True)
        application.write_bytes(b"existing application\n")
        changed = self.files()
        self.assertEqual(self.plan(expected=1)["operations"], [])
        self.assertEqual(changed, self.files())
        self.assertFalse(self.data.exists())

    def test_foreign_edit_blocks_restore_without_partial_writes(self):
        plan = self.plan()
        self.apply(plan)
        app = self.project / "src/project_app/app.py"
        app.write_bytes(b"foreign edit\n")
        before = self.files()
        self.cli("restore", "--backup", plan["backup"]["id"], expected=1)
        self.assertEqual(before, self.files())
        self.assertEqual(app.read_bytes(), b"foreign edit\n")

    def test_private_snapshot_and_marker_do_not_enter_git(self):
        marker = "INTEGRATION_TEST_ONLY_NOT_A_CREDENTIAL"
        config = self.project / "config/project.yaml"
        config.write_bytes(config.read_bytes() + f"\n# {marker}\n".encode())
        before = self.files()
        plan = self.plan()
        self.assertNotIn(marker, self.plan_file.read_text(encoding="utf-8"))
        applied = self.apply(plan)
        self.assertNotIn(marker, applied.stdout + applied.stderr)
        backup = self.snapshot(plan, before)
        self.assertTrue(any(marker.encode() in p.read_bytes() for p in backup.glob("original-*")))
        candidates = self.git("ls-files", "--cached", "--others", "--exclude-standard",
                              cwd=self.project).stdout.splitlines()
        self.assertTrue(all(".t0004-backup-" not in name for name in candidates))
        self.assertNotIn(marker.encode(), self.git("show", "HEAD:config/project.yaml",
                                                  cwd=self.project).stdout.encode())
        self.assertNotIn(marker, self.git("show", ":config/project.yaml", cwd=self.project).stdout)
        self.assertEqual(self.git("diff", "--cached", "--name-only", cwd=self.project).stdout, "")
        self.cli("restore", "--backup", plan["backup"]["id"])
        self.assertEqual(before, self.files())

    def test_format_3_still_applies_and_restores(self):
        before = self.files()
        plan = self.plan(module=False)
        self.assertEqual(plan["format"], 3)
        self.apply(plan)
        self.assertNotEqual(before, self.files())
        noop = self.plan(module=False)
        self.assertEqual(noop["operations"], [])
        self.cli("restore", "--backup", plan["backup"]["id"])
        self.assertEqual(before, self.files())


if __name__ == "__main__":
    unittest.main()
