# Projektübergabe

Flüchtiger Arbeitsstand. Entscheidungen stehen in [DV_KONZEPT.md](DV_KONZEPT.md) und
[GENERATOR_CONTRACT.md](GENERATOR_CONTRACT.md). Git hat bei Widersprüchen Vorrang.

## Aktueller Stand

- Schritt 128C auf `feat/docker-infrastructure-pr-b`: Der separate Workflow
  `.github/workflows/docker-validation.yml` prüft unter Ubuntu 24.04 die echten
  generierten Images und Konsolenstarts sowie unter Windows die Sicherheitsregression
  und, sofern verfügbar, die Compose-Konfiguration. Die bestehende `ci.yml` richtet
  auf beiden Plattformen Temurin 25 ein und führt die vollständige Integration aus.
  Lokal sind Docker und Java nicht verfügbar; deren Laufzeitprüfungen und die
  Plattform-CI sind offen. Der geprüfte Konfigurationspfad von `scripts/docker_ci.py`
  bestand lokal bis zum ausdrücklich übersprungenen Compose-Aufruf. Der Benutzer hat
  einen Draft-PR für die CI-Abnahme ausdrücklich freigegeben; nicht eigenständig mergen.

- Schritt 128B auf `feat/docker-infrastructure-pr-b`, ausgehend von `cc4f5a9`:
  Die öffentliche Auswahl `--infrastructure docker-compose` und die festen
  Docker-Dateien sind über die bestehende Format-4-Engine integriert. Spätere
  Sprachmodule prüfen bekannte Docker-Dateien und erweitern Compose, Docker-Doku
  und Dockerfiles in derselben Transaktion. Die 33 zulässigen Reihenfolgen über
  alle sieben nichtleeren Sprachmengen konvergieren; Reverse-Restore ist getestet.
  Der installierte Generator bestand den zusätzlichen t0003-End-to-End-Test für
  Python → Docker → Java, einschließlich Git-Index und Restore. Projektcheck und
  `git diff --check` bestanden; die vollständige Generator-Suite bestand mit 216
  Tests, davon 24 plattformbedingt übersprungen. Die vollständige
  isolierte Integration meldete fünf Java-Laufzeitfehler und einen Java-Starterfehler,
  weil lokal kein JDK vorhanden ist; Docker ist ebenfalls nicht verfügbar. Reale
  Image-Builds, Java-Laufzeitabnahme und Plattform-CI stehen deshalb aus. Gemäß
  Auftrag kein Commit, Push oder PR vor erfolgreicher vollständiger Regression.

- Schritt 128A auf `feat/docker-infrastructure-pr-b`, ausgehend von `cc4f5a9`:
  PR #20 ist gemergt; die ältere Angabe unten zum offenen Review ist historisch.
  Ein reproduzierter Fehler bei Änderung einer installierten Sprachdatei nach dem
  Snapshot wurde durch vollständige erneute Modulplanung vor dem ersten Schreiben
  korrigiert. Bei registriertem Docker bindet der Modulplan die installierten
  Sprachdateien und ihre Attribute. Eine geschlossene neue Projektion ergänzt
  `docs/DOCKER.md`; alte PR-A-Projektionen bleiben gültig. Synthetische Compose-
  Operationen testen die bestehende Format-4-Engine, sind aber keine Docker-Erzeugung.
  Bis echte Dateizustände existieren, verweigert die Sprachplanung vorhandene Dateien
  auf den betreffenden Docker-Pfaden; PR B muss diese Prüfung gezielt ersetzen.
  Das Integritäts-Gate bleibt offen: Die echten Docker-Dateizustände und ihre
  Integration in die Sprachplanung sind noch nicht implementiert und daher nicht
  end-to-end geprüft. Projektcheck und `git diff --check` erfolgreich; vollständige
  Generator-Suite mit UTF-8 und Zugriff auf den lokalen Backup-Speicher: 207 Tests
  erfolgreich, 24 übersprungen. Ergänzte gezielte Attribut-, Metadaten- und
  synthetische Compose-Tests ebenfalls erfolgreich. Kein Commit, Push oder PR.

