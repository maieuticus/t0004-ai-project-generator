"""Isolated GitHub access boundary for private template retrieval."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import urlsplit


COMPATIBLE_REFERENCE = "6e8363a7ac7d99220d743eea077dcd5cefda9042"
RELEASE_REFERENCE = "964de8538d19cefcb483faff38f10124615a9783"


@dataclass(frozen=True)
class AccessResult:
    success: bool
    category: str
    message: str


@dataclass(frozen=True)
class ReferenceStatus:
    compatible: bool
    default_branch_drift: bool


def redact(value: str) -> str:
    """Remove credential-shaped values from diagnostics."""
    import re

    return re.sub(
        r"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"glpat-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16})",
        "REDACTED",
        value,
    )


def classify_error(stderr: str) -> AccessResult:
    """Classify Git failures without returning raw subprocess output."""
    text = stderr.lower()
    if "expired" in text:
        category = "expired"
    elif any(marker in text for marker in ("403", "permission denied", "access denied", "forbidden")):
        category = "forbidden"
    elif any(marker in text for marker in ("404", "repository not found", "couldn't find remote ref",
                                           "could not find remote ref", "invalid reference")):
        category = "not_found"
    elif any(marker in text for marker in ("could not read username", "could not read password",
                                           "terminal prompts disabled", "no credentials", "not logged in",
                                           "authentication failed")):
        category = "missing"
    elif any(marker in text for marker in ("could not resolve host", "connection timed out",
                                           "connection refused", "network is unreachable")):
        category = "network"
    else:
        category = "unknown"
    messages = {
        "expired": "Zugriff fehlgeschlagen: Zugangsdaten sind abgelaufen.",
        "forbidden": "Zugriff fehlgeschlagen: Berechtigung fehlt.",
        "not_found": "Zugriff fehlgeschlagen: Repository oder Referenz nicht gefunden.",
        "missing": "Zugriff fehlgeschlagen: Zugangsdaten fehlen.",
        "network": "Zugriff fehlgeschlagen: Netzwerk nicht erreichbar.",
        "unknown": "Zugriff fehlgeschlagen: Ursache konnte nicht sicher klassifiziert werden.",
    }
    return AccessResult(False, category, redact(messages[category]))


def git_environment(inherited: dict[str, str] | None = None) -> dict[str, str]:
    """Return a noninteractive environment isolated from caller Git configuration."""
    source = os.environ if inherited is None else inherited
    retained = ("PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "WINDIR", "PATHEXT", "TMP", "TEMP",
                "LANG", "LC_ALL", "LC_CTYPE")
    environment = {key: source[key] for key in retained if key in source}
    environment.update(
        GCM_INTERACTIVE="Never",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_TERMINAL_PROMPT="0",
    )
    return environment


def fetch_command(source: str, destination: Path, reference: str) -> list[str]:
    """Build the credential-helper-only fetch command without token arguments."""
    return [
        "git",
        "-c",
        "credential.helper=!gh auth git-credential",
        "fetch",
        "--no-tags",
        source,
        f"{reference}:refs/t0004/private-access",
    ]


def _credential_bearing_source(source: str) -> bool:
    parsed = urlsplit(source)
    return bool(parsed.scheme and (parsed.username is not None or parsed.password is not None))


def fetch_reference(
    source: str, destination: Path, reference: str, *, env: dict[str, str] | None = None
) -> AccessResult:
    """Fetch one reference into a new bare repository without storing a remote."""
    if _credential_bearing_source(source):
        return AccessResult(False, "unknown", "Zugriff fehlgeschlagen: Zugangsdaten in der Quelle sind nicht zulässig.")
    if destination.exists():
        return AccessResult(False, "unknown", "Zugriff fehlgeschlagen: Ziel existiert bereits.")
    try:
        subprocess.run(
            ["git", "init", "--bare", str(destination)],
            capture_output=True,
            check=True,
            env=git_environment(env),
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        result = subprocess.run(
            fetch_command(source, destination, reference),
            cwd=destination,
            capture_output=True,
            check=False,
            env=git_environment(env),
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return AccessResult(False, "network", "Zugriff fehlgeschlagen: Git ist nicht verfügbar.")
    if result.returncode == 0:
        return AccessResult(True, "ok", "Referenz wurde abgerufen.")
    shutil.rmtree(destination)
    return classify_error(result.stderr)


def reference_status(reference: str, default_branch_reference: str) -> ReferenceStatus:
    """State compatibility and default-branch drift for a resolved reference."""
    return ReferenceStatus(
        compatible=reference == COMPATIBLE_REFERENCE,
        default_branch_drift=default_branch_reference != COMPATIBLE_REFERENCE,
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Fetch one Git reference without persisting credentials.")
    parser.add_argument("source")
    parser.add_argument("destination", type=Path)
    parser.add_argument("reference")
    args = parser.parse_args(argv)
    result = fetch_reference(args.source, args.destination, args.reference)
    print(result.message)
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
