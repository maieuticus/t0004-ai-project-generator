# Private GitHub Access – Acceptance Evidence

Status: Teilnachweise; vollständige Abnahme T023 noch offen.

| Case | Expected | Observed | Date | Evidence |
|---|---|---|---|---|
| T030 – Private template update check | Eigenständiger Versionsvergleich aus t0003 über bestehenden Git-Zugang; kein t0004-Helper | PASS: Release 0.1.0 entspricht dem privaten Tag v0.1.0 | 2026-11-09 | Manuell protokollierte PowerShell-Ausgaben, siehe unten |

## T030 – Nachweis

- Repository: `maieuticus/t0003-private-access-test`
- Skript: `scripts/update_check.py` aus der lokalen t0003-Testkopie
- Zugriff: bestehende Git-Authentifizierung; kein neu erstellter PAT
- Privater Zugriff mit `git ls-remote --tags --refs` bestätigt
- Ausgabe: `Template-Update: keine neue Version (übernommen: 0.1.0, verfügbar: v0.1.0).`
- Kein t0004-Hilfsprogramm verwendet
- `template.source` ausschließlich lokal und vorübergehend angepasst
- Ursprüngliche Konfiguration anschließend mit `git restore` wiederhergestellt
- Nachweise beruhen auf den während des Tests kontrollierten Terminalausgaben

## Noch offen

- T019-B: formalen GitHub-Template-Erstellungsnachweis abschliessen.
- T019-A: manuellen PostgreSQL-Check nach Korrektur wiederholen
- T020-D: automatischer Vergleich nicht nachgewiesen
- T021: verbleibende Negativ- und Plattformtests
- T022: Prüfung auf Zugangsdaten-Leaks
- T023: vollständige Abnahmematrix
- T024: Bereinigung der Testressourcen
- Entscheidung über private Original-Repositories

## T020-D – Private versioned-base comparison

- Datum: 2026-11-09
- Ergebnis: PASS (manueller, rein lesender Vergleich)
- Private Template-Quelle: maieuticus/t0003-private-access-test
- Gepinnter Basis-Commit: 6e8363a7ac7d99220d743eea077dcd5cefda9042
- Bestehendes privates Projekt: t0004-private-e2e-test
- Testkopie: t020d-compare-sandbox
- Vergleichsbasis: t020d-template-snapshot
- Privater Git-Abruf mit bestehender Anmeldung erfolgreich
- Vergleich: git diff --no-index
- Lokale Testaenderung in README.md erkannt
- Nach dem Vergleich weiterhin vorhanden: M README.md
- Keine anderen Projektdateien laut git status veraendert
- Keine Commits, Pushes oder GitHub Actions ausgeloest
- Einschraenkung: manueller Dateivergleich, keine automatisierte Generator-Vergleichsfunktion nachgewiesen

## T019-A – Testnachweis

- Datum: 2026-11-09
- Quelle: öffentliches t0003-Template
- Ziel: privates Testprojekt `maieuticus/t019-public-to-private-test`
- Python, TypeScript, Java und React: Plan, Apply, Check, No-op und Restore bestanden
- Docker Compose: vollständiger Testzyklus bestanden
- PostgreSQL: Plan, Apply, No-op und Restore bestanden
- Ursprünglicher Fehler: allgemeiner PostgreSQL-Check meldete `valid: false`
- Ursache: fehlendes `allow_postgresql=True` im allgemeinen CLI-Check
- Korrektur: `src/project_generator/cli.py`
- Regressionstest: `test_postgresql_general_check_after_install`
- Regressionstest vor Korrektur fehlgeschlagen, danach bestanden
- Infrastruktur-Testsuite: 38 Tests bestanden
- Gesamte Testsuite: 288 Tests, OK (26 übersprungen)
- PostgreSQL-Testkopie nach Restore: sauberer Git-Arbeitsbaum
- Manueller PostgreSQL-Check nach Korrektur noch offen
- Kein tatsächlicher Docker- oder PostgreSQL-Laufzeittest
- Keine Commits oder Pushes in die Original-Repositories

