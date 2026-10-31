# Changelog

Alle wesentlichen Änderungen am Template. Format: [SemVer](https://semver.org/lang/de/). Das
Template wird getrennt vom Generator versioniert. Kategorien: Arbeitsregeln, Specify/Tooling,
Projektstruktur, Adapter, CI, Sicherheit, Breaking Changes, Migrationshinweise.

## [Unveröffentlicht]

### Python-Modul
- `new` und `plan --module python` planen `python@0.1.0` mit `src/`-Layout, Beispiel,
  `unittest`, Projektcheck und Ergänzung der bestehenden CI. Bestätigtes Apply und Restore
  verwenden die vorhandene Mehrdatei-Engine. Der geprüfte t0003-Check-/CI-Dateistand ist
  zusätzlich zum unveränderten Template-Release erforderlich.

### Sicherheit
- Restore verweigert für beide Manifestformate auch dann eine zwischenzeitliche Änderung,
  wenn diese nach einem protokollierten Teilzustand wieder dem älteren Generatorergebnis
  entspricht.
- Interne Mehrdatei-Transaktionen mit Planformat 4 und Manifestformat 3 prüfen sämtliche
  Ausgangs- und Restore-Zustände, sichern vorhandene Dateien und erfassen fehlende Dateien
  sowie Teilzustände. Ohne Modulauswahl bleiben `new` und `plan` bei Format 3;
  vorhandene Manifestformat-2-Backups bleiben lesbar.
- Installierbare Generator-CLI mit lokalem, lesendem Safety-Core-Plan. Planformat 3 erlaubt
  bestätigtes Apply der Metadatenoperation mit geschütztem Snapshot und konfliktbewusstem
  Restore. `new` erstellt denselben Plan für ein bereits vorhandenes t0003-Projekt; es erstellt
  kein Repository und unterstützt noch keine Profile oder vollständiges `verify`.
- `migrate` erstellt ohne Änderungen einen begrenzten Bestandsbericht mit Strategievergleich;
  eine schreibende Migration ist nicht implementiert.
- Backups liegen außerhalb von Git-Arbeitsverzeichnissen; erfasste Teilzustände nach
  Schreibfehlern können ohne Überschreiben späterer Fremdänderungen zurückgenommen werden.
- Basis- und neue Generator-Tests laufen weiterhin in der vorhandenen Linux-/Windows-CI.

## [0.1.0] – 2026-10-30

### Projektstruktur
- Die Implementierungsvorgabe liegt auf dem Branch `maintenance` und wird nicht in Projektkopien kopiert.
- Neutrales Template: README, `AGENTS.md`, `config/project.yaml`, DV-Konzept, Handoff, Quickstarts.

### Specify/Tooling
- Wählbar: Spec Kit (gepinnt 1.0.7, Windows-sicherer Python-Wrapper) und OpenSpec (gepinnt 1.15.0).
- `scripts/sdd.py`, `check.py`, `status.py`, `update_check.py`.
- `scripts/handoff.py`: Export (kompakt/umfassend, mit Secret-Filter und Commit-Stempel) und
  `import-check` für externe Rückgaben (nur lesend, weist Abweichungen seit dem Export aus).

### Adapter
- `.github/copilot-instructions.md` verweist nur auf `AGENTS.md`.

### CI
- GitHub Actions mit `contents: read`: Template-Tests und Praxistest einer Projektkopie.
