# Changelog

Alle wesentlichen Änderungen am Template. Format: [SemVer](https://semver.org/lang/de/). Das
Template wird getrennt vom Generator versioniert. Kategorien: Arbeitsregeln, Specify/Tooling,
Projektstruktur, Adapter, CI, Sicherheit, Breaking Changes, Migrationshinweise.

## [Unveröffentlicht]

### Sicherheit
- Installierbare Generator-CLI mit lokaler Konfigurationsprüfung und ausschließlich lesendem,
  deterministischem Safety-Core-Plan; keine Schreib-, Backup- oder Migrationsfunktion.
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
