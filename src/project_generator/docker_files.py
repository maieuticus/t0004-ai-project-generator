"""Deterministic, fixed Docker Compose artifacts for the three starter modules."""

from .module_states import MODULES

PYTHON_IMAGE = "python:3.13.13-slim-bookworm@sha256:355bfa66770995d7e9a0da4b3473b44d0cb451f6b56f5615ad9c39e3c4eca03f"
NODE_IMAGE = "node:24.11.1-bookworm-slim@sha256:48abc13a19400ca3985071e287bd405a1d99306770eb81d61202fb6b65cf0b57"
JDK_IMAGE = "eclipse-temurin:25.0.2_10-jdk-noble@sha256:b866059783e3dd2dd183937b713e77d0fd94d87ce7bdd4ed4a77d79e97a276cd"
JRE_IMAGE = "eclipse-temurin:25.0.2_10-jre-noble@sha256:a051234f864d7ab78bf0188c3c540ac06c711a3b566f00f246be37073cc99dce"

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


def docker_files(modules: frozenset[str]) -> dict[str, bytes]:
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
    return {".dockerignore": IGNORE, "compose.yaml": compose.encode("utf-8"),
            **{f"Dockerfile.{name}": DOCKERFILES[name] for name in MODULES if name in modules},
            "docs/DOCKER.md": doc.encode("utf-8")}
