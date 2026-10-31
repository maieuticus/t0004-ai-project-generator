# Generator Contract

Dieser Vertrag definiert die Mindestanforderungen für die Generator-CLI in `t0004`.

## CLI-Grundsätze

- Die Referenzimplementierung ist eine Python-CLI.
- Plattformziele: Linux, Windows, GitHub Codespaces.
- Jeder Fehler liefert einen klaren Exitcode und eine verwertbare Meldung.
- Der installierbare Einstiegspunkt lautet `t0004-generator`. Der Safety-Core verwendet:
  `t0004-generator version`, `t0004-generator check [ZIELPROJEKT]` und
  `t0004-generator plan [ZIELPROJEKT]`, `t0004-generator new [ZIELPROJEKT]`,
  `t0004-generator migrate [QUELLPROJEKT]`,
  `t0004-generator apply [ZIELPROJEKT] --plan DATEI --confirm PLAN-ID` und
  `t0004-generator restore [ZIELPROJEKT] --backup BACKUP-ID`.
  `--json` liefert bei `check`, `plan`, `new` und `migrate` eine maschinenlesbare Darstellung.
- Exitcodes: `0` erfolgreich, `1` bei Kompatibilitäts- oder Voraussetzungskonflikten,
  verweigerten Transaktionen oder Transaktionsfehlern, `2` bei ungültigen Argumenten,
  Pfaden oder Konfigurationen.

## Generator-Modi

- Der Benutzer erstellt ein Repository über GitHubs Template-Funktion aus t0003. `new`
  richtet das vorhandene kompatible Projekt optional ein; es erstellt kein Repository.
  Der derzeitige Einstieg ist lesend und erzeugt denselben Plan wie `plan`: ausschließlich
  `generator.version` kann anschließend mit bestätigtem `apply` gesetzt werden. Bei bereits
  aktueller Version ist der Plan ohne Operation und Backup. Profile, SDD-Initialisierung und
  Generator-Upgrades sind nicht implementiert.
- `migrate` prüft ein bestehendes Projekt ausschließlich lesend, auch ohne
  `config/project.yaml`. Es vergleicht Strategien, erzeugt aber keinen ausführbaren Plan,
  Snapshot oder Projektdateien und führt keine Migration aus.
- Für `migrate` sind zwei Strategien verbindlich vergleichbar auszuweisen:
  - neues t0003-Projekt mit selektivem Import, bevorzugt für kleine Altprojekte;
  - In-place-Update, oft geeignet für etablierte Projekte.
- Der Vergleich benennt Risiken sowie Arbeits- und Tokenaufwand. Eine schreibende Migration setzt
  die ausdrückliche Freigabe der gewählten Strategie voraus.

### Lesender Migrationsbericht

- Die Bestandsanalyse erfasst ausschließlich Dateimetadaten und feste Namens-/Endungsindikatoren
  für Struktur, Konfiguration, Sprachen, Technologien, Dokumentation, Tests, CI und Assets.
  Sie liest bis zu 1 MiB von `config/project.yaml` und akzeptiert höchstens 256 Zeilen zu je
  512 Bytes. Sie klassifiziert vorhandene t0003-Metadaten
  mithilfe des bestehenden Validators; Werte, Modulnamen und Befehle werden nicht ausgegeben
  oder ausgeführt. Andere Inhalte werden durch die Bestandsanalyse nicht ausgewertet.
- Bei sicher prüfbarem `.git`-Verzeichnis ermittelt lokales Git versionierte Änderungen und
  unversionierte Einträge, ohne optionale Sperren, FSMonitor, Hooks oder Submodule. Git kann
  dabei Git-Konfiguration, Index, Ignore-Dateien und versionierte Dateiinhalte lesen.
  Git-Ausgaben und Fehlermeldungen mit Pfaden bleiben intern. Globale/systemweite Konfiguration,
  Attribute und übernommene Git-Umgebungsvariablen werden deaktiviert. Repositories mit
  konfigurierten Git-Filtern, Konfigurations-Includes, partiellen Klonen und Git-Indirektionen
  werden nicht per Git untersucht; ihr Status ist nicht verfügbar.
  Git-Worktrees mit `.git`-Datei, Repositories ohne lesbaren Index sowie große oder unsichere
  Git-Metadaten werden nicht geprüft. Ignorierte Dateien und Submodule sind nicht erfasst;
  unversionierte Verzeichnisse zählen als ein Eintrag. Ausgeschlossene Verzeichnisse und Links
  werden auch beim Git-Status ausgelassen. Bei unvollständiger Strukturprüfung wird kein Git-Status
  erhoben. Der Status kann damit unvollständig sein.
