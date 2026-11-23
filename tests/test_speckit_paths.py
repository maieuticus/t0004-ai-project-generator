"""Regression tests for Spec Kit feature-path resolution."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")


@unittest.skipIf(os.name == "nt" or BASH is None, "requires a POSIX Bash environment")
class SpecKitPaths(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        shutil.copytree(ROOT / ".specify" / "scripts", self.root / ".specify" / "scripts")
        shutil.copytree(ROOT / ".specify" / "templates", self.root / ".specify" / "templates")
        self.relative = "specs/003 space 'quoted';$HOME"
        self.feature = self.root / self.relative
        self.env = os.environ.copy()
        for key in ("SPECIFY_INIT_DIR", "SPECIFY_FEATURE", "SPECIFY_FEATURE_DIRECTORY"):
            self.env.pop(key, None)
        self.env["SPECIFY_INIT_DIR"] = str(self.root)

    def run_script(self, name, *args, feature=None):
        env = self.env.copy()
        if feature is not None:
            env["SPECIFY_FEATURE_DIRECTORY"] = feature
        return subprocess.run(
            [BASH, str(self.root / ".specify" / "scripts" / "bash" / name), *args],
            cwd=self.root, env=env, capture_output=True, text=True, encoding="utf-8",
        )

    def test_paths_only_is_literal_and_does_not_persist_override(self):
        state = self.root / ".specify" / "feature.json"
        state.write_text('{"feature_directory":"specs/previous"}\n', encoding="utf-8")
        before = state.read_bytes()
        result = self.run_script("check-prerequisites.sh", "--paths-only", "--json",
                                 feature=self.relative)
        self.assertEqual(result.returncode, 0, result.stderr)
        paths = json.loads(result.stdout)
        self.assertEqual(paths["FEATURE_DIR"], str(self.feature))
        self.assertEqual(paths["BRANCH"], Path(self.relative).name)
        self.assertEqual(paths["FEATURE_SPEC"], str(self.feature / "spec.md"))
        self.assertEqual(state.read_bytes(), before)

    def test_setup_and_prerequisites_use_persisted_feature_without_overwriting_plan(self):
        result = self.run_script("setup-plan.sh", "--json", feature=self.relative)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["IMPL_PLAN"], str(self.feature / "plan.md"))
        state = self.root / ".specify" / "feature.json"
        self.assertEqual(json.loads(state.read_text(encoding="utf-8"))["feature_directory"],
                         self.relative)
        (self.feature / "plan.md").write_text("existing plan\n", encoding="utf-8")
        (self.feature / "spec.md").write_text("specification\n", encoding="utf-8")
        (self.feature / "tasks.md").write_text("tasks\n", encoding="utf-8")

        result = self.run_script("setup-plan.sh", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.feature / "plan.md").read_text(encoding="utf-8"), "existing plan\n")
        result = self.run_script("setup-tasks.sh", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["FEATURE_DIR"], str(self.feature))
        result = self.run_script("check-prerequisites.sh", "--json", "--require-spec",
                                 "--require-tasks", "--include-tasks")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["FEATURE_DIR"], str(self.feature))
        self.assertIn("tasks.md", json.loads(result.stdout)["AVAILABLE_DOCS"])

    def test_missing_feature_context_fails_explicitly(self):
        for script in ("setup-plan.sh", "setup-tasks.sh", "check-prerequisites.sh"):
            with self.subTest(script=script):
                result = self.run_script(script, "--json")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Feature directory not found", result.stderr)

    def test_existing_get_feature_paths_output_is_preserved(self):
        env = self.env.copy()
        env["SPECIFY_FEATURE_DIRECTORY"] = self.relative
        common = self.root / ".specify" / "scripts" / "bash" / "common.sh"
        result = subprocess.run(
            [BASH, "-c", 'source "$1"; get_feature_paths --no-persist', "bash", str(common)],
            cwd=self.root, env=env, capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = subprocess.run(
            [BASH, "-c", "printf 'FEATURE_DIR=%q\\n' \"$1\"", "bash", str(self.feature)],
            capture_output=True, text=True, encoding="utf-8", check=True,
        )
        self.assertIn(expected.stdout, result.stdout)
        self.assertFalse((self.root / ".specify" / "feature.json").exists())


if __name__ == "__main__":
    unittest.main()
