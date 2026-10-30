"""Repository-owned Specify runtime. Standard library only; no console launcher."""

import base64
import json
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".artifacts/specify"
ENTRYPOINT = "from specify_cli import main; main()"


def pinned_version():
    version = (ROOT / ".specify-version").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError(".specify-version muss eine stabile Version wie MAJOR.MINOR.PATCH enthalten.")
    return version


def uv_command():
    # Prefer the private fallback, if bootstrap previously installed it.
    python = STATE / ("uv-windows" if os.name == "nt" else "uv-posix") / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if python.is_file():
        command = [str(python), "-I", "-m", "uv"]
        try:
            if subprocess.run(command + ["--version"], capture_output=True, check=False).returncode == 0:
                return command
        except OSError:
            pass
    uv = shutil.which("uv")
    if uv:
        return [uv]
    raise ValueError("uv fehlt. Zuerst python scripts/bootstrap_specify.py ausführen.")


def tool_environment():
    # Isolate repositories and platforms, including a checkout shared with WSL.
    platform = "windows" if os.name == "nt" else "posix"
    env = dict(os.environ)
    env["UV_TOOL_DIR"] = str(STATE / platform / "tools")
    env["UV_TOOL_BIN_DIR"] = str(STATE / platform / "bin")
    env["PATH"] = env["UV_TOOL_BIN_DIR"] + os.pathsep + env.get("PATH", "")
    return env


def tool_python(command, env):
    directory = subprocess.run(command + ["tool", "dir"], env=env, check=True,
                               capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
    if not directory or not Path(directory).is_absolute():
        raise ValueError("uv tool dir hat keinen absoluten Tool-Pfad geliefert.")
    return Path(directory) / "specify-cli" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def installed_version(python):
    if not python.is_file():
        return None
    result = subprocess.run(
        [str(python), "-I", "-c",
         "from importlib.metadata import version; import specify_cli; print(version('specify-cli'))"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def install_signature():
    return hashlib.sha256(pinned_version().encode() +
                          (ROOT / "scripts/specify-constraints.txt").read_bytes()).hexdigest()


def signature_path(env):
    return Path(env["UV_TOOL_DIR"]).parent / "installed.sha256"


def installation_matches(python, env):
    stamp = signature_path(env)
    return (installed_version(python) == pinned_version() and stamp.is_file()
            and stamp.read_text(encoding="utf-8").strip() == install_signature())


def runtime():
    version = pinned_version()
    command = uv_command()
    env = tool_environment()
    python = tool_python(command, env)
    if not installation_matches(python, env):
        raise ValueError(f"Spec Kit {version} fehlt oder ist beschädigt. "
                         "python scripts/bootstrap_specify.py ausführen; bei Bedarf mit --repair.")
    return python, env


def run(arguments):
    python, env = runtime()
    # Preserve the caller's cwd: Specify commands operate on the selected project.
    return subprocess.run([str(python), "-I", "-c", ENTRYPOINT, *arguments],
                          env=env, check=False).returncode


def main():
    try:
        arguments = sys.argv[1:]
        if len(arguments) == 2 and arguments[0] == "--repo-args-base64":
            arguments = json.loads(base64.b64decode(arguments[1], validate=True).decode("utf-8"))
            if not isinstance(arguments, list) or not all(isinstance(arg, str) for arg in arguments):
                raise ValueError("Ungültige Wrapper-Argumente.")
        return run(arguments)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Specify: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
