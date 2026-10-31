# Projektübergabe

Flüchtiger Arbeitsstand für den Wechsel zwischen Agenten und Umgebungen. Er ändert keine
Architekturentscheidungen (diese stehen in [DV_KONZEPT.md](DV_KONZEPT.md) und den Specs). Keine
Secrets, Tokens oder Zugangsdaten eintragen. Git hat bei Widersprüchen Vorrang.

## Aktueller Stand

- Stand: 2026-10-31
- Branch: `feat/safe-apply-snapshot-restore`, ausgehend von `main` / `3168e4d` (PR #4 gemergt).
- Aktive Aufgabe: Bestätigtes Apply und Restore der Metadatenoperation zu Issue #2.
- Erledigt:
  - Safety-Core und Gate-A-Plan sind gemergt; die Linux- und Windows-CI von PR #4 war erfolgreich.
  - Planformat 2 beschreibt die Metadatenänderung und die vorab nicht vorhandenen Backup-Pfade.
  - Apply verlangt einen unveränderten JSON-Plan und dessen bestätigte ID; Snapshot und
    Restore prüfen Inhalt und Zugriffsmetadaten und verweigern fremde Änderungen.
  - Für die Dauer jedes `apply`-/`restore`-Aufrufs ist exklusiver Projektzugriff mit dem
    Nutzer vereinbart. Backups können Secrets enthalten und werden nicht automatisch ignoriert.
- Offen:
  - CI des Feature-Branches unter Linux und Windows und menschliches PR-Review.
  - `new`, read-only-`migrate`, technologieabhängiges `verify`, Integration und Releases
    bleiben separate Etappen; t0003 bleibt unverändert.
- Blocker: Windows-CI meldete abweichende Zugriffsmetadaten nach Dateiersetzung; die
  Ursache und der plattformübergreifende Nachweis werden untersucht.
- Letzte Prüfergebnisse: 16 Baseline-Tests und 36 Generator-Tests lokal erfolgreich,
  ein Windows-Test lokal übersprungen; Linux-CI erfolgreich, Windows-CI fehlgeschlagen.
- Nicht synchronisierte Änderungen: per `git status` und PR-Stand prüfen.

## Nächster Schritt

CI des aktuellen PR-Commitstands prüfen und das Review-Gate durch den Menschen durchführen.

## Entscheidungen und Quellen

Die verbindliche Gate-A-Matrix und PR-Reihenfolge stehen in
[DV_KONZEPT.md](DV_KONZEPT.md). Der Schnittstellenvertrag ergänzt sie in
[GENERATOR_CONTRACT.md](GENERATOR_CONTRACT.md).

## Probleme

Windows-Dateiersetzung und Zugriffsmetadaten müssen vor dem Review erfolgreich geprüft sein.
