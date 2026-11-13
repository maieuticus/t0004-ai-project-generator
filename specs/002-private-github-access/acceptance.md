# Private GitHub Access – Acceptance Evidence

## B12 - Architekturentscheidung 2026-11-13

Status: Verbindliche Architekturentscheidung; T023 noch offen.

- t0003-ai-project-template bleibt PUBLIC und GitHub-Template.
- t0004-ai-project-generator bleibt PUBLIC.
- GitHub Free bleibt bestehen; kein GitHub Pro erforderlich.
- Neue Anwendungsprojekte sollen standardmaessig PRIVATE sein.
  Die tatsaechliche Umsetzung dieser Vorgabe ist zu pruefen.
- Beide Original-Repositories benoetigen verbindliche
  Branch Protection und erforderliche CI-/Secret-Scan-Checks.
- Durchsetzung der Merge-Sperren muss praktisch verifiziert werden.
- Vor finaler Abnahme sind oeffentliche Inhalte und Git-Historien
  auf Secrets, interne Informationen und personenbezogene Daten
  zu pruefen.
- Die fruehere GitHub-HTTP-403-Einschraenkung bezog sich auf
  private Repositories; sie ist kein Nachweis fuer einen
  erfolgreich eingerichteten Schutz der oeffentlichen Originale.
- T021: PASS im dokumentierten Pruefumfang.
- SC-005: Getestete PostgreSQL-Korrektur als Ausnahme genehmigt.
- SC-006: E2E-Nachweis PASS.
- Noch offene T019-Nachweise und T023 sind getrennt zu bewerten.
- T024 erfolgt erst nach erfolgreicher Abnahme.
- Die datierten frueheren Statusangaben bleiben als
  historische Zwischenstaende erhalten.

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

## Noch offen (Stand 2026-11-12)

- T019-A: manueller PostgreSQL-Check nach Korrektur offen;
  automatisierter Regressionstest bestanden.
- T019-B: formaler Nachweis der GitHub-Template-Erstellung
  gesondert zu bewerten; sechs Modulvarianten bestanden.
- T020-D: manueller Vergleich bestanden; Automatisierung
  nicht nachgewiesen.
- T021: Live-Negativfaelle und Fork-Credential-Isolation
  nicht vollstaendig nachgewiesen.
- SC-005: Freigabe der CLI-Fehlerkorrektur als Abweichung offen.
- SC-006: Live-Ablehnung der Release-Referenz offen.
- T023: vollstaendige Freigabe und CI-Abnahme offen.
- T024: finale Bereinigung nach Produktivabnahme.
- Privatisierung: noch nicht freigegeben.
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
- Actual fork pull-request execution: PR #34 from maieuticus-ci-test confirmed; CI runs 42207460291 and 42207460019 successful. Explicit private_auth=not_verified log evidence remains unavailable (GitHub API error).
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
| T020-D | Versionierter privater Basisvergleich | PASS (manueller Vergleich, AC3) | bis 2026-11-11 | Gepinnte Basis abgerufen; lokaler README-Unterschied erkannt und erhalten; keine automatisierte Generatorfunktion nachgewiesen |
| T030 | Privater update_check-Zugriff | PASS | bis 2026-11-11 | T030-Nachweis in acceptance.md |
| T021 | 5 Negativfaelle Windows/Linux | TEILWEISE | 2026-11-11 | Tests bestanden; einzelne Live-Faelle nicht nachgewiesen |
| Gitleaks lokal | Secret blockiert; harmlose Commits erlaubt | PASS | 2026-11-11 | Echte Commit-Tests |
| Gitleaks CI | Positiv- und Negativlauf | PASS | 2026-11-11 | Runs 43004546560 / 43010709119 |
| Merge-Sperre | Fehlerhafter Scan verhindert Merge | NICHT VERFUEGBAR | 2026-11-11 | GitHub HTTP 403; Tarifbeschraenkung |
| Lokale Hook-Einrichtung | Wiederholbar, ohne fremde Hooks zu ersetzen | PASS MANUELL | 2026-11-11 | setup_security.py; frischer Klon |
| T022 | Secret-Pruefung und Token-Kontrolle | PASS IM PRUEFUMFANG | 2026-11-11 | 21 Ordner, 36 Git-Historien, 11 Dateien, Nutzerbestaetigung |

