# Implementation Plan: Private GitHub Usage

**Spec**: [spec.md](spec.md) | **Status**: Inkrement 1 abgeschlossen; Review Gate 1 am 2026-11-06 menschlich freigegeben | **Architektur**: V1 (Authentifizierung an den Systemgrenzen)

## Technical Context

- Betroffene t0004-Randstellen (bei Umsetzung): `integration/test_t0003_integration.py`, `scripts/docker_ci.py`, `.github/workflows/ci.yml`, `.github/workflows/docker-validation.yml`, `docs/QUICKSTART.md`, `README.md`. Das geerbte `scripts/update_check.py` wird separat geprüft, bleibt ohne Abhängigkeit auf einen t0004-Helfer und erhält keine Umsetzung in Inkrement 1 oder 2.
- Unverändert: `src/project_generator/**` (Kern, Plan/Apply/Restore, historische Zustände).
- Credential-Quellen: lokal/Codespaces ausschließlich vorhandene `gh`-Anmeldung bzw. Credential Helper (pro Befehl, ohne Änderung oder neue Ablage der Git-Konfiguration); CI: Fine-Grained PAT, Contents: read, nur Template-Repository. Die Helper-Schnittstelle akzeptiert keine Token-Argumente, persistiert nichts und redigiert Subprozessausgaben. Deploy Key nur nach dokumentiertem Vergleich.
- Kompatibilitätsnachweis: `6e8363a7ac7d99220d743eea077dcd5cefda9042` identifiziert die originale kompatible t0003-Basis; `964de8538d19cefcb483faff38f10124615a9783` bleibt der ältere, abgelehnte Release-Stand. Weil „Use this template“ unabhängige Git-Historien erzeugt, prüfen Tests die bestehenden Vertragsdateien und ihre bekannten Digests, `config/project.yaml` sowie zulässige historische Modul-/CI-Projektionen statt eines Commit-Vorfahren. Es werden keine Tags geändert und keine vollständige Historie übertragen.
- Repo-Erstellung ist getrennt vom Lesen zu verifizieren (FR-012): Die GitHub-REST-Doku führt „Create a repository using a template" (`POST /repos/{template}/generate`) als eigenen Endpunkt; die zugehörige Fine-Grained-Berechtigung (vermutlich Administration: write beim Zielkonto) ist **nicht verifiziert** und wird in Inkrement 3 praktisch geprüft.
- CI-Vertrauen: `pull_request`-Läufe aus Forks erhalten keine Secrets; `pull_request_target` wird nicht verwendet. Template-abhängige Prüfungen melden dort auf Linux und Windows „übersprungen/nicht geprüft". Ein Secret ist nur für den Abrufschritt sichtbar, ist Contents-read für ein Repository und nie als Job- oder Workflow-Umgebung verfügbar.

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
| 1 | Zugriffsgrundlage | Gemeinsame t0004-Abruf-Hilfe in `scripts/` (pro-Befehl-Credential, Fehlerklassen 401/403/404/abgelaufen/fehlend, keine Prompts und keine Token-Argumente); Leak-Scan- und Credential-Store-Isolationsprüfung; historiesicherer Kompatibilitätsnachweis | Unit-Tests je Fehlerklasse mit lokalen Bare-Repositories und Stubs, inklusive Windows-kompatibler Umgebung; kein Token und kein privates Repository; Leak-Scan, Generator-Suite und `check.py` grün; `git diff` zeigt `src/` unverändert | Keine | 1–1,5 Tage | Falsche Erfolgsmeldungen bei Fehlern; Credential in Logs |
| 2 | CI und Integration | Gepinnte Referenz `6e8363a`, Default-Branch-Drift, Trusted/Untrusted-Trennung und Skip-Semantik; Secret nur im Abrufschritt; das t0003-Update-Skript bleibt unverändert und unabhängig | Vier grüne Hosted-Jobs (Ubuntu/Windows, Docker Linux/Windows), statischer Nachweis für Minimalrechte und ein gezielter Fork-/Untrusted-Lauf mit „übersprungen" | 1 | 1,5–2 Tage | Windows-Abweichungen; Secret-Exposition in Fork-Läufen |
| 3 | Private Testkopien und Abnahme | Nutzer legt private Kopien an (geprüfte, gepinnte Commits, kein Mirror); Read-only-Credential; Matrix A–D; negative Tests (kein Zugriff, falscher Scope, abgelaufen, fehlendes Secret, Fork); echte Projekterstellung und separate private Prüfung des t0003-Updatechecks | Abnahmematrix mit Ergebnis/Datum, Berechtigungsnachweis, Leak-Scan über Logs, Konfiguration, Plan, Snapshot, Backup sowie Agenten-Secret-Isolation | 2; Nutzeraktion (Kopien, Token) | 1–2 Tage plus Wartezeit | Offene Frage zur Berechtigung bei „Use this template" mit privatem Template; Token-Handhabung |
| 4 | Dokumentation und Sichtbarkeitsentscheidung | Berechtigungsleitfaden, Rotation/Widerruf, Hinweis auf bleibende öffentliche Forks, Umschaltplan mit Rollback; DV-Konzept-Entscheidung | Dokumentationsreview, Checkliste der Umschaltbedingungen | 3 | 0,5–1 Tag | Nicht rückholbare öffentliche Kopien |

Jedes Inkrement endet mit menschlichem Review Gate; die Sichtbarkeitsänderung ist ein separater, genehmigungspflichtiger Schritt nach Gate 4.

## Review Gate 1 Evidence

The human review approved T001–T008 on 2026-11-06. Draft PR #32 passed the Ubuntu
and Windows baseline and Docker checks; the generator core remains unchanged and all
credentials used in tests are synthetic. Authentication against an actual private
GitHub repository, credential scope verification and private update-check acceptance
remain explicitly deferred to Increment 3 and its human gates.

## Offene Entscheidungen

1. Deploy Key vs. Fine-Grained PAT (Vergleich und Dokumentation vor T014 in Inkrement 2).
2. Konto/Name der privaten Testkopien (Inkrement 3).
3. Ob private Kopie von p9999 benötigt wird oder neue Testprojekte genügen.
