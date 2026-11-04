"""Deterministic, fixed Docker Compose artifacts for the three starter modules."""

from .module_states import MODULES

PYTHON_IMAGE = "python:3.13.13-slim-bookworm@sha256:355bfa66770995d7e9a0da4b3473b44d0cb451f6b56f5615ad9c39e3c4eca03f"
NODE_IMAGE = "node:24.11.1-bookworm-slim@sha256:48abc13a19400ca3985071e287bd405a1d99306770eb81d61202fb6b65cf0b57"
JDK_IMAGE = "eclipse-temurin:25.0.2_10-jdk-noble@sha256:b866059783e3dd2dd183937b713e77d0fd94d87ce7bdd4ed4a77d79e97a276cd"
JRE_IMAGE = "eclipse-temurin:25.0.2_10-jre-noble@sha256:a051234f864d7ab78bf0188c3c540ac06c711a3b566f00f246be37073cc99dce"
# Docker Registry manifest index, verified 2026-11-04 for library/postgres:18.6.
POSTGRES_IMAGE = "postgres:18.6@sha256:3a4264520e121176619f54ff867d12774bc81e95e7b84db58d63bccdb6144b81"

DOCKERFILES = {
    "python": f'''FROM {PYTHON_IMAGE}
RUN python -m pip uninstall -y pip
WORKDIR /app
COPY src/project_app /app/project_app
USER 65532:65532
CMD ["python", "-m", "project_app"]
'''.encode("utf-8"),
    "typescript": f'''FROM {NODE_IMAGE} AS build
WORKDIR /app
COPY typescript/package.json typescript/package-lock.json ./
RUN npm ci --ignore-scripts
COPY typescript/tsconfig.json ./
COPY typescript/src ./src
RUN npm run build

FROM {NODE_IMAGE} AS runtime
RUN rm -rf /usr/local/lib/node_modules /usr/local/bin/npm /usr/local/bin/npx /opt/yarn* /usr/local/bin/yarn* /usr/local/bin/corepack
WORKDIR /app
COPY --from=build /app/package.json ./
COPY --from=build /app/dist ./dist
USER node
CMD ["node", "dist/main.js"]
'''.encode("utf-8"),
    "java": f'''FROM {JDK_IMAGE} AS build
RUN apt-get update && apt-get install -y --no-install-recommends unzip && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY java/ ./
RUN sh mvnw verify

FROM {JRE_IMAGE} AS runtime
WORKDIR /app
COPY --from=build /app/target/project-java-starter-0.1.0.jar ./app.jar
USER 65532:65532
CMD ["java", "-jar", "app.jar"]
'''.encode("utf-8"),
}

IGNORE = b'''# Local data, secrets and generated files
.git
.env
.env.*
**/.env
**/.env.*
**/*.pem
**/*.key
**/*secret*
**/backups
**/exports
**/.t0004-backup-*
**/node_modules
**/__pycache__
**/*.pyc
**/.venv
**/venv
**/target
**/dist
**/build
**/*.egg-info
'''

WORKFLOW = b'''name: Docker Compose
on:
  push:
  pull_request:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  compose:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - name: Validate, build and run services
        shell: bash
        run: |
          set -eu
          docker compose version
          docker compose config -q
          docker compose build
          while IFS= read -r service; do
            docker compose run --rm --no-deps "$service"
          done < <(docker compose config --services)
'''

POSTGRES_WORKFLOW = b'''name: Docker Compose
on:
  push:
  pull_request:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  compose:
    strategy:
      matrix:
        os: [ubuntu-24.04, windows-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - name: Validate Compose with isolated test secret
        shell: bash
        run: |
          set -eu
          umask 077
          mkdir .secrets
          openssl rand -hex 32 > .secrets/postgres_password
          trap 'docker compose down --volumes --remove-orphans || true; rm -rf .secrets' EXIT
          docker compose version
          docker compose config -q
      - name: Build and run console services
        if: runner.os == 'Linux'
        shell: bash
        run: |
          set -eu
          umask 077
          mkdir .secrets
          openssl rand -hex 32 > .secrets/postgres_password
          trap 'docker compose down --volumes --remove-orphans || true; rm -rf .secrets' EXIT
          docker compose build
          docker compose up -d db-postgres
          container="$(docker compose ps -q db-postgres)"
          test -n "$container"
          for attempt in $(seq 1 90); do
            if [ "$(docker inspect -f '{{.State.Health.Status}}' "$container")" = healthy ]; then
              break
            fi
            sleep 1
          done
          test "$(docker inspect -f '{{.State.Health.Status}}' "$container")" = healthy
          docker compose exec -T db-postgres sh -ec '
            PGPASSWORD="$(cat "$POSTGRES_PASSWORD_FILE")"; export PGPASSWORD
            psql -h 127.0.0.1 -U project_admin -d project_db -v ON_ERROR_STOP=1 \
              -c "CREATE TABLE runtime_probe (value text NOT NULL); INSERT INTO runtime_probe VALUES (\\$\\$persisted\\$\\$);"
            test "$(psql -h 127.0.0.1 -U project_admin -d project_db -Atc "SELECT value FROM runtime_probe;")" = persisted
            if PGPASSWORD=wrong-password psql -h 127.0.0.1 -U project_admin -d project_db -c "SELECT 1"; then
              exit 1
            fi
          '
          docker compose up -d --force-recreate db-postgres
          container="$(docker compose ps -q db-postgres)"
          for attempt in $(seq 1 90); do
            if [ "$(docker inspect -f '{{.State.Health.Status}}' "$container")" = healthy ]; then
              break
            fi
            sleep 1
          done
          test "$(docker inspect -f '{{.State.Health.Status}}' "$container")" = healthy
          docker compose exec -T db-postgres sh -ec '
            PGPASSWORD="$(cat "$POSTGRES_PASSWORD_FILE")"; export PGPASSWORD
            test "$(psql -h 127.0.0.1 -U project_admin -d project_db -Atc "SELECT value FROM runtime_probe;")" = persisted
          '
          if [ "$(docker inspect -f '{{with index .NetworkSettings.Ports "5432/tcp"}}mapped{{end}}' "$container")" = mapped ]; then
            exit 1
          fi
          for service in app-python app-typescript app-java; do
            if docker compose config --services | grep -Fxq "$service"; then
              docker compose run --rm --no-deps "$service"
            fi
          done
'''


