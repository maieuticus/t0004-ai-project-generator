"""Tests for pinned template references used by the integration suite."""

from pathlib import Path
import tempfile
import unittest
from unittest import mock

from integration import test_t0003_integration


class IntegrationAccess(unittest.TestCase):
    def test_missing_access_is_skipped_as_not_verified(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        destination = Path(temporary.name) / "must-not-be-created.git"
        failure = test_t0003_integration.gh_access.AccessResult(
            False, "missing", "Zugriff fehlgeschlagen: Zugangsdaten fehlen."
        )
        with mock.patch.object(
            test_t0003_integration.gh_access, "fetch_reference", return_value=failure
        ) as fetch:
            with self.assertRaisesRegex(unittest.SkipTest, "not verified"):
                test_t0003_integration.fetch_pinned_reference(
                    "https://example.invalid/template.git",
                    destination,
                    test_t0003_integration.COMPATIBLE,
                    {},
                )
        fetch.assert_called_once_with(
            "https://example.invalid/template.git",
            destination,
            test_t0003_integration.COMPATIBLE,
            env={},
        )
        self.assertFalse(destination.exists())
