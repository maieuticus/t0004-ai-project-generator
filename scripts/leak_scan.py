"""Scan acceptance artifacts for credential-shaped values without exposing them."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sys


PATTERNS = {
    "GitHub token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    "GitLab token": re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private key": re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
}


@dataclass(frozen=True)
class Finding:
    path: Path
    message: str


def _files(paths: list[Path]):
    for path in paths:
        if path.is_symlink():
            continue
        if path.is_file():
            yield path
        elif path.is_dir():
            for candidate in path.rglob("*"):
                if candidate.is_file() and not candidate.is_symlink():
                    yield candidate


def scan_paths(paths: list[Path]) -> list[Finding]:
    """Return credential-pattern findings without copying matched content."""
    findings = []
    for path in _files(paths):
        try:
            content = path.read_bytes().decode("utf-8", errors="replace")
        except OSError:
            continue
        for name, pattern in PATTERNS.items():
            if pattern.search(content):
                findings.append(Finding(path, f"{name} in {path}: REDACTED"))
                break
    return findings


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Scan files for credential-shaped values.")
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args(argv)
    findings = scan_paths(args.paths)
    for finding in findings:
        print(finding.message)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
