"""Check the fixed TypeScript assets before they become a public module."""

from importlib import resources
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from project_generator.plan import _operation_paths


FILES = (
    "typescript/.gitignore",
    "typescript/package.json",
    "typescript/package-lock.json",
    "typescript/tsconfig.json",
    "typescript/src/app.ts",
    "typescript/src/main.ts",
    "typescript/test/app.test.mjs",
    "docs/TYPESCRIPT.md",
)


def asset(name: str) -> bytes:
    resource = resources.files("project_generator").joinpath("templates", "typescript")
    relative = name.removeprefix("typescript/") if name.startswith("typescript/") else name
    return resource.joinpath(*relative.split("/")).read_bytes()


class TypeScriptTemplates(unittest.TestCase):
    def test_public_typescript_selection_is_not_enabled_in_pr_a(self):
        result = subprocess.run(
            [sys.executable, "-m", "project_generator", "plan", "--module", "typescript"],
            cwd=ROOT, env=dict(os.environ, PYTHONPATH=str(ROOT / "src")),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        self.assertEqual(result.returncode, 2)

    def test_assets_fit_existing_multi_file_engine(self):
        changes = [(name, "create", asset(name)) for name in FILES]
        self.assertEqual(len(_operation_paths(changes)), len(FILES))

    def test_lockfile_matches_exact_development_dependencies(self):
        package = json.loads(asset("typescript/package.json"))
        lock = json.loads(asset("typescript/package-lock.json"))
        self.assertTrue(package["private"])
        self.assertEqual(package["engines"]["node"], ">=24 <25")
        self.assertNotIn("dependencies", package)
        self.assertEqual(lock["lockfileVersion"], 3)
        self.assertEqual(lock["packages"][""]["devDependencies"], package["devDependencies"])
        for name, version in package["devDependencies"].items():
            entry = lock["packages"]["node_modules/" + name]
            self.assertEqual(entry["version"], version)
            self.assertIn("integrity", entry)
        config = json.loads(asset("typescript/tsconfig.json"))["compilerOptions"]
        self.assertTrue(config["strict"])
        self.assertEqual((config["module"], config["moduleResolution"]), ("NodeNext", "NodeNext"))


if __name__ == "__main__":
    unittest.main()
