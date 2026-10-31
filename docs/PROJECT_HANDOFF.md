# Projektübergabe

Flüchtiger Arbeitsstand für den Wechsel zwischen Agenten und Umgebungen. Er ändert keine
Architekturentscheidungen (diese stehen in [DV_KONZEPT.md](DV_KONZEPT.md) und den Specs). Keine
Secrets, Tokens oder Zugangsdaten eintragen. Git hat bei Widersprüchen Vorrang.

## Aktueller Stand

- Stand: 2026-10-31
- Branch: `feat/minimal-new-entry`, ausgehend von `main` / `b24fec3` (PR #5 gemergt).
- Aktive Aufgabe: Minimaler `new`-Einstieg für ein vorhandenes t0003-Projekt zu Issue #2.
- Erledigt:
  - Safety-Core und bestätigtes Apply/Restore sind mit PR #5 gemergt; die CI von `main`
    auf `b24fec3` war unter Linux und Windows erfolgreich.
  - Die Architekturprüfung ist freigegeben: GitHub erstellt das Repository aus t0003;
    `new` plant ausschließlich die vorhandene Metadatenoperation.
  - `new` liefert denselben lesenden Plan wie `plan`; Apply, Snapshot und Restore bleiben
    unverändert und die bereits aktuelle Generator-Version ist ein No-op.
  - Planformat 3 bindet die Metadatenänderung und Backup-Pfade an Projekt und lokalen Speicher.
  - Apply verlangt einen unveränderten JSON-Plan und dessen bestätigte ID; Snapshot und
    Restore prüfen Inhalt und Zugriffsmetadaten und verweigern fremde Änderungen.
  - Für die Dauer jedes `apply`-/`restore`-Aufrufs ist exklusiver Projektzugriff vereinbart.
    Geschützte lokale Backups liegen außerhalb erkannter Git-Arbeitsverzeichnisse und
    können Secrets enthalten; die Codespaces-Standardbasis übersteht Container-Rebuilds.
  - Erfasste Teilzustände nach Schreibfehlern sind konfliktbewusst wiederherstellbar.
    Bei abruptem Abbruch vor ihrer Erfassung kann manuelle Wiederherstellung nötig sein.
- Offen:
  - Menschliches PR-Review; CI-Ergebnisse des aktuellen PR-Kopfstands prüfen.
  - Weitergehende Einrichtung, read-only-`migrate`, technologieabhängiges `verify`,
    Integration und Releases bleiben separate Etappen; t0003 bleibt unverändert.
- Blocker: keine bekannten; CI des aktuellen PR-Commitstands prüfen.
- Letzte Prüfergebnisse: Lokal unter Linux 63 Generator-Tests (5 Windows-Tests übersprungen),
  16 Baseline-Tests und `python scripts/check.py` erfolgreich. CI von `main` auf `b24fec3`
  erfolgreich; CI des aktuellen PR-Kopfstands gesondert prüfen.
- Nicht synchronisierte Änderungen: per `git status` und PR-Stand prüfen.

## Nächster Schritt

CI des aktuellen PR-Commitstands prüfen und das Review-Gate durch den Menschen durchführen.

## Entscheidungen und Quellen

Die verbindliche Gate-A-Matrix und PR-Reihenfolge stehen in
[DV_KONZEPT.md](DV_KONZEPT.md). Der Schnittstellenvertrag ergänzt sie in
[GENERATOR_CONTRACT.md](GENERATOR_CONTRACT.md).

## Probleme

Keine über die noch ausstehenden Prüfungen hinaus bekannt.
