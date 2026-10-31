"""Trusted Python module content and read-only format-4 planning."""

import hashlib
import json
import re
from pathlib import Path

from . import projectcfg
from .config import ConfigurationError
from .plan import (
    _canonical_id, _directory_states, _location_fingerprint, _operation_state,
    assess, backup_store, file_attributes, metadata_result, multi_plan_target, read_target,
)
from .python_compat import PYTHON_CI_SHA256, VERIFIED_FILES, python_capabilities

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


def _add_check(content: bytes) -> bytes:
    text = content.decode("utf-8")
    if CHECK in projectcfg.checks(text):
        return content
    lines = text.splitlines(keepends=True)
    newline = "\r\n" if "\r\n" in text else "\n"
    command = "  - " + json.dumps(CHECK) + newline
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
            if not lines[last].endswith(("\n", "\r")):
                lines[last] += newline
            lines.insert(last + 1, command)
            return "".join(lines).encode("utf-8")
    raise ConfigurationError("config/project.yaml: checks kann nicht sicher geändert werden.")


def _metadata_with_module(content: bytes, version: str, current_version: str | None) -> bytes:
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
            match = re.fullmatch(r"(  modules:)[ \t]*\[[ \t]*\]([ \t]*(?:#.*)?)", body)
            if match:
                lines[index] = f'{match.group(1)} ["{MODULE}"]{match.group(2)}{line[len(body):]}'
                return _add_check("".join(lines).encode("utf-8"))
    raise ConfigurationError("config/project.yaml: generator.modules kann nicht sicher geändert werden.")


def python_plan_target(target: str, version: str) -> tuple[dict[str, object], list[tuple[str, str, bytes]]]:
    content, missing = read_target(target)
    metadata, conflicts, warnings = assess(content, version, missing)
    capabilities = python_capabilities(target)
    conflicts.extend(capabilities["conflicts"])
    root = Path(target).expanduser().resolve(strict=True)
    _directory_states(root, list(FILES))
    installed = metadata["modules"] == [MODULE]
    checks = projectcfg.checks(content.decode("utf-8"))
    ci, _ = _operation_state(root, CI_PATH)
    ci_hash = hashlib.sha256(ci).hexdigest() if ci is not None else None
    if installed and CHECK not in checks:
        conflicts.append("config/project.yaml: Python-Projektprüfung fehlt oder wurde verändert.")
    if installed and ci_hash != PYTHON_CI_SHA256:
        conflicts.append(f"{CI_PATH}: Python-CI-Erweiterung fehlt oder wurde verändert.")
    if not installed and ci_hash != VERIFIED_FILES[CI_PATH]:
        conflicts.append(f"{CI_PATH}: erwartete t0003-CI-Basis ist nicht vorhanden.")
    changes = []
    for name, result in FILES.items():
        original, _ = _operation_state(root, name)
        if installed:
            if original != result:
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
        config_result = _metadata_with_module(content, version, metadata["generator_version"])
        changes.append(("config/project.yaml", "modify", config_result))
        changes.append((CI_PATH, "modify", ci + CI_EXTENSION))
        return multi_plan_target(target, version, changes, module="python"), changes

    identity = {
        "format": 4,
        "module": "python",
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
