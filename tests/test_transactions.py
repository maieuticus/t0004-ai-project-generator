"""Safe apply and restore tests confined to temporary projects."""

import hashlib
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
from project_generator import transaction
from project_generator.plan import _windows_security_component

SOURCE_CONFIG = (ROOT / "config/project.yaml").read_text(encoding="utf-8")


class Transactions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
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
        self.assertFalse(list(self.project.glob(".t0004-backup-*")))

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
        self.assertFalse(list(self.project.glob(".t0004-backup-*")))
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
        self.assertFalse((self.project / plan["backup"]["directory"]).exists())
        result = self.apply(plan)
        self.assertEqual(result.returncode, 0, result.stderr)
        backup_id = self.backup_id(result.stdout)
        self.assertEqual(backup_id, plan["backup"]["id"])
        backup = self.project / (transaction.BACKUP_PREFIX + backup_id)
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
        collision = self.project / plan["backup"]["directory"]
        collision.mkdir()
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
        stage = self.project / plan["backup"]["temporary"]
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
        backup = self.project / (transaction.BACKUP_PREFIX + backup_id)
        os.chmod(backup, 0o755)
        current = self.config.read_bytes()
        restored = self.cli("restore", str(self.project), "--backup", backup_id)
        self.assertEqual(restored.returncode, 1, restored.stderr)
        self.assertIn("nicht ausreichend geschützt", restored.stderr)
        self.assertEqual(self.config.read_bytes(), current)

    @unittest.skipUnless(os.name == "nt", "Windows DACL semantics")
    def test_windows_replace_preserves_access_metadata(self):
        before = {
            "mode": stat.S_IMODE(self.config.stat().st_mode),
            "owner": _windows_security_component(self.config, 1),
            "group": _windows_security_component(self.config, 2),
            "dacl": _windows_security_component(self.config, 4),
        }
        backup = self.project / ".private-fixture"
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
        backup = self.project / (transaction.BACKUP_PREFIX + backup_id)
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

    def test_tampered_backup_and_path_traversal_are_refused(self):
        plan = self.plan()
        applied = self.apply(plan)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        backup_id = self.backup_id(applied.stdout)
        backup = self.project / (transaction.BACKUP_PREFIX + backup_id)
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
            backup = self.project / plan["backup"]["directory"]
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
        self.assertTrue((self.project / (transaction.BACKUP_PREFIX + backup_id) / "manifest.json").is_file())
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
        original_backup = self.project / (transaction.BACKUP_PREFIX + backup_id) / "original"
        original_backup.unlink()
        original_backup.symlink_to(outside)
        current = self.config.read_bytes()
        restored = self.cli("restore", str(self.project), "--backup", backup_id)
        self.assertEqual(restored.returncode, 1, restored.stderr)
        self.assertEqual(self.config.read_bytes(), current)


if __name__ == "__main__":
    unittest.main()
