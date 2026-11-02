# Projektübergabe

Flüchtiger Arbeitsstand. Entscheidungen stehen in [DV_KONZEPT.md](DV_KONZEPT.md) und
[GENERATOR_CONTRACT.md](GENERATOR_CONTRACT.md). Git hat bei Widersprüchen Vorrang.

## Aktueller Stand

- Schritt 113C: TypeScript-Vorlage und Regressionstest korrigiert. Lokale Regression
  mit aktueller isolierter Paketinstallation: 140 Generator-Tests bestanden, 21 unter
  Windows übersprungen; 12 Integrationstests bestanden, einschließlich Node-Build,
  Node-Tests und Python-Regression. Der Projektcheck ist erfolgreich. Von 16 Basistests
  bestanden 15; `test_speckit` scheiterte an der lokalen PowerShell-Ausführungsrichtlinie.
  Die CLI-EXE bleibt lokal durch die Anwendungsrichtlinie blockiert; der dokumentierte
  Python-Moduleinstieg wurde für die Integration genutzt. Keine Richtlinie wurde geändert.
- Schritt 113B: Reale p9999-Praxistests mit t0004/main `fc44849` erfolgreich.
  TypeScript allein: PR #2, Commit `7d3bbd167e3f1745a40d75441b9573f981cee8f7`;
  Python dann TypeScript: PR #3, Commit `3f5571a78a37743000f8b0c4e0935e99ec190d7c`.
  Beide Push- und PR-Workflows auf Ubuntu und Windows erfolgreich; die nur für das
  t0003-Repository vorgesehenen Template-Tests werden in p9999 übersprungen. Lokale
  Installation, Build, Tests und Beispiele erfolgreich. p9999/main blieb `bb19b76`,
  Python allein: PR #1, Commit `7b0de35093b68ab4c7c22838bd8023e7d48342f5`.
  Alle drei PRs bleiben offen und ungemergt. Die veraltete Zukunftsaussage in der
  generierten TypeScript-Dokumentation wurde in Schritt 113C korrigiert.
- Schritt 113A läuft auf `test/typescript-module-e2e`, ausgehend von `main` / `fc44849`.
  PR #12 ist gemergt; nachfolgende Branch- und PR-Angaben sind historisch. Der Git-Baum
  von p9999/main (`bb19b76`) und t0003 `6e8363a` ist identisch: `cc888863ebd53e4a7fde5fe198d4756b00009fc9`.
- Windows: Projektcheck erfolgreich; Generator-Tests 139 bestanden, 21 plattformbedingt
  übersprungen; Integration 12 bestanden. Diese umfasst die drei Modulkonfigurationen,
  npm ci, Node 24, Build, Node-Tests, Anwendung, Projektcheck und Restore. Sicherheitsfälle
  decken fremde und manipulierte Dateien, veraltete Pläne, alte Templates, Konflikte,
  beschädigte Snapshots und die Verweigerung ohne Teiländerung ab.
- Basistests: 15 bestanden, ein Fehler (`test_speckit`), da die lokale PowerShell-Richtlinie
  Skripte blockiert. Keine Richtlinienänderung. Der erfolgreiche Generatorlauf verwendete
  `PYTHONUTF8=1` außerhalb der Sandbox; Integration nutzte die lokale t0003-Referenz und
  `T0004_TEST_CLI_MODULE=1`, da die lokale Anwendungsrichtlinie die CLI-EXE blockiert.
  PR C und dessen CI-Abnahme stehen noch aus.
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

Schritt 113C zur abschließenden Prüfung und PR C durchführen.

## Risiken

Die korrigierte TypeScript-Dokumentationsvorlage ändert den bytegenau erwarteten
Modulzustand: Projekte aus PR B mit der alten Dokumentation melden bei späterer
Modulplanung einen Konflikt. Die Datei ist bewusst an die neue Vorlage anzupassen;
ein automatisches Überschreiben erfolgt nicht.

Apply und Restore setzen während des Aufrufs exklusiven Projektzugriff voraus. Nach
abruptem Abbruch oder fehlgeschlagener Protokollierung kann manuelle Wiederherstellung
erforderlich sein. `verify` als eigener Generatorbefehl und Releases bleiben offen.
