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
```
