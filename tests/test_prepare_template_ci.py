"""Tests for preparing a local, credential-free template mirror for CI."""

import contextlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from scripts import prepare_template_ci


class PrepareTemplateCi(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.output = self.base / "github-output"
        self.source = self.base / "source"
        self.source.mkdir()
        inherited = dict(os.environ, HOME=str(self.base / "home"),
                         USERPROFILE=str(self.base / "home"))
        self.env = prepare_template_ci.gh_access.git_environment(inherited)
        self.env["GH_TOKEN"] = "synthetic-fixture-credential"

    def git(self, *args: str, cwd: Path):
        return subprocess.run(
            ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
        ).stdout.strip()

    def test_missing_credential_marks_template_not_verified(self):
        log = io.StringIO()
        with (
            mock.patch.dict(os.environ, {"GITHUB_OUTPUT": str(self.output)}, clear=True),
            contextlib.redirect_stdout(log),
        ):
            self.assertFalse(prepare_template_ci.prepare(self.base / "mirror.git", {}))
        output = self.output.read_text(encoding="utf-8")
        self.assertIn("template_ready=false", output)
        self.assertIn("private_auth=not_verified", output)
        self.assertIn("Private template retrieval: FAILED", log.getvalue())
        self.assertFalse((self.base / "mirror.git").exists())

    def test_missing_credential_fails_trusted_command(self):
        with mock.patch.dict(os.environ, {"GITHUB_OUTPUT": str(self.output)}, clear=True):
            self.assertEqual(prepare_template_ci.main(["--mirror", str(self.base / "mirror.git")]), 1)

    def test_untrusted_mode_never_uses_an_inherited_credential(self):
        log = io.StringIO()
        with (
            mock.patch.dict(os.environ, {
                "GITHUB_OUTPUT": str(self.output),
                "GH_TOKEN": "synthetic-fixture-credential",
            }, clear=True),
            contextlib.redirect_stdout(log),
        ):
            self.assertEqual(prepare_template_ci.main(["--untrusted"]), 0)
        output = self.output.read_text(encoding="utf-8")
        self.assertIn("template_ready=false", output)
        self.assertIn("private_auth=not_verified", output)
        self.assertIn("untrusted event", log.getvalue())
        self.assertNotIn("synthetic-fixture-credential", log.getvalue())
        self.assertFalse((self.base / "mirror.git").exists())

    def test_fetch_failure_is_non_success_and_not_private_auth_success(self):
        failure = prepare_template_ci.gh_access.AccessResult(
            False, "forbidden", "Zugriff fehlgeschlagen: Berechtigung fehlt."
        )
        with (
            mock.patch.object(prepare_template_ci, "SOURCE", "https://example.invalid/repo.git"),
            mock.patch.object(
                prepare_template_ci.gh_access, "fetch_reference", return_value=failure
            ),
            mock.patch.dict(os.environ, {
                "GH_TOKEN": self.env["GH_TOKEN"],
                "GITHUB_OUTPUT": str(self.output),
            }, clear=True),
        ):
            self.assertEqual(
                prepare_template_ci.main(["--mirror", str(self.base / "mirror.git")]), 1
            )
        output = self.output.read_text(encoding="utf-8")
        self.assertIn("template_ready=false", output)
        self.assertIn("private_auth=not_verified", output)
        self.assertNotIn("private_auth=passed", output)

    def test_rejected_credential_fails_and_never_reports_private_authentication(self):
        failure = prepare_template_ci.gh_access.AccessResult(
            False, "forbidden", "Zugriff fehlgeschlagen: Berechtigung fehlt."
        )
        log = io.StringIO()
        with (
            mock.patch.object(prepare_template_ci.gh_access, "fetch_reference", return_value=failure),
            mock.patch.dict(os.environ, {
                "GH_TOKEN": self.env["GH_TOKEN"], "GITHUB_OUTPUT": str(self.output),
            }, clear=True),
            contextlib.redirect_stdout(log),
        ):
            self.assertEqual(prepare_template_ci.main(["--mirror", str(self.base / "mirror.git")]), 1)
        output = self.output.read_text(encoding="utf-8")
        self.assertIn("template_ready=false", output)
        self.assertIn("private_auth=not_verified", output)
        self.assertNotIn("private_auth=passed", output)
        self.assertIn("FAILED (forbidden)", log.getvalue())
        self.assertNotIn(self.env["GH_TOKEN"], log.getvalue())

    def test_default_branch_resolution_failure_is_not_private_auth_success(self):
        success = prepare_template_ci.gh_access.AccessResult(
            True, "ok", "Referenz wurde abgerufen."
        )
        failure = prepare_template_ci.gh_access.AccessResult(
            False, "forbidden", "Zugriff fehlgeschlagen: Berechtigung fehlt."
        )
        log = io.StringIO()
        with (
            mock.patch.object(
                prepare_template_ci.gh_access, "fetch_reference", return_value=success
            ),
            mock.patch.object(
                prepare_template_ci.gh_access, "resolve_default_branch", return_value=failure
            ),
            mock.patch.dict(os.environ, {
                "GH_TOKEN": self.env["GH_TOKEN"], "GITHUB_OUTPUT": str(self.output),
            }, clear=True),
            contextlib.redirect_stdout(log),
        ):
            self.assertEqual(prepare_template_ci.main(["--mirror", str(self.base / "mirror.git")]), 1)
        output = self.output.read_text(encoding="utf-8")
        self.assertIn("template_ready=false", output)
        self.assertIn("private_auth=not_verified", output)
        self.assertNotIn("private_auth=passed", output)
        self.assertIn("FAILED (forbidden)", log.getvalue())
        self.assertNotIn(self.env["GH_TOKEN"], output + log.getvalue())

    def test_default_branch_fetch_failure_is_not_private_auth_success(self):
        success = prepare_template_ci.gh_access.AccessResult(
            True, "ok", "Referenz wurde abgerufen."
        )
        failure = prepare_template_ci.gh_access.AccessResult(
            False, "forbidden", "Zugriff fehlgeschlagen: Berechtigung fehlt."
        )
        default_reference = "a" * 40
        log = io.StringIO()
        with (
            mock.patch.object(
                prepare_template_ci.gh_access,
                "fetch_reference",
                side_effect=(success, success, failure),
            ) as fetch,
            mock.patch.object(
                prepare_template_ci.gh_access,
                "resolve_default_branch",
                return_value=prepare_template_ci.gh_access.AccessResult(
                    True, "ok", "Default-Branch wurde aufgelöst.", default_reference
                ),
            ),
            mock.patch.dict(os.environ, {
                "GH_TOKEN": self.env["GH_TOKEN"], "GITHUB_OUTPUT": str(self.output),
            }, clear=True),
            contextlib.redirect_stdout(log),
        ):
            self.assertEqual(prepare_template_ci.main(["--mirror", str(self.base / "mirror.git")]), 1)
        output = self.output.read_text(encoding="utf-8")
        self.assertEqual(fetch.call_args_list[-1].args[2], default_reference)
        self.assertIn("template_ready=false", output)
        self.assertIn("private_auth=not_verified", output)
        self.assertNotIn("private_auth=passed", output)
        self.assertIn("FAILED (forbidden)", log.getvalue())
        self.assertNotIn(self.env["GH_TOKEN"], output + log.getvalue())

    def test_private_source_and_original_pins_are_fixed(self):
        self.assertEqual(
            prepare_template_ci.gh_access.T0003_SOURCE,
            "https://github.com/maieuticus/t0003-private-access-test.git",
        )
        self.assertEqual(
            prepare_template_ci.gh_access.COMPATIBLE_REFERENCE,
            "6e8363a7ac7d99220d743eea077dcd5cefda9042",
        )
        self.assertEqual(
            prepare_template_ci.gh_access.RELEASE_REFERENCE,
            "964de8538d19cefcb483faff38f10124615a9783",
        )

    def test_simulated_private_fetch_reports_authentication_passed(self):
        self.git("init", "--quiet", cwd=self.source)
        self.git("config", "user.name", "Fixture", cwd=self.source)
        self.git("config", "user.email", "fixture@example.invalid", cwd=self.source)
        (self.source / "fixture.txt").write_text("compatible\n", encoding="utf-8")
        self.git("add", ".", cwd=self.source)
        self.git("commit", "--quiet", "-m", "compatible", cwd=self.source)
        compatible = self.git("rev-parse", "HEAD", cwd=self.source)
        (self.source / "fixture.txt").write_text("release\n", encoding="utf-8")
        self.git("commit", "--quiet", "-am", "release", cwd=self.source)
        release = self.git("rev-parse", "HEAD", cwd=self.source)
        output = io.StringIO()
        real_fetch = prepare_template_ci.gh_access.fetch_reference
        private_source = prepare_template_ci.gh_access.T0003_SOURCE

        def fetch_private_simulation(source, destination, reference, **kwargs):
            self.assertEqual(source, private_source)
            return real_fetch(self.source.as_posix(), destination, reference, **kwargs)

        def resolve_private_simulation(source, **kwargs):
            self.assertEqual(source, private_source)
            return prepare_template_ci.gh_access.AccessResult(
                True, "ok", "Default-Branch wurde aufgelöst.", release
            )

        with (
            mock.patch.object(prepare_template_ci, "SOURCE", prepare_template_ci.gh_access.T0003_SOURCE),
            mock.patch.object(prepare_template_ci.gh_access, "COMPATIBLE_REFERENCE", compatible),
            mock.patch.object(prepare_template_ci.gh_access, "RELEASE_REFERENCE", release),
            mock.patch.object(prepare_template_ci.gh_access, "fetch_reference", side_effect=fetch_private_simulation),
            mock.patch.object(prepare_template_ci.gh_access, "resolve_default_branch", side_effect=resolve_private_simulation),
            mock.patch.dict(os.environ, {"GITHUB_OUTPUT": str(self.output)}, clear=True),
            contextlib.redirect_stdout(output),
        ):
            self.assertTrue(prepare_template_ci.prepare(self.base / "private-mirror.git", self.env))
        result = self.output.read_text(encoding="utf-8")
        self.assertIn("template_ready=true", result)
        self.assertIn("private_auth=passed", result)
        self.assertIn("Private template retrieval: PASS", output.getvalue())
        self.assertNotIn(self.env["GH_TOKEN"], result + output.getvalue())

    def test_fetches_pins_and_default_branch_without_persisting_credential(self):
        self.git("init", "--quiet", cwd=self.source)
        self.git("config", "user.name", "Fixture", cwd=self.source)
        self.git("config", "user.email", "fixture@example.invalid", cwd=self.source)
        (self.source / "fixture.txt").write_text("compatible\n", encoding="utf-8")
        self.git("add", ".", cwd=self.source)
        self.git("commit", "--quiet", "-m", "compatible", cwd=self.source)
        compatible = self.git("rev-parse", "HEAD", cwd=self.source)
        (self.source / "fixture.txt").write_text("release\n", encoding="utf-8")
        self.git("commit", "--quiet", "-am", "release", cwd=self.source)
        release = self.git("rev-parse", "HEAD", cwd=self.source)
        git = shutil.which("git", path=self.env["PATH"])
        self.assertIsNotNone(git)
        expected_git = os.path.abspath(git)
        log = io.StringIO()
        completed = []
        real_run = subprocess.run

        def capture_run(*args, **kwargs):
            result = real_run(*args, **kwargs)
            completed.append(result)
            return result

        with (
            mock.patch.object(prepare_template_ci, "SOURCE", str(self.source)),
            mock.patch.object(prepare_template_ci.gh_access, "COMPATIBLE_REFERENCE", compatible),
            mock.patch.object(prepare_template_ci.gh_access, "RELEASE_REFERENCE", release),
            mock.patch.dict(os.environ, {
                "GITHUB_OUTPUT": str(self.output),
                "GITHUB_STEP_SUMMARY": str(self.base / "step-summary"),
            }, clear=True),
            mock.patch.object(subprocess, "run", side_effect=capture_run) as run,
            contextlib.redirect_stdout(log),
        ):
            self.assertTrue(prepare_template_ci.prepare(self.base / "mirror.git", self.env))

        calls = run.call_args_list
        self.assertTrue(all(
            os.path.normcase(call.args[0][0]) == os.path.normcase(expected_git) for call in calls
        ))
        self.assertTrue(any(call.args[0][1:3] == ["init", "--bare"] for call in calls))
        self.assertTrue(any("fetch" in call.args[0] for call in calls))
        self.assertTrue(any("ls-remote" in call.args[0] for call in calls))
        self.assertTrue(any("update-ref" in call.args[0] for call in calls))
        self.assertTrue(any("symbolic-ref" in call.args[0] for call in calls))
        for call in calls:
            args = call.args[0]
            child_env = call.kwargs["env"]
            self.assertNotIn(self.env["GH_TOKEN"], " ".join(args))
            self.assertEqual(child_env["GIT_CONFIG_GLOBAL"], os.devnull)
            self.assertEqual(child_env["GIT_CONFIG_NOSYSTEM"], "1")
            self.assertEqual(child_env["GIT_TERMINAL_PROMPT"], "0")
            if "fetch" in args or "ls-remote" in args:
                self.assertEqual(child_env["GH_TOKEN"], self.env["GH_TOKEN"])
            else:
                self.assertNotIn("GH_TOKEN", child_env)
        for result in completed:
            self.assertNotIn(self.env["GH_TOKEN"], result.stdout)
            self.assertNotIn(self.env["GH_TOKEN"], result.stderr)

        output = self.output.read_text(encoding="utf-8")
        summary = (self.base / "step-summary").read_text(encoding="utf-8")
        self.assertIn("template_ready=true", output)
        self.assertIn("private_auth=not_verified", output)
        self.assertIn("Local fixture retrieval: PASS", summary)
        self.assertIn("private authentication: NOT VERIFIED", summary)
        self.assertEqual(self.git("--git-dir", str(self.base / "mirror.git"), "rev-parse", "HEAD",
                                  cwd=self.base), release)
        config = (self.base / "mirror.git" / "config").read_text(encoding="utf-8")
        self.assertNotIn(self.env["GH_TOKEN"], config)
        self.assertNotIn(self.env["GH_TOKEN"], output)
        self.assertNotIn(self.env["GH_TOKEN"], summary)
        self.assertNotIn(self.env["GH_TOKEN"], log.getvalue())


if __name__ == "__main__":
    unittest.main()
