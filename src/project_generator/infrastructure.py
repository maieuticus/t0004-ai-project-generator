"""Internal fixed Docker Compose infrastructure planning for PR A."""

import hashlib
import hmac
import json
import re
from pathlib import Path

from . import projectcfg
from .config import ConfigurationError
from .infrastructure_states import (
    DOCKER_COMPOSE, POSTGRESQL, INFRASTRUCTURE, POSTGRESQL_PROJECTION,
    docker_projection_with_ci, valid_infrastructure,
)
from .docker_files import docker_files
from .module_states import CI_STATES, MODULES
from .plan import (
    PathSafetyError, _canonical_id, _directory_states, _location_fingerprint, _operation_state, _portable_path_collisions,
    backup_store, file_attributes, multi_plan_target, read_target, assess,
)
from .python_module import CHECKS, CI_PATH, _files_for, _matches_module_file
from .transaction import TransactionError, apply_multi
from .postgresql_files import POSTGRES_GITIGNORES, postgresql_gitignore


def _metadata_with_infrastructure(content: bytes, infrastructure: str) -> bytes:
    """Add or replace the canonical infrastructure list without changing other config bytes."""
    lines = content.decode("utf-8").splitlines(keepends=True)
    generator_start = next(
        (index for index, line in enumerate(lines)
         if re.fullmatch(r"generator:\s*(#.*)?", line.rstrip("\r\n"))),
        None,
    )
    if generator_start is None:
        raise ConfigurationError("config/project.yaml: generator.infrastructure kann nicht sicher geändert werden.")
    generator_end = next(
        (index for index in range(generator_start + 1, len(lines))
         if (body := lines[index].rstrip("\r\n")) and not body.startswith((" ", "#"))),
        len(lines),
    )
    module_index = None
    infrastructure_index = None
    for index in range(generator_start + 1, generator_end):
        body = lines[index].rstrip("\r\n")
        if re.fullmatch(r"  modules:[ \t]*(\[[^\]\r\n]*\])(?:[ \t]*(?:#.*)?)?", body):
            module_index = index
        if re.fullmatch(r"  infrastructure:[ \t]*(\[[^\]\r\n]*\])(?:[ \t]*(?:#.*)?)?", body):
            infrastructure_index = index
    if module_index is None:
        raise ConfigurationError("config/project.yaml: generator.infrastructure kann nicht sicher geändert werden.")
    from .config import load_metadata
    metadata = load_metadata(content)
    existing = metadata["infrastructure"]
    if infrastructure not in INFRASTRUCTURE or not valid_infrastructure(existing, metadata["modules"]):
        raise ConfigurationError("config/project.yaml: ungültiger Infrastrukturzustand.")
    selected = [value for value in INFRASTRUCTURE.values()
                if value in existing or value == INFRASTRUCTURE[infrastructure]]
    if not valid_infrastructure(selected, metadata["modules"]):
        raise ConfigurationError("config/project.yaml: Infrastrukturabhängigkeit fehlt.")
    value = json.dumps(selected)
    if infrastructure_index is not None:
        line = lines[infrastructure_index]
        body = line.rstrip("\r\n")
        match = re.fullmatch(r"(  infrastructure:)[ \t]*(\[[^\]\r\n]*\])([ \t]*(?:#.*)?)", body)
        if match is None:
            raise ConfigurationError("config/project.yaml: generator.infrastructure kann nicht sicher geändert werden.")
        lines[infrastructure_index] = f"{match.group(1)} {value}{match.group(3)}{line[len(body):]}"
    else:
        newline = "\r\n" if "\r\n" in content.decode("utf-8") else "\n"
        lines.insert(module_index + 1, f"  infrastructure: {value}{newline}")
    result = "".join(lines).encode("utf-8")
    load_metadata(result)
    return result


