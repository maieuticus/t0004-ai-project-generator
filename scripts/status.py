"""Show the documented project status without changing any project file."""

from pathlib import Path
import re
import subprocess
import sys

import projectcfg

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ("Aktueller Stand", "Nächster Schritt")


def section(document: str, title: str) -> str:
    """Return a level-two section, ignoring headings inside code fences."""
    lines, active, fenced = [], False, False
    for line in document.splitlines():
        if re.match(r" {0,3}(`{3,}|~{3,})", line):
            fenced = not fenced
        elif not fenced and re.match(r"#{1,2} ", line):
            if active:
                break
            active = line.rstrip() == f"## {title}"
        if active:
            lines.append(line)
    if not any(line.strip() for line in lines[1:]):
        raise ValueError(f"Abschnitt '## {title}' fehlt oder ist leer in docs/PROJECT_HANDOFF.md.")
    return "\n".join(lines).strip()


def git(*args: str) -> str:
    try:
        result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)
    except OSError:
        return "unbekannt"
    return result.stdout.strip() if result.returncode == 0 else "unbekannt"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    handoff = ROOT / "docs/PROJECT_HANDOFF.md"
    try:
        document = handoff.read_text(encoding="utf-8")
        parts = [section(document, title) for title in SECTIONS]
        config = projectcfg.read_text()
    except (OSError, UnicodeError, ValueError) as error:
        print(f"Projektstatus nicht verfügbar: {error}", file=sys.stderr)
        return 1
    print("\n\n".join(parts))
    print("\n## Repository und Werkzeuge")
    print(f"- Branch/Commit: {git('rev-parse', '--abbrev-ref', 'HEAD')} @ {git('rev-parse', '--short', 'HEAD')}")
    print(f"- Nicht committete Änderungen: {'ja' if git('status', '--porcelain') not in ('', 'unbekannt') else 'nein/unbekannt'}")
    print(f"- SDD-Werkzeug: {projectcfg.get(config, 'sdd', 'tool') or 'noch nicht gewählt'}")
    print(f"- Template-Version (übernommen): {projectcfg.get(config, 'template', 'release')}")
    print(f"\nQuelle: {handoff}")
    print("Dokumentierter Stand; kein automatischer Abgleich mit Tests. Git-Stand hat Vorrang vor dem Handoff.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