## T019-B - Testnachweis

- Datum: 2026-11-10
- Privates Template: `maieuticus/t0003-private-access-test`
- Privates Projekt: `maieuticus/t0004-private-e2e-test`
- GitHub-Sichtbarkeit beider Repositories: PRIVATE
- Vergleich der Git-Dateistrukturen: 39 Objekte je Repository, 0 Abweichungen
- Ausgangskonfiguration: Generator-Check erfolgreich
- Automatisierter Runner: 6 von 6 Testvarianten bestanden
- Python: 8 Operationen
- TypeScript: 10 Operationen
- Java: 11 Operationen
- React: 14 Operationen
- Docker Compose: Python 8, Docker Compose 6 Operationen
- PostgreSQL: Python 8, Docker Compose 6, PostgreSQL 6 Operationen
- Alle Varianten: Plan, Apply, Check, No-op und Restore bestanden
- Git-Arbeitsbaum nach Restore jeweils sauber
- Urspruenglicher Installationsplan nach Restore wiederhergestellt
- Bericht: `t019-b-acceptance-20261110-211440-482086/report.json`
- Laut Bericht keine Credentials oder Backup-IDs enthalten
- Einschraenkung: tatsaechliche Docker-/PostgreSQL-Laufzeit nicht getestet
- Einschraenkung: identische Git-Dateistruktur beweist nicht allein die Erstellung ueber GitHubs Template-Funktion
- Keine Commits oder Pushes in die Original-Repositories

## T021 - Security acceptance (partial)

- Date: 2026-11-11
- Windows: 10 authentication tests passed
- Linux Ubuntu WSL2: 10 authentication tests passed
- CI run 42600283741: Ubuntu and Windows baseline jobs successful
- Missing credential: automated failure test passed
- Rejected private access: automated failure test passed
- Untrusted mode: inherited credential not used
- Workflow review: private fetch restricted to trusted push on main
- Workflow review: untrusted events use --untrusted
- Live wrong-repository-scope credential: not verified
- Live expired credential: not verified
- Actual fork pull-request execution: not verified
- Status: PARTIAL; T021 is not fully accepted

### Gitleaks-CI-E2E (2026-11-11)

- Isoliertes privates Repository: `maieuticus/t0003-secret-scan-e2e-test`
- Positivtest: Run 43004546560, success, Scan secrets ausgefuehrt.
- Negativtest: Run 43010709119, failure im Schritt Scan secrets.
- Negativtest verwendete ausschliesslich synthetische Zugangsdaten.
- Negativtest-Branch auf GitHub geloescht.
- GitHub Actions nach der Abnahme wieder deaktiviert.
- Lokaler Pre-Commit-Hook: blockierender und erlaubter Commit getestet.
- Offen: verpflichtende Merge-Pruefung, vollstaendiger t0004-Ablauf,
  restliche T022-Pruefbereiche und Bereinigung T024.

### GitHub-Merge-Sperre (2026-11-11)
- Status: TARIFBEDINGT NICHT VERFUEGBAR.
- GitHub API: HTTP 403, Upgrade auf GitHub Pro erforderlich.
- Private Repositories bleiben privat.
- Gitleaks Pre-Commit und GitHub-CI positiv/negativ getestet.
- CI-Fehler verhindert ohne Branch-Schutz nicht verbindlich den Merge.
- Vor produktiver Freigabe Schutzluecke als Restrisiko bewerten.

### Sicherheitsintegration T019-B (2026-11-11)
- Alle 6 Technologiemodule: PASS.
- Plan, Apply, Check, No-op und Restore erfolgreich.
- Alle 6 Git-Arbeitskopien nach Restore sauber.
- 3 Sicherheitsdateien in allen 6 Projekten SHA-256-identisch zur Vorlage.
- Quelle: privates t0003-Test-Template, Commit 9a26559.
- Bericht: t019-b-acceptance-20261111-124401-555280/report.json.
- Keine produktiven Repository-Aenderungen.

