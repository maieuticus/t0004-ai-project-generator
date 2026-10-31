"""Command-line interface for safe, confirmed generator operations."""

import argparse
import json
import sys

from . import installed_version
from .config import ConfigurationError
from .plan import (
    PathSafetyError, assess, check_prerequisites, plan_target, read_target,
)
from .transaction import TransactionError, apply, restore


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="t0004-generator", description="t0004 generator safety core")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("version", help="installierte Generator-Version ausgeben")
    for name in ("check", "plan", "new"):
        help_text = "Projekt prüfen" if name == "check" else "lesenden Plan erstellen"
        command = commands.add_parser(name, help=help_text)
        command.add_argument("target", nargs="?", default=".", help="Zielprojekt (Standard: aktuelles Verzeichnis)")
        command.add_argument("--json", action="store_true", dest="as_json", help="maschinenlesbare Ausgabe")
    command = commands.add_parser("apply", help="bestätigten Plan ausführen")
    command.add_argument("target", nargs="?", default=".", help="Zielprojekt")
    command.add_argument("--plan", required=True, help="gespeicherter JSON-Plan")
    command.add_argument("--confirm", required=True, metavar="PLAN_ID", help="bestätigte Plan-ID")
    command = commands.add_parser("restore", help="Generatoränderung kontrolliert zurücknehmen")
    command.add_argument("target", nargs="?", default=".", help="Zielprojekt")
    command.add_argument("--backup", required=True, metavar="BACKUP_ID", help="Backup-ID aus apply")
    return parser


def _emit(data: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=True, sort_keys=True, indent=2))
        return
    if "plan_id" in data:
        print(f"Plan-ID (SHA-256): {data['plan_id']}")
        print(f"Ausgangsfingerabdruck (SHA-256, config/project.yaml): {data['source_fingerprint']}")
        print("Nur lesend; semantischer Diff (apply benötigt den bestätigten JSON-Plan):")
        if not data["operations"]:
            print("Keine Dateioperationen geplant.")
        for operation in data["operations"]:
            print(f"{operation['action']}: {operation['path']}\n{operation['diff']}", end="")
        if data["backup"]:
            print(f"Geplanter geschützter Snapshot: {data['backup']['directory']}")
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
        if args.command == "apply":
            backup_id = apply(args.target, args.plan, args.confirm, installed_version())
            print(f"Apply geprüft und abgeschlossen. Backup-ID: {backup_id}")
            print("Der geschützte lokale Snapshot kann Secrets enthalten und darf nicht geteilt werden.")
            return 0
        if args.command == "restore":
            print(restore(args.target, args.backup))
            return 0
        content, missing = read_target(args.target)
        version = installed_version()
        if args.command == "check":
            _, conflicts, warnings = assess(content, version, missing)
            conflicts.extend(check_prerequisites())
            result = {"valid": not conflicts, "conflicts": conflicts, "warnings": warnings}
        else:
            _, result = plan_target(args.target, version)
        _emit(result, args.as_json)
        if args.command == "new" and not args.as_json and not result["conflicts"] and not result["operations"]:
            print("Die Generator-Version ist bereits aktuell.")
        return 1 if result["conflicts"] else 0
    except (ConfigurationError, PathSafetyError) as error:
        print(f"Fehler: {error}", file=sys.stderr)
        return 2
    except TransactionError as error:
        print(f"Konflikt: {error}", file=sys.stderr)
        return 1
    except OSError:
        print("Fehler: Eine benötigte Datei oder die Generator-Version ist nicht verfügbar.", file=sys.stderr)
        return 2
