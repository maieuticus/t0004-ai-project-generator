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
HISTORICAL_COMMIT = "6e8363a7ac7d99220d743eea077dcd5cefda9042"
RELEASE_COMMIT = "964de8538d19cefcb483faff38f10124615a9783"
CANDIDATE_COMMIT = "8ee48ed15eea629e51c8e4a64102c6a06cf8726a"
HISTORICAL_FILES = {
    "scripts/check.py": "08be5d0fc5bddb6bbd9209c659a77456c785bfaa3ee24ebb06c20d390d6a2d4e",
    "scripts/projectcfg.py": "f446580597e0c3e7c46ab20cd31e8bbc609316a5a8ae65696da8814244832d20",
    ".github/workflows/ci.yml": "f54914e7f43f14acde14b33693abdbc303784c90c84c87e6bdd7f385e22731cd",
}
RELEASE_FILES = {
    **HISTORICAL_FILES,
    ".github/workflows/ci.yml": "18a51ef1b44f6b7bb2347c289b2195a4e3744f910a40f3a0378cf03b2c8c0a21",
}
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
        "GIT_ASKPASS", "SSH_ASKPASS", "GIT_CONFIG_PARAMETERS", "GIT_TEMPLATE_DIR",
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


def _fetch_verified(mirror: Path, commit: str, files: dict[str, str],
                    env: dict[str, str]) -> None:
    _git(mirror, [
        "fetch", "--no-tags", "--no-recurse-submodules", SOURCE, commit,
    ], env)
    actual_commit = _git(
        mirror, ["rev-parse", "--verify", "FETCH_HEAD^{commit}"], env
    ).stdout.strip()
    if actual_commit != commit:
        raise CandidatePreparationError("Fetched template commit does not match the pinned commit")
    for name, expected in files.items():
        content = _git(mirror, ["cat-file", "blob", f"{commit}:{name}"], env, binary=True).stdout
        if hashlib.sha256(content).hexdigest() != expected:
            raise CandidatePreparationError(f"Template capability hash mismatch: {name}")


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
        raise CandidatePreparationError(
            "Candidate mirror path already exists; choose a fresh path to avoid untrusted Git configuration"
        )
    mirror.parent.mkdir(parents=True, exist_ok=True)
    mirror.mkdir()
    subprocess.run(
        ["git", "init", "--bare", "--quiet", str(mirror)],
        cwd=ROOT, env=git_env, check=True, capture_output=True, text=True, encoding="utf-8",
    )

    for label, commit, files in (
        ("historical", HISTORICAL_COMMIT, HISTORICAL_FILES),
        ("release", RELEASE_COMMIT, RELEASE_FILES),
        ("candidate", CANDIDATE_COMMIT, CANDIDATE_FILES),
    ):
        _fetch_verified(mirror, commit, files, git_env)
        pinned_ref = f"refs/heads/t0004-{label}-{commit}"
        _git(mirror, ["update-ref", pinned_ref, commit], git_env)
        if label == "candidate":
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
