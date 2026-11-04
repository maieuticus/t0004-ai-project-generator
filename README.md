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

Weitere Technologiemodule, SDD-Initialisierung, Generator-Upgrades
und das vollständige technologieabhängige `verify` sind nicht verfügbar.

`--module java` plant den Java-25-/Maven-Starter mit Format 4. Der feste
Projektcheck-Adapter startet `mvnw.cmd` unter Windows und `sh mvnw` unter Unix;
so ist kein transportiertes Unix-Ausführungsrecht erforderlich. Erst der Check
kann Maven und Abhängigkeiten herunterladen und führt JUnit und den JAR-Build aus.
Plan und Apply starten weder Build noch Download.
Unter Unix wird für den geprüften ZIP-Download `unzip` benötigt: Der originale
Wrapper weicht ohne `unzip` auf ein anderes Archiv aus, dessen Hash nicht dem
festgelegten ZIP-Hash entspricht; der Build wird dann sicher abgelehnt.

Der Windows-Wrapper wird mit Git-stabilen LF-Zeilenenden erzeugt. Bei bereits
installierten Java-Modulen erkennt die Planung auch die exakt bekannte frühere
CRLF-Fassung; andere Änderungen bleiben Konflikte. Für alte Snapshots gelten die
ursprünglich gespeicherten Dateihashes: Hat Git die Datei danach verändert, verweigert
Restore die automatische Rücknahme weiterhin, bis der Zustand geprüft ist.

`--module typescript` plant `typescript@0.1.0` im Ordner `typescript/`. Alle drei Module
lassen sich nacheinander in beliebiger Reihenfolge installieren. Jeder Apply erzeugt einen
eigenen geschützten Snapshot; Restore erfolgt in umgekehrter Installationsreihenfolge.
Die CI installiert mit Node 24 zuerst per `npm ci --ignore-scripts --prefix typescript`
und führt danach den Projektcheck mit TypeScript-Build und `node:test` aus. Plan und Apply
installieren keine Pakete. Der echte GitHub-Template-Test mit p9999 ist abgeschlossen.

Nach mindestens einem Sprachmodul plant `t0004-generator plan /pfad/zum/projekt
--infrastructure docker-compose --json` die feste Erweiterung `docker-compose@0.1.0`.
Der gespeicherte Plan wird wie bei Sprachmodulen mit `apply --plan DATEI --confirm
PLAN-ID` bestätigt. Er erzeugt Compose, `.dockerignore`, sprachabhängige Dockerfiles
und `docs/DOCKER.md`; Generatorbefehle starten kein Docker. Mit Docker Engine und
Compose können die Konsolenprogramme anschließend über `docker compose build` und
`docker compose run --rm app-python` (entsprechend `app-typescript`, `app-java` für
installierte Module) gestartet werden. Neue Sprachmodule erweitern die bekannten Dateien
innerhalb ihrer geschützten Transaktion. Fremdänderungen sind Konflikte; Restore erfolgt
in umgekehrter Apply-Reihenfolge. Weitere Hinweise stehen in der erzeugten Docker-Doku.

Bei Projekten, die mit der früheren TypeScript-Vorlage aus PR B erstellt wurden, enthält
`docs/TYPESCRIPT.md` eine veraltete Aussage. Da Moduldateien bytegenau geprüft werden,
meldet eine erneute Modulplanung mit der korrigierten Vorlage einen Konflikt, auch bei
der anschließenden Planung des Python-Moduls. Die Datei muss vor der weiteren Planung
bewusst an die korrigierte Vorlage angepasst werden; der Generator überschreibt sie nicht.

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

Strategie B bietet einen ausschließlich lesenden Basisplan:

```text
t0004-generator migrate /pfad/zum/bestandsprojekt --baseline --json
```

Der Plan zeigt das feste Paket einschließlich Ergebnis-Hashes. Die migrationsspezifische
`AGENTS.md` muss nach Inhaltsprüfung separat mit `--confirm-agents <SHA256>` bestätigt werden;
die Bestätigung ist an die Plan-ID gebunden. Auch ein konfliktfreier Plan ist nicht ausführbar.
Vor einem späteren Apply ist ein unabhängiges, auf Wiederherstellbarkeit geprüftes Komplettbackup
erforderlich; siehe [Generator-Vertrag](docs/GENERATOR_CONTRACT.md). Es werden keine Checks
ausgeführt, keine CI verändert und keine Module eingerichtet oder freigegeben.

Für Strategie A kann eine konkrete Auswahl ausschließlich lesend geplant werden:

```text
t0004-generator migrate /pfad/zum/altprojekt --destination /pfad/zum/t0003-projekt --file src/app.py --file docs/anleitung.md --json
```

Der Plan liest nur; eine Übernahme erfordert einen separaten bestätigten `apply`:

```text
t0004-generator migrate /pfad/zum/altprojekt --destination /pfad/zum/t0003-projekt --file src/app.py --json > /tmp/migration.json
t0004-generator apply /pfad/zum/t0003-projekt --source /pfad/zum/altprojekt --plan /tmp/migration.json --confirm <Plan-ID>
t0004-generator restore /pfad/zum/t0003-projekt --backup <Backup-ID>
```

Die Plan-ID und Auswahl vor der ausdrücklichen Bestätigung prüfen. Apply berechnet den Plan
erneut, liest die ausgewählten Quellbytes und erstellt vor Zieländerungen einen geschützten
Snapshot. Restore prüft den Zielzustand und entfernt neue Dateien sowie nur leere, neu
angelegte Verzeichnisse. Fremdänderungen verhindern die automatische Rücknahme.
Quelle und Ziel müssen getrennt sein, das Ziel muss den geprüften t0003-Stand erfüllen.
Nur ausdrücklich ausgewählte `.md`, `.txt`, `.py` und `.ts`-Dateien sind zulässig;
versteckte Pfade, Konfigurations-, Build- und Abhängigkeitsverzeichnisse sind ausgeschlossen.
Vorhandene Zieldateien sind Konflikte. Dateinamen und Hashes stehen im Plan und können
vertraulich sein; Inhalt, Dateinamen und Hashes vor einer Weitergabe selbst prüfen. Die
Planung erkennt Secrets in ausgewählten Dateien nicht und übernimmt keine Git-Historie.
Für Planung und Apply müssen Quelle und Ziel exklusiv genutzt werden. Pfadprüfungen und
Lesezugriffe sind plattformübergreifend nicht atomar; nicht kooperierende Prozesse und
Bind-Mounts können daher auch während Apply Race-Conditions verursachen. Nach abruptem
Abbruch kann eine manuelle Wiederherstellung erforderlich sein.
Dateisysteme können Zugriffszeiten aktualisieren; liegt die Python-Installation in einem
Projekt, `PYTHONDONTWRITEBYTECODE=1` setzen.

Beispiel unter Linux; Plan und bestätigte ID vor `apply` selbst prüfen:

```text
t0004-generator new /pfad/zum/projekt --module python --json > /tmp/t0004-plan.json
t0004-generator apply /pfad/zum/projekt --plan /tmp/t0004-plan.json --confirm <Plan-ID>
t0004-generator restore /pfad/zum/projekt --backup <Backup-ID>
```

Für TypeScript oder Java `--module typescript` beziehungsweise `--module java`
verwenden und für jedes weitere Modul einen neuen Plan erzeugen und bestätigen.

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
