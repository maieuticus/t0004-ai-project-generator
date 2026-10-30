"""Validate the active feature's analysis report before the analyze gate."""

import json
import re
import sys
from pathlib import Path

FENCED_BLOCK = re.compile(r"(?ms)^(`{3,}|~{3,})[^\n]*\n.*?^\1[ \t]*$")
FINDING_HEADING = re.compile(r"^### (A\d+)\s+[—-]\s+.+$", re.MULTILINE)
ANY_FINDING_HEADING = re.compile(r"^[ \t]*#{3,}[ \t]+[^\r\n]*$", re.MULTILINE)
FIELD_LINE = re.compile(
    r"(?m)^[ \t]*(?:[-*][ \t]*)?\*\*([^:\r\n]+):\*\*[ \t]*([^\r\n]*?)[ \t]*\r?$"
)
ALLOWED_FIELDS = {"Status", "Begründung", "Geändertes Artefakt"}


def validate_report(root: Path) -> tuple[Path | None, list[str]]:
    errors = []
    root = root.resolve()
    specify_dir = root / ".specify"
    context_file = specify_dir / "feature.json"
    if specify_dir.is_symlink() or context_file.is_symlink() or not context_file.is_file():
        return None, [
            "Aktiver Feature-Kontext fehlt: .specify/feature.json; Feature-Kontext "
            "herstellen und den Workflow erneut ausführen."
        ]

    try:
        context = json.loads(context_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return None, [f"Feature-Kontext ist ungültig: {error}"]
    if not isinstance(context, dict):
        return None, ["Feature-Kontext muss ein JSON-Objekt sein."]

    feature_value = context.get("feature_directory")
    if not isinstance(feature_value, str) or not feature_value.strip():
        return None, ["Feature-Kontext enthält kein feature_directory."]

    specs_dir = root / "specs"
    if specs_dir.is_symlink():
        return None, ["Der specs-Ordner darf kein symbolischer Link sein."]
    try:
        resolved_specs = specs_dir.resolve(strict=True)
        feature_candidate = Path(feature_value)
        if not feature_candidate.is_absolute():
            feature_candidate = root / feature_candidate
        if feature_candidate.is_symlink():
            return None, ["Das aktive Feature-Verzeichnis darf kein symbolischer Link sein."]
        feature_dir = feature_candidate.resolve(strict=True)
    except OSError as error:
        return None, [f"Aktives Feature-Verzeichnis fehlt oder ist unlesbar: {error}"]

    if (
        not resolved_specs.is_dir()
        or resolved_specs.parent != root
        or feature_dir.parent != resolved_specs
        or not feature_dir.is_dir()
    ):
        return None, ["feature_directory muss direkt unter specs/ liegen."]

    report_path = feature_dir / "analyze.md"
    if report_path.is_symlink() or not report_path.is_file():
        return report_path, [
            "Analysebericht fehlt oder ist kein reguläres File: analyze.md; "
            "Bericht im aktiven Feature erstellen."
        ]
    try:
        report = report_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        return report_path, [f"Analysebericht ist unlesbar: {error}"]

    report = FENCED_BLOCK.sub("", report)
    sections = list(re.finditer(r"(?m)^## Wesentliche Befunde[ \t]*$", report))
    if len(sections) != 1:
        return report_path, ["Analysebericht muss genau einen Abschnitt '## Wesentliche Befunde' enthalten."]

    section_start = sections[0].end()
    next_section = re.search(r"(?m)^## (?!#).*$", report[section_start:])
    section = report[section_start:section_start + next_section.start()] if next_section else report[section_start:]
    headings = list(ANY_FINDING_HEADING.finditer(section))

    if not headings:
        if section.strip() == "Keine wesentlichen Befunde.":
            return report_path, []
        return report_path, [
            "Ohne Befunde muss der Abschnitt exakt 'Keine wesentlichen Befunde.' enthalten."
        ]
    if "Keine wesentlichen Befunde." in section:
        errors.append("Der Leereintrag darf nicht mit Befundüberschriften kombiniert werden.")
    if section[:headings[0].start()].strip():
        errors.append("Vor der ersten Befundüberschrift ist nur Leerraum erlaubt; Befunde vollständig strukturieren.")

    for index, heading in enumerate(headings):
        heading_words = heading.group(0).lstrip("# \t").split()
        finding_id = heading_words[0] if heading_words else "Befund ohne ID"
        if not FINDING_HEADING.fullmatch(heading.group(0)):
            errors.append(f"{finding_id}: Befundüberschrift muss dem Format '### A001 — P1: ...' folgen.")
            continue
        block_end = headings[index + 1].start() if index + 1 < len(headings) else len(section)
        block = section[heading.end():block_end]
        field_values = {field_name: [] for field_name in ALLOWED_FIELDS}
        for field_name, field_value in FIELD_LINE.findall(block):
            normalized_field = field_name.strip()
            if normalized_field not in ALLOWED_FIELDS:
                errors.append(
                    f"{finding_id}: unbekanntes Feld {normalized_field!r}; "
                    "erlaubt sind nur Status, Begründung und Geändertes Artefakt."
                )
                continue
            field_values[normalized_field].append(field_value)

        for field_name, values in field_values.items():
            if len(values) > 1:
                errors.append(f"{finding_id}: Feld {field_name!r} darf nur einmal vorkommen.")

        status_values = field_values["Status"]
        reason_values = field_values["Begründung"]
        artifact_values = field_values["Geändertes Artefakt"]
        if len(status_values) != 1:
            errors.append(
                f"{finding_id}: genau ein Statusfeld ist erforderlich; "
                "Status offen, geklärt oder akzeptiert dokumentieren."
            )
            continue
        if len(reason_values) != 1 or not reason_values[0].strip():
            errors.append(f"{finding_id}: genau eine nichtleere Begründung ist erforderlich.")
        status = status_values[0].strip().strip("`").lower()
        if status not in {"offen", "geklärt", "akzeptiert"}:
            errors.append(
                f"{finding_id}: unbekannter Status {status_values[0]!r}; "
                "Status offen, geklärt oder akzeptiert dokumentieren."
            )
        elif status == "offen":
            errors.append(
                f"{finding_id}: wesentlicher Befund ist offen; Befund klären "
                "und den Bericht aktualisieren."
            )
        elif status == "geklärt" and (
            len(artifact_values) != 1 or not artifact_values[0].strip()
        ):
            errors.append(f"{finding_id}: bei Status 'geklärt' ist 'Geändertes Artefakt' erforderlich.")

    return report_path, errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    report_path, errors = validate_report(root)
    if errors:
        print("\n".join(f"Analyze-Gate blockiert: {error}" for error in errors), file=sys.stderr)
        return 1

    if report_path is None:
        print("Analyze-Gate blockiert: validierter Berichtsweg fehlt.", file=sys.stderr)
        return 1
    print(json.dumps({"report_path": report_path.relative_to(root).as_posix()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
