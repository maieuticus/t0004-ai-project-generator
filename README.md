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

## Integration mit t0003

Nach `python -m pip install --no-deps .` führt
`python -m unittest discover -s integration -v` die installierte CLI in temporären
Projekten gegen die echten t0003-Commits `6e8363a7ac7d99220d743eea077dcd5cefda9042`
und `964de8538d19cefcb483faff38f10124615a9783` (ursprüngliches Release) aus. Git und
Netzzugriff auf das öffentliche t0003-Repository sind erforderlich; pip benötigt bei Bedarf
Zugriff auf seine Build-Abhängigkeiten. Die CI führt dies unter Linux und Windows aus.
Backups liegen ausschließlich in einem temporären, von der CLI geschützten Speicher
außerhalb des Projekt-Repositories und werden nach den Tests entfernt.

Offline kann `T0004_T0003_MIRROR` auf den absoluten Pfad eines zuvor beschafften lokalen
Git-Repositories gesetzt werden, das **beide** vollständigen Commit-Objekte samt zugehöriger
Bäume und Dateien enthält. Die fest gepinnten Commit-IDs bleiben unverändert; fehlen
Objekte, schlägt der Test fehl. Für eine vollständig netzlose Ausführung müssen auch
Pythons Build-Abhängigkeiten lokal verfügbar sein.

Die Testprojekte werden aus Git-Quellständen ausgecheckt. Sie belegen **nicht** das
tatsächliche Anlegen eines GitHub-Repositories über „Use this template“; dieser Schritt
und die anschließende CLI-Nutzung bleiben eine separate manuelle Abnahme.

## Generator Safety-Core und bestätigtes Apply

Python 3.11+ und Git werden vorausgesetzt. Den Generator bei Bedarf ausdrücklich installieren:

```text
python -m pip install .
t0004-generator version
t0004-generator check /pfad/zum/projekt
t0004-generator plan /pfad/zum/projekt
t0004-generator new /pfad/zum/projekt
t0004-generator migrate /pfad/zum/bestandsprojekt
```

Für ein neues Projekt zuerst auf GitHub **Use this template** bei `t0003-ai-project-template`
wählen und das erstellte Repository lokal öffnen. `new` richtet dieses vorhandene Projekt
optional ein; es erstellt kein GitHub-Repository und greift nicht auf das Netzwerk zu.

Unter Windows statt `/pfad/zum/projekt` einen Windows-Pfad angeben. Ohne Pfad wird das aktuelle
Verzeichnis verwendet; `check`, `plan`, `new` und `migrate` unterstützen `--json`. Sie führen keine Befehle
aus der Projektkonfiguration aus. `new` und `plan` schreiben nichts ins Zielprojekt und liefern
denselben Plan. Ohne Modulauswahl betrifft der ausführbare Plan ausschließlich
`generator.version`: Ist die Version bereits aktuell, gibt es keine Operation und kein Backup.

Mit `new /pfad/zum/projekt --module python --json` oder dem entsprechenden `plan` wird
`python@0.1.0` über einen Mehrdatei-Plan im Format 4 vorbereitet. Das Modul erstellt ein
installierbares `project_app` im `src/`-Layout, ein ausführbares Beispiel, `unittest`-Tests
und `docs/PYTHON.md`. Es ergänzt den Projektcheck und die bestehende GitHub Action und trägt
das Modul in `config/project.yaml` ein. Vorhandene oder nachträglich veränderte Moduldateien
werden nicht überschrieben; ein vollständig unverändertes Modul ergibt einen No-op.

Voraussetzung ist `template.release: 0.1.0` **und** der bytegenau geprüfte t0003-Dateistand
der Check- und CI-Dateien aus Commit `6e8363a`. Der ursprüngliche Release-Stand erfüllt die
CI-Voraussetzung nicht. Auch andere möglicherweise kompatible Änderungen werden vorsorglich
abgelehnt; `6e8363a` ist kein behauptetes neues offizielles Release. Dateiinhalte und
Zugriffsmetadaten der Voraussetzungen sind an den Plan gebunden und werden vor dem ersten
Projekt-Schreibzugriff erneut geprüft.

