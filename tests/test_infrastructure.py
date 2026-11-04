"""Internal Docker Compose infrastructure state and transaction coverage."""

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

from test_typescript_module import TypeScriptModule

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from project_generator import infrastructure, installed_version, python_module, transaction
from project_generator.infrastructure_states import DOCKER_COMPOSE, docker_projection
from project_generator.module_states import CI_STATES


class DockerInfrastructure(unittest.TestCase):
    setUp = TypeScriptModule.setUp
    cli = TypeScriptModule.cli
    select = TypeScriptModule.select
    install = TypeScriptModule.install
    files = TypeScriptModule.files

    def select_docker(self):
        with mock.patch.dict(os.environ, {"T0004_BACKUP_HOME": str(self.base / "data")}):
            return infrastructure.infrastructure_plan_target(
                str(self.project), installed_version(), DOCKER_COMPOSE,
            )

    def install_docker(self):
        plan, changes = self.select_docker()
        self.assertEqual(plan["conflicts"], [])
        self.assertEqual(plan["format"], 4)
        self.assertEqual(plan["infrastructure"], DOCKER_COMPOSE)
        self.assertEqual(changes[0][0], "config/project.yaml")
        with mock.patch.dict(os.environ, {"T0004_BACKUP_HOME": str(self.base / "data")}):
            backup = infrastructure.apply_infrastructure(
                str(self.project), plan, plan["plan_id"], installed_version(), DOCKER_COMPOSE,
            )
        return plan, backup

    def assert_docker_state(self, modules):
        config = (self.project / "config/project.yaml").read_text(encoding="utf-8")
        expected_modules = [f"{module}@0.1.0" for module in ("python", "typescript", "java")
                            if module in modules]
        self.assertIn(f"modules: {json.dumps(expected_modules)}", config)
        self.assertIn('infrastructure: ["docker-compose@0.1.0"]', config)
        self.assertEqual((self.project / ".github/workflows/ci.yml").read_bytes(),
                         CI_STATES[frozenset(modules)])
        self.assertEqual(
            list(docker_projection(frozenset(modules))),
            [".dockerignore", "compose.yaml",
             *(f"Dockerfile.{module}" for module in ("python", "typescript", "java")
              if module in modules)],
        )
        for path in docker_projection(frozenset(modules)):
            self.assertFalse((self.project / path).exists(), path)

    def restore_all(self, plans):
        for backup in reversed(plans):
            result = self.cli("restore", "--backup", backup)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_docker_requires_an_installed_language_and_has_no_public_cli_selection(self):
        before = self.files()
        plan, changes = self.select_docker()
        self.assertEqual(changes, [])
        self.assertEqual(plan["operations"], [])
        self.assertTrue(any("mindestens ein installiertes Sprachmodul" in item
                            for item in plan["conflicts"]))
        self.assertEqual(before, self.files())
        result = self.cli("plan", "--module", "docker-compose", "--json")
        self.assertEqual(result.returncode, 2)

    def test_python_docker_java_is_deterministic_and_restores_in_reverse_order(self):
        subprocess.run(["git", "init", "--quiet"], cwd=self.project, check=True)
        subprocess.run(["git", "add", "."], cwd=self.project, check=True)
        index = (self.project / ".git/index").read_bytes()
        original = self.files()

        python = self.install("python")
        docker, docker_backup = self.install_docker()
        java = self.install("java")
        self.assert_docker_state({"python", "java"})
        self.assertEqual((self.project / ".git/index").read_bytes(), index)

        noop, changes = self.select_docker()
        self.assertEqual(noop["operations"], [])
        self.assertEqual(changes, [])
        self.assertIsNone(noop["backup"])
        self.assertEqual(
            noop["projection"],
            [".dockerignore", "compose.yaml", "Dockerfile.python", "Dockerfile.java"],
        )

        before_refusal = self.files()
        self.assertEqual(self.cli("restore", "--backup", python["backup"]["id"]).returncode, 1)
        self.assertEqual(before_refusal, self.files())
        self.restore_all([python["backup"]["id"], docker_backup, java["backup"]["id"]])
        self.assertEqual(self.files(), original)

    def test_java_docker_typescript_then_python_matches_the_known_final_state(self):
        original = self.files()
        java = self.install("java")
        _, docker_backup = self.install_docker()
        typescript = self.install("typescript")
        python = self.install("python")
        self.assert_docker_state({"python", "typescript", "java"})

        self.restore_all([
            java["backup"]["id"], docker_backup, typescript["backup"]["id"], python["backup"]["id"],
        ])
        self.assertEqual(self.files(), original)

    def test_python_typescript_docker_projects_the_known_state(self):
        original = self.files()
        python = self.install("python")
        typescript = self.install("typescript")
        docker, docker_backup = self.install_docker()
        self.assert_docker_state({"python", "typescript"})
        self.assertEqual(
            docker["projection"],
            [".dockerignore", "compose.yaml", "Dockerfile.python", "Dockerfile.typescript"],
        )
        self.restore_all([python["backup"]["id"], typescript["backup"]["id"], docker_backup])
        self.assertEqual(self.files(), original)

    def test_foreign_compose_projection_blocks_the_plan_and_snapshot_recheck(self):
        self.install("python")
        foreign = self.project / "compose.yaml"
        foreign.write_bytes(b"foreign")
        plan, changes = self.select_docker()
        self.assertEqual(changes, [])
        self.assertTrue(any("compose.yaml" in item for item in plan["conflicts"]))
        foreign.unlink()

        plan, _ = self.select_docker()
        original_config = (self.project / "config/project.yaml").read_bytes()
        real_progress = transaction._multi_progress

        def create_projection_after_snapshot(backup, progress):
            real_progress(backup, progress)
            foreign.write_bytes(b"foreign")

        with mock.patch.object(transaction, "_multi_progress", side_effect=create_projection_after_snapshot):
            with mock.patch.dict(os.environ, {"T0004_BACKUP_HOME": str(self.base / "data")}):
                with self.assertRaisesRegex(transaction.TransactionError, "Ziel wurde nicht geschrieben"):
                    infrastructure.apply_infrastructure(
                        str(self.project), plan, plan["plan_id"], installed_version(), DOCKER_COMPOSE,
                    )
        self.assertEqual((self.project / "config/project.yaml").read_bytes(), original_config)
        self.assertEqual(foreign.read_bytes(), b"foreign")

    def test_java_legacy_crlf_state_remains_accepted_by_docker_preconditions(self):
        real_files = python_module._files_for

        def legacy_files(module):
            files = dict(real_files(module))
            if module == "java":
                files["java/mvnw.cmd"] = files["java/mvnw.cmd"].replace(b"\n", b"\r\n")
            return files

        with mock.patch.dict(os.environ, {"T0004_BACKUP_HOME": str(self.base / "data")}):
            with mock.patch.object(python_module, "_files_for", side_effect=legacy_files):
                java, changes = python_module.module_plan_target(str(self.project), installed_version(), "java")
                transaction.apply_multi(
                    str(self.project), java, java["plan_id"], installed_version(), changes, module="java",
                )
        plan, docker_backup = self.install_docker()
        self.assertEqual(plan["conflicts"], [])
        wrapper = self.project / "java/mvnw.cmd"
        self.assertIn(b"\r\n", wrapper.read_bytes())
        wrapper.write_bytes(wrapper.read_bytes() + b"foreign\r\n")
        conflict, changes = self.select_docker()
        self.assertEqual(changes, [])
        self.assertTrue(conflict["conflicts"])
        wrapper.write_bytes(legacy_files("java")["java/mvnw.cmd"])
        self.restore_all([java["backup"]["id"], docker_backup])


if __name__ == "__main__":
    unittest.main()