- Schritt 127 auf `feat/docker-infrastructure-pr-a`, ausgehend von `main` / `67cb088`:
  Docker Compose ist als feste interne Infrastrukturkennung `docker-compose@0.1.0`
  vorbereitet, getrennt von den drei Sprachmodulen. Der Format-4-Kern bindet die
  vollständige Sprachprojektion, die reservierten künftigen Docker-Pfade und den
  Infrastrukturzustand an Plan, Snapshot und Restore. PR A erzeugt keine Dockerfiles
  oder `compose.yaml`, bietet keine öffentliche CLI-Auswahl, verändert die acht
  Sprach-CI-Zustände nicht und führt keine Container oder Builds aus. Die gezielte
  Zustandsmatrix einschließlich Python→Docker→Java, Java→Docker→TypeScript,
  Python→TypeScript→Docker, Fremdprojektion nach Snapshot, Reverse Restore,
  Git-Index und Java-CRLF-Kompatibilität ist lokal erfolgreich. Projektcheck und
  201 Generator-Tests (24 plattformbedingt übersprungen) sind erfolgreich.
  Die Template-Basistests liefern 15 Erfolge; `test_speckit` wird nur durch die
  lokale PowerShell-Ausführungsrichtlinie blockiert. Die Installationsintegration
  besteht außerhalb der Java-Laufzeit: 15 von 21 Tests sind erfolgreich; fünf
  Java-Runtime-Fälle und der Java-Startertest scheitern, weil kein JDK bzw. kein
  `java` im lokalen `PATH` vorhanden ist. Keine Richtlinien- oder Systemänderung
  vorgenommen. Commit `bb59598` und [PR #20](https://github.com/maieuticus/t0004-ai-project-generator/pull/20)
  sind veröffentlicht. Die GitHub-Actions für Push und PR bestanden jeweils auf
  Ubuntu und Windows. Der PR bleibt für menschliches Review offen und wird nicht
  selbst gemergt.

- Schritt 124D auf `test/java-module-e2e`: Projektcheck, 16 Windows-Basistests,
  191 Generator-Tests (24 plattformbedingt übersprungen) und alle 21 Paket-
  Integrationstests erneut erfolgreich. Die lokale Ubuntu-Regression aus Schritt 124A
  und die beiden GitHub-Praxistests aus Schritt 124C sind ebenfalls erfolgreich.
  Der PR gegen `main` und seine finale Ubuntu-/Windows-CI stehen noch aus.

- Schritt 124C: Beide GitHub-Praxistests gegen unverändertes p9999/main `bb19b76`
  sind erfolgreich und ungemergt: Java allein [PR #4](https://github.com/maieuticus/p9999-ai-project-template-test-repo/pull/4)
  auf `6dfa9a70371d40cf61638c7918b5b4545344c08b`, alle drei Module
  [PR #5](https://github.com/maieuticus/p9999-ai-project-template-test-repo/pull/5)
  auf `0eee0c9afcc00153b749501a9f21a540599dcb25`. Push- und PR-Workflows auf
  Ubuntu und Windows erfolgreich. Lokale Projektchecks, Maven, JUnit, JAR und beim
  Drei-Modul-Projekt Python und TypeScript bestanden; frische Checkouts ergaben
  für jedes installierte Modul einen No-op. Die ursprünglichen temporären Testklone
  mit vorgemerkten Dateien wurden nicht verändert. WSL-Unzip wurde gesondert mit
  einem temporär entpackten Ubuntu-Paket geprüft. t0004/main bleibt `5ed1f5d`.

- Schritt 124A auf `test/java-module-e2e`, ausgehend von `main` / `5ed1f5d`:
  Git normalisierte den alten CRLF-Wrapper im Index auf LF; erst ein frischer Checkout
  änderte die Arbeitsbaum-Bytes. Die neue Vorlage liefert LF und die Modulplanung
  erkennt ausschließlich die exakt bekannte alte CRLF-Fassung zusätzlich. Restore
  prüft alte Snapshots unverändert streng. Git-Checkout, No-op und Restore sind in
  Integrationstests abgedeckt; den aktuellen Commitstand zeigt Git.
- Windows: 191 Generator-Tests erfolgreich (24 übersprungen), 21 Paket-Integrationstests
  erfolgreich, einschließlich Java-Matrix, sechs Reihenfolgen und Strategie A. Der
  Windows-Wrapper mit LF bestand Maven verify und JUnit. In Schritt 124B bestanden alle
  16 Windows-Basistests einschließlich `test_speckit` mit ausschließlich prozesslokalem
  `RemoteSigned`; die dauerhaften Richtlinienbereiche blieben unverändert. Ubuntu/WSL:
  191 Generator-Tests erfolgreich (7 übersprungen),
  21 Integrations- und 16 Basistests erfolgreich. Der generierte Unix-Wrapper hat kein
  Ausführungsbit; der dokumentierte `sh`-Aufruf funktioniert. Ohne `unzip` schlägt
  der originale Wrapper wegen eines Hashkonflikts beim tar.gz-Fallback sicher fehl;
  für den erfolgreichen Lauf wurde ein Ubuntu-unzip-Paket temporär entpackt.
  Finale GitHub-CI steht aus. p9999/main auf GitHub und lokal `bb19b76`, Baum gleich
  t0003 `6e8363a`; zwei temporäre Testklone enthalten vorgemerkte Dateien, keine
  Commits oder Pushes. t0003 und bestehende p9999-PRs blieben unverändert.

- Schritt 123 auf `feat/java-module-pr-b`, ausgehend von `main` / `da96c96`:
  Java ist über die bestehende Format-4-Engine integriert; drei feste Module und acht
  Zustände sind getestet. Windows: 188 Generator-Tests erfolgreich, 24 übersprungen;
  der ergänzte Java-Sicherheitstest und Projektcheck bestehen. Java-Build und Plattform-CI
  bleiben offen; lokal ist kein JDK verfügbar.
  PR A (#17) ist bereits gemergt; die folgende Angabe zu dessen offenem Review ist historisch.

- Schritt 121 auf `feat/java-module-pr-a`, ausgehend von `main` / `4c02d0c`:
  Die freigegebene Java-25-Startervorlage ist als Paketressource vorbereitet;
  eine öffentliche Modulauswahl und die Format-4-Integration gehören erst zu PR B.
  Maven 3.9.11 und Wrapper 3.3.4 sind festgelegt; der SHA-256 der Maven-ZIP
  wurde aus dem anhand des offiziellen SHA-512 geprüften Archiv berechnet.
  Plattform- und CI-Ergebnisse sind am endgültigen PR-Commit zu prüfen.
  Strategie A und B sowie der Forschungsbranch bleiben unverändert.

- Schritt 118A.2 auf `feat/strategy-b-baseline-plan`: Architektur für eine additive,
  ausdrücklich gekennzeichnete Migrationsbasis ist freigegeben. Der lesende Plan und das
  feste Paket sind implementiert; Strategie-B-Apply und -Restore sind nicht enthalten.
  Windows: Generator-Regression 180 Tests erfolgreich, 24 übersprungen; der erweiterte
  Basistest ist gesondert erfolgreich. Projektcheck erfolgreich. Template-Tests: 15 bestanden,
  Spec-Kit durch lokale PowerShell-Ausführungsrichtlinie blockiert. Alle 15 Integrationstests
  gegen gepinnte t0003-Stände erfolgreich; der Strategie-B-Test wurde nach der letzten
  Planänderung mit erneut installiertem Paket wiederholt. CI siehe aktuellen PR-Stand;
  kein Login oder Richtlinienwechsel vorgenommen.
  Die folgenden älteren Branch- und PR-Angaben sind historisch; PR #15 ist in main gemergt.

- Schritt 117 auf `feat/strategy-a-migration-apply`, ausgehend von `main` / `fad094f`:
  Strategie A bindet bestätigten Apply und Restore an die bestehende Format-4-Engine.
  Quelle und Ziel sowie der vollständige lesende Plan werden vor dem Import erneut geprüft;
  die Quellbytes werden im Speicher gehalten. Verzeichnisidentität und Änderungszeit sind
  zusätzlich an neue Migrationspläne gebunden. Snapshot und Restore bleiben in der
  bestehenden Mehrdatei-Engine. Die Plattform-CI und menschliches Review sind noch offen.
  Windows: 175 Generator-Tests (23 plattformbedingt übersprungen) und 14 Integrationstests
  mit isolierter echter t0003-Kopie bestanden. Linux steht noch aus. Die Basistests liefen
  in der Sandbox: 13 bestanden, zwei OpenSpec-Tests scheiterten am Netzwerkzugriff und
  Spec Kit am Windows-Zugriff. Der frühere Handoff zu Schritt 116 ist historisch; PR #14
  wurde in `main` gemergt. Der Branch ist für den PR gegen `main` vorbereitet.
- Schritt 116: Branch `feat/strategy-a-migration-plan` auf `main` / `f806194`.
  Das Analyze-Gate für eine lesende, explizite Strategie-A-Dateiplanung ist freigegeben.
  Der Plan bindet Quelle, Ziel, Auswahl und Zustandsfingerabdrücke und ist nicht ausführbar;
  Apply und Restore für Migrationsdateien bleiben Schritt 117. Die Ausführungsgrenzen stehen
  im Generator-Vertrag. Windows: Projektcheck und 13 Integrationstests erfolgreich;
  die Generator-Regression war mit 21 plattformbedingten Übersprüngen erfolgreich.
  Von 16 Basistests scheitert lokal `test_speckit` an der PowerShell-Ausführungsrichtlinie;
  diese wurde nicht geändert. Linux-/Windows-CI und menschliches Review sind offen.
- Schritt 113C: TypeScript-Vorlage und Regressionstest korrigiert. Lokale Regression
  mit aktueller isolierter Paketinstallation: 140 Generator-Tests bestanden, 21 unter
  Windows übersprungen; 12 Integrationstests bestanden, einschließlich Node-Build,
  Node-Tests und Python-Regression. Der Projektcheck ist erfolgreich. Von 16 Basistests
  bestanden 15; `test_speckit` scheiterte an der lokalen PowerShell-Ausführungsrichtlinie.
  Die CLI-EXE bleibt lokal durch die Anwendungsrichtlinie blockiert; der dokumentierte
  Python-Moduleinstieg wurde für die Integration genutzt. Keine Richtlinie wurde geändert.
- Schritt 113B: Reale p9999-Praxistests mit t0004/main `fc44849` erfolgreich.
  TypeScript allein: PR #2, Commit `7d3bbd167e3f1745a40d75441b9573f981cee8f7`;
  Python dann TypeScript: PR #3, Commit `3f5571a78a37743000f8b0c4e0935e99ec190d7c`.
  Beide Push- und PR-Workflows auf Ubuntu und Windows erfolgreich; die nur für das
  t0003-Repository vorgesehenen Template-Tests werden in p9999 übersprungen. Lokale
  Installation, Build, Tests und Beispiele erfolgreich. p9999/main blieb `bb19b76`,
  Python allein: PR #1, Commit `7b0de35093b68ab4c7c22838bd8023e7d48342f5`.
  Alle drei PRs bleiben offen und ungemergt. Die veraltete Zukunftsaussage in der
  generierten TypeScript-Dokumentation wurde in Schritt 113C korrigiert.
- Schritt 113A läuft auf `test/typescript-module-e2e`, ausgehend von `main` / `fc44849`.
  PR #12 ist gemergt; nachfolgende Branch- und PR-Angaben sind historisch. Der Git-Baum
  von p9999/main (`bb19b76`) und t0003 `6e8363a` ist identisch: `cc888863ebd53e4a7fde5fe198d4756b00009fc9`.
- Windows: Projektcheck erfolgreich; Generator-Tests 139 bestanden, 21 plattformbedingt
  übersprungen; Integration 12 bestanden. Diese umfasst die drei Modulkonfigurationen,
  npm ci, Node 24, Build, Node-Tests, Anwendung, Projektcheck und Restore. Sicherheitsfälle
  decken fremde und manipulierte Dateien, veraltete Pläne, alte Templates, Konflikte,
  beschädigte Snapshots und die Verweigerung ohne Teiländerung ab.
- Basistests: 15 bestanden, ein Fehler (`test_speckit`), da die lokale PowerShell-Richtlinie
  Skripte blockiert. Keine Richtlinienänderung. Der erfolgreiche Generatorlauf verwendete
  `PYTHONUTF8=1` außerhalb der Sandbox; Integration nutzte die lokale t0003-Referenz und
  `T0004_TEST_CLI_MODULE=1`, da die lokale Anwendungsrichtlinie die CLI-EXE blockiert.
  PR C und dessen CI-Abnahme stehen noch aus.
- Stand: 2026-11-02.
- Branch: `feat/typescript-module-pr-b`, ausgehend von `main` / `34b1b33`.
- PR A (#11) ist in `main` gemergt. Der alte Handoff war insoweit veraltet.
- Freigegebene Architektur: TypeScript unter `typescript/`, Node 24, strict/NodeNext,
  `node:test`, feste Abhängigkeiten und Lockfile; sequenzielle Python-/TypeScript-Installation
  über die vorhandene Format-4-Engine und Restore in umgekehrter Reihenfolge.
- PR B bindet TypeScript an CLI, Read-only-Plan, bestätigten Apply, Snapshot und Restore an.
  Vier feste CI-Zustände und kanonische Modulmetadaten unterstützen beide Reihenfolgen.
- t0003-Kompatibilität bleibt auf den geprüften Entwicklungsstand `6e8363a` beschränkt;
  der ursprüngliche Release-Commit wird weiterhin abgelehnt. Der echte GitHub-Template-Test
  mit p9999 war bereits erfolgreich; t0003 und p9999 werden hier nicht geändert.
- PR #12 ist gegen `main` offen, Implementierungsstand `1e19973`.
- Lokal erfolgreich: `python scripts/check.py`, 159 Generator-Tests (21 plattformbedingt
  übersprungen) und 10 Integrationstests gegen die gepinnten t0003-Commits. Der lokale
  Windows-Basistest `test_speckit` wird durch die PowerShell-Ausführungsrichtlinie blockiert;
  die übrigen 15 Basistests sind grün. Die Integrationstests liefen hier über
  `python -m project_generator`, weil die lokale Anwendungsrichtlinie erzeugte `.exe`
  blockiert. Die reguläre CLI läuft in der CI.
- Beide Linux- und beide Windows-CI-Läufe von PR #12 waren auf `1e19973` erfolgreich.

## Nächster Schritt

Den Draft-PR mit den vollständigen Ubuntu-/Windows- und Docker-CI-Läufen prüfen;
erst nach erfolgreicher Abnahme die Mergefähigkeit beurteilen.

## Risiken

Die korrigierte TypeScript-Dokumentationsvorlage ändert den bytegenau erwarteten
Modulzustand: Projekte aus PR B mit der alten Dokumentation melden bei späterer
Modulplanung einen Konflikt. Die Datei ist bewusst an die neue Vorlage anzupassen;
ein automatisches Überschreiben erfolgt nicht.

Apply und Restore setzen während des Aufrufs exklusiven Projektzugriff voraus. Nach
abruptem Abbruch oder fehlgeschlagener Protokollierung kann manuelle Wiederherstellung
erforderlich sein. `verify` als eigener Generatorbefehl und Releases bleiben offen.
