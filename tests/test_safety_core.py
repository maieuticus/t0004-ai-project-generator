"""CLI and safety-core tests using isolated project fixtures."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE_CONFIG = (ROOT / "config/project.yaml").read_text(encoding="utf-8")
sys.path.insert(0, str(ROOT / "src"))
from project_generator.plan import create_plan


class SafetyCoreCli(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "Projekt mit Leerzeichen"
        (self.project / "config").mkdir(parents=True)
        self.config = self.project / "config/project.yaml"
        self.config.write_text(SOURCE_CONFIG, encoding="utf-8")
        (self.project / "docs").mkdir()
        for name in ("README.md", "AGENTS.md", "docs/DV_KONZEPT.md", "docs/PROJECT_HANDOFF.md"):
            (self.project / name).write_text("fixture\n", encoding="utf-8")

    def run_cli(self, *args: str, path: str | None = None, encoding: str = "utf-8"):
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONDONTWRITEBYTECODE="1",
                   PYTHONIOENCODING=encoding)
        if path is not None:
            env["PATH"] = path
        return subprocess.run(
            [sys.executable, "-B", "-m", "project_generator", *args],
            cwd=self.project, env=env, capture_output=True, text=True, encoding="utf-8",
        )

    def change(self, before: str, after: str):
        text = self.config.read_text(encoding="utf-8")
        self.assertIn(before, text)
        self.config.write_text(text.replace(before, after), encoding="utf-8")

    def test_version_and_check(self):
        version = self.run_cli("version")
        self.assertEqual(version.returncode, 0, version.stderr)
        self.assertEqual(version.stdout.strip(), (ROOT / "VERSION").read_text(encoding="utf-8").strip())
        checked = self.run_cli("check", "--json")
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertTrue(json.loads(checked.stdout)["valid"])

    def test_text_output_is_utf8_with_non_utf8_environment(self):
        result = self.run_cli("check", encoding="cp1252")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Kompatibilität", result.stdout)

    def test_neutral_template_without_project_name_is_valid(self):
        self.change('name: "t0004-ai-project-generator"', 'name: ""')
        result = self.run_cli("plan", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_quoted_project_name_with_colon_is_valid(self):
        self.change('name: "t0004-ai-project-generator"', 'name: "Example: project"')
        result = self.run_cli("check")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_configuration_rejected_without_leaking_values(self):
        cases = [
            ("schema_version: 1", "schema_version: 2"),
            ("release: 0.1.0", "release: SECRET-INVALID-VALUE"),
            ("tool: null", "tool: secret-invalid-tool"),
            ("modules: []", "modules: not-json"),
            ("checks: []", 'checks:\n  - ["python", 42]'),
            ('name: "t0004-ai-project-generator"', 'name: "t0004"\n  name: "duplicate"'),
            ('name: "t0004-ai-project-generator"', 'name: "unterminated'),
            ('name: "t0004-ai-project-generator"', r'name: "bad\q"'),
            ("base_commit: null", "base_commit: [broken"),
        ]
        for before, after in cases:
            with self.subTest(before=before):
                self.config.write_text(SOURCE_CONFIG.replace(before, after), encoding="utf-8")
                for command in ("check", "plan"):
                    result = self.run_cli(command, "--json")
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertNotIn("SECRET-INVALID-VALUE", result.stdout + result.stderr)
                    self.assertNotIn("secret-invalid-tool", result.stdout + result.stderr)
                    self.assertNotIn("Traceback", result.stderr)

    def test_plan_is_reproducible_and_never_mutates_target(self):
        self.change('checks: []', 'checks:\n  - ["python", "-c", "write-secret-file"]')
        before = {p.relative_to(self.project): p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        first = self.run_cli("plan", "--json")
        second = self.run_cli("plan", str(self.project), "--json")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        plan = json.loads(first.stdout)
        self.assertTrue(plan["read_only"])
        self.assertEqual(plan["source_fingerprint"], hashlib.sha256(self.config.read_bytes()).hexdigest())
        self.assertRegex(plan["plan_id"], r"^[0-9a-f]{64}$")
        self.assertEqual(plan["operations"][0]["path"], "config/project.yaml")
        self.assertIn("- generator.version: null", plan["operations"][0]["diff"])
        self.assertNotIn("write-secret-file", first.stdout)
        after = {p.relative_to(self.project): p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_fingerprint_and_plan_id_change_when_config_changes(self):
        first = json.loads(self.run_cli("plan", "--json").stdout)
        self.config.write_text(self.config.read_text(encoding="utf-8") + "# comment\n", encoding="utf-8")
        second = json.loads(self.run_cli("plan", "--json").stdout)
        self.assertNotEqual(first["source_fingerprint"], second["source_fingerprint"])
        self.assertNotEqual(first["plan_id"], second["plan_id"])

    def test_secret_values_never_appear_in_plan_or_errors(self):
        self.change("version: null\n  modules", "version: null  # secret-example-value\n  modules")
        for command in ("check", "plan"):
            result = self.run_cli(command, "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("secret-example-value", result.stdout + result.stderr)

    def test_identical_bytes_across_project_paths_produce_same_plan(self):
        other = Path(self.temp.name) / "another"
        (other / "config").mkdir(parents=True)
        (other / "docs").mkdir()
        (other / "config/project.yaml").write_bytes(self.config.read_bytes())
        for name in ("README.md", "AGENTS.md", "docs/DV_KONZEPT.md", "docs/PROJECT_HANDOFF.md"):
            (other / name).write_text("different content\n", encoding="utf-8")
        first = self.run_cli("plan", "--json")
        second = self.run_cli("plan", str(other), "--json")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(json.loads(first.stdout), json.loads(second.stdout))

    def test_fixed_plan_id_is_platform_independent(self):
        fixture = (
            'schema_version: 1\nproject:\n  name: ""\ntemplate:\n'
            '  source: https://github.com/maieuticus/t0003-ai-project-template\n'
            '  release: 0.1.0\n  base_commit: null\n  last_update_check: null\n'
            'sdd:\n  tool: null\n  version: null\ngenerator:\n  version: null\n'
            '  modules: []\nchecks: []\n'
        ).encode("utf-8")
        self.assertEqual(create_plan(fixture, "0.1.0", [])["plan_id"],
                         "9d8559c49181667cd1c9777cec2f2f7cc32c7b3debacb356cba443586818a5b2")

    def test_conflicts_exit_nonzero_and_never_propose_upgrade(self):
        for before, after in [
            ("release: 0.1.0", "release: 9.0.0"),
            ("version: null\n  modules", 'version: "9.0.0"\n  modules'),
            ("modules: []", 'modules: ["module@1.2.3"]'),
        ]:
            with self.subTest(after=after):
                self.config.write_text(SOURCE_CONFIG.replace(before, after), encoding="utf-8")
                for command in ("check", "plan"):
                    result = self.run_cli(command, "--json")
                    self.assertEqual(result.returncode, 1, result.stderr)
                    report = json.loads(result.stdout)
                    self.assertTrue(report["conflicts"])
                    if command == "plan":
                        self.assertEqual(report["operations"], [])

    def test_recorded_current_version_needs_no_operation(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.change("version: null\n  modules", f'version: "{version}"\n  modules')
        plan = json.loads(self.run_cli("plan", "--json").stdout)
        self.assertEqual(plan["operations"], [])
        self.assertEqual(plan["conflicts"], [])

    def test_missing_prerequisite_is_a_conflict(self):
        (self.project / "README.md").unlink()
        for command in ("check", "plan"):
            result = self.run_cli(command, "--json")
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("README.md", json.loads(result.stdout)["conflicts"][0])

    def test_check_reports_missing_git_without_needing_it_for_plan(self):
        self.assertEqual(self.run_cli("check", path="").returncode, 1)
        self.assertEqual(self.run_cli("plan", path="").returncode, 0)

    def test_sdd_selection_reports_unverified_integration(self):
        self.change("tool: null", 'tool: "speckit"')
        self.change("  version: null\ngenerator:", '  version: "1.0.7"\ngenerator:')
        result = self.run_cli("check", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("nicht geprüft", json.loads(result.stdout)["warnings"][0])

    def test_unsafe_and_missing_paths(self):
        for target in (str(Path(self.project.anchor)), "../other", "missing"):
            result = self.run_cli("plan", target)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_config_symlink_and_linked_config_directory_rejected(self):
        target = Path(self.temp.name) / "outside.yaml"
        target.write_text(SOURCE_CONFIG, encoding="utf-8")
        self.config.unlink()
        try:
            self.config.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks not available on this platform")
        result = self.run_cli("plan")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.config.unlink()
        (self.project / "config").rmdir()
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        (outside / "project.yaml").write_text(SOURCE_CONFIG, encoding="utf-8")
        (self.project / "config").symlink_to(outside, target_is_directory=True)
        self.assertEqual(self.run_cli("plan").returncode, 2)

    def test_bad_arguments_and_non_utf8_config(self):
        self.assertEqual(self.run_cli("apply").returncode, 2)
        self.config.write_bytes(b"\xff")
        result = self.run_cli("check")
        self.assertEqual(result.returncode, 2)
        self.assertIn("UTF-8", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