### Historische Ausgangs-Snapshots (2026-11-11)

- `t0003-ai-project-template`: aktuell `6e8363a7ac7d`; erwartete Sichtbarkeit, Template-Rolle und Actions-Einstellung bestaetigt.
- `t0004-ai-project-generator`: aktuell `c8d8d1fd165f`; erwartete Sichtbarkeit, Template-Rolle und Actions-Einstellung bestaetigt.
- `t0004-private-e2e-test`: aktuell `27acb9fe9021`; erwartete Sichtbarkeit, Template-Rolle und Actions-Einstellung bestaetigt.
- HEAD der beiden Original-Repositories mit frueheren Referenz-Commits abgeglichen.
- Fuer `t0004-private-e2e-test` ist kein unabhaengiger historischer HEAD-Vergleich belegt.
- Original-Repositories bleiben bis Gate 3 und der Freigabe unveraendert.
- Offene Punkte: T021-Restnachweise, Merge-Restrisiko, T024 und Gate 3.

## A2 - Nachweisabgleich (2026-11-12)

- T019-A: Der Regressionstest
  test_postgresql_general_check_after_install
  prueft valid=true und conflicts=[].
  Manueller Check nach Restore nicht wiederholt.
  Kein Docker/PostgreSQL-Laufzeittest.

- SC-002 / T021: Synthetische Fehler fuer
  abgelaufenen Token und verweigerten Zugriff
  werden als nicht erfolgreich klassifiziert.
  Live-Tests fuer abgelaufene und falsch
  berechtigte Tokens fehlen. Fork-PR #34
  erfolgreich; expliziter Credential-Isolations-
  Lognachweis fehlt. Status: PARTIAL.

- SC-005: Commit 877df96 aendert genau eine
  Zeile in cli.py (allow_postgresql=True).
  Technisch notwendige Fehlerkorrektur mit
  Regressionstest; formale Abweichung von
  der Vorgabe unveraenderter Kerndateien.
  Freigabe der Abweichung noch offen.

- SC-006: Privater GitHub-API-Abruf erfolgreich:
  COMPATIBLE 6e8363a7ac7d99220d743eea077dcd5cefda9042
  RELEASE 964de8538d19cefcb483faff38f10124615a9783
  Unit-Test unterscheidet beide Referenzen.
  Live-Ablehnung der Release-Referenz bei
  Modulinstallation noch nicht nachgewiesen.
  Status: PARTIAL.

## T023 - Aktualisierte Bestandsaufnahme (2026-11-12)

| Repository | Privat | Template | Default | HEAD |
|---|---|---|---|---|
| t0003-ai-project-template | Nein | Ja | main | 4319e05abca3fe4362d94bf1a0f4e39966dbbef7 |
| t0004-ai-project-generator | Nein | Nein | main | c8d8d1fd165fc2d3ea01b88ab1702db24261179e |
| t0004-private-e2e-test | Ja | Nein | main | 27acb9fe9021a5d668efb52bf7a5e297da581640 |

- t0003 PR #4 wurde am 2026-11-11 gemergt.
- Die kompatible Referenz 6e8363a ist ein gepinnter
  Basiscommit und nicht der aktuelle t0003-main-HEAD.
- t0004 PR #35 bleibt offen und mergekonfliktfrei.
  Baseline Linux/Windows und Docker Windows waren erfolgreich;
  Docker Linux ist fehlgeschlagen.
- Neue CI-Laeufe sind derzeit nicht verlaesslich ausfuehrbar.
  Eine Budgetaenderung wurde nicht vorgenommen.
