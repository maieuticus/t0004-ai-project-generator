# Projektübergabe

Flüchtiger Arbeitsstand für den Wechsel zwischen Agenten und Umgebungen. Er ändert keine
Architekturentscheidungen (diese stehen in [DV_KONZEPT.md](DV_KONZEPT.md) und den Specs). Keine
Secrets, Tokens oder Zugangsdaten eintragen. Git hat bei Widersprüchen Vorrang.

## Aktueller Stand

- Stand: 2026-10-31
- Branch: `feat/python-technology-module`, ausgehend von `main` / `5799be1` (PR #8 gemergt).
- Aktive Aufgabe: PR #9 unabhängig prüfen, bestätigte Fehler beheben und CI des Kopfstands prüfen.
- Erledigt:
  - `python@0.1.0` erstellt ein Python-Starterpaket, Beispiel, Tests und Dokumentation;
    es erweitert Projektchecks und die vorhandene GitHub Action.
  - `new` und `plan --module python` erstellen Format-4-Pläne; bestätigtes Apply und
    Restore verwenden die vorhandene Mehrdatei-Engine. Moduldateien und t0003-Voraussetzungen
    werden auf Konflikte geprüft; ein vollständig unveränderter Modulzustand ist ein No-op.
  - `template.release: 0.1.0` bleibt erforderlich; zusätzlich werden die geprüften Check- und
    CI-Dateistände von t0003-Commit `6e8363a` vorausgesetzt und an den Plan gebunden.
    Der ursprüngliche Release-Stand wird nachvollziehbar abgelehnt. Kein t0003-Release.
  - Die Teilstände `b9efea3`, `d6cd91d` und `5b7a536` sind auf dem Feature-Branch gesichert.
  - PR #9 ist offen. Die unabhängige Prüfung korrigiert die Reihenfolge bestehender Checks
    und lehnt plattformabhängige Kollisionen mit vorhandenen Pfaden ab.
  - `migrate` bleibt eine lesende Bestandsanalyse; Format-3-Pläne und ältere Backups bleiben
    unter ihren bisherigen Bedingungen unterstützt.
- Offen:
  - CI des endgültigen PR-Kopfstands und menschliches Review prüfen; nicht automatisch mergen.
  - Abschließendes `verify`, separate Releases und die vollständige Gate-A-Praxismatrix
    bleiben spätere Etappen; t0003 bleibt unverändert.
- Blocker: keine bekannten; den tatsächlichen CI- und Git-Stand prüfen.
- Prüfergebnisse: Unter Linux 130 Generator-Tests (6 plattformbedingt übersprungen),
  16 Basistests, Projektcheck sowie Paketinstallation erfolgreich. Eine temporäre Fixture
  aus dem echten t0003-Commit `6e8363a`
  bestätigte Plan, Apply, Projektcheck, No-op und bytegenaues Restore aller 32 Originaldateien.
  Windows ist lokal nicht geprüft; den CI-Stand des tatsächlichen PR-Kopfstands abfragen.
- Synchronisierung: die Sicherung erfolgt abschnittsweise auf dem Feature-Branch; tatsächlichen
  Git- und PR-Stand prüfen.

## Nächster Schritt

CI des endgültigen PR-Kopfstands prüfen und das Review-Gate durch den Menschen durchführen.

## Entscheidungen und Quellen

Die verbindliche Gate-A-Matrix und PR-Reihenfolge stehen in
[DV_KONZEPT.md](DV_KONZEPT.md). Der Schnittstellenvertrag einschließlich Analysegrenzen steht in
[GENERATOR_CONTRACT.md](GENERATOR_CONTRACT.md).

## Probleme

Apply und Restore setzen exklusiven Projektzugriff während des jeweiligen Aufrufs voraus.
Nach abruptem Abbruch oder fehlgeschlagener Protokollierung kann ein Teilzustand manuelle
Wiederherstellung erfordern. Die lesende Migrationsanalyse setzt ein während ihres Aufrufs
unverändertes Quellprojekt voraus.
