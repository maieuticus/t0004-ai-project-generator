# T024 ? Bereinigungsplan

Datum: 2026-11-11
Status: Dokumentiert; endgueltige Bereinigung nach Gate 3.

## Sicherheitsstatus

- Fuenf GitHub-Test-Repositories sind privat.
- GitHub Actions sind in allen fuenf deaktiviert.
- Alle fuenf enthalten 0 Repository-Secrets.
- Frueherer temporaerer GitHub-PAT: Widerruf zuvor geprueft.
- T022-Secret-Scans bestanden im dokumentierten Pruefumfang.

## Dauerhaft behalten

- maieuticus/t0003-ai-project-template
- maieuticus/t0004-ai-project-generator

## Bis zur produktiven Integration behalten

- maieuticus/t0003-private-access-test
- maieuticus/t0004-private-generator-test
- maieuticus/t0004-private-e2e-test

## Nach erfolgreicher Freigabe entfernen

- maieuticus/t0003-secret-scan-e2e-test
- maieuticus/t019-public-to-private-test
- Anschliessend auch die drei zentralen Test-Repositories,
  sofern saemtliche Nachweise dauerhaft gesichert sind.

## Lokale Ressourcen

32 Elemente unter C:/Users/tim inventarisiert:
- Produktive Generator-Arbeitskopie behalten.
- Drei zentrale Test-Arbeitskopien bis Gate 3 behalten.
- 28 weitere Testdateien/-verzeichnisse nach
  Nachweissicherung einzeln pruefen und bereinigen.
- T019-B-Berichte und Testlaeufer bis zur Freigabe behalten.
- Original-Repositories niemals als Testartefakte loeschen.

## Freigabebedingungen vor Loeschungen

1. Gate 3 und produktive Integration erfolgreich abgeschlossen.
2. Urspruengliche Repositories und Datenschutz geprueft.
3. Abnahmenachweise dauerhaft versioniert und gesichert.
4. Rollback-Strategie dokumentiert und geprueft.
5. Jedes Loeschziel unmittelbar vorher erneut verifiziert.

Es wurden durch diesen Plan keine Ressourcen geloescht.
