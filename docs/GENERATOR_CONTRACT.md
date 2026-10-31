# Generator Contract

Dieser Vertrag definiert die Mindestanforderungen für die Generator-CLI in `t0004`.

## CLI-Grundsätze

- Die Referenzimplementierung ist eine Python-CLI.
- Plattformziele: Linux, Windows, GitHub Codespaces.
- Jeder Fehler liefert einen klaren Exitcode und eine verwertbare Meldung.
- Der installierbare Einstiegspunkt lautet `t0004-generator`. Der Safety-Core verwendet:
  `t0004-generator version`, `t0004-generator check [ZIELPROJEKT]` und
  `t0004-generator plan [ZIELPROJEKT]`, `t0004-generator apply [ZIELPROJEKT] --plan DATEI
  --confirm PLAN-ID` und `t0004-generator restore [ZIELPROJEKT] --backup BACKUP-ID`.
  `--json` liefert bei `check` und `plan` eine maschinenlesbare Darstellung.
- Exitcodes: `0` erfolgreich, `1` bei Kompatibilitäts- oder Voraussetzungskonflikten,
  verweigerten Transaktionen oder Transaktionsfehlern, `2` bei ungültigen Argumenten,
  Pfaden oder Konfigurationen.

## Generator-Modi

- `new` erstellt ein neues Zielprojekt aus einer kompatiblen t0003-Basis.
- `migrate` prüft ein bestehendes Projekt zunächst ausschließlich lesend. Die Bestandsanalyse
  umfasst Dokumente, Code, Assets, Konfiguration und Tests; Secrets werden weder übernommen noch
  ausgegeben.
- Für `migrate` sind zwei Strategien verbindlich vergleichbar auszuweisen:
  - neues t0003-Projekt mit selektivem Import, bevorzugt für kleine Altprojekte;
  - In-place-Update, oft geeignet für etablierte Projekte.
- Der Vergleich benennt Risiken sowie Arbeits- und Tokenaufwand. Eine schreibende Migration setzt
  die ausdrückliche Freigabe der gewählten Strategie voraus.

## Ausführungsmodi

- `dry-run` ist der Standard und zeigt nur den Plan:
  - betroffene Dateien,
  - Diffs/Änderungen,
  - Konflikte und Abhängigkeiten.
- Schreibender Modus (`apply`) ist explizit und setzt vorherige Freigabe voraus.
- Planformat 2 beschreibt ausschließlich die tatsächliche Änderung von `generator.version`
  in `config/project.yaml`, einschließlich semantischem Diff, SHA-256 der Original- und
  Zielbytes sowie Fingerabdruck der Zugriffsmetadaten. Der Plan benennt auch das vorab
  nicht vorhandene Backup-Verzeichnis, Original, Manifest und temporäre Datei. Andere
  Konfigurationsinhalte werden nicht ausgegeben. Bei Konflikten oder bereits gesetzter
  aktueller Version gibt es keine Operation und kein Backup.
- Die Plan-ID ist SHA-256 über die kanonische versionierte Darstellung der Operation,
  Konflikte, Warnungen und Backup-Pfade. Die gleichen vollständigen Eingaben ergeben die
  gleiche ID; Dateimodus, Besitzer/Gruppe und erweiterte Attribute unter POSIX bzw. Modus und
  Sicherheitsdeskriptor unter Windows gehen in den Zugriffs-Fingerabdruck ein. Unterschiedliche
  Plattform-Metadaten oder bereits vorhandene Backup-Pfade können die ID ändern.
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
  Integrationskompatibilität bleibt ausdrücklich ungeprüft. `plan` benötigt Git nicht.

## Sicherheit und Änderungsstrategie

- Für jeden Aufruf von `apply` oder `restore` muss das Zielprojekt exklusiv genutzt werden:
  andere Prozesse dürfen es während des Aufrufs nicht verändern. Portable Dateisperren
  können nicht kooperierende Programme nicht zuverlässig ausschließen. Zwischen Aufrufen
  werden Inhalts- und Zugriffsänderungen erkannt; bei Konflikten erfolgt kein Restore.
- Vor der Änderung wird unter `.t0004-backup-<ID>/` ein Snapshot der vollständigen
  Originalbytes und ein Manifest angelegt. Unter POSIX ist das Verzeichnis auf den
  ausführenden Benutzer beschränkt (0700); unter Windows erhält es eine geschützte DACL
  für diesen Benutzer und SYSTEM. Administratoren/root und Prozesse desselben Benutzers
  sind nicht ausgeschlossen. Das Backup enthält möglicherweise Secrets und ist nicht
  automatisch Git-ignoriert.
- Snapshotdateien werden vor der Ersetzung synchronisiert, unter POSIX zusätzlich die
  Verzeichniseinträge. Eine Wiederherstellbarkeit nach Stromausfall oder Dateisystemfehlern
  kann insbesondere unter Windows nicht garantiert werden.
- Die Zielzustandsprüfung nach `apply` und `restore` umfasst Dateiinhalt und
  Zugriffs-Fingerabdruck. Ein fehlgeschlagenes `apply` nennt die Backup-ID, sofern die
  Transaktion bereits begonnen wurde. Ist der Zielzustand weder Original noch das
  berechnete Ergebnis, ist nur eine manuelle Wiederherstellung zulässig. Gleiches gilt
  bei fremden Zwischenänderungen, geänderten Berechtigungen oder beschädigtem Backup.
- `restore` ändert nur die geplante Datei, falls sie dem Generatorergebnis entspricht;
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
