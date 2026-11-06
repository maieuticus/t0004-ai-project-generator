"""Run the Docker CI checks against the local, capability-verified test fixture."""

from pathlib import Path
import shutil
import sys
import unittest
from unittest import mock

import test_python_module

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import docker_ci


class DockerFixtureCi(unittest.TestCase):
    setUp = test_python_module.PythonModule.setUp

    def test_docker_validation_on_local_fixture(self):
        config_only = "--config-only" in sys.argv

        def checkout_fixture(base, project, source, env):
            shutil.copytree(self.project, project)
            safe_env = docker_ci.gh_access.git_environment(env)
            docker_ci.run(["git", "init", "--quiet"], cwd=project, env=safe_env)
            docker_ci.run(["git", "add", "."], cwd=project, env=safe_env)
            docker_ci.run(
                ["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "--quiet", "-m", "Local Docker fixture"],
                cwd=project,
                env=safe_env,
            )

        args = ["docker_ci.py"] + (["--config-only"] if config_only else [])
        print("Docker validation uses a local fixture; pinned t0003 is not tested here.", flush=True)
        with (
            mock.patch.object(docker_ci, "checkout_template", side_effect=checkout_fixture),
            mock.patch.object(sys, "argv", args),
        ):
            docker_ci.main()


if __name__ == "__main__":
    config_only = "--config-only" in sys.argv
    sys.argv = [sys.argv[0]] + (["--config-only"] if config_only else [])
    unittest.main(argv=[sys.argv[0]], verbosity=2)