- T021 und SC-006 bleiben teilweise offen.
- SC-005 benoetigt eine formale Abweichungsentscheidung.
- T023 ist dokumentiert, aber noch nicht final freigegeben.
- Keine Privatisierung und keine finale T024-Bereinigung.

## B8 - Ergaenzende E2E-Nachweise (2026-11-12)

### SC-006 - Release-Ablehnung

- Beide private Git-Referenzen zuvor erfolgreich abgerufen.
- Gezielt ausgefuehrt:
  test_original_release_is_rejected
- Ergebnis: Ran 1 test, OK, TEST_EXIT=0.
- Test wurde nicht uebersprungen.
- Kompatibler Basiscommit bleibt unveraendert gepinnt.
- SC-006: PASS im dokumentierten E2E-Pruefumfang.

### T021 / SC-004 - Echter Fork-PR

- Fork-PR #34 von maieuticus-ci-test bestaetigt.
- CI-Runs: 42207460291 und 42207460019.
- Vier Jobs erfolgreich: Baseline Ubuntu/Windows,
  Docker Linux/Windows.
- In allen vier Jobs:
  Fetch pinned template refs (trusted push only)
  = skipped.
- In allen vier Jobs:
  Report template checks not verified for untrusted events
  = success.
- Workflowseitige Fork-Isolation damit nachgewiesen.
- Konkreter Inhalt der Report-Logs nicht separat verifiziert.
- Live-Negativtests fuer expired und wrong scope
  bleiben offen; synthetische Tests bestanden.
- T021 war bei B8 noch PARTIAL; Abschluss siehe B10.

### PR #35 - CI

- Commit fcdd994c329c8e8cfd167b731edd4568352ed0f5
- Alle 8 GitHub-Actions-Checks erfolgreich.
- Docker-Linux zuvor zeitweise durch DNS-Fehler gestoert.
- Kein Dockerfile-Fix erforderlich gewesen.
- SC-005-Abweichungsfreigabe und finale T023-Abnahme offen.

## B9 - Reale Negativtests und SC-005-Freigabe

### T021 - Realer anonymer Zugriff

- Privates Repository: t0003-private-access-test.
- Git-Zugriff ohne Zugangsdaten ausgefuehrt.
- Ergebnis: ACCESS_BLOCKED=True, GIT_EXIT=128.
- Bewertung: PASS fuer reale anonyme Zugriffsverweigerung.

### T021 - Realer falscher Repository-Umfang

- Separater Fine-grained-Test-Token.
- Erlaubtes Repository: t0004-private-generator-test.
- Nicht erlaubtes Repository: t0003-private-access-test.
- Autorisierter API-Zugriff: HTTP 200.
- Nicht autorisierter API-Zugriff: HTTP 404.
- Ergebnis: WRONG_SCOPE_ACCESS=DENIED, RESULT=PASS.
- Bewertung: PASS fuer reale Repository-Zugriffsbeschraenkung.
- Kein Tokenwert in dieser Abnahmedokumentation.

### SC-005 - Ausdruecklich genehmigte Ausnahme

- Benutzerentscheidung vom 2026-11-12: Ausnahme genehmigt.
- Betroffen: src/project_generator/cli.py.
- Korrektur: allow_postgresql=True.
- Bestehender Korrekturcommit: 877df96.
- Begruendung: PostgreSQL-Unterstuetzung muss korrekt
  an die Generator-Konfiguration weitergegeben werden.
- Die getestete Korrektur bleibt bestehen.
- Keine pauschale Freigabe weiterer Generator-Core-Aenderungen.
- Bewertung: Genehmigte, dokumentierte SC-005-Ausnahme.

### Verbleibende Freigabesperre

- T021: Realer Ablauf eines zuvor gueltigen Tokens
  noch nicht nachgewiesen.
