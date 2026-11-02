"""Java and three-module integration through the public CLI."""
import itertools
import os
from unittest import mock
import json
import unittest
from pathlib import Path

from test_typescript_module import TypeScriptModule
from project_generator.module_states import CI_STATES
from project_generator import installed_version, python_module, transaction


class JavaModule(unittest.TestCase):
    setUp = TypeScriptModule.setUp
    cli = TypeScriptModule.cli
    select = TypeScriptModule.select
    install = TypeScriptModule.install
    files = TypeScriptModule.files

    def test_all_states_and_orders_with_reverse_restore(self):
        original = self.files()
        states = {frozenset(): original}
        for order in itertools.permutations(("python", "typescript", "java")):
            plans = []
            for module in order:
                plans.append(self.install(module))
                key = frozenset(p["module"] for p in plans)
                content = self.files()
                if key in states:
                    self.assertEqual(states[key], content, order)
                else:
                    states[key] = content
                self.assertEqual((self.project / ".github/workflows/ci.yml").read_bytes(), CI_STATES[key])
                code, noop = self.select(module)
                self.assertEqual(code, 0, noop["conflicts"])
                self.assertEqual(noop["operations"], [])
            before = self.files()
            self.assertEqual(self.cli("restore", "--backup", plans[0]["backup"]["id"]).returncode, 1)
            self.assertEqual(before, self.files())
            for plan in reversed(plans):
                result = self.cli("restore", "--backup", plan["backup"]["id"])
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.files(), original)
        self.assertEqual(len(states), 8)

    def test_java_conflicts_and_build_output_preserved(self):
        plan = self.install("java")
        source = self.project / "java/src/main/java/org/example/app/App.java"
        original = source.read_bytes()
        source.unlink()
        code, conflict = self.select("java")
        self.assertEqual(code, 1)
        self.assertEqual(conflict["operations"], [])
        source.write_bytes(original + b"\n// foreign change\n")
        before = self.files()
        self.assertEqual(self.cli("restore", "--backup", plan["backup"]["id"]).returncode, 1)
        self.assertEqual(before, self.files())
        source.write_bytes(original)
        target = self.project / "java/target/foreign.txt"
        target.parent.mkdir()
        target.write_text("build output", encoding="utf-8")
        result = self.cli("restore", "--backup", plan["backup"]["id"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(target.read_text(encoding="utf-8"), "build output")

    def test_legacy_crlf_wrapper_is_exact_and_restore_remains_strict(self):
        real_files = python_module._files_for
        def legacy_files(module):
            files = dict(real_files(module))
            if module == "java":
                files["java/mvnw.cmd"] = files["java/mvnw.cmd"].replace(b"\n", b"\r\n")
            return files

        with (mock.patch.dict(os.environ, {"T0004_BACKUP_HOME": str(self.base / "data")}),
              mock.patch.object(python_module, "_files_for", side_effect=legacy_files)):
            plan, changes = python_module.module_plan_target(str(self.project), installed_version(), "java")
            transaction.apply_multi(str(self.project), plan, plan["plan_id"], installed_version(),
                                    changes, module="java")
        wrapper = self.project / "java/mvnw.cmd"
        legacy = wrapper.read_bytes()
        self.assertIn(b"\r\n", legacy)
        code, noop = self.select("java")
        self.assertEqual(code, 0, noop["conflicts"])
        self.assertEqual(noop["operations"], [])
        for module in ("python", "typescript"):
            code, additional = self.select(module)
            self.assertEqual(code, 0, additional["conflicts"])
        wrapper.write_bytes(legacy.replace(b"\r\n", b"\n"))
        code, noop = self.select("java")
        self.assertEqual(code, 0, noop["conflicts"])
        before = self.files()
        self.assertEqual(self.cli("restore", "--backup", plan["backup"]["id"]).returncode, 1)
        self.assertEqual(before, self.files())
        wrapper.write_bytes(legacy + b"rem foreign change\r\n")
        before = self.files()
        code, conflict = self.select("java")
        self.assertEqual(code, 1)
        self.assertEqual(conflict["operations"], [])
        self.assertEqual(self.cli("restore", "--backup", plan["backup"]["id"]).returncode, 1)
        self.assertEqual(before, self.files())
        wrapper.write_bytes(legacy)
        self.assertEqual(self.cli("restore", "--backup", plan["backup"]["id"]).returncode, 0)

    def test_java_tampered_plan_and_missing_snapshot_are_refused(self):
        _, plan = self.select("java")
        tampered = json.loads(json.dumps(plan))
        tampered["operations"][0]["after_sha256"] = "0" * 64
        self.plan_file.write_text(json.dumps(tampered), encoding="utf-8")
        before = self.files()
        self.assertEqual(self.cli("apply", "--plan", str(self.plan_file),
                                  "--confirm", plan["plan_id"]).returncode, 1)
        self.assertEqual(before, self.files())
        plan = self.install("java")
        backup = self.base / "data/t0004-generator/backups" / (".t0004-backup-" + plan["backup"]["id"])
        next(backup.glob("original-*")).unlink()
        before = self.files()
        self.assertEqual(self.cli("restore", "--backup", plan["backup"]["id"]).returncode, 1)
        self.assertEqual(before, self.files())

    def test_java_stale_plan_foreign_path_and_tampered_snapshot(self):
        foreign = self.project / "java/pom.xml"
        foreign.parent.mkdir()
        foreign.write_bytes(b"foreign")
        code, conflict = self.select("java")
        self.assertEqual(code, 1)
        self.assertEqual(conflict["operations"], [])
        foreign.unlink()
        foreign.parent.rmdir()
        _, plan = self.select("java")
        self.plan_file.write_text(json.dumps(plan), encoding="utf-8")
        config = self.project / "config/project.yaml"
        config.write_bytes(config.read_bytes() + b"# changed\n")
        before = self.files()
        self.assertEqual(self.cli("apply", "--plan", str(self.plan_file), "--confirm", plan["plan_id"]).returncode, 1)
        self.assertEqual(self.files(), before)
        plan = self.install("java")
        backup = self.base / "data/t0004-generator/backups" / (".t0004-backup-" + plan["backup"]["id"])
        manifest = backup / "manifest.json"
        manifest.write_bytes(manifest.read_bytes().replace(b'"format": 3', b'"format": 9', 1))
        before = self.files()
        self.assertEqual(self.cli("restore", "--backup", plan["backup"]["id"]).returncode, 1)
        self.assertEqual(self.files(), before)


if __name__ == "__main__":
    unittest.main()
