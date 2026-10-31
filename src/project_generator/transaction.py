"""Confirmed metadata changes and conflict-aware recovery."""

import ctypes
import errno
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import stat

from .config import ConfigurationError, VERSION
from .plan import (
    BACKUP_PREFIX, MAX_CONFIG_BYTES, PathSafetyError, _location_fingerprint, backup_store,
    _canonical_id, _directory_states, _operation_paths, _operation_state, create_plan,
    file_attributes, metadata_result, multi_plan_target, path_attributes, plan_target, read_target,
)

ID_PATTERN = re.compile(r"[0-9a-f]{32}")
PLAN_PATTERN = re.compile(r"[0-9a-f]{64}")
MAX_PLAN_BYTES = 64 * 1024


class TransactionError(ValueError):
    """A transaction was refused or could not be completed safely."""


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _error_detail(error: Exception) -> str:
    if isinstance(error, OSError):
        return f"Dateisystemfehler (Code {error.errno or getattr(error, 'winerror', None) or 'unbekannt'})"
    return str(error)


def _windows_user_sid() -> str:
    from ctypes import wintypes

    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi.OpenProcessToken.restype = wintypes.BOOL
    advapi.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                            wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    advapi.GetTokenInformation.restype = wintypes.BOOL
    advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
    advapi.ConvertSidToStringSidW.restype = wintypes.BOOL
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    token = wintypes.HANDLE()
    sid_string = wintypes.LPWSTR()
    if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 0x0008, ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        size = wintypes.DWORD()
        advapi.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
        if not size.value:
            raise ctypes.WinError(ctypes.get_last_error())
        data = ctypes.create_string_buffer(size.value)
        if not advapi.GetTokenInformation(token, 1, data, size, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        sid = ctypes.cast(data, ctypes.POINTER(ctypes.c_void_p))[0]
        if not advapi.ConvertSidToStringSidW(sid, ctypes.byref(sid_string)):
            raise ctypes.WinError(ctypes.get_last_error())
        return sid_string.value
    finally:
        if sid_string:
            kernel.LocalFree(ctypes.cast(sid_string, ctypes.c_void_p))
        kernel.CloseHandle(token)


def _windows_private_mkdir(path: Path) -> None:
    from ctypes import wintypes

    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p
    ]
    advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p

    class SecurityAttributes(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("descriptor", ctypes.c_void_p),
                    ("inherit", wintypes.BOOL)]

    kernel.CreateDirectoryW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(SecurityAttributes)]
    kernel.CreateDirectoryW.restype = wintypes.BOOL
    descriptor = ctypes.c_void_p()
    try:
        sddl = f"D:P(A;OICI;FA;;;{_windows_user_sid()})(A;OICI;FA;;;SY)"
        if not advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            sddl, 1, ctypes.byref(descriptor), None
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        attributes = SecurityAttributes(ctypes.sizeof(SecurityAttributes), descriptor, False)
        if not kernel.CreateDirectoryW(str(path), ctypes.byref(attributes)):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        if descriptor:
            kernel.LocalFree(descriptor)


