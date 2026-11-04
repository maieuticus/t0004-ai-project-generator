"""Trusted Python module content and read-only format-4 planning."""

import hashlib
import json
import re
from pathlib import Path
from importlib import resources

from . import projectcfg
from .config import ConfigurationError
from .plan import (
    _canonical_id, _directory_states, _location_fingerprint, _operation_state, _portable_path_collisions,
    assess, backup_store, file_attributes, metadata_result, multi_plan_target, read_target,
)
from .python_compat import PYTHON_CI_SHA256, VERIFIED_FILES, python_capabilities
from .module_states import MODULES, CI_STATES, known_ci

MODULE = "python@0.1.0"
CHECK = ["python", "-m", "unittest", "discover", "-s", "tests", "-v"]
CI_PATH = ".github/workflows/ci.yml"
CI_EXTENSION = b"      - run: python -m pip install --no-deps .\n      - run: python -m project_app\n"
FILES = {
    "pyproject.toml": b'''[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "project-app"
version = "0.1.0"
description = "Python starter project"
requires-python = ">=3.11"
dependencies = []

[tool.setuptools.packages.find]
where = ["src"]
''',
    "src/project_app/__init__.py": b'"""Example application package."""\n',
    "src/project_app/__main__.py": b'''"""Run the starter application."""

from .app import main

if __name__ == "__main__":
    main()
''',
    "src/project_app/app.py": b'''"""A minimal executable example."""


def main() -> None:
    print("Hello from project_app!")
''',
    "tests/test_project_app.py": b'''"""Tests for the example application."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from project_app.app import main


class ApplicationTest(unittest.TestCase):
    def test_main(self):
        output = StringIO()
        with redirect_stdout(output):
            main()
        self.assertEqual(output.getvalue(), "Hello from project_app!\\n")


if __name__ == "__main__":
    unittest.main()
''',
    "docs/PYTHON.md": b'''# Python starter

Requires Python 3.11 or newer. Install and run the example:

```text
python -m pip install .
python -m project_app
python -m unittest discover -s tests -v
```

The application uses a `src/` layout and only the Python standard library.
`python scripts/check.py` also runs the configured project tests.
''',
}


TS_VERIFY = ["npm", "run", "verify", "--prefix", "typescript"]
JAVA_VERIFY = ["python", "scripts/check_java.py"]
JAVA_FILES = tuple("java/" + name for name in (
    ".gitignore", ".mvn/wrapper/maven-wrapper.properties", "mvnw", "mvnw.cmd", "pom.xml",
    "src/main/java/org/example/app/App.java", "src/test/java/org/example/app/AppTest.java",
)) + ("docs/JAVA.md",)
JAVA_ADAPTER = b'''"""Run the fixed Java starter verification on supported platforms."""
import os
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
if os.name == "nt":
    command = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", "mvnw.cmd", "verify"]
else:
    command = ["sh", "mvnw", "verify"]
raise SystemExit(subprocess.run(command, cwd=root / "java", check=False).returncode)
'''
CHECKS = {"python": CHECK, "typescript": TS_VERIFY, "java": JAVA_VERIFY}
TS_FILES = tuple("typescript/" + name for name in
                 (".gitignore", "package.json", "package-lock.json", "tsconfig.json",
                  "src/app.ts", "src/main.ts", "test/app.test.mjs")) + ("docs/TYPESCRIPT.md",)


def _files_for(module: str) -> dict[str, bytes]:
    if module == "python":
        return FILES
    root = resources.files("project_generator").joinpath("templates", module)
    names = TS_FILES if module == "typescript" else JAVA_FILES
    files = {name: root.joinpath(*name.removeprefix(module + "/").split("/")).read_bytes()
             for name in names}
    if module == "java":
        files["scripts/check_java.py"] = JAVA_ADAPTER
    return files


# Only the exact wrapper shipped before Git-stable LF packaging is compatible.
_LEGACY_JAVA_WRAPPER_SHA256 = "46eedb8419bd14fe70d5bb2916d7b6f51806e51b39d5b76a42610384ca929c1c"


