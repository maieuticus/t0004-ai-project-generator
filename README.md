# Projekt

> Dieses Projekt wurde aus `t0003-ai-project-template` erstellt. Es ist technologieneutral:
> Sprache, Datenbank und Architektur sind noch nicht festgelegt. Zuerst kommt die Idee.

## Einstieg

1. Beschreibe deine Projektidee frei in einer Sitzung mit deinem KI-Agenten.
2. Der Agent klärt Anforderungen, empfiehlt ein SDD-Werkzeug (Spec Kit oder OpenSpec) und
   schlägt eine Architektur vor. Du gibst beides frei.
3. Danach richtet der Agent nur das Nötige ein.

Kurzanleitung: [docs/QUICKSTART.md](docs/QUICKSTART.md) · SDD-Wahl:
[docs/SDD_QUICKSTART.md](docs/SDD_QUICKSTART.md)

## Wichtige Dateien

| Datei | Zweck |
|---|---|
| [AGENTS.md](AGENTS.md) | Arbeitsregeln für alle KI-Agenten |
| [docs/DV_KONZEPT.md](docs/DV_KONZEPT.md) | verbindliche Projektbeschreibung und Architektur |
| [docs/PROJECT_HANDOFF.md](docs/PROJECT_HANDOFF.md) | aktueller Arbeitsstand für die Übergabe |
| [config/project.yaml](config/project.yaml) | Projekt-, Template- und SDD-Metadaten |
| [CHANGELOG.md](CHANGELOG.md) | Änderungen des Templates |

## Prüfen

```text
python scripts/check.py        # Dokumente, Pflichtdateien, projektspezifische Prüfungen
python scripts/status.py       # dokumentierten Arbeitsstand anzeigen
```
