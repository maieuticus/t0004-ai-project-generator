"""Exercise the installed generator and its real Compose artifacts in CI."""

import argparse
import json
import os
from pathlib import Path
import secrets
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

        def generator(*arguments, expected=0):
            return run([sys.executable, "-m", "project_generator", *arguments],
                       cwd=project, env=env, expected=expected)

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
        noop = json.loads(generator("plan", "--infrastructure", "postgresql", "--json"))
        if noop["conflicts"] or noop["operations"]:
            raise RuntimeError("PostgreSQL plan is not a no-op")
        saved = compose.read_bytes()
        compose.write_bytes(saved + b"# foreign\n")
        generator("restore", "--backup", backups[-1], expected=1)
        compose.write_bytes(saved)

        if sentinel.exists():
            raise RuntimeError("A generator command attempted to execute Docker")
        env["PATH"] = original_path

        secret_dir = project / ".secrets"
        secret_dir.mkdir(mode=0o700)
        password_file = secret_dir / "postgres_password"
        password = secrets.token_urlsafe(32)
        password_file.write_text(password, encoding="utf-8")
        password_file.chmod(0o600)
        if password.encode("utf-8") in compose.read_bytes() or password_file.read_bytes() != password.encode("utf-8"):
            raise RuntimeError("PostgreSQL test password was not isolated correctly")

        project_name = "t0004pg" + secrets.token_hex(8)
        docker = ["docker", "compose", "--project-name", project_name]
        runtime_started = False

        def compose_run(*arguments, expected=0):
            return run([*docker, *arguments], cwd=project, env=env, expected=expected)

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

        def postgres_sql(sql: str, *, expected=0) -> str:
            return compose_run(
                "exec", "-T", "db-postgres", "sh", "-ec",
                'PGPASSWORD="$(cat "$POSTGRES_PASSWORD_FILE")"; export PGPASSWORD; '
                'exec psql -h 127.0.0.1 -U project_admin -d project_db '
                '-v ON_ERROR_STOP=1 -c "$1"',
                "postgres-sql",
                sql,
                expected=expected,
            )

        def cleanup_runtime() -> None:
            if runtime_started:
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
                container = compose_run("ps", "-q", "db-postgres").strip()
                ports = json.loads(run(["docker", "inspect", "--format", "{{json .NetworkSettings.Ports}}", container],
                                       cwd=project, env=env))
                if ports.get("5432/tcp"):
                    raise RuntimeError("PostgreSQL unexpectedly has a host port")
                logs = compose_run("logs", "--no-color", "db-postgres")
                if password in logs:
                    raise RuntimeError("PostgreSQL logs exposed the test password")
                for path in ("compose.yaml", ".github/workflows/docker.yml", "docs/DOCKER.md",
                             "docs/POSTGRESQL.md", ".gitignore"):
                    if password in (project / path).read_text(encoding="utf-8"):
                        raise RuntimeError("Versioned PostgreSQL projection exposed the test password")
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
        if (project / ".git/index").read_bytes() != index:
            raise RuntimeError("Restore modified the Git index")
        print("Reverse restore and Git index OK")


if __name__ == "__main__":
    main()
