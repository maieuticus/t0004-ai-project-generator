"""Safety core for the t0004 project generator."""

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def installed_version() -> str:
    """Return the installed distribution version, with a source-tree fallback."""
    try:
        return version("t0004-ai-project-generator")
    except PackageNotFoundError:
        return (Path(__file__).resolve().parents[2] / "VERSION").read_text(encoding="utf-8").strip()
