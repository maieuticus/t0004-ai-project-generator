"""Fixed infrastructure identities and deterministic future file projections."""

from itertools import combinations

from .module_states import MODULES

DOCKER_COMPOSE = "docker-compose"
INFRASTRUCTURE = {DOCKER_COMPOSE: "docker-compose@0.1.0"}


def docker_projection(modules: frozenset[str]) -> tuple[str, ...]:
    """Return the PR-B Docker file paths for a known, non-empty language state."""
    known = frozenset(MODULES)
    if not modules or not modules.issubset(known):
        raise ValueError("Docker Compose benötigt mindestens ein bekanntes Sprachmodul.")
    return (
        ".dockerignore",
        "compose.yaml",
        *(f"Dockerfile.{module}" for module in MODULES if module in modules),
    )


def known_docker_projection(paths: object) -> bool:
    """Validate a serialized PR-A projection without accepting arbitrary paths."""
    if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
        return False
    expected = {
        docker_projection(frozenset(names))
        for count in range(1, len(MODULES) + 1)
        for names in combinations(MODULES, count)
    }
    return tuple(paths) in expected
