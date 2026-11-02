"""Synthetic-only experiment; this is not a backup gate or a public API.

The test owns the three temporary trees and the two Robocopy invocations. It
assumes an honest operating system and executable and exclusive access; it
cannot prove which process wrote identical bytes or detect transient changes.
"""

import hashlib
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from project_generator.migrate import _safe_git_layout
from project_generator.plan import PathSafetyError, _is_link, _windows_check_streams, _windows_security_component


class PrototypeError(ValueError):
    pass


def _directory_streams(path):
    """Reject directory ADS; FindFirstStream may report no streams for a directory."""
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
    data = StreamData()
    handle = kernel.FindFirstStreamW(str(path), 0, ctypes.byref(data), 0)
    if handle == ctypes.c_void_p(-1).value:
        if ctypes.get_last_error() == 38:  # ERROR_HANDLE_EOF
            return
        raise PrototypeError("directory streams cannot be enumerated")
    try:
        while True:
            if data.name != "::$DATA":
                raise PrototypeError("directory alternate stream is unsupported")
            if not kernel.FindNextStreamW(handle, ctypes.byref(data)):
                if ctypes.get_last_error() != 38:
                    raise PrototypeError("directory streams cannot be enumerated")
                break
    finally:
        kernel.FindClose(handle)


def _tree(root):
    """Compare bytes, paths and a limited set of metadata, including the root."""
    entries = {}
    stack = [(root, ".")]
    while stack:
        path, rel = stack.pop()
        info = path.lstat()
        if _is_link(path):
            raise PrototypeError("links and reparse points are unsupported")
        directory = stat.S_ISDIR(info.st_mode)
        if not directory and not stat.S_ISREG(info.st_mode):
            raise PrototypeError("unsupported object")
        if directory:
            _directory_streams(path)
            with os.scandir(path) as children:
                for child in children:
                    name = child.name if rel == "." else rel + "/" + child.name
                    stack.append((Path(child.path), name))
            content = None
        else:
            content = hashlib.sha256(path.read_bytes()).hexdigest()
        # Git commonly marks loose objects read-only. Record that flag rather
        # than using the write-engine's stricter replacement-only policy.
        try:
            if info.st_file_attributes & ~(0x1 | 0x2 | 0x4 | 0x10 | 0x20 | 0x80 | 0x100 | 0x2000):
                raise PrototypeError("unsupported Windows file attributes")
            if not directory:
                if info.st_nlink != 1:
                    raise PrototypeError("hardlinks are unsupported")
                _windows_check_streams(path)
            metadata = (info.st_file_attributes, _windows_security_component(path, 7))
        except (OSError, PathSafetyError) as error:
            raise PrototypeError("unsupported or unreadable metadata") from error
        entries[rel] = ("directory" if directory else "file", content, info.st_mtime_ns, metadata)
    return entries


def _git(root, *args):
    if not _safe_git_layout(root / ".git", root.stat().st_dev):
        raise PrototypeError("unsafe Git layout or external object store")
    env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR", "PATHEXT", "TEMP", "TMP") if key in os.environ}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_OPTIONAL_LOCKS="0",
               GIT_TERMINAL_PROMPT="0", GIT_NO_LAZY_FETCH="1", GIT_NO_REPLACE_OBJECTS="1")
    result = subprocess.run(["git", "--no-optional-locks", "-c", "core.fsmonitor=false",
                             "--git-dir", str(root / ".git"), "--work-tree", str(root), *args],
                            cwd=root, env=env, capture_output=True, timeout=30)
    if result.returncode:
        raise PrototypeError("Git verification failed")
    return result.stdout


def _git_state(root):
    return (_git(root, "rev-parse", "HEAD"), _git(root, "symbolic-ref", "HEAD"),
            _git(root, "for-each-ref", "--format=%(refname) %(objectname)"),
            _git(root, "rev-list", "--all"), hashlib.sha256((root / ".git" / "index").read_bytes()).digest())