def _windows_check_private_acl(path: Path, directory: bool) -> None:
    from ctypes import wintypes

    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi.GetFileSecurityW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p,
                                         wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    advapi.GetFileSecurityW.restype = wintypes.BOOL
    advapi.GetSecurityDescriptorControl.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.WORD),
                                                      ctypes.POINTER(wintypes.DWORD)]
    advapi.GetSecurityDescriptorControl.restype = wintypes.BOOL
    advapi.GetSecurityDescriptorDacl.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.BOOL),
                                                 ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.BOOL)]
    advapi.GetSecurityDescriptorDacl.restype = wintypes.BOOL
    advapi.GetAclInformation.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.c_int]
    advapi.GetAclInformation.restype = wintypes.BOOL
    advapi.GetAce.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p)]
    advapi.GetAce.restype = wintypes.BOOL
    advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
    advapi.ConvertSidToStringSidW.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p

    class AclSize(ctypes.Structure):
        _fields_ = [("count", wintypes.DWORD), ("used", wintypes.DWORD), ("free", wintypes.DWORD)]

    size = wintypes.DWORD()
    advapi.GetFileSecurityW(str(path), 4, None, 0, ctypes.byref(size))
    if not size.value:
        raise ctypes.WinError(ctypes.get_last_error())
    descriptor = ctypes.create_string_buffer(size.value)
    if not advapi.GetFileSecurityW(str(path), 4, descriptor, size, ctypes.byref(size)):
        raise ctypes.WinError(ctypes.get_last_error())
    control, revision = wintypes.WORD(), wintypes.DWORD()
    present, defaulted, acl = wintypes.BOOL(), wintypes.BOOL(), ctypes.c_void_p()
    if (not advapi.GetSecurityDescriptorControl(descriptor, ctypes.byref(control), ctypes.byref(revision))
            or not advapi.GetSecurityDescriptorDacl(
                descriptor, ctypes.byref(present), ctypes.byref(acl), ctypes.byref(defaulted)
            )):
        raise ctypes.WinError(ctypes.get_last_error())
    acl_size = AclSize()
    if not present.value or not acl or (directory and not control.value & 0x1000):
        raise TransactionError("Backup hat keine ausreichend geschützte Windows-DACL.")
    if not advapi.GetAclInformation(acl, ctypes.byref(acl_size), ctypes.sizeof(acl_size), 2):
        raise ctypes.WinError(ctypes.get_last_error())
    if acl_size.count != 2:
        raise TransactionError("Backup hat unerwartete Windows-Zugriffsrechte.")
    principals = set()
    for index in range(acl_size.count):
        ace = ctypes.c_void_p()
        if not advapi.GetAce(acl, index, ctypes.byref(ace)):
            raise ctypes.WinError(ctypes.get_last_error())
        header = ctypes.cast(ace, ctypes.POINTER(ctypes.c_ubyte))
        mask = ctypes.c_uint32.from_address(ace.value + 4).value
        if (header[0] != 0 or (directory and header[1] != 3)
                or (not directory and header[1] & 8) or mask != 0x1F01FF):
            raise TransactionError("Backup hat unerwartete Windows-Zugriffsrechte.")
        sid = wintypes.LPWSTR()
        if not advapi.ConvertSidToStringSidW(ace.value + 8, ctypes.byref(sid)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            principals.add(sid.value)
        finally:
            kernel.LocalFree(ctypes.cast(sid, ctypes.c_void_p))
    if principals != {_windows_user_sid(), "S-1-5-18"}:
        raise TransactionError("Backup hat unerwartete Windows-Zugriffsrechte.")


def _private_mkdir(path: Path) -> None:
    if os.name == "nt":
        _windows_private_mkdir(path)
        _windows_check_private_acl(path, directory=True)
    else:
        path.mkdir(mode=0o700)
        info = path.lstat()
        if stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != os.getuid():
            raise TransactionError("Backup-Verzeichnis ist nicht ausreichend geschützt.")


def _private_directory(path: Path) -> None:
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)):
        raise TransactionError("Backup-Verzeichnis ist kein sicheres Verzeichnis.")
    if os.name != "nt" and (stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != os.getuid()):
        raise TransactionError("Backup-Verzeichnis ist nicht ausreichend geschützt.")
    if os.name == "nt":
        _windows_check_private_acl(path, directory=True)


def _prepare_store(target: str) -> Path:
    store = backup_store(target)
    store.parent.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if backup_store(target) != store:
        raise TransactionError("Backup-Speicher hat sich unerwartet geändert.")
    for path in (store.parent, store):
        try:
            _private_mkdir(path)
        except FileExistsError:
            _private_directory(path)
    if backup_store(target) != store:
        raise TransactionError("Backup-Speicher hat sich unerwartet geändert.")
    _sync_directory(store.parent.parent)
    _sync_directory(store.parent)
    return store


def _read_file(path: Path, limit: int, private: bool = False) -> bytes:
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)):
        raise TransactionError("Plan oder Backup enthält keine sichere reguläre Datei.")
    if private:
        if info.st_nlink != 1:
            raise TransactionError("Backup-Datei hat mehrere oder unbekannte Hardlinks.")
        if os.name == "nt":
            _windows_check_private_acl(path, directory=False)
        elif info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise TransactionError("Backup-Datei ist nicht ausreichend geschützt.")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as file:
        if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
            raise TransactionError("Plan oder Backup enthält keine sichere reguläre Datei.")
        data = file.read(limit + 1)
    if len(data) > limit:
        raise TransactionError("Plan oder Backup überschreitet die zulässige Größe.")
    return data


