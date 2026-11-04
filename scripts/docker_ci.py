"""Exercise the installed generator and its real Compose artifacts in CI."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess
import sys
import tempfile
import time

COMMIT = "6e8363a7ac7d99220d743eea077dcd5cefda9042"
SOURCE = "https://github.com/maieuticus/t0003-ai-project-template.git"
POSTGRES_IMAGE = "postgres:18.6@sha256:3a4264520e121176619f54ff867d12774bc81e95e7b84db58d63bccdb6144b81"


def run(command, *, cwd, env, expected=0):
    result = subprocess.run(command, cwd=cwd, env=env, text=True, encoding="utf-8",
                            errors="replace", capture_output=True, check=False)
    if result.returncode != expected:
        raise RuntimeError(f"Command {command!r} exited {result.returncode}, expected {expected}:\n"
                           f"{result.stdout}\n{result.stderr}")
    return result.stdout


def run_binary(command, *, cwd, env, expected=0):
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, check=False)
    if result.returncode != expected:
        raise RuntimeError(f"Command {command!r} exited {result.returncode}, expected {expected}:\n"
                           f"{result.stdout.decode(errors='replace')}\n"
                           f"{result.stderr.decode(errors='replace')}")
    return result.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-only", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="t0004-docker-ci-") as tmp:
        base = Path(tmp)
        project = base / "project"
        env = dict(os.environ, T0004_BACKUP_HOME=str(base / "backup"), PYTHONUTF8="1",
                   PYTHONDONTWRITEBYTECODE="1", GIT_TERMINAL_PROMPT="0")
        source = os.environ.get("T0004_T0003_MIRROR", SOURCE)
        run(["git", "clone", "--no-checkout", source, str(project)], cwd=base, env=env)
        run(["git", "-c", "core.autocrlf=false", "checkout", "--detach", COMMIT], cwd=project, env=env)
        index = (project / ".git/index").read_bytes()
        plan_file = base / "plan.json"
        sentinel = base / "docker-called"
        guard = base / "guard"
        guard.mkdir()
        executable = guard / ("docker.cmd" if os.name == "nt" else "docker")
        executable.write_text('@echo called > "%DOCKER_CI_SENTINEL%"\n@exit /b 99\n' if os.name == "nt"
                              else '#!/bin/sh\nprintf called > "$DOCKER_CI_SENTINEL"\nexit 99\n', encoding="utf-8")
        if os.name != "nt":
            executable.chmod(0o755)
        original_path = env.get("PATH", "")
        env["PATH"] = str(guard) + os.pathsep + original_path
        env["DOCKER_CI_SENTINEL"] = str(sentinel)

        def generator(*arguments, cwd=project, expected=0):
            return run([sys.executable, "-m", "project_generator", *arguments],
                       cwd=cwd, env=env, expected=expected)

        def install(*selection):
            raw = generator("plan", *selection, "--json")
            plan = json.loads(raw)
            if plan["conflicts"] or not plan["operations"]:
                raise RuntimeError(f"Unexpected generator plan: {plan}")
            plan_file.write_text(raw, encoding="utf-8")
            generator("apply", "--plan", str(plan_file), "--confirm", plan["plan_id"])
            return plan["backup"]["id"]

        backups = [install("--module", "python"), install("--infrastructure", "docker-compose")]
        backups.append(install("--infrastructure", "postgresql"))
        compose = project / "compose.yaml"
        if "app-python:" not in compose.read_text(encoding="utf-8") or "db-postgres:" not in compose.read_text(encoding="utf-8"):
            raise RuntimeError("Python service is missing")
        backups += [install("--module", "typescript"), install("--module", "java")]
        for name in ("python", "typescript", "java"):
            if f"app-{name}:" not in compose.read_text(encoding="utf-8"):
                raise RuntimeError(f"Missing service {name}")
        if (project / ".git/index").read_bytes() != index:
            raise RuntimeError("Generator modified the Git index")
        saved = compose.read_bytes()
        compose.write_bytes(saved + b"# foreign\n")
        generator("restore", "--backup", backups[-1], expected=1)
        compose.write_bytes(saved)

        if sentinel.exists():
            raise RuntimeError("A generator command attempted to execute Docker")
        env["PATH"] = original_path

        run(["git", "add", "--all"], cwd=project, env=env)
        run(["git", "-c", "user.name=t0004 Docker CI", "-c",
             "user.email=t0004-docker-ci@example.invalid", "commit", "--quiet",
             "-m", "Commit generated PostgreSQL test project"], cwd=project, env=env)
        committed_index = (project / ".git/index").read_bytes()
        fresh_project = base / "fresh-checkout"
        run(["git", "clone", "--quiet", "--no-hardlinks", "--no-checkout",
             str(project), str(fresh_project)], cwd=base, env=env)
        run(["git", "-c", "core.autocrlf=false", "checkout", "--quiet", "--detach", "HEAD"],
            cwd=fresh_project, env=env)
        fresh_index = (fresh_project / ".git/index").read_bytes()
        for selection in (("--module", "python"), ("--module", "typescript"),
                          ("--module", "java"), ("--infrastructure", "postgresql")):
            plan = json.loads(generator("plan", *selection, "--json", cwd=fresh_project))
            if plan["conflicts"] or plan["operations"] or plan["backup"] is not None:
                raise RuntimeError(f"Fresh-checkout no-op failed for {selection}: {plan}")
        if (fresh_project / ".git/index").read_bytes() != fresh_index:
            raise RuntimeError("Fresh-checkout no-op modified the Git index")
        if run(["git", "status", "--porcelain"], cwd=fresh_project, env=env).strip():
            raise RuntimeError("Fresh-checkout no-op modified project files")
        print("Fresh-checkout no-op: Python, TypeScript, Java and PostgreSQL; "
              "Git index and worktree unchanged")

        secret_dir = project / ".secrets"
        secret_dir.mkdir(mode=0o700)
        password_file = secret_dir / "postgres_password"
        password = secrets.token_urlsafe(32)
        password_file.write_text(password, encoding="utf-8")
        password_file.chmod(0o600)
        if os.name == "posix":
            if stat.S_IMODE(secret_dir.stat().st_mode) != 0o700:
                raise RuntimeError("PostgreSQL secret directory permissions are not 0700")
            if stat.S_IMODE(password_file.stat().st_mode) != 0o600:
                raise RuntimeError("PostgreSQL secret file permissions are not 0600")
        run(["git", "check-ignore", "--quiet", ".secrets/postgres_password"],
            cwd=project, env=env)
        tracked = run(["git", "ls-files", "-z"], cwd=project, env=env).split("\0")
        if ".secrets/postgres_password" in tracked:
            raise RuntimeError("PostgreSQL secret file is tracked by Git")
        for relative in tracked:
            if relative and password.encode("utf-8") in (project / relative).read_bytes():
                raise RuntimeError("PostgreSQL test password appears in a versioned file")
        if password.encode("utf-8") in compose.read_bytes() or password_file.read_bytes() != password.encode("utf-8"):
            raise RuntimeError("PostgreSQL test password was not isolated correctly")

        project_name = "t0004pg" + secrets.token_hex(8)
        docker = ["docker", "compose", "--project-name", project_name]
        if not args.config_only:
            for resource_type in ("container", "volume", "network"):
                option = {"container": "ps", "volume": "volume", "network": "network"}[resource_type]
                command = (["docker", "compose", "--project-name", project_name, "ps", "-aq"]
                           if resource_type == "container" else
                           ["docker", option, "ls", "-q", "--filter",
                            f"label=com.docker.compose.project={project_name}"])
                if run(command, cwd=project, env=env).strip():
                    raise RuntimeError(f"Refusing to reuse existing Compose {resource_type} resources")
        runtime_started = False

        def compose_run(*arguments, expected=0):
            return run([*docker, *arguments], cwd=project, env=env, expected=expected)

        def postgres_authenticated(*arguments, expected=0):
            return compose_run(
                "exec", "-T", "db-postgres", "sh", "-ec",
                'PGPASSWORD="$(cat "$POSTGRES_PASSWORD_FILE")"; export PGPASSWORD; exec "$@"',
                "postgres-auth", *arguments, expected=expected,
            )

        def wait_for_health() -> None:
            container = compose_run("ps", "-q", "db-postgres").strip()
            if not container:
                raise RuntimeError("PostgreSQL container was not created")
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                status = run(["docker", "inspect", "--format", "{{.State.Health.Status}}", container],
                             cwd=project, env=env).strip()
                if status == "healthy":
                    return
                time.sleep(1)
            raise RuntimeError("PostgreSQL healthcheck did not become healthy")

        def postgres_sql(sql: str, *, database="project_db", expected=0) -> str:
            return compose_run(
                "exec", "-T", "db-postgres", "sh", "-ec",
                'PGPASSWORD="$(cat "$POSTGRES_PASSWORD_FILE")"; export PGPASSWORD; '
                'exec psql -X -h 127.0.0.1 -U project_admin -d "$1" '
                '-v ON_ERROR_STOP=1 -c "$2"',
                "postgres-sql",
                database,
                sql,
                expected=expected,
            )

        def postgres_query(sql: str, *, database="project_db") -> str:
            return compose_run(
                "exec", "-T", "db-postgres", "sh", "-ec",
                'PGPASSWORD="$(cat "$POSTGRES_PASSWORD_FILE")"; export PGPASSWORD; '
                'exec psql -X -A -t -F "|" -h 127.0.0.1 -U project_admin -d "$1" -c "$2"',
                "postgres-query",
                database,
                sql,
            ).strip()

        def cleanup_runtime() -> None:
            if runtime_started:
                for resource_type in ("container", "volume", "network"):
                    if resource_type == "container":
                        command = [*docker, "ps", "-aq"]
                    else:
                        command = ["docker", resource_type, "ls", "-q", "--filter",
                                   f"label=com.docker.compose.project={project_name}"]
                    resources = run(command, cwd=project, env=env).split()
                    for resource in resources:
                        label_path = ".Config.Labels" if resource_type == "container" else ".Labels"
                        inspect = ["docker", "inspect"] if resource_type == "container" else [
                            "docker", resource_type, "inspect"
                        ]
                        label = run([*inspect, "--format",
                                     f'{{{{ index {label_path} "com.docker.compose.project" }}}}',
                                     resource], cwd=project, env=env).strip()
                        if label != project_name:
                            raise RuntimeError(f"Refusing to clean unowned Docker {resource_type}")
                compose_run("down", "--volumes", "--remove-orphans")

        if args.config_only:
            print(compose_run("version"))
            compose_run("config", "-q")
            print("Docker Compose configuration OK")
        else:
            try:
                print(run(["docker", "version"], cwd=project, env=env))
                print(compose_run("version"))
                compose_run("config", "-q")
                config = json.loads(compose_run("config", "--format", "json"))
                services = config["services"]
                if set(services) != {"app-python", "app-typescript", "app-java", "db-postgres"}:
                    raise RuntimeError("Unexpected Compose services")
                for name, service in services.items():
                    for key in ("ports", "devices", "cap_add", "privileged", "network_mode", "pid"):
                        if service.get(key):
                            raise RuntimeError(f"Unexpected {key} on {name}")
                    if name.startswith("app-") and (service.get("volumes") or service.get("depends_on")):
                        raise RuntimeError(f"Unexpected dependency on {name}")
                database = services["db-postgres"]
                if database.get("image") != POSTGRES_IMAGE or database.get("ports"):
                    raise RuntimeError("PostgreSQL image or network projection is unsafe")
                if database.get("volumes") != [{"type": "volume", "source": "postgres_data",
                                                 "target": "/var/lib/postgresql", "volume": {}}]:
                    raise RuntimeError("PostgreSQL volume projection is unexpected")
                if not database.get("secrets"):
                    raise RuntimeError("PostgreSQL secret is missing")
                compose_run("build")
                runtime_started = True
                compose_run("up", "-d", "db-postgres")
                wait_for_health()
                print("PostgreSQL version: " + postgres_query("SHOW server_version;"))
                postgres_sql("CREATE TABLE runtime_probe (value text NOT NULL); INSERT INTO runtime_probe VALUES ('persisted');")
                output = postgres_sql("SELECT value FROM runtime_probe;")
                if "persisted" not in output:
                    raise RuntimeError("PostgreSQL did not return written test data")
                wrong_password = compose_run(
                    "exec", "-T", "db-postgres", "sh", "-ec",
                    "if PGPASSWORD=wrong-password psql -h 127.0.0.1 -U project_admin -d project_db -c 'SELECT 1'; "
                    "then exit 1; fi",
                )
                if wrong_password:
                    raise RuntimeError("Wrong PostgreSQL password unexpectedly produced output")
                compose_run("up", "-d", "--force-recreate", "db-postgres")
                wait_for_health()
                if "persisted" not in postgres_sql("SELECT value FROM runtime_probe;"):
                    raise RuntimeError("PostgreSQL data did not persist across container recreation")
                run_id = secrets.token_hex(8)
                expected_rows = [f"1|postgresql-pr-c-{run_id}-alpha",
                                 f"2|postgresql-pr-c-{run_id}-beta"]
                postgres_sql("CREATE TABLE backup_probe (id integer PRIMARY KEY, marker text NOT NULL); "
                             f"INSERT INTO backup_probe VALUES (1, 'postgresql-pr-c-{run_id}-alpha'), "
                             f"(2, 'postgresql-pr-c-{run_id}-beta');")
                archive = base / "postgresql-custom.dump"
                archive_bytes = run_binary(
                    [*docker, "exec", "-T", "db-postgres", "sh", "-ec",
                     'PGPASSWORD="$(cat "$POSTGRES_PASSWORD_FILE")"; export PGPASSWORD; '
                     'exec pg_dump --no-password --host=127.0.0.1 --username=project_admin '
                     '--dbname=project_db --format=custom'],
                    cwd=project, env=env,
                )
                archive.write_bytes(archive_bytes)
                if not archive_bytes or archive.is_relative_to(project):
                    raise RuntimeError("Logical PostgreSQL backup is empty or inside the project")
                archive_container_path = "/tmp/t0004-postgresql-custom.dump"
                compose_run("cp", str(archive), f"db-postgres:{archive_container_path}")
                archive_listing = postgres_authenticated("pg_restore", "--list", archive_container_path)
                if "backup_probe" not in archive_listing:
                    raise RuntimeError("Custom-format backup does not list the test table")
                print(f"Logical pg_dump: custom archive OK ({len(archive_bytes)} bytes, "
                      f"sha256 {hashlib.sha256(archive_bytes).hexdigest()})")

                postgres_sql("CREATE DATABASE restore_target;")
                postgres_authenticated(
                    "pg_restore", "--exit-on-error", "--no-owner", "--no-acl", "--no-password",
                    "--host=127.0.0.1", "--username=project_admin", "--dbname=restore_target",
                    archive_container_path,
                )
                schema_query = (
                    "SELECT table_name || ':' || string_agg(column_name || ':' || data_type, "
                    "',' ORDER BY ordinal_position) FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name IN ('runtime_probe', 'backup_probe') "
                    "GROUP BY table_name ORDER BY table_name;"
                )
                rows_query = "SELECT id::text || '|' || marker FROM backup_probe ORDER BY id;"
                runtime_query = "SELECT value FROM runtime_probe ORDER BY value;"
                source_snapshot = (
                    postgres_query(schema_query),
                    postgres_query("SELECT count(*) FROM backup_probe;"),
                    postgres_query(rows_query),
                    postgres_query(runtime_query),
                )
                restored_snapshot = (
                    postgres_query(schema_query, database="restore_target"),
                    postgres_query("SELECT count(*) FROM backup_probe;", database="restore_target"),
                    postgres_query(rows_query, database="restore_target"),
                    postgres_query(runtime_query, database="restore_target"),
                )
                expected_schema = "backup_probe:id:integer,marker:text\nruntime_probe:value:text"
                if source_snapshot != restored_snapshot:
                    raise RuntimeError("PostgreSQL source and restored database differ")
                if source_snapshot[0] != expected_schema or source_snapshot[1] != "2":
                    raise RuntimeError(f"Restored PostgreSQL schema or row count is unexpected: {source_snapshot}")
                if source_snapshot[2].splitlines() != expected_rows:
                    raise RuntimeError("Restored PostgreSQL test values do not match")
                print("Logical pg_restore: isolated target database schema, row count and test values match")

                invalid_archive = base / "invalid-postgresql.dump"
                invalid_archive.write_bytes(b"not-a-postgresql-custom-archive\n")
                invalid_container_path = "/tmp/t0004-invalid-postgresql.dump"
                compose_run("cp", str(invalid_archive), f"db-postgres:{invalid_container_path}")
                postgres_authenticated("pg_restore", "--list", invalid_container_path, expected=1)
                compose_run(
                    "exec", "-T", "db-postgres", "sh", "-ec",
                    "unset PGPASSWORD PGPASSFILE; exec pg_dump --no-password "
                    "--host=127.0.0.1 --username=project_admin --dbname=project_db --format=custom",
                    expected=1,
                )
                print("Backup error cases: invalid archive and missing credentials rejected")
                container = compose_run("ps", "-q", "db-postgres").strip()
                ports = json.loads(run(["docker", "inspect", "--format", "{{json .NetworkSettings.Ports}}", container],
                                       cwd=project, env=env))
                if ports.get("5432/tcp"):
                    raise RuntimeError("PostgreSQL unexpectedly has a host port")
                logs = compose_run("logs", "--no-color", "db-postgres")
                if password in logs:
                    raise RuntimeError("PostgreSQL logs exposed the test password")
                for relative in tracked:
                    if relative and password.encode("utf-8") in (project / relative).read_bytes():
                        raise RuntimeError("PostgreSQL test password appears in a versioned file")
                if password in logs or password.encode("utf-8") in archive_bytes:
                    raise RuntimeError("PostgreSQL test password appears in logs or backup archive")
                messages = {"python": "Hello from project_app!", "typescript": "Hello from project-typescript-starter!",
                            "java": "Hello from project-java-starter!"}
                for name, message in messages.items():
                    service = "app-" + name
                    output = compose_run("run", "--rm", "--no-deps", service)
                    if output.strip() != message:
                        raise RuntimeError(f"Unexpected {service} output: {output!r}")
                    uid = compose_run("run", "--rm", "--no-deps", "--entrypoint", "id", service, "-u").strip()
                    if not uid.isdigit() or int(uid) == 0:
                        raise RuntimeError(f"{service} runs as root: {uid!r}")
                    compose_run("run", "--rm", "--no-deps", "--entrypoint", "sh", service, "-c", "exit 7",
                                expected=7)
                    print(f"{service}: build, output, non-root and exit status OK")
            finally:
                cleanup_runtime()

        password_file.unlink()
        secret_dir.rmdir()

        for backup in reversed(backups):
            generator("restore", "--backup", backup)
        if (project / ".git/index").read_bytes() != committed_index:
            raise RuntimeError("Restore modified the Git index")
        print("Reverse restore and Git index OK")


if __name__ == "__main__":
    main()
