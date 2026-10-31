"""Command-line interface for safe, confirmed generator operations."""

import argparse
import json
import sys

from . import installed_version
from .config import ConfigurationError
from .migrate import analyze, emit_text
from .plan import (
    PathSafetyError, assess, check_prerequisites, plan_target, read_target,
)
from .transaction import TransactionError, apply, restore


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        if self.prog.endswith(" migrate") or getattr(self, "redact_migrate_errors", False):
            message = "Ungültige Argumente für migrate."
        super().error(message)


def _parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(prog="t0004-generator", description="t0004 generator safety core")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("version", help="installierte Generator-Version ausgeben")
    for name in ("check", "plan", "new"):
        help_text = "Projekt prüfen" if name == "check" else "lesenden Plan erstellen"
        command = commands.add_parser(name, help=help_text)
        command.add_argument("target", nargs="?", default=".", help="Zielprojekt (Standard: aktuelles Verzeichnis)")
        command.add_argument("--json", action="store_true", dest="as_json", help="maschinenlesbare Ausgabe")
        if name != "check":
            command.add_argument("--module", choices=("python",), help="Technologiemodul planen")
    command = commands.add_parser("migrate", help="bestehendes Projekt ausschließlich lesend analysieren")
    command.add_argument("target", nargs="?", default=".", help="Quellprojekt (Standard: aktuelles Verzeichnis)")
    command.add_argument("--json", action="store_true", dest="as_json", help="maschinenlesbarer Analysebericht")
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
        source = data.get("source_fingerprint", data.get("source_sha256"))
        print(f"Ausgangsfingerabdruck (SHA-256, config/project.yaml): {source}")
        kind = "geplante Dateioperationen" if data.get("format") == 4 else "semantischer Diff"
        print(f"Nur lesend; {kind} (apply benötigt den bestätigten JSON-Plan):")
        if not data["operations"]:
            print("Keine Dateioperationen geplant.")
        for operation in data["operations"]:
            print(f"{operation['action']}: {operation['path']}")
            if "diff" in operation:
                print(operation["diff"], end="")
        if data["backup"]:
            print(f"Geplanter geschützter Snapshot: {data['backup'].get('directory', data['backup']['id'])}")
    else:
        print("Projektkonfiguration und grundlegende Kompatibilität: "
              + ("Konflikte" if data["conflicts"] else "OK"))
    for warning in data.get("warnings", []):
        print(f"Hinweis: {warning}")
    for conflict in data.get("conflicts", []):
        print(f"Konflikt: {conflict}")


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = _parser()
    arguments = argv if argv is not None else sys.argv[1:]
    parser.redact_migrate_errors = bool(arguments and arguments[0] == "migrate")
    args = parser.parse_args(argv)
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
        if args.command == "migrate":
            report = analyze(args.target)
            if args.as_json:
                print(json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2))
            else:
                emit_text(report)
            return 0
        content, missing = read_target(args.target)
        version = installed_version()
        if args.command == "check":
            _, conflicts, warnings = assess(content, version, missing)
            conflicts.extend(check_prerequisites())
            result = {"valid": not conflicts, "conflicts": conflicts, "warnings": warnings}
        elif args.module == "python":
            from .python_module import python_plan_target
            result, _ = python_plan_target(args.target, version)
        else:
            _, result = plan_target(args.target, version)
        _emit(result, args.as_json)
        if args.command == "new" and not args.as_json and not result.get("conflicts") and not result["operations"]:
            if args.module == "python":
                print("Das Python-Modul ist bereits korrekt eingerichtet.")
            else:
                print("Die Generator-Version ist bereits aktuell.")
        return 1 if result.get("conflicts") else 0
    except (ConfigurationError, PathSafetyError) as error:
        print(f"Fehler: {error}", file=sys.stderr)
        return 2
    except TransactionError as error:
        print(f"Konflikt: {error}", file=sys.stderr)
        return 1
    except OSError:
        print("Fehler: Eine benötigte Datei oder die Generator-Version ist nicht verfügbar.", file=sys.stderr)
        return 2