def _matches_module_file(module: str, name: str, original: bytes | None, expected: bytes) -> bool:
    if original == expected:
        return True
    return (module == "java" and name == "java/mvnw.cmd" and original is not None
            and hashlib.sha256(original).hexdigest() == _LEGACY_JAVA_WRAPPER_SHA256
            and original == expected.replace(b"\n", b"\r\n"))


def _add_check(content: bytes, check: list[str] = CHECK) -> bytes:
    text = content.decode("utf-8")
    if check in projectcfg.checks(text):
        return content
    lines = text.splitlines(keepends=True)
    newline = "\r\n" if "\r\n" in text else "\n"
    command = "  - " + json.dumps(check) + newline
    for index, line in enumerate(lines):
        body = line.rstrip("\r\n")
        empty = re.fullmatch(r"(checks:)[ \t]*\[[ \t]*\]([ \t]*(?:#.*)?)", body)
        if empty:
            lines[index] = empty.group(1) + empty.group(2) + newline + command
            return "".join(lines).encode("utf-8")
        if re.fullmatch(r"checks:[ \t]*(?:#.*)?", body):
            last = index
            for entry_index in range(index + 1, len(lines)):
                entry = lines[entry_index].rstrip("\r\n")
                if entry and not entry.startswith((" ", "#")):
                    break
                if re.fullmatch(r"  - \[.*\][ \t]*", entry):
                    last = entry_index
                    if any(check == CHECKS[earlier] and entry.strip() == "- " + json.dumps(CHECKS[later])
                           for earlier in CHECKS for later in CHECKS
                           if list(CHECKS).index(earlier) < list(CHECKS).index(later)):
                        lines.insert(entry_index, command)
                        return "".join(lines).encode("utf-8")
            if not lines[last].endswith(("\n", "\r")):
                lines[last] += newline
            lines.insert(last + 1, command)
            return "".join(lines).encode("utf-8")
    raise ConfigurationError("config/project.yaml: checks kann nicht sicher geändert werden.")


def _metadata_with_module(content: bytes, version: str, current_version: str | None,
                          module: str = "python") -> bytes:
    if current_version is None:
        content = metadata_result(content, version)
    lines = content.decode("utf-8").splitlines(keepends=True)
    in_generator = False
    for index, line in enumerate(lines):
        body = line.rstrip("\r\n")
        if re.fullmatch(r"generator:\s*(#.*)?", body):
            in_generator = True
            continue
        if in_generator and body and not body.startswith((" ", "#")):
            break
        if in_generator:
            match = re.fullmatch(r"(  modules:)[ \t]*(\[[^\]\r\n]*\])([ \t]*(?:#.*)?)", body)
            if match:
                current = json.loads(match.group(2))
                wanted = [value for value in MODULES.values() if value in current or value == MODULES[module]]
                lines[index] = f'{match.group(1)} {json.dumps(wanted)}{match.group(3)}{line[len(body):]}'
                result = "".join(lines).encode("utf-8")
                return _add_check(result) if module == "python" else _add_check(result, CHECKS[module])
    raise ConfigurationError("config/project.yaml: generator.modules kann nicht sicher geändert werden.")


