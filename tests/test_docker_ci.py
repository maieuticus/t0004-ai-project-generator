"""Tests for Docker CI's pinned t0003 fetch boundary."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import docker_ci


class DockerCiTemplateFetch(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / "source"
        self.source.mkdir()
        inherited = dict(os.environ, HOME=str(self.base / "home"),
                         USERPROFILE=str(self.base / "home"),
                         GH_CONFIG_DIR=str(self.base / "gh-config"))
        self.env = docker_ci.gh_access.git_environment(inherited)

    def git(self, *args: str, cwd: Path):
        return subprocess.run(
            ["git", *args], cwd=cwd, env=self.env, check=True, capture_output=True, text=True
        ).stdout.strip()

    def test_fetches_only_the_pinned_commit_then_checks_out_local_copy(self):
        self.git("init", "--quiet", cwd=self.source)
        self.git("config", "user.name", "Fixture", cwd=self.source)
        self.git("config", "user.email", "fixture@example.invalid", cwd=self.source)
        (self.source / "fixture.txt").write_text("pinned state\n", encoding="utf-8")
        self.git("add", ".", cwd=self.source)
        self.git("commit", "--quiet", "-m", "compatible base", cwd=self.source)
        pinned = self.git("rev-parse", "HEAD", cwd=self.source)
        self.git("checkout", "--quiet", "--orphan", "later", cwd=self.source)
        (self.source / "fixture.txt").write_text("default branch drift\n", encoding="utf-8")
        self.git("add", ".", cwd=self.source)
        self.git("commit", "--quiet", "-m", "drift", cwd=self.source)

        project = self.base / "project"
        with mock.patch.object(docker_ci, "COMMIT", pinned):
            docker_ci.checkout_template(self.base, project, str(self.source), self.env)

        self.assertEqual(self.git("rev-parse", "HEAD", cwd=project), pinned)
        self.assertEqual((project / "fixture.txt").read_text(encoding="utf-8"), "pinned state\n")
        config = (project / ".git/config").read_text(encoding="utf-8")
        self.assertNotIn("https://", config)
        self.assertNotIn("password", config.lower())
        self.assertTrue((self.base / "t0003-template.git").is_dir())


if __name__ == "__main__":
    unittest.main()
