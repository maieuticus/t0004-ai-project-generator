"""Confirmed metadata changes and conflict-aware recovery."""

import ctypes
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import stat

from .config import ConfigurationError, VERSION
from .plan import (
    BACKUP_PREFIX, MAX_CONFIG_BYTES, PathSafetyError, choose_backup_id, create_plan,
    file_attributes, metadata_result, read_target,
)

ID_PATTERN = re.compile(r"[0-9a-f]{32}")
PLAN_PATTERN = re.compile(r"[0-9a-f]{64}")
MAX_PLAN_BYTES = 64 * 1024


class TransactionError(ValueError):
    """A transaction was refused or could not be completed safely."""


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


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


def _windows_check_private_directory(path: Path) -> None:
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
    if not present.value or not acl or not control.value & 0x1000:
        raise TransactionError("Backup-Verzeichnis hat keine geschützte Windows-DACL.")
    if not advapi.GetAclInformation(acl, ctypes.byref(acl_size), ctypes.sizeof(acl_size), 2):
        raise ctypes.WinError(ctypes.get_last_error())
    if acl_size.count != 2:
        raise TransactionError("Backup-Verzeichnis hat unerwartete Windows-Zugriffsrechte.")
    principals = set()
    for index in range(acl_size.count):
        ace = ctypes.c_void_p()
        if not advapi.GetAce(acl, index, ctypes.byref(ace)):
            raise ctypes.WinError(ctypes.get_last_error())
        header = ctypes.cast(ace, ctypes.POINTER(ctypes.c_ubyte))
        mask = ctypes.c_uint32.from_address(ace.value + 4).value
        if header[0] != 0 or header[1] != 3 or mask != 0x1F01FF:
            raise TransactionError("Backup-Verzeichnis hat unerwartete Windows-Zugriffsrechte.")
        sid = wintypes.LPWSTR()
        if not advapi.ConvertSidToStringSidW(ace.value + 8, ctypes.byref(sid)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            principals.add(sid.value)
        finally:
            kernel.LocalFree(ctypes.cast(sid, ctypes.c_void_p))
    if principals != {_windows_user_sid(), "S-1-5-18"}:
        raise TransactionError("Backup-Verzeichnis hat unerwartete Windows-Zugriffsrechte.")


def _private_mkdir(path: Path) -> None:
    if os.name == "nt":
        _windows_private_mkdir(path)
        _windows_check_private_directory(path)
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
        _windows_check_private_directory(path)


def _read_file(path: Path, limit: int) -> bytes:
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)):
        raise TransactionError("Plan oder Backup enthält keine sichere reguläre Datei.")
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
    with os.fdopen(fd, "wb") as file:
        file.write(content)
        file.flush()
        os.fsync(file.fileno())


def _sync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _replace(source: Path, target: Path) -> None:
    if os.name == "nt":
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.ReplaceFileW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                        wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p]
        kernel.ReplaceFileW.restype = wintypes.BOOL
        if not kernel.ReplaceFileW(str(target), str(source), None, 0, None, None):
            raise ctypes.WinError(ctypes.get_last_error())
    else:
        os.replace(source, target)


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
    content, missing = read_target(target)
    attributes = file_attributes(target)
    if backup_id is None:
        backup_id = choose_backup_id(content, version, attributes, target)
    return content, create_plan(content, version, missing, attributes, backup_id)


