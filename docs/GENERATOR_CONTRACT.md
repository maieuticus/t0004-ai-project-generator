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
  `new` und `plan` akzeptieren optional `--module python`.
- Exitcodes: `0` erfolgreich, `1` bei Kompatibilitäts- oder Voraussetzungskonflikten,
  verweigerten Transaktionen oder Transaktionsfehlern, `2` bei ungültigen Argumenten,
  Pfaden oder Konfigurationen.

## Generator-Modi

- Der Benutzer erstellt ein Repository über GitHubs Template-Funktion aus t0003. `new`
  richtet das vorhandene kompatible Projekt optional ein; es erstellt kein Repository.
  Der Einstieg ist lesend und erzeugt denselben Plan wie `plan`. Ohne Modulauswahl wird
  ausschließlich `generator.version` geplant; mit `--module python` wird `python@0.1.0`
  einschließlich Projektchecks und CI geplant. Bei bereits korrekt eingerichtetem Zustand
  gibt es keine Operation und kein Backup. Andere Profile, SDD-Initialisierung und
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
  Attribute und übernommene Git-Umgebungsvariablen werden deaktiviert. Dadurch kann der Status
  insbesondere bei globalen Zeilenendeneinstellungen vom üblichen Git-Status abweichen.
  Repositories mit
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
  - semantische Diffs für Format 3 beziehungsweise Aktionen und Fingerabdrücke für Format 4,
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
  gespeicherte Generator-Version und unbekannte Modullisten sind Konflikte, keine Upgrades.
  `check` erkennt die Metadaten von `python@0.1.0`, prüft aber weder Moduldateien noch
  die zusätzlichen Modulvoraussetzungen; dafür ist `plan --module python` erforderlich.
  Eine SDD-Auswahl wird auf Konsistenz und Versionsformat geprüft; ihre Laufzeit- und
  Integrationskompatibilität bleibt ausdrücklich ungeprüft. `plan` und `new` benötigen Git nicht.

### Mehrdatei-Pläne und Python-Modul

- Die bestehende Engine unterstützt Planformat 4 mit deterministisch sortierten
  `create`- und `modify`-Operationen. Für `--module python` wird es öffentlich von `new`
  und `plan` erzeugt und von `apply` akzeptiert. Ohne Modulauswahl bleibt Format 3 erhalten.
  Format 4 wird ausschließlich mit vertrauenswürdigem, intern bereitgestelltem Operationsinhalt
  erzeugt und angewendet; JSON-Planinhalte werden nicht als auszuführende Dateiinhalte übernommen.
- `python@0.1.0` erstellt `pyproject.toml`, `src/project_app/`, ein ausführbares Beispiel,
  `tests/test_project_app.py` und `docs/PYTHON.md`. Es ergänzt den `unittest`-Aufruf in
  `config/project.yaml` und erweitert `.github/workflows/ci.yml` um Paketinstallation und
  Beispielaufruf. Ein neu einzutragender Testcheck folgt den vorhandenen Checks, deren
  Reihenfolge erhalten bleibt. Die Namen `project-app` und `project_app` sind feste Starter-Namen
  und müssen bei Bedarf vom Projekt angepasst werden.
- Zusätzlich zum weiterhin erforderlichen `template.release: 0.1.0` müssen
  `scripts/check.py`, `scripts/projectcfg.py` und `.github/workflows/ci.yml` den bytegenau
  geprüften t0003-Dateiständen von Commit `6e8363a` entsprechen. Der Check muss konfigurierte
  Prüfungen ausführen, die CI muss Template-Tests auf das Template-Repository beschränken.
  Der ursprüngliche Release-Stand erfüllt Letzteres nicht und wird abgelehnt. Nach Einrichtung
  ist auch der exakt vom Modul erweiterte CI-Stand zulässig. Andere, eventuell gleichwertige
  Varianten werden vorsorglich abgelehnt; es wird kein neues t0003-Release behauptet.
- Modulpläne binden Rohbyte- und Zugriffs-Fingerabdrücke dieser drei Dateien sowie ihrer
  Verzeichnisse als Voraussetzungen ein. `apply` prüft sie bei der Planneuberechnung und
  nach dem Snapshot vor dem ersten Projekt-Schreibzugriff erneut. Einzelne Konflikte liefern
  keine Operationen. Bereits korrekt eingerichtete Module liefern einen No-op; fehlende oder
  inhaltlich veränderte Moduldateien, geänderte CI oder ein fehlender Projektcheck sind
  Konflikte. Nach Einrichtung vergleicht der No-op-Test die Inhalte, nicht frühere
  Zugriffsmetadaten der generierten Dateien.
