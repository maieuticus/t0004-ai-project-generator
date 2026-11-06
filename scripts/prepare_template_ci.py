"""Prepare a credential-free local template mirror during a trusted CI retrieval step."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gh_access


SOURCE = gh_access.T0003_SOURCE


def set_output(name: str, value: str) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8", newline="\n") as stream:
            stream.write(f"{name}={value}\n")


def report_status(message: str) -> None:
    print(message)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8", newline="\n") as stream:
            stream.write(f"{message}\n\n")


def not_verified(message: str) -> None:
    report_status(message)
    set_output("template_ready", "false")
    set_output("private_auth", "not_verified")


def prepare(mirror: Path, env: dict[str, str]) -> bool:
    if not env.get("GH_TOKEN"):
        not_verified(
            "Public generator checks continue without a secret; "
            "private authentication: NOT VERIFIED (read credential is not configured)."
        )
        return False

    mirror = mirror.resolve()
    references = (gh_access.COMPATIBLE_REFERENCE, gh_access.RELEASE_REFERENCE)
    for reference in references:
        result = gh_access.fetch_reference(
            SOURCE, mirror, reference, env=env, include_credential_env=True
        )
        if not result.success:
            not_verified(
                f"Public template fetch: FAILED ({result.category}); "
                f"private authentication: NOT VERIFIED. {result.message}"
            )
            return False

    default_branch = gh_access.resolve_default_branch(
        SOURCE, env=env, include_credential_env=True
    )
    if not default_branch.success or default_branch.reference is None:
        not_verified(
            f"Public template fetch: FAILED ({default_branch.category}); "
            f"private authentication: NOT VERIFIED. {default_branch.message}"
        )
        return False
    result = gh_access.fetch_reference(
        SOURCE, mirror, default_branch.reference, env=env, include_credential_env=True
    )
    if not result.success:
        not_verified(
            f"Public template fetch: FAILED ({result.category}); "
            f"private authentication: NOT VERIFIED. {result.message}"
        )
        return False

    local_env = gh_access.git_environment(env)
    default_ref = gh_access.fetched_ref(default_branch.reference)
    branch = "refs/heads/t0004-ci-default"
    subprocess.run(
        ["git", "--git-dir", str(mirror), "update-ref", branch, default_ref],
        check=True,
        capture_output=True,
        env=local_env,
        text=True,
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "--git-dir", str(mirror), "symbolic-ref", "HEAD", branch],
        check=True,
        capture_output=True,
        env=local_env,
        text=True,
        encoding="utf-8",
    )
    set_output("template_ready", "true")
    set_output("private_auth", "not_verified")
    set_output("mirror", str(mirror))
    report_status(
        "Public template retrieval: PASS; pinned local mirror is ready. "
        "Private authentication: NOT VERIFIED (the source is public)."
    )
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch pinned template refs for trusted CI.")
    parser.add_argument("--mirror", type=Path, default=None)
    parser.add_argument("--untrusted", action="store_true")
    args = parser.parse_args(argv)
    if args.untrusted:
        not_verified(
            "Public generator checks run without a credential; "
            "private authentication: NOT VERIFIED (untrusted event)."
        )
        return 0
    configured = os.environ.get("T0004_T0003_MIRROR")
    runner_temp = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir()))
    if args.mirror:
        mirror = args.mirror
    elif configured:
        mirror = Path(configured)
    else:
        mirror = runner_temp / "t0003-template.git"
    try:
        return 0 if prepare(mirror, dict(os.environ)) else (0 if not os.environ.get("GH_TOKEN") else 1)
    except (OSError, subprocess.SubprocessError) as error:
        not_verified(
            f"Public template retrieval: FAILED; private authentication: NOT VERIFIED. "
            f"{gh_access.redact(str(error))}"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
