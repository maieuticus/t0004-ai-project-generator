# PostgreSQL-Compose-Erweiterung

`t0004-generator plan PROJEKT --infrastructure postgresql --json` setzt eine vollständig
installierte Docker-Compose-Infrastruktur und mindestens ein Sprachmodul voraus. Das bestätigte
Apply ergänzt `db-postgres` mit PostgreSQL 18.6 am geprüften Registry-Digest, einem benannten
Volume auf `/var/lib/postgresql`, Healthcheck, Compose-Secret und ohne Host-Portfreigabe.

Vor dem ersten Start erstellt der Benutzer lokal `.secrets/postgres_password` mit restriktiven
Zugriffsrechten. Die Datei ist in `.gitignore` ausgeschlossen; der Generator erzeugt sie nicht
und schreibt kein Passwort in Projektdateien oder Pläne. Neu initialisierte Datenverzeichnisse
verwenden SCRAM-TCP-Authentifizierung. Die Passwortdatei ersetzt oder rotiert kein Passwort in
einem bestehenden Volume.

Die lokale Docker-Abnahme prüft in einem zufällig benannten temporären Compose-Projekt
Healthcheck, TCP-Authentifizierung, Passwortablehnung, Schreib-/Lesezugriff, Persistenz nach
Container-Neuerstellung, fehlende Host-Portbindung und Geheimnisabwesenheit. Plan, Apply und
Restore führen keine Docker- oder Datenbankbefehle aus und verändern keine Volumes.

Ein Generator-Snapshot sichert ausschließlich Projektdateien. Er ist kein PostgreSQL-Backup und
stellt keine Datenbankdaten wieder her. `pg_dump`/`pg_restore` und weitergehende Recovery-
Nachweise gehören zu PostgreSQL PR C.
