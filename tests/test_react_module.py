"""Public React module planning and independent installation."""

import hashlib
from itertools import combinations
import json
from pathlib import Path
import sys
import unittest

from test_python_module import PythonModule
from test_react_template import FILES as REACT_TEMPLATE_FILES, asset

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from project_generator import projectcfg, python_module
from project_generator.config import load_metadata
from project_generator.docker_files import docker_files
from project_generator.infrastructure_states import (
    DOCKER_COMPOSE, POSTGRESQL, INFRASTRUCTURE, docker_projection_with_ci, valid_infrastructure,
)
from project_generator.module_states import CI_DIGESTS, CI_STATES, DOCKER_MODULES, MODULES, known_ci
from project_generator.plan import assess
from project_generator.python_module import CHECKS


REACT_CHECK = ["npm", "run", "verify", "--prefix", "react"]
REACT_FILES = tuple("react/" + name for name in REACT_TEMPLATE_FILES)


class ReactModuleProjection(unittest.TestCase):
    def test_react_assets_check_and_metadata_are_canonical(self):
        files = python_module._files_for("react")
        self.assertEqual(set(files), set(REACT_FILES))
        for name in REACT_FILES:
            self.assertEqual(files[name], asset(name.removeprefix("react/")))
        self.assertEqual(CHECKS["react"], REACT_CHECK)

        config = (ROOT / "config/project.yaml").read_bytes()
        version = None
        for module in reversed(tuple(MODULES)):
            config = python_module._metadata_with_module(config, "0.1.0", version, module)
            version = "0.1.0"
        metadata = load_metadata(config)
        self.assertEqual(metadata["modules"], list(MODULES.values()))
        self.assertEqual(projectcfg.checks(config.decode("utf-8")), list(CHECKS.values()))
        assessed, conflicts, _ = assess(config, "0.1.0", [])
        self.assertEqual(assessed["modules"], list(MODULES.values()))
        self.assertEqual(conflicts, [])

    def test_react_ci_states_preserve_all_eight_historical_bytes(self):
        for modules, expected_digest in CI_DIGESTS.items():
            with self.subTest(modules=modules):
                self.assertEqual(hashlib.sha256(CI_STATES[modules]).hexdigest(), expected_digest)
                self.assertEqual(known_ci(CI_STATES[modules]), modules)

        self.assertEqual(len(CI_STATES), 16)
        self.assertEqual(len(set(CI_STATES.values())), 16)
        for count in range(len(MODULES) + 1):
            for names in combinations(MODULES, count):
                modules = frozenset(names)
                self.assertEqual(b"--prefix react" in CI_STATES[modules], "react" in modules)

    def test_react_does_not_change_docker_service_projections(self):
        console = frozenset({"python"})
        with_react = console | {"react"}
        self.assertEqual(docker_files(with_react), docker_files(console))
        self.assertEqual(
            docker_files(with_react, postgresql=True),
            docker_files(console, postgresql=True),
        )
        self.assertEqual(docker_projection_with_ci(with_react), docker_projection_with_ci(console))
        self.assertNotIn("react", DOCKER_MODULES)
        self.assertFalse(valid_infrastructure(
            [INFRASTRUCTURE[DOCKER_COMPOSE]],
            [MODULES["react"]],
        ))
        with self.assertRaises(ValueError):
            docker_files(frozenset({"react"}))


