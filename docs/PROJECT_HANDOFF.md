# Projektübergabe

Flüchtiger Arbeitsstand. Entscheidungen stehen in [DV_KONZEPT.md](DV_KONZEPT.md) und
[GENERATOR_CONTRACT.md](GENERATOR_CONTRACT.md). Git hat bei Widersprüchen Vorrang.

## Aktueller Stand

- Stand: 2026-11-02.
- Branch: `feat/typescript-module-pr-b`, ausgehend von `main` / `34b1b33`.
- PR A (#11) ist in `main` gemergt. Der alte Handoff war insoweit veraltet.
- Freigegebene Architektur: TypeScript unter `typescript/`, Node 24, strict/NodeNext,
  `node:test`, feste Abhängigkeiten und Lockfile; sequenzielle Python-/TypeScript-Installation
  über die vorhandene Format-4-Engine und Restore in umgekehrter Reihenfolge.
- PR B bindet TypeScript an CLI, Read-only-Plan, bestätigten Apply, Snapshot und Restore an.
  Vier feste CI-Zustände und kanonische Modulmetadaten unterstützen beide Reihenfolgen.
- t0003-Kompatibilität bleibt auf den geprüften Entwicklungsstand `6e8363a` beschränkt;
  der ursprüngliche Release-Commit wird weiterhin abgelehnt. Der echte GitHub-Template-Test
  mit p9999 war bereits erfolgreich; t0003 und p9999 werden hier nicht geändert.
- PR #12 ist gegen `main` offen, Implementierungsstand `1e19973`.
- Lokal erfolgreich: `python scripts/check.py`, 159 Generator-Tests (21 plattformbedingt
  übersprungen) und 10 Integrationstests gegen die gepinnten t0003-Commits. Der lokale
  Windows-Basistest `test_speckit` wird durch die PowerShell-Ausführungsrichtlinie blockiert;
  die übrigen 15 Basistests sind grün. Die Integrationstests liefen hier über
  `python -m project_generator`, weil die lokale Anwendungsrichtlinie erzeugte `.exe`
  blockiert. Die reguläre CLI läuft in der CI.
- Beide Linux- und beide Windows-CI-Läufe von PR #12 waren auf `1e19973` erfolgreich.

## Nächster Schritt

Menschliches Review-Gate für PR #12 durchführen; nicht automatisch mergen.

## Risiken

Apply und Restore setzen während des Aufrufs exklusiven Projektzugriff voraus. Nach
abruptem Abbruch oder fehlgeschlagener Protokollierung kann manuelle Wiederherstellung
erforderlich sein. `verify` als eigener Generatorbefehl und Releases bleiben offen.
