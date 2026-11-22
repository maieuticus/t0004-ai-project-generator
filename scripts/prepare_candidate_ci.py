"""Fetch and verify the pinned public t0003 candidate without credentials."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://github.com/maieuticus/t0003-ai-project-template.git"
CANDIDATE_COMMIT = "8ee48ed15eea629e51c8e4a64102c6a06cf8726a"
CANDIDATE_FILES = {
    "scripts/check.py": "4a9dd7519b7973442d570743685eaa5184242d80b7554f6d26645ae599b1721b",
    "scripts/projectcfg.py": "f446580597e0c3e7c46ab20cd31e8bbc609316a5a8ae65696da8814244832d20",
    "scripts/diagrams.py": "79b7482172ba7460b057a94ed9dcf31d13109ed098f267a7e28546f13fd06ee7",
    ".github/workflows/ci.yml": "f54914e7f43f14acde14b33693abdbc303784c90c84c87e6bdd7f385e22731cd",
}


class CandidatePreparationError(ValueError):
    """The candidate mirror could not be safely prepared or verified."""


def _git_environment(source: dict[str, str]) -> dict[str, str]:
    env = dict(source)
    removed = {
        "GH_TOKEN", "GITHUB_TOKEN", "T0004_REPO_TOKEN", "GIT_CONFIG_COUNT",
        "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
        "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_ASKPASS", "SSH_ASKPASS",
    }
    for key in removed:
        env.pop(key, None)
    for key in tuple(env):
        if key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")):
            env.pop(key, None)
    env.update({
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
    })
    return env


def _git(mirror: Path, args: list[str], env: dict[str, str], *, binary: bool = False):
    command = ["git", "--git-dir", str(mirror), *args]
    return subprocess.run(
        command, cwd=ROOT, env=env, check=True, capture_output=True,
        text=not binary, encoding=None if binary else "utf-8",
    )


def prepare(mirror: Path, env: dict[str, str]) -> Path:
    if not mirror.is_absolute():
        raise ValueError("Candidate mirror path must be absolute")
    mirror = mirror.expanduser()
    if mirror.is_symlink():
        raise CandidatePreparationError("Candidate mirror must not be a symlink")
    mirror = mirror.resolve()
    if mirror.is_relative_to(ROOT):
        raise CandidatePreparationError("Candidate mirror must be outside the repository")

    git_env = _git_environment(env)
    if mirror.exists():
        if not mirror.is_dir():
            raise CandidatePreparationError("Candidate mirror path is not a directory")
        bare = subprocess.run(
            ["git", "--git-dir", str(mirror), "rev-parse", "--is-bare-repository"],
            cwd=ROOT, env=git_env, check=True, capture_output=True, text=True, encoding="utf-8",
        ).stdout.strip()
        if bare != "true":
            raise CandidatePreparationError("Candidate mirror is not a bare Git repository")
    else:
        mirror.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "init", "--bare", "--quiet", str(mirror)],
            cwd=ROOT, env=git_env, check=True, capture_output=True, text=True, encoding="utf-8",
        )

    _git(mirror, [
        "fetch", "--no-tags", "--no-recurse-submodules", SOURCE, CANDIDATE_COMMIT,
    ], git_env)
    actual_commit = _git(
        mirror, ["rev-parse", "--verify", "FETCH_HEAD^{commit}"], git_env
    ).stdout.strip()
    if actual_commit != CANDIDATE_COMMIT:
        raise CandidatePreparationError("Fetched candidate commit does not match the pinned commit")

    for name, expected in CANDIDATE_FILES.items():
        content = _git(
            mirror, ["cat-file", "blob", f"{CANDIDATE_COMMIT}:{name}"], git_env, binary=True
        ).stdout
        actual = hashlib.sha256(content).hexdigest()
        if actual != expected:
            raise CandidatePreparationError(f"Candidate capability hash mismatch: {name}")
    pinned_ref = f"refs/heads/t0004-candidate-{CANDIDATE_COMMIT}"
    _git(mirror, ["update-ref", pinned_ref, CANDIDATE_COMMIT], git_env)
    _git(mirror, ["symbolic-ref", "HEAD", pinned_ref], git_env)
    return mirror


def _set_output(name: str, value: str) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8", newline="\n") as stream:
            stream.write(f"{name}={value}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mirror", type=Path)
    args = parser.parse_args(argv)
    configured = os.environ.get("T0004_T0003_CANDIDATE_MIRROR")
    runner_temp = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir()))
    mirror = args.mirror or (Path(configured) if configured else runner_temp / "t0003-candidate.git")
    try:
        verified = prepare(mirror, dict(os.environ))
    except (CandidatePreparationError, OSError, subprocess.SubprocessError, ValueError) as error:
        print(f"Candidate template retrieval failed: {error}", file=sys.stderr)
        return 1
    _set_output("candidate_mirror", str(verified))
    print(f"Candidate template verified: {CANDIDATE_COMMIT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
