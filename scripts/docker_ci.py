"""Exercise the installed generator and its real Compose artifacts in CI."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

COMMIT = "6e8363a7ac7d99220d743eea077dcd5cefda9042"
SOURCE = "https://github.com/maieuticus/t0003-ai-project-template.git"


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
        compose = project / "compose.yaml"
        if "app-python:" not in compose.read_text(encoding="utf-8"):
            raise RuntimeError("Python service is missing")
        backups += [install("--module", "typescript"), install("--module", "java")]
        for name in ("python", "typescript", "java"):
            if f"app-{name}:" not in compose.read_text(encoding="utf-8"):
                raise RuntimeError(f"Missing service {name}")
        if (project / ".git/index").read_bytes() != index:
            raise RuntimeError("Generator modified the Git index")
        noop = json.loads(generator("plan", "--infrastructure", "docker-compose", "--json"))
        if noop["conflicts"] or noop["operations"]:
            raise RuntimeError("Docker plan is not a no-op")
        saved = compose.read_bytes()
        compose.write_bytes(saved + b"# foreign\n")
        generator("restore", "--backup", backups[-1], expected=1)
        compose.write_bytes(saved)

        if sentinel.exists():
            raise RuntimeError("A generator command attempted to execute Docker")
        env["PATH"] = original_path

        docker = ["docker", "compose"]
        if args.config_only:
            try:
                run([*docker, "version"], cwd=project, env=env)
            except (FileNotFoundError, RuntimeError):
                print("Docker Compose unavailable: configuration check skipped")
            else:
                run([*docker, "config", "-q"], cwd=project, env=env)
                print("Docker Compose configuration OK")
        else:
            print(run(["docker", "version"], cwd=project, env=env))
            print(run([*docker, "version"], cwd=project, env=env))
            run([*docker, "config", "-q"], cwd=project, env=env)
            config = json.loads(run([*docker, "config", "--format", "json"], cwd=project, env=env))
            services = config["services"]
            if set(services) != {"app-python", "app-typescript", "app-java"}:
                raise RuntimeError("Unexpected Compose services")
            for name, service in services.items():
                for key in ("ports", "volumes", "devices", "cap_add", "privileged", "network_mode", "pid"):
                    if service.get(key):
                        raise RuntimeError(f"Unexpected {key} on {name}")
            run([*docker, "build"], cwd=project, env=env)
            messages = {"python": "Hello from project_app!", "typescript": "Hello from project-typescript-starter!",
                        "java": "Hello from project-java-starter!"}
            for name, message in messages.items():
                service = "app-" + name
                output = run([*docker, "run", "--rm", "--no-deps", service], cwd=project, env=env)
                if output.strip() != message:
                    raise RuntimeError(f"Unexpected {service} output: {output!r}")
                uid = run([*docker, "run", "--rm", "--no-deps", "--entrypoint", "id", service, "-u"],
                          cwd=project, env=env).strip()
                if not uid.isdigit() or int(uid) == 0:
                    raise RuntimeError(f"{service} runs as root: {uid!r}")
                run([*docker, "run", "--rm", "--no-deps", "--entrypoint", "sh", service, "-c", "exit 7"],
                    cwd=project, env=env, expected=7)
                print(f"{service}: build, output, non-root and exit status OK")

        for backup in reversed(backups):
            generator("restore", "--backup", backup)
        if (project / ".git/index").read_bytes() != index:
            raise RuntimeError("Restore modified the Git index")
        print("Reverse restore and Git index OK")


if __name__ == "__main__":
    main()