class ReactModule(unittest.TestCase):
    setUp = PythonModule.setUp
    cli = PythonModule.cli

    def select(self, command="plan", module="react"):
        result = self.cli(command, "--module", module, "--json")
        self.assertEqual(
            result.returncode,
            0,
            f"{module} module selection failed.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        return json.loads(result.stdout)

    def files(self):
        return {path.relative_to(self.project).as_posix(): path.read_bytes()
                for path in self.project.rglob("*") if path.is_file()}

    def install(self, module="react"):
        plan = self.select(module=module)
        self.plan_file.write_text(json.dumps(plan), encoding="utf-8")
        applied = self.cli("apply", "--plan", str(self.plan_file), "--confirm", plan["plan_id"])
        self.assertEqual(applied.returncode, 0, applied.stderr)
        return plan

    def install_infrastructure(self, infrastructure):
        result = self.cli("plan", "--infrastructure", infrastructure, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.plan_file.write_text(result.stdout, encoding="utf-8")
        applied = self.cli("apply", "--plan", str(self.plan_file), "--confirm", plan["plan_id"])
        self.assertEqual(applied.returncode, 0, applied.stderr)
        return plan

    def test_public_react_plan_is_read_only_and_independent_of_typescript(self):
        original = self.files()
        plan = self.select()
        self.assertEqual(plan, self.select("new"))
        self.assertEqual(plan["format"], 4)
        self.assertEqual(plan["module"], "react")
        self.assertTrue(plan["read_only"])
        self.assertEqual(plan["conflicts"], [])
        self.assertEqual(len(plan["preconditions"]["files"]), 3)
        operations = {operation["path"]: operation["action"] for operation in plan["operations"]}
        self.assertEqual(
            set(operations),
            set(REACT_FILES) | {"config/project.yaml", ".github/workflows/ci.yml"},
        )
        self.assertTrue(all(operations[name] == "create" for name in REACT_FILES))
        self.assertEqual(operations["config/project.yaml"], "modify")
        self.assertEqual(operations[".github/workflows/ci.yml"], "modify")
        self.assertEqual(self.files(), original)
        self.assertFalse((self.project / "typescript").exists())

    def test_react_install_sets_only_react_metadata_and_project_check(self):
        self.assertFalse((self.project / "typescript").exists())
        plan = self.install()

        config = (self.project / "config/project.yaml").read_text(encoding="utf-8")
        self.assertIn('modules: ["react@0.1.0"]', config)
        self.assertEqual(projectcfg.checks(config), [REACT_CHECK])
        self.assertTrue(all((self.project / name).is_file() for name in REACT_FILES))
        self.assertFalse((self.project / "typescript").exists())
        self.assertEqual((self.project / ".github/workflows/ci.yml").read_bytes(),
                         CI_STATES[frozenset({"react"})])

        noop = self.select()
        self.assertEqual(noop["operations"], [])
        self.assertIsNone(noop["backup"])
        restored = self.cli("restore", "--backup", plan["backup"]["id"])
        self.assertEqual(restored.returncode, 0, restored.stderr)

    def test_all_sixteen_module_subsets_plan_apply_noop_and_restore(self):
        original = self.files()
        ordered_modules = tuple(MODULES)
        for count in range(len(ordered_modules) + 1):
            for names in combinations(ordered_modules, count):
                modules = frozenset(names)
                with self.subTest(modules=modules):
                    plans = []
                    try:
                        for module in ordered_modules:
                            if module not in modules:
                                continue
                            before_plan = self.files()
                            plan = self.select(module=module)
                            self.assertEqual(plan["module"], module)
                            self.assertEqual(plan["conflicts"], [])
                            self.assertEqual(self.files(), before_plan)
                            self.plan_file.write_text(json.dumps(plan), encoding="utf-8")
                            applied = self.cli("apply", "--plan", str(self.plan_file),
                                               "--confirm", plan["plan_id"])
                            self.assertEqual(applied.returncode, 0, applied.stderr)
                            plans.append(plan)

                        metadata = load_metadata((self.project / "config/project.yaml").read_bytes())
                        expected_ids = [MODULES[module] for module in ordered_modules if module in modules]
                        self.assertEqual(metadata["modules"], expected_ids)
                        self.assertEqual(
                            projectcfg.checks((self.project / "config/project.yaml").read_text(encoding="utf-8")),
                            [CHECKS[module] for module in ordered_modules if module in modules],
                        )
                        self.assertEqual((self.project / ".github/workflows/ci.yml").read_bytes(),
                                         CI_STATES[modules])
                        for module in ordered_modules:
                            if module in modules:
                                for path, content in python_module._files_for(module).items():
                                    self.assertEqual((self.project / path).read_bytes(), content, path)
                                noop = self.select(module=module)
                                self.assertEqual(noop["operations"], [])
                                self.assertIsNone(noop["backup"])
                            else:
                                self.assertFalse((self.project / module).exists())
                    finally:
                        for plan in reversed(plans):
                            restored = self.cli("restore", "--backup", plan["backup"]["id"])
                            self.assertEqual(restored.returncode, 0, restored.stderr)
                    self.assertEqual(self.files(), original)

    def test_react_pairwise_install_orders_converge_and_restore(self):
        original = self.files()
        for module in ("python", "typescript", "java"):
            final_states = []
            for order in (("react", module), (module, "react")):
                with self.subTest(order=order):
                    plans = [self.install(item) for item in order]
                    config = (self.project / "config/project.yaml").read_text(encoding="utf-8")
                    expected = [MODULES[name] for name in ("python", "typescript", "java", "react")
                                if name in order]
                    self.assertIn(f"modules: {json.dumps(expected)}", config)
                    self.assertEqual((self.project / ".github/workflows/ci.yml").read_bytes(),
                                     CI_STATES[frozenset(order)])
                    final_states.append(self.files())
                    before_refusal = self.files()
                    refused = self.cli("restore", "--backup", plans[0]["backup"]["id"])
                    self.assertEqual(refused.returncode, 1)
                    self.assertEqual(self.files(), before_refusal)
                    for plan in reversed(plans):
                        restored = self.cli("restore", "--backup", plan["backup"]["id"])
                        self.assertEqual(restored.returncode, 0, restored.stderr)
                    self.assertEqual(self.files(), original)
            self.assertEqual(final_states[0], final_states[1])

    def test_react_coexists_with_docker_postgresql_without_adding_a_service(self):
        python = self.install("python")
        docker = self.install_infrastructure(DOCKER_COMPOSE)
        postgresql = self.install_infrastructure(POSTGRESQL)
        docker_paths = {
            ".dockerignore", "compose.yaml", "Dockerfile.python", "docs/DOCKER.md",
            ".github/workflows/docker.yml", "docs/POSTGRESQL.md", ".gitignore",
        }
        before = self.files()
        projection = {path: before[path] for path in docker_paths}

        react = self.install()
        after = self.files()
        self.assertEqual({path: after[path] for path in docker_paths}, projection)
        self.assertFalse((self.project / "Dockerfile.react").exists())
        self.assertNotIn(b"app-react", after["compose.yaml"])
        self.assertEqual(after[".github/workflows/ci.yml"],
                         CI_STATES[frozenset({"python", "react"})])
        noop = self.select()
        self.assertEqual(noop["operations"], [])
        self.assertIsNone(noop["backup"])
        self.assertFalse(any("app-react" in line for line in after["compose.yaml"].decode().splitlines()))

        for backup in (react["backup"]["id"], postgresql["backup"]["id"],
                       docker["backup"]["id"], python["backup"]["id"]):
            restored = self.cli("restore", "--backup", backup)
            self.assertEqual(restored.returncode, 0, restored.stderr)

    def test_console_module_after_react_extends_compose_and_converges(self):
        steps = (("python", None), (None, DOCKER_COMPOSE), (None, POSTGRESQL),
                 ("react", None), ("java", None))
        backups = []
        initial = self.files()
        for module, infrastructure in steps:
            plan = self.install(module) if module else self.install_infrastructure(infrastructure)
            backups.append(plan["backup"]["id"])
            if module == "react":
                before_java = self.files()
        after = self.files()
        compose = after["compose.yaml"].decode()
        self.assertIn("app-java", compose)
        self.assertIn("app-python", compose)
        self.assertNotIn("app-react", compose)
        self.assertIn("postgres", compose)
        self.assertTrue((self.project / "Dockerfile.java").exists())
        self.assertFalse((self.project / "Dockerfile.react").exists())
        self.assertEqual(after[".github/workflows/ci.yml"],
                         CI_STATES[frozenset({"python", "react", "java"})])
        for path in REACT_FILES:
            self.assertEqual(after[path], before_java[path])
        self.assertEqual(self.select(module="java")["operations"], [])
        self.assertEqual(self.select()["operations"], [])
        self.assertEqual(self.cli("restore", "--backup", backups[0]).returncode, 1)
        self.assertEqual(self.files(), after)

        java_backup = backups.pop()
        self.assertEqual(self.cli("restore", "--backup", java_backup).returncode, 0)
        self.assertEqual(self.files(), before_java)
        for backup in reversed(backups):
            restored = self.cli("restore", "--backup", backup)
            self.assertEqual(restored.returncode, 0, restored.stderr)
        self.assertEqual(self.files(), initial)

    def test_console_module_after_react_blocks_on_modified_compose_without_writes(self):
        self.install("python")
        self.install_infrastructure(DOCKER_COMPOSE)
        self.install("react")
        compose = self.project / "compose.yaml"
        compose.write_bytes(compose.read_bytes() + b"# user edit\n")
        original = self.files()
        result = self.cli("plan", "--module", "java", "--json")
        self.assertEqual(result.returncode, 1)
        plan = json.loads(result.stdout)
        self.assertTrue(plan["conflicts"])
        self.assertEqual(plan["operations"], [])
        self.assertEqual(self.files(), original)

    def test_react_alone_does_not_satisfy_docker_prerequisite(self):
        plan = self.install()
        result = self.cli("plan", "--infrastructure", "docker-compose", "--json")
        self.assertEqual(result.returncode, 1)
        conflict = json.loads(result.stdout)
        self.assertTrue(conflict["conflicts"])
        self.assertEqual(conflict["operations"], [])
        restored = self.cli("restore", "--backup", plan["backup"]["id"])
        self.assertEqual(restored.returncode, 0, restored.stderr)

    def test_foreign_react_path_and_modified_files_block_without_writes(self):
        foreign = self.project / "react/package.json"
        foreign.parent.mkdir()
        foreign.write_bytes(b"foreign package")
        before = self.files()
        result = self.cli("plan", "--module", "react", "--json")
        self.assertEqual(result.returncode, 1)
        conflict = json.loads(result.stdout)
        self.assertTrue(conflict["conflicts"])
        self.assertEqual(conflict["operations"], [])
        self.assertEqual(self.files(), before)

        foreign.unlink()
        foreign.parent.rmdir()
        plan = self.install()
        managed = self.project / "react/src/App.tsx"
        original_content = managed.read_bytes()
        managed.write_bytes(original_content + b"\n// foreign change\n")
        before = self.files()
        result = self.cli("plan", "--module", "react", "--json")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["operations"], [])
        refused = self.cli("restore", "--backup", plan["backup"]["id"])
        self.assertEqual(refused.returncode, 1)
        self.assertEqual(self.files(), before)

        managed.write_bytes(original_content)
        restored = self.cli("restore", "--backup", plan["backup"]["id"])
        self.assertEqual(restored.returncode, 0, restored.stderr)

    def test_tampered_stale_and_unconfirmed_react_plans_are_rejected(self):
        original = self.files()
        plan = self.select()
        self.plan_file.write_text(json.dumps(plan), encoding="utf-8")

        unconfirmed = self.cli("apply", "--plan", str(self.plan_file), "--confirm", "0" * 64)
        self.assertEqual(unconfirmed.returncode, 1)
        self.assertEqual(self.files(), original)

        tampered = json.loads(json.dumps(plan))
        tampered["operations"][0]["after_sha256"] = "0" * 64
        self.plan_file.write_text(json.dumps(tampered), encoding="utf-8")
        refused = self.cli("apply", "--plan", str(self.plan_file), "--confirm", plan["plan_id"])
        self.assertEqual(refused.returncode, 1)
        self.assertEqual(self.files(), original)
        self.assertFalse((self.base / "data").exists())

        self.plan_file.write_text(json.dumps(plan), encoding="utf-8")
        config = self.project / "config/project.yaml"
        original_config = config.read_bytes()
        config.write_bytes(original_config + b"# stale plan input\n")
        before_stale_apply = self.files()
        stale = self.cli("apply", "--plan", str(self.plan_file), "--confirm", plan["plan_id"])
        self.assertEqual(stale.returncode, 1)
        self.assertEqual(self.files(), before_stale_apply)
        self.assertFalse((self.base / "data").exists())

    def test_incompatible_react_metadata_and_checks_are_conflicts(self):
        config = self.project / "config/project.yaml"
        original_config = config.read_bytes()
        config.write_bytes(original_config.replace(b"modules: []", b'modules: ["react@9.9.9"]'))
        result = self.cli("plan", "--module", "react", "--json")
        self.assertEqual(result.returncode, 1)
        self.assertTrue(json.loads(result.stdout)["conflicts"])
        config.write_bytes(original_config)

        plan = self.install()
        configured = config.read_bytes()
        config.write_bytes(configured.replace(
            b'  - ["npm", "run", "verify", "--prefix", "react"]\n', b""
        ))
        before = self.files()
        result = self.cli("plan", "--module", "react", "--json")
        self.assertEqual(result.returncode, 1)
        self.assertTrue(json.loads(result.stdout)["conflicts"])
        refused = self.cli("restore", "--backup", plan["backup"]["id"])
        self.assertEqual(refused.returncode, 1)
        self.assertEqual(self.files(), before)
        config.write_bytes(configured)
        restored = self.cli("restore", "--backup", plan["backup"]["id"])
        self.assertEqual(restored.returncode, 0, restored.stderr)


if __name__ == "__main__":
    unittest.main()