- Synthetische Expired-Token-Tests bereits bestanden.
- Ein Token-Widerruf ersetzt keinen echten Ablauf.
- T021 war bei B9 noch PARTIAL; Abschluss siehe B10.
- T023 bleibt offen.
- PR #35 bleibt bis zur vollstaendigen Freigabe ungemergt.

## B10 - T021 Abschluss (2026-11-13)

### Abgelaufener Test-Token - realer Nachweis

- Die Testzugangskennung lautete `t021-negative-scope-20261112` (kein Authentifizierungswert).
- 2026-11-12: Erlaubtes privates Repository lieferte HTTP 200.
- Ablaufdatum laut GitHub: 2026-11-13.
- 2026-11-13: GitHub zeigte "This token has expired".
- 2026-11-13: Derselbe Token lieferte HTTP 401
  beim Zugriff auf das zuvor erlaubte Repository.
- Token wurde fuer diesen Nachweis nicht vorzeitig widerrufen.
- Ergebnis: EXPIRED_TOKEN=PASS.
- Kein Tokenwert im Repository oder in diesem Nachweis.

### T021 - Abschlussbewertung

- Fehlende Anmeldung: realer Negativtest PASS.
- Falscher Repository-Umfang: realer Negativtest PASS.
- Abgelaufener Token: realer Negativtest PASS.
- Untrusted Fork-PR: Workflow-Isolation real bestaetigt.
- Automatisierte Negativtests: zuvor bestanden.
- T021: PASS im dokumentierten Pruefumfang.
- Die frueheren PARTIAL-Angaben sind Zwischenstaende
  und durch diese Abschlussbewertung ueberholt.

### Weiterhin offen

- T023: Formale Gesamtabnahme.
- PR #35: Dokumentation noch nicht gepusht oder gemergt.
- GitHub-Branch-Protection-Einschraenkung bleibt dokumentiert.
- Sichtbarkeitswechsel beider Original-Repositories
  erfordert separate ausdrueckliche Freigabe.

## B19 - Required-Check-Merge-Sperren (2026-11-13)

### t0003 - Realer Negativtest

- Repository: maieuticus/t0003-ai-project-template (PUBLIC).
- Test-PR: #5, Testcommit cdea4369747c.
- Commit mit [skip ci]; kein erforderlicher Check ausgefuehrt.
- Erforderlich: gitleaks, template (ubuntu-latest),
  template (windows-latest).
- GitHub GraphQL: MERGEABLE=MERGEABLE, MERGE_STATE=BLOCKED.
- GitHub REST: mergeable=true, mergeable_state=blocked.
- HEAD_CHECK_COUNT=0.
- Ergebnis: T0003_MERGE_GUARD=PASS.

### t0004 - Realer Negativtest

- Repository: maieuticus/t0004-ai-project-generator (PUBLIC).
- Test-PR: #36, Testcommit a06533de52a6.
- Commit mit [skip ci]; kein erforderlicher Check ausgefuehrt.
- Erforderlich: gitleaks, baseline (ubuntu-latest),
  baseline (windows-latest), docker-linux, docker-windows.
- GitHub GraphQL: MERGEABLE=MERGEABLE, MERGE_STATE=BLOCKED.
- GitHub REST: mergeable_state=blocked.
- HEAD_CHECK_COUNT=0.
- Ergebnis: T0004_MERGE_GUARD=PASS.

### Bewertung und Grenzen

- Branch Protection fuer beide Original-Repositories
  zuvor per GitHub-API konfiguriert und verifiziert.
- Sperre bei fehlenden Required Checks fuer beide
  Repositories praktisch nachgewiesen.
- Es wurde kein Test-Merge ausgefuehrt.
- Ein absichtlich fehlgeschlagener CI-Check wurde
  nicht separat getestet.
- PR #35 hatte auf Commit 92676d8 alle
  zehn GitHub-Actions-Checks erfolgreich bestanden.
- Die Test-PRs #5 und #36 sind nach Sicherung
  dieser Nachweise kontrolliert zu bereinigen.
- T023 bleibt bis zur Gesamtabnahme offen.
