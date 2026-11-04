# Docker Compose im Generator

Die Infrastruktur `docker-compose@0.1.0` benötigt mindestens ein installiertes
Sprachmodul sowie zur späteren Nutzung Docker Engine und das Compose-Plugin.
Ein lesender Plan und ein bestätigtes Apply werden wie folgt vorbereitet:

```text
t0004-generator plan PROJEKT --infrastructure docker-compose --json > docker-plan.json
t0004-generator apply PROJEKT --plan docker-plan.json --confirm PLAN-ID
```

Der Plan erzeugt `.dockerignore`, `compose.yaml`, `docs/DOCKER.md` und für jede
installierte Sprache das zugehörige Dockerfile. Nach der Installation startet
`docker compose build` den Build; `docker compose run --rm app-python`,
`app-typescript` beziehungsweise `app-java` startet den jeweils vorhandenen
Konsolen-Starter. Die Programme veröffentlichen keine Ports und sind keine Server.
Plan und Apply starten weder Docker noch Container.

Spätere Sprachmodule erweitern bekannte Docker-Dateien in derselben geschützten
Transaktion. Fehlende oder fremd geänderte Dateien sind Konflikte; fremde Compose-Dateien
werden nicht gemischt oder überschrieben. Restore erfolgt in umgekehrter Apply-Reihenfolge
und verweigert Fremdänderungen. Die Generator-Snapshots können Secrets enthalten.
Historische, nur intern durch PR A registrierte Docker-Zustände ohne Dateien sind
Konflikte; ihre alten Snapshots bleiben rücknehmbar.

Die Konsolen-Starter verwenden keine Volumes, Host-Mounts, Ports, Healthchecks,
privilegierten Container oder Docker-Sockets. Die Ausschlussliste verhindert nicht die
Aufnahme aller projektspezifischen Secrets und muss überprüft werden.

Nach einer vollständigen Docker-Installation kann PostgreSQL als feste Erweiterung geplant
werden. Sie ergänzt ausschließlich bekannte Dateien über dieselbe Format-4-Transaktion:

```text
t0004-generator plan PROJEKT --infrastructure postgresql --json > postgres-plan.json
t0004-generator apply PROJEKT --plan postgres-plan.json --confirm PLAN-ID
```

Die Erweiterung erzeugt keine Passwortdatei. Vor einem späteren Containerstart muss der
Benutzer `.secrets/postgres_password` lokal erstellen; der Generator ergänzt nur die exakt
bekannte t0003-`.gitignore` um diese Regel. Compose verwendet `db-postgres`, ein benanntes
Volume und einen Healthcheck ohne Host-Portfreigabe. Plan, Apply und Restore starten oder
stoppen keine Container und ändern oder löschen weder Volumes noch Datenbankdaten. Ein
Generator-Snapshot ist kein Datenbankbackup. Für Image-Updates offizielle Docker-Hub-Tags und
Mehrplattform-Digests neu prüfen, Vorlagen anpassen und die Build- und Laufzeittests erneut
ausführen.

Die festgelegten Mehrplattform-Digests wurden gegen die Docker-Hub-Tagmetadaten der
offiziellen Images geprüft:

| Image-Tag | SHA-256-Indexdigest |
|---|---|
| `python:3.13.13-slim-bookworm` | `355bfa66770995d7e9a0da4b3473b44d0cb451f6b56f5615ad9c39e3c4eca03f` |
| `node:24.11.1-bookworm-slim` | `48abc13a19400ca3985071e287bd405a1d99306770eb81d61202fb6b65cf0b57` |
| `eclipse-temurin:25.0.2_10-jdk-noble` | `b866059783e3dd2dd183937b713e77d0fd94d87ce7bdd4ed4a77d79e97a276cd` |
| `eclipse-temurin:25.0.2_10-jre-noble` | `a051234f864d7ab78bf0188c3c540ac06c711a3b566f00f246be37073cc99dce` |
| `postgres:18.6` | `3a4264520e121176619f54ff867d12774bc81e95e7b84db58d63bccdb6144b81` |