def docker_files(modules: frozenset[str], postgresql: bool = False) -> dict[str, bytes]:
    """Return the complete trusted projection in canonical module order."""
    if not modules or not modules.issubset(MODULES):
        raise ValueError("Docker Compose benötigt mindestens ein bekanntes Sprachmodul.")
    compose = "services:\n" + "".join(
        f"  app-{name}:\n    build:\n      context: .\n      dockerfile: Dockerfile.{name}\n"
        for name in MODULES if name in modules
    )
    commands = "".join(f"docker compose run --rm app-{name}\n" for name in MODULES if name in modules)
    doc = f'''# Docker Compose

Voraussetzung sind Docker Engine und das Compose-Plugin. Die Starter sind Konsolenprogramme;
sie stellen keinen dauerhaften Dienst bereit und veröffentlichen keine Ports.
Die Infrastruktur wird nach mindestens einem Sprachmodul mit folgendem lesenden Plan
und anschließend bestätigtem Apply eingerichtet:

```text
t0004-generator plan PROJEKT --infrastructure docker-compose --json > docker-plan.json
t0004-generator apply PROJEKT --plan docker-plan.json --confirm PLAN-ID
```

```text
docker compose build
{commands}```

Ein später installiertes Sprachmodul erweitert Compose und ergänzt sein Dockerfile in
derselben geschützten Generatortransaktion. Fremde oder veränderte Docker-Dateien führen
zum Konflikt; es erfolgt kein YAML-Merge und kein Überschreiben. Snapshots sind in
umgekehrter Apply-Reihenfolge zurückzunehmen. Eine Fremdänderung verhindert Restore.

Die Container erhalten keine Volumes, Host-Mounts, Docker-Sockets oder privilegierten Rechte.
Build-Kontexte dürfen dennoch keine Geheimnisse enthalten; die Ausschlussliste ist an das
Projekt anzupassen. PostgreSQL ist nicht implementiert.

Images sind auf Version und Mehrplattform-Digest festgelegt. Für ein Update offizielle
Docker-Hub-Tags und Digests prüfen, die Vorlagen ändern und alle Builds und Tests wiederholen.
'''
    if postgresql:
        compose += f'''  db-postgres:
    image: {POSTGRES_IMAGE}
    environment:
      POSTGRES_USER: project_admin
      POSTGRES_DB: project_db
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password
      POSTGRES_INITDB_ARGS: --auth-host=scram-sha-256
    secrets:
      - postgres_password
    volumes:
      - postgres_data:/var/lib/postgresql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U project_admin -d project_db"]
      interval: 10s
      timeout: 5s
      retries: 5
volumes:
  postgres_data:
secrets:
  postgres_password:
    file: .secrets/postgres_password
'''
        doc = doc.replace("Die Container erhalten keine Volumes, Host-Mounts, Docker-Sockets oder privilegierten Rechte.\n", "Die Konsolenstarter erhalten keine Volumes, Host-Mounts, Docker-Sockets oder privilegierten Rechte.\n")
        doc = doc.replace("PostgreSQL ist nicht implementiert.", "Für PostgreSQL siehe docs/POSTGRESQL.md.")
    result = {".dockerignore": IGNORE, "compose.yaml": compose.encode("utf-8"),
            **{f"Dockerfile.{name}": DOCKERFILES[name] for name in MODULES if name in modules},
            "docs/DOCKER.md": doc.encode("utf-8"), ".github/workflows/docker.yml": WORKFLOW}
    if postgresql:
        from .postgresql_files import POSTGRESQL_DOC
        result[".github/workflows/docker.yml"] = POSTGRES_WORKFLOW
        result["docs/POSTGRESQL.md"] = POSTGRESQL_DOC
    return result
