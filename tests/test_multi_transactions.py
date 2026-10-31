"""Format-4 transactions on isolated synthetic projects."""

import errno
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from project_generator import installed_version
from project_generator import plan as planning
from project_generator import transaction


class MultiTransactions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / "project"
        (self.project / "config").mkdir(parents=True)
        (self.project / "docs").mkdir()
        (self.project / "config/project.yaml").write_bytes((ROOT / "config/project.yaml").read_bytes())
        for name in ("README.md", "AGENTS.md", "docs/DV_KONZEPT.md", "docs/PROJECT_HANDOFF.md"):
            (self.project / name).write_bytes(b"fixture\n")
        self.data = self.base / "data"
        patch = mock.patch.dict(os.environ, {"T0004_BACKUP_HOME": str(self.data)})
        patch.start()
        self.addCleanup(patch.stop)
        self.version = installed_version()
        self.target = str(self.project)

    def plan(self, changes):
        return planning.multi_plan_target(self.target, self.version, changes)

    def apply(self, changes, plan=None):
        plan = plan or self.plan(changes)
        return transaction.apply_multi(self.target, plan, plan["plan_id"], self.version, changes)

    def backup(self, backup_id):
        return self.data / "t0004-generator/backups" / (transaction.BACKUP_PREFIX + backup_id)

    def test_create_files_and_directories_restore_and_repeat(self):
        changes = [("one/a.txt", "create", b"alpha\n"), ("one/nested/b.txt", "create", b"beta\n")]
        plan = self.plan(changes)
        self.assertEqual(plan["format"], 4)
        self.assertEqual(plan, self.plan(list(reversed(changes))))
        self.assertFalse((self.project / "one").exists())
        backup_id = self.apply(changes, plan)
        self.assertEqual((self.project / "one/a.txt").read_bytes(), b"alpha\n")
        self.assertEqual((self.project / "one/nested/b.txt").read_bytes(), b"beta\n")
        manifest = json.loads((self.backup(backup_id) / "manifest.json").read_text())
        self.assertEqual(manifest["format"], 3)
        self.assertEqual(manifest["plan"], plan)
        self.assertIn("wiederhergestellt", transaction.restore(self.target, backup_id))
        self.assertFalse((self.project / "one").exists())
        self.assertIn("keine Änderung", transaction.restore(self.target, backup_id))

    def test_mixed_operations_restore_original_bytes_and_preserve_unrelated_files(self):
        original = b"\xfforiginal\r\nwith\x00bytes"
        (self.project / "existing.bin").write_bytes(original)
        changes = [("existing.bin", "modify", b"updated"), ("new/file.txt", "create", b"new")]
        backup_id = self.apply(changes)
        self.assertEqual((self.project / "existing.bin").read_bytes(), b"updated")
        (self.project / "new/user.txt").write_bytes(b"user")
        self.assertIn("nicht leere Verzeichnisse", transaction.restore(self.target, backup_id))
        self.assertEqual((self.project / "existing.bin").read_bytes(), original)
        self.assertFalse((self.project / "new/file.txt").exists())
        self.assertEqual((self.project / "new/user.txt").read_bytes(), b"user")
        self.assertIn("nicht leere Verzeichnisse", transaction.restore(self.target, backup_id))

    def test_partial_or_invalid_configuration_can_be_restored_from_snapshot(self):
        config = self.project / "config/project.yaml"
        original = config.read_bytes()
        changes = [("config/project.yaml", "modify", b"\xffpartial"),
                   ("new", "create", b"new")]
        backup_id = self.apply(changes)
        transaction.restore(self.target, backup_id)
        self.assertEqual(config.read_bytes(), original)
        self.assertFalse((self.project / "new").exists())

    def test_changed_one_input_rejects_all_without_snapshot(self):
        existing = self.project / "existing.txt"
        existing.write_bytes(b"before")
        changes = [("existing.txt", "modify", b"after"), ("new.txt", "create", b"new")]
        plan = self.plan(changes)
        existing.write_bytes(b"foreign")
        with self.assertRaises(transaction.TransactionError):
            self.apply(changes, plan)
        self.assertEqual(existing.read_bytes(), b"foreign")
        self.assertFalse((self.project / "new.txt").exists())
        self.assertFalse(self.data.exists())

    def test_new_file_appearing_after_plan_is_not_overwritten(self):
        changes = [("a.txt", "create", b"new"), ("b.txt", "create", b"new")]
        plan = self.plan(changes)
        (self.project / "b.txt").write_bytes(b"foreign")
        with self.assertRaises(transaction.TransactionError):
            self.apply(changes, plan)
        self.assertFalse((self.project / "a.txt").exists())
        self.assertEqual((self.project / "b.txt").read_bytes(), b"foreign")

    def test_change_during_snapshot_is_detected_before_first_project_write(self):
        (self.project / "old").write_bytes(b"before")
        changes = [("new", "create", b"new"), ("old", "modify", b"after")]
        plan = self.plan(changes)
        real_progress = transaction._multi_progress

        def foreign_edit(backup, progress):
            real_progress(backup, progress)
            (self.project / "old").write_bytes(b"foreign")

        with mock.patch.object(transaction, "_multi_progress", side_effect=foreign_edit):
            with self.assertRaisesRegex(transaction.TransactionError, "Ziel wurde nicht geschrieben"):
                self.apply(changes, plan)
        self.assertFalse((self.project / "new").exists())
        self.assertEqual((self.project / "old").read_bytes(), b"foreign")

    def test_foreign_change_prevents_all_restore_writes(self):
        (self.project / "old.txt").write_bytes(b"original")
        changes = [("old.txt", "modify", b"result"), ("new.txt", "create", b"new")]
        backup_id = self.apply(changes)
        (self.project / "new.txt").write_bytes(b"foreign")
        with self.assertRaisesRegex(transaction.TransactionError, "Fremde Zwischenänderung"):
            transaction.restore(self.target, backup_id)
        self.assertEqual((self.project / "old.txt").read_bytes(), b"result")
        self.assertEqual((self.project / "new.txt").read_bytes(), b"foreign")

    def test_tampered_plan_or_untrusted_contents_are_refused(self):
        changes = [("a.txt", "create", b"trusted")]
        plan = self.plan(changes)
        altered = json.loads(json.dumps(plan))
        altered["operations"][0]["path"] = "../outside"
        with self.assertRaises(transaction.TransactionError):
            transaction.apply_multi(self.target, altered, plan["plan_id"], self.version, changes)
        with self.assertRaises(transaction.TransactionError):
            transaction.apply_multi(self.target, plan, plan["plan_id"], self.version,
                                    [("a.txt", "create", b"untrusted")])
        with self.assertRaises(transaction.TransactionError):
            transaction.apply_multi(self.target, plan, "0" * 64, self.version, changes)
        self.assertFalse(self.data.exists())

    def test_unsafe_duplicate_and_colliding_paths_are_refused(self):
        for names in (["../outside"], ["/absolute"], ["x\\outside"], [".git/config"],
                      ["NUL.txt"], ["a", "a/b"], ["a", "a-1", "a/b"],
                      ["A/file", "a/other"], ["same", "SAME"], ["foo./bar"]):
            with self.subTest(names=names):
                with self.assertRaises(planning.PathSafetyError):
                    self.plan([(name, "create", b"x") for name in names])

    def test_symlinked_directory_is_refused(self):
        outside = self.base / "outside"
        outside.mkdir()
        try:
            (self.project / "link").symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks not available on this platform")
        with self.assertRaises(planning.PathSafetyError):
            self.plan([("link/file", "create", b"x")])

    def test_hardlinked_file_is_refused(self):
        outside = self.base / "outside"
        outside.mkdir()
        existing = self.project / "existing"
        existing.write_bytes(b"original")
        try:
            os.link(existing, outside / "linked")
        except (OSError, NotImplementedError):
            self.skipTest("Hardlinks not available on this platform")
        with self.assertRaises(planning.PathSafetyError):
            self.plan([("existing", "modify", b"new")])
        self.assertEqual((outside / "linked").read_bytes(), b"original")

    @unittest.skipIf(os.name == "nt", "POSIX mode test")
    def test_changed_file_or_directory_permissions_reject_apply_and_restore(self):
        directory = self.project / "existing"
        directory.mkdir()
        file = directory / "file"
        file.write_bytes(b"original")
        changes = [("existing/file", "modify", b"new"), ("new", "create", b"new")]
        plan = self.plan(changes)
        old_mode = stat.S_IMODE(directory.stat().st_mode)
        directory.chmod(old_mode ^ 0o100)
        with self.assertRaises(transaction.TransactionError):
            self.apply(changes, plan)
        directory.chmod(old_mode)
        backup_id = self.apply(changes)
        mode = stat.S_IMODE(file.stat().st_mode)
        file.chmod(mode ^ 0o100)
        with self.assertRaises(transaction.TransactionError):
            transaction.restore(self.target, backup_id)
        self.assertTrue((self.project / "new").exists())
        file.chmod(mode)
        transaction.restore(self.target, backup_id)
        self.assertEqual(file.read_bytes(), b"original")

    def test_apply_failure_after_first_operation_is_recoverable(self):
        changes = [("a.txt", "create", b"a"), ("b.txt", "create", b"b")]
        plan = self.plan(changes)
        real_create = transaction._multi_create

        def fail_second(path, content, opened):
            if path.name == "b.txt":
                raise OSError(errno.ENOSPC, "simulated")
            return real_create(path, content, opened)

        with mock.patch.object(transaction, "_multi_create", side_effect=fail_second):
            with self.assertRaisesRegex(transaction.TransactionError, plan["backup"]["id"]):
                self.apply(changes, plan)
        self.assertTrue((self.project / "a.txt").exists())
        self.assertFalse((self.project / "b.txt").exists())
        transaction.restore(self.target, plan["backup"]["id"])
        self.assertFalse((self.project / "a.txt").exists())

    def test_partial_create_and_modify_are_recoverable_if_unchanged(self):
        (self.project / "b.txt").write_bytes(b"before")
        changes = [("a.txt", "create", b"created"), ("b.txt", "modify", b"modified")]
        plan = self.plan(changes)

        def partial_create(path, content, opened):
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            opened[0] = True
            with os.fdopen(fd, "wb") as file:
                file.write(b"partial")
            raise OSError(errno.ENOSPC, "simulated")

        with mock.patch.object(transaction, "_multi_create", side_effect=partial_create):
            with self.assertRaises(transaction.TransactionError):
                self.apply(changes, plan)
        self.assertEqual((self.project / "a.txt").read_bytes(), b"partial")
        transaction.restore(self.target, plan["backup"]["id"])
        self.assertFalse((self.project / "a.txt").exists())
        self.assertEqual((self.project / "b.txt").read_bytes(), b"before")

        plan = self.plan(changes)

        def partial_modify(backup, target, content):
            target.write_bytes(b"partial-modify")
            raise OSError(errno.ENOSPC, "simulated")

        with mock.patch.object(transaction, "_stage_and_replace", side_effect=partial_modify):
            with self.assertRaises(transaction.TransactionError):
                self.apply(changes, plan)
        transaction.restore(self.target, plan["backup"]["id"])
        self.assertFalse((self.project / "a.txt").exists())
        self.assertEqual((self.project / "b.txt").read_bytes(), b"before")

    def test_foreign_edit_after_partial_write_blocks_entire_restore(self):
        (self.project / "b").write_bytes(b"before")
        changes = [("a", "create", b"new"), ("b", "modify", b"after")]
        plan = self.plan(changes)

        def partial_modify(backup, target, content):
            target.write_bytes(b"partial")
            raise OSError(errno.ENOSPC, "simulated")

        with mock.patch.object(transaction, "_stage_and_replace", side_effect=partial_modify):
            with self.assertRaises(transaction.TransactionError):
                self.apply(changes, plan)
        (self.project / "b").write_bytes(b"foreign")
        with self.assertRaisesRegex(transaction.TransactionError, "Fremde Zwischenänderung"):
            transaction.restore(self.target, plan["backup"]["id"])
        self.assertEqual((self.project / "a").read_bytes(), b"new")
        self.assertEqual((self.project / "b").read_bytes(), b"foreign")

    def test_foreign_return_to_generator_result_after_partial_apply_is_refused(self):
        (self.project / "b").write_bytes(b"before")
        changes = [("a", "create", b"new"), ("b", "modify", b"after")]
        plan = self.plan(changes)

        def partial_modify(backup, target, content):
            target.write_bytes(b"partial")
            raise OSError(errno.ENOSPC, "simulated")

        with mock.patch.object(transaction, "_stage_and_replace", side_effect=partial_modify):
            with self.assertRaises(transaction.TransactionError):
                self.apply(changes, plan)
        (self.project / "b").write_bytes(b"after")
        with self.assertRaisesRegex(transaction.TransactionError, "Fremde Zwischenänderung"):
            transaction.restore(self.target, plan["backup"]["id"])
        self.assertEqual((self.project / "a").read_bytes(), b"new")
        self.assertEqual((self.project / "b").read_bytes(), b"after")

    def test_failed_directory_record_can_be_recovered(self):
        changes = [("new/file", "create", b"new")]
        plan = self.plan(changes)
        real_record = transaction._multi_record_directory
        calls = 0

        def fail_once(*args):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError(errno.ENOSPC, "simulated")
            return real_record(*args)

        with mock.patch.object(transaction, "_multi_record_directory", side_effect=fail_once):
            with self.assertRaises(transaction.TransactionError):
                self.apply(changes, plan)
        self.assertTrue((self.project / "new").is_dir())
        transaction.restore(self.target, plan["backup"]["id"])
        self.assertFalse((self.project / "new").exists())

    def test_failed_progress_record_refuses_unsafe_restore(self):
        changes = [("file", "create", b"new")]
        plan = self.plan(changes)
        real_progress = transaction._multi_progress

        def fail_file_record(backup, progress):
            if progress["files"]:
                raise OSError(errno.ENOSPC, "simulated")
            return real_progress(backup, progress)

        with mock.patch.object(transaction, "_multi_progress", side_effect=fail_file_record):
            with self.assertRaisesRegex(transaction.TransactionError, "manuelle Wiederherstellung"):
                self.apply(changes, plan)
        with self.assertRaisesRegex(transaction.TransactionError, "Fremde Zwischenänderung"):
            transaction.restore(self.target, plan["backup"]["id"])
        self.assertEqual((self.project / "file").read_bytes(), b"new")

    def test_abrupt_exit_before_create_record_refuses_restore(self):
        changes = [("file", "create", b"new")]
        plan = self.plan(changes)
        script = (
            "import json, os, sys\n"
            "from project_generator import transaction\n"
            "original = transaction._multi_create\n"
            "def crash(path, content, opened):\n"
            "    original(path, content, opened)\n"
            "    os._exit(73)\n"
            "transaction._multi_create = crash\n"
            "plan = json.loads(sys.argv[2])\n"
            "transaction.apply_multi(sys.argv[1], plan, plan['plan_id'], sys.argv[3], "
            "[('file', 'create', b'new')])\n"
        )
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run([sys.executable, "-B", "-c", script, self.target,
                                 json.dumps(plan), self.version], cwd=self.project, env=env)
        self.assertEqual(result.returncode, 73)
        with self.assertRaisesRegex(transaction.TransactionError, "Fremde Zwischenänderung"):
            transaction.restore(self.target, plan["backup"]["id"])
        self.assertEqual((self.project / "file").read_bytes(), b"new")

    def test_failed_stage_write_removes_only_its_own_temporary_file(self):
        private = self.base / "private"
        transaction._private_mkdir(private)
        path = private / "stage"
        original_fdopen = os.fdopen

        class FailedWrite:
            def __init__(self, fd, mode):
                self.file = original_fdopen(fd, mode)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.file.close()

            def write(self, content):
                self.file.write(content[:1])
                raise OSError(errno.ENOSPC, "simulated")

        with mock.patch.object(transaction.os, "fdopen", side_effect=FailedWrite):
            with self.assertRaises(OSError):
                transaction._write_new(path, b"content")
        self.assertFalse(path.exists())
        path.write_bytes(b"existing")
        with self.assertRaises(FileExistsError):
            transaction._write_new(path, b"new")
        self.assertEqual(path.read_bytes(), b"existing")

    @unittest.skipUnless(os.name == "nt", "Windows DACL semantics")
    def test_windows_changed_file_acl_blocks_restore(self):
        (self.project / "old").write_bytes(b"before")
        changes = [("new", "create", b"new"), ("old", "modify", b"after")]
        backup_id = self.apply(changes)
        result = subprocess.run(["icacls", str(self.project / "old"), "/grant", "*S-1-1-0:R"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        with self.assertRaises(transaction.TransactionError):
            transaction.restore(self.target, backup_id)
        self.assertEqual((self.project / "old").read_bytes(), b"after")
        self.assertEqual((self.project / "new").read_bytes(), b"new")

    def test_failed_restore_partial_can_be_retried(self):
        (self.project / "a.txt").write_bytes(b"before")
        changes = [("a.txt", "modify", b"after"), ("b.txt", "create", b"new")]
        backup_id = self.apply(changes)

        def partial_restore(backup, target, content):
            target.write_bytes(b"partial")
            raise OSError(errno.ENOSPC, "simulated")

        with mock.patch.object(transaction, "_stage_and_replace", side_effect=partial_restore):
            with self.assertRaisesRegex(transaction.TransactionError, "Teilzustand erfasst"):
                transaction.restore(self.target, backup_id)
        self.assertEqual((self.project / "a.txt").read_bytes(), b"partial")
        transaction.restore(self.target, backup_id)
        self.assertEqual((self.project / "a.txt").read_bytes(), b"before")
        self.assertFalse((self.project / "b.txt").exists())

    def test_foreign_return_to_generator_result_after_partial_restore_is_refused(self):
        (self.project / "b.txt").write_bytes(b"before")
        changes = [("b.txt", "modify", b"after"), ("z.txt", "create", b"new")]
        backup_id = self.apply(changes)

        def partial_restore(backup, target, content):
            target.write_bytes(b"partial")
            raise OSError(errno.ENOSPC, "simulated")

        with mock.patch.object(transaction, "_stage_and_replace", side_effect=partial_restore):
            with self.assertRaisesRegex(transaction.TransactionError, "Teilzustand erfasst"):
                transaction.restore(self.target, backup_id)
        (self.project / "b.txt").write_bytes(b"after")
        with self.assertRaisesRegex(transaction.TransactionError, "Fremde Zwischenänderung"):
            transaction.restore(self.target, backup_id)
        self.assertEqual((self.project / "z.txt").read_bytes(), b"new")
        self.assertEqual((self.project / "b.txt").read_bytes(), b"after")

    def test_restore_failure_after_removing_first_file_can_be_retried(self):
        (self.project / "b").write_bytes(b"before")
        changes = [("a", "create", b"new"), ("b", "modify", b"after")]
        backup_id = self.apply(changes)
        with mock.patch.object(transaction, "_stage_and_replace",
                               side_effect=OSError(errno.ENOSPC, "simulated")):
            with self.assertRaises(transaction.TransactionError):
                transaction.restore(self.target, backup_id)
        self.assertFalse((self.project / "a").exists())
        self.assertEqual((self.project / "b").read_bytes(), b"after")
        transaction.restore(self.target, backup_id)
        self.assertEqual((self.project / "b").read_bytes(), b"before")

    def test_unrecorded_created_file_requires_manual_recovery(self):
        changes = [("file", "create", b"content")]
        backup_id = self.apply(changes)
        progress = self.backup(backup_id) / "progress.json"
        data = json.loads(progress.read_text())
        data["files"] = {}
        progress.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(transaction.TransactionError, "Fremde Zwischenänderung"):
            transaction.restore(self.target, backup_id)
        self.assertEqual((self.project / "file").read_bytes(), b"content")

    def test_tampered_snapshot_is_rejected_before_any_restore(self):
        (self.project / "old").write_bytes(b"original")
        changes = [("new", "create", b"new"), ("old", "modify", b"after")]
        backup_id = self.apply(changes)
        (self.backup(backup_id) / "original-01").write_bytes(b"tampered")
        with self.assertRaises(transaction.TransactionError):
            transaction.restore(self.target, backup_id)
        self.assertEqual((self.project / "old").read_bytes(), b"after")
        self.assertEqual((self.project / "new").read_bytes(), b"new")

    def test_replaced_directory_is_not_followed_during_restore(self):
        changes = [("new/file", "create", b"new")]
        backup_id = self.apply(changes)
        (self.project / "new/file").unlink()
        (self.project / "new").rmdir()
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "file").write_bytes(b"foreign")
        try:
            (self.project / "new").symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks not available on this platform")
        with self.assertRaises(transaction.TransactionError):
            transaction.restore(self.target, backup_id)
        self.assertEqual((outside / "file").read_bytes(), b"foreign")

    def test_format_3_plan_and_manifest_2_still_work(self):
        _, plan = planning.plan_target(self.target, self.version)
        self.assertEqual(plan["format"], 3)
        plan_file = self.base / "plan.json"
        plan_file.write_text(json.dumps(plan), encoding="utf-8")
        old_backup = transaction.apply(self.target, str(plan_file), plan["plan_id"], self.version)
        manifest = json.loads((self.backup(old_backup) / "manifest.json").read_text())
        self.assertEqual(manifest["format"], 2)
        new_backup = self.apply([("file", "create", b"new")])
        transaction.restore(self.target, new_backup)
        transaction.restore(self.target, old_backup)
        self.assertEqual((self.project / "config/project.yaml").read_bytes(),
                         (ROOT / "config/project.yaml").read_bytes())


if __name__ == "__main__":
    unittest.main()
