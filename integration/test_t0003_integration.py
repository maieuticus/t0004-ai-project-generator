"""Installed CLI integration against two immutable public t0003 commits."""

import hashlib
import contextlib
import errno
import io
import itertools
from importlib import resources
import json
import os
from pathlib import Path
import shutil
import site
import stat
import subprocess
import sys
import sysconfig
import tempfile
import unittest
from unittest import mock


SOURCE = "https://github.com/maieuticus/t0003-ai-project-template.git"
COMPATIBLE = "6e8363a7ac7d99220d743eea077dcd5cefda9042"
RELEASE = "964de8538d19cefcb483faff38f10124615a9783"
ROOT = Path(__file__).resolve().parents[1]


class T0003Integration(unittest.TestCase):
    def docker_install(self, selection):
        result = self.cli("plan", *selection, "--json")
        plan = json.loads(result.stdout)
        self.assertFalse(plan["conflicts"])
        self.plan_file.write_text(result.stdout, encoding="utf-8")
        self.apply(plan)
        return plan

    def docker_java_setup(self):
        self.docker_install(("--module", "python"))
        docker = self.docker_install(("--infrastructure", "docker-compose"))
        result = self.cli("plan", "--module", "java", "--json")
        plan = json.loads(result.stdout)
        self.plan_file.write_text(result.stdout, encoding="utf-8")
        return docker, plan

    def assert_docker_refused(self, *args):
        before, index = self.files(), (self.project / ".git/index").read_bytes()
        result = self.cli(*args, expected=1)
        self.assertIn("Konflikt:", result.stderr)
        self.assertEqual(before, self.files())
        self.assertEqual(index, (self.project / ".git/index").read_bytes())
        return result

    def docker_inprocess_apply(self, plan, hook, callback):
        # Invoke the public CLI entry point in-process solely for deterministic fault injection.
        from project_generator import cli, transaction
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(transaction, hook, side_effect=callback):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = cli.main(["apply", str(self.project), "--plan", str(self.plan_file),
                                 "--confirm", plan["plan_id"]])
        self.assertEqual(code, 1, stderr.getvalue())
        self.assertIn("Konflikt:", stderr.getvalue())
        return stderr.getvalue()

    def test_docker_security_foreign_compose_before_install(self):
        self.docker_install(("--module", "python"))
        compose = self.project / "compose.yaml"
        compose.write_bytes(b"foreign compose\n")
        before, index = self.files(), (self.project / ".git/index").read_bytes()
        result = self.cli("plan", "--infrastructure", "docker-compose", "--json", expected=1)
        self.assertTrue(any("compose.yaml" in item for item in json.loads(result.stdout)["conflicts"]))
        self.assertEqual(before, self.files())
        self.assertEqual(index, (self.project / ".git/index").read_bytes())

    def test_docker_security_stale_plan_and_attributes(self):
        _, plan = self.docker_java_setup()
        compose = self.project / "compose.yaml"
        original = compose.read_bytes()
        compose.write_bytes(b"foreign compose\n")
        self.assert_docker_refused("apply", "--plan", str(self.plan_file), "--confirm", plan["plan_id"])
        compose.write_bytes(original)
        dockerfile = self.project / "Dockerfile.python"
        mode = stat.S_IMODE(dockerfile.stat().st_mode)
        try:
            dockerfile.chmod(mode & ~stat.S_IWRITE)
            self.assert_docker_refused("apply", "--plan", str(self.plan_file), "--confirm", plan["plan_id"])
        finally:
            dockerfile.chmod(mode)

    def test_docker_security_plan_and_metadata_tampering(self):
        _, plan = self.docker_java_setup()
        self.assert_docker_refused("apply", "--plan", str(self.plan_file), "--confirm", "0" * 64)
        for field in ("plan_id", "after_sha256"):
            with self.subTest(field=field):
                altered = json.loads(json.dumps(plan))
                if field == "plan_id":
                    altered[field] = "0" * 64
                else:
                    next(op for op in altered["operations"] if op["path"] == "compose.yaml")[field] = "0" * 64
                self.plan_file.write_text(json.dumps(altered), encoding="utf-8")
                self.assert_docker_refused("apply", "--plan", str(self.plan_file), "--confirm", plan["plan_id"])
        self.plan_file.write_text(json.dumps(plan), encoding="utf-8")
        config = self.project / "config/project.yaml"
        original = config.read_bytes()
        for old, new in ((b'"docker-compose@0.1.0"', b'"foreign@0.1.0"'),
                         (b'"python@0.1.0"', b'"typescript@0.1.0"')):
            with self.subTest(metadata=old):
                config.write_bytes(original.replace(old, new))
                before, index = self.files(), (self.project / ".git/index").read_bytes()
                result = self.cli("apply", "--plan", str(self.plan_file), "--confirm", plan["plan_id"], expected=1)
                self.assertIn("Konflikt:", result.stderr)
                self.assertEqual(before, self.files())
                self.assertEqual(index, (self.project / ".git/index").read_bytes())
        config.write_bytes(original)

    def test_docker_security_snapshot_recheck_before_write(self):
        _, plan = self.docker_java_setup()
        from project_generator import transaction
        compose = self.project / "compose.yaml"
        before, index = self.files(), (self.project / ".git/index").read_bytes()
        real = transaction._multi_progress

        def inject(backup, progress):
            real(backup, progress)
            compose.write_bytes(b"foreign after snapshot\n")

        error = self.docker_inprocess_apply(plan, "_multi_progress", inject)
        self.assertIn("Ziel wurde nicht geschrieben", error)
        before["compose.yaml"] = b"foreign after snapshot\n"
        self.assertEqual(before, self.files())
        self.assertEqual(index, (self.project / ".git/index").read_bytes())

    def test_docker_security_restore_manifest_original_and_dependencies(self):
        docker, java = self.docker_java_setup()
        self.apply(java)
        self.assert_docker_refused("restore", "--backup", docker["backup"]["id"])
        backup = self.data / "t0004-generator" / "backups" / (".t0004-backup-" + java["backup"]["id"])
        manifest = backup / "manifest.json"
        original_index = next(i for i, op in enumerate(java["operations"]) if op["path"] == "compose.yaml")
        original = backup / f"original-{original_index:02d}"
        for damaged in (manifest, original):
            content = damaged.read_bytes()
            damaged.write_bytes(b"tampered")
            self.assert_docker_refused("restore", "--backup", java["backup"]["id"])
            damaged.write_bytes(content)
        for name in ("compose.yaml", "Dockerfile.java", "docs/DOCKER.md"):
            path = self.project / name
            content = path.read_bytes()
            path.write_bytes(b"foreign\n")
            self.assert_docker_refused("restore", "--backup", java["backup"]["id"])
            path.write_bytes(content)
        self.cli("restore", "--backup", java["backup"]["id"])
        workflow = self.project / ".github/workflows/docker.yml"
        content = workflow.read_bytes()
        workflow.write_bytes(b"foreign\n")
        self.assert_docker_refused("restore", "--backup", docker["backup"]["id"])
        workflow.write_bytes(content)
        self.cli("restore", "--backup", docker["backup"]["id"])

    def test_docker_security_partial_transaction_recovery(self):
        _, plan = self.docker_java_setup()
        from project_generator import transaction
        before, index = self.files(), (self.project / ".git/index").read_bytes()
        real = transaction._multi_create
        calls = []

        def fail_second(path, content, opened):
            calls.append(path)
            if len(calls) == 2:
                raise OSError(errno.ENOSPC, "injected failure")
            return real(path, content, opened)

        error = self.docker_inprocess_apply(plan, "_multi_create", fail_second)
        self.assertIn(plan["backup"]["id"], error)
        self.assertGreaterEqual(len(calls), 2)
        self.assertNotEqual(before, self.files())
        self.assertEqual(index, (self.project / ".git/index").read_bytes())
        partial = calls[0]
        written = partial.read_bytes()
        partial.write_bytes(b"foreign after partial apply\n")
        self.assert_docker_refused("restore", "--backup", plan["backup"]["id"])
        partial.write_bytes(written)
        self.cli("restore", "--backup", plan["backup"]["id"])
        self.assertEqual(before, self.files())
        self.assertEqual(index, (self.project / ".git/index").read_bytes())

    def test_installed_docker_compose_update_and_reverse_restore(self):
        original = self.files()
        index = (self.project / ".git/index").read_bytes()
        python = self.plan()
        self.apply(python)
        result = self.cli("plan", "--infrastructure", "docker-compose", "--json")
        docker = json.loads(result.stdout)
        self.plan_file.write_text(result.stdout, encoding="utf-8")
        self.apply(docker)
        compose = self.project / "compose.yaml"
        self.assertIn(b"app-python:", compose.read_bytes())
        self.assertNotIn(b"app-java:", compose.read_bytes())
        result = self.cli("plan", "--module", "java", "--json")
        java = json.loads(result.stdout)
        self.plan_file.write_text(result.stdout, encoding="utf-8")
        self.apply(java)
        self.assertIn(b"app-java:", compose.read_bytes())
        self.assertTrue((self.project / "Dockerfile.java").is_file())
        self.assertEqual((self.project / ".git/index").read_bytes(), index)
        self.cli("restore", "--backup", docker["backup"]["id"], expected=1)
        for plan in (java, docker, python):
            self.cli("restore", "--backup", plan["backup"]["id"])
        self.assertEqual(self.files(), original)

    def test_strategy_b_package_provenance_and_read_only_cli(self):
        old = self.case / "old-baseline"
        old.mkdir()
        self.git("init", "--quiet", str(old), cwd=self.case)
        self.git("config", "user.name", "Fixture", cwd=old)
        self.git("config", "user.email", "fixture@example.invalid", cwd=old)
        self.git("config", "core.autocrlf", "false", cwd=old)
        (old / "README.md").write_bytes(b"# Existing\n")
        self.git("add", "README.md", cwd=old)
        self.git("commit", "--quiet", "-m", "initial", cwd=old)
        index = (old / ".git/index").read_bytes()
        preview = self.cli("migrate", str(old), "--baseline", "--json", expected=1)
        first = json.loads(preview.stdout)
        agents = next(op for op in first["operations"] if op["path"] == "AGENTS.md")
        confirmed = self.cli("migrate", str(old), "--baseline", "--confirm-agents",
                             agents["after_sha256"], "--json")
        plan = json.loads(confirmed.stdout)
        self.assertFalse(plan["conflicts"])
        self.assertFalse(plan["executable"])
        self.assertEqual(plan["base_commit"], COMPATIBLE)
        for operation in plan["operations"]:
            blob = subprocess.run(["git", "--git-dir", str(self.source), "show",
                                   f"{COMPATIBLE}:{operation['path']}"], cwd=self.case,
                                  env=self.git_env, check=True, capture_output=True).stdout
            self.assertEqual(hashlib.sha256(blob).hexdigest(), operation["source_sha256"])
        self.assertEqual((old / ".git/index").read_bytes(), index)
        self.assertEqual(sorted(p.name for p in old.iterdir()), [".git", "README.md"])

    def test_strategy_a_read_only_plan_against_real_t0003(self):
        old = self.case / "old-project"
        (old / "src").mkdir(parents=True)
        (old / "src/example.py").write_text("print('private fixture')\n", encoding="utf-8")
        self.git("init", "--quiet", str(old), cwd=self.case)
        self.git("-C", str(old), "add", "src/example.py", cwd=self.case)
        source_index = (old / ".git/index").read_bytes()
        target_index = (self.project / ".git/index").read_bytes()
        before = self.file_states()
        args = ("migrate", str(old), "--destination", str(self.project),
                "--file", "src/example.py", "--json")
        first = self.cli(*args)
        self.assertEqual(first.stdout, self.cli(*args).stdout)
        report = json.loads(first.stdout)
        self.assertFalse(report["executable"])
        self.assertEqual(report["operations"][0]["path"], "src/example.py")
        self.assertNotIn("private fixture", first.stdout)
        self.assertEqual(before, self.file_states())
        self.assertEqual(source_index, (old / ".git/index").read_bytes())
        self.assertEqual(target_index, (self.project / ".git/index").read_bytes())
        self.assertEqual((old / "src/example.py").read_text(encoding="utf-8"), "print('private fixture')\n")

    def test_strategy_a_apply_restore_against_real_t0003(self):
        old = self.case / "old-project"
        (old / "src").mkdir(parents=True)
        (old / "src/example.py").write_bytes(b"example\r\n")
        self.git("init", "--quiet", str(old), cwd=self.case)
        self.git("-C", str(old), "add", ".", cwd=self.case)
        source_index = (old / ".git/index").read_bytes()
        target_index = (self.project / ".git/index").read_bytes()
        before = self.files()
        result = self.cli("migrate", str(old), "--destination", str(self.project),
                          "--file", "src/example.py", "--json")
        plan = json.loads(result.stdout)
        self.plan_file.write_text(result.stdout, encoding="utf-8")
        applied = self.cli("apply", "--source", str(old), "--plan", str(self.plan_file),
                           "--confirm", plan["plan_id"])
        backup_id = applied.stdout.split("Backup-ID: ")[1].splitlines()[0]
        self.assertEqual((self.project / "src/example.py").read_bytes(), b"example\r\n")
        self.cli("apply", "--source", str(old), "--plan", str(self.plan_file),
                 "--confirm", plan["plan_id"], expected=1)
        self.cli("restore", "--backup", backup_id)
        self.assertEqual(before, self.files())
        self.assertEqual(source_index, (old / ".git/index").read_bytes())
        self.assertEqual(target_index, (self.project / ".git/index").read_bytes())
        self.assertEqual((old / "src/example.py").read_bytes(), b"example\r\n")

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
        if not cls.cli_path.is_file() and site.USER_BASE:
            user_scripts = Path(site.USER_BASE) / ("Scripts" if os.name == "nt" else "bin") / executable
            if user_scripts.is_file():
                cls.cli_path = user_scripts
        if not cls.cli_path.is_file() and not os.environ.get("T0004_TEST_CLI_MODULE"):
            raise RuntimeError("Install the generator into the test Python environment first")
        cls.cli_command = ([sys.executable, "-m", "project_generator"]
                           if os.environ.get("T0004_TEST_CLI_MODULE") else [str(cls.cli_path)])

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
        return self.run_command([*self.cli_command, *args], expected=expected)

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
        result = self.cli("plan", "--module", "typescript", "--json", expected=1)
        plan = json.loads(result.stdout)
        self.assertEqual(plan["operations"], [])
        self.assertTrue(plan["conflicts"])
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

    def test_packaged_java_starter_in_t0003_copy(self):
        """Exercise the installed Java resources without exposing a public module."""
        source = resources.files("project_generator").joinpath("templates", "java")
        names = (".gitignore", "pom.xml", "mvnw", "mvnw.cmd",
                 ".mvn/wrapper/maven-wrapper.properties",
                 "src/main/java/org/example/app/App.java",
                 "src/test/java/org/example/app/AppTest.java", "docs/JAVA.md")
        copied = {}
        for name in names:
            destination = self.project / (name if name.startswith("docs/") else "java/" + name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            content = source.joinpath(*name.split("/")).read_bytes()
            destination.write_bytes(content)
            copied[destination] = content

        wrapper = self.project / "java" / ("mvnw.cmd" if os.name == "nt" else "mvnw")
        if os.name != "nt":
            installed_wrapper = source.joinpath("mvnw")
            self.assertTrue(os.access(installed_wrapper, os.X_OK), "installed wrapper lost its executable mode")
            shutil.copymode(installed_wrapper, wrapper)
            self.assertTrue(os.access(wrapper, os.X_OK))
        environment = dict(self.env, MAVEN_USER_HOME=str(self.case / "maven-home"))
        version = self.run_command(["java", "-version"], env=environment)
        self.assertIn('version "25', version.stdout + version.stderr)

        # An empty wrapper cache forces a download and checksum validation.
        properties = self.project / "java/.mvn/wrapper/maven-wrapper.properties"
        correct = properties.read_bytes()
        properties.write_bytes(correct.replace(b"0d7125e8", b"1d7125e8"))
        bad = subprocess.run([str(wrapper), "-v"], cwd=self.project / "java", env=environment,
                             capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertNotEqual(bad.returncode, 0, bad.stdout + bad.stderr)
        self.assertIn("SHA-256", bad.stdout + bad.stderr)
        properties.write_bytes(correct)
        result = self.run_command([str(wrapper), "-v"], cwd=self.project / "java", env=environment)
        self.assertIn("Apache Maven 3.9.11", result.stdout)

        # Exercise the real t0003 project-check subprocess contract.
        config = self.project / "config/project.yaml"
        content = config.read_text(encoding="utf-8")
        command = ["java/mvnw.cmd" if os.name == "nt" else "java/mvnw", "-f", "java/pom.xml", "verify"]
        self.assertIn("checks: []", content)
        config.write_text(content.replace("checks: []", "checks:\n  - " + json.dumps(command)), encoding="utf-8")
        result = self.run_command([sys.executable, "scripts/check.py"], env=environment)
        self.assertIn("BUILD SUCCESS", result.stdout)
        report = self.project / "java/target/surefire-reports/TEST-org.example.app.AppTest.xml"
        self.assertIn('tests="1"', report.read_text(encoding="utf-8"))
        example = self.run_command(["java", "-jar", "java/target/project-java-starter-0.1.0.jar"], env=environment)
        self.assertEqual(example.stdout.strip(), "Hello from project-java-starter!")
        self.assertEqual({path: path.read_bytes() for path in copied}, copied)

    def test_java_generated_wrapper_survives_git_normalization(self):
        result = self.cli("plan", "--module", "java", "--json")
        plan = json.loads(result.stdout)
        self.plan_file.write_text(result.stdout, encoding="utf-8")
        self.apply(plan)
        wrapper = self.project / "java/mvnw.cmd"
        content = wrapper.read_bytes()
        # Git's clean filter must not change bytes which future plans authenticate.
        normalized = subprocess.run(["git", "hash-object", "--path=java/mvnw.cmd", "--stdin"],
                                    input=content, cwd=self.project, env=self.git_env,
                                    check=True, capture_output=True).stdout.strip()
        raw = subprocess.run(["git", "hash-object", "--stdin"], input=content,
                             cwd=self.project, env=self.git_env,
                             check=True, capture_output=True).stdout.strip()
        self.assertEqual(normalized, raw, "Git normalizes the generated Java wrapper")

    def test_java_git_checkout_noop_and_restore(self):
        foreign = self.project / "foreign-user-file.txt"
        foreign.write_bytes(b"do not change\n")
        before = self.files()
        original_index = (self.project / ".git/index").read_bytes()
        result = self.cli("plan", "--module", "java", "--json")
        plan = json.loads(result.stdout)
        self.plan_file.write_text(result.stdout, encoding="utf-8")
        self.apply(plan)
        self.assertEqual(original_index, (self.project / ".git/index").read_bytes())
        wrapper = self.project / "java/mvnw.cmd"
        expected = wrapper.read_bytes()
        self.assertNotIn(b"\r", expected)
        self.git("config", "user.name", "Fixture", cwd=self.project)
        self.git("config", "user.email", "fixture@example.invalid", cwd=self.project)
        self.git("add", "--", ".github/workflows/ci.yml", "config/project.yaml", "docs/JAVA.md",
                 "java", "scripts/check_java.py", cwd=self.project)
        blob = subprocess.run(["git", "show", ":java/mvnw.cmd"], cwd=self.project,
                              env=self.git_env, check=True, capture_output=True).stdout
        self.assertEqual(hashlib.sha256(blob).digest(), hashlib.sha256(expected).digest())
        self.git("commit", "--quiet", "-m", "generated fixture", cwd=self.project)
        self.git("checkout", "--", "java/mvnw.cmd", cwd=self.project)
        self.assertEqual(wrapper.read_bytes(), expected)
        noop = json.loads(self.cli("plan", "--module", "java", "--json").stdout)
        self.assertEqual(noop["operations"], [])
        fresh = self.case / "fresh-checkout"
        self.git("-c", "core.autocrlf=false", "clone", "--quiet", "--no-hardlinks",
                 str(self.project), str(fresh), cwd=self.case)
        self.assertEqual((fresh / "java/mvnw.cmd").read_bytes(), expected)
        fresh_noop = json.loads(self.cli("plan", str(fresh), "--module", "java", "--json").stdout)
        self.assertEqual(fresh_noop["operations"], [])
        committed_index = (self.project / ".git/index").read_bytes()
        self.cli("restore", "--backup", plan["backup"]["id"])
        self.assertEqual(before, self.files())
        self.assertEqual(committed_index, (self.project / ".git/index").read_bytes())

    def test_java_module_installation_orders(self):
        self.java_module_matrix(runtime_checks=False)

    def test_java_module_runtime_matrix(self):
        self.java_module_matrix(runtime_checks=True)

    def java_module_matrix(self, *, runtime_checks):
        # The installed distribution supplies both the CLI and its packaged resources.
        orders = [("java",), ("python", "java"), ("typescript", "java")]
        orders += list(itertools.permutations(("python", "typescript", "java")))
        if runtime_checks:
            orders = orders[:4]
        states = {}
        for number, modules in enumerate(orders):
            with self.subTest(modules=modules):
                if number:
                    self.project = self.case / f"java-project-{number}"
                    self.checkout(COMPATIBLE)
                original = self.files()
                index = (self.project / ".git/index").read_bytes()
                plans = []
                for module in modules:
                    before = self.files()
                    result = self.cli("plan", "--module", module, "--json")
                    plan = json.loads(result.stdout)
                    self.assertEqual(before, self.files())
                    self.assertFalse(plan["conflicts"])
                    self.plan_file.write_text(result.stdout, encoding="utf-8")
                    self.apply(plan)
                    self.snapshot(plan, before)
                    for op in plan["operations"]:
                        self.assertEqual(hashlib.sha256((self.project / op["path"]).read_bytes()).hexdigest(),
                                         op["after_sha256"])
                    plans.append(plan)
                final = self.files()
                key = frozenset(modules)
                if key in states:
                    self.assertEqual(states[key], final)
                else:
                    states[key] = final
                for module in modules:
                    noop = json.loads(self.cli("plan", "--module", module, "--json").stdout)
                    self.assertEqual(noop["operations"], [])
                    self.assertIsNone(noop["backup"])
                # Runtime artifacts stay in a separate copy, so restore is byte-exact.
                if runtime_checks:
                    runtime = self.case / f"java-runtime-{number}"
                    shutil.copytree(self.project, runtime, ignore=shutil.ignore_patterns(".git"))
                    env = dict(self.env, MAVEN_USER_HOME=str(self.case / "maven-home"),
                               npm_config_cache=str(self.case / "npm-cache"))
                    if "typescript" in modules:
                        npm = "npm.cmd" if os.name == "nt" else "npm"
                        self.run_command([npm, "ci", "--ignore-scripts", "--prefix", "typescript",
                                          "--no-audit", "--no-fund"], cwd=runtime, env=env)
                        self.run_command([npm, "run", "build", "--prefix", "typescript"],
                                         cwd=runtime, env=env)
                        example = self.run_command([npm, "run", "start", "--prefix", "typescript"],
                                                   cwd=runtime, env=env)
                        self.assertIn("Hello from project-typescript-starter!", example.stdout)
                    if "python" in modules:
                        app = self.run_command([sys.executable, "-m", "project_app"], cwd=runtime,
                                               env=dict(env, PYTHONPATH=str(runtime / "src")))
                        self.assertEqual(app.stdout.strip(), "Hello from project_app!")
                    checked = self.run_command([sys.executable, "scripts/check.py"], cwd=runtime, env=env)
                    self.assertIn("BUILD SUCCESS", checked.stdout)
                    report = runtime / "java/target/surefire-reports/TEST-org.example.app.AppTest.xml"
                    self.assertIn('tests="1"', report.read_text(encoding="utf-8"))
                    jar = self.run_command(["java", "-jar", "java/target/project-java-starter-0.1.0.jar"],
                                           cwd=runtime, env=env)
                    self.assertEqual(jar.stdout.strip(), "Hello from project-java-starter!")
                if len(plans) > 1:
                    self.cli("restore", "--backup", plans[0]["backup"]["id"], expected=1)
                    self.assertEqual(final, self.files())
                for plan in reversed(plans):
                    self.cli("restore", "--backup", plan["backup"]["id"])
                self.assertEqual(original, self.files())
                self.assertEqual(index, (self.project / ".git/index").read_bytes())

    def test_public_java_apply_and_project_check(self):
        before = self.files()
        index = (self.project / ".git/index").read_bytes()
        result = self.cli("plan", "--module", "java", "--json")
        plan = json.loads(result.stdout)
        self.assertEqual(plan["format"], 4)
        self.assertEqual(before, self.files())
        self.plan_file.write_text(result.stdout, encoding="utf-8")
        self.apply(plan)
        self.snapshot(plan, before)
        if os.name != "nt":
            # Apply creates a regular non-executable file; the adapter invokes sh.
            self.assertFalse(stat.S_IMODE((self.project / "java/mvnw").stat().st_mode) & 0o111)
        environment = dict(self.env, MAVEN_USER_HOME=str(self.case / "maven-home"))
        checked = self.run_command([sys.executable, "scripts/check.py"], env=environment)
        self.assertIn("BUILD SUCCESS", checked.stdout)
        report = self.project / "java/target/surefire-reports/TEST-org.example.app.AppTest.xml"
        self.assertIn('tests="1"', report.read_text(encoding="utf-8"))
        example = self.run_command(["java", "-jar", "java/target/project-java-starter-0.1.0.jar"], env=environment)
        self.assertEqual(example.stdout.strip(), "Hello from project-java-starter!")
        self.cli("restore", "--backup", plan["backup"]["id"])
        self.assertTrue(report.is_file())
        self.assertEqual(index, (self.project / ".git/index").read_bytes())

    def test_packaged_typescript_starter_in_t0003_copy(self):
        """Exercise installed package data independently of the apply path."""
        source = resources.files("project_generator").joinpath("templates", "typescript")
        names = (
            ".gitignore", "package.json", "package-lock.json", "tsconfig.json",
            "src/app.ts", "src/main.ts", "test/app.test.mjs", "docs/TYPESCRIPT.md",
        )
        copied = {}
        for name in names:
            destination = self.project / (name if name.startswith("docs/") else "typescript/" + name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            content = source.joinpath(*name.split("/")).read_bytes()
            destination.write_bytes(content)
            copied[destination] = content
        npm = "npm.cmd" if os.name == "nt" else "npm"
        environment = dict(self.env, npm_config_cache=str(self.case / "npm-cache"))
        module = self.project / "typescript"
        node = self.run_command(["node", "--version"], cwd=module, env=environment)
        self.assertRegex(node.stdout.strip(), r"^v24\.")
        self.run_command([npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund"],
                         cwd=module, env=environment)
        self.run_command([npm, "run", "build"], cwd=module, env=environment)
        tested = self.run_command([npm, "test"], cwd=module, env=environment)
        self.assertRegex(tested.stdout, r"\bpass 2\b")
        example = self.run_command([npm, "run", "start"], cwd=module, env=environment)
        self.assertIn("Hello from project-typescript-starter!", example.stdout)
        self.assertEqual({path: path.read_bytes() for path in copied}, copied)

    def test_public_typescript_apply_and_project_check(self):
        before = self.files()
        result = self.cli("plan", "--module", "typescript", "--json")
        plan = json.loads(result.stdout)
        self.assertEqual(plan["format"], 4)
        self.assertEqual(plan["module"], "typescript")
        self.assertEqual(before, self.files())
        self.plan_file.write_text(result.stdout, encoding="utf-8")
        self.apply(plan)
        self.snapshot(plan, before)
        check_copy = self.case / "check-copy"
        shutil.copytree(self.project, check_copy, ignore=shutil.ignore_patterns(".git"))
        npm = "npm.cmd" if os.name == "nt" else "npm"
        environment = dict(self.env, npm_config_cache=str(self.case / "npm-cache"))
        node = self.run_command(["node", "--version"], cwd=check_copy, env=environment)
        self.assertRegex(node.stdout.strip(), r"^v24\.")
        self.run_command([npm, "ci", "--ignore-scripts", "--prefix", "typescript",
                          "--no-audit", "--no-fund"], cwd=check_copy, env=environment)
        checked = self.run_command([sys.executable, "scripts/check.py"], cwd=check_copy, env=environment)
        self.assertIn("pass 2", checked.stdout)
        self.cli("restore", "--backup", plan["backup"]["id"])
        self.assertEqual(before, self.files())

    def test_typescript_module_orders_restore_and_conflicts(self):
        combined = []
        for number, modules in enumerate((("typescript",), ("python", "typescript"),
                                          ("typescript", "python"))):
            with self.subTest(modules=modules):
                if number:
                    self.project = self.case / f"project-{number}"
                    self.checkout(COMPATIBLE)
                original = self.files()
                index = (self.project / ".git/index").read_bytes()
                plans = []
                for module in modules:
                    before = self.files()
                    self.cli("check", "--json")
                    result = self.cli("plan", "--module", module, "--json")
                    plan = json.loads(result.stdout)
                    self.assertEqual(before, self.files())
                    self.assertEqual(plan["conflicts"], [])
                    self.plan_file.write_text(result.stdout, encoding="utf-8")
                    self.apply(plan)
                    self.snapshot(plan, before)
                    for operation in plan["operations"]:
                        content = (self.project / operation["path"]).read_bytes()
                        self.assertEqual(hashlib.sha256(content).hexdigest(), operation["after_sha256"])
                    plans.append(plan)
                final = self.files()
                check_copy = self.case / f"runtime-{number}"
                shutil.copytree(self.project, check_copy, ignore=shutil.ignore_patterns(".git"))
                environment = dict(self.env, npm_config_cache=str(self.case / "npm-cache"))
                npm = "npm.cmd" if os.name == "nt" else "npm"
                node = self.run_command(["node", "--version"], cwd=check_copy, env=environment)
                self.assertRegex(node.stdout.strip(), r"^v24\.")
                self.run_command([npm, "ci", "--ignore-scripts", "--prefix", "typescript",
                                  "--no-audit", "--no-fund"], cwd=check_copy, env=environment)
                if "python" in modules:
                    self.run_command([sys.executable, "-m", "pip", "install", "--no-deps",
                                      "--target", str(self.case / f"installed-{number}"), "."],
                                     cwd=check_copy, env=environment)
                self.run_command([npm, "run", "build", "--prefix", "typescript"],
                                 cwd=check_copy, env=environment)
                self.run_command([npm, "test", "--prefix", "typescript"],
                                 cwd=check_copy, env=environment)
                example = self.run_command([npm, "run", "start", "--prefix", "typescript"],
                                           cwd=check_copy, env=environment)
                self.assertIn("Hello from project-typescript-starter!", example.stdout)
                self.run_command([sys.executable, "scripts/check.py"], cwd=check_copy, env=environment)
                if len(modules) == 2:
                    combined.append(final)
                    self.cli("restore", "--backup", plans[0]["backup"]["id"], expected=1)
                    self.assertEqual(final, self.files())
                for module in modules:
                    noop = json.loads(self.cli("plan", "--module", module, "--json").stdout)
                    self.assertEqual(noop["operations"], [])
                    self.assertIsNone(noop["backup"])
                for plan in reversed(plans):
                    self.cli("restore", "--backup", plan["backup"]["id"])
                self.assertEqual(original, self.files())
                self.assertEqual(index, (self.project / ".git/index").read_bytes())
        self.assertEqual(combined[0], combined[1])

    def test_typescript_stale_plan_and_damaged_snapshot_are_refused(self):
        result = self.cli("plan", "--module", "typescript", "--json")
        plan = json.loads(result.stdout)
        self.plan_file.write_text(result.stdout, encoding="utf-8")
        target = self.project / "scripts/check.py"
        original = target.read_bytes()
        target.write_bytes(original + b"\n# changed\n")
        changed = self.files()
        self.apply(plan, expected=1)
        self.assertEqual(changed, self.files())
        self.assertFalse(self.data.exists())
        target.write_bytes(original)
        result = self.cli("plan", "--module", "typescript", "--json")
        plan = json.loads(result.stdout)
        self.plan_file.write_text(result.stdout, encoding="utf-8")
        before = self.files()
        self.apply(plan)
        backup = self.snapshot(plan, before)
        after = self.files()
        manifest = backup / "manifest.json"
        manifest_bytes = manifest.read_bytes()
        manifest.write_bytes(b"corrupt")
        self.cli("restore", "--backup", plan["backup"]["id"], expected=1)
        self.assertEqual(after, self.files())
        manifest.write_bytes(manifest_bytes)
        original_file = next(backup.glob("original-*"))
        original_file.unlink()
        self.cli("restore", "--backup", plan["backup"]["id"], expected=1)
        self.assertEqual(after, self.files())


if __name__ == "__main__":
    unittest.main()
