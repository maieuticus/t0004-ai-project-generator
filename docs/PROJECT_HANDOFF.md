# Projektübergabe

Flüchtiger Arbeitsstand für den Wechsel zwischen Agenten und Umgebungen. Er ändert keine
Architekturentscheidungen (diese stehen in [DV_KONZEPT.md](DV_KONZEPT.md) und den Specs). Keine
Secrets, Tokens oder Zugangsdaten eintragen. Git hat bei Widersprüchen Vorrang.

## Aktueller Stand

- Stand: 2026-10-31
- Branch: `feat/multi-file-operations`, ausgehend von `main` / `f7d32f9` (PR #7 gemergt).
- Aktive Aufgabe: PR A für interne sichere Mehrdatei-Operationen.
- Erledigt:
  - Safety-Core, bestätigtes Apply/Restore und minimaler `new`-Einstieg sind gemergt.
  - `migrate` liefert einen versionierten Analysebericht statt eines Apply-Plans und unterstützt
    Projekte ohne t0003-Metadaten. Eine schreibende Migration ist nicht implementiert.
  - Die bestehende Engine unterstützt intern Format-4-Pläne und Manifestformat 3 für
    mehrere Create-/Modify-Operationen, geschützte Snapshots und konfliktbewusstes Restore.
    Öffentliche `new`-/`plan`-Befehle bleiben bei Format 3; ein Technologiemodul fehlt.
  - Format-3-Pläne und Manifestformat-2-Backups bleiben unter den bisherigen Bedingungen
    unterstützt. Mehrdatei-Änderungen sind nicht atomar; Einzelheiten und Grenzen stehen
    im Generator-Vertrag.
- Offen:
  - Linux-/Windows-CI und menschliches Review des PR-Kopfstands; nicht automatisch mergen.
  - Python-Modul, technologieabhängiges `verify`, Integration und Releases bleiben separate
    Etappen; t0003 bleibt unverändert.
- Blocker: keine bekannten; tatsächlichen CI-, Git- und PR-Stand prüfen.
- Prüfergebnisse: Lokal unter Linux 107 Generator-Tests erfolgreich, davon 6 Windows-Tests
  übersprungen. 16 Basistests erfolgreich, davon 3 netzwerkabhängige Tests im Offline-Modus
  übersprungen. `python scripts/check.py` erfolgreich. Die Linux-/Windows-CI ist separat
  auf dem tatsächlichen PR-Kopfstand zu prüfen.
- Nicht synchronisierte Änderungen: per `git status` und PR-Stand prüfen.

## Nächster Schritt

CI des PR-Kopfstands prüfen und das Review-Gate durch den Menschen durchführen.

## Entscheidungen und Quellen

Die verbindliche Gate-A-Matrix und PR-Reihenfolge stehen in
[DV_KONZEPT.md](DV_KONZEPT.md). Der Schnittstellenvertrag einschließlich Analysegrenzen steht in
[GENERATOR_CONTRACT.md](GENERATOR_CONTRACT.md).

## Probleme

Apply und Restore setzen exklusiven Projektzugriff während des jeweiligen Aufrufs voraus.
Nach abruptem Abbruch oder fehlgeschlagener Protokollierung kann ein Teilzustand manuelle
Wiederherstellung erfordern. Die lesende Migrationsanalyse setzt ein während ihres Aufrufs
unverändertes Quellprojekt voraus.
