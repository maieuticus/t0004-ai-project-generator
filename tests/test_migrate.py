"""Read-only migration inventory tests with isolated projects."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from project_generator import migrate


class MigrationAnalysis(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "project"
        self.project.mkdir()

    def write(self, name, content="fixture\n"):
        path = self.project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def cli(self, *args, cwd=None, extra_env=None):
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONDONTWRITEBYTECODE="1")
        if extra_env:
            env.update(extra_env)
        return subprocess.run([sys.executable, "-B", "-m", "project_generator", "migrate", *args],
                              cwd=cwd or self.project, env=env, capture_output=True, text=True,
                              encoding="utf-8")

    def report(self, *args):
        result = self.cli(*args, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.project, check=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)

    def init_git(self):
        if not shutil.which("git"):
            self.skipTest("Git unavailable")
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "maintenance.auto", "false")
        self.git("config", "gc.auto", "0")
        self.git("config", "core.autocrlf", "false")
        self.write("tracked.txt")
        self.git("add", "tracked.txt")
        self.git("commit", "-qm", "fixture")

    def snapshot(self):
        result = {}
        for path in self.project.rglob("*"):
            info = path.lstat()
            name = str(path.relative_to(self.project))
            if path.is_symlink():
                result[name] = ("link", os.readlink(path))
            elif path.is_file():
                result[name] = ("file", info.st_mode, info.st_mtime_ns, path.read_bytes())
            elif path.is_dir():
                result[name] = ("dir", info.st_mode, info.st_mtime_ns)
        return result

    def test_python_java_typescript_and_mixed_indicators(self):
        for name in ("src/main.py", "src/Main.java", "web/main.ts", "web/View.tsx",
                     "pyproject.toml", "pom.xml", "package.json", "tsconfig.json",
                     "README.md", "tests/test_main.py", ".github/workflows/ci.yml", "assets/logo.png"):
            self.write(name)
        report = self.report()
        self.assertEqual(report["report_version"], 1)
        self.assertEqual(report["kind"], "read_only_migration_analysis")
        self.assertEqual(report["indicators"]["languages"], ["Java", "Python", "TypeScript"])
        self.assertEqual(report["indicators"]["technologies"],
                         ["Maven", "Node.js", "Python packaging", "TypeScript configuration"])
        self.assertTrue(report["indicators"]["documentation"])
        self.assertTrue(report["indicators"]["tests"])
        self.assertTrue(report["indicators"]["ci_configuration"])
        self.assertTrue(report["indicators"]["assets"])
        self.assertEqual(report["facts"]["t0003_metadata"], "not_observed")
        self.assertEqual(report["facts"]["git"]["state"], "not_detected")
        self.assertEqual(set(report["strategies"]), {"A", "B"})
        self.assertNotIn("operations", report)
        text = self.cli()
        self.assertEqual(text.returncode, 0, text.stderr)
        for heading in ("Nachgewiesene Fakten", "Erkannte Hinweise", "Nicht untersuchte Bereiche",
                        "Strategievergleich", "Empfehlung und Unsicherheit"):
            self.assertIn(heading, text.stdout)

    def test_individual_language_projects(self):
        for language, name in (("Python", "app.py"), ("Java", "Main.java"), ("TypeScript", "app.ts")):
            with self.subTest(language=language):
                path = self.write(f"{language}/{name}")
                report = self.report(str(path.parent))
                self.assertEqual(report["indicators"]["languages"], [language])

    def test_windows_uses_stat_instead_of_direntry_device_number(self):
        self.write("item.py")
        with os.scandir(self.project) as entries:
            entry = next(entries)
            with mock.patch.object(migrate.os, "name", "nt"):
                info = migrate._entry_stat(entry, self.project)
        self.assertEqual(info.st_dev, self.project.stat().st_dev)

    def test_metadata_present_valid_invalid_and_unverified(self):
        config = (ROOT / "config/project.yaml").read_text(encoding="utf-8")
        path = self.write("config/project.yaml", config)
        report = self.report()
        self.assertEqual(report["facts"]["t0003_metadata"], "recognized_supported")
        self.assertEqual(report["facts"]["t0003_details"],
                         {"generator_version_configured": False, "modules_configured": False,
                          "sdd_configured": False})
        path.write_text(config.replace("release: 0.1.0", "release: 9.0.0"), encoding="utf-8")
        report = self.report()
        self.assertEqual(report["facts"]["t0003_metadata"], "recognized_unverified_version")
        self.assertTrue(report["conflicts"])
        path.write_text("arbitrary: project config\n", encoding="utf-8")
        report = self.report()
        self.assertEqual(report["facts"]["t0003_metadata"], "not_recognized")
        self.assertEqual(report["recommendation"]["strategy"], "offen")
        self.assertTrue(report["conflicts"])

    def test_git_status_changes_and_no_writes(self):
        self.init_git()
        self.write("tracked.txt", "modified\n")
        self.write("untracked-secret.txt", "SECRET_VALUE\n")
        before = self.snapshot()
        report = self.report()
        after = self.snapshot()
        self.assertEqual(before, after)
        self.assertEqual(report["facts"]["git"],
                         {"state": "available", "tracked_changes": 1, "untracked": 1})
        self.assertTrue(report["conflicts"])

    def test_git_renames_and_missing_git_are_reported_without_names(self):
        self.init_git()
        self.git("mv", "tracked.txt", "private-rename.txt")
        report = self.report()
        self.assertEqual(report["facts"]["git"]["tracked_changes"], 1)
        self.assertNotIn("private-rename", json.dumps(report))
        with mock.patch.object(migrate.shutil, "which", return_value=None):
            report = migrate.analyze(str(self.project))
        self.assertEqual(report["facts"]["git"]["state"], "unavailable")

    def test_no_names_values_environment_or_git_diagnostics_leak(self):
        self.init_git()
        secret = "PRIVATE_EXAMPLE_4a7b3"
        self.write(f"{secret}.py", secret)
        self.write("config/project.yaml", "invalid: " + secret)
        self.write("README.md", secret)
        self.write(".gitignore", secret)
        for args in ((), ("--json",)):
            result = self.cli(*args, extra_env={"MIGRATE_SECRET_FIXTURE": secret})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(secret, result.stdout + result.stderr)
        invalid = self.cli(str(self.project / secret))
        self.assertEqual(invalid.returncode, 2)
        self.assertNotIn(secret, invalid.stdout + invalid.stderr)

    def test_excluded_directories_and_symlinks_are_not_followed(self):
        self.write("node_modules/hidden.java")
        self.write("dist/hidden.ts")
        self.write("src/main.py")
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        (outside / "outside.rs").write_text("fixture", encoding="utf-8")
        try:
            (self.project / "linked").symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            pass
        report = self.report()
        self.assertEqual(report["indicators"]["languages"], ["Python"])
        self.assertEqual(report["facts"]["structure"]["excluded_directories"], 2)
        self.assertTrue(any("ausgeschlossen" in item for item in report["analysis_limits"]))
        if (self.project / "linked").is_symlink():
            self.assertGreater(report["facts"]["structure"]["symlinks_or_special"], 0)
            result = self.cli(str(self.project / "linked"))
            self.assertEqual(result.returncode, 2)

    def test_limited_entries_depth_and_unreadable_directory(self):
        for index in range(12):
            self.write(f"dir{index}/item.py")
        self.write("deep/one/two/three/main.java")
        with mock.patch.object(migrate, "MAX_ENTRIES", 5):
            report = migrate.analyze(str(self.project))
        self.assertEqual(report["facts"]["observed_entries"], 5)
        self.assertTrue(any("Anzahl" in limit for limit in report["analysis_limits"]))
        self.assertEqual(report["recommendation"]["strategy"], "offen")
        with mock.patch.object(migrate, "MAX_DEPTH", 1):
            report = migrate.analyze(str(self.project))
        self.assertTrue(any("Verzeichnistiefe" in limit for limit in report["analysis_limits"]))
        original = os.scandir

        def denied(path):
            if Path(path).name == "deep":
                raise PermissionError("secret diagnostic")
            return original(path)

        with mock.patch.object(migrate.os, "supports_fd", set()):
            with mock.patch.object(migrate.os, "scandir", side_effect=denied):
                report = migrate.analyze(str(self.project))
        self.assertTrue(any("nicht lesbar" in limit for limit in report["analysis_limits"]))
        self.assertNotIn("secret diagnostic", json.dumps(report))

    def test_unreadable_or_oversized_metadata(self):
        path = self.write("config/project.yaml", "a" * (migrate.MAX_CONFIG_BYTES + 1))
        self.assertEqual(self.report()["facts"]["t0003_metadata"], "unreadable_or_unsupported")
        path.write_text("x" * (migrate.MAX_METADATA_LINE_BYTES + 1), encoding="utf-8")
        self.assertEqual(self.report()["facts"]["t0003_metadata"], "unreadable_or_unsupported")
        path.write_text("#\n" * (migrate.MAX_METADATA_LINES + 1), encoding="utf-8")
        self.assertEqual(self.report()["facts"]["t0003_metadata"], "unreadable_or_unsupported")
        path.write_text("fixture", encoding="utf-8")
        with mock.patch.object(migrate.os, "supports_fd", set()):
            with mock.patch.object(migrate.os, "open", side_effect=PermissionError("private error")):
                report = migrate.analyze(str(self.project))
        self.assertEqual(report["facts"]["t0003_metadata"], "unreadable_or_unsupported")
        self.assertNotIn("private error", json.dumps(report))

    def test_git_fsmonitor_is_not_executed_and_environment_is_ignored(self):
        self.init_git()
        sentinel = self.project / "fsmonitor-ran"
        script = self.write("fsmonitor-test", "#!/bin/sh\necho invoked > fsmonitor-ran\n")
        script.chmod(0o755)
        self.git("config", "core.fsmonitor", "./fsmonitor-test")
        result = self.cli("--json", extra_env={"GIT_CONFIG_COUNT": "1",
                                               "GIT_CONFIG_KEY_0": "core.fsmonitor",
                                               "GIT_CONFIG_VALUE_0": "./fsmonitor-test"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["facts"]["git"]["state"], "available")
        self.assertFalse(sentinel.exists())

    def test_git_unavailable_and_worktree_git_file_are_explicit(self):
        self.write(".git", "gitdir: ../sensitive")
        report = self.report()
        self.assertEqual(report["facts"]["git"]["state"], "unavailable")
        self.assertTrue(any("Git-Status nicht verfügbar" in limit for limit in report["analysis_limits"]))
        self.assertNotIn("sensitive", json.dumps(report))

    def test_git_indirection_partial_clone_and_output_limit_are_not_used(self):
        self.init_git()
        self.write("untracked-file-with-a-long-name.txt")
        with mock.patch.object(migrate, "MAX_GIT_OUTPUT", 8):
            report = migrate.analyze(str(self.project))
        self.assertEqual(report["facts"]["git"]["state"], "unavailable")
        self.git("config", "remote.origin.promisor", "true")
        self.assertEqual(self.report()["facts"]["git"]["state"], "unavailable")
        self.git("config", "--unset", "remote.origin.promisor")
        self.git("config", "include.path", "../external-config")
        self.assertEqual(self.report()["facts"]["git"]["state"], "unavailable")
        self.git("config", "--unset", "include.path")
        self.write(".git/objects/info/alternates", "../outside\n")
        self.assertEqual(self.report()["facts"]["git"]["state"], "unavailable")

    def test_git_custom_clean_filter_never_runs(self):
        self.init_git()
        self.write(".gitattributes", "tracked.txt filter=fixture\n")
        self.git("add", ".gitattributes")
        self.git("commit", "-qm", "attributes")
        script = self.write("filter-test", "#!/bin/sh\necho invoked > filter-ran\ncat\n")
        script.chmod(0o755)
        self.git("config", "filter.fixture.clean", "./filter-test")
        self.write("tracked.txt", "modified\n")
        report = self.report()
        self.assertEqual(report["facts"]["git"]["state"], "unavailable")
        self.assertFalse((self.project / "filter-ran").exists())

    def test_git_excludes_dependency_directories_and_symlinks(self):
        self.init_git()
        self.write("node_modules/tracked.txt")
        self.git("add", "node_modules/tracked.txt")
        self.git("commit", "-qm", "tracked dependency")
        self.write("node_modules/tracked.txt", "modified\n")
        self.write("node_modules/ignored-by-inventory.txt")
        self.write("visible.txt")
        report = self.report()
        self.assertEqual(report["facts"]["git"]["state"], "available")
        self.assertEqual(report["facts"]["git"]["untracked"], 1)
        self.assertEqual(report["facts"]["git"]["tracked_changes"], 0)

    def test_special_files_are_not_opened(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFOs not available")
        os.mkfifo(self.project / "private-fifo")
        report = self.report()
        self.assertEqual(report["facts"]["structure"]["symlinks_or_special"], 1)
        self.assertTrue(any("Spezialdateien" in limit for limit in report["analysis_limits"]))

    def test_symlink_swap_is_not_followed_during_posix_scan(self):
        if not (os.scandir in os.supports_fd and os.open in os.supports_dir_fd
                and hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY")):
            self.skipTest("descriptor-relative scan not available")
        self.write("config/project.yaml", (ROOT / "config/project.yaml").read_text(encoding="utf-8"))
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        (outside / "project.yaml").write_text("private fixture", encoding="utf-8")
        original_open = os.open
        swapped = False

        def swapping_open(path, flags, *args, **kwargs):
            nonlocal swapped
            if path == "config" and kwargs.get("dir_fd") is not None and not swapped:
                swapped = True
                (self.project / "config").rename(self.project / "moved")
                (self.project / "config").symlink_to(outside, target_is_directory=True)
            return original_open(path, flags, *args, **kwargs)

        with mock.patch.object(migrate.os, "open", side_effect=swapping_open) as open_mock:
            with mock.patch.object(migrate.os, "supports_dir_fd", {open_mock}):
                report = migrate.analyze(str(self.project))
        self.assertTrue(swapped)
        self.assertEqual(report["facts"]["t0003_metadata"], "not_observed")
        self.assertTrue(any("nicht lesbar" in item for item in report["analysis_limits"]))

    def test_invalid_source_errors_are_sanitized(self):
        result = self.cli("../PRIVATE_EXAMPLE")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("PRIVATE_EXAMPLE", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        result = self.cli("--json=PRIVATE_EXAMPLE")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("PRIVATE_EXAMPLE", result.stderr)


if __name__ == "__main__":
    unittest.main()
