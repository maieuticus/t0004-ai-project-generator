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
  - Unter Windows bleiben die Sicherheitsmetadaten durch direktes Schreiben erhalten;
    zusätzliche Streams, Hardlinks und nicht unterstützte Attribute werden abgelehnt.
    Ein unterbrochener Schreibvorgang kann manuelle Wiederherstellung erfordern.
- Offen:
  - CI des Feature-Branches unter Linux und Windows und menschliches PR-Review.
  - `new`, read-only-`migrate`, technologieabhängiges `verify`, Integration und Releases
    bleiben separate Etappen; t0003 bleibt unverändert.
- Blocker: keine bekannten; CI des aktuellen PR-Commitstands prüfen.
- Letzte Prüfergebnisse: 16 Baseline-Tests und 37 Generator-Tests lokal erfolgreich,
  vier Windows-spezifische Tests lokal übersprungen. Für Commit `ca43db3` waren Linux
  und ein Windows-CI-Job erfolgreich; einen weiteren Windows-Job und spätere Commits prüfen.
- Nicht synchronisierte Änderungen: per `git status` und PR-Stand prüfen.

## Nächster Schritt

CI des aktuellen PR-Commitstands prüfen und das Review-Gate durch den Menschen durchführen.

## Entscheidungen und Quellen

Die verbindliche Gate-A-Matrix und PR-Reihenfolge stehen in
[DV_KONZEPT.md](DV_KONZEPT.md). Der Schnittstellenvertrag ergänzt sie in
[GENERATOR_CONTRACT.md](GENERATOR_CONTRACT.md).

## Probleme

Keine über die noch ausstehenden Prüfungen hinaus bekannt.