- Es werden höchstens 4000 Projekteinträge bis Tiefe 6 untersucht. Separat werden höchstens
  4000 Git-Metadateneinträge bis Tiefe 16 geprüft; der Git-Index ist auf 16 MiB, dessen Ausgabe
  auf 1 MiB und die Laufzeit des Git-Prozesses auf 10 Sekunden begrenzt. Symlinks, Junctions,
  erkennbare Dateisystemgrenzen und übliche Abhängigkeits-/Build-Verzeichnisse werden nicht
  verfolgt. Bind-Mounts auf demselben Dateisystem sind nicht auf jeder Plattform erkennbar.
  Nicht lesbare, ausgelassene und begrenzte Bereiche stehen im Bericht; Inhalte regulärer
  Dateien werden außer wie oben beschrieben nicht auf Lesbarkeit geprüft. Die Zählungen und
  Indikatoren betreffen nur beobachtete Einträge.
- Für den Aufruf muss das Quellprojekt unverändert bleiben: parallele Änderungen, insbesondere
  an Verzeichnissen und Git-Metadaten, können plattformübergreifend nicht sicher ausgeschlossen
  werden. Wo unterstützt, werden Verzeichnisse descriptor-relativ und ohne Symlink-Verfolgung
  geöffnet. Betriebssystem und Dateisystem können lesebedingt Zugriffszeiten aktualisieren.
  Python kann beim Import Bytecode am Installationsort ablegen; liegt die Generatorinstallation
  im Quellprojekt, verhindert `PYTHONDONTWRITEBYTECODE=1` diese Laufzeitschreibvorgänge.
- Die Ausgabe enthält keine individuellen Dateinamen, Quelltexte, Geheimnisse, Umgebungsvariablen,
  Git-Diagnosen oder Konfigurationswerte. Fehlende Hinweise sind kein Abwesenheitsbeweis. Die
  Empfehlung ist vorläufig bzw. ausdrücklich offen; eine Umsetzung erfordert menschliche Freigabe.
- JSON-Bericht Version 1: `report_version`, `kind`, `facts`, `indicators`, `analysis_limits`,
  `conflicts`, `prerequisites`, `strategies` und `recommendation`. `facts.git.state` ist
  `available`, `not_detected` oder `unavailable`; nicht verfügbare Zählwerte sind `null`.
  `facts.t0003_metadata` ist `not_observed`, `recognized_supported`,
  `recognized_unverified_version`, `not_recognized` oder `unreadable_or_unsupported`.
  `facts.t0003_details` enthält nur Belegungsindikatoren oder `null`. Die
  `recommendation.strategy` ist `A` oder `offen`. Der Bericht ist kein `plan`-Format und
  darf nicht an `apply` übergeben werden. Ein erfolgreicher Bericht liefert Exitcode 0,
  auch bei Konflikten und Analysegrenzen; ein ungültiger Quellpfad liefert 2.

## Ausführungsmodi

- `dry-run` ist der Standard und zeigt nur den Plan:
  - betroffene Dateien,
  - Diffs/Änderungen,
  - Konflikte und Abhängigkeiten.
- Schreibender Modus (`apply`) ist explizit und setzt vorherige Freigabe voraus.
- Planformat 3 beschreibt ausschließlich die tatsächliche Änderung von `generator.version`
  in `config/project.yaml`, einschließlich semantischem Diff, SHA-256 der Original- und
  Zielbytes sowie Fingerabdruck der Zugriffsmetadaten. Der Plan benennt auch das vorab
  nicht vorhandene Backup-Verzeichnis, Original, Manifest, temporäre Datei und optionales
  Wiederherstellungsprotokoll. Projekt- und Speicherpfad sind durch Fingerabdrücke gebunden.
  Andere Konfigurationsinhalte werden nicht ausgegeben. Bei Konflikten oder bereits gesetzter
  aktueller Version gibt es keine Operation und kein Backup.
