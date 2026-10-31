# Projektübergabe

Flüchtiger Arbeitsstand für den Wechsel zwischen Agenten und Umgebungen. Er ändert keine
Architekturentscheidungen (diese stehen in [DV_KONZEPT.md](DV_KONZEPT.md) und den Specs). Keine
Secrets, Tokens oder Zugangsdaten eintragen. Git hat bei Widersprüchen Vorrang.

## Aktueller Stand

- Stand: 2026-10-31
- Branch: `feat/read-only-migrate`, ausgehend von `main` / `f4b4654` (PR #6 gemergt).
- Aktive Aufgabe: Lesende Bestandsanalyse und Strategievergleich für `migrate`.
- Erledigt:
  - Safety-Core, bestätigtes Apply/Restore und minimaler `new`-Einstieg sind gemergt.
  - `migrate` liefert einen versionierten Analysebericht statt eines Apply-Plans und unterstützt
    Projekte ohne t0003-Metadaten. Eine schreibende Migration ist nicht implementiert.
  - Die Analyse begrenzt Rekursion, Dateimengen und Git-Ressourcen, gibt nur feste Kategorien
    und Zählwerte aus und nennt nicht geprüfte Bereiche und offene Entscheidungen.
  - Der bestehende GitHub-Actions-Workflow führt den neuen Einstieg auf Linux und Windows aus.
- Offen:
  - CI des PR-Kopfstands und menschliches PR-Review; den PR nicht automatisch mergen.
  - Weitergehende Einrichtung, technologieabhängiges `verify`, Integration und Releases bleiben
    separate Etappen; t0003 bleibt unverändert.
- Blocker: keine bekannten; CI- und PR-Stand über Git prüfen.
- Prüfergebnisse: Lokal unter Linux 80 Generator-Tests (5 Windows-Tests übersprungen), 16
  Basistests und `python scripts/check.py` erfolgreich. Linux-/Windows-CI des PR-Kopfstands
  gesondert prüfen.
- Nicht synchronisierte Änderungen: per `git status` und PR-Stand prüfen.

## Nächster Schritt

CI des PR-Kopfstands prüfen und das Review-Gate durch den Menschen durchführen.

## Entscheidungen und Quellen

Die verbindliche Gate-A-Matrix und PR-Reihenfolge stehen in
[DV_KONZEPT.md](DV_KONZEPT.md). Der Schnittstellenvertrag einschließlich Analysegrenzen steht in
[GENERATOR_CONTRACT.md](GENERATOR_CONTRACT.md).

## Probleme

Die Analyse setzt ein während des Aufrufs unverändertes Quellprojekt voraus. Lesebedingte
Zugriffszeiten und Python-Bytecode sind im Generator-Vertrag beschrieben.
