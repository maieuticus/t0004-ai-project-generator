"""Validate the supported subset of the canonical project metadata."""

import json
import re

from . import projectcfg

VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")
SECTIONS = {
    "project": {"name"},
    "template": {"source", "release", "base_commit", "last_update_check"},
    "sdd": {"tool", "version"},
    "generator": {"version", "modules"},
}
TEMPLATE_SOURCE = "https://github.com/maieuticus/t0003-ai-project-template"
SCALAR = re.compile(r'''(?: "(?:[^"\\]|\\.)*" | '[^']*' | [^\[\]{}"'\r\n]* )\s*(?:\s\#.*)?''', re.VERBOSE)


class ConfigurationError(ValueError):
    """Canonical project metadata is invalid or cannot be read."""


def _validate_structure(text: str) -> None:
    seen: dict[str, set[str]] = {}
    section = None
    schema_seen = False
    checks_seen = False
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        top = re.fullmatch(r"([a-z_]+):(?:\s*(.*?)\s*)?", line)
        if top:
            key, value = top.groups()
            value = (value or "").split("#", 1)[0].strip()
            if key == "schema_version":
                if schema_seen or value != "1":
                    raise ConfigurationError("config/project.yaml: schema_version muss eindeutig 1 sein.")
                schema_seen, section = True, None
            elif key == "checks":
                if checks_seen or value not in {"", "[]"}:
                    raise ConfigurationError("config/project.yaml: checks ist ungültig oder doppelt.")
                checks_seen, section = True, "checks" if not value else None
            elif key in SECTIONS and not value and key not in seen:
                seen[key], section = set(), key
            else:
                raise ConfigurationError("config/project.yaml: unbekannter, doppelter oder ungültiger Abschnitt.")
            continue
        entry = re.fullmatch(r"  ([a-z_]+):(.*)", line)
        if section in SECTIONS and entry:
            key = entry.group(1)
            if key not in SECTIONS[section] or key in seen[section]:
                raise ConfigurationError(f"config/project.yaml: ungültiger oder doppelter Schlüssel in {section}.")
            value = entry.group(2).strip()
            if (section, key) != ("generator", "modules") and (
                not SCALAR.fullmatch(value) or (not value.startswith(("'", '"')) and re.search(r":\s", value))
            ):
                raise ConfigurationError(f"config/project.yaml: ungültiger Skalar in {section}.")
            if (section, key) != ("generator", "modules") and value.startswith('"'):
                quoted = re.match(r'^("(?:[^"\\]|\\.)*")', value)
                try:
                    json.loads(quoted.group(1))
                except (AttributeError, json.JSONDecodeError) as error:
                    raise ConfigurationError(f"config/project.yaml: ungültiger String in {section}.") from error
            seen[section].add(key)
        elif section == "checks" and re.fullmatch(r"  - \[.*\]\s*", line):
            try:
                command = json.loads(line.strip()[2:])
            except json.JSONDecodeError as error:
                raise ConfigurationError("config/project.yaml: ungültiger checks-Eintrag.") from error
            if not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
                raise ConfigurationError("config/project.yaml: checks benötigt nicht leere Listen von Strings.")
        else:
            raise ConfigurationError("config/project.yaml: ungültiges oder nicht unterstütztes Format.")
    if not schema_seen or not checks_seen or set(seen) != set(SECTIONS):
        raise ConfigurationError("config/project.yaml: Pflichtabschnitt oder schema_version fehlt.")
    if any(seen[section] != keys for section, keys in SECTIONS.items()):
        raise ConfigurationError("config/project.yaml: erforderlicher Metadatenschlüssel fehlt.")


def load_metadata(content: bytes) -> dict[str, object]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ConfigurationError("config/project.yaml muss UTF-8 sein.") from error
    _validate_structure(text)
    try:
        projectcfg.checks(text)
        get = lambda section, key: projectcfg.get(text, section, key)
        name = get("project", "name")
        source = get("template", "source")
        release = get("template", "release")
        tool = get("sdd", "tool")
        tool_version = get("sdd", "version")
        generator_version = get("generator", "version")
        modules = json.loads(get("generator", "modules") or "null")
    except (ValueError, TypeError) as error:
        raise ConfigurationError("config/project.yaml enthält ungültige Werte oder Prüfungen.") from error

    if name and len(name) > 200:
        raise ConfigurationError("config/project.yaml: project.name ist zu lang.")
    if source != TEMPLATE_SOURCE:
        raise ConfigurationError("config/project.yaml: template.source ist nicht die freigegebene t0003-Basis.")
    if not release or not VERSION.fullmatch(release):
        raise ConfigurationError("config/project.yaml: template.release muss MAJOR.MINOR.PATCH sein.")
    if tool not in {None, "speckit", "openspec"}:
        raise ConfigurationError("config/project.yaml: sdd.tool muss speckit, openspec oder null sein.")
    if (tool is None) != (tool_version is None):
        raise ConfigurationError("config/project.yaml: sdd.tool und sdd.version müssen gemeinsam gesetzt sein.")
    if tool_version and not VERSION.fullmatch(tool_version):
        raise ConfigurationError("config/project.yaml: sdd.version muss MAJOR.MINOR.PATCH sein.")
    if generator_version is not None and not VERSION.fullmatch(generator_version):
        raise ConfigurationError("config/project.yaml: generator.version muss null oder MAJOR.MINOR.PATCH sein.")
    if not isinstance(modules, list):
        raise ConfigurationError("config/project.yaml: generator.modules muss eine JSON-Liste sein.")
    return {
        "template_release": release,
        "sdd_tool": tool,
        "sdd_version": tool_version,
        "generator_version": generator_version,
        "has_modules": bool(modules),
    }