### T022 Sicherheitsabschluss (2026-11-11)
- Ergebnis: PASS im dokumentierten Pruefumfang.
- Gitleaks: 21 Verzeichnisse, 36 Git-Historien und 11 Einzeldateien ohne Funde.
- Git fsck: 0 unerreichbare Objekte, 0 Prueffehler.
- Keine relevanten Archive oder Generator-Backups gefunden.
- T0003_READ_TOKEN in vier kontrollierten Test-Repositories nicht vorhanden.
- Frueherer temporaerer PAT: Widerruf zuvor geprueft.
- Nutzerbestaetigung vom 2026-11-11: nur lesender Template-Zugriff.
- Nutzerbestaetigung: keine Klartextweitergabe an ChatGPT, Copilot oder andere KI-Agenten.
- Restrisiko: Musterbasierte Erkennung und begrenzter Pruefumfang.
- Keine produktiven Repository-Aenderungen.

## T023 ? Finale Abnahmematrix (2026-11-11)

| Fall | Soll | Ist | Datum | Nachweis |
|---|---|---|---|---|
| T019-A | 6 Module: Plan/Apply/Check/Restore | PASS | 2026-11-10 | T019-A in acceptance.md |
| T019-B | 6 Module inkl. No-op/Restore | PASS | 2026-11-11 | t019-b-acceptance-20261111-124401-555280/report.json |
| Sicherheitsdateien | 3 Dateien in 6 Kopien identisch | PASS | 2026-11-11 | 18 SHA-256-Vergleiche |
| T020-C | Privater Template-Abruf in CI | PASS | bis 2026-11-11 | CI-Runs 42600283741 / 42600283876 |
| T020-D | Versionierter privater Basisvergleich | TEILWEISE | bis 2026-11-11 | Manueller Vergleich; Automatisierung offen |
| T030 | Privater update_check-Zugriff | PASS | bis 2026-11-11 | T030-Nachweis in acceptance.md |
| T021 | 5 Negativfaelle Windows/Linux | TEILWEISE | 2026-11-11 | Tests bestanden; einzelne Live-Faelle nicht nachgewiesen |
| Gitleaks lokal | Secret blockiert; harmlose Commits erlaubt | PASS | 2026-11-11 | Echte Commit-Tests |
| Gitleaks CI | Positiv- und Negativlauf | PASS | 2026-11-11 | Runs 43004546560 / 43010709119 |
| Merge-Sperre | Fehlerhafter Scan verhindert Merge | NICHT VERFUEGBAR | 2026-11-11 | GitHub HTTP 403; Tarifbeschraenkung |
| Lokale Hook-Einrichtung | Wiederholbar, ohne fremde Hooks zu ersetzen | PASS MANUELL | 2026-11-11 | setup_security.py; frischer Klon |
| T022 | Secret-Pruefung und Token-Kontrolle | PASS IM PRUEFUMFANG | 2026-11-11 | 21 Ordner, 36 Git-Historien, 11 Dateien, Nutzerbestaetigung |

### Unveraenderte Ausgangs-Repositories

- `t0003-ai-project-template`: aktuell `6e8363a7ac7d`; erwartete Sichtbarkeit, Template-Rolle und Actions-Einstellung bestaetigt.
- `t0004-ai-project-generator`: aktuell `c8d8d1fd165f`; erwartete Sichtbarkeit, Template-Rolle und Actions-Einstellung bestaetigt.
- `t0004-private-e2e-test`: aktuell `27acb9fe9021`; erwartete Sichtbarkeit, Template-Rolle und Actions-Einstellung bestaetigt.
- HEAD der beiden Original-Repositories mit frueheren Referenz-Commits abgeglichen.
- Fuer `t0004-private-e2e-test` ist kein unabhaengiger historischer HEAD-Vergleich belegt.
- Original-Repositories bleiben bis Gate 3 und der Freigabe unveraendert.
- Offene Punkte: T021-Restnachweise, Merge-Restrisiko, T024 und Gate 3.
