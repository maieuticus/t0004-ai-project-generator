"""Read-only assessment and deterministic planning of generator metadata."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat

from .config import ConfigurationError, load_metadata

SUPPORTED_TEMPLATE_RELEASES = {"0.1.0"}
MAX_CONFIG_BYTES = 1024 * 1024
REQUIRED_FILES = ("README.md", "AGENTS.md", "docs/DV_KONZEPT.md", "docs/PROJECT_HANDOFF.md")
BACKUP_PREFIX = ".t0004-backup-"


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


def metadata_result(content: bytes, generator_version: str) -> bytes:
    """Replace only the validated generator version, retaining all other bytes."""
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
            match = re.fullmatch(r"(  version:)([ \t]*)(null|~)?([ \t]*)(#.*)?", body)
            if match:
                ending = line[len(body):]
                spacing, suffix = match.group(2), match.group(4)
                if match.group(5) and not suffix:
                    spacing, suffix = spacing[:1], spacing[1:] or " "
                lines[index] = (f'{match.group(1)}{spacing}"{generator_version}"'
                                f'{suffix}{match.group(5) or ""}{ending}')
                result = "".join(lines).encode("utf-8")
                load_metadata(result)
                return result
    raise ConfigurationError("config/project.yaml: generator.version kann nicht sicher geändert werden.")


def _windows_security_component(path: Path, information: int) -> str:
    import ctypes
    from ctypes import wintypes

    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi.GetFileSecurityW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p,
                                         wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    advapi.GetFileSecurityW.restype = wintypes.BOOL
    advapi.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [
        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi.ConvertSecurityDescriptorToStringSecurityDescriptorW.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    size = wintypes.DWORD()
    advapi.GetFileSecurityW(str(path), information, None, 0, ctypes.byref(size))
    if not size.value:
        raise ctypes.WinError(ctypes.get_last_error())
    data = ctypes.create_string_buffer(size.value)
    if not advapi.GetFileSecurityW(str(path), information, data, size, ctypes.byref(size)):
        raise ctypes.WinError(ctypes.get_last_error())
    output = wintypes.LPWSTR()
    if not advapi.ConvertSecurityDescriptorToStringSecurityDescriptorW(
        data, 1, information, ctypes.byref(output), None
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return output.value
    finally:
        kernel.LocalFree(ctypes.cast(output, ctypes.c_void_p))


def file_attributes(target: str) -> str:
    """Fingerprint access metadata without exporting its potentially sensitive contents."""
    path = Path(target).expanduser().resolve(strict=True) / "config" / "project.yaml"
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise PathSafetyError("config/project.yaml muss eine reguläre Datei sein.")
    attributes = {"mode": stat.S_IMODE(info.st_mode)}
    if os.name == "nt":
        descriptor = _windows_security_component(path, 7)
        attributes["security"] = hashlib.sha256(descriptor.encode("utf-8")).hexdigest()
    else:
        attributes["owner"] = info.st_uid
        attributes["group"] = info.st_gid
        if hasattr(os, "listxattr"):
            attributes["xattrs"] = {
                name: hashlib.sha256(os.getxattr(path, name, follow_symlinks=False)).hexdigest()
                for name in sorted(os.listxattr(path, follow_symlinks=False))
            }
    encoded = json.dumps(attributes, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("ascii")).hexdigest()


def choose_backup_id(content: bytes, version: str, attributes: str | None,
                     target: str | None = None) -> str:
    root = Path(target).expanduser().resolve(strict=True) if target is not None else None
    for counter in range(1024):
        seed = json.dumps([hashlib.sha256(content).hexdigest(), version, attributes, counter],
                          ensure_ascii=True, separators=(",", ":"))
        candidate = hashlib.sha256(seed.encode("ascii")).hexdigest()[:32]
        if root is None or not os.path.lexists(root / (BACKUP_PREFIX + candidate)):
            return candidate
    raise PathSafetyError("Kein freier Backup-Pfad verfügbar.")


def create_plan(content: bytes, generator_version: str, missing: list[str],
                attributes: str | None = None, backup_id: str | None = None) -> dict[str, object]:
    metadata, conflicts, warnings = assess(content, generator_version, missing)
    fingerprint = hashlib.sha256(content).hexdigest()
    operations = []
    backup = None
    if not conflicts and metadata["generator_version"] is None:
        result = metadata_result(content, generator_version)
        operations.append({
            "path": "config/project.yaml",
            "action": "modify",
            "diff": f"- generator.version: null\n+ generator.version: {generator_version}\n",
            "before_sha256": fingerprint,
            "after_sha256": hashlib.sha256(result).hexdigest(),
            "before_attributes": attributes,
        })
        backup_id = backup_id or choose_backup_id(content, generator_version, attributes)
        directory = BACKUP_PREFIX + backup_id
        backup = {
            "id": backup_id,
            "directory": directory,
            "original": f"{directory}/original",
            "manifest": f"{directory}/manifest.json",
            "temporary": f"{directory}/stage",
            "before": "not_exists",
            "original_sha256": fingerprint,
        }
    identity = {
        "format": 2,
        "generator_version": generator_version,
        "source_fingerprint": fingerprint,
        "operations": operations,
        "backup": backup,
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
