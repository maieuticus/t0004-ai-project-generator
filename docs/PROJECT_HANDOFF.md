# Projektübergabe

Flüchtiger Arbeitsstand für den Wechsel zwischen Agenten und Umgebungen. Er ändert keine
Architekturentscheidungen (diese stehen in [DV_KONZEPT.md](DV_KONZEPT.md) und den Specs). Keine
Secrets, Tokens oder Zugangsdaten eintragen. Git hat bei Widersprüchen Vorrang.

## Aktueller Stand

- Stand: 2026-10-31
- Branch: `feat/t0003-integration-tests`, ausgehend von `main` / `c0e5587` (PR #9 gemergt).
- Aktive Aufgabe: Integration von t0003 und dem installierten Python-Generator nachweisen.
- Erledigt:
  - Acht Integrationstests verwenden die installierte CLI und echte Git-Quellstände:
    kompatibler t0003-Commit `6e8363a7ac7d99220d743eea077dcd5cefda9042` sowie
    ursprünglicher Release-Commit `964de8538d19cefcb483faff38f10124615a9783`.
  - Plan, bestätigtes Apply, Python-Anwendung und -Tests, Projektcheck, Snapshot, No-op und
    bytegenaues Restore sowie Konflikte und Format 3 werden geprüft. Die vorhandene
    Linux-/Windows-CI führt die Tests aus; ein lokaler Git-Mirror ist optional.
  - PR #9 ist gemergt. Der kompatible t0003-Entwicklungsstand ist kein neues Release;
    `migrate` bleibt eine lesende Bestandsanalyse.
- Offen:
  - CI des PR-Kopfstands und menschliches Review prüfen; nicht automatisch mergen.
  - Die tatsächliche GitHub-Erstellung über „Use this template“ ist nicht automatisiert
    und braucht eine separate manuelle Abnahme. Abschließendes `verify`, separate Releases
    und die vollständige Gate-A-Praxismatrix bleiben spätere Etappen.
- Blocker: Windows nur über CI prüfbar; tatsächlichen CI- und PR-Stand abfragen.
- Prüfergebnisse: Unter Linux acht Integrationstests mit öffentlicher Quelle und lokalem
  Mirror, 135 Generator-Tests (6 plattformbedingt übersprungen), 16 Basistests und
  Projektcheck erfolgreich. Windows ist lokal nicht geprüft.
- Synchronisierung: Git- und PR-Stand prüfen; Merge ist nicht beauftragt.

## Nächster Schritt

CI des Integrationstest-PR-Kopfstands prüfen und das Review-Gate durch den Menschen durchführen.

## Entscheidungen und Quellen

Die verbindliche Gate-A-Matrix und PR-Reihenfolge stehen in
[DV_KONZEPT.md](DV_KONZEPT.md). Der Schnittstellenvertrag einschließlich Analysegrenzen steht in
[GENERATOR_CONTRACT.md](GENERATOR_CONTRACT.md).

## Probleme

Apply und Restore setzen exklusiven Projektzugriff während des jeweiligen Aufrufs voraus.
Nach abruptem Abbruch oder fehlgeschlagener Protokollierung kann ein Teilzustand manuelle
Wiederherstellung erfordern. Die lesende Migrationsanalyse setzt ein während ihres Aufrufs
unverändertes Quellprojekt voraus.