def apply(target: str, plan_file: str, confirmation: str, version: str) -> str:
    if not PLAN_PATTERN.fullmatch(confirmation):
        raise TransactionError("Eine gültige bestätigte Plan-ID ist erforderlich.")
    supplied = _json_object(_read_file(Path(plan_file), MAX_PLAN_BYTES))
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
    backup = root / (BACKUP_PREFIX + backup_id)
    config = root / "config" / "project.yaml"
    mode = stat.S_IMODE(config.lstat().st_mode)
    manifest = {
        "format": 1,
        "backup_id": backup_id,
        "path": "config/project.yaml",
        "plan_id": expected["plan_id"],
        "generator_version": version,
        "before_sha256": _digest(content),
        "after_sha256": _digest(result),
        "attributes": expected["operations"][0]["before_attributes"],
        "original_mode": mode,
    }
    try:
        _private_mkdir(backup)
        _write_new(backup / "original", content)
        _write_new(backup / "manifest.json", json.dumps(manifest, sort_keys=True).encode("utf-8"))
        _sync_directory(backup)
        _sync_directory(root)
        current, fresh = _current_plan(target, version, backup_id)
        if current != content or fresh != expected or stat.S_IMODE(config.lstat().st_mode) != mode:
            raise TransactionError("Projektzustand hat sich vor apply geändert.")
        _stage_and_replace(backup, config, result)
        actual, _ = read_target(target)
        if (actual != result or stat.S_IMODE(config.lstat().st_mode) != mode
                or file_attributes(target) != manifest["attributes"]):
            raise TransactionError("Zielzustand nach apply stimmt nicht mit dem Plan überein.")
    except (OSError, TransactionError, PathSafetyError, ConfigurationError) as error:
        detail = (f"Dateisystemfehler (Code {error.errno or getattr(error, 'winerror', None) or 'unbekannt'})"
                  if isinstance(error, OSError) else str(error))
        raise TransactionError(
            f"Apply nicht abgeschlossen: {detail}. Backup-ID: {backup_id}. "
            "Projektzustand prüfen; bei Konflikten manuell aus dem Backup wiederherstellen."
        ) from error
    return backup_id


def restore(target: str, backup_id: str) -> str:
    if not ID_PATTERN.fullmatch(backup_id):
        raise TransactionError("Ungültige Backup-ID.")
    try:
        current, _ = read_target(target)
        root = Path(target).expanduser().resolve(strict=True)
        backup = root / (BACKUP_PREFIX + backup_id)
        config = root / "config" / "project.yaml"
        _private_directory(backup)
        manifest = _json_object(_read_file(backup / "manifest.json", MAX_PLAN_BYTES))
        original = _read_file(backup / "original", MAX_CONFIG_BYTES)
        if set(manifest) != {"format", "backup_id", "path", "plan_id", "generator_version",
                             "before_sha256", "after_sha256", "attributes", "original_mode"}:
            raise TransactionError("Backup-Manifest ist ungültig.")
        version = manifest["generator_version"]
        if (manifest["format"] != 1 or manifest["backup_id"] != backup_id
                or manifest["path"] != "config/project.yaml"
                or not isinstance(version, str) or not VERSION.fullmatch(version)
                or not isinstance(manifest["attributes"], str)
                or not PLAN_PATTERN.fullmatch(manifest["attributes"])
                or not isinstance(manifest["original_mode"], int)
                or not 0 <= manifest["original_mode"] <= 0o7777):
            raise TransactionError("Backup-Manifest ist ungültig.")
        expected = create_plan(original, version, [], manifest["attributes"], backup_id)
        if (len(expected["operations"]) != 1 or manifest["plan_id"] != expected["plan_id"]
                or manifest["before_sha256"] != _digest(original)
                or manifest["after_sha256"] != expected["operations"][0]["after_sha256"]):
            raise TransactionError("Backup oder Manifest ist verändert.")
        if (stat.S_IMODE(config.lstat().st_mode) != manifest["original_mode"]
                or file_attributes(target) != manifest["attributes"]):
            raise TransactionError("Dateiberechtigungen wurden zwischenzeitlich geändert.")
        if current == original:
            return "Bereits im ursprünglichen Zustand; keine Änderung."
        if _digest(current) != manifest["after_sha256"]:
            raise TransactionError("Fremde Zwischenänderung; keine automatische Wiederherstellung.")
        fresh, _ = read_target(target)
        if (fresh != current or stat.S_IMODE(config.lstat().st_mode) != manifest["original_mode"]
                or file_attributes(target) != manifest["attributes"]):
            raise TransactionError("Projektzustand hat sich vor restore geändert.")
        _stage_and_replace(backup, config, original)
        restored, _ = read_target(target)
        if restored != original or file_attributes(target) != manifest["attributes"]:
            raise TransactionError("Zielzustand nach restore stimmt nicht mit dem Backup überein.")
        return "Ursprünglicher Dateizustand wiederhergestellt."
    except (OSError, TransactionError, PathSafetyError, ConfigurationError) as error:
        raise TransactionError(
            f"Restore verweigert oder fehlgeschlagen: {error} "
            f"Backup-ID: {backup_id}; Projekt und Backup für manuelle Wiederherstellung prüfen."
        ) from error