def module_plan_target(target: str, version: str, module: str,
                       backup_id: str | None = None) -> tuple[dict[str, object], list[tuple[str, str, bytes]]]:
    if module not in MODULES:
        raise ConfigurationError("Unbekanntes Technologiemodul.")
    files = _files_for(module)
    content, missing = read_target(target)
    metadata, conflicts, warnings = assess(content, version, missing)
    capabilities = python_capabilities(target)
    conflicts.extend(capabilities["conflicts"])
    root = Path(target).expanduser().resolve(strict=True)
    _directory_states(root, list(files))
    for name in _portable_path_collisions(root, [*files, "config/project.yaml", CI_PATH]):
        conflicts.append(f"{name}: Pfad kollidiert auf anderen Plattformen.")
    installed = MODULES[module] in metadata["modules"]
    checks = projectcfg.checks(content.decode("utf-8"))
    ci, _ = _operation_state(root, CI_PATH)
    expected_modules = frozenset(name for name in MODULES if MODULES[name] in metadata["modules"])
    from .infrastructure_states import DOCKER_COMPOSE, INFRASTRUCTURE
    docker_changes = []
    if INFRASTRUCTURE[DOCKER_COMPOSE] in metadata["infrastructure"]:
        from .docker_files import docker_files
        old_files = docker_files(expected_modules) if expected_modules else {}
        new_files = docker_files(expected_modules | {module})
        for name in _portable_path_collisions(root, list(new_files)):
            conflicts.append(f"{name}: Pfad kollidiert auf anderen Plattformen.")
        for name, expected in old_files.items():
            existing, _ = _operation_state(root, name)
            if existing != expected:
                conflicts.append(f"{name}: Docker-Datei fehlt oder wurde verändert.")
            elif not installed and expected != new_files[name]:
                docker_changes.append((name, "modify", new_files[name]))
        for name in new_files.keys() - old_files.keys():
            existing, _ = _operation_state(root, name)
            if existing is not None:
                conflicts.append(f"{name}: vorhandene Datei wird nicht überschrieben.")
            elif not installed:
                docker_changes.append((name, "create", new_files[name]))
    check = CHECKS[module]
    if installed and check not in checks:
        label = {"python": "Python", "typescript": "TypeScript", "java": "Java"}[module]
        conflicts.append(f"config/project.yaml: {label}-Projektprüfung fehlt oder wurde verändert.")
    for other in MODULES:
        if other != module and other in expected_modules:
            if CHECKS[other] not in checks:
                conflicts.append(f"config/project.yaml: {other}-Projektprüfung fehlt oder wurde verändert.")
            for name, result in _files_for(other).items():
                original, _ = _operation_state(root, name)
                if not _matches_module_file(other, name, original, result):
                    conflicts.append(f"{name}: vorhandenes {other}-Modul fehlt oder wurde verändert.")
    if ci != CI_STATES[expected_modules]:
        label = "Python-CI-Erweiterung" if module == "python" and installed else "geprüfter CI-Zustand"
        conflicts.append(f"{CI_PATH}: {label} fehlt oder wurde verändert.")
    changes = []
    for name, result in files.items():
        original, _ = _operation_state(root, name)
        if installed:
            if not _matches_module_file(module, name, original, result):
                conflicts.append(f"{name}: Moduldatei fehlt oder wurde verändert.")
        elif original is not None:
            conflicts.append(f"{name}: vorhandene Datei wird nicht überschrieben.")
        else:
            changes.append((name, "create", result))
    if installed and metadata["generator_version"] != version:
        conflicts.append("generator.version: installiertes Modul hat keine passende Generatorversion.")
    if any(re.fullmatch(r"\.t0004-backup-[0-9a-f]{32}", entry.name, re.IGNORECASE)
           for entry in root.iterdir()):
        conflicts.append("Altes Backup im Zielprojekt: vor Git-Operationen geschützt außerhalb sichern.")
    if not installed and not conflicts and ci is not None:
        changes.extend(docker_changes)
        config_result = _metadata_with_module(content, version, metadata["generator_version"], module)
        changes.append(("config/project.yaml", "modify", config_result))
        changes.append((CI_PATH, "modify", CI_STATES[expected_modules | {module}]))
        return multi_plan_target(target, version, changes, backup_id, module=module), changes

    identity = {
        "format": 4,
        "module": module,
        "generator_version": version,
        "source_sha256": hashlib.sha256(content).hexdigest(),
        "source_attributes": file_attributes(target),
        "project_fingerprint": _location_fingerprint(root),
        "storage_fingerprint": _location_fingerprint(backup_store(target)),
        "preconditions": {"files": capabilities["files"], "directories": capabilities["directories"]},
        "operations": [],
        "directories": [],
        "backup": None,
        "warnings": warnings,
        "conflicts": conflicts,
    }
    return {**identity, "plan_id": _canonical_id(identity), "read_only": True}, []


def python_plan_target(target: str, version: str) -> tuple[dict[str, object], list[tuple[str, str, bytes]]]:
    return module_plan_target(target, version, "python")