- Die Plan-ID ist SHA-256 über die kanonische versionierte Darstellung der Operation,
  Konflikte, Warnungen und Backup-Pfade. Die gleichen vollständigen Eingaben ergeben die
  gleiche ID; Dateimodus, Besitzer/Gruppe und erweiterte Attribute unter POSIX bzw. Modus und
  Sicherheitsdeskriptor unter Windows gehen in den Zugriffs-Fingerabdruck ein. Unterschiedliche
  Projekt- oder Speicherpfade, Plattform-Metadaten oder bereits vorhandene Backup-Pfade
  können die ID ändern.
- `apply` akzeptiert nur den gespeicherten vollständigen JSON-Plan und die ausdrücklich
  bestätigte Plan-ID. Es berechnet beides aus dem aktuellen Projekt neu, verweigert
  Abweichungen und prüft vor der Ersetzung nochmals Zustand und Konfiguration.
  Dateiinhalte und Zeilenenden außerhalb des ersetzten Skalars bleiben erhalten.
- Unsichere Pfade (unter anderem `..`, Netzwerkpfade sowie Symlinks/Junctions am Ziel,
  bei `config` oder `docs`) und ungültige Konfigurationen werden abgelehnt. Weder
  Konfigurationswerte noch Datei- oder Kommentarinhalt werden als Diagnose ausgegeben.
- `check` prüft das unterstützte YAML-Teilschema, die Existenz regulärer Basisdateien und Git
  im `PATH`, ohne Projektprüfungen auszuführen. Die geprüfte Template-Version ist ausschließlich
  t0003 `0.1.0`; andere Versionen sind nicht als kompatibel nachgewiesen. Eine abweichende
  gespeicherte Generator-Version und nicht leere Modullisten sind Konflikte, keine Upgrades.
  Eine SDD-Auswahl wird auf Konsistenz und Versionsformat geprüft; ihre Laufzeit- und
  Integrationskompatibilität bleibt ausdrücklich ungeprüft. `plan` und `new` benötigen Git nicht.

## Sicherheit und Änderungsstrategie

- Für jeden Aufruf von `apply` oder `restore` muss das Zielprojekt exklusiv genutzt werden:
  andere Prozesse dürfen es während des Aufrufs nicht verändern. Portable Dateisperren
  können nicht kooperierende Programme nicht zuverlässig ausschließen. Zwischen Aufrufen
  werden Inhalts- und Zugriffsänderungen erkannt; bei Konflikten erfolgt kein Restore.
- Vor der Änderung wird in einem benutzerlokalen Speicher außerhalb des Zielprojekts und
  erkannter Git-Arbeitsverzeichnisse unter `t0004-generator/backups/.t0004-backup-<ID>/`
  ein Snapshot der vollständigen Originalbytes und ein Manifest angelegt. Die Standardbasis
  ist unter Linux `$XDG_DATA_HOME` oder `~/.local/share`, unter Windows `%LOCALAPPDATA%`
  oder `%USERPROFILE%\AppData\Local`, in Codespaces `/workspaces/.t0004-data`.
  `T0004_BACKUP_HOME` kann eine andere absolute lokale Basis vorgeben. Symlinks/Junctions,
  Netzwerkpfade, `..` und Pfade innerhalb eines Git-Arbeitsverzeichnisses werden abgelehnt;
  die Prüfung erkennt insbesondere `.git`-Verzeichnisse und Worktree-`.git`-Dateien.
  Plan und Restore sind an denselben aufgelösten Projekt- und Speicherpfad gebunden.
- Backups der früheren PR-Fassung, die noch im Zielprojekt liegen, werden weder
  verschoben noch gelöscht. `plan` meldet sie als Konflikt; vor Git-Operationen müssen
  sie vom Benutzer geschützt außerhalb des Arbeitsverzeichnisses gesichert werden.
