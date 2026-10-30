"""Check project documents and run the configured checks without a shell."""

import argparse
import ast
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import unquote

import projectcfg

SKIP_DIRS = {".git", ".venv", "node_modules", ".artifacts", "__pycache__", "target", "dist", "build", "exports", "backups"}
REQUIRED = (
    "README.md", "AGENTS.md", "config/project.yaml",
    "docs/DV_KONZEPT.md", "docs/PROJECT_HANDOFF.md", "docs/GENERATOR_CONTRACT.md",
    "docs/SDD_QUICKSTART.md", "docs/QUICKSTART.md",
)
HANDOFF_SECTIONS = ("## Aktueller Stand", "## Nächster Schritt")


def candidates(root: Path):
    for directory, names, files in os.walk(root):
        names[:] = [n for n in names if n not in SKIP_DIRS and not (Path(directory) / n).is_symlink()]
        for name in files:
            path = Path(directory) / name
            if not path.is_symlink():
                yield path


def headings(text: str) -> set[str]:
    result, counts = set(), {}
    for heading in re.findall(r"^#{1,6} (.+)$", text, re.MULTILINE):
        slug = re.sub(r"[^\w\s-]", "", heading.lower()).replace(" ", "-")
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        result.add(f"{slug}-{count}" if count else slug)
    return result


def validate(root: Path) -> list[str]:
    errors = [f"{name}: Pflichtdatei fehlt" for name in REQUIRED if not (root / name).is_file()]
    for path in candidates(root):
        relative = path.relative_to(root)
        if relative.parts[0] in {".specify", "openspec", ".github"} and relative.suffix == ".md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        try:
            if path.suffix == ".json":
                json.loads(text)
            elif path.suffix == ".py":
                ast.parse(text, filename=str(relative))
            elif path.suffix == ".md":
                prose = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
                for target in re.findall(r"\[[^\]]*\]\(([^)\s]+)\)", prose):
                    if re.match(r"^[a-zA-Z][\w+.-]*:", target):
                        continue
                    name, _, fragment = unquote(target).partition("#")
                    dest = (path.parent / name).resolve() if name else path
                    if not dest.exists():
                        errors.append(f"{relative}: Linkziel fehlt: {target}")
                    elif fragment and dest.is_file() and dest.suffix == ".md":
                        if fragment not in headings(dest.read_text(encoding="utf-8")):
                            errors.append(f"{relative}: Anker fehlt: {target}")
        except (ValueError, SyntaxError) as error:
            errors.append(f"{relative}: {error}")
    handoff = root / "docs/PROJECT_HANDOFF.md"
    if handoff.is_file():
        content = handoff.read_text(encoding="utf-8")
        errors += [f"docs/PROJECT_HANDOFF.md: Abschnitt '{s}' fehlt" for s in HANDOFF_SECTIONS if s not in content]
    for name in ("vision.md", "architecture.md", "development.md", "operations.md"):
        if (root / "docs" / name).exists():
            errors.append(f"docs/{name}: Inhalt gehört in docs/DV_KONZEPT.md")
    config = root / "config/project.yaml"
    if config.is_file():
        try:
            text = projectcfg.read_text(config)
            tool = projectcfg.get(text, "sdd", "tool")
            if tool not in {None, "speckit", "openspec"}:
                errors.append(f"config/project.yaml: sdd.tool '{tool}' ungültig (speckit | openspec | null)")
            projectcfg.checks(text)
        except (ValueError, json.JSONDecodeError) as error:
            errors.append(str(error))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static-only", action="store_true", help="nur Dokumente und Syntax prüfen")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    errors = validate(root)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Dokumentlinks, Pflichtdateien und Dateisyntax: OK", flush=True)
    if args.static_only:
        return 0
    commands = projectcfg.checks(projectcfg.read_text(root / "config/project.yaml"))
    if not commands:
        print("Keine projektspezifischen Prüfungen in config/project.yaml konfiguriert.")
    for command in commands:
        command[0] = sys.executable if command[0] == "python" else (shutil.which(command[0]) or command[0])
        print("Prüfung:", " ".join(command), flush=True)
        if subprocess.run(command, cwd=root, check=False).returncode:
            return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
