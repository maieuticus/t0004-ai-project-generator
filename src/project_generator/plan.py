"""Read-only assessment and deterministic planning of generator metadata."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat

from .config import ConfigurationError, load_metadata

SUPPORTED_TEMPLATE_RELEASES = {"0.1.0"}
MAX_CONFIG_BYTES = 1024 * 1024
REQUIRED_FILES = ("README.md", "AGENTS.md", "docs/DV_KONZEPT.md", "docs/PROJECT_HANDOFF.md")


class PathSafetyError(ValueError):
    """The target project cannot be inspected safely."""


def _is_link(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def read_target(value: str) -> tuple[bytes, list[str]]:
    try:
        requested = Path(value).expanduser()
        if ".." in requested.parts or str(requested).startswith(("//", "\\\\")):
            raise PathSafetyError("Zielpfad darf weder '..' noch einen Netzwerkpfad enthalten.")
        if _is_link(requested):
            raise PathSafetyError("Zielprojekt darf kein Symlink oder Junction sein.")
        root = requested.resolve(strict=True)
        if not root.is_dir() or root == Path(root.anchor):
            raise PathSafetyError("Zielprojekt muss ein vorhandenes Verzeichnis außerhalb des Dateisystemwurzelverzeichnisses sein.")
        directory = root / "config"
        config = directory / "project.yaml"
        if _is_link(directory) or _is_link(config) or not directory.is_dir():
            raise PathSafetyError("config/project.yaml darf keinen Symlink oder Junction verwenden.")
        if not stat.S_ISREG(config.lstat().st_mode):
            raise PathSafetyError("config/project.yaml muss eine reguläre Datei sein.")
        flags = (os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
                 | getattr(os, "O_NONBLOCK", 0))
        fd = os.open(config, flags)
        with os.fdopen(fd, "rb") as file:
            if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
                raise PathSafetyError("config/project.yaml muss eine reguläre Datei sein.")
            content = file.read(MAX_CONFIG_BYTES + 1)
        if len(content) > MAX_CONFIG_BYTES:
            raise ConfigurationError("config/project.yaml überschreitet die zulässige Größe.")
        docs = root / "docs"
        if _is_link(docs):
            raise PathSafetyError("docs darf kein Symlink oder Junction sein.")
        missing = []
        for name in REQUIRED_FILES:
            path = root / name
            try:
                if not stat.S_ISREG(path.lstat().st_mode):
                    missing.append(name)
            except FileNotFoundError:
                missing.append(name)
        return content, missing
    except (PathSafetyError, ConfigurationError):
        raise
    except (OSError, RuntimeError, ValueError) as error:
        raise PathSafetyError("Zielprojekt oder config/project.yaml ist nicht lesbar.") from error


def assess(content: bytes, generator_version: str, missing: list[str]) -> tuple[dict[str, object], list[str], list[str]]:
    metadata = load_metadata(content)
    conflicts = [f"Pflichtdatei fehlt oder ist keine reguläre Datei: {name}" for name in missing]
    if metadata["template_release"] not in SUPPORTED_TEMPLATE_RELEASES:
        conflicts.append("template.release: Kompatibilität ist für diese Version nicht nachgewiesen.")
    if metadata["generator_version"] not in (None, generator_version):
        conflicts.append("generator.version: abweichende Version; kein automatisches Upgrade.")
    if metadata["has_modules"]:
        conflicts.append("generator.modules: Modulversionen werden in dieser Etappe nicht unterstützt.")
    warnings = []
    if metadata["sdd_tool"] is not None:
        warnings.append("sdd.version: Format geprüft; Laufzeit- und Integrationskompatibilität nicht geprüft.")
    return metadata, conflicts, warnings


def create_plan(content: bytes, generator_version: str, missing: list[str]) -> dict[str, object]:
    metadata, conflicts, warnings = assess(content, generator_version, missing)
    fingerprint = hashlib.sha256(content).hexdigest()
    operations = []
    if not conflicts and metadata["generator_version"] is None:
        operations.append({
            "path": "config/project.yaml",
            "action": "modify",
            "diff": f"- generator.version: null\n+ generator.version: {generator_version}\n",
        })
    identity = {
        "format": 1,
        "generator_version": generator_version,
        "source_fingerprint": fingerprint,
        "operations": operations,
        "conflicts": conflicts,
        "warnings": warnings,
    }
    encoded = json.dumps(identity, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")
    return {
        **identity,
        "plan_id": hashlib.sha256(encoded).hexdigest(),
        "fingerprint_scope": "config/project.yaml (raw bytes)",
        "diff_format": "semantic",
        "read_only": True,
    }


def check_prerequisites() -> list[str]:
    return [] if shutil.which("git") else ["Git wurde im PATH nicht gefunden."]
