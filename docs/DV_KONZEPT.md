# DV-Konzept

Verbindliche Projektbeschreibung für das Generator-Repository. Architektur- und
Verhaltensentscheidungen gelten erst nach Freigabe.

## Status dieses Dokuments

Bootstrap-Stand für `t0004-ai-project-generator`.

## Projektziel

Python-Generator als eigenständiges Werkzeug bereitstellen, der Projekte aus einer stabilen
Template-Basis nachvollziehbar erweitert. Standardmodus ist `dry-run`; schreibende Änderungen
erfolgen erst nach expliziter Freigabe.

## Anforderungen und Erfolgskriterien

- CLI mit klaren Subcommands, Exitcodes und verständlichen Fehlermeldungen.
- `dry-run` zeigt geplante Änderungen inkl. Konflikten.
- `apply` führt Änderungen nur nach bestätigter Freigabe aus.
- Backups und sicherer Rollback für bestehende Dateien.
- Tests und CI für Linux, Windows sowie Codespaces-nahe Abläufe.

## Architektur

Modularer Python-Kern mit optionalen Profilen/Modulen. Vertrag und Sicherheitsregeln stehen in
`docs/GENERATOR_CONTRACT.md`; Detailentscheidungen folgen über den SDD-Prozess.

## Entwicklung und Betrieb

Primär Python-basierte Entwicklung und Prüfung. SDD-Werkzeug (Spec Kit/OpenSpec) wird wie im
Template nur nach expliziter Auswahl eingerichtet.

## Entscheidungen

| Datum | Entscheidung | Freigabe durch |
|---|---|---|
| 2026-10-30 | `t0004` als separates Generator-Repository auf Basis von `t0003 v0.1.0` starten | Nutzer |
