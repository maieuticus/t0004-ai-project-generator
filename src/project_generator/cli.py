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
            selection = command.add_mutually_exclusive_group()
            selection.add_argument("--module", choices=("python", "typescript", "java", "react"),
                                   help="Technologiemodul planen")
            selection.add_argument("--infrastructure", choices=("docker-compose", "postgresql"),
                                   help="Infrastruktur planen")
    command = commands.add_parser("migrate", help="bestehendes Projekt ausschließlich lesend analysieren")
    command.add_argument("target", nargs="?", default=".", help="Quellprojekt (Standard: aktuelles Verzeichnis)")
    command.add_argument("--json", action="store_true", dest="as_json", help="maschinenlesbarer Analysebericht")
    command.add_argument("--destination", help="vorhandenes t0003-Ziel für Strategie A")
    command.add_argument("--file", action="append", dest="files", help="ausdrücklich ausgewählte relative Datei; wiederholbar")
    command.add_argument("--baseline", action="store_true", help="lesenden Strategie-B-Basisplan erstellen")
    command.add_argument("--confirm-agents", metavar="SHA256", help="exakten AGENTS.md-Ergebnis-Hash bestätigen")
    command = commands.add_parser("apply", help="bestätigten Plan ausführen")
    command.add_argument("target", nargs="?", default=".", help="Zielprojekt")
    command.add_argument("--plan", required=True, help="gespeicherter JSON-Plan")
    command.add_argument("--confirm", required=True, metavar="PLAN_ID", help="bestätigte Plan-ID")
    command.add_argument("--source", help="Quellprojekt für einen Strategie-A-Plan")
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
            backup_id = apply(args.target, args.plan, args.confirm, installed_version(), args.source)
            print(f"Apply geprüft und abgeschlossen. Backup-ID: {backup_id}")
            print("Der geschützte lokale Snapshot kann Secrets enthalten und darf nicht geteilt werden.")
            return 0
        if args.command == "restore":
            print(restore(args.target, args.backup))
            return 0
        if args.command == "migrate":
            if args.baseline:
                if args.destination is not None or args.files is not None:
                    raise PathSafetyError("Strategie B kann nicht mit Strategie A kombiniert werden.")
                from .baseline_plan import baseline_plan
                report = baseline_plan(args.target, installed_version(), args.confirm_agents)
                if args.as_json:
                    print(json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2))
                else:
                    print(f"Nicht ausführbarer Strategie-B-Plan: {report['plan_id']}")
                    print("AGENTS.md-Vorschau:\n" + report["agents_preview"])
                    for operation in report["operations"]:
                        print(f"create: {operation['path']} {operation['after_sha256']}")
                    for item in report["conflicts"]:
                        print(f"Konflikt: {item}")
                    for item in report["warnings"]:
                        print(f"Hinweis: {item}")
                return 1 if report["conflicts"] else 0
            if args.confirm_agents is not None:
                raise PathSafetyError("AGENTS-Bestätigung benötigt --baseline.")
            if args.destination is not None or args.files is not None:
                if not args.destination or not args.files:
                    raise PathSafetyError("Migrationsplanung benötigt --destination und mindestens ein --file.")
                from .migration_plan import migration_plan
                report = migration_plan(args.target, args.destination, args.files, installed_version())
                if args.as_json:
                    print(json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2))
                else:
                    print(f"Nicht ausführbarer Strategie-A-Plan: {report['plan_id']}")
                    for operation in report["operations"]:
                        print(f"{operation['action']}: {operation['path']}")
                    for conflict in report["conflicts"]:
                        print(f"Konflikt: {conflict}")
                    for warning in report["warnings"]:
                        print(f"Hinweis: {warning}")
                return 1 if report["conflicts"] else 0
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
        elif args.infrastructure:
            from .infrastructure import infrastructure_plan_target
            result, _ = infrastructure_plan_target(args.target, version, args.infrastructure)
        elif args.module in ("python", "typescript", "java", "react"):
            from .python_module import module_plan_target
            result, _ = module_plan_target(args.target, version, args.module)
        else:
            _, result = plan_target(args.target, version)
        _emit(result, args.as_json)
        if args.command == "new" and not args.as_json and not result.get("conflicts") and not result["operations"]:
            if args.infrastructure:
                print("Die Infrastruktur ist bereits korrekt eingerichtet.")
            elif args.module in ("python", "typescript", "java", "react"):
                label = {"python": "Python", "typescript": "TypeScript", "java": "Java",
                         "react": "React"}[args.module]
                print(f"Das {label}-Modul ist bereits korrekt eingerichtet.")
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
