"""Tests for local and aggregated release verification reports."""

import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import verify


def _criterion(criterion_id, platform, evidence_source="local", status="passed"):
    return {
        "criterion_id": criterion_id,
        "status": status,
        "platform": platform,
        "evidence": f"test:{criterion_id}",
        "evidence_source": evidence_source,
    }


def _report(platform, *, evidence_source="local", failed=(), omitted=()):
    criteria = [
        _criterion(
            name, platform, evidence_source,
            "failed" if name in failed else "passed",
        )
        for name in (
            "repository-checks", "template-tests", "generator-tests",
            "historical-integrations", "candidate-integrations",
        )
        if name not in omitted
    ]
    for workflow in ("new", "migrate"):
        criterion_id = f"{workflow}-{platform.lower()}"
        if criterion_id not in omitted:
            criteria.append(_criterion(
                criterion_id,
                platform,
                evidence_source,
                "failed" if criterion_id in failed else "passed",
            ))
    return {
        "platform": platform,
        "evidence_source": evidence_source,
        "status": "failed" if failed else "passed",
        "criteria": criteria,
        "summary": f"{platform} verification",
    }


class VerifyTests(unittest.TestCase):
    def run_main(self, args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = verify.main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def write_report(self, directory, name, report):
        path = Path(directory) / name
        path.write_text(json.dumps(report), encoding="utf-8")
        return path

    def test_aggregate_passes_only_complete_linux_and_windows_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            linux = self.write_report(
                directory, "linux.json", _report("Linux", evidence_source="local"),
            )
            windows = self.write_report(
                directory, "windows.json", _report("Windows", evidence_source="hosted"),
            )

            code, output, _ = self.run_main([
                "--aggregate", str(linux), str(windows), "--json",
            ])

        result = json.loads(output)
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(
            {item["criterion_id"] for item in result["criteria"] if item["criterion_id"] in {
                "new-linux", "new-windows", "migrate-linux", "migrate-windows",
            }},
            {"new-linux", "new-windows", "migrate-linux", "migrate-windows"},
        )
        self.assertEqual(
            {item["platform"] for item in result["criteria"]},
            {"Linux", "Windows"},
        )
        self.assertEqual(
            {item["evidence_source"] for item in result["criteria"] if item["platform"] == "Linux"},
            {"local"},
        )
        self.assertEqual(
            {item["evidence_source"] for item in result["criteria"] if item["platform"] == "Windows"},
            {"hosted"},
        )

    def test_aggregate_rejects_missing_platform_criteria(self):
        with tempfile.TemporaryDirectory() as directory:
            linux = self.write_report(directory, "linux.json", _report("Linux"))
            windows = self.write_report(
                directory, "windows.json", _report("Windows", omitted=("migrate-windows",)),
            )

            code, output, _ = self.run_main([
                "--aggregate", str(linux), str(windows), "--json",
            ])

        result = json.loads(output)
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "not_verified")
        self.assertIn("migrate-windows", result["blockers"])

    def test_aggregate_rejects_duplicate_platform_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            first = self.write_report(directory, "first.json", _report("Linux"))
            second = self.write_report(directory, "second.json", _report("Linux"))

            code, output, _ = self.run_main([
                "--aggregate", str(first), str(second), "--json",
            ])

        result = json.loads(output)
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "not_verified")
        self.assertTrue(any("duplicate" in item for item in result["blockers"]))

    def test_aggregate_rejects_mismatched_evidence_source(self):
        with tempfile.TemporaryDirectory() as directory:
            linux_report = _report("Linux")
            linux_report["criteria"][0]["evidence_source"] = "hosted"
            linux = self.write_report(directory, "linux.json", linux_report)
            windows = self.write_report(
                directory, "windows.json", _report("Windows", evidence_source="hosted"),
            )

            code, output, _ = self.run_main([
                "--aggregate", str(linux), str(windows), "--json",
            ])

        result = json.loads(output)
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "not_verified")
        self.assertTrue(any("mismatched evidence source" in item for item in result["blockers"]))

    def test_aggregate_failed_criterion_is_not_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            linux = self.write_report(
                directory, "linux.json", _report("Linux", failed=("new-linux",)),
            )
            windows = self.write_report(directory, "windows.json", _report("Windows"))

            code, output, _ = self.run_main([
                "--aggregate", str(linux), str(windows), "--json",
            ])

        result = json.loads(output)
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "not_ready")
        self.assertIn("new-linux", result["blockers"])

    def test_local_report_is_platform_scoped_and_preserves_release_metadata(self):
        version_before = (ROOT / "VERSION").read_bytes()
        changelog_before = (ROOT / "CHANGELOG.md").read_bytes()
        local_report = _report("Linux")
        with mock.patch.object(verify, "run_local_verification", return_value=local_report):
            code, output, _ = self.run_main(["--json"])

        result = json.loads(output)
        self.assertEqual(code, 0)
        self.assertEqual(result["platform"], "Linux")
        self.assertEqual(result["status"], "passed")
        self.assertEqual((ROOT / "VERSION").read_bytes(), version_before)
        self.assertEqual((ROOT / "CHANGELOG.md").read_bytes(), changelog_before)

    def test_local_human_output_identifies_platform_and_status(self):
        with mock.patch.object(verify, "run_local_verification", return_value=_report("Windows")):
            code, output, _ = self.run_main([])

        self.assertEqual(code, 0)
        self.assertIn("Windows", output)
        self.assertIn("passed", output)

    def test_verification_environment_excludes_private_credentials(self):
        with mock.patch.dict(os.environ, {
            "GH_TOKEN": "private-token",
            "GITHUB_TOKEN": "github-token",
            "T0004_REPO_TOKEN": "repository-token",
        }):
            environment = verify._verification_environment()

        self.assertNotIn("GH_TOKEN", environment)
        self.assertNotIn("GITHUB_TOKEN", environment)
        self.assertNotIn("T0004_REPO_TOKEN", environment)

    def test_evidence_source_distinguishes_local_and_github_actions(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(verify._evidence_source(), "local")
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}, clear=True):
            self.assertEqual(verify._evidence_source(), "hosted")