Andere Technologiemodule, SDD-Initialisierung, Generator-Upgrades, eine schreibende Migration
und das vollständige technologieabhängige `verify` sind nicht verfügbar.

`migrate` untersucht auch Projekte ohne t0003-Konfiguration und vergleicht selektive Übernahme
mit schrittweiser Anpassung. Der Bericht ist **kein Apply-Plan** und verändert keine Projektdateien.
Er enthält nur feste Kategorien und Zählwerte, keine individuellen Dateinamen, Inhalte oder
Konfigurationswerte. Fehlende Hinweise sind kein Nachweis für deren Abwesenheit; Grenzen und
offene Entscheidungen stehen im Bericht. Symlinks und Abhängigkeitsordner werden nicht verfolgt;
Tiefe und Anzahl der Einträge sind begrenzt. Git-Status ist bei unsicheren Git-Metadaten,
Worktrees, konfigurierten Git-Filtern und partiellen Klonen nicht verfügbar. Ignorierte Dateien,
Submodule und ausgeschlossene Verzeichnisse bleiben beim Git-Status offen.
Während der Analyse darf kein anderer Prozess das Projekt verändern. Dateisysteme können beim
Lesen Zugriffszeiten aktualisieren; die Laufzeit selbst kann Bytecode-Caches am Installationsort
erzeugen. Liegt die Generatorinstallation im Quellprojekt, zum Schutz davor
`PYTHONDONTWRITEBYTECODE=1` setzen. Weitere Grenzen und das JSON-Format stehen im
[Generator-Vertrag](docs/GENERATOR_CONTRACT.md).

Beispiel unter Linux; Plan und bestätigte ID vor `apply` selbst prüfen:

```text
t0004-generator new /pfad/zum/projekt --module python --json > /tmp/t0004-plan.json
t0004-generator apply /pfad/zum/projekt --plan /tmp/t0004-plan.json --confirm <Plan-ID>
t0004-generator restore /pfad/zum/projekt --backup <Backup-ID>
```

In Windows PowerShell den Plan z. B. mit `t0004-generator new C:\projekt --module python --json |
Out-File -Encoding utf8 "$env:TEMP\t0004-plan.json"` speichern und diesen Pfad bei `--plan`
verwenden. `apply` gibt die Backup-ID aus; `restore` behält das Backup zur manuellen Prüfung.
Backups liegen standardmäßig in einem geschützten lokalen Speicher außerhalb von
Git-Arbeitsverzeichnissen:

| Umgebung | Speicherbasis |
|---|---|
| Linux | `$XDG_DATA_HOME` oder `~/.local/share` |
| Windows | `%LOCALAPPDATA%` oder `%USERPROFILE%\AppData\Local` |
| Codespaces | `/workspaces/.t0004-data` (über Container-Rebuilds hinweg persistent) |

Der tatsächliche Snapshot liegt unter `t0004-generator/backups/.t0004-backup-<Backup-ID>`
innerhalb dieser Basis. `T0004_BACKUP_HOME` kann eine andere absolute lokale Basis wählen;
sie darf weder im Zielprojekt noch in einem Git-Arbeitsverzeichnis liegen. Für Plan, Apply
und Restore muss dieselbe Speicherbasis und derselbe Projektpfad verwendet werden.

Snapshots enthalten die vollständige ursprüngliche Konfiguration und möglicherweise Secrets.
Git erfasst sie bei normalen Operationen im Projekt nicht; sie dürfen nicht manuell in ein
Repository kopiert oder unbedacht geteilt werden. Beim Löschen eines Codespace gehen auch
dessen Backups verloren; bei anderer Speicherbasis kann dies bereits beim Rebuild geschehen.
Alte Backups aus vorherigen PR-Versionen bleiben unverändert im Projekt; `plan` meldet
sie als Konflikt. Vor Git-Operationen müssen sie geschützt außerhalb gesichert werden.

Details zu Versionsgrenzen, Konflikten, Fingerabdruck und Exitcodes stehen im
[Generator-Vertrag](docs/GENERATOR_CONTRACT.md).
