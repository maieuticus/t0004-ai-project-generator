"""Compatibility wrapper for the shared project configuration helpers."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from project_generator.projectcfg import CONFIG, ROOT, checks, get, read_text, set_value

__all__ = ["CONFIG", "ROOT", "checks", "get", "read_text", "set_value"]
