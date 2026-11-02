"""Java and three-module integration through the public CLI."""
import itertools
import json
import unittest
from pathlib import Path

from test_typescript_module import TypeScriptModule
from project_generator.module_states import CI_STATES


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
