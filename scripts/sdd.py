"""Select and set up the project's SDD tool (Spec Kit or OpenSpec) after user approval.

  python scripts/sdd.py select speckit|openspec [--integration NAME]
  python scripts/sdd.py status

`select` only prepares the chosen tool and records it in config/project.yaml.
Existing project files are never overwritten: files changed by the tool's
initialization are restored and reported. Switching to the other tool needs a
separate, approved migration plan and is refused here.
"""

import argparse
import os
from pathlib import Path
import subprocess
import sys

import projectcfg
import openspec_tool

ROOT = projectcfg.ROOT
DEFAULT_INTEGRATION = {"speckit": "copilot", "openspec": "github-copilot"}
SKIP = {".git", ".artifacts", "node_modules", "__pycache__"}


def snapshot() -> dict[str, bytes]:
    files = {}
    for directory, names, entries in os.walk(ROOT):
        names[:] = [n for n in names if n not in SKIP]
        for entry in entries:
            path = Path(directory) / entry
            if not path.is_symlink():
                files[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    return files


def protect_existing(before: dict[str, bytes]) -> list[str]:
    restored = []
    for relative, content in before.items():
        path = ROOT / relative
        if not path.is_file() or path.read_bytes() != content:
            path.write_bytes(content)
            restored.append(relative)
    return restored


def init_speckit(integration: str) -> str:
    sys.path.insert(0, str(ROOT / "scripts"))
    import specify_tool

    if (ROOT / ".specify").exists():
        raise ValueError(".specify/ existiert bereits. Für Updates: specify integration upgrade <integration>.")
    version = specify_tool.pinned_version()
    if subprocess.run([sys.executable, str(ROOT / "scripts/bootstrap_specify.py")], check=False).returncode:
        raise ValueError("Spec-Kit-Setup fehlgeschlagen.")
    python, env = specify_tool.runtime()
    command = [str(python), "-I", "-c", specify_tool.ENTRYPOINT, "init", "--here", "--force", "--non-interactive",
               "--ignore-agent-tools", "--integration", integration, "--script", "ps" if os.name == "nt" else "sh"]
    before = snapshot()
    result = subprocess.run(command, cwd=ROOT, env=env, check=False)
    restored = protect_existing(before)
    if restored:
        print("Vorhandene Dateien wurden nicht überschrieben (Spec-Kit-Fassung verworfen): " + ", ".join(restored))
    if result.returncode:
        raise ValueError("specify init ist fehlgeschlagen.")
    # Project workflow with the human analyze and review gates.
    workflow = ROOT / ".specify/workflows/project-sdd/workflow.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_bytes((ROOT / "scripts/speckit/project-sdd.workflow.yml").read_bytes())
    return version


def init_openspec(integration: str) -> str:
    if (ROOT / "openspec").exists():
        raise ValueError("openspec/ existiert bereits.")
    version = openspec_tool.pinned_version()
    before = snapshot()
    code = openspec_tool.run(["init", "--tools", integration, "--no-animation", ROOT.as_posix()])
    restored = protect_existing(before)
    if restored:
        print("Vorhandene Dateien wurden nicht überschrieben (OpenSpec-Fassung verworfen): " + ", ".join(restored))
    if code:
        raise ValueError("openspec init ist fehlgeschlagen.")
    return version


def select(tool: str, integration: str | None) -> int:
    text = projectcfg.read_text()
    current = projectcfg.get(text, "sdd", "tool")
    if current and current != tool:
        raise ValueError(f"Bereits '{current}' gewählt. Ein Wechsel braucht einen genehmigten Migrationsplan; "
                         "bestehende Specs nie still überschreiben.")
    if current == tool:
        raise ValueError(f"'{tool}' ist bereits eingerichtet.")
    chosen = integration or DEFAULT_INTEGRATION[tool]
    version = init_speckit(chosen) if tool == "speckit" else init_openspec(chosen)
    text = projectcfg.set_value(text, "sdd", "tool", tool)
    text = projectcfg.set_value(text, "sdd", "version", version)
    projectcfg.CONFIG.write_text(text, encoding="utf-8", newline="\n")
    print(f"SDD-Werkzeug '{tool}' {version} eingerichtet und in config/project.yaml vermerkt.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    choose = sub.add_parser("select", help="Werkzeug nach Freigabe einrichten")
    choose.add_argument("tool", choices=["speckit", "openspec"])
    choose.add_argument("--integration", help="Agenten-Integration des Werkzeugs (Standard: Copilot)")
    sub.add_parser("status", help="gewähltes Werkzeug anzeigen")
    args = parser.parse_args()
    try:
        if args.command == "status":
            text = projectcfg.read_text()
            print(f"SDD-Werkzeug: {projectcfg.get(text, 'sdd', 'tool') or 'noch nicht gewählt'} "
                  f"({projectcfg.get(text, 'sdd', 'version') or '-'})")
            return 0
        return select(args.tool, args.integration)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"SDD: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