def _copy(source, destination):
    if os.path.lexists(destination):
        raise PrototypeError("destination must not exist")
    result = subprocess.run(["robocopy", str(source), str(destination), "/E", "/COPY:DATS",
                             "/DCOPY:DAT", "/R:0", "/W:0", "/XJ", "/NP"],
                            capture_output=True, timeout=60)
    # A nonempty synthetic Git fixture copied to a new destination must report
    # copied files and no extras/mismatches. Tree comparison independently
    # detects missing/skipped files; do not parse localized Robocopy output.
    if result.returncode != 1:
        raise PrototypeError(f"robocopy did not complete cleanly ({result.returncode})")


def _experiment(base, hook=lambda stage: None):
    """Only called on the fixture created by this test module, never a user project."""
    source, backup, restore = (base / name for name in ("source", "backup", "restore"))
    original = _tree(source)
    original_git = _git_state(source)
    _copy(source, backup)
    hook("after_backup")
    if _tree(backup) != original or _git_state(backup) != original_git:
        raise PrototypeError("backup differs from source")
    backup_before = _tree(backup)
    hook("before_restore")
    _copy(backup, restore)
    hook("after_restore")
    if _tree(backup) != backup_before or _tree(restore) != backup_before:
        raise PrototypeError("backup changed or restore differs from backup")
    if _git_state(restore) != original_git:
        raise PrototypeError("restored Git data differs")
    _git(restore, "fsck", "--full")
    hook("before_final_source")
    if _tree(source) != original or _git_state(source) != original_git or _tree(backup) != backup_before:
        raise PrototypeError("source or backup changed during test")


