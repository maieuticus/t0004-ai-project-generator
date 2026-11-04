"""Checks for the not-yet-public PostgreSQL Compose projection."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from project_generator.docker_files import POSTGRES_IMAGE, WORKFLOW, docker_files
from project_generator.infrastructure_states import POSTGRESQL_PROJECTION, known_postgresql_projection


class PostgreSQLProjection(unittest.TestCase):
    def test_projection_keeps_legacy_docker_and_adds_postgres_service(self):
        modules = frozenset({"python"})
        old = docker_files(modules)
        generated = docker_files(modules, postgresql=True)
        self.assertEqual(old[".github/workflows/docker.yml"], WORKFLOW)
        self.assertNotIn(b"db-postgres", old["compose.yaml"])
        self.assertIn(POSTGRES_IMAGE.encode(), generated["compose.yaml"])
        self.assertIn(b"postgres_data:/var/lib/postgresql", generated["compose.yaml"])
        self.assertIn(b"file: .secrets/postgres_password", generated["compose.yaml"])
        self.assertIn(b"POSTGRES_INITDB_ARGS: --auth-host=scram-sha-256", generated["compose.yaml"])
        self.assertNotIn(b"ports:", generated["compose.yaml"])
        self.assertEqual(old[".dockerignore"], generated[".dockerignore"])
        self.assertIn(b"kein Datenbankbackup", generated["docs/POSTGRESQL.md"])
        self.assertIn(b"openssl rand -hex 32", generated[".github/workflows/docker.yml"])
        self.assertIn(b"docker compose up -d db-postgres", generated[".github/workflows/docker.yml"])
        self.assertIn(b"--force-recreate db-postgres", generated[".github/workflows/docker.yml"])
        self.assertIn(b"VALUES (\\$\\$persisted\\$\\$);", generated[".github/workflows/docker.yml"])

    def test_projection_is_closed(self):
        self.assertTrue(known_postgresql_projection(list(POSTGRESQL_PROJECTION)))
        self.assertFalse(known_postgresql_projection(list(POSTGRESQL_PROJECTION) + ["other"]))
        self.assertFalse(known_postgresql_projection(list(reversed(POSTGRESQL_PROJECTION))))


if __name__ == "__main__":
    unittest.main()
