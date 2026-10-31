"""Safe apply and restore tests confined to temporary projects."""

import hashlib
import errno
import json
import os
from pathlib import Path
import re
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
from project_generator.plan import _windows_security_component

SOURCE_CONFIG = (ROOT / "config/project.yaml").read_text(encoding="utf-8")


class Transactions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.data_home = self.base / "local data"
        self.backups = self.data_home / "t0004-generator" / "backups"
        environment = mock.patch.dict(os.environ, {"T0004_BACKUP_HOME": str(self.data_home)})
        environment.start()
        self.addCleanup(environment.stop)
        self.project = self.base / "Projekt mit Leerzeichen"
        (self.project / "config").mkdir(parents=True)
        (self.project / "docs").mkdir()
        self.config = self.project / "config" / "project.yaml"
        self.original = SOURCE_CONFIG.replace(
            "version: null\n  modules", "version: null  # secret-example\n  modules"
        ).replace("\n", "\r\n").encode("utf-8")
        self.config.write_bytes(self.original)
        for name in ("README.md", "AGENTS.md", "docs/DV_KONZEPT.md", "docs/PROJECT_HANDOFF.md"):
            (self.project / name).write_text("fixture\n", encoding="utf-8")
        self.plan_file = self.base / "plan.json"

    def cli(self, *args):
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run(
            [sys.executable, "-B", "-m", "project_generator", *args],
            cwd=self.project, env=env, capture_output=True, text=True, encoding="utf-8",
        )

    def plan(self):
        before = self.config.read_bytes()
        result = self.cli("plan", str(self.project), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("secret-example", result.stdout)
        self.assertEqual(self.config.read_bytes(), before)
        self.plan_file.write_text(result.stdout, encoding="utf-8")
        return json.loads(result.stdout)

    def apply(self, plan):
        return self.cli("apply", str(self.project), "--plan", str(self.plan_file),
                        "--confirm", plan["plan_id"])

    def backup_id(self, output):
        match = re.search(r"Backup-ID: ([0-9a-f]{32})", output)
        self.assertIsNotNone(match, output)
        return match.group(1)

    def test_confirmation_is_required(self):
        self.plan()
        result = self.cli("apply", str(self.project), "--plan", str(self.plan_file))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.config.read_bytes(), self.original)
        self.assertFalse(self.backups.exists())

    def test_tampered_plan_and_confirmation_are_refused(self):
        plan = self.plan()
        plan["operations"][0]["path"] = "../outside"
        self.plan_file.write_text(json.dumps(plan), encoding="utf-8")
        result = self.apply(plan)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("verändert", result.stderr)
        self.assertEqual(self.config.read_bytes(), self.original)
        plan = self.plan()
        result = self.cli("apply", str(self.project), "--plan", str(self.plan_file),
                          "--confirm", "0" * 64)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(self.backups.exists())
        plan = self.plan()
        plan["read_only"] = 1
        self.plan_file.write_text(json.dumps(plan), encoding="utf-8")
        self.assertEqual(self.apply(plan).returncode, 1)

    def test_invalid_or_duplicate_json_is_refused_without_traceback(self):
        plan = self.plan()
        for data in ('{"format": 2, "format": 2}', '{"format": ' + "9" * 10000 + "}"):
            self.plan_file.write_text(data, encoding="utf-8")
            result = self.apply(plan)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.config.read_bytes(), self.original)

    def test_utf8_bom_plan_is_accepted(self):
        plan = self.plan()
        self.plan_file.write_bytes(b"\xef\xbb\xbf" + self.plan_file.read_bytes())
        result = self.apply(plan)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_metadata_variants_preserve_other_bytes(self):
        version = installed_version().encode("ascii")
        for value in (b"null", b"~", b""):
            with self.subTest(value=value):
                source = self.original.replace(b"version: null  # secret-example",
                                               b"version: " + value + b"  # secret-example")
                result = transaction.metadata_result(source, version.decode("ascii"))
                expected = source.replace(b"version: " + value + b"  # secret-example",
                                          b'version: "' + version + b'"  # secret-example')
                self.assertEqual(result, expected)

    def test_oversized_result_is_rejected_before_writing(self):
        size = transaction.MAX_CONFIG_BYTES
        original = self.original + b"#" + b"x" * (size - len(self.original) - 2) + b"\n"
        self.config.write_bytes(original)
        result = self.cli("plan", str(self.project), "--json")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("überschreitet", result.stderr)
        self.assertEqual(self.config.read_bytes(), original)
        self.assertFalse(self.backups.exists())

    def test_stale_plan_and_missing_required_file_are_refused(self):
        plan = self.plan()
        changed = self.original + b"# user edit\r\n"
        self.config.write_bytes(changed)
        result = self.apply(plan)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.config.read_bytes(), changed)
        plan = self.plan()
        (self.project / "README.md").unlink()
        result = self.apply(plan)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.config.read_bytes(), changed)

    def test_apply_snapshot_restore_and_repeated_restore(self):
        plan = self.plan()
        self.assertEqual(plan["operations"][0]["before_sha256"], hashlib.sha256(self.original).hexdigest())
        self.assertEqual(plan["backup"]["before"], "not_exists")
        self.assertFalse((self.backups / plan["backup"]["directory"]).exists())
        result = self.apply(plan)
        self.assertEqual(result.returncode, 0, result.stderr)
        backup_id = self.backup_id(result.stdout)
        self.assertEqual(backup_id, plan["backup"]["id"])
        backup = self.backups / (transaction.BACKUP_PREFIX + backup_id)
        manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual((backup / "original").read_bytes(), self.original)
        self.assertEqual(manifest["plan_id"], plan["plan_id"])
        self.assertEqual(hashlib.sha256(self.config.read_bytes()).hexdigest(),
                         plan["operations"][0]["after_sha256"])
        self.assertIn(b"# secret-example\r\n", self.config.read_bytes())
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((backup / "original").stat().st_mode), 0o600)
        restored = self.cli("restore", str(self.project), "--backup", backup_id)
        self.assertEqual(restored.returncode, 0, restored.stderr)
        self.assertEqual(self.config.read_bytes(), self.original)
        repeated = self.cli("restore", str(self.project), "--backup", backup_id)
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        self.assertIn("keine Änderung", repeated.stdout)

    def test_snapshot_stays_outside_git_worktree_and_is_not_staged(self):
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        plan = self.plan()
        self.assertFalse(self.data_home.exists())
        applied = self.apply(plan)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        backup_id = self.backup_id(applied.stdout)
        subprocess.run(["git", "-C", str(self.project), "add", "-A"], check=True)
        tracked = subprocess.run(["git", "-C", str(self.project), "ls-files", "-z"],
                                 check=True, capture_output=True).stdout.split(b"\0")
        self.assertFalse(any(b".t0004-backup-" in name for name in tracked))
        self.assertTrue((self.backups / (transaction.BACKUP_PREFIX + backup_id) / "original").is_file())
        self.assertFalse(list(self.project.rglob(".t0004-backup-*")))
        restored = self.cli("restore", str(self.project), "--backup", backup_id)
        self.assertEqual(restored.returncode, 0, restored.stderr)
        self.assertEqual(self.config.read_bytes(), self.original)

    def test_existing_legacy_backup_in_project_is_reported_without_changes(self):
        legacy = self.project / (transaction.BACKUP_PREFIX + "a" * 32)
        legacy.mkdir()
        (legacy / "original").write_bytes(b"legacy-secret")
        result = self.cli("plan", str(self.project), "--json")
        self.assertEqual(result.returncode, 1, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(plan["operations"], [])
        self.assertIn("Altes Backup", plan["conflicts"][0])
        self.assertNotIn("legacy-secret", result.stdout + result.stderr)
        self.assertEqual((legacy / "original").read_bytes(), b"legacy-secret")
        self.assertFalse(self.backups.exists())

    def test_storage_inside_another_git_worktree_is_rejected(self):
        other = self.base / "other-repo"
        other.mkdir()
        subprocess.run(["git", "init", "-q", str(other)], check=True)
        with mock.patch.dict(os.environ, {"T0004_BACKUP_HOME": str(other / "data")}):
            result = self.cli("plan", str(self.project), "--json")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("Git-Arbeitsverzeichnis", result.stderr)
        self.assertFalse((other / "data").exists())
        self.assertEqual(self.config.read_bytes(), self.original)

    def test_git_worktree_marker_file_is_rejected(self):
        other = self.base / "linked-worktree"
        other.mkdir()
        (other / ".git").write_text("gitdir: ../external-git\n", encoding="utf-8")
        with mock.patch.dict(os.environ, {"T0004_BACKUP_HOME": str(other / "data")}):
            result = self.cli("plan", str(self.project), "--json")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("Git-Arbeitsverzeichnis", result.stderr)
        self.assertFalse((other / "data").exists())

    def test_plan_cannot_be_applied_to_another_project_or_store(self):
        plan = self.plan()
        other = self.base / "second project"
        (other / "config").mkdir(parents=True)
        (other / "docs").mkdir()
        (other / "config" / "project.yaml").write_bytes(self.original)
        for name in ("README.md", "AGENTS.md", "docs/DV_KONZEPT.md", "docs/PROJECT_HANDOFF.md"):
            (other / name).write_text("fixture\n", encoding="utf-8")
        result = self.cli("apply", str(other), "--plan", str(self.plan_file), "--confirm", plan["plan_id"])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual((other / "config/project.yaml").read_bytes(), self.original)
        with mock.patch.dict(os.environ, {"T0004_BACKUP_HOME": str(self.base / "other-data")}):
            result = self.apply(plan)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.config.read_bytes(), self.original)
        self.assertFalse(self.backups.exists())

    def test_backup_cannot_restore_another_project(self):
        plan = self.plan()
        applied = self.apply(plan)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        backup_id = self.backup_id(applied.stdout)
        other = self.base / "other-project"
        (other / "config").mkdir(parents=True)
        (other / "docs").mkdir()
        other_config = other / "config" / "project.yaml"
        other_config.write_bytes(self.config.read_bytes())
        for name in ("README.md", "AGENTS.md", "docs/DV_KONZEPT.md", "docs/PROJECT_HANDOFF.md"):
            (other / name).write_text("fixture\n", encoding="utf-8")
        restored = self.cli("restore", str(other), "--backup", backup_id)
        self.assertEqual(restored.returncode, 1, restored.stderr)
        self.assertEqual(other_config.read_bytes(), self.config.read_bytes())

    def test_symlinked_storage_is_rejected(self):
        actual = self.base / "actual-data"
        actual.mkdir()
        try:
            self.data_home.symlink_to(actual, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("directory symlinks unavailable")
        result = self.cli("plan", str(self.project), "--json")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("Symlinks", result.stderr)
        self.assertFalse(list(actual.iterdir()))

    @unittest.skipIf(os.name == "nt", "Codespaces runs on Linux")
    def test_codespaces_default_uses_persistent_workspace_storage(self):
        persistent = self.base / "persistent-workspace"
        with mock.patch.dict(os.environ, {"CODESPACES": "true"}, clear=True), \
                mock.patch.object(planning, "CODESPACES_DATA_HOME", persistent):
            store = planning.backup_store(str(self.project))
        self.assertEqual(store, persistent / "t0004-generator" / "backups")
        self.assertFalse(persistent.exists())

    def test_foreign_edit_prevents_restore(self):
        plan = self.plan()
        applied = self.apply(plan)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        backup_id = self.backup_id(applied.stdout)
        changed = self.config.read_bytes() + b"# foreign edit\r\n"
        self.config.write_bytes(changed)
        restored = self.cli("restore", str(self.project), "--backup", backup_id)
        self.assertEqual(restored.returncode, 1, restored.stderr)
        self.assertIn("Fremde Zwischenänderung", restored.stderr)
        self.assertEqual(self.config.read_bytes(), changed)

    def test_existing_backup_path_invalidates_plan(self):
        plan = self.plan()
        collision = self.backups / plan["backup"]["directory"]
        collision.mkdir(parents=True)
        (collision / "foreign").write_text("keep", encoding="utf-8")
        result = self.apply(plan)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual((collision / "foreign").read_text(encoding="utf-8"), "keep")
        self.assertEqual(self.config.read_bytes(), self.original)

    def test_existing_stage_is_not_deleted_on_restore(self):
        plan = self.plan()
        applied = self.apply(plan)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        backup_id = self.backup_id(applied.stdout)
        stage = self.backups / plan["backup"]["temporary"]
        stage.write_bytes(b"foreign data")
        current = self.config.read_bytes()
        restored = self.cli("restore", str(self.project), "--backup", backup_id)
        self.assertEqual(restored.returncode, 1, restored.stderr)
        self.assertEqual(stage.read_bytes(), b"foreign data")
        self.assertEqual(self.config.read_bytes(), current)

    def test_deleted_config_requires_manual_recovery(self):
        plan = self.plan()
        applied = self.apply(plan)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        backup_id = self.backup_id(applied.stdout)
        self.config.unlink()
        restored = self.cli("restore", str(self.project), "--backup", backup_id)
        self.assertEqual(restored.returncode, 1, restored.stderr)
        self.assertIn("manuelle Wiederherstellung", restored.stderr)
        self.assertFalse(self.config.exists())

    @unittest.skipIf(os.name == "nt", "POSIX mode semantics")
    def test_changed_permissions_prevent_apply_and_restore(self):
        plan = self.plan()
        original_mode = stat.S_IMODE(self.config.stat().st_mode)
        os.chmod(self.config, original_mode ^ 0o040)
        result = self.apply(plan)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.config.read_bytes(), self.original)
        os.chmod(self.config, original_mode)
        plan = self.plan()
        applied = self.apply(plan)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        backup_id = self.backup_id(applied.stdout)
        current = self.config.read_bytes()
        os.chmod(self.config, original_mode ^ 0o040)
        restored = self.cli("restore", str(self.project), "--backup", backup_id)
        self.assertEqual(restored.returncode, 1, restored.stderr)
        self.assertIn("Dateiberechtigungen", restored.stderr)
        self.assertEqual(self.config.read_bytes(), current)

    @unittest.skipUnless(hasattr(os, "setxattr"), "extended attributes unavailable")
    def test_extended_attributes_preserved_and_foreign_change_refused(self):
        try:
            os.setxattr(self.config, "user.t0004-test", b"original")
        except OSError:
            self.skipTest("filesystem does not support user extended attributes")
        plan = self.plan()
        applied = self.apply(plan)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertEqual(os.getxattr(self.config, "user.t0004-test"), b"original")
        backup_id = self.backup_id(applied.stdout)
        os.setxattr(self.config, "user.t0004-test", b"foreign")
        restored = self.cli("restore", str(self.project), "--backup", backup_id)
        self.assertEqual(restored.returncode, 1, restored.stderr)
        self.assertEqual(os.getxattr(self.config, "user.t0004-test"), b"foreign")

    @unittest.skipIf(os.name == "nt", "POSIX mode semantics")
    def test_insecure_backup_directory_prevents_restore(self):
        plan = self.plan()
        applied = self.apply(plan)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        backup_id = self.backup_id(applied.stdout)
        backup = self.backups / (transaction.BACKUP_PREFIX + backup_id)
        os.chmod(backup, 0o755)
        current = self.config.read_bytes()
        restored = self.cli("restore", str(self.project), "--backup", backup_id)
        self.assertEqual(restored.returncode, 1, restored.stderr)
        self.assertIn("nicht ausreichend geschützt", restored.stderr)
        self.assertEqual(self.config.read_bytes(), current)

    @unittest.skipIf(os.name == "nt", "POSIX mode semantics")
    def test_insecure_backup_file_prevents_restore(self):
        plan = self.plan()
        applied = self.apply(plan)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        backup_id = self.backup_id(applied.stdout)
        backup = self.backups / (transaction.BACKUP_PREFIX + backup_id)
        os.chmod(backup / "original", 0o644)
        current = self.config.read_bytes()
        restored = self.cli("restore", str(self.project), "--backup", backup_id)
        self.assertEqual(restored.returncode, 1, restored.stderr)
        self.assertIn("nicht ausreichend geschützt", restored.stderr)
        self.assertEqual(self.config.read_bytes(), current)

    @unittest.skipIf(os.name == "nt", "POSIX mode semantics")
    def test_insecure_store_prevents_snapshot_and_write(self):
        plan = self.plan()
        self.backups.parent.mkdir(parents=True)
        os.chmod(self.backups.parent, 0o755)
        result = self.apply(plan)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("nicht ausreichend geschützt", result.stderr)
        self.assertIn("Ziel wurde nicht geschrieben", result.stderr)
        self.assertEqual(self.config.read_bytes(), self.original)
        self.assertFalse((self.backups / plan["backup"]["directory"]).exists())

    @unittest.skipUnless(os.name == "nt", "Windows DACL semantics")
    def test_windows_replace_preserves_access_metadata(self):
        before = {
            "mode": stat.S_IMODE(self.config.stat().st_mode),
            "owner": _windows_security_component(self.config, 1),
            "group": _windows_security_component(self.config, 2),
            "dacl": _windows_security_component(self.config, 4),
        }
        backup = self.base / ".private-fixture"
        transaction._private_mkdir(backup)
        stage = backup / "stage"
        transaction._write_new(stage, self.original + b"# fixture\r\n")
        transaction._replace(stage, self.config)
        after = {
            "mode": stat.S_IMODE(self.config.stat().st_mode),
            "owner": _windows_security_component(self.config, 1),
            "group": _windows_security_component(self.config, 2),
            "dacl": _windows_security_component(self.config, 4),
        }
        changed = [key for key in before if before[key] != after[key]]
        self.assertEqual(changed, [])

    @unittest.skipUnless(os.name == "nt", "Windows DACL semantics")
    def test_windows_insecure_backup_dacl_prevents_restore(self):
        plan = self.plan()
        applied = self.apply(plan)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        backup_id = self.backup_id(applied.stdout)
        backup = self.backups / (transaction.BACKUP_PREFIX + backup_id)
        changed_acl = subprocess.run(
            ["icacls", str(backup), "/grant", "*S-1-1-0:(OI)(CI)F"],
            capture_output=True, text=True,
        )
        self.assertEqual(changed_acl.returncode, 0, changed_acl.stderr)
        current = self.config.read_bytes()
        restored = self.cli("restore", str(self.project), "--backup", backup_id)
        self.assertEqual(restored.returncode, 1, restored.stderr)
        self.assertIn("Zugriffsrechte", restored.stderr)
        self.assertEqual(self.config.read_bytes(), current)

    @unittest.skipUnless(os.name == "nt", "Windows DACL semantics")
    def test_windows_insecure_backup_file_dacl_prevents_restore(self):
        plan = self.plan()
        applied = self.apply(plan)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        backup_id = self.backup_id(applied.stdout)
        backup = self.backups / (transaction.BACKUP_PREFIX + backup_id)
        changed_acl = subprocess.run(
            ["icacls", str(backup / "original"), "/grant", "*S-1-1-0:R"],
            capture_output=True, text=True,
        )
        self.assertEqual(changed_acl.returncode, 0, changed_acl.stderr)
        current = self.config.read_bytes()
        restored = self.cli("restore", str(self.project), "--backup", backup_id)
        self.assertEqual(restored.returncode, 1, restored.stderr)
        self.assertIn("Zugriffsrechte", restored.stderr)
        self.assertEqual(self.config.read_bytes(), current)

    def test_tampered_backup_and_path_traversal_are_refused(self):
        plan = self.plan()
        applied = self.apply(plan)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        backup_id = self.backup_id(applied.stdout)
        backup = self.backups / (transaction.BACKUP_PREFIX + backup_id)
        (backup / "original").write_bytes(self.original + b"# modified\n")
        current = self.config.read_bytes()
        restored = self.cli("restore", str(self.project), "--backup", backup_id)
        self.assertEqual(restored.returncode, 1, restored.stderr)
        self.assertEqual(self.config.read_bytes(), current)
        self.assertEqual(self.cli("restore", str(self.project), "--backup", "../outside").returncode, 1)

    def test_failed_apply_preserves_other_files_and_keeps_recoverable_backup(self):
        plan = self.plan()
        other = self.project / "other.txt"
        other.write_bytes(b"untouched")
        def fail_before_replace(source, target):
            backup = self.backups / plan["backup"]["directory"]
            self.assertEqual((backup / "original").read_bytes(), self.original)
            self.assertTrue((backup / "manifest.json").is_file())
            self.assertEqual(target.read_bytes(), self.original)
            raise OSError("injected")

        with mock.patch.object(transaction, "_replace", side_effect=fail_before_replace):
            with self.assertRaises(transaction.TransactionError) as raised:
                transaction.apply(str(self.project), str(self.plan_file), plan["plan_id"], installed_version())
        backup_id = self.backup_id(str(raised.exception))
        self.assertEqual(self.config.read_bytes(), self.original)
        self.assertEqual(other.read_bytes(), b"untouched")
        self.assertTrue((self.backups / (transaction.BACKUP_PREFIX + backup_id) / "manifest.json").is_file())
        self.assertIn("keine Änderung", transaction.restore(str(self.project), backup_id))

    def test_failure_after_replace_can_be_restored(self):
        plan = self.plan()
        replace = transaction._replace

        def fail_after_replace(source, target):
            replace(source, target)
            raise OSError("injected after replace")

        with mock.patch.object(transaction, "_replace", side_effect=fail_after_replace):
            with self.assertRaises(transaction.TransactionError) as raised:
                transaction.apply(str(self.project), str(self.plan_file), plan["plan_id"], installed_version())
        backup_id = self.backup_id(str(raised.exception))
        transaction.restore(str(self.project), backup_id)
        self.assertEqual(self.config.read_bytes(), self.original)

    def test_partial_write_is_recoverable_if_unchanged(self):
        plan = self.plan()
        other = self.project / "other.txt"
        other.write_bytes(b"untouched")

        def partial_write(source, target):
            target.write_bytes(source.read_bytes()[:32])
            raise OSError("injected partial write")

        with mock.patch.object(transaction, "_replace", side_effect=partial_write):
            with self.assertRaises(transaction.TransactionError) as raised:
                transaction.apply(str(self.project), str(self.plan_file), plan["plan_id"], installed_version())
        backup_id = self.backup_id(str(raised.exception))
        self.assertNotEqual(self.config.read_bytes(), self.original)
        self.assertTrue((self.backups / (transaction.BACKUP_PREFIX + backup_id) / "recovery.json").is_file())
        transaction.restore(str(self.project), backup_id)
        self.assertEqual(self.config.read_bytes(), self.original)
        self.assertEqual(other.read_bytes(), b"untouched")
        self.assertEqual((self.backups / (transaction.BACKUP_PREFIX + backup_id) / "original").read_bytes(),
                         self.original)

    def test_foreign_edit_after_partial_write_prevents_restore(self):
        plan = self.plan()

        def partial_write(source, target):
            target.write_bytes(source.read_bytes()[:32])
            raise OSError("injected partial write")

        with mock.patch.object(transaction, "_replace", side_effect=partial_write):
            with self.assertRaises(transaction.TransactionError) as raised:
                transaction.apply(str(self.project), str(self.plan_file), plan["plan_id"], installed_version())
        backup_id = self.backup_id(str(raised.exception))
        changed = self.config.read_bytes() + b"foreign work"
        self.config.write_bytes(changed)
        with self.assertRaisesRegex(transaction.TransactionError, "Fremde Zwischenänderung"):
            transaction.restore(str(self.project), backup_id)
        self.assertEqual(self.config.read_bytes(), changed)

    def test_low_level_write_failure_can_be_restored(self):
        plan = self.plan()
        original_open = Path.open

        class FailedWrite:
            def __init__(self, file):
                self.file = file

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.file.close()

            def write(self, content):
                self.file.write(content[:-10])
                self.file.flush()
                raise OSError("injected write failure")

        def faulty_open(path, *args, **kwargs):
            file = original_open(path, *args, **kwargs)
            if args and args[0] == "r+b" and path.samefile(self.config):
                return FailedWrite(file)
            return file

        with mock.patch.object(Path, "open", new=faulty_open), \
                mock.patch.object(transaction, "_replace", side_effect=transaction._write_in_place):
            with self.assertRaises(transaction.TransactionError) as raised:
                transaction.apply(str(self.project), str(self.plan_file), plan["plan_id"], installed_version())
        self.assertIn("Teilzustand erfasst", str(raised.exception))
        backup_id = self.backup_id(str(raised.exception))
        transaction.restore(str(self.project), backup_id)
        self.assertEqual(self.config.read_bytes(), self.original)

    def test_process_interruption_requires_manual_recovery(self):
        plan = self.plan()

        def interrupted(source, target):
            target.write_bytes(source.read_bytes()[:32])
            raise KeyboardInterrupt

        with mock.patch.object(transaction, "_replace", side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                transaction.apply(str(self.project), str(self.plan_file), plan["plan_id"], installed_version())
        backup_id = plan["backup"]["id"]
        partial = self.config.read_bytes()
        with self.assertRaisesRegex(transaction.TransactionError, "manuelle Wiederherstellung"):
            transaction.restore(str(self.project), backup_id)
        self.assertEqual(self.config.read_bytes(), partial)
        self.assertEqual((self.backups / (transaction.BACKUP_PREFIX + backup_id) / "original").read_bytes(),
                         self.original)

    def test_abrupt_process_exit_preserves_snapshot_and_requires_manual_recovery(self):
        plan = self.plan()
        script = (
            "import os, sys\n"
            "from project_generator import installed_version, transaction\n"
            "def crash(source, target):\n"
            "    target.write_bytes(source.read_bytes()[:32])\n"
            "    os._exit(73)\n"
            "transaction._replace = crash\n"
            "transaction.apply(sys.argv[1], sys.argv[2], sys.argv[3], installed_version())\n"
        )
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run(
            [sys.executable, "-B", "-c", script, str(self.project), str(self.plan_file), plan["plan_id"]],
            cwd=self.project, env=env, capture_output=True,
        )
        self.assertEqual(result.returncode, 73)
        backup = self.backups / plan["backup"]["directory"]
        self.assertEqual((backup / "original").read_bytes(), self.original)
        self.assertTrue((backup / "stage").is_file())
        self.assertFalse((backup / "recovery.json").exists())
        partial = self.config.read_bytes()
        restored = self.cli("restore", str(self.project), "--backup", plan["backup"]["id"])
        self.assertEqual(restored.returncode, 1, restored.stderr)
        self.assertIn("manuelle Wiederherstellung", restored.stderr)
        self.assertEqual(self.config.read_bytes(), partial)
        self.assertTrue((backup / "stage").is_file())

    def test_failure_to_record_partial_state_requires_manual_recovery(self):
        plan = self.plan()
        write_new = transaction._write_new

        def partial_write(source, target):
            target.write_bytes(source.read_bytes()[:32])
            raise OSError("injected partial write")

        def fail_record(path, content):
            if path.name == "recovery.tmp":
                raise OSError("injected journal failure")
            return write_new(path, content)

        with mock.patch.object(transaction, "_replace", side_effect=partial_write), \
                mock.patch.object(transaction, "_write_new", side_effect=fail_record):
            with self.assertRaises(transaction.TransactionError) as raised:
                transaction.apply(str(self.project), str(self.plan_file), plan["plan_id"], installed_version())
        self.assertIn("Teilzustand konnte nicht sicher erfasst", str(raised.exception))
        backup_id = self.backup_id(str(raised.exception))
        partial = self.config.read_bytes()
        with self.assertRaisesRegex(transaction.TransactionError, "manuelle Wiederherstellung"):
            transaction.restore(str(self.project), backup_id)
        self.assertEqual(self.config.read_bytes(), partial)
        self.assertEqual((self.backups / (transaction.BACKUP_PREFIX + backup_id) / "original").read_bytes(),
                         self.original)

    def test_partial_apply_and_restore_failures_can_be_retried(self):
        plan = self.plan()

        def partial_apply(source, target):
            target.write_bytes(source.read_bytes()[:32])
            raise OSError("injected partial apply")

        with mock.patch.object(transaction, "_replace", side_effect=partial_apply):
            with self.assertRaises(transaction.TransactionError) as raised:
                transaction.apply(str(self.project), str(self.plan_file), plan["plan_id"], installed_version())
        backup_id = self.backup_id(str(raised.exception))

        def partial_restore(source, target):
            target.write_bytes(source.read_bytes()[:41])
            raise OSError("injected partial restore")

        with mock.patch.object(transaction, "_replace", side_effect=partial_restore):
            with self.assertRaisesRegex(transaction.TransactionError, "Teilzustand erfasst"):
                transaction.restore(str(self.project), backup_id)
        transaction.restore(str(self.project), backup_id)
        self.assertEqual(self.config.read_bytes(), self.original)

    @unittest.skipIf(os.name == "nt", "POSIX cross-device rename")
    def test_cross_device_fallback_and_hardlink_protection(self):
        plan = self.plan()
        with mock.patch.object(transaction.os, "replace", side_effect=OSError(errno.EXDEV, "cross-device")):
            backup_id = transaction.apply(str(self.project), str(self.plan_file), plan["plan_id"],
                                          installed_version())
            transaction.restore(str(self.project), backup_id)
        self.assertEqual(self.config.read_bytes(), self.original)
        outside = self.base / "hardlink.yaml"
        os.link(self.config, outside)
        plan = self.plan()
        with mock.patch.object(transaction.os, "replace", side_effect=OSError(errno.EXDEV, "cross-device")):
            with self.assertRaisesRegex(transaction.TransactionError, "Hardlinks"):
                transaction.apply(str(self.project), str(self.plan_file), plan["plan_id"], installed_version())
        self.assertEqual(outside.read_bytes(), self.original)
        self.assertEqual(self.config.read_bytes(), self.original)

    @unittest.skipUnless(os.name == "nt", "Windows alternate streams")
    def test_windows_alternate_streams_are_rejected(self):
        try:
            with open(str(self.config) + ":extra", "wb") as stream:
                stream.write(b"untouched stream")
        except OSError:
            self.skipTest("filesystem does not support alternate streams")
        result = self.cli("plan", str(self.project), "--json")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("Dateistreams", result.stderr)
        self.assertEqual(self.config.read_bytes(), self.original)
        with open(str(self.config) + ":extra", "rb") as stream:
            self.assertEqual(stream.read(), b"untouched stream")

    @unittest.skipUnless(os.name == "nt", "Windows hard links")
    def test_windows_hard_links_outside_project_are_rejected(self):
        outside = self.base / "outside.yaml"
        try:
            os.link(self.config, outside)
        except OSError:
            self.skipTest("filesystem does not support hard links")
        result = self.cli("plan", str(self.project), "--json")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("Hardlinks", result.stderr)
        self.assertEqual(outside.read_bytes(), self.original)

    def test_symlinked_config_or_backup_is_refused(self):
        plan = self.plan()
        outside = self.base / "outside.yaml"
        outside.write_bytes(self.original)
        self.config.unlink()
        try:
            self.config.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks not available on this platform")
        result = self.apply(plan)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(outside.read_bytes(), self.original)
        self.config.unlink()
        self.config.write_bytes(self.original)
        applied = self.apply(plan)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        backup_id = self.backup_id(applied.stdout)
        original_backup = self.backups / (transaction.BACKUP_PREFIX + backup_id) / "original"
        original_backup.unlink()
        original_backup.symlink_to(outside)
        current = self.config.read_bytes()
        restored = self.cli("restore", str(self.project), "--backup", backup_id)
        self.assertEqual(restored.returncode, 1, restored.stderr)
        self.assertEqual(self.config.read_bytes(), current)


if __name__ == "__main__":
    unittest.main()
