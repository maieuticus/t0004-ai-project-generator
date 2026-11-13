# T028 – Produktiver Umstellungs- und Rollback-Plan

## B12 - Neuer Zielzustand 2026-11-13

Dieser Beschluss ersetzt die urspruenglich geplante
Privatisierung der beiden Original-Repositories.

### Verbindlicher Zielzustand

- t0003-ai-project-template: PUBLIC, isTemplate=true.
- t0004-ai-project-generator: PUBLIC.
- GitHub-Tarif: Free.
- Fuer beide: geschuetzter main-Branch, verpflichtende
  Pull-Request- und CI-Pruefungen inklusive Secret-Scan.
- Neue konkrete Projekte: standardmaessig PRIVATE als Zielvorgabe;
  Generatorverhalten und GitHub-Berechtigungen praktisch pruefen.
- Keine geplante Sichtbarkeitsumstellung der Originale.

### Abnahmebedingungen

1. Oeffentliche Inhalte und Historien auf
   vertrauliche Informationen pruefen.
2. Branch Protection fuer beide Originale einrichten.
3. Required Checks und Merge-Sperren praktisch verifizieren.
4. Ausstehende T019-Nachweise und T023 abschliessen.
5. Integrations-PR erst nach Freigabe und erfolgreicher CI mergen.
6. Privates E2E-Testprojekt erstellen und Generator pruefen.
7. T024-Bereinigung erst nach gesicherter Abnahme durchfuehren.

Die frueheren Phasen zur Privatisierung sind historisch
dokumentiert, aber nicht mehr zur Ausfuehrung freigegeben.

Stand: 2026-11-11
Status: Entwurf zur Abnahme. Keine Ausführungsfreigabe.

## 1. Ziel und Geltungsbereich

Die beiden Original-Repositories sollen nach erfolgreicher Integration und
Praxistests dauerhaft privat betrieben werden:

1. maieuticus/t0003-ai-project-template
2. maieuticus/t0004-ai-project-generator

Die isolierten Test-Repositories sind keine produktiven Ziel-Repositories.
Keine automatische Sichtbarkeitsänderung, Löschung oder Veröffentlichung.

## 2. Voraussetzungen – vor jeder Produktivänderung

- T019 bis T023: Ergebnisse und Einschränkungen aus acceptance.md prüfen.
- T024: cleanup-plan.md vorhanden; notwendige Testbelege aufbewahren.
- T025 bis T027: Dokumentationsentscheidungen versioniert.
- T029: Projektübergabe und lokale Abschlussprüfungen erfolgreich.
- Original-Repositories anhand Owner, Name, Sichtbarkeit, Default-Branch,
  Template-Eigenschaft und aktuellem Commit erneut identifizieren.
- Baseline-Commits und Änderungen seit der Abnahme vergleichen.
- Isolierte Änderungen vollständig prüfen und Übernahmeumfang festlegen.
- Geprüfte Backups beider Original-Repositories, einschließlich Git-Historie,
  sowie relevante GitHub-Metadaten und Abnahmenachweise sichern.
- Backups auf Lesbarkeit und Wiederherstellbarkeit prüfen.
- Bestehende öffentliche Forks, Kopien, Veröffentlichungen und externe
  Abhängigkeiten erfassen; ursprüngliche Veröffentlichungen sind durch
  Privatisierung nicht rückwirkend geschützt.
- Berechtigungen zum Ändern der Sichtbarkeit und zum Erstellen privater
  Projekte aus dem Template kontrollieren.
- Für private Quellen erforderliche minimale Leserechte sicher einrichten.
  Frühere widerrufene Testtokens nicht wiederverwenden.
- Schutzfunktionen und eventuelle GitHub-Plan-Einschränkungen dokumentieren.
- Geheimnis- und Historienprüfung im vereinbarten Umfang abschließen.
- Konkrete Prüfergebnisse und Freigabeentscheidung protokollieren.

STOP bei fehlender Voraussetzung oder unerklärter Abweichung.

## 3. Phase A – Änderungen kontrolliert integrieren

A1. t0003:
- Sicherheitskonfiguration und Security-Setup aus dem geprüften
  privaten Template-Test-Repository abgleichen.
- Änderungen über kontrollierten Branch/PR übernehmen.
- Keine Secrets, Testtokens oder Testartefakte übernehmen.
- Tests, Security-Checks und Template-Eignung prüfen.
- Erst nach Abnahme in den Default-Branch integrieren.

A2. t0004:
- Geprüfte Generatorimplementierung, Tests und Dokumentation
  aus dem isolierten Generator-Test-Repository übernehmen.
- Branch/PR und Review verwenden; kein Force-Push.
- Plan/Apply/Check, Modulvarianten, CI und Negativtests prüfen.
- COMPATIBLE und RELEASE getrennt bewerten; historische
  Referenzen nicht stillschweigend in Releases umdeuten.
