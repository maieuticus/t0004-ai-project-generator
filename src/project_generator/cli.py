"""Command-line interface for the non-mutating generator safety core."""

import argparse
import json
import sys

from . import installed_version
from .config import ConfigurationError
from .plan import PathSafetyError, assess, check_prerequisites, create_plan, read_target


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="t0004-generator", description="t0004 generator safety core")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("version", help="installierte Generator-Version ausgeben")
    for name in ("check", "plan"):
        command = commands.add_parser(name, help="Projekt prüfen" if name == "check" else "lesenden Plan erstellen")
        command.add_argument("target", nargs="?", default=".", help="Zielprojekt (Standard: aktuelles Verzeichnis)")
        command.add_argument("--json", action="store_true", dest="as_json", help="maschinenlesbare Ausgabe")
    return parser


def _emit(data: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=True, sort_keys=True, indent=2))
        return
    if "plan_id" in data:
        print(f"Plan-ID (SHA-256): {data['plan_id']}")
        print(f"Ausgangsfingerabdruck (SHA-256, config/project.yaml): {data['source_fingerprint']}")
        print("Nur lesend; semantischer Diff (kein Patch):")
        if not data["operations"]:
            print("Keine Dateioperationen geplant.")
        for operation in data["operations"]:
            print(f"{operation['action']}: {operation['path']}\n{operation['diff']}", end="")
    else:
        print("Projektkonfiguration und grundlegende Kompatibilität: "
              + ("Konflikte" if data["conflicts"] else "OK"))
    for warning in data["warnings"]:
        print(f"Hinweis: {warning}")
    for conflict in data["conflicts"]:
        print(f"Konflikt: {conflict}")


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)
    try:
        if args.command == "version":
            print(installed_version())
            return 0
        content, missing = read_target(args.target)
        version = installed_version()
        if args.command == "check":
            _, conflicts, warnings = assess(content, version, missing)
            conflicts.extend(check_prerequisites())
            result = {"valid": not conflicts, "conflicts": conflicts, "warnings": warnings}
        else:
            result = create_plan(content, version, missing)
        _emit(result, args.as_json)
        return 1 if result["conflicts"] else 0
    except (ConfigurationError, PathSafetyError) as error:
        print(f"Fehler: {error}", file=sys.stderr)
        return 2
    except OSError:
        print("Fehler: Generator-Version ist nicht verfügbar.", file=sys.stderr)
        return 2
