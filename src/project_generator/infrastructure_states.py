"""Fixed infrastructure identities and deterministic future file projections."""

from itertools import combinations

from .module_states import MODULES, DOCKER_MODULES

DOCKER_COMPOSE = "docker-compose"
POSTGRESQL = "postgresql"
INFRASTRUCTURE = {DOCKER_COMPOSE: "docker-compose@0.1.0", POSTGRESQL: "postgresql@0.1.0"}


def valid_infrastructure(values: object, modules: object) -> bool:
    """Validate the closed ordered state and its structural dependencies."""
    if not isinstance(values, list) or not isinstance(modules, (list, tuple, frozenset)):
        return False
    if values != [value for value in INFRASTRUCTURE.values() if value in values]:
        return False
    has_console_module = any(MODULES[name] in modules for name in DOCKER_MODULES)
    return not ((INFRASTRUCTURE[POSTGRESQL] in values and INFRASTRUCTURE[DOCKER_COMPOSE] not in values)
                or (INFRASTRUCTURE[DOCKER_COMPOSE] in values and not has_console_module))


# A distinct projection keeps historical Docker snapshot path lists unchanged.
POSTGRESQL_PROJECTION = ("config/project.yaml", "compose.yaml", ".github/workflows/docker.yml",
                         "docs/DOCKER.md", "docs/POSTGRESQL.md", ".gitignore")


def known_postgresql_projection(paths: object) -> bool:
    """Accept only the fixed PostgreSQL projection, in its canonical order."""
    return isinstance(paths, list) and tuple(paths) == POSTGRESQL_PROJECTION


def docker_projection(modules: frozenset[str]) -> tuple[str, ...]:
    """Return the PR-B Docker file paths for a known, non-empty language state."""
    docker_modules = modules & DOCKER_MODULES
    if not modules or not modules.issubset(MODULES) or not docker_modules:
        raise ValueError("Docker Compose benötigt mindestens ein bekanntes Sprachmodul.")
    return (
        ".dockerignore",
        "compose.yaml",
        *(f"Dockerfile.{module}" for module in MODULES if module in docker_modules),
    )


def docker_projection_with_docs(modules: frozenset[str]) -> tuple[str, ...]:
    """Closed PR-B projection; PR-A snapshots retain their original projection."""
    return (*docker_projection(modules), "docs/DOCKER.md")


def docker_projection_with_ci(modules: frozenset[str]) -> tuple[str, ...]:
    """PR-C projection; older snapshots keep their original path lists."""
    return (*docker_projection_with_docs(modules), ".github/workflows/docker.yml")


def known_docker_projection(paths: object) -> bool:
    """Accept the fixed PR-A and PR-B projections, never arbitrary paths."""
    if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
        return False
    expected = {
        projection(frozenset(names))
        for count in range(1, len(DOCKER_MODULES) + 1)
        for names in combinations(tuple(name for name in MODULES if name in DOCKER_MODULES), count)
        for projection in (docker_projection, docker_projection_with_docs, docker_projection_with_ci)
    }
    return tuple(paths) in expected