- Erst nach Abnahme in den Default-Branch integrieren.

Beide Original-Repositories bleiben in Phase A zunächst öffentlich.
Vor jeder Veröffentlichung sicherstellen, dass kein vertraulicher
Inhalt in den zu übernehmenden Commits enthalten ist.

## 4. Phase B – Freigabepunkt

Nach erfolgreicher Integration:

- Aktuelle Commits und saubere Arbeitsverzeichnisse erfassen.
- CI-Ergebnisse, Privatzugriffsrechte und Backups bestätigen.
- Die verbleibenden bekannten Einschränkungen offen dokumentieren.
- Ausdrückliche Benutzerfreigabe für die Sichtbarkeitsumstellung
  beider namentlich benannten Original-Repositories einholen.

Ohne Freigabe kein Wechsel der Sichtbarkeit.

## 5. Phase C – Zuerst t0003 privat schalten

- Sichtbarkeit ausschließlich des Original-Repositories
  maieuticus/t0003-ai-project-template auf privat ändern.
- Sofort prüfen: private=True, isTemplate=True, korrekter
  Default-Branch und erwarteter HEAD.
- Mit berechtigter Identität tatsächlichen Lesezugriff prüfen.
- Neues privates Testprojekt aus dem produktiven privaten
  Template erstellen und Inhalt sowie Sichtbarkeit kontrollieren.
- Security-Setup, Workflow-Verhalten und benötigte Berechtigungen
  überprüfen. Keine Zugangsdaten protokollieren.
- Negative Zugriffsfälle weiterhin als Nicht-Erfolg behandeln.

STOP bei einem Fehler; t0004 noch nicht privat schalten.

## 6. Phase D – Danach t0004 privat schalten

Nur nach bestandener Phase C:

- Sichtbarkeit ausschließlich von
  maieuticus/t0004-ai-project-generator auf privat ändern.
- Sofort private=True, Default-Branch und HEAD überprüfen.
- Private Template-Referenzen, authentifizierten Zugriff,
  CI, Generator-Plan/Apply/Check und die relevanten
  Modul- und Sicherheitsprüfungen erneut kontrollieren.
- Neue private Projektanlage und anschließende Generator-
  Anwendung als End-to-End-Test dokumentieren.
- Bekannte GitHub-Schutzbeschränkungen separat bewerten.

STOP bei einem Fehler; keine automatische Ersatzquelle nutzen.

## 7. Rollback und Fehlerbehandlung

Vor einer Sichtbarkeitsänderung:
- Fehlgeschlagene Integration stoppen; Änderungen kontrolliert
  zurücknehmen oder korrigieren. Originalhistorie nicht überschreiben.
- Backups und Abnahmenachweise erhalten.

Nach der Privatisierung von t0003:
- t0003 privat lassen, t0004 zunächst unverändert lassen.
- Fehler innerhalb des privaten Repositories beheben oder
  aus geprüftem Backup wiederherstellen.
- Keine automatische Rückkehr zu öffentlich.

Nach der Privatisierung beider Repositories:
- Beide privat lassen und Änderungen kontrolliert korrigieren
  beziehungsweise aus geprüften Backups wiederherstellen.
- Sichtbarkeit nur nach gesonderter Risikoanalyse und ausdrücklicher
  Benutzerentscheidung ändern.

Eine erneute Veröffentlichung ist kein vollständiger Rollback:
öffentliche Forks bleiben außerhalb des privaten Originals;
verlorene Sterne/Watcher und vorher veröffentlichte Inhalte
werden dadurch nicht wiederhergestellt.

## 8. Abschluss und Bereinigung

- Tatsächliche Commits, Sichtbarkeit, Tests, bekannte Restrisiken
  und Benutzerfreigabe im Handoff dokumentieren.
- Beide Original-Repositories sowie neu erstellte Projekte prüfen.
- Erforderliche Security-Hooks pro Arbeitskopie einrichten.
- CI-Secrets auf Notwendigkeit prüfen und temporäre Tokens widerrufen.
- Erst danach cleanup-plan.md abarbeiten.
- Jedes lokale oder entfernte Testartefakt vor Löschung erneut
  identifizieren und einzeln freigeben.
- Produktive Repositories und dauerhaft benötigte Nachweise behalten.

## 9. Referenzen

- specs/002-private-github-access/spec.md
- specs/002-private-github-access/tasks.md
- specs/002-private-github-access/acceptance.md
- specs/002-private-github-access/cleanup-plan.md
- docs/GENERATOR_CONTRACT.md
- docs/PROJECT_HANDOFF.md
- https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility
- https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-repository-from-a-template
