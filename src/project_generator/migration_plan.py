"""Bounded, non-executable strategy A planning for explicitly selected files."""

import hashlib
import os
from pathlib import Path
import stat

from .migrate import EXCLUDED, _root
from .plan import (MAX_CONFIG_BYTES, PathSafetyError, _canonical_id, _directory_states,
                   _location_fingerprint, _operation_paths, _portable_path_collisions,
                   assess, path_attributes, read_target)
from .python_compat import python_capabilities

EXTENSIONS = {".md", ".txt", ".py", ".ts"}
CONFIG_NAMES = {"requirements.txt", "constraints.txt", "pipfile", "dockerfile",
                "setup.py", "settings.py", "config.py", "conftest.py"}


def _state(root: Path, name: str, *, text_only: bool = False) -> dict[str, object] | None:
    path = root.joinpath(*name.split("/"))
    try:
        before = path.lstat()
    except FileNotFoundError:
        return None
    if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
            or before.st_dev != root.stat().st_dev):
        raise PathSafetyError("Datei ist kein unterstütztes reguläres Einzeldateiziel.")
    attributes = path_attributes(path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(path, flags), "rb") as file:
        opened = os.fstat(file.fileno())
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise PathSafetyError("Datei wurde während der Planung verändert.")
        content = file.read(MAX_CONFIG_BYTES + 1)
        after = os.fstat(file.fileno())
    final = path.lstat()
    def identity(info):
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
                info.st_ctime_ns if os.name != "nt" else None)
    if identity(before) != identity(opened) or identity(opened) != identity(after) or identity(after) != identity(final):
        raise PathSafetyError("Datei wurde während der Planung verändert.")
    if len(content) > MAX_CONFIG_BYTES:
        raise PathSafetyError("Datei überschreitet die zulässige Größe.")
    if text_only:
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise PathSafetyError("Quelldatei ist kein unterstützter UTF-8-Text.") from error
        if b"\x00" in content:
            raise PathSafetyError("Quelldatei ist kein unterstützter UTF-8-Text.")
    if path_attributes(path) != attributes:
        raise PathSafetyError("Dateizugriff wurde während der Planung verändert.")
    return {"sha256": hashlib.sha256(content).hexdigest(), "attributes": attributes, "size": len(content)}


def migration_plan(source: str, target: str, selected: list[str], version: str) -> dict[str, object]:
    source_root, target_root = _root(source), _root(target)
    if (os.path.samefile(source_root, target_root) or source_root in target_root.parents
            or target_root in source_root.parents):
        raise PathSafetyError("Quelle und Ziel dürfen sich nicht überschneiden.")
    ordered = _operation_paths([(name, "create", b"") for name in selected])
    names = [name for name, _, _ in ordered]
    for name in names:
        parts = name.split("/")
        if (any(part.startswith(".") or part.casefold() in EXCLUDED or part.casefold() == "config" for part in parts)
                or parts[-1].casefold() in CONFIG_NAMES or parts[-1].casefold().startswith(("requirements", "constraints"))
                or Path(name).suffix.lower() not in EXTENSIONS):
            raise PathSafetyError("Dateiauswahl enthält einen ausgeschlossenen Pfad oder Dateityp.")
    content, missing = read_target(str(target_root))
    config_attributes = path_attributes(target_root / "config" / "project.yaml")
    _, conflicts, warnings = assess(content, version, missing)
    capabilities = python_capabilities(str(target_root))
    conflicts.extend(capabilities["conflicts"])
    source_dirs = _directory_states(source_root, names)
    target_dirs = _directory_states(target_root, names)
    if len(source_dirs) > 64 or len(target_dirs) > 64:
        raise PathSafetyError("Dateiauswahl betrifft zu viele Verzeichnisse.")
    if _portable_path_collisions(source_root, names) or _portable_path_collisions(target_root, names):
        raise PathSafetyError("Dateiauswahl kollidiert auf anderen Plattformen.")
    operations = []
    total = 0
    for name in names:
        src = _state(source_root, name, text_only=True)
        dst = _state(target_root, name)
        if src is None:
            raise PathSafetyError("Eine ausgewählte Quelldatei fehlt oder ist nicht lesbar.")
        total += src["size"]
        if total > 8 * MAX_CONFIG_BYTES:
            raise PathSafetyError("Dateiauswahl überschreitet die zulässige Gesamtgröße.")
        if dst is not None:
            conflicts.append(f"Zieldatei bereits vorhanden: {name}")
        operations.append({"path": name, "action": "create", "source": src, "target": dst})
    if (read_target(str(target_root)) != (content, missing)
            or path_attributes(target_root / "config" / "project.yaml") != config_attributes
            or python_capabilities(str(target_root)) != capabilities
            or _directory_states(source_root, names) != source_dirs
            or _directory_states(target_root, names) != target_dirs
            or any(_state(source_root, op["path"], text_only=True) != op["source"]
                   or _state(target_root, op["path"]) != op["target"] for op in operations)):
        raise PathSafetyError("Projektzustand wurde während der Planung verändert.")
    identity = {
        "kind": "strategy_a_migration_plan", "plan_version": 1, "read_only": True,
        "executable": False, "generator_version": version,
        "source_project": _location_fingerprint(source_root),
        "target_project": _location_fingerprint(target_root),
        "target_config_sha256": hashlib.sha256(content).hexdigest(),
        "target_config_attributes": config_attributes,
        "source_directories": source_dirs, "target_directories": target_dirs,
        "target_preconditions": {"files": capabilities["files"], "directories": capabilities["directories"]},
        "operations": operations, "conflicts": conflicts,
        "warnings": warnings + ["Nur lesend; keine Übernahme, kein Apply und kein Restore verfügbar.",
                                "Auswahl und Inhalte manuell auf vertrauliche Daten prüfen."],
    }
    return {**identity, "plan_id": _canonical_id(identity)}
