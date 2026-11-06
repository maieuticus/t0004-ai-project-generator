"""Tests for the isolated private-template access boundary."""

import hashlib
import importlib.util
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from project_generator import module_states, python_compat


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class GitAccess(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.access = load_script("gh_access")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def git(self, *args: str, cwd: Path):
        return subprocess.run(
            ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, encoding="utf-8"
        )

    def test_error_categories_are_non_successful_and_redacted(self):
        cases = {
            "fatal: could not read Username for 'https://example.invalid': terminal prompts disabled": "missing",
            "remote: Your token has expired": "expired",
            "remote: Permission to example/template.git denied to user\nfatal: unable to access: 403": "forbidden",
            "fatal: repository 'https://example.invalid/missing.git/' not found (404)": "not_found",
            "fatal: Could not resolve host: example.invalid": "network",
            "fatal: unexpected ghp_abcdefghijklmnopqrstuvwxyz0123456789": "unknown",
        }
        for error, expected in cases.items():
            with self.subTest(expected=expected):
                result = self.access.classify_error(error)
                self.assertEqual(result.category, expected)
                self.assertFalse(result.success)
                self.assertNotIn("ghp_abcdefghijklmnopqrstuvwxyz0123456789", result.message)
                self.assertNotIn("compatible", result.message.lower())
                self.assertNotIn("current", result.message.lower())

    def test_fetch_uses_an_isolated_noninteractive_existing_helper(self):
        source = self.base / "source"
        source.mkdir()
        self.git("init", "--quiet", cwd=source)
        self.git("config", "user.name", "Fixture", cwd=source)
        self.git("config", "user.email", "fixture@example.invalid", cwd=source)
        (source / "file.txt").write_text("fixture\n", encoding="utf-8")
        self.git("add", "file.txt", cwd=source)
        self.git("commit", "--quiet", "-m", "fixture", cwd=source)
        expected = self.git("rev-parse", "HEAD", cwd=source).stdout.strip()

        destination = self.base / "destination.git"
        global_config = self.base / "global.gitconfig"
        global_config.write_text("[credential]\n\thelper = store\n", encoding="utf-8")
        inherited = {
            "PATH": os.environ["PATH"],
            "HOME": str(self.base / "home"),
            "GIT_CONFIG_GLOBAL": str(global_config),
            "GIT_CONFIG_NOSYSTEM": "0",
            "GIT_TERMINAL_PROMPT": "1",
            "GH_TOKEN": "ghp_abcdefghijklmnopqrstuvwxyz0123456789",
            "GITHUB_TOKEN": "ghp_abcdefghijklmnopqrstuvwxyz0123456789",
        }
        environment = self.access.git_environment(inherited)
        self.assertEqual(environment["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(environment["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertEqual(environment["GIT_CONFIG_GLOBAL"], os.devnull)
        self.assertNotIn("GH_TOKEN", environment)
        self.assertNotIn("GITHUB_TOKEN", environment)

        helper_directory = self.base / "helper"
        helper_directory.mkdir()
        sentinel = self.base / "credential-helper-called"
        helper = helper_directory / "credential_helper.py"
        helper.write_text(
            'from pathlib import Path\n'
            'import os\n'
            'Path(os.environ["GH_HELPER_SENTINEL"]).write_text("invoked", encoding="utf-8")\n'
            'print("username=fixture")\n'
            'print("password=synthetic")\n',
            encoding="utf-8",
        )
        def git_shell_path(path: Path) -> str:
            text = path.resolve().as_posix()
            return f"/{text[0].lower()}{text[2:]}" if os.name == "nt" and text[1:3] == ":/" else text

        helper_command = "!" + " ".join(
            shlex.quote(git_shell_path(path)) for path in (Path(sys.executable), helper)
        )
        helper_environment = dict(environment, GH_HELPER_SENTINEL=str(sentinel))
        helper_result = subprocess.run(
            ["git", "-c", f"credential.helper={helper_command}", "credential", "fill"],
            input="protocol=https\nhost=example.invalid\n\n",
            capture_output=True,
            check=True,
            env=helper_environment,
            text=True,
            encoding="utf-8",
        )
        self.assertTrue(sentinel.is_file())
        self.assertIn("username=fixture", helper_result.stdout)

        result = self.access.fetch_reference(source.as_posix(), destination, "HEAD", env=inherited)
        self.assertTrue(result.success, result.message)
        self.assertEqual(result.category, "ok")
        self.assertEqual(
            self.git("--git-dir", str(destination), "rev-parse", "FETCH_HEAD", cwd=self.base).stdout.strip(),
            expected,
        )
        self.assertFalse((destination / "config").read_text(encoding="utf-8").__contains__("remote "))
        self.assertEqual(global_config.read_text(encoding="utf-8"), "[credential]\n\thelper = store\n")
        command = self.access.fetch_command(source.as_posix(), destination, "HEAD")
        self.assertIn("credential.helper=!gh auth git-credential", command)
        self.assertFalse(any("ghp_" in part or "token" in part.lower() for part in command))

    def test_reference_status_reports_release_and_default_branch_drift_without_writing(self):
        compatible = self.access.COMPATIBLE_REFERENCE
        release = self.access.RELEASE_REFERENCE
        self.assertTrue(self.access.reference_status(compatible, compatible).compatible)
        self.assertFalse(self.access.reference_status(release, compatible).compatible)
        drift = self.access.reference_status(compatible, "different-commit")
        self.assertTrue(drift.compatible)
        self.assertTrue(drift.default_branch_drift)

    def test_compatibility_uses_known_files_metadata_and_ci_state_not_history(self):
        project = self.base / "generated-project"
        for name, digest in python_compat.VERIFIED_FILES.items():
            path = project / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if name == ".github/workflows/ci.yml":
                path.write_bytes(module_states.CI_STATES[frozenset()])
            elif name == "scripts/check.py":
                path.write_bytes((ROOT / name).read_bytes().replace(
                    b'"docs/DV_KONZEPT.md", "docs/PROJECT_HANDOFF.md", "docs/GENERATOR_CONTRACT.md",\n'
                    b'    "docs/SDD_QUICKSTART.md", "docs/QUICKSTART.md",',
                    b'"docs/DV_KONZEPT.md", "docs/PROJECT_HANDOFF.md", '
                    b'"docs/SDD_QUICKSTART.md", "docs/QUICKSTART.md",',
                ))
            else:
                path.write_bytes(
                    (ROOT / "src/project_generator/projectcfg.py").read_bytes().replace(
                        b"parents[2]", b"parents[1]"
                    )
                )
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
        (project / "config").mkdir()
        (project / "config/project.yaml").write_text(
            'schema_version: 1\ntemplate:\n  release: 0.1.0\n  base_commit: null\n',
            encoding="utf-8",
        )
        self.git("init", "--quiet", cwd=project)
        self.git("config", "user.name", "Fixture", cwd=project)
        self.git("config", "user.email", "fixture@example.invalid", cwd=project)
        self.git("add", ".", cwd=project)
        self.git("commit", "--quiet", "-m", "independent generated history", cwd=project)

        result = python_compat.python_capabilities(str(project))
        self.assertEqual(result["conflicts"], [])
        self.assertFalse((project / ".git" / "shallow").exists())
        self.assertEqual(self.access.reference_status(self.access.COMPATIBLE_REFERENCE,
                                                       self.access.COMPATIBLE_REFERENCE).compatible, True)
        self.assertEqual(self.access.reference_status(self.access.RELEASE_REFERENCE,
                                                       self.access.COMPATIBLE_REFERENCE).compatible, False)


if __name__ == "__main__":
    unittest.main()