def _json_object(data: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise TransactionError("Plan oder Manifest enthält doppelte Schlüssel.")
            result[key] = value
        return result

    try:
        result = json.loads(data.decode("utf-8-sig"), object_pairs_hook=unique)
    except TransactionError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as error:
        raise TransactionError("Plan oder Manifest ist kein gültiges JSON.") from error
    if not isinstance(result, dict):
        raise TransactionError("Plan oder Manifest muss ein JSON-Objekt sein.")
    return result


def _write_new(path: Path, content: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        if os.name == "nt":
            _windows_check_private_acl(path, directory=False)
        with os.fdopen(fd, "wb") as file:
            fd = None
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
    except BaseException:
        if fd is not None:
            os.close(fd)
        path.unlink(missing_ok=True)
        raise


def _sync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_in_place(source: Path, target: Path) -> None:
    if target.lstat().st_nlink != 1:
        raise TransactionError("Direktes Schreiben von Dateien mit mehreren oder unbekannten Hardlinks ist unsicher.")
    content = _read_file(source, MAX_CONFIG_BYTES, private=os.name == "nt")
    with target.open("r+b") as file:
        file.write(content)
        file.truncate()
        file.flush()
        os.fsync(file.fileno())


def _replace(source: Path, target: Path) -> None:
    if os.name == "nt":
        _write_in_place(source, target)
        return
    try:
        os.replace(source, target)
    except OSError as error:
        if error.errno != errno.EXDEV:
            raise
        _write_in_place(source, target)


def _stage_and_replace(backup: Path, target: Path, content: bytes) -> None:
    info = target.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise TransactionError("Zieldatei ist keine reguläre Datei.")
    if os.name != "nt" and info.st_uid != os.getuid():
        raise TransactionError("Zieldatei gehört nicht dem ausführenden Benutzer.")
    stage = backup / "stage"
    created = False
    try:
        _write_new(stage, content)
        created = True
        if os.name != "nt":
            os.chown(stage, info.st_uid, info.st_gid)
            os.chmod(stage, stat.S_IMODE(info.st_mode))
            if hasattr(os, "listxattr"):
                for name in os.listxattr(target, follow_symlinks=False):
                    os.setxattr(stage, name, os.getxattr(target, name, follow_symlinks=False),
                                follow_symlinks=False)
        _replace(stage, target)
        _sync_directory(target.parent)
        _sync_directory(backup)
    finally:
        if created:
            try:
                stage.unlink()
            except FileNotFoundError:
                pass


def _current_plan(target: str, version: str, backup_id: str | None = None) -> tuple[bytes, dict]:
    return plan_target(target, version, backup_id)


def _record_partial(target: str, backup: Path, manifest: dict, original: bytes, result: bytes) -> bool:
    current, _ = read_target(target)
    if current in (original, result):
        return False
    if file_attributes(target) != manifest["attributes"]:
        raise TransactionError("Geänderte Zugriffsmetadaten verhindern die Erfassung des Teilzustands.")
    record = {"format": 1, "plan_id": manifest["plan_id"], "partial_sha256": _digest(current)}
    record_path = backup / "recovery.json"
    if os.path.lexists(record_path):
        previous = _json_object(_read_file(record_path, MAX_PLAN_BYTES, private=True))
        if (set(previous) != {"format", "plan_id", "partial_sha256"}
                or type(previous["format"]) is not int or previous["format"] != 1
                or previous["plan_id"] != manifest["plan_id"]
                or not isinstance(previous["partial_sha256"], str)
                or not PLAN_PATTERN.fullmatch(previous["partial_sha256"])):
            raise TransactionError("Vorhandenes Wiederherstellungsprotokoll ist ungültig.")
    temporary = backup / "recovery.tmp"
    _write_new(temporary, json.dumps(record, sort_keys=True).encode("utf-8"))
    os.replace(temporary, record_path)
    _sync_directory(backup)
    return True


def apply(target: str, plan_file: str, confirmation: str, version: str) -> str:
    if not PLAN_PATTERN.fullmatch(confirmation):
        raise TransactionError("Eine gültige bestätigte Plan-ID ist erforderlich.")
    supplied = _json_object(_read_file(Path(plan_file), MAX_PLAN_BYTES))
    if supplied.get("format") == 4:
        if supplied.get("module") != "python":
            raise TransactionError("Unbekannter öffentlicher Mehrdatei-Plan.")
        from .python_module import python_plan_target
        try:
            expected, changes = python_plan_target(target, version)
        except (PathSafetyError, ConfigurationError, OSError) as error:
            raise TransactionError(f"Modulplan kann nicht geprüft werden: {_error_detail(error)}") from error
        if expected.get("conflicts") or not changes:
            raise TransactionError("Modulplan enthält Konflikte oder keine ausführbare Operation.")
        return apply_multi(target, supplied, confirmation, version, changes, module="python")
    content, expected = _current_plan(target, version)
    if expected["conflicts"]:
        raise TransactionError("Projektkonflikte verhindern apply.")
    if not expected["operations"]:
        raise TransactionError("Der Plan enthält keine ausführbare Operation.")
    canonical = lambda plan: json.dumps(plan, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    if (not hmac.compare_digest(confirmation, expected["plan_id"])
            or canonical(supplied) != canonical(expected)):
        raise TransactionError("Plan ist verändert, veraltet oder nicht mit der bestätigten ID identisch.")

    result = metadata_result(content, version)
    root = Path(target).expanduser().resolve(strict=True)
    backup_id = expected["backup"]["id"]
    store = backup_store(target)
    backup = store / (BACKUP_PREFIX + backup_id)
    config = root / "config" / "project.yaml"
    mode = stat.S_IMODE(config.lstat().st_mode)
    manifest = {
        "format": 2,
        "backup_id": backup_id,
        "path": "config/project.yaml",
        "plan_id": expected["plan_id"],
        "generator_version": version,
        "before_sha256": _digest(content),
        "after_sha256": _digest(result),
        "attributes": expected["operations"][0]["before_attributes"],
        "original_mode": mode,
        "project_fingerprint": expected["project_fingerprint"],
        "storage_fingerprint": expected["storage_fingerprint"],
    }
    write_started = False
    try:
        _prepare_store(target)
        _private_mkdir(backup)
        _write_new(backup / "original", content)
        _write_new(backup / "manifest.json", json.dumps(manifest, sort_keys=True).encode("utf-8"))
        _sync_directory(backup)
        _sync_directory(store)
        current, fresh = _current_plan(target, version, backup_id)
        if current != content or fresh != expected or stat.S_IMODE(config.lstat().st_mode) != mode:
            raise TransactionError("Projektzustand hat sich vor apply geändert.")
        write_started = True
        _stage_and_replace(backup, config, result)
        actual, _ = read_target(target)
        if (actual != result or stat.S_IMODE(config.lstat().st_mode) != mode
                or file_attributes(target) != manifest["attributes"]):
            raise TransactionError("Zielzustand nach apply stimmt nicht mit dem Plan überein.")
    except (OSError, TransactionError, PathSafetyError, ConfigurationError) as error:
        recovery_note = ""
        if write_started:
            try:
                if _record_partial(target, backup, manifest, content, result):
                    recovery_note = " Teilzustand erfasst; restore ist ohne Zwischenänderungen möglich."
            except (OSError, TransactionError, PathSafetyError, ConfigurationError):
                recovery_note = " Teilzustand konnte nicht sicher erfasst werden; manuelle Wiederherstellung nötig."
        if not write_started:
            recovery_note = " Das Ziel wurde nicht geschrieben; das Backup kann unvollständig sein."
        raise TransactionError(
            f"Apply nicht abgeschlossen: {_error_detail(error)}. Backup-ID: {backup_id}. "
            f"Projektzustand prüfen; bei Konflikten manuell aus dem Backup wiederherstellen.{recovery_note}"
        ) from error
    return backup_id


def _multi_progress(backup: Path, progress: dict) -> None:
    temporary = backup / "progress.tmp"
    _write_new(temporary, json.dumps(progress, sort_keys=True).encode("utf-8"))
    try:
        os.replace(temporary, backup / "progress.json")
    finally:
        temporary.unlink(missing_ok=True)
    _sync_directory(backup)


def _multi_record_file(root: Path, backup: Path, progress: dict, operation: dict) -> None:
    content, attributes = _operation_state(root, operation["path"])
    if content is None:
        if operation["action"] == "modify":
            raise TransactionError("Geänderte Datei fehlt; Teilzustand kann nicht erfasst werden.")
        return
    if operation["action"] == "modify" and attributes != operation["before_attributes"]:
        raise TransactionError("Geänderte Zugriffsmetadaten verhindern die Erfassung des Teilzustands.")
    progress["files"][operation["path"]] = {"sha256": _digest(content), "attributes": attributes}
    _multi_progress(backup, progress)


def _multi_record_directory(root: Path, backup: Path, progress: dict, name: str) -> None:
    attributes = path_attributes(root.joinpath(*name.split("/")), directory=True)
    progress["directories"][name] = attributes
    _multi_progress(backup, progress)


def _multi_create(path: Path, content: bytes, opened: list[bool]) -> None:
    flags = (os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
             | getattr(os, "O_NOFOLLOW", 0))
    fd = os.open(path, flags, 0o666)
    opened[0] = True
    with os.fdopen(fd, "wb") as file:
        file.write(content)
        file.flush()
        os.fsync(file.fileno())
    _sync_directory(path.parent)


def apply_multi(target: str, supplied: dict, confirmation: str, version: str,
                changes: list[tuple[str, str, bytes]], *, module: str | None = None) -> str:
    """Apply a format-4 plan against operations supplied by trusted generator code."""
    if not isinstance(confirmation, str) or not PLAN_PATTERN.fullmatch(confirmation):
        raise TransactionError("Eine gültige bestätigte Plan-ID ist erforderlich.")
    try:
        ordered = _operation_paths(changes)
        expected = multi_plan_target(target, version, changes, module=module)
        canonical = lambda plan: json.dumps(plan, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        if (not hmac.compare_digest(confirmation, expected["plan_id"])
                or canonical(supplied) != canonical(expected)):
            raise TransactionError("Plan ist verändert, veraltet oder nicht mit der bestätigten ID identisch.")
    except (PathSafetyError, ConfigurationError, OSError, TypeError, ValueError) as error:
        if isinstance(error, TransactionError):
            raise
        raise TransactionError(f"Mehrdatei-Plan kann nicht geprüft werden: {_error_detail(error)}") from error

    root = Path(target).expanduser().resolve(strict=True)
    store = backup_store(target)
    backup_id = expected["backup"]["id"]
    backup = store / (BACKUP_PREFIX + backup_id)
    progress = {"format": 1, "plan_id": expected["plan_id"], "files": {}, "directories": {}}
    manifest = {"format": 3, "plan": expected}
    active_operation = None
    active_directory = None
    opened = [False]
    project_write_started = False
    try:
        _prepare_store(target)
        _private_mkdir(backup)
        for index, operation in enumerate(expected["operations"]):
            original, attributes = _operation_state(root, operation["path"])
            if operation["action"] == "modify":
                if (original is None or _digest(original) != operation["before_sha256"]
                        or attributes != operation["before_attributes"]):
                    raise TransactionError("Dateizustand hat sich vor dem Snapshot geändert.")
                _write_new(backup / f"original-{index:02d}", original)
            elif original is not None:
                raise TransactionError("Neue Datei ist vor dem Snapshot bereits vorhanden.")
        _write_new(backup / "manifest.json", json.dumps(manifest, sort_keys=True).encode("utf-8"))
        _multi_progress(backup, progress)
        _sync_directory(backup)
        _sync_directory(store)
        if multi_plan_target(target, version, changes, backup_id, module=module) != expected:
            raise TransactionError("Projektzustand hat sich vor apply geändert.")
        for directory in expected["directories"]:
            if directory["before_attributes"] is not None:
                continue
            name = directory["path"]
            path = root.joinpath(*name.split("/"))
            path.mkdir()
            active_directory = name
            project_write_started = True
            _sync_directory(path.parent)
            _multi_record_directory(root, backup, progress, name)
            active_directory = None
        for operation, (_, _, result) in zip(expected["operations"], ordered):
            active_operation = operation
            opened[0] = False
            path = root.joinpath(*operation["path"].split("/"))
            project_write_started = True
            if operation["action"] == "create":
                _multi_create(path, result, opened)
            else:
                _stage_and_replace(backup, path, result)
            actual, attributes = _operation_state(root, operation["path"])
            if (actual is None or _digest(actual) != operation["after_sha256"]
                    or (operation["action"] == "modify" and attributes != operation["before_attributes"])):
                raise TransactionError("Zielzustand nach apply stimmt nicht mit dem Plan überein.")
            _multi_record_file(root, backup, progress, operation)
            active_operation = None
    except (OSError, TransactionError, PathSafetyError, ConfigurationError) as error:
        note = ""
        try:
            if active_directory is not None:
                _multi_record_directory(root, backup, progress, active_directory)
            if active_operation is not None and (active_operation["action"] == "modify" or opened[0]):
                _multi_record_file(root, backup, progress, active_operation)
            if project_write_started:
                note = " Erfasste Teilzustände stehen im Protokoll; restore prüft alle Zustände vor der Rücknahme."
            else:
                note = " Das Ziel wurde nicht geschrieben; das Backup kann unvollständig sein."
        except (OSError, TransactionError, PathSafetyError, ConfigurationError):
            note = " Teilzustand nicht sicher erfasst; manuelle Wiederherstellung kann nötig sein."
        raise TransactionError(
            f"Apply nicht abgeschlossen: {_error_detail(error)}. Backup-ID: {backup_id}."
            f" Projekt und Backup prüfen.{note}"
        ) from error
    return backup_id


def _validate_multi_backup(root: Path, store: Path, backup: Path, backup_id: str,
                           manifest: dict) -> tuple[dict, dict, list[bytes | None]]:
    if set(manifest) != {"format", "plan"} or type(manifest["format"]) is not int or manifest["format"] != 3:
        raise TransactionError("Mehrdatei-Manifest ist ungültig.")
    plan = manifest["plan"]
    fields = {"format", "generator_version", "source_sha256", "source_attributes",
              "project_fingerprint", "storage_fingerprint", "operations", "directories",
              "warnings", "backup", "plan_id", "read_only"}
    if isinstance(plan, dict) and "module" in plan:
        fields |= {"module", "preconditions", "conflicts"}
    if not isinstance(plan, dict) or set(plan) != fields:
        raise TransactionError("Mehrdatei-Plan im Backup ist ungültig.")
    if "module" in plan:
        conditions = plan["preconditions"]
        if (plan["module"] != "python" or plan["conflicts"] != [] or not isinstance(conditions, dict)
                or set(conditions) != {"files", "directories"}
                or not isinstance(conditions["files"], list)
                or not isinstance(conditions["directories"], list)
                or any(not isinstance(state, dict) or set(state) != {"path", "sha256", "attributes"}
                       or not isinstance(state["path"], str)
                       or not all(isinstance(state[key], str) and PLAN_PATTERN.fullmatch(state[key])
                                  for key in ("sha256", "attributes")) for state in conditions["files"])
                or any(not isinstance(state, dict) or set(state) != {"path", "before_attributes"}
                       or not isinstance(state["path"], str)
                       or not isinstance(state["before_attributes"], str)
                       or not PLAN_PATTERN.fullmatch(state["before_attributes"])
                       for state in conditions["directories"])):
            raise TransactionError("Modulvoraussetzungen im Backup sind ungültig.")
    identity = {key: value for key, value in plan.items() if key not in {"plan_id", "read_only"}}
    if (type(plan["format"]) is not int or plan["format"] != 4 or plan["read_only"] is not True
            or not isinstance(plan["generator_version"], str)
            or not VERSION.fullmatch(plan["generator_version"])
            or plan["project_fingerprint"] != _location_fingerprint(root)
            or plan["storage_fingerprint"] != _location_fingerprint(store)
            or plan["backup"] != {"id": backup_id, "before": "not_exists"}
            or not isinstance(plan["plan_id"], str) or plan["plan_id"] != _canonical_id(identity)
            or not isinstance(plan["warnings"], list)
            or not all(isinstance(item, str) for item in plan["warnings"])
            or not all(isinstance(plan[key], str) and PLAN_PATTERN.fullmatch(plan[key])
                       for key in ("source_sha256", "source_attributes"))):
        raise TransactionError("Mehrdatei-Plan oder Backup-Bindung ist ungültig.")
    operations = plan["operations"]
    if not isinstance(operations, list):
        raise TransactionError("Mehrdatei-Operationen sind ungültig.")
    changes = []
    for operation in operations:
        if not isinstance(operation, dict) or set(operation) != {
            "path", "action", "before_sha256", "before_attributes", "after_sha256"
        }:
            raise TransactionError("Mehrdatei-Operation ist ungültig.")
        changes.append((operation["path"], operation["action"], b""))
        if not isinstance(operation["after_sha256"], str) or not PLAN_PATTERN.fullmatch(operation["after_sha256"]):
            raise TransactionError("Ziel-Fingerabdruck ist ungültig.")
        if operation["action"] == "create":
            if operation["before_sha256"] is not None or operation["before_attributes"] is not None:
                raise TransactionError("Ausgangszustand einer neuen Datei ist ungültig.")
        elif not all(isinstance(operation[key], str) and PLAN_PATTERN.fullmatch(operation[key])
                     for key in ("before_sha256", "before_attributes")):
            raise TransactionError("Ausgangszustand einer vorhandenen Datei ist ungültig.")
    if _operation_paths(changes) != changes:
        raise TransactionError("Mehrdatei-Operationen sind nicht eindeutig sortiert.")
    directory_names = {"."}
    for operation in operations:
        parts = operation["path"].split("/")[:-1]
        directory_names.update("/".join(parts[:index]) for index in range(1, len(parts) + 1))
    directories = plan["directories"]
    if (not isinstance(directories, list)
            or len(directories) > 64
            or any(not isinstance(item, dict) or set(item) != {"path", "before_attributes"}
                   for item in directories)
            or [item["path"] for item in directories]
            != sorted(directory_names, key=lambda value: (value.count("/"), value.lower()))
            or any(item["before_attributes"] is not None
                   and (not isinstance(item["before_attributes"], str)
                        or not PLAN_PATTERN.fullmatch(item["before_attributes"])) for item in directories)
            or directories[0]["before_attributes"] is None):
        raise TransactionError("Verzeichniszustände im Mehrdatei-Plan sind ungültig.")
    progress = _json_object(_read_file(backup / "progress.json", MAX_PLAN_BYTES, private=True))
    if (set(progress) != {"format", "plan_id", "files", "directories"}
            or type(progress["format"]) is not int or progress["format"] != 1
            or progress["plan_id"] != plan["plan_id"]
            or not isinstance(progress["files"], dict) or not isinstance(progress["directories"], dict)
            or not set(progress["files"]).issubset({item["path"] for item in operations})
            or not set(progress["directories"]).issubset(
                {item["path"] for item in directories if item["before_attributes"] is None})):
        raise TransactionError("Mehrdatei-Protokoll ist ungültig.")
    for state in progress["files"].values():
        if (not isinstance(state, dict) or set(state) != {"sha256", "attributes"}
                or not all(isinstance(state[key], str) and PLAN_PATTERN.fullmatch(state[key])
                           for key in ("sha256", "attributes"))):
            raise TransactionError("Dateizustand im Mehrdatei-Protokoll ist ungültig.")
    for operation in operations:
        state = progress["files"].get(operation["path"])
        if state and operation["action"] == "modify" and state["attributes"] != operation["before_attributes"]:
            raise TransactionError("Zugriffsmetadaten im Mehrdatei-Protokoll sind ungültig.")
    if any(not isinstance(value, str) or not PLAN_PATTERN.fullmatch(value)
           for value in progress["directories"].values()):
        raise TransactionError("Verzeichniszustand im Mehrdatei-Protokoll ist ungültig.")
    originals = []
    for index, operation in enumerate(operations):
        if operation["action"] == "create":
            originals.append(None)
        else:
            original = _read_file(backup / f"original-{index:02d}", MAX_CONFIG_BYTES, private=True)
            if _digest(original) != operation["before_sha256"]:
                raise TransactionError("Originaldatei im Mehrdatei-Backup ist verändert.")
            originals.append(original)
    return plan, progress, originals


def _restore_multi(root: Path, store: Path, backup: Path, backup_id: str, manifest: dict) -> str:
    plan, progress, originals = _validate_multi_backup(root, store, backup, backup_id, manifest)
    directories = _directory_states(root, [operation["path"] for operation in plan["operations"]])
    for expected, current in zip(plan["directories"], directories):
        before = expected["before_attributes"]
        actual = current["before_attributes"]
        if before is not None:
            if actual != before:
                raise TransactionError("Verzeichnis oder Zugriffsmetadaten wurden zwischenzeitlich geändert.")
        elif actual is not None and actual != progress["directories"].get(expected["path"]):
            raise TransactionError("Neues Verzeichnis ist nicht als Generatorzustand nachgewiesen.")
    states = []
    for operation, original in zip(plan["operations"], originals):
        content, attributes = _operation_state(root, operation["path"])
        if content is None:
            if original is not None:
                raise TransactionError("Vorhandene Datei fehlt; keine automatische Wiederherstellung.")
            states.append("original")
            continue
        digest = _digest(content)
        if original is not None and digest == operation["before_sha256"] and attributes == operation["before_attributes"]:
            states.append("original")
            continue
        recorded = progress["files"].get(operation["path"])
        expected_result = (original is not None and digest == operation["after_sha256"]
                           and attributes == operation["before_attributes"])
        if ((recorded is None and not expected_result)
                or (recorded is not None and recorded != {"sha256": digest, "attributes": attributes})):
            raise TransactionError("Fremde Zwischenänderung; keine automatische Wiederherstellung.")
        states.append("changed")

    active = None
    try:
        for operation, original, state in zip(plan["operations"], originals, states):
            if state == "original":
                continue
            active = operation
            path = root.joinpath(*operation["path"].split("/"))
            if original is None:
                path.unlink()
                _sync_directory(path.parent)
                if os.path.lexists(path):
                    raise TransactionError("Neue Datei konnte nicht sicher entfernt werden.")
            else:
                _stage_and_replace(backup, path, original)
                restored, attributes = _operation_state(root, operation["path"])
                if restored != original or attributes != operation["before_attributes"]:
                    raise TransactionError("Wiederhergestellter Dateizustand stimmt nicht mit dem Backup überein.")
            active = None
        remaining = []
        for directory in reversed(plan["directories"]):
            if directory["before_attributes"] is not None:
                continue
            path = root.joinpath(*directory["path"].split("/"))
            if not os.path.lexists(path):
                continue
            try:
                path.rmdir()
                _sync_directory(path.parent)
            except OSError as error:
                if error.errno not in (errno.ENOTEMPTY, errno.EEXIST):
                    raise
                remaining.append(directory["path"])
        if remaining:
            return "Dateien wiederhergestellt; nicht leere Verzeichnisse bleiben erhalten."
        if all(state == "original" for state in states):
            return "Bereits im ursprünglichen Zustand; keine Änderung."
        return "Ursprüngliche Dateizustände wiederhergestellt."
    except (OSError, TransactionError, PathSafetyError) as error:
        note = ""
        if active is not None and active["action"] == "modify":
            try:
                _multi_record_file(root, backup, progress, active)
                note = " Teilzustand erfasst; restore kann erneut geprüft werden."
            except (OSError, TransactionError, PathSafetyError):
                note = " Teilzustand nicht sicher erfasst; manuelle Wiederherstellung kann nötig sein."
        raise TransactionError(f"Mehrdatei-Restore fehlgeschlagen: {_error_detail(error)}.{note}") from error


def restore(target: str, backup_id: str) -> str:
    if not ID_PATTERN.fullmatch(backup_id):
        raise TransactionError("Ungültige Backup-ID.")
    write_started = False
    try:
        current, _ = read_target(target)
        root = Path(target).expanduser().resolve(strict=True)
        store = backup_store(target)
        _private_directory(store.parent)
        _private_directory(store)
        backup = store / (BACKUP_PREFIX + backup_id)
        config = root / "config" / "project.yaml"
        _private_directory(backup)
        manifest = _json_object(_read_file(backup / "manifest.json", MAX_PLAN_BYTES, private=True))
        if manifest.get("format") == 3:
            return _restore_multi(root, store, backup, backup_id, manifest)
        original = _read_file(backup / "original", MAX_CONFIG_BYTES, private=True)
        if set(manifest) != {"format", "backup_id", "path", "plan_id", "generator_version",
                             "before_sha256", "after_sha256", "attributes", "original_mode",
                             "project_fingerprint", "storage_fingerprint"}:
            raise TransactionError("Backup-Manifest ist ungültig.")
        version = manifest["generator_version"]
        if (type(manifest["format"]) is not int or manifest["format"] != 2 or manifest["backup_id"] != backup_id
                or manifest["path"] != "config/project.yaml"
                or manifest["project_fingerprint"] != _location_fingerprint(root)
                or manifest["storage_fingerprint"] != _location_fingerprint(store)
                or not isinstance(version, str) or not VERSION.fullmatch(version)
                or not isinstance(manifest["attributes"], str)
                or not PLAN_PATTERN.fullmatch(manifest["attributes"])
                or type(manifest["original_mode"]) is not int
                or not 0 <= manifest["original_mode"] <= 0o7777):
            raise TransactionError("Backup-Manifest ist ungültig.")
        expected = create_plan(original, version, [], manifest["attributes"], backup_id,
                               manifest["project_fingerprint"], manifest["storage_fingerprint"])
        if (len(expected["operations"]) != 1 or manifest["plan_id"] != expected["plan_id"]
                or manifest["before_sha256"] != _digest(original)
                or manifest["after_sha256"] != expected["operations"][0]["after_sha256"]):
            raise TransactionError("Backup oder Manifest ist verändert.")
        if (stat.S_IMODE(config.lstat().st_mode) != manifest["original_mode"]
                or file_attributes(target) != manifest["attributes"]):
            raise TransactionError("Dateiberechtigungen wurden zwischenzeitlich geändert.")
        if current == original:
            return "Bereits im ursprünglichen Zustand; keine Änderung."
        try:
            record = _json_object(_read_file(backup / "recovery.json", MAX_PLAN_BYTES, private=True))
        except FileNotFoundError:
            if _digest(current) != manifest["after_sha256"]:
                raise TransactionError("Fremde Zwischenänderung; keine automatische Wiederherstellung.")
        else:
            if (set(record) != {"format", "plan_id", "partial_sha256"}
                    or type(record["format"]) is not int or record["format"] != 1
                    or record["plan_id"] != manifest["plan_id"]
                    or record["partial_sha256"] != _digest(current)):
                raise TransactionError("Fremde Zwischenänderung; keine automatische Wiederherstellung.")
        fresh, _ = read_target(target)
        if (fresh != current or stat.S_IMODE(config.lstat().st_mode) != manifest["original_mode"]
                or file_attributes(target) != manifest["attributes"]):
            raise TransactionError("Projektzustand hat sich vor restore geändert.")
        write_started = True
        _stage_and_replace(backup, config, original)
        restored, _ = read_target(target)
        if restored != original or file_attributes(target) != manifest["attributes"]:
            raise TransactionError("Zielzustand nach restore stimmt nicht mit dem Backup überein.")
        return "Ursprünglicher Dateizustand wiederhergestellt."
    except (OSError, TransactionError, PathSafetyError, ConfigurationError) as error:
        recovery_note = ""
        if write_started:
            try:
                result = metadata_result(original, version)
                if _record_partial(target, backup, manifest, original, result):
                    recovery_note = " Teilzustand erfasst; restore ist ohne Zwischenänderungen erneut möglich."
            except (OSError, TransactionError, PathSafetyError, ConfigurationError):
                recovery_note = " Teilzustand konnte nicht sicher erfasst werden; manuelle Wiederherstellung nötig."
        raise TransactionError(
            f"Restore verweigert oder fehlgeschlagen: {_error_detail(error)} "
            f"Backup-ID: {backup_id}; Projekt und Backup für manuelle Wiederherstellung prüfen.{recovery_note}"
        ) from error