def _language_preconditions(root: Path, modules: frozenset[str]) -> tuple[dict[str, object], list[str]]:
    """Bind the known language installation before Docker state can be recorded."""
    conflicts = []
    files = []
    checks = projectcfg.checks((root / "config/project.yaml").read_text(encoding="utf-8"))
    ci, ci_attributes = _operation_state(root, CI_PATH)
    if ci != CI_STATES[modules]:
        conflicts.append(f"{CI_PATH}: geprüfter Sprach-CI-Zustand fehlt oder wurde verändert.")
    else:
        files.append({
            "path": CI_PATH,
            "sha256": hashlib.sha256(ci).hexdigest(),
            "attributes": ci_attributes,
        })
    for module in MODULES:
        if module not in modules:
            continue
        if CHECKS[module] not in checks:
            conflicts.append(f"config/project.yaml: {module}-Projektprüfung fehlt oder wurde verändert.")
        for name, result in _files_for(module).items():
            original, attributes = _operation_state(root, name)
            if not _matches_module_file(module, name, original, result):
                conflicts.append(f"{name}: vorhandenes {module}-Modul fehlt oder wurde verändert.")
                continue
            files.append({
                "path": name,
                "sha256": hashlib.sha256(original).hexdigest(),
                "attributes": attributes,
            })
    files.sort(key=lambda state: state["path"].lower())
    return {
        "files": files,
        "directories": _directory_states(root, [state["path"] for state in files]),
    }, conflicts


def _docker_preconditions(root: Path, modules: frozenset[str]) -> tuple[dict[str, object], list[str]]:
    """Bind the complete known Docker projection before PostgreSQL extends it."""
    preconditions, conflicts = _language_preconditions(root, modules)
    files = {state["path"]: state for state in preconditions["files"]}
    for name, result in docker_files(modules).items():
        existing, attributes = _operation_state(root, name)
        if existing != result:
            conflicts.append(f"{name}: Docker-Datei fehlt oder wurde verändert.")
            continue
        files[name] = {
            "path": name,
            "sha256": hashlib.sha256(existing).hexdigest(),
            "attributes": attributes,
        }
    return {
        "files": sorted(files.values(), key=lambda state: state["path"].lower()),
        "directories": _directory_states(root, list(files)),
    }, conflicts


def _empty_plan(target: str, version: str, content: bytes, warnings: list[str], conflicts: list[str],
                preconditions: dict[str, object], projection: list[str],
                infrastructure: str) -> dict[str, object]:
    root = Path(target).expanduser().resolve(strict=True)
    identity = {
        "format": 4,
        "infrastructure": infrastructure,
        "generator_version": version,
        "source_sha256": hashlib.sha256(content).hexdigest(),
        "source_attributes": file_attributes(target),
        "project_fingerprint": _location_fingerprint(root),
        "storage_fingerprint": _location_fingerprint(backup_store(target)),
        "preconditions": preconditions,
        "projection": projection,
        "operations": [],
        "directories": [],
        "backup": None,
        "warnings": warnings,
        "conflicts": conflicts,
    }
    return {**identity, "plan_id": _canonical_id(identity), "read_only": True}


