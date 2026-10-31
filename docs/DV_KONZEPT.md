# DV-Konzept

Verbindliche Projektbeschreibung für das Generator-Repository. Architektur- und
Verhaltensentscheidungen gelten erst nach Freigabe.

## Status dieses Dokuments

Gate A freigegeben: Übernahmematrix, Schnittstellenvertrag und PR-Reihenfolge sind
verbindlich. Der vorgezogene Safety-Core und sein bestätigtes Apply/Restore für eine
Metadatenoperation decken nur Teil-Etappen ab; die vollständigen Generator-Modi sind offen.

## Projektziel

Python-Generator als eigenständiges Werkzeug bereitstellen, der Projekte aus einer stabilen
Template-Basis nachvollziehbar erweitert. Standardmodus ist `dry-run`; schreibende Änderungen
erfolgen erst nach expliziter Freigabe.

## Anforderungen und Erfolgskriterien

- CLI mit klaren Subcommands, Exitcodes und verständlichen Fehlermeldungen.
- `dry-run` zeigt geplante Änderungen inkl. Konflikten.
- `apply` führt Änderungen nur nach bestätigter Freigabe aus.
- Backups und sicherer Rollback für bestehende Dateien.
- Tests und CI für Linux, Windows sowie Codespaces-nahe Abläufe.

## Architektur

Modularer Python-Kern mit optionalen Profilen/Modulen. Vertrag und Sicherheitsregeln stehen in
`docs/GENERATOR_CONTRACT.md`; Detailentscheidungen folgen über den SDD-Prozess.

### Gate-A-Übernahmematrix

| Bereich | Übernahmeentscheidung | Verbindliche Ausprägung für t0004 |
|---|---|---|
| Template-Basis | übernehmen | t0003 bleibt die neutrale, versionierte Projektbasis. |
| Neuprojekt-Generator | separat umsetzen | Der Modus `new` erzeugt aus einer t0003-Basis ein neues Zielprojekt; `dry-run` bleibt Standard. |
| Bestandsmigration | separat umsetzen | Der Modus `migrate` beginnt mit einer ausschließlich lesenden Bestandsanalyse von Dokumenten, Code, Assets, Konfiguration und Tests; Secrets werden weder übernommen noch ausgegeben. |
| Migrationsentscheidung | vergleichen, nicht vorwegnehmen | `migrate` vergleicht nachvollziehbar (A) neues t0003-Projekt mit selektivem Import und (B) In-place-Update. Er weist Risiken sowie Arbeits- und Tokenaufwand aus; die Umsetzung erfolgt erst nach Freigabe. |
| CI | t0003-Basis erhalten | GitHub Actions aus t0003 bleibt die neutrale CI-Basis. t0004 ergänzt bei Bedarf technologieabhängige Jobs innerhalb dieser Struktur, nicht als konkurrierende CI. |
| Releases | getrennt versionieren | t0003 und t0004 erhalten unabhängige stabile Releases und Changelogs. Kompatibilität wird über eine explizite Integrationsprüfung nachgewiesen. |
| Erstes Release | zurückstellen | Keycloak, Colyseus und das API-Service-Rezept gehören nicht zum ersten t0004-Release. |

### Verbindliche PR-Reihenfolge

| Etappe | PR-Inhalt | Abnahmekriterium |
|---|---|---|
| 1 | Gate-A-Dokumentation | Übernahmematrix, Schnittstellenvertrag und diese PR-Reihenfolge sind geprüft. |
| 2 | Modus `new` | `new` erfüllt Dry-run-, Freigabe-, Backup- und Rollback-Vertrag auf einer t0003-Basis. |
| 3 | Modus `migrate` | Eine read-only-Bestandsanalyse sowie der Vergleich von selektivem Import und In-place-Update liegen vor; schreibende Migrationen benötigen eine Freigabe. |
| 4 | Technologieabhängige CI-Ergänzungen | Zusätzliche Jobs erweitern die bestehende GitHub-Actions-Struktur, ohne die neutrale t0003-Basis zu ersetzen. |
| 5 | `verify`, Releases und Integration | `verify` schließt die Umsetzung ab; stabile Releases für t0003 und t0004 bleiben getrennt, und die Integration sowie die vier Praxistests sind nachgewiesen. |

Die vier verpflichtenden Praxistests der abschließenden Etappe sind:

1. `new` unter Linux.
2. `new` unter Windows.
3. `migrate` unter Linux, einschließlich read-only-Bestandsanalyse und Strategievergleich.
4. `migrate` unter Windows, einschließlich read-only-Bestandsanalyse und Strategievergleich.

Codespaces bleibt ein Plattformziel des Generatorvertrags und wird zusätzlich zur Vierer-Matrix
geprüft, sobald die technische Ausführung dafür bereitsteht.

Der Safety-Core und das bestätigte Apply/Restore für `generator.version` sind vorgezogene
Teil-Etappen zu `new`. Sie implementieren weder den Modus `new` noch dessen vollständigen
Freigabe-, Backup- und Rollback-Vertrag. Die oben genannten Abnahmekriterien bleiben offen.

## Entwicklung und Betrieb

Primär Python-basierte Entwicklung und Prüfung. SDD-Werkzeug (Spec Kit/OpenSpec) wird wie im
Template nur nach expliziter Auswahl eingerichtet.

## Entscheidungen

| Datum | Entscheidung | Freigabe durch |
|---|---|---|
| 2026-10-30 | `t0004` als separates Generator-Repository auf Basis von `t0003 v0.1.0` starten | Nutzer |
| 2026-10-30 | Gate-A-Übernahmematrix und PR-Reihenfolge einschließlich `new`, `migrate`, CI-Ergänzungen, `verify` und getrennter Releases freigegeben | Nutzer |
| 2026-10-30 | Keycloak, Colyseus und API-Service-Rezept aus erstem Release zurückgestellt | Nutzer |