- Unter POSIX sind die Backup-Verzeichnisse auf den ausführenden Benutzer beschränkt
  (0700), Original, Manifest und Protokoll auf höchstens 0600. Unter Windows erhalten die
  Verzeichnisse eine geschützte DACL für diesen Benutzer und SYSTEM; die Berechtigungen
  der Dateien werden vor dem Schreiben und beim Restore geprüft. Administratoren/root und
  Prozesse desselben Benutzers sind nicht ausgeschlossen. Backups können Secrets enthalten. Normales `git add` im
  Projekt erfasst sie nicht; manuelles Kopieren in ein Repository oder nachträgliches
  Anlegen eines übergeordneten Git-Arbeitsverzeichnisses kann diesen Schutz aufheben.
- In Codespaces übersteht die Standardbasis einen Container-Rebuild; beim Löschen des
  Codespace gehen die Daten verloren. Andere Speicherbasen außerhalb von `/workspaces`
  können bereits beim Rebuild verloren gehen.
- Die privaten Backup-Verzeichnisse verhindern keinen Entzug der Verfügbarkeit, falls
  andere Benutzer einen übergeordneten Ordner umbenennen oder Einträge darin löschen dürfen.
  Insbesondere können die Berechtigungen von `/workspaces` dies in Codespaces erlauben.
- Snapshotdateien werden vor der Ersetzung synchronisiert, unter POSIX zusätzlich die
  Verzeichniseinträge. Eine Wiederherstellbarkeit nach Stromausfall oder Dateisystemfehlern
  kann insbesondere unter Windows nicht garantiert werden.
- Unter Windows bleibt die Originaldatei zur Wahrung ihrer Sicherheitsmetadaten erhalten
  und wird nach dem Snapshot direkt beschrieben. Unter POSIX erfolgt bei unterschiedlichen
  Dateisystemen ebenfalls direktes Schreiben; mehrere oder unbekannte Hardlinks werden
  dabei abgelehnt. Windows lehnt außerdem zusätzliche Dateistreams, Hardlinks und nicht
  unterstützte Dateiattribute ab.
- Bei einem abgefangenen Schreibfehler wird ein lesbarer Teilzustand nach Prüfung seiner
  Zugriffsmetadaten mit Fingerabdruck im geschützten Backup protokolliert. `restore` darf
  diesen Zustand nur zurücknehmen, wenn Inhalt und Rechte unverändert sind. Bei einem
  abrupten Abbruch vor der Protokollierung oder wenn die Protokollierung fehlschlägt,
  muss ein Teilzustand manuell aus dem Snapshot wiederhergestellt werden.
- Die Zielzustandsprüfung nach `apply` und `restore` umfasst Dateiinhalt und
  Zugriffs-Fingerabdruck. Ein fehlgeschlagenes `apply` nennt die Backup-ID, sofern die
  Transaktion bereits begonnen wurde. Ist der Zielzustand weder Original, berechnetes
  Ergebnis noch protokollierter Teilzustand, ist nur manuelle Wiederherstellung zulässig.
  Gleiches gilt bei fremden Zwischenänderungen, geänderten Berechtigungen oder beschädigtem Backup.
- `restore` ändert nur die geplante Datei, falls sie dem Generatorergebnis oder einem
  protokollierten Teilzustand entspricht;
  ein bereits wiederhergestellter Originalzustand ist ein No-op. Es löscht weder das
  Backup noch andere Dateien. Nicht abgeschlossene temporäre Dateien sind manuell zu
  prüfen. Backup- und Plan-ID sind Prüfsummen bzw. Identifikatoren, keine Signaturen
  gegen Manipulation durch den ausführenden Benutzer.
- Keine stillen Überschreibungen bei Konflikten.
- Bei Fehlern muss ein sicherer Rollback ohne Verlust fremder Zwischenarbeit möglich sein.
- Keine dynamische Ausführung beliebiger externer Skripte ohne Prüfung.

## Nachvollziehbarkeit

- Generator-Version und gewählte Module/Profiles werden in Zielprojekten dokumentiert.
- Änderungen werden in Tests und Changelog nachvollziehbar abgesichert.
- `verify` prüft abschließend die Integrationskompatibilität von t0003 und t0004 sowie die
  verpflichtenden Praxistests für `new` und `migrate` unter Linux und Windows.
- Stabile Releases von t0003 und t0004 werden getrennt versioniert und veröffentlicht.
