"""Export the project hand-off for an external discussion and check returned results.

  python scripts/handoff.py export [--full] [--output PATH]
  python scripts/handoff.py import-check RETURNED.md

Both commands are read-only with respect to project files. `export` writes one
Markdown file (default: exports/, git-ignored) stamped with the repository state and
redacts lines that look like secrets. `import-check` compares a returned document
with the *current* repository, reports drift since the export and prints a decision
table; it never applies anything.
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STAMP = re.compile(r"<!-- handoff-export v1 commit=(?P<commit>\S+) branch=(?P<branch>\S+) dirty=(?P<dirty>true|false) "
                   r"created=(?P<created>\S+) -->")
SECRET = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY-----|\bgh[pousr]_[A-Za-z0-9]{20,}|\bgithub_pat_[A-Za-z0-9_]{20,}|\bAKIA[0-9A-Z]{16}"
    r"|\bsk-[A-Za-z0-9_-]{20,}|(?i:\b(?:password|passwort|secret|token|api[_-]?key)\b)\s*[:=]\s*[\"']?[^\s\"'<>{}_*-]{6,})")
ARCHITECTURE_HINTS = ("architektur", "architecture", "dv_konzept", "dv-konzept", "constitution")


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False)
    if result.returncode:
        raise ValueError(f"git {' '.join(args)} fehlgeschlagen: {result.stderr.strip()}")
    return result.stdout.strip()


def redact(text: str) -> tuple[str, int]:
    count, lines = 0, []
    for line in text.splitlines():
        if SECRET.search(line):
            lines.append("[ENTFERNT: möglicher Zugangsdatenwert]")
            count += 1
        else:
            lines.append(line)
    return "\n".join(lines), count


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def spec_files() -> list[str]:
    files = []
    for base in ("specs", "openspec"):
        directory = ROOT / base
        if directory.is_dir():
            files += sorted(p.relative_to(ROOT).as_posix() for p in directory.rglob("*.md") if not p.is_symlink())
    return files


def build_export(full: bool) -> tuple[str, int]:
    commit = git("rev-parse", "HEAD")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    dirty = "true" if git("status", "--porcelain") else "false"
    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    parts = [f"<!-- handoff-export v1 commit={commit} branch={branch.replace(' ', '_')} dirty={dirty} created={created} -->",
             f"# Projektübergabe-Export ({'umfassend' if full else 'kompakt'})",
             f"Stand: Commit `{commit[:10]}` auf `{branch}`; nicht committete Änderungen: {'ja' if dirty == 'true' else 'nein'}. "
             "Rückgaben sind vorläufig und erteilen keine Entscheidungen oder Rechte.",
             "## Arbeitsstand (docs/PROJECT_HANDOFF.md)", read("docs/PROJECT_HANDOFF.md")]
    if full:
        parts += ["## Projektmetadaten (config/project.yaml)", "```yaml\n" + read("config/project.yaml") + "\n```",
                  "## Verbindliche Projektbeschreibung (docs/DV_KONZEPT.md)", read("docs/DV_KONZEPT.md")]
        for path in spec_files():
            parts += [f"## Spezifikation: {path}", read(path)]
        parts += ["## Letzte Commits", "```text\n" + git("log", "--oneline", "-15") + "\n```",
                  "## Offene Fragen und Tests",
                  "Offene Fragen stehen im Handoff. Testergebnisse: `python scripts/check.py` ausführen; "
                  "dieser Export enthält keine Ausführungsergebnisse."]
    return redact("\n\n".join(parts) + "\n")


def export(full: bool, output: Path | None) -> int:
    text, redacted = build_export(full)
    if output is None:
        name = f"handoff-{'full' if full else 'compact'}-{git('rev-parse', '--short', 'HEAD')}.md"
        output = ROOT / "exports" / name
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8", newline="\n")
    print(f"Export geschrieben: {output}")
    if redacted:
        print(f"Hinweis: {redacted} Zeile(n) mit möglichen Zugangsdaten entfernt. Export vor dem Teilen trotzdem prüfen.")
    return 0


def import_check(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    stamp = STAMP.search(text)
    head = git("rev-parse", "HEAD")
    dirty_now = bool(git("status", "--porcelain"))
    print(f"# Importanalyse: {path.name}\n")
    findings = 0
    if not stamp:
        print("- WARNUNG: Kein Export-Stempel gefunden. Herkunft und Stand sind unbekannt.")
        findings += 1
    else:
        exported = stamp.group("commit")
        if exported != head:
            findings += 1
            try:
                changed = git("diff", "--name-only", exported, "HEAD").splitlines()
                detail = f"{len(changed)} Datei(en) seit dem Export geändert: " + ", ".join(changed[:15])
            except ValueError:
                detail = "Exportstand ist in diesem Repository nicht auffindbar."
            print(f"- WARNUNG: Export stammt von Commit {exported[:10]}, aktuell ist {head[:10]}. {detail}")
        if stamp.group("dirty") == "true" or dirty_now:
            findings += 1
            print("- WARNUNG: Beim Export oder jetzt gibt es nicht committete Änderungen; der Vergleich ist unvollständig.")
    if SECRET.search(text):
        findings += 1
        print("- WARNUNG: Die Rückgabe enthält Text, der wie Zugangsdaten aussieht. Nicht übernehmen.")
    lowered = text.lower()
    if any(hint in lowered for hint in ARCHITECTURE_HINTS):
        findings += 1
        print("- HINWEIS: Die Rückgabe berührt möglicherweise genehmigte Architekturentscheidungen. "
              "Nur nach ausdrücklicher Freigabe übernehmen.")
    if not findings:
        print("- Keine Abweichungen festgestellt.")
    headings = [h for h in re.findall(r"^#{1,3} (.+)$", text, re.MULTILINE)]
    print("\n## Entscheidungsvorlage (übernehmen / anpassen / verwerfen / offen)\n")
    print("| Abschnitt der Rückgabe | Entscheidung |\n|---|---|")
    for heading in headings[1:] or ["(keine Abschnitte)"]:
        print(f"| {heading} | offen |")
    print("\nNichts wurde geändert. Verbindliche Dokumente erst nach Freigabe aktualisieren.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    exporter = sub.add_parser("export")
    exporter.add_argument("--full", action="store_true", help="umfassender Export statt kompakt")
    exporter.add_argument("--output", type=Path)
    importer = sub.add_parser("import-check")
    importer.add_argument("file", type=Path)
    args = parser.parse_args()
    try:
        return export(args.full, args.output) if args.command == "export" else import_check(args.file)
    except (OSError, ValueError, UnicodeError) as error:
        print(f"Handoff: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
