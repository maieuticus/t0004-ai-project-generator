# SDD-Auswahl: Spec Kit oder OpenSpec

Spec-Driven Development (SDD) heißt: erst Anforderungen und Plan, dann Umsetzung. Dieses Template
unterstützt zwei gleichwertige Werkzeuge. **Es ist keines vorgewählt.** Dein Agent empfiehlt eines
mit Begründung, du bestätigst, dann richtet er nur dieses ein.

## Entscheidungshilfe

| | Spec Kit | OpenSpec |
|---|---|---|
| Stil | feste Abfolge: specify → plan → tasks → analyze → implement | leichtgewichtig: Änderungen vorschlagen, umsetzen, archivieren |
| Struktur | `specs/<nr>-<name>/`, `.specify/` | `openspec/` mit `changes/` und `specs/` |
| Gates | Analyze- und Review-Gate als Workflow `project-sdd` | Review in der Umsetzung, nicht als Workflow-Gate |
| Voraussetzung | Python 3.11+ (bringt `uv` selbst mit, kein globales Install) | Node.js ≥ 20.19 und npm |
| Eher geeignet für | größere Projekte mit Review-Pflicht | kleine bis mittlere Projekte, laufende Änderungen |

## Einrichten

```text
python scripts/sdd.py select speckit      # oder: openspec
python scripts/sdd.py status              # zeigt Wahl und Version
```

- Version und Wahl landen in `config/project.yaml` (`sdd.tool`, `sdd.version`). Die Versionen sind
  fest gepinnt (`.specify-version`, `.openspec-version`).
- Vorhandene Projektdateien werden nie überschrieben. Was das Werkzeug ändern würde, wird
  verworfen und gemeldet.
- Standard-Agent-Integration ist Copilot. Andere: `--integration codex` (beide Werkzeuge).
- Der Wechsel auf das andere Werkzeug wird abgelehnt. Er braucht einen genehmigten Migrationsplan.

## Spec Kit nutzen

- Windows PowerShell: `.\scripts\specify.ps1 <Argumente>`; Linux/Codespaces: `./scripts/specify <Argumente>`.
  Unter Windows niemals `specify.exe` verwenden.
- Reparatur: `python scripts/bootstrap_specify.py --repair`.
- Der Agent erhält nach der Einrichtung die Skills `speckit-specify`, `-clarify`, `-plan`, `-tasks`,
  `-analyze`, `-implement`, `-converge` (bei Copilot unter `.github/skills/`).
- Workflow mit Analyze- und Review-Gate: `./scripts/specify workflow run project-sdd --input spec="Beschreibung"`.

## OpenSpec nutzen

- Aufruf: `python scripts/openspec_tool.py <Argumente>` (führt die gepinnte Version per `npm exec` aus).
- Der Agent erhält Prompts und Skills `opsx-propose`, `opsx-apply`, `opsx-archive`, `opsx-explore`,
  `opsx-sync`, `opsx-update` (bei Copilot unter `.github/prompts/` und `.github/skills/`).
- Start einer Änderung: `/opsx-propose "deine Idee"`.

## Geprüfter Stand

Geprüft (Linux/Codespaces): Einrichtung beider Werkzeuge in einer echten Projektkopie, erzeugte
Dateien, Eintrag in `config/project.yaml`, Schutz vorhandener Dateien. **Nicht E2E geprüft:**
Aufruf der Slash-Commands in einem laufenden Agenten, der Workflow `project-sdd` im Lauf, Windows
(wird in CI geprüft), andere Agenten als Copilot und Codex.
