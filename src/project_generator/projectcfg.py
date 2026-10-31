"""Minimal reader/writer for config/project.yaml; standard library only.

The file deliberately uses a simple subset of YAML (two-level scalars and one
JSON list per line under `checks`) so no package installation is required.
Edits replace single lines, which preserves comments and the rest of the file.
"""

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config" / "project.yaml"


def read_text(path: Path = CONFIG) -> str:
    return path.read_text(encoding="utf-8")


def _scalar(raw: str):
    value = re.sub(r"\s+#.*$", "", raw).strip()
    if value in {"", "null", "~"}:
        return None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1] or None
    return value


def _section_range(lines: list[str], section: str) -> tuple[int, int]:
    start = next((i for i, line in enumerate(lines) if re.fullmatch(rf"{re.escape(section)}:\s*(#.*)?", line)), None)
    if start is None:
        raise ValueError(f"config/project.yaml: Abschnitt '{section}' fehlt.")
    end = start + 1
    while end < len(lines) and (not lines[end].strip() or lines[end].startswith((" ", "#"))):
        end += 1
    return start, end


def get(text: str, section: str, key: str):
    lines = text.splitlines()
    start, end = _section_range(lines, section)
    for line in lines[start + 1:end]:
        match = re.fullmatch(rf"  {re.escape(key)}:(.*)", line)
        if match:
            return _scalar(match.group(1))
    raise ValueError(f"config/project.yaml: '{section}.{key}' fehlt.")


def set_value(text: str, section: str, key: str, value: str | None) -> str:
    lines = text.splitlines()
    start, end = _section_range(lines, section)
    rendered = "null" if value is None else json.dumps(value, ensure_ascii=False)
    for index in range(start + 1, end):
        if re.fullmatch(rf"  {re.escape(key)}:.*", lines[index]):
            lines[index] = f"  {key}: {rendered}"
            return "\n".join(lines) + "\n"
    raise ValueError(f"config/project.yaml: '{section}.{key}' fehlt.")


def checks(text: str) -> list[list[str]]:
    result = []
    in_checks = False
    for line in text.splitlines():
        if re.fullmatch(r"checks:\s*(\[\s*\])?\s*(#.*)?", line):
            in_checks = line.split("#")[0].strip() == "checks:"
            continue
        if in_checks:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            match = re.fullmatch(r"  - (\[.*\])\s*", line)
            if not match:
                if line.startswith(" "):
                    raise ValueError(f"config/project.yaml: ungültiger Eintrag in 'checks': {line.strip()}")
                break
            command = json.loads(match.group(1))
            if not command or not all(isinstance(part, str) for part in command):
                raise ValueError("Jede Prüfung muss eine nicht leere Liste von Strings sein.")
            result.append(command)
    return result
