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
        self.contents = {
            "scripts/check.py": b"candidate check\n",
            "scripts/projectcfg.py": b"candidate config parser\n",
            "scripts/diagrams.py": b"candidate diagram checker\n",
            ".github/workflows/ci.yml": b"candidate workflow\n",
        }
        for name, content in self.contents.items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        subprocess.run(["git", "-C", str(self.source), "add", "."], check=True)
        subprocess.run([
            "git", "-C", str(self.source), "-c", "user.name=Candidate fixture",
            "-c", "user.email=candidate@example.invalid", "commit", "-qm", "candidate",
        ], check=True)
        self.commit = subprocess.run(
            ["git", "-C", str(self.source), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        self.hashes = {name: hashlib.sha256(value).hexdigest()
                       for name, value in self.contents.items()}
        self.patches = [
            mock.patch.object(prepare_candidate_ci, "SOURCE", str(self.source)),
            mock.patch.object(prepare_candidate_ci, "CANDIDATE_COMMIT", self.commit),
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
                   GIT_CONFIG_VALUE_0="store")
        with mock.patch.object(prepare_candidate_ci.subprocess, "run", side_effect=capture_run):
            result = prepare_candidate_ci.prepare(mirror, env)

        self.assertEqual(result, mirror.resolve())
        self.assertTrue(captured_environments)
        for child_env in captured_environments:
            self.assertNotIn("GH_TOKEN", child_env)
            self.assertNotIn("GITHUB_TOKEN", child_env)
            self.assertNotIn("T0004_REPO_TOKEN", child_env)
            self.assertNotIn("GIT_CONFIG_COUNT", child_env)
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

    def test_relative_mirror_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "absolute"):
            prepare_candidate_ci.prepare(Path("relative-candidate.git"), dict(os.environ))


if __name__ == "__main__":
    unittest.main()