@unittest.skipUnless(os.name == "nt" and shutil.which("git") and shutil.which("robocopy"), "Windows Git and Robocopy required")
class WindowsBackupPrototype(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="t0004-synthetic-backup-prototype-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.source = self.base / "source"
        self.source.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Synthetic")
        self.git("config", "user.email", "synthetic@example.invalid")
        self.git("config", "core.autocrlf", "false")
        (self.source / ".gitignore").write_text("ignored/\n", encoding="utf-8")
        (self.source / "tracked.txt").write_bytes(b"first\n")
        self.git("add", ".")
        self.git("commit", "-qm", "first")
        self.git("tag", "fixture")
        (self.source / "tracked.txt").write_bytes(b"second\n")
        self.git("add", "tracked.txt")
        self.git("commit", "-qm", "second")
        self.git("branch", "fixture")
        (self.source / "untracked.txt").write_bytes(b"synthetic untracked")
        (self.source / "ignored").mkdir()
        (self.source / "ignored" / "ignored.txt").write_bytes(b"synthetic ignored")
        (self.source / "empty").mkdir()

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.source, check=True, capture_output=True)

    def remove_copies(self):
        def clear_readonly(function, name, error):
            os.chmod(name, stat.S_IWRITE)
            function(name)
        for name in ("backup", "restore"):
            path = self.base / name
            if path.exists():
                shutil.rmtree(path, onexc=clear_readonly)

    def test_success(self):
        _experiment(self.base)

    def test_manipulated_and_missing_backup_files(self):
        for action in ("modify", "remove"):
            with self.subTest(action=action):
                def sabotage(stage):
                    if stage == "before_restore":
                        path = self.base / "backup" / "ignored" / "ignored.txt"
                        path.write_bytes(b"bad") if action == "modify" else path.unlink()
                with self.assertRaises(PrototypeError):
                    _experiment(self.base, sabotage)
                self.remove_copies()

    def test_untrusted_preexisting_restore_rejected(self):
        def sabotage(stage):
            if stage == "before_restore":
                shutil.copytree(self.source, self.base / "restore")
        with self.assertRaisesRegex(PrototypeError, "destination must not exist"):
            _experiment(self.base, sabotage)

    def test_redirected_restore_cannot_hide_bad_backup(self):
        original_copy = _copy
        def sabotage(stage):
            if stage == "before_restore":
                (self.base / "backup" / "ignored" / "ignored.txt").write_bytes(b"bad backup")
        def redirected(source, destination):
            # Simulate a dishonest second invocation that copies the original
            # source even though the caller supplied the backup path.
            original_copy(self.source if source == self.base / "backup" else source, destination)
        with mock.patch(__name__ + "._copy", side_effect=redirected):
            with self.assertRaisesRegex(PrototypeError, "backup changed"):
                _experiment(self.base, sabotage)

    def test_identical_source_redirect_is_indistinguishable(self):
        # A compromised copy routine can read the source when both trees are
        # identical. This documents the trust boundary, not a security success.
        original_copy = _copy
        def redirected(source, destination):
            original_copy(self.source if source == self.base / "backup" else source, destination)
        with mock.patch(__name__ + "._copy", side_effect=redirected):
            _experiment(self.base)

    def test_git_index_and_reference_changes(self):
        for relative in (".git/index", ".git/refs/heads/fixture"):
            with self.subTest(path=relative):
                def sabotage(stage):
                    if stage == "after_restore":
                        (self.base / "restore" / relative).write_bytes(b"modified")
                with self.assertRaises(PrototypeError):
                    _experiment(self.base, sabotage)
                self.remove_copies()

    def test_robocopy_failure(self):
        for code in (0, 2, 3, 7, 8, 16):
            with self.subTest(exit_code=code):
                with mock.patch(__name__ + ".subprocess.run", return_value=subprocess.CompletedProcess([], code)):
                    with self.assertRaisesRegex(PrototypeError, "robocopy"):
                        _copy(self.source, self.base / "backup")

    def test_second_robocopy_failure(self):
        original_copy = _copy
        def fail_restore(source, destination):
            if source == self.base / "backup":
                raise PrototypeError("robocopy failed")
            original_copy(source, destination)
        with mock.patch(__name__ + "._copy", side_effect=fail_restore):
            with self.assertRaisesRegex(PrototypeError, "robocopy failed"):
                _experiment(self.base)

    def test_unsupported_stream(self):
        try:
            with open(str(self.source / "untracked.txt") + ":extra", "wb") as stream:
                stream.write(b"synthetic")
        except OSError:
            self.skipTest("ADS unavailable")
        with self.assertRaises(PrototypeError):
            _experiment(self.base)

    def test_hardlink_rejected(self):
        os.link(self.source / "untracked.txt", self.source / "linked.txt")
        with self.assertRaises(PrototypeError):
            _experiment(self.base)

    def test_directory_stream_rejected(self):
        try:
            with open(str(self.source / "empty") + ":extra", "wb") as stream:
                stream.write(b"synthetic")
        except OSError:
            self.skipTest("directory ADS unavailable")
        with self.assertRaisesRegex(PrototypeError, "directory alternate stream"):
            _experiment(self.base)

    def test_external_git_object_store_rejected(self):
        (self.source / ".git" / "objects" / "info" / "alternates").write_text("outside", encoding="utf-8")
        with self.assertRaisesRegex(PrototypeError, "external object store"):
            _experiment(self.base)

    def test_junction_rejected(self):
        link = self.source / "junction"
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(self.source / "empty")],
                                capture_output=True)
        if result.returncode:
            self.skipTest("junction unavailable")
        self.addCleanup(lambda: os.rmdir(link) if link.exists() else None)
        with self.assertRaisesRegex(PrototypeError, "links and reparse"):
            _experiment(self.base)

    def test_changed_acl_is_rejected(self):
        def sabotage(stage):
            if stage == "after_restore":
                path = self.base / "restore" / "untracked.txt"
                subprocess.run(["icacls", str(path), "/grant", "*S-1-1-0:R"],
                               check=True, capture_output=True)
        with self.assertRaisesRegex(PrototypeError, "restore differs"):
            _experiment(self.base, sabotage)

    def test_changed_timestamp_is_rejected(self):
        def sabotage(stage):
            if stage == "after_restore":
                path = self.base / "restore" / "untracked.txt"
                info = path.stat()
                os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns - 2_000_000_000))
        with self.assertRaisesRegex(PrototypeError, "restore differs"):
            _experiment(self.base, sabotage)

    def test_changed_file_attributes_are_rejected(self):
        def sabotage(stage):
            if stage == "after_restore":
                os.chmod(self.base / "restore" / "untracked.txt", stat.S_IREAD)
        with self.assertRaisesRegex(PrototypeError, "restore differs"):
            _experiment(self.base, sabotage)

    def test_source_change_rejected(self):
        def sabotage(stage):
            if stage == "before_final_source":
                (self.source / "untracked.txt").write_bytes(b"changed")
        with self.assertRaisesRegex(PrototypeError, "source or backup changed"):
            _experiment(self.base, sabotage)


if __name__ == "__main__":
    unittest.main()
