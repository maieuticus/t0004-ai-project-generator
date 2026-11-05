"""Verify the independently packaged React starter before module integration."""

from importlib import resources
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


FILES = (
    ".gitignore",
    "index.html",
    "package.json",
    "package-lock.json",
    "tsconfig.json",
    "vite.config.ts",
    "src/App.tsx",
    "src/counter.ts",
    "src/main.tsx",
    "src/style.css",
    "test/app.test.mjs",
    "docs/REACT.md",
)


def asset(name: str) -> bytes:
    resource = resources.files("project_generator").joinpath("templates", "react")
    return resource.joinpath(*name.split("/")).read_bytes()


def npm_command(*args: str) -> list[str]:
    if sys.platform == "win32":
        return ["cmd.exe", "/d", "/c", "npm.cmd", *args]
    return ["npm", *args]


class ReactTemplate(unittest.TestCase):
    def test_packaged_assets_include_locked_starter_and_documented_preview(self):
        package = json.loads(asset("package.json"))
        lock = json.loads(asset("package-lock.json"))
        documentation = asset("docs/REACT.md").decode("utf-8")

        self.assertEqual(package["scripts"]["verify"], "npm run test && npm run build")
        self.assertEqual(package["scripts"]["start"], "vite --strictPort")
        self.assertEqual(package["packageManager"], "npm@11.19.1")
        self.assertEqual(lock["lockfileVersion"], 3)
        self.assertEqual(lock["packages"][""]["dependencies"], package["dependencies"])
        self.assertEqual(lock["packages"][""]["devDependencies"], package["devDependencies"])
        for dependencies in ("dependencies", "devDependencies"):
            for name, version in package[dependencies].items():
                entry = lock["packages"]["node_modules/" + name]
                self.assertEqual(entry["version"], version)
                self.assertIn("integrity", entry)

        self.assertIn("npm ci --ignore-scripts --no-audit --no-fund --strict-peer-deps", documentation)
        self.assertIn("npm run verify", documentation)
        self.assertIn("npm start", documentation)
        self.assertIn("http://localhost:5173/", documentation)
        self.assertEqual(asset(".gitignore"), b"node_modules/\ndist/\n")

    def test_clean_install_verify_and_build_output(self):
        resource = resources.files("project_generator").joinpath("templates", "react")
        with resources.as_file(resource) as source, tempfile.TemporaryDirectory() as temporary:
            starter = Path(temporary) / "react"
            shutil.copytree(
                source,
                starter,
                ignore=shutil.ignore_patterns("node_modules", "dist"),
            )
            installed = subprocess.run(
                npm_command("ci", "--ignore-scripts", "--no-audit", "--no-fund", "--strict-peer-deps"),
                cwd=starter,
                capture_output=True,
                text=True,
            )
            self.assertEqual(installed.returncode, 0, installed.stderr)
            verified = subprocess.run(
                npm_command("run", "verify"),
                cwd=starter,
                capture_output=True,
                text=True,
            )
            self.assertEqual(verified.returncode, 0, verified.stderr)
            self.assertTrue((starter / "dist/index.html").is_file())
            self.assertTrue(any((starter / "dist/assets").iterdir()))


if __name__ == "__main__":
    unittest.main()