- Die JSON-Ausgabe enthält Dateipfade, Zustands- und Ergebnis-Hashes sowie Konflikte, aber keine
  Dateiinhalte oder textuellen Diffs der Mehrdatei-Operationen. Ein bestehender fremder
  Dateipfad ist auch bei identischem Inhalt ein Konflikt, solange das Modul nicht eingetragen ist.
- Format 4 bindet Generatorversion, Ausgangskonfiguration, Projekt- und Speicherort,
  Operationen, Verzeichniszustände, Warnungen und Backup-ID an seine Plan-ID. Pro Datei
  sind Aktion, relativer Pfad, Originalhash und Zugriffs-Fingerabdruck beziehungsweise
  ausdrückliche Abwesenheit sowie der Hash des Ergebnisses enthalten. Dateiinhalt und
  Zugriffsmetadaten selbst werden nicht ausgegeben.
- Vor dem ersten Projekt-Schreibzugriff werden alle geplanten Dateien und Verzeichnisse
  erneut geprüft und alle vorhandenen Originaldateien zusammen mit den Abwesenheiten in
  einem geschützten Snapshot mit Manifestformat 3 dokumentiert. Das interne Apply berechnet
  den gesamten Plan aus vertrauenswürdigen Operationen neu; Abweichungen verhindern
  sämtliche Projektänderungen.
- Relative Pfade sind auf portable ASCII-Namen und höchstens 16 Komponenten beziehungsweise
  240 Zeichen begrenzt. Traversal, `.git`, Windows-Gerätenamen, nicht reguläre Dateien,
  Symlinks/Junctions, Hardlinks, erkannte Dateisystemgrenzen sowie doppelte oder
  plattformabhängig kollidierende Pfade sind nicht zulässig. Eine Transaktion umfasst
  höchstens 32 Dateien und 64 Verzeichnisse; pro Datei sind höchstens 1 MiB und für
  Original- beziehungsweise Zielinhalte jeweils insgesamt höchstens 8 MiB zulässig.
  Bind-Mounts auf demselben Dateisystem sind nicht zuverlässig erkennbar.
- Bei Python-Modulpfaden werden auch bereits vorhandene abweichende Schreibweisen in
  übergeordneten Verzeichnissen als Konflikte erkannt, einschließlich Groß-/Kleinschreibung
  und unter Windows ignorierter abschließender Punkte oder Leerzeichen. Das wird vor dem
  ersten Projekt-Schreibzugriff erneut geprüft.
- Neue Dateien werden exklusiv erstellt. Fortschritt und lesbare Teilzustände werden im
  geschützten Backup protokolliert. Das öffentliche `restore` unterstützt Manifestformat 3:
  Es prüft zuerst sämtliche Dateien, Verzeichnisse, Zugriffsmetadaten und Originale.
  Eine fremde Zwischenänderung verhindert die gesamte automatische Rücknahme. Ursprünglich
  fehlende Dateien werden nur bei dokumentiertem Generatorzustand entfernt; neu angelegte
  Verzeichnisse werden nur leer entfernt. Fremde Inhalte in ihnen bleiben erhalten.
- Nach einem abgefangenen Fehler können dokumentierte Teilzustände erneut geprüft und
  zurückgenommen werden. Bei abruptem Abbruch vor der Protokollierung oder wenn diese
  fehlschlägt, kann manuelle Wiederherstellung nötig sein. Auch Restore selbst kann
  teilweise scheitern; ein erneuter Aufruf prüft die verbleibenden Zustände. Ein
  Mehrdatei-Apply oder -Restore ist nicht atomar.
- Für eine zurückzunehmende Datei hat ein vorhandener protokollierter Teilzustand Vorrang
  vor einem älteren Generatorergebnis. Weicht die Datei vom zuletzt protokollierten Zustand
  ab, wird Restore verweigert, auch wenn sie wieder den alten Ergebnisbytes entspricht.
  Ohne Dateiprotokoll kann der bekannte Ergebniszustand als Rückfall dienen; ursprünglich
  fehlende Dateien benötigen weiterhin einen dokumentierten Generatorzustand.
- Format-3-Pläne bleiben unter den bisherigen Versions- und Zustandsbedingungen ausführbar;
  Manifestformat-2-Backups und bestehende Manifestformat-3-Backups bleiben wiederherstellbar.
  Bereits gespeicherte Python-Pläne, die den Testcheck vor vorhandenen Checks einfügen würden,
  werden als veraltet abgelehnt und müssen neu erstellt werden. Plan- und Backup-IDs sind
  Integritätsprüfungen, keine Authentisierung. Insbesondere sind fremde Zustände mit exakt
  denselben Bytes und Zugriffsmetadaten nicht von Generatorzuständen unterscheidbar.

