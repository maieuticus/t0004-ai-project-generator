# Quickstart

Kurzanleitung für den ersten Start. Es sind nur Kommandos aufgeführt, die in diesem Template
geprüft wurden; Grenzen stehen am Ende.

## 1. Projekt starten

1. Auf GitHub **Use this template** wählen und ein privates Repository erstellen.
2. Öffnen in **VS Code** (lokal klonen) oder in **GitHub Codespaces** (Code → Codespaces → neu).
   Voraussetzung: Git und Python 3.11+. Docker wird nicht benötigt.
3. Optional in `config/project.yaml` den Projektnamen eintragen.

## 2. Agent starten

Du installierst und startest den Agenten selbst. Das Template installiert nichts und startet
keinen Agenten automatisch.

- **GitHub Copilot (VS Code/Chat):** Repository öffnen; Copilot liest `.github/copilot-instructions.md`,
  die auf `AGENTS.md` verweist.
- **Copilot CLI / Codex / andere:** im Projektordner starten. Sage am Anfang: _„Lies AGENTS.md und
  docs/PROJECT_HANDOFF.md und beginne mit dem Ideen-Dialog.“_ Nicht jedes Werkzeug liest `AGENTS.md`
  automatisch; dieser Satz ist der sichere Start.

## 3. Idee → SDD-Wahl → Architektur

1. Beschreibe deine Projektidee frei.
2. Der Agent klärt Anforderungen und empfiehlt Spec Kit oder OpenSpec. Bestätige.
3. Der Agent führt `python scripts/sdd.py select speckit|openspec` aus. Details:
   [SDD_QUICKSTART.md](SDD_QUICKSTART.md).
4. Der Agent schlägt eine Architektur vor. Erst nach deiner Freigabe richtet er Technik ein.

## 4. Setup, Check, Status

```text
python scripts/sdd.py select speckit      # Setup des gewählten SDD-Werkzeugs
python scripts/check.py                   # Check: Dokumente, Pflichtdateien, Projektprüfungen
python scripts/status.py                  # Status: Handoff, Git, SDD, Template-Version
python scripts/update_check.py            # optional: neuere Template-Version veröffentlicht?
```

## 5. Arbeit wieder aufnehmen oder Agent wechseln

Der Agent pflegt `docs/PROJECT_HANDOFF.md` nach wesentlichen Schritten. Neue Sitzung: Agent bitten,
den Handoff zu lesen und mit `git status` abzugleichen. Wechsel zwischen Umgebungen funktioniert nur
über Git (committen und pushen, in der anderen Umgebung pullen).

## 6. Mit ChatGPT besprechen

```text
python scripts/handoff.py export            # kompakt (Handoff); --full für umfassend
python scripts/handoff.py import-check antwort.md
```

Der Export liegt in `exports/` (nicht in Git) und trägt den Commit-Stand. Ergebnisse von ChatGPT
speicherst du als Datei und gibst sie dem Agenten; `import-check` warnt, wenn sich das Repo seit dem
Export geändert hat, und ändert nichts. Übernommen wird erst nach deiner Freigabe.

## Agenten: was geprüft ist

| Agent | Startdatei | Stand |
|---|---|---|
| GitHub Copilot (Chat, CLI) | `.github/copilot-instructions.md` → `AGENTS.md` | Adapter vorhanden; Lesen nicht E2E verifiziert |
| Codex | `AGENTS.md` | Dateien werden erzeugt (`--integration codex`); Lesen nicht E2E verifiziert |
| OpenCode, Kimi | `AGENTS.md` | dokumentiert, nicht E2E verifiziert; im Zweifel den Startsatz aus Abschnitt 2 verwenden |

Nur der Startsatz aus Abschnitt 2 ist agentenunabhängig sicher. Auto-Erkennung des Handoffs wird
nicht behauptet.

## Grenzen

Geprüft: Python-Skripte unter Linux/Codespaces. Windows und macOS sind nicht manuell geprüft (CI
prüft Windows). Keine Agenten-E2E-Tests; welche Agenten welche Startdatei lesen, ist je Werkzeug
unterschiedlich.

## Privates Template einrichten (T025)

1. In GitHub prüfen, dass die verwendete Identität Leserechte auf das private
   Quell-Template besitzt und private Ziel-Repositories erstellen darf.
2. GitHub-Authentifizierung lokal prüfen (`gh auth status`). Keine Tokens oder
   vollständigen Authentifizierungsdetails in Agenten-Prompts kopieren.
3. Falls ein separater Lesezugriff erforderlich ist, ein zeitlich begrenztes
   Token mit minimalen Berechtigungen verwenden. Für entsprechende CI-Abläufe
   wird das vereinbarte Secret `T0003_READ_TOKEN` verwendet.
4. Ein benötigtes CI-Secret über die GitHub-Oberfläche oder einen sicheren
   Administrationsweg hinterlegen; niemals in Workflow-Dateien eintragen.
5. Den Generator zunächst mit `plan`, anschließend nach Prüfung mit `apply`
   verwenden. Dabei private Quellreferenz und private Zielsichtbarkeit prüfen.
6. Nach Erstellung kontrollieren: Repository ist privat, Vorlage und erwartete
   Dateien sind vorhanden, es wurden keine Secrets übernommen.
7. GitHub Actions und Schutzmechanismen bewusst konfigurieren. Fehlende
   Branch-Protection-Funktionen aufgrund des GitHub-Plans dokumentieren.
8. Bei jeder neuen lokalen Arbeitskopie die vorgesehene Security-Einrichtung
   ausführen und ihre Wirksamkeit prüfen.

### Token-Rotation und Widerruf

Für eine Rotation zunächst neuen Zugriff mit minimalen Rechten einrichten,
den privaten Lesezugriff überprüfen und erst danach den alten Zugriff widerrufen.
Nach dem Widerruf kontrollieren, dass der alte Zugang nicht weiter nutzbar ist.

Bei temporären Abnahmetokens: nach Abschluss widerrufen, nicht mehr benötigte
CI-Secrets entfernen und den Abschluss im Abnahmeprotokoll dokumentieren.

Private Inhalte oder Tokens dürfen weder in öffentliche Repositories noch an
nicht ausdrücklich freigegebene KI-Dienste übertragen werden. Ein gescheiterter
privater Zugriff darf keine automatische öffentliche Ersatzquelle verwenden.

Die endgültige Umstellung und spätere Bereinigung erfolgen nur nach
erfolgreicher Abnahme und gemäß `specs/002-private-github-access/switch-plan.md`.
