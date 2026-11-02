"""Public TypeScript selection and the two sequential module orders."""

import json
from pathlib import Path
import sys
import unittest

from test_python_module import PythonModule

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from project_generator.module_states import CI_STATES
from project_generator.python_module import CHECK, TS_VERIFY


class TypeScriptModule(unittest.TestCase):
    setUp = PythonModule.setUp
    cli = PythonModule.cli

    def select(self, module):
        result = self.cli("plan", "--module", module, "--json")
        self.assertIn(result.returncode, (0, 1), result.stderr)
        return result.returncode, json.loads(result.stdout)

    def install(self, module):
        code, plan = self.select(module)
        self.assertEqual(code, 0, plan["conflicts"])
        self.assertEqual(plan["format"], 4)
        self.assertEqual(plan["module"], module)
        self.plan_file.write_text(json.dumps(plan), encoding="utf-8")
        applied = self.cli("apply", "--plan", str(self.plan_file), "--confirm", plan["plan_id"])
        self.assertEqual(applied.returncode, 0, applied.stderr)
        return plan

    def files(self):
        return {p.relative_to(self.project).as_posix(): p.read_bytes()
                for p in self.project.rglob("*") if p.is_file()}

    def test_typescript_only_plan_apply_noop_restore(self):
        original = self.files()
        code, plan = self.select("typescript")
        self.assertEqual(code, 0)
        self.assertEqual(self.files(), original)
        self.assertEqual(len(plan["preconditions"]["files"]), 3)
        plan = self.install("typescript")
        self.assertEqual((self.project / ".github/workflows/ci.yml").read_bytes(),
                         CI_STATES[frozenset({"typescript"})])
        config = (self.project / "config/project.yaml").read_text(encoding="utf-8")
        self.assertIn('modules: ["typescript@0.1.0"]', config)
        self.assertIn(json.dumps(TS_VERIFY), config)
        code, noop = self.select("typescript")
        self.assertEqual(code, 0)
        self.assertEqual(noop["operations"], [])
        self.assertIsNone(noop["backup"])
        restored = self.cli("restore", "--backup", plan["backup"]["id"])
        self.assertEqual(restored.returncode, 0, restored.stderr)
        self.assertEqual(self.files(), original)

    def test_both_orders_have_identical_contents_and_reverse_restore(self):
        original = self.files()
        final_states = []
        for order in (("python", "typescript"), ("typescript", "python")):
            with self.subTest(order=order):
                first = self.install(order[0])
                second = self.install(order[1])
                final_states.append(self.files())
                config = (self.project / "config/project.yaml").read_text(encoding="utf-8")
                self.assertIn('modules: ["python@0.1.0", "typescript@0.1.0"]', config)
                self.assertIn(json.dumps(CHECK), config)
                self.assertIn(json.dumps(TS_VERIFY), config)
                self.assertEqual((self.project / ".github/workflows/ci.yml").read_bytes(),
                                 CI_STATES[frozenset({"python", "typescript"})])
                before_refusal = self.files()
                refused = self.cli("restore", "--backup", first["backup"]["id"])
                self.assertEqual(refused.returncode, 1)
                self.assertEqual(self.files(), before_refusal)
                for plan in (second, first):
                    restored = self.cli("restore", "--backup", plan["backup"]["id"])
                    self.assertEqual(restored.returncode, 0, restored.stderr)
                self.assertEqual(self.files(), original)
        self.assertEqual(final_states[0], final_states[1])

    def test_foreign_files_and_stale_plan_leave_project_unchanged(self):
        foreign = self.project / "typescript/package.json"
        foreign.parent.mkdir()
        foreign.write_bytes(b"foreign")
        code, conflict = self.select("typescript")
        self.assertEqual(code, 1)
        self.assertEqual(conflict["operations"], [])
        foreign.unlink()
        foreign.parent.rmdir()
        _, plan = self.select("typescript")
        self.plan_file.write_text(json.dumps(plan), encoding="utf-8")
        config = self.project / "config/project.yaml"
        config.write_bytes(config.read_bytes() + b"# user change\n")
        before = self.files()
        refused = self.cli("apply", "--plan", str(self.plan_file), "--confirm", plan["plan_id"])
        self.assertEqual(refused.returncode, 1)
        self.assertEqual(self.files(), before)
        self.assertFalse((self.base / "data").exists())

    def test_modified_module_blocks_plan_and_restore_without_partial_changes(self):
        plan = self.install("typescript")
        module_file = self.project / "typescript/src/app.ts"
        module_file.write_bytes(module_file.read_bytes() + b"\n// foreign change\n")
        before = self.files()
        code, conflict = self.select("typescript")
        self.assertEqual(code, 1)
        self.assertEqual(conflict["operations"], [])
        self.assertEqual(before, self.files())
        restored = self.cli("restore", "--backup", plan["backup"]["id"])
        self.assertEqual(restored.returncode, 1, restored.stderr)
        self.assertEqual(before, self.files())


if __name__ == "__main__":
    unittest.main()
