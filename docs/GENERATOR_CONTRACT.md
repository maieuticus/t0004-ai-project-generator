# Generator Contract

Dieser Vertrag definiert die Mindestanforderungen für die Generator-CLI in `t0004`.

## CLI-Grundsätze

- Die Referenzimplementierung ist eine Python-CLI.
- Plattformziele: Linux, Windows, GitHub Codespaces.
- Jeder Fehler liefert einen klaren Exitcode und eine verwertbare Meldung.
- Der installierbare Einstiegspunkt lautet `t0004-generator`. Der Safety-Core verwendet:
  `t0004-generator version`, `t0004-generator check [ZIELPROJEKT]` und
  `t0004-generator plan [ZIELPROJEKT]`. `--json` liefert bei `check` und `plan`
  eine maschinenlesbare, plattformneutrale Darstellung.
- Exitcodes: `0` erfolgreich, `1` bei Kompatibilitäts- oder Voraussetzungskonflikten,
  `2` bei ungültigen Argumenten, Pfaden oder Konfigurationen.

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
- Die Safety-Core-Etappe implementiert ausschließlich `version`, `check` und den
  rein lesenden `plan`; sie implementiert weder `apply` noch Backups oder Rollback.
- `plan` berechnet Plan-ID und Ausgangsfingerabdruck deterministisch aus der
  validierten kanonischen Konfiguration. Der Ausgangsfingerabdruck ist SHA-256 über die
  Originalbytes von `config/project.yaml`, nicht über das gesamte Projekt. Die Plan-ID ist
  SHA-256 über die versionierte Plandarstellung einschließlich Fingerabdruck, Konflikten und
  Operationen. Die gleichen Eingaben einschließlich Zeilenenden ergeben plattformübergreifend
  dieselbe ID; eine andere Konfiguration oder ein anderer Konflikt ändert die ID.
- Der Plan zeigt nur eine hypothetische Änderung von `generator.version` als **semantischen
  Diff** (kein ausführbarer Patch); andere Inhalte der Konfiguration werden nicht ausgegeben.
  Er belegt weder eine tatsächliche Generatorausführung noch eine Freigabe und ist keine
  Grundlage für automatisches `apply`. Bei Konflikten werden keine Operationen vorgeschlagen.
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

- Vor Änderungen an bestehenden Dateien werden Backups erstellt.
- Keine stillen Überschreibungen bei Konflikten.
- Bei Fehlern muss ein sicherer Rollback ohne Verlust fremder Zwischenarbeit möglich sein.
- Keine dynamische Ausführung beliebiger externer Skripte ohne Prüfung.

## Nachvollziehbarkeit

- Generator-Version und gewählte Module/Profiles werden in Zielprojekten dokumentiert.
- Änderungen werden in Tests und Changelog nachvollziehbar abgesichert.
- `verify` prüft abschließend die Integrationskompatibilität von t0003 und t0004 sowie die
  verpflichtenden Praxistests für `new` und `migrate` unter Linux und Windows.
- Stabile Releases von t0003 und t0004 werden getrennt versioniert und veröffentlicht.
