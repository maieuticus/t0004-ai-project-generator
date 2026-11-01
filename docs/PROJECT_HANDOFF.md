# Projektübergabe

Flüchtiger Arbeitsstand für den Wechsel zwischen Agenten und Umgebungen. Er ändert keine
Architekturentscheidungen (diese stehen in [DV_KONZEPT.md](DV_KONZEPT.md) und den Specs). Keine
Secrets, Tokens oder Zugangsdaten eintragen. Git hat bei Widersprüchen Vorrang.

## Aktueller Stand

- Stand: 2026-11-01
- Branch: `feat/typescript-module-pr-a`, ausgehend von `main` / `f90951e`.
- Aktive Aufgabe: PR #11 (TypeScript-Modul, PR A) im menschlichen Review-Gate; noch keine
  öffentliche TypeScript-Modulauswahl oder schreibende TypeScript-Planung.
- Erledigt:
  - PR #10 für die t0003-Integration ist laut Git-Historie gemergt. Acht bestehende
    Integrationstests bleiben erhalten; der kompatible t0003-Commit `6e8363a` ist
    weiterhin kein offizielles neues Release.
  - Architektur für `typescript@0.1.0` durch den Nutzer freigegeben: isolierter Ordner,
    Node 24, strict/NodeNext, `node:test`, feste Abhängigkeiten und Lockfile, bestehende
    Mehrdatei-Engine, sequenzielle Installation beider Module und Restore rückwärts.
  - PR A dokumentiert den Modulvertrag und paketiert acht feste Starterdateien. Ein neuer
    Integrationstest verwendet die installierten Paketdaten in einer temporären t0003-Kopie
    und prüft `npm ci --ignore-scripts`, Build, zwei Node-Tests und das ausführbare Beispiel.
  - Lokal unter Windows erfolgreich: Projektcheck, 16 Basistests, 138 Generator-Unit-Tests
    (19 plattformbedingt übersprungen) und 9 Integrationstests. Für den bekannten
    Spec-Kit-Basistest galt `RemoteSigned` nur im Process-Scope; danach wieder `Restricted`.
  - PR #11 ist geöffnet. Die Linux-/Windows-CI auf dem Implementierungsstand `c5c9a13`
    ist erfolgreich; ein anfänglicher Linux-Fehler im neuen Test wurde durch expliziten
    Python-Quellpfad vor der Paketinstallation behoben.
- Offen:
  - Menschliches Review-Gate für PR #11 durchführen; nicht automatisch mergen.
  - Öffentliche TypeScript-Planung, Apply, No-op und kombinierte Python-/TypeScript-Zustände
    folgen erst in späteren freigegebenen PRs. `verify` und Releases bleiben offen.
- Blocker: keiner für PR A; menschliches Review steht aus.
- Synchronisierung: Feature-Branch zu origin gepusht, PR #11 offen; Merge ist nicht beauftragt.

## Nächster Schritt

Das menschliche Review-Gate für PR #11 durchführen.

## Entscheidungen und Quellen

Die Gate-A-Matrix und freigegebene TypeScript-Architektur stehen in
[DV_KONZEPT.md](DV_KONZEPT.md). Der TypeScript-Modulvertrag und die Grenzen der vorhandenen
Engine stehen in [GENERATOR_CONTRACT.md](GENERATOR_CONTRACT.md).

## Probleme

Apply und Restore setzen exklusiven Projektzugriff während des jeweiligen Aufrufs voraus.
Nach abruptem Abbruch oder fehlgeschlagener Protokollierung kann ein Teilzustand manuelle
Wiederherstellung erfordern. Die lesende Migrationsanalyse setzt ein während ihres Aufrufs
unverändertes Quellprojekt voraus.
