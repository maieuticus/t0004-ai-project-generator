# t0004-ai-project-generator

> Eigenständiges Generator-Repository auf Basis von `t0003-ai-project-template`.
> Ziel ist eine sichere, nachvollziehbare Python-CLI mit `dry-run` als Standard.

## Einstieg

1. Regeln und Arbeitsstand lesen: `AGENTS.md`, `docs/PROJECT_HANDOFF.md`, `docs/DV_KONZEPT.md`.
2. Generator-Vertrag prüfen: `docs/GENERATOR_CONTRACT.md`.
3. Änderungen über den SDD-Ablauf planen und umsetzen.

## Wichtige Dateien

| Datei | Zweck |
|---|---|
| [AGENTS.md](AGENTS.md) | Arbeitsregeln für alle KI-Agenten |
| [docs/DV_KONZEPT.md](docs/DV_KONZEPT.md) | verbindliche Generator-Ziele und Architektur |
| [docs/GENERATOR_CONTRACT.md](docs/GENERATOR_CONTRACT.md) | CLI-Vertrag inkl. Dry-run/Apply/Backup-Rollback |
| [docs/PROJECT_HANDOFF.md](docs/PROJECT_HANDOFF.md) | aktueller Arbeitsstand für Übergaben |
| [config/project.yaml](config/project.yaml) | Projekt-, Template- und SDD-Metadaten |

## Prüfen

```text
python scripts/check.py
python scripts/status.py
python -m unittest discover -s .github/template-tests -v
python -m unittest discover -s tests -v
```

## Generator Safety-Core

Python 3.11+ und Git werden vorausgesetzt. Den Generator bei Bedarf ausdrücklich installieren:

```text
python -m pip install .
t0004-generator version
t0004-generator check /pfad/zum/projekt
t0004-generator plan /pfad/zum/projekt
```

Unter Windows statt `/pfad/zum/projekt` einen Windows-Pfad angeben. Ohne Pfad wird das aktuelle
Verzeichnis verwendet; `check` und `plan` unterstützen `--json`. Beide führen keine Befehle aus
der Projektkonfiguration aus und greifen nicht auf das Netzwerk zu. `plan` zeigt ausschließlich
einen semantischen Vorschlag für `generator.version`, keine ausführbare Patchdatei. Er schreibt
nichts ins Zielprojekt. `new`, `apply`, Backup, Rollback und Migration sind noch nicht verfügbar.

Details zu Versionsgrenzen, Konflikten, Fingerabdruck und Exitcodes stehen im
[Generator-Vertrag](docs/GENERATOR_CONTRACT.md).
