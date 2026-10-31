"""Read-only assessment and deterministic planning of generator metadata."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat

from .config import ConfigurationError, VERSION, load_metadata

SUPPORTED_TEMPLATE_RELEASES = {"0.1.0"}
MAX_CONFIG_BYTES = 1024 * 1024
REQUIRED_FILES = ("README.md", "AGENTS.md", "docs/DV_KONZEPT.md", "docs/PROJECT_HANDOFF.md")
BACKUP_PREFIX = ".t0004-backup-"
CODESPACES_DATA_HOME = Path("/workspaces/.t0004-data")


class PathSafetyError(ValueError):
    """The target project cannot be inspected safely."""


def backup_store(target: str) -> Path:
    override = os.environ.get("T0004_BACKUP_HOME")
    if override:
        base = Path(override)
    elif os.name == "nt":
        configured = os.environ.get("LOCALAPPDATA")
        base = Path(configured) if configured else Path.home() / "AppData" / "Local"
    elif os.environ.get("CODESPACES", "").lower() == "true":
        base = CODESPACES_DATA_HOME
    else:
        configured = os.environ.get("XDG_DATA_HOME")
        base = Path(configured) if configured else Path.home() / ".local" / "share"
    if not base.is_absolute() or ".." in base.parts or str(base).startswith(("//", "\\\\")):
        raise PathSafetyError("Der lokale Backup-Speicher muss ein absoluter lokaler Pfad ohne '..' sein.")
    candidate = base / "t0004-generator" / "backups"
    for path in (candidate, *candidate.parents):
        if _is_link(path):
            raise PathSafetyError("Der Backup-Speicher darf keine Symlinks oder Junctions verwenden.")
    store = candidate.resolve(strict=False)
    root = Path(target).expanduser().resolve(strict=True)
    if store == root or store.is_relative_to(root) or root.is_relative_to(store):
        raise PathSafetyError("Der Backup-Speicher muss außerhalb des Zielprojekts liegen.")
    for parent in (store, *store.parents):
        if os.path.lexists(parent / ".git"):
            raise PathSafetyError("Der Backup-Speicher darf nicht in einem Git-Arbeitsverzeichnis liegen.")
    return store


def _location_fingerprint(path: Path) -> str:
    return hashlib.sha256(os.fsencode(os.path.normcase(str(path)))).hexdigest()


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
                if len(result) > MAX_CONFIG_BYTES:
                    raise ConfigurationError("config/project.yaml überschreitet nach der Änderung die zulässige Größe.")
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


def _windows_check_streams(path: Path) -> None:
    import ctypes
    from ctypes import wintypes

    class StreamData(ctypes.Structure):
        _fields_ = [("size", ctypes.c_longlong), ("name", wintypes.WCHAR * 296)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.FindFirstStreamW.argtypes = [wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(StreamData), wintypes.DWORD]
    kernel.FindFirstStreamW.restype = wintypes.HANDLE
    kernel.FindNextStreamW.argtypes = [wintypes.HANDLE, ctypes.POINTER(StreamData)]
    kernel.FindNextStreamW.restype = wintypes.BOOL
    kernel.FindClose.argtypes = [wintypes.HANDLE]
    kernel.FindClose.restype = wintypes.BOOL
    data = StreamData()
    handle = kernel.FindFirstStreamW(str(path), 0, ctypes.byref(data), 0)
    if handle == ctypes.c_void_p(-1).value:
        raise PathSafetyError("Windows-Dateistreams können nicht sicher geprüft werden.")
    try:
        while True:
            if data.name != "::$DATA":
                raise PathSafetyError("Zusätzliche Windows-Dateistreams werden nicht unterstützt.")
            if not kernel.FindNextStreamW(handle, ctypes.byref(data)):
                if ctypes.get_last_error() != 38:
                    raise PathSafetyError("Windows-Dateistreams können nicht sicher geprüft werden.")
                break
    finally:
        kernel.FindClose(handle)


def path_attributes(path: Path, *, directory: bool = False) -> str:
    """Fingerprint access metadata without exporting its potentially sensitive contents."""
    info = path.lstat()
    if (not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
            or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)):
        raise PathSafetyError("Pfad ist keine sichere reguläre Datei oder kein sicheres Verzeichnis.")
    attributes = {"mode": stat.S_IMODE(info.st_mode)}
    if os.name == "nt":
        if not directory and info.st_nlink != 1:
            raise PathSafetyError("Windows-Dateien mit mehreren oder unbekannten Hardlinks werden nicht unterstützt.")
        supported_flags = 0x2 | 0x4 | 0x20 | 0x80 | 0x100 | 0x2000
        if not directory and info.st_file_attributes & ~supported_flags:
            raise PathSafetyError("Windows-Dateiattribute werden für sichere Ersetzung nicht unterstützt.")
        if not directory:
            _windows_check_streams(path)
        attributes["file_flags"] = info.st_file_attributes
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


def file_attributes(target: str) -> str:
    path = Path(target).expanduser().resolve(strict=True) / "config" / "project.yaml"
    return path_attributes(path)


def choose_backup_id(content: bytes, version: str, attributes: str | None,
                     target: str | None = None) -> str:
    store = backup_store(target) if target is not None else None
    project = _location_fingerprint(Path(target).expanduser().resolve(strict=True)) if target is not None else None
    for counter in range(1024):
        seed = json.dumps([hashlib.sha256(content).hexdigest(), version, attributes, project, counter],
                          ensure_ascii=True, separators=(",", ":"))
        candidate = hashlib.sha256(seed.encode("ascii")).hexdigest()[:32]
        if store is None or not os.path.lexists(store / (BACKUP_PREFIX + candidate)):
            return candidate
    raise PathSafetyError("Kein freier Backup-Pfad verfügbar.")


def create_plan(content: bytes, generator_version: str, missing: list[str],
                attributes: str | None = None, backup_id: str | None = None,
                project_fingerprint: str | None = None, storage_fingerprint: str | None = None,
                legacy_backups: bool = False) -> dict[str, object]:
    metadata, conflicts, warnings = assess(content, generator_version, missing)
    if legacy_backups:
        conflicts.append("Altes Backup im Zielprojekt: vor Git-Operationen geschützt außerhalb sichern.")
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
            "recovery": f"{directory}/recovery.json",
            "recovery_temporary": f"{directory}/recovery.tmp",
            "before": "not_exists",
            "original_sha256": fingerprint,
        }
    identity = {
        "format": 3,
        "generator_version": generator_version,
        "source_fingerprint": fingerprint,
        "project_fingerprint": project_fingerprint,
        "storage_fingerprint": storage_fingerprint,
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


def plan_target(target: str, generator_version: str, backup_id: str | None = None) -> tuple[bytes, dict[str, object]]:
    content, missing = read_target(target)
    attributes = file_attributes(target)
    store = backup_store(target)
    root = Path(target).expanduser().resolve(strict=True)
    legacy_backups = any(re.fullmatch(r"\.t0004-backup-[0-9a-f]{32}", entry.name, re.IGNORECASE)
                         for entry in root.iterdir())
    if backup_id is None:
        backup_id = choose_backup_id(content, generator_version, attributes, target)
    return content, create_plan(content, generator_version, missing, attributes, backup_id,
                                _location_fingerprint(root), _location_fingerprint(store), legacy_backups)


def _relative_operation_path(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 240:
        raise PathSafetyError("Ungültiger relativer Operationspfad.")
    parts = value.split("/")
    if len(parts) > 16:
        raise PathSafetyError("Operationspfad ist zu tief verschachtelt.")
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10))}
    for part in parts:
        if (not part or part in {".", ".."} or part.endswith((" ", "."))
                or len(part) > 255 or not re.fullmatch(r"[A-Za-z0-9_. -]+", part)
                or part.casefold() == ".git" or part.split(".", 1)[0].upper() in reserved):
            raise PathSafetyError("Unsicherer relativer Operationspfad.")
    return value


def _operation_paths(changes: list[tuple[str, str, bytes]]) -> list[tuple[str, str, bytes]]:
    if not isinstance(changes, list) or not 1 <= len(changes) <= 32:
        raise PathSafetyError("Eine Transaktion benötigt zwischen 1 und 32 Operationen.")
    ordered = []
    for change in changes:
        if not isinstance(change, tuple) or len(change) != 3:
            raise PathSafetyError("Ungültige Operation.")
        name, action, content = change
        name = _relative_operation_path(name)
        if (not isinstance(action, str) or action not in {"create", "modify"}
                or not isinstance(content, bytes) or len(content) > MAX_CONFIG_BYTES):
            raise PathSafetyError("Ungültige Operation oder zu großer Dateiinhalt.")
        ordered.append((name, action, content))
    ordered.sort(key=lambda item: item[0].lower())
    keys = [name.lower() for name, _, _ in ordered]
    key_set = set(keys)
    if (len(key_set) != len(keys)
            or any("/".join(key.split("/")[:index]) in key_set
                   for key in keys for index in range(1, len(key.split("/"))))):
        raise PathSafetyError("Operationspfade sind doppelt oder überschneiden sich.")
    spellings = {}
    for name, _, _ in ordered:
        parts = name.split("/")
        for index in range(1, len(parts) + 1):
            part = "/".join(parts[:index])
            previous = spellings.setdefault(part.lower(), part)
            if previous != part:
                raise PathSafetyError("Operationspfade kollidieren auf anderen Plattformen.")
    if sum(len(content) for _, _, content in ordered) > 8 * MAX_CONFIG_BYTES:
        raise PathSafetyError("Die geplanten Dateiinhalte überschreiten die zulässige Gesamtgröße.")
    return ordered


def _directory_states(root: Path, names: list[str]) -> list[dict[str, str | None]]:
    directories = {"."}
    for name in names:
        parts = name.split("/")[:-1]
        directories.update("/".join(parts[:index]) for index in range(1, len(parts) + 1))
    states = []
    root_device = root.lstat().st_dev
    for name in sorted(directories, key=lambda value: (value.count("/"), value.lower())):
        path = root if name == "." else root.joinpath(*name.split("/"))
        try:
            attributes = path_attributes(path, directory=True)
            if path.lstat().st_dev != root_device:
                raise PathSafetyError("Dateisystemgrenzen innerhalb des Projekts werden nicht unterstützt.")
        except FileNotFoundError:
            attributes = None
        states.append({"path": name, "before_attributes": attributes})
    return states


def _operation_state(root: Path, name: str) -> tuple[bytes | None, str | None]:
    path = root.joinpath(*name.split("/"))
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None, None
    if info.st_dev != root.lstat().st_dev:
        raise PathSafetyError("Dateisystemgrenzen innerhalb des Projekts werden nicht unterstützt.")
    if info.st_nlink != 1:
        raise PathSafetyError("Dateien mit mehreren oder unbekannten Hardlinks werden nicht unterstützt.")
    attributes = path_attributes(path)
    flags = (os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
             | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(os.open(path, flags), "rb") as file:
        if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
            raise PathSafetyError("Operationsziel ist keine reguläre Datei.")
        content = file.read(MAX_CONFIG_BYTES + 1)
    if len(content) > MAX_CONFIG_BYTES:
        raise PathSafetyError("Operationsziel überschreitet die zulässige Größe.")
    return content, attributes


def _canonical_id(identity: dict[str, object]) -> str:
    encoded = json.dumps(identity, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def multi_plan_target(target: str, generator_version: str, changes: list[tuple[str, str, bytes]],
                      backup_id: str | None = None) -> dict[str, object]:
    """Build an internal format-4 plan from trusted, already-rendered operations."""
    if not isinstance(generator_version, str) or not VERSION.fullmatch(generator_version):
        raise PathSafetyError("Ungültige Generatorversion.")
    content, missing = read_target(target)
    _, conflicts, warnings = assess(content, generator_version, missing)
    if conflicts:
        raise PathSafetyError("Projektkonflikte verhindern die Planung.")
    ordered = _operation_paths(changes)
    root = Path(target).expanduser().resolve(strict=True)
    store = backup_store(target)
    if any(re.fullmatch(r"\.t0004-backup-[0-9a-f]{32}", entry.name, re.IGNORECASE)
           for entry in root.iterdir()):
        raise PathSafetyError("Altes Backup im Zielprojekt muss zunächst geschützt gesichert werden.")
    directories = _directory_states(root, [name for name, _, _ in ordered])
    if len(directories) > 64:
        raise PathSafetyError("Die Transaktion betrifft zu viele Verzeichnisse.")
    operations = []
    total_original = 0
    for name, action, result in ordered:
        original, attributes = _operation_state(root, name)
        if (action == "create") != (original is None):
            raise PathSafetyError("Operationsziel entspricht nicht dem erwarteten Ausgangszustand.")
        total_original += len(original) if original is not None else 0
        operations.append({
            "path": name, "action": action,
            "before_sha256": hashlib.sha256(original).hexdigest() if original is not None else None,
            "before_attributes": attributes,
            "after_sha256": hashlib.sha256(result).hexdigest(),
        })
    if total_original > 8 * MAX_CONFIG_BYTES:
        raise PathSafetyError("Die Originaldateien überschreiten die zulässige Gesamtgröße.")
    identity = {
        "format": 4,
        "generator_version": generator_version,
        "source_sha256": hashlib.sha256(content).hexdigest(),
        "source_attributes": file_attributes(target),
        "project_fingerprint": _location_fingerprint(root),
        "storage_fingerprint": _location_fingerprint(store),
        "operations": operations,
        "directories": directories,
        "warnings": warnings,
    }
    if backup_id is None:
        for counter in range(1024):
            candidate = _canonical_id({"identity": identity, "counter": counter})[:32]
            if not os.path.lexists(store / (BACKUP_PREFIX + candidate)):
                backup_id = candidate
                break
        else:
            raise PathSafetyError("Kein freier Backup-Pfad verfügbar.")
    if not re.fullmatch(r"[0-9a-f]{32}", backup_id):
        raise PathSafetyError("Ungültige Backup-ID.")
    identity["backup"] = {"id": backup_id, "before": "not_exists"}
    return {**identity, "plan_id": _canonical_id(identity), "read_only": True}


def check_prerequisites() -> list[str]:
    return [] if shutil.which("git") else ["Git wurde im PATH nicht gefunden."]