def infrastructure_plan_target(target: str, version: str, infrastructure: str = DOCKER_COMPOSE,
                               backup_id: str | None = None) -> tuple[dict[str, object], list[tuple[str, str, bytes]]]:
    """Plan a fixed infrastructure projection without Docker execution."""
    if infrastructure not in INFRASTRUCTURE:
        raise ConfigurationError("Unbekannte feste Infrastruktur.")
    content, missing = read_target(target)
    metadata, conflicts, warnings = assess(
        content, version, missing, allow_postgresql=infrastructure == POSTGRESQL,
    )
    root = Path(target).expanduser().resolve(strict=True)
    modules = frozenset(name for name, value in MODULES.items() if value in metadata["modules"])
    projection = (
        list(POSTGRESQL_PROJECTION)
        if infrastructure == POSTGRESQL
        else list(docker_projection_with_ci(modules)) if modules else []
    )
    if not modules:
        conflicts.append("docker-compose@0.1.0 benötigt mindestens ein installiertes Sprachmodul.")
        return _empty_plan(target, version, content, warnings, conflicts, {"files": [], "directories": []},
                           projection, infrastructure), []
    if infrastructure == POSTGRESQL and INFRASTRUCTURE[DOCKER_COMPOSE] not in metadata["infrastructure"]:
        conflicts.append("postgresql@0.1.0 benötigt docker-compose@0.1.0.")
        return _empty_plan(target, version, content, warnings, conflicts, {"files": [], "directories": []},
                           projection, infrastructure), []
    installed = INFRASTRUCTURE[infrastructure] in metadata["infrastructure"]
    if infrastructure == POSTGRESQL and not installed:
        preconditions, dependency_conflicts = _docker_preconditions(root, modules)
    else:
        preconditions, dependency_conflicts = _language_preconditions(root, modules)
    conflicts.extend(dependency_conflicts)
    files = docker_files(modules, postgresql=infrastructure == POSTGRESQL)
    projection_paths = [*files, ".gitignore"] if infrastructure == POSTGRESQL else list(files)
    for name in _portable_path_collisions(root, projection_paths):
        conflicts.append(f"{name}: Pfad kollidiert auf anderen Plattformen.")
    if infrastructure == DOCKER_COMPOSE:
        for name, result in files.items():
            existing, _ = _operation_state(root, name)
            if installed and existing != result:
                conflicts.append(f"{name}: Docker-Datei fehlt oder wurde verändert.")
            elif not installed and existing is not None:
                conflicts.append(f"{name}: vorhandene Docker-Projektion wird nicht überschrieben.")
    else:
        base_files = docker_files(modules)
        for name, result in files.items():
            existing, _ = _operation_state(root, name)
            if installed and existing != result:
                conflicts.append(f"{name}: PostgreSQL-Projektion fehlt oder wurde verändert.")
            elif not installed and name not in base_files and existing is not None:
                conflicts.append(f"{name}: vorhandene PostgreSQL-Projektion wird nicht überschrieben.")
        existing_ignore, _ = _operation_state(root, ".gitignore")
        expected_ignore = POSTGRES_GITIGNORES[-1] if installed else POSTGRES_GITIGNORES[0]
        if existing_ignore != expected_ignore:
            conflicts.append(".gitignore: geprüfter Zustand für das lokale PostgreSQL-Secret fehlt oder wurde verändert.")
    if installed or conflicts:
        return _empty_plan(target, version, content, warnings, conflicts, preconditions, projection,
                           infrastructure), []
    result = _metadata_with_infrastructure(content, infrastructure)
    if infrastructure == DOCKER_COMPOSE:
        changes = [("config/project.yaml", "modify", result)] + [
            (name, "create", data) for name, data in files.items()
        ]
    else:
        base_files = docker_files(modules)
        changes = [("config/project.yaml", "modify", result)]
        changes.extend(
            (name, "create" if name not in base_files else "modify", data)
            for name, data in files.items()
            if base_files.get(name) != data
        )
        changes.append((".gitignore", "modify", postgresql_gitignore(existing_ignore)))
    return multi_plan_target(
        target, version, changes, backup_id, infrastructure=infrastructure,
        preconditions=preconditions, projection=projection,
    ), changes


def apply_infrastructure(target: str, supplied: dict, confirmation: str, version: str,
                         infrastructure: str = DOCKER_COMPOSE) -> str:
    """Apply a trusted fixed infrastructure plan with the existing Format-4 engine."""
    expected, changes = infrastructure_plan_target(target, version, infrastructure)
    if expected["conflicts"] or not changes:
        raise TransactionError("Infrastrukturplan enthält Konflikte oder keine ausführbare Operation.")

    def validate() -> None:
        fresh, fresh_changes = infrastructure_plan_target(
            target, version, infrastructure, expected["backup"]["id"],
        )
        if (fresh != supplied or fresh_changes != changes
                or not hmac.compare_digest(confirmation, fresh["plan_id"])):
            raise TransactionError("Infrastrukturplan ist verändert, veraltet oder nicht bestätigt.")

    return apply_multi(
        target, supplied, confirmation, version, changes, infrastructure=infrastructure,
        preconditions=expected["preconditions"], projection=expected["projection"], preflight=validate,
    )
