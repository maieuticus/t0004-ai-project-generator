# Generator Contract

Dieser Vertrag definiert die Mindestanforderungen für die Generator-CLI in `t0004`.

## CLI-Grundsätze

- Die Referenzimplementierung ist eine Python-CLI.
- Plattformziele: Linux, Windows, GitHub Codespaces.
- Jeder Fehler liefert einen klaren Exitcode und eine verwertbare Meldung.

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