### Freigegebener Vertrag für `typescript@0.1.0` (noch nicht öffentlich ausführbar)

- Das Modul ist fest im Generator vorgesehen. Es verwendet ausschließlich die vorhandene
  Format-4-Mehrdatei-Engine. Dieser PR enthält Vertrag und paketierte Starterdateien, aber
  weder `--module typescript` noch einen TypeScript-Apply-Pfad. Es gibt keine zweite
  Schreib-Engine und kein allgemeines Plugin-System.
- Die festen Moduldateien liegen im Zielprojekt unter `typescript/`: `.gitignore`,
  `package.json`, `package-lock.json`, `tsconfig.json`, `src/app.ts`, `src/main.ts` und
  `test/app.test.mjs`; hinzu kommt `docs/TYPESCRIPT.md`. Node.js 24, TypeScript mit
  `strict` und `NodeNext`, sowie `node:test` sind die erste geprüfte Laufzeitkombination.
  Entwicklungsabhängigkeiten sind exakt gepinnt und im Lockfile mit Integritätshashes
  gebunden. `node_modules/` und `dist/` bleiben lokale, ignorierte Ergebnisse.
- Die spätere Planung setzt weiterhin `template.release: 0.1.0` und bytegenau nachgewiesene
  t0003-Fähigkeiten für `scripts/check.py`, `scripts/projectcfg.py` und die bestehende CI
  voraus. Der ursprüngliche Release-Commit ohne passende CI wird nicht still zugelassen.
  Für die CI sind nur explizit geprüfte Basis-, Python-, TypeScript- und kombinierte
  Dateistände zulässig. Das Modul ergänzt einen festen `verify`-Check, ohne bestehende
  Checks umzuordnen. Die bestehende CI erhält `npm ci --ignore-scripts` vor dem
  Projektcheck; Plan und Apply führen niemals npm oder andere Projektbefehle aus.
- `generator.modules` erlaubt nach Umsetzung nur die bekannten Einträge
  `python@0.1.0` und `typescript@0.1.0`, jeweils höchstens einmal. Unbekannte Versionen,
  doppelte Einträge und abweichende Moduldateien sind Konflikte. Die Module werden
  einzeln geplant und angewandt; beide Reihenfolgen müssen zum selben unterstützten
  Doppelmodul-Zustand führen. Es gibt keinen gemeinsamen Zwei-Modul-Apply.
- Ein vorhandener fremder Modulpfad wird nicht überschrieben, auch bei identischem Inhalt.
  Plan und Apply binden die Voraussetzungen, Datei- und Verzeichniszustände sowie
  CI-/Konfigurationsänderungen wie beim Python-Modul an Fingerabdrücke und Plan-ID.
  Ein vollständig unverändertes, eingetragenes Modul ergibt einen No-op ohne Backup;
  fehlende oder geänderte Moduldateien, Check oder CI ergeben einen Konflikt.
- `restore` verwendet unverändert das geschützte Format-3-Mehrdatei-Manifest und prüft
  fremde Zwischenänderungen vor jeder Rücknahme. Nach Installation beider Module ist
  in umgekehrter Apply-Reihenfolge zurückzunehmen. Der Versuch, zuerst das ältere
  Modul-Backup zurückzunehmen, wird wegen des geänderten Konfigurations-/CI-Zustands
  verweigert. Backups werden nicht automatisch gelöscht.

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
  muss ein Teilzustand manuell aus dem Snapshot wiederhergestellt werden. Auch bei
  Manifestformat 2 hat ein vorhandenes Teilzustandsprotokoll Vorrang vor den älteren
  Generator-Ergebnisbytes.
- Die Zielzustandsprüfung nach `apply` und `restore` umfasst Dateiinhalt und
  Zugriffs-Fingerabdruck. Ein fehlgeschlagenes `apply` nennt die Backup-ID, sofern die
  Transaktion bereits begonnen wurde. Ist der Zielzustand weder Original, berechnetes
  Ergebnis noch protokollierter Teilzustand, ist nur manuelle Wiederherstellung zulässig.
  Gleiches gilt bei fremden Zwischenänderungen, geänderten Berechtigungen oder beschädigtem Backup.
- Bei Manifestformat 2 ändert `restore` nur die geplante Datei, falls sie dem Generatorergebnis oder einem
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
