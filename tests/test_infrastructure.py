"""Internal Docker Compose infrastructure state and transaction coverage."""

import json
import hashlib
import itertools
import os
import stat
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

from test_typescript_module import TypeScriptModule

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from project_generator import infrastructure, installed_version, python_module, transaction
from project_generator.infrastructure_states import (
    DOCKER_COMPOSE, POSTGRESQL, INFRASTRUCTURE, POSTGRESQL_PROJECTION, valid_infrastructure,
    docker_projection, docker_projection_with_docs, docker_projection_with_ci, known_docker_projection,
)
from project_generator.config import ConfigurationError, load_metadata
from project_generator.module_states import CI_STATES
from project_generator.docker_files import docker_files
from project_generator.postgresql_files import POSTGRES_GITIGNORES


class DockerInfrastructure(unittest.TestCase):
    setUp = TypeScriptModule.setUp
    cli = TypeScriptModule.cli
    select = TypeScriptModule.select
    install = TypeScriptModule.install
    files = TypeScriptModule.files

    def test_closed_infrastructure_states_and_dependencies(self):
        docker, postgres = INFRASTRUCTURE.values()
        for state in ([], [docker], [docker, postgres]):
            self.assertTrue(valid_infrastructure(state, ["python@0.1.0"]))
        for state, modules in (([postgres], ["python@0.1.0"]), ([docker], []),
                               ([docker, postgres], []), ([docker, docker], ["python"]),
                               ([docker, "unknown@0.1.0"], ["python"]),
                               ([postgres, docker], ["python"])):
            self.assertFalse(valid_infrastructure(state, modules))
        self.assertEqual(set(POSTGRESQL_PROJECTION), {"config/project.yaml", "compose.yaml",
            ".github/workflows/docker.yml", "docs/DOCKER.md", "docs/POSTGRESQL.md", ".gitignore"})

    def test_metadata_addition_preserves_state_and_rejects_invalid_input(self):
        self.install("python")
        content = (self.project / "config/project.yaml").read_bytes()
        with self.assertRaises(ConfigurationError):
            infrastructure._metadata_with_infrastructure(content, POSTGRESQL)
        docker = infrastructure._metadata_with_infrastructure(content, DOCKER_COMPOSE)
        both = infrastructure._metadata_with_infrastructure(docker, POSTGRESQL)
        self.assertEqual(load_metadata(both)["infrastructure"], list(INFRASTRUCTURE.values()))
        self.assertEqual(infrastructure._metadata_with_infrastructure(both, DOCKER_COMPOSE), both)
        malformed = docker.replace(b'"docker-compose@0.1.0"', b'"docker-compose@0.1.0", "unknown"')
        with self.assertRaises(ConfigurationError):
            infrastructure._metadata_with_infrastructure(malformed, POSTGRESQL)

    def test_unimplemented_postgresql_metadata_blocks_all_plans(self):
        self.install("python")
        self.install_docker()
        config = self.project / "config/project.yaml"
        config.write_bytes(infrastructure._metadata_with_infrastructure(config.read_bytes(), POSTGRESQL))
        before = self.files()
        for args in (("plan", "--json"), ("plan", "--module", "java", "--json"),
                     ("plan", "--infrastructure", "docker-compose", "--json")):
            result = self.cli(*args)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertTrue(json.loads(result.stdout)["conflicts"])
        self.assertEqual(self.files(), before)

    def test_public_docker_selection_apply_and_noop(self):
        self.install("python")
        result = self.cli("plan", "--infrastructure", "docker-compose", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.plan_file.write_text(json.dumps(plan), encoding="utf-8")
        applied = self.cli("apply", "--plan", str(self.plan_file), "--confirm", plan["plan_id"])
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assert_docker_state({"python"})
        result = self.cli("plan", "--infrastructure", "docker-compose", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["operations"], [])
        self.assertEqual(self.cli("restore", "--backup", plan["backup"]["id"]).returncode, 0)

    def test_public_no_language_unknown_infrastructure_and_foreign_dockerfile(self):
        result = self.cli("plan", "--infrastructure", "docker-compose", "--json")
        self.assertEqual(result.returncode, 1)
        self.assertTrue(json.loads(result.stdout)["conflicts"])
        self.assertEqual(self.cli("plan", "--infrastructure", "unknown").returncode, 2)
        self.install("python")
        path = self.project / "Dockerfile.python"
        path.write_bytes(b"foreign\n")
        result = self.cli("plan", "--infrastructure", "docker-compose", "--json")
        self.assertEqual(result.returncode, 1)
        self.assertTrue(any("Dockerfile.python" in c for c in json.loads(result.stdout)["conflicts"]))
        self.assertEqual(path.read_bytes(), b"foreign\n")

    def test_docker_restore_before_later_language_is_refused(self):
        self.install("python")
        _, docker_backup = self.install_docker()
        java = self.install("java")
        before = self.files()
        refused = self.cli("restore", "--backup", docker_backup)
        self.assertEqual(refused.returncode, 1)
        self.assertEqual(self.files(), before)
        self.restore_all([docker_backup, java["backup"]["id"]])

    def test_damaged_docker_snapshot_is_refused(self):
        self.install("python")
        _, backup = self.install_docker()
        with mock.patch.dict(os.environ, {"T0004_BACKUP_HOME": str(self.base / "data")}):
            store = transaction.backup_store(str(self.project))
            manifest = store / (".t0004-backup-" + backup) / "manifest.json"
            manifest.write_bytes(b"{}")
            before = self.files()
            with self.assertRaises(transaction.TransactionError):
                transaction.restore(str(self.project), backup)
            self.assertEqual(before, self.files())

    def test_workflow_conflicts_and_restore_are_protected(self):
        self.install("python")
        workflow = self.project / ".github/workflows/docker.yml"
        workflow.write_bytes(b"foreign\n")
        plan, changes = self.select_docker()
        self.assertFalse(changes)
        self.assertTrue(any("docker.yml" in item for item in plan["conflicts"]))
        workflow.unlink()
        _, backup = self.install_docker()
        generated = workflow.read_bytes()
        workflow.write_bytes(b"foreign\n")
        before = self.files()
        self.assertEqual(self.cli("restore", "--backup", backup).returncode, 1)
        self.assertEqual(before, self.files())
        workflow.write_bytes(generated)
        self.assertEqual(self.cli("restore", "--backup", backup).returncode, 0)
        self.assertFalse(workflow.exists())

    def test_historical_installation_without_workflow_is_not_modified(self):
        self.install("python")
        self.install_docker()
        workflow = self.project / ".github/workflows/docker.yml"
        workflow.unlink()
        before = self.files()
        plan, changes = self.select_docker()
        self.assertFalse(changes)
        self.assertTrue(any("docker.yml" in item for item in plan["conflicts"]))
        self.assertEqual(before, self.files())

    def test_all_language_subsets_and_installation_orders_converge(self):
        modules = ("python", "typescript", "java")
        original = self.files()
        for count in range(1, 4):
            for subset in itertools.combinations(modules, count):
                target = None
                for order in itertools.permutations((*subset, "docker")):
                    if order[0] == "docker":
                        continue
                    with self.subTest(order=order):
                        backups = []
                        for name in order:
                            if name == "docker":
                                _, backup = self.install_docker()
                            else:
                                backup = self.install(name)["backup"]["id"]
                            backups.append(backup)
                        self.assert_docker_state(set(subset))
                        current = self.files()
                        if target is None:
                            target = current
                        else:
                            self.assertEqual(current, target)
                        self.restore_all(backups)
                        self.assertEqual(self.files(), original)

    def test_projections_are_closed_and_old_snapshots_keep_their_meaning(self):
        from itertools import combinations
        for count in range(1, 4):
            for names in combinations(("python", "typescript", "java"), count):
                old = list(docker_projection(frozenset(names)))
                new = list(docker_projection_with_docs(frozenset(names)))
                self.assertEqual(new, old + ["docs/DOCKER.md"])
                self.assertTrue(known_docker_projection(old))
                self.assertTrue(known_docker_projection(new))
                self.assertTrue(known_docker_projection(list(docker_projection_with_ci(frozenset(names)))))
                self.assertFalse(known_docker_projection(new + ["docs/foreign.md"]))

    def test_foreign_compose_blocks_later_language_plan(self):
        self.install("python")
        self.install_docker()
        (self.project / "compose.yaml").write_bytes(b"foreign\n")
        with mock.patch.dict(os.environ, {"T0004_BACKUP_HOME": str(self.base / "data")}):
            plan, changes = python_module.module_plan_target(str(self.project), installed_version(), "java")
        self.assertEqual(changes, [])
        self.assertTrue(any("compose.yaml" in conflict for conflict in plan["conflicts"]))

    def test_foreign_compose_created_after_snapshot_blocks_later_language_apply(self):
        self.install("python")
        self.install_docker()
        with mock.patch.dict(os.environ, {"T0004_BACKUP_HOME": str(self.base / "data")}):
            plan, _ = python_module.module_plan_target(str(self.project), installed_version(), "java")
            self.plan_file.write_text(json.dumps(plan), encoding="utf-8")
            compose = self.project / "compose.yaml"
            real_progress = transaction._multi_progress

            def create_after_snapshot(backup, progress):
                real_progress(backup, progress)
                compose.write_bytes(b"foreign\n")

            with mock.patch.object(transaction, "_multi_progress", side_effect=create_after_snapshot):
                with self.assertRaisesRegex(transaction.TransactionError, "Ziel wurde nicht geschrieben"):
                    transaction.apply(str(self.project), str(self.plan_file), plan["plan_id"], installed_version())
            self.assertEqual(compose.read_bytes(), b"foreign\n")
            self.assertFalse((self.project / "java").exists())

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

    def select_postgresql(self):
        result = self.cli("plan", "--infrastructure", "postgresql", "--json")
        self.assertIn(result.returncode, (0, 1), result.stderr)
        return result.returncode, json.loads(result.stdout)

    def install_postgresql(self):
        code, plan = self.select_postgresql()
        self.assertEqual(code, 0, plan["conflicts"])
        self.assertEqual(plan["format"], 4)
        self.assertEqual(plan["infrastructure"], POSTGRESQL)
        self.plan_file.write_text(json.dumps(plan), encoding="utf-8")
        applied = self.cli("apply", "--plan", str(self.plan_file), "--confirm", plan["plan_id"])
        self.assertEqual(applied.returncode, 0, applied.stderr)
        return plan

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
        for path, content in docker_files(frozenset(modules)).items():
            self.assertEqual((self.project / path).read_bytes(), content, path)

    def assert_postgresql_state(self, modules):
        config = (self.project / "config/project.yaml").read_text(encoding="utf-8")
        expected_modules = [f"{module}@0.1.0" for module in ("python", "typescript", "java")
                            if module in modules]
        self.assertIn(f"modules: {json.dumps(expected_modules)}", config)
        self.assertIn('infrastructure: ["docker-compose@0.1.0", "postgresql@0.1.0"]', config)
        for path, content in docker_files(frozenset(modules), postgresql=True).items():
            self.assertEqual((self.project / path).read_bytes(), content, path)
        self.assertEqual((self.project / ".gitignore").read_bytes(), POSTGRES_GITIGNORES[-1])
        self.assertFalse((self.project / ".secrets/postgres_password").exists())

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
            [".dockerignore", "compose.yaml", "Dockerfile.python", "Dockerfile.java", "docs/DOCKER.md", ".github/workflows/docker.yml"],
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
            [".dockerignore", "compose.yaml", "Dockerfile.python", "Dockerfile.typescript", "docs/DOCKER.md", ".github/workflows/docker.yml"],
        )
        self.restore_all([python["backup"]["id"], typescript["backup"]["id"], docker_backup])
        self.assertEqual(self.files(), original)

    def test_public_postgresql_plan_apply_noop_java_and_reverse_restore(self):
        original = self.files()
        python = self.install("python")
        _, docker_backup = self.install_docker()
        postgres = self.install_postgresql()
        self.assert_postgresql_state({"python"})

        code, noop = self.select_postgresql()
        self.assertEqual(code, 0, noop["conflicts"])
        self.assertEqual(noop["operations"], [])
        self.assertIsNone(noop["backup"])

        java = self.install("java")
        self.assert_postgresql_state({"python", "java"})
        before_refusal = self.files()
        self.assertEqual(self.cli("restore", "--backup", postgres["backup"]["id"]).returncode, 1)
        self.assertEqual(self.files(), before_refusal)
        self.restore_all([
            python["backup"]["id"], docker_backup, postgres["backup"]["id"], java["backup"]["id"],
        ])
        self.assertEqual(self.files(), original)

    def test_postgresql_requires_docker_and_exact_ignore_file(self):
        self.install("python")
        code, plan = self.select_postgresql()
        self.assertEqual(code, 1)
        self.assertTrue(any("benötigt docker-compose" in item for item in plan["conflicts"]))

        self.install_docker()
        ignore = self.project / ".gitignore"
        original = ignore.read_bytes()
        ignore.write_bytes(original + b"# foreign\n")
        code, plan = self.select_postgresql()
        self.assertEqual(code, 1)
        self.assertTrue(any(".gitignore" in item for item in plan["conflicts"]))
        self.assertEqual(ignore.read_bytes(), original + b"# foreign\n")

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

    def test_language_dependency_changed_after_snapshot_blocks_module_apply(self):
        self.install("python")
        self.install_docker()
        with mock.patch.dict(os.environ, {"T0004_BACKUP_HOME": str(self.base / "data")}):
            plan, _ = python_module.module_plan_target(str(self.project), installed_version(), "java")
            self.plan_file.write_text(json.dumps(plan), encoding="utf-8")
            dependency = self.project / "src/project_app/app.py"
            original = dependency.read_bytes()
            before_config = (self.project / "config/project.yaml").read_bytes()
            real_progress = transaction._multi_progress

            def edit_after_snapshot(backup, progress):
                real_progress(backup, progress)
                dependency.write_bytes(original + b"# foreign\n")

            with mock.patch.object(transaction, "_multi_progress", side_effect=edit_after_snapshot):
                with self.assertRaisesRegex(transaction.TransactionError, "Ziel wurde nicht geschrieben"):
                    transaction.apply(str(self.project), str(self.plan_file), plan["plan_id"], installed_version())
            self.assertEqual((self.project / "config/project.yaml").read_bytes(), before_config)
            self.assertFalse((self.project / "java").exists())

    def test_installed_language_fingerprint_is_bound_when_docker_registered(self):
        self.install("python")
        self.install_docker()
        with mock.patch.dict(os.environ, {"T0004_BACKUP_HOME": str(self.base / "data")}):
            plan, _ = python_module.module_plan_target(str(self.project), installed_version(), "java")
            state = next(item for item in plan["preconditions"]["files"]
                         if item["path"] == "src/project_app/app.py")
            dependency = self.project / state["path"]
            self.assertEqual(state["sha256"], hashlib.sha256(dependency.read_bytes()).hexdigest())
            self.assertIsInstance(state["attributes"], str)
            self.plan_file.write_text(json.dumps(plan), encoding="utf-8")
            config = self.project / "config/project.yaml"
            config.write_bytes(config.read_bytes().replace(b'"python@0.1.0"', b'"typescript@0.1.0"'))
            before = self.files()
            with self.assertRaises(transaction.TransactionError):
                transaction.apply(str(self.project), str(self.plan_file), plan["plan_id"], installed_version())
            self.assertEqual(before, self.files())

    def test_installed_language_attribute_change_rejects_confirmed_plan(self):
        self.install("python")
        self.install_docker()
        dependency = self.project / "src/project_app/app.py"
        mode = stat.S_IMODE(dependency.stat().st_mode)
        with mock.patch.dict(os.environ, {"T0004_BACKUP_HOME": str(self.base / "data")}):
            plan, _ = python_module.module_plan_target(str(self.project), installed_version(), "java")
            self.plan_file.write_text(json.dumps(plan), encoding="utf-8")
            try:
                dependency.chmod(mode & ~stat.S_IWRITE)
                before = self.files()
                with self.assertRaises(transaction.TransactionError):
                    transaction.apply(str(self.project), str(self.plan_file), plan["plan_id"], installed_version())
                self.assertEqual(before, self.files())
            finally:
                dependency.chmod(mode)

    def test_dockerfile_attributes_are_bound_to_later_language_plan(self):
        self.install("python")
        self.install_docker()
        path = self.project / "Dockerfile.python"
        mode = stat.S_IMODE(path.stat().st_mode)
        with mock.patch.dict(os.environ, {"T0004_BACKUP_HOME": str(self.base / "data")}):
            plan, _ = python_module.module_plan_target(str(self.project), installed_version(), "java")
            state = next(item for item in plan["preconditions"]["files"] if item["path"] == "Dockerfile.python")
            self.assertEqual(state["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            self.plan_file.write_text(json.dumps(plan), encoding="utf-8")
            try:
                path.chmod(mode & ~stat.S_IWRITE)
                with self.assertRaises(transaction.TransactionError):
                    transaction.apply(str(self.project), str(self.plan_file), plan["plan_id"], installed_version())
                self.assertFalse((self.project / "java").exists())
            finally:
                path.chmod(mode)

    def test_format4_fixture_compose_operation_and_reverse_restore(self):
        # The earlier synthetic transaction now exercises real generated bytes.
        self.install("python")
        self.install_docker()
        with mock.patch.dict(os.environ, {"T0004_BACKUP_HOME": str(self.base / "data")}):
            compose = self.project / "compose.yaml"
            original = compose.read_bytes()
            target = docker_files(frozenset({"python", "java"}))["compose.yaml"]
            plan, changes = python_module.module_plan_target(str(self.project), installed_version(), "java")
            operation = next(op for op in plan["operations"] if op["path"] == "compose.yaml")
            self.assertEqual(operation["before_sha256"], hashlib.sha256(original).hexdigest())
            self.assertEqual(operation["after_sha256"], hashlib.sha256(target).hexdigest())
            backup = transaction.apply_multi(str(self.project), plan, plan["plan_id"], installed_version(),
                                             changes, module="java")
            self.assertEqual(compose.read_bytes(), target)
            compose.write_bytes(b"foreign\n")
            with self.assertRaises(transaction.TransactionError):
                transaction.restore(str(self.project), backup)
            compose.write_bytes(target)
            transaction.restore(str(self.project), backup)
            self.assertEqual(compose.read_bytes(), original)
            self.assertFalse((self.project / "Dockerfile.java").exists())

    def test_format4_fixture_compose_changed_after_snapshot_aborts(self):
        self.install("python")
        self.install_docker()
        with mock.patch.dict(os.environ, {"T0004_BACKUP_HOME": str(self.base / "data")}):
            compose = self.project / "compose.yaml"
            plan, changes = python_module.module_plan_target(str(self.project), installed_version(), "java")
            real_progress = transaction._multi_progress

            def edit_after_snapshot(backup, progress):
                real_progress(backup, progress)
                compose.write_bytes(b"foreign\n")

            with mock.patch.object(transaction, "_multi_progress", side_effect=edit_after_snapshot):
                with self.assertRaisesRegex(transaction.TransactionError, "Ziel wurde nicht geschrieben"):
                    transaction.apply_multi(str(self.project), plan, plan["plan_id"], installed_version(),
                                            changes, module="java")
            self.assertEqual(compose.read_bytes(), b"foreign\n")
            self.assertFalse((self.project / "java").exists())

    def test_format4_fixture_stale_compose_and_manipulated_plan_rejected(self):
        self.install("python")
        self.install_docker()
        with mock.patch.dict(os.environ, {"T0004_BACKUP_HOME": str(self.base / "data")}):
            compose = self.project / "compose.yaml"
            plan, changes = python_module.module_plan_target(str(self.project), installed_version(), "java")
            manipulated = json.loads(json.dumps(plan))
            manipulated["preconditions"]["files"][0]["sha256"] = "0" * 64
            with self.assertRaises(transaction.TransactionError):
                transaction.apply_multi(str(self.project), manipulated, plan["plan_id"], installed_version(),
                                        changes, module="java")
            compose.write_bytes(b"foreign\n")
            with self.assertRaises(transaction.TransactionError):
                transaction.apply_multi(str(self.project), plan, plan["plan_id"], installed_version(),
                                        changes, module="java")
            self.assertFalse((self.project / "java").exists())

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
