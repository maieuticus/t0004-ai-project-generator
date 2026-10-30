"""Run the pinned OpenSpec CLI through npm without a global installation.

The version lives in `.openspec-version`. Requires Node.js >= 20.19 and npm.
"""

from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "@fission-ai/openspec"
MIN_NODE = (20, 19)


def pinned_version() -> str:
    version = (ROOT / ".openspec-version").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError(".openspec-version muss eine stabile Version wie MAJOR.MINOR.PATCH enthalten.")
    return version


def check_node() -> str:
    npm, node = shutil.which("npm"), shutil.which("node")
    if not npm or not node:
        raise ValueError("Node.js (>= 20.19) und npm fehlen. OpenSpec benötigt beides.")
    output = subprocess.run([node, "--version"], capture_output=True, text=True, check=False).stdout.strip()
    match = re.fullmatch(r"v(\d+)\.(\d+)\.\d+.*", output)
    if not match or (int(match.group(1)), int(match.group(2))) < MIN_NODE:
        raise ValueError(f"Node.js >= 20.19 erforderlich, gefunden: {output or 'unbekannt'}.")
    return npm


def run(arguments: list[str]) -> int:
    npm = check_node()
    command = [npm, "exec", "--yes", f"--package={PACKAGE}@{pinned_version()}", "--", "openspec", *arguments]
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def main() -> int:
    try:
        return run(sys.argv[1:])
    except (OSError, ValueError) as error:
        print(f"OpenSpec: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
