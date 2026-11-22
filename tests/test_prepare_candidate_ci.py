"""Credential-free retrieval of the pinned public candidate template."""

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import prepare_candidate_ci


class PrepareCandidateCi(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        subprocess.run(["git", "init", "-q", str(self.source)], check=True)
        self.historical_contents = {
            "scripts/check.py": b"historical check\n",
            "scripts/projectcfg.py": b"historical config parser\n",
            ".github/workflows/ci.yml": b"historical workflow\n",
        }
        self.release_contents = {
            **self.historical_contents,
            ".github/workflows/ci.yml": b"released workflow\n",
        }
        self.contents = {
            "scripts/check.py": b"candidate check\n",
            "scripts/projectcfg.py": b"candidate config parser\n",
            "scripts/diagrams.py": b"candidate diagram checker\n",
            ".github/workflows/ci.yml": b"candidate workflow\n",
        }
        def commit_files(files, message):
            for name, content in files.items():
                path = self.source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            subprocess.run(["git", "-C", str(self.source), "add", "."], check=True)
            subprocess.run([
                "git", "-C", str(self.source), "-c", "user.name=Candidate fixture",
                "-c", "user.email=candidate@example.invalid", "commit", "-qm", message,
            ], check=True)
            return subprocess.run(
                ["git", "-C", str(self.source), "rev-parse", "HEAD"],
                check=True, capture_output=True, text=True,
            ).stdout.strip()

        self.historical_commit = commit_files(self.historical_contents, "historical")
        self.release_commit = commit_files(
            {".github/workflows/ci.yml": self.release_contents[".github/workflows/ci.yml"]},
            "release",
        )
        self.commit = commit_files(self.contents, "candidate")
        self.historical_hashes = {
            name: hashlib.sha256(content).hexdigest()
            for name, content in self.historical_contents.items()
        }
        self.release_hashes = {
            name: hashlib.sha256(content).hexdigest()
            for name, content in self.release_contents.items()
        }
        self.hashes = {name: hashlib.sha256(value).hexdigest()
                       for name, value in self.contents.items()}
        self.patches = [
            mock.patch.object(prepare_candidate_ci, "SOURCE", str(self.source)),
            mock.patch.object(prepare_candidate_ci, "HISTORICAL_COMMIT", self.historical_commit),
            mock.patch.object(prepare_candidate_ci, "RELEASE_COMMIT", self.release_commit),
            mock.patch.object(prepare_candidate_ci, "CANDIDATE_COMMIT", self.commit),
            mock.patch.object(prepare_candidate_ci, "HISTORICAL_FILES", self.historical_hashes),
            mock.patch.object(prepare_candidate_ci, "RELEASE_FILES", self.release_hashes),
            mock.patch.object(prepare_candidate_ci, "CANDIDATE_FILES", self.hashes),
        ]
        for patch in self.patches:
            patch.start()
            self.addCleanup(patch.stop)

    def test_fetches_exact_commit_and_capability_hashes_without_credentials(self):
        mirror = self.root / "candidate.git"
        captured_environments = []
        real_run = subprocess.run

        def capture_run(*args, **kwargs):
            captured_environments.append(kwargs["env"])
            return real_run(*args, **kwargs)

        env = dict(os.environ, GH_TOKEN="must-not-be-forwarded",
                   GITHUB_TOKEN="must-not-be-forwarded",
                   T0004_REPO_TOKEN="must-not-be-forwarded",
                   GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="credential.helper",
                   GIT_CONFIG_VALUE_0="store", GIT_CONFIG_PARAMETERS="credential.helper=store",
                   GIT_TEMPLATE_DIR=str(self.root / "untrusted-template"))
        with mock.patch.object(prepare_candidate_ci.subprocess, "run", side_effect=capture_run):
            result = prepare_candidate_ci.prepare(mirror, env)

        self.assertEqual(result, mirror.resolve())
        self.assertTrue(captured_environments)
        for child_env in captured_environments:
            self.assertNotIn("GH_TOKEN", child_env)
            self.assertNotIn("GITHUB_TOKEN", child_env)
            self.assertNotIn("T0004_REPO_TOKEN", child_env)
            self.assertNotIn("GIT_CONFIG_COUNT", child_env)
            self.assertNotIn("GIT_CONFIG_PARAMETERS", child_env)
            self.assertNotIn("GIT_TEMPLATE_DIR", child_env)
            self.assertEqual(child_env["GIT_TERMINAL_PROMPT"], "0")
        actual = subprocess.run(
            ["git", "--git-dir", str(mirror), "rev-parse", "FETCH_HEAD^{commit}"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        self.assertEqual(actual, self.commit)
        default = subprocess.run(
            ["git", "--git-dir", str(mirror), "rev-parse", "HEAD^{commit}"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        self.assertEqual(default, self.commit)
        for label, commit in (
            ("historical", self.historical_commit),
            ("release", self.release_commit),
            ("candidate", self.commit),
        ):
            actual = subprocess.run(
                ["git", "--git-dir", str(mirror), "rev-parse",
                 f"refs/heads/t0004-{label}-{commit}^{{commit}}"],
                check=True, capture_output=True, text=True,
            ).stdout.strip()
            self.assertEqual(actual, commit)

    def test_unavailable_commit_fails_without_branch_fallback(self):
        with mock.patch.object(prepare_candidate_ci, "CANDIDATE_COMMIT", "0" * 40):
            with self.assertRaises((subprocess.CalledProcessError, RuntimeError)):
                prepare_candidate_ci.prepare(self.root / "candidate.git", dict(os.environ))

    def test_hash_mismatch_fails_closed(self):
        wrong_hashes = dict(self.hashes, **{"scripts/diagrams.py": "0" * 64})
        with mock.patch.object(prepare_candidate_ci, "CANDIDATE_FILES", wrong_hashes):
            with self.assertRaisesRegex(
                prepare_candidate_ci.CandidatePreparationError, "scripts/diagrams.py"
            ):
                prepare_candidate_ci.prepare(self.root / "candidate.git", dict(os.environ))

    def test_historical_and_release_hash_mismatches_fail_closed(self):
        for label, field, expected, path in (
            ("historical", "HISTORICAL_FILES", self.historical_hashes, "scripts/check.py"),
            ("release", "RELEASE_FILES", self.release_hashes, ".github/workflows/ci.yml"),
        ):
            with self.subTest(reference=label):
                wrong = dict(expected)
                wrong[path] = "0" * 64
                with mock.patch.object(prepare_candidate_ci, field, wrong):
                    with self.assertRaisesRegex(
                        prepare_candidate_ci.CandidatePreparationError, path.replace(".", r"\.")
                    ):
                        prepare_candidate_ci.prepare(
                            self.root / f"{label}-mismatch.git", dict(os.environ)
                        )

    def test_relative_mirror_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "absolute"):
            prepare_candidate_ci.prepare(Path("relative-candidate.git"), dict(os.environ))

    def test_existing_mirror_is_rejected_before_git_is_invoked(self):
        mirror = self.root / "existing.git"
        subprocess.run(["git", "init", "--bare", "-q", str(mirror)], check=True)
        with mock.patch.object(
            prepare_candidate_ci.subprocess, "run",
            side_effect=AssertionError("existing mirror must not be used"),
        ):
            with self.assertRaisesRegex(
                prepare_candidate_ci.CandidatePreparationError, "fresh path"
            ):
                prepare_candidate_ci.prepare(mirror, dict(os.environ))


if __name__ == "__main__":
    unittest.main()
