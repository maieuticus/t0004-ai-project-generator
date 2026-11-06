# Implementation Plan: Private GitHub Usage

**Spec**: [spec.md](spec.md) | **Status**: Entwurf, wartet auf LOS | **Architektur**: V1 (Authentifizierung an den Systemgrenzen)

## Technical Context

- Betroffene Randstellen (bei Umsetzung): `integration/test_t0003_integration.py`, `scripts/docker_ci.py`, `scripts/update_check.py`, `.github/workflows/ci.yml`, `.github/workflows/docker-validation.yml`, `docs/QUICKSTART.md`, `README.md`.
- Unverändert: `src/project_generator/**` (Kern, Plan/Apply/Restore, historische Zustände).
- Credential-Quellen: lokal/Codespaces `gh`-Anmeldung bzw. Credential Helper (pro Befehl, ohne Änderung der Git-Konfiguration); CI: Fine-Grained PAT, Contents: read, nur Template-Repository. Deploy Key nur nach dokumentiertem Vergleich.
- Repo-Erstellung ist getrennt vom Lesen zu verifizieren (FR-012): Die GitHub-REST-Doku führt „Create a repository using a template" (`POST /repos/{template}/generate`) als eigenen Endpunkt; die zugehörige Fine-Grained-Berechtigung (vermutlich Administration: write beim Zielkonto) ist **nicht verifiziert** und wird in Inkrement 3 praktisch geprüft.
- CI-Vertrauen: `pull_request`-Läufe aus Forks erhalten keine Secrets; `pull_request_target` wird nicht verwendet. Template-abhängige Prüfungen melden dort „übersprungen/nicht geprüft".

## Constitution Check

| Prinzip | Bewertung |
|---------|-----------|
| I Engine wiederverwenden | Kern unverändert, nur Randskripte |
| II Einfach/deterministisch | Kein neuer Dienst, keine GitHub App |
| III Historische Zustände | Acht Byte-Zustände unverändert (FR-016) |
| IV Plan vor Schreiben | Keine neue Schreibfunktion im Kern |
| VI Begrenzter Umfang | Keine Schreib-Tokens, Agenten ohne Credentials |
| VII Inkrementell | Vier Inkremente mit Review Gate |

## Inkremente

| # | Ziel | Technische Änderungen | Tests / Abnahmenachweis | Abhängigkeiten | Aufwand | Risiken |
|---|------|----------------------|-------------------------|----------------|---------|---------|
| 1 | Zugriffsgrundlage | Gemeinsame Abruf-Hilfe in `scripts/` (pro-Befehl-Credential, Fehlerklassen 401/403/404/abgelaufen/fehlend, keine Prompts); Leak-Scan-Prüfung | Unit-Tests je Fehlerklasse, Leak-Scan, Generator-Suite und `check.py` grün; `git diff` zeigt `src/` unverändert | Keine | 1–1,5 Tage | Falsche Erfolgsmeldungen bei Fehlern; Credential in Logs |
| 2 | CI und Integration | Gepinnte Referenz `6e8363a` in Tests/CI; Trusted/Untrusted-Trennung; Skip-Semantik; Credential nur in Abrufschritten; Update-Check „nicht geprüft" | Vier grüne Hosted-Jobs (Ubuntu/Windows, Docker Linux/Windows) plus gezielter Fork-/Untrusted-Lauf mit „übersprungen" | 1 | 1–2 Tage | Windows-Abweichungen; Secret-Exposition in Fork-Läufen |
| 3 | Private Testkopien und Abnahme | Nutzer legt private Kopien an (geprüfte, gepinnte Commits, kein Mirror); Read-only-Credential; Matrix A–D; negative Tests (kein Zugriff, falscher Scope, abgelaufen, fehlendes Secret); echte Projekterstellung | Abnahmematrix mit Ergebnis/Datum, Leak-Scan über Logs, Konfiguration, Plan, Snapshot, Backup | 2; Nutzeraktion (Kopien, Token) | 1–2 Tage plus Wartezeit | Offene Frage zur Berechtigung bei „Use this template" mit privatem Template; Token-Handhabung |
| 4 | Dokumentation und Sichtbarkeitsentscheidung | Berechtigungsleitfaden, Rotation/Widerruf, Hinweis auf bleibende öffentliche Forks, Umschaltplan mit Rollback; DV-Konzept-Entscheidung | Dokumentationsreview, Checkliste der Umschaltbedingungen | 3 | 0,5–1 Tag | Nicht rückholbare öffentliche Kopien |

Jedes Inkrement endet mit menschlichem Review Gate; die Sichtbarkeitsänderung ist ein separater, genehmigungspflichtiger Schritt nach Gate 4.

## Offene Entscheidungen

1. Deploy Key vs. Fine-Grained PAT (Vergleich in Inkrement 2).
2. Konto/Name der privaten Testkopien (Inkrement 3).
3. Umgang mit Differenz `main` (`6e8363a`) zu Release `964de85` in t0003 (Release neu setzen oder dokumentiert trennen).
4. Ob private Kopie von p9999 benötigt wird oder neue Testprojekte genügen.
