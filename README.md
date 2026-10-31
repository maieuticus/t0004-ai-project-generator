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

## Generator Safety-Core und bestätigtes Apply

Python 3.11+ und Git werden vorausgesetzt. Den Generator bei Bedarf ausdrücklich installieren:

```text
python -m pip install .
t0004-generator version
t0004-generator check /pfad/zum/projekt
t0004-generator plan /pfad/zum/projekt
```

Unter Windows statt `/pfad/zum/projekt` einen Windows-Pfad angeben. Ohne Pfad wird das aktuelle
Verzeichnis verwendet; `check` und `plan` unterstützen `--json`. Beide führen keine Befehle aus
der Projektkonfiguration aus und greifen nicht auf das Netzwerk zu. `plan` schreibt nichts ins
Zielprojekt. Der ausführbare Plan betrifft derzeit ausschließlich `generator.version`; `new`,
Migration und das vollständige technologieabhängige `verify` sind noch nicht verfügbar.

Beispiel unter Linux; Plan und bestätigte ID vor `apply` selbst prüfen:

```text
t0004-generator plan /pfad/zum/projekt --json > /tmp/t0004-plan.json
t0004-generator apply /pfad/zum/projekt --plan /tmp/t0004-plan.json --confirm <Plan-ID>
t0004-generator restore /pfad/zum/projekt --backup <Backup-ID>
```

In Windows PowerShell den Plan z. B. mit `t0004-generator plan C:\projekt --json |
Out-File -Encoding utf8 "$env:TEMP\t0004-plan.json"` speichern und diesen Pfad bei `--plan`
verwenden. `apply` gibt die Backup-ID aus; `restore` behält das Backup zur manuellen Prüfung.
Backups enthalten die vollständige ursprüngliche Konfiguration, möglicherweise mit Secrets.
Sie werden **nicht automatisch von Git ausgeschlossen** und dürfen nicht committed oder
unbedacht geteilt werden.

Details zu Versionsgrenzen, Konflikten, Fingerabdruck und Exitcodes stehen im
[Generator-Vertrag](docs/GENERATOR_CONTRACT.md).
