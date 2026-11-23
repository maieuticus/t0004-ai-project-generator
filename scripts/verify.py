"""Run repository release checks or aggregate per-platform verification reports."""

import argparse
import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLATFORMS = ("Linux", "Windows")
COMMON_CRITERIA = (
    "repository-checks",
    "template-tests",
    "generator-tests",
    "historical-integrations",
    "candidate-integrations",
)
PRACTICAL_METHODS = {
    "new": "test_release_gate_new_python",
    "migrate": "test_release_gate_migrate_read_only",
}
VALID_STATUSES = {"passed", "failed", "not_verified"}
VALID_EVIDENCE_SOURCES = {"local", "hosted"}


def _evidence_source() -> str:
    return "hosted" if os.environ.get("GITHUB_ACTIONS") == "true" else "local"


class _RecordingResult(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.outcomes: dict[str, str] = {}

    def addSuccess(self, test):
        super().addSuccess(test)
        self.outcomes[test.id()] = "passed"

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.outcomes[test.id()] = "failed"

    def addError(self, test, err):
        super().addError(test, err)
        self.outcomes[test.id()] = "failed"

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.outcomes[test.id()] = "not_verified"

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self.outcomes[test.id()] = "failed"


def _verification_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for key in ("GH_TOKEN", "GITHUB_TOKEN", "T0004_REPO_TOKEN"):
        environment.pop(key, None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def _criterion(
    criterion_id: str,
    status: str,
    current_platform: str,
    evidence: str,
    evidence_source: str,
    blocker: str | None = None,
) -> dict[str, str]:
    result = {
        "criterion_id": criterion_id,
        "status": status,
        "platform": current_platform,
        "evidence": evidence,
        "evidence_source": evidence_source,
    }
    if blocker:
        result["blocker"] = blocker
    return result


def _run_command(
    criterion_id: str,
    command: list[str],
    environment: dict[str, str],
    evidence_source: str,
) -> dict[str, str]:
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as error:
        return _criterion(
            criterion_id,
            "not_verified",
            platform.system(),
            " ".join(command),
            evidence_source,
            f"could not start ({type(error).__name__})",
        )
    status = "passed" if result.returncode == 0 else "failed"
    blocker = None if status == "passed" else f"command exited with {result.returncode}"
    if status == "failed":
        detail = (result.stderr or result.stdout).strip()
        if detail:
            print(
                f"{criterion_id} failed:\n{detail[-4000:]}",
                file=sys.stderr,
            )
    return _criterion(
        criterion_id, status, platform.system(), " ".join(command), evidence_source, blocker,
    )


def _run_integration_class(class_name: str, environment: dict[str, str]):
    sys.path[:0] = [str(ROOT), str(ROOT / "scripts"), str(ROOT / "src")]
    try:
        module = importlib.import_module("integration.test_t0003_integration")
        test_class = getattr(module, class_name)
    except (ImportError, AttributeError) as error:
        return "not_verified", {}, f"integration tests unavailable ({type(error).__name__})"

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(test_class)
    result = _RecordingResult()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        previous_environment = dict(os.environ)
        try:
            os.environ.clear()
            os.environ.update(environment)
            suite.run(result)
        finally:
            os.environ.clear()
            os.environ.update(previous_environment)

    if result.failures or result.errors:
        status = "failed"
        blocker = f"{len(result.failures)} failed and {len(result.errors)} errored tests"
    elif result.testsRun == 0 or len(result.skipped) == result.testsRun:
        status = "not_verified"
        blocker = "integration suite did not produce a verified test result"
    else:
        status = "passed"
        blocker = None
    return status, result.outcomes, blocker


def _valid_mirrors(environment: dict[str, str]) -> bool:
    for key in ("T0004_T0003_MIRROR", "T0004_T0003_CANDIDATE_MIRROR"):
        value = environment.get(key)
        if not value:
            return False
        path = Path(value)
        if not path.is_absolute() or not path.is_dir():
            return False
    return True


def run_local_verification() -> dict[str, object]:
    current_platform = platform.system()
    evidence_source = _evidence_source()
    environment = _verification_environment()
    criteria = [
        _run_command(
            "repository-checks",
            [sys.executable, "-B", "scripts/check.py"],
            environment,
            evidence_source,
        ),
        _run_command(
            "template-tests",
            [sys.executable, "-B", "-m", "unittest", "discover", "-s", ".github/template-tests"],
            environment,
            evidence_source,
        ),
        _run_command(
            "generator-tests",
            [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"],
            environment,
            evidence_source,
        ),
    ]

    if current_platform not in PLATFORMS:
        blocker = f"{current_platform} is not a required release platform"
        criteria.extend(
            _criterion(
                name, "not_verified", current_platform, "not run", evidence_source, blocker,
            )
            for name in (*("historical-integrations", "candidate-integrations"),
                         *(f"{workflow}-{current_platform.lower()}" for workflow in PRACTICAL_METHODS))
        )
        return _local_report(current_platform, criteria, evidence_source)

    if not _valid_mirrors(environment):
        blocker = "both credential-free pinned template mirrors are required"
        criteria.extend(
            _criterion(
                name, "not_verified", current_platform, "not run", evidence_source, blocker,
            )
            for name in (
                "historical-integrations",
                "candidate-integrations",
                *(f"{workflow}-{current_platform.lower()}" for workflow in PRACTICAL_METHODS),
            )
        )
        return _local_report(current_platform, criteria, evidence_source)

    for class_name, criterion_id in (
        ("T0003Integration", "historical-integrations"),
        ("CandidateTemplateIntegration", "candidate-integrations"),
    ):
        status, outcomes, blocker = _run_integration_class(class_name, environment)
        criteria.append(_criterion(
            criterion_id, status, current_platform, class_name, evidence_source, blocker,
        ))
        if class_name == "T0003Integration":
            for workflow, method in PRACTICAL_METHODS.items():
                outcome = next(
                    (value for test_id, value in outcomes.items() if test_id.endswith(f".{method}")),
                    "not_verified",
                )
                reason = {
                    "failed": "practical test failed",
                    "not_verified": "required practical test did not produce a result",
                }.get(outcome)
                criteria.append(_criterion(
                    f"{workflow}-{current_platform.lower()}",
                    outcome,
                    current_platform,
                    method,
                    evidence_source,
                    reason,
                ))

    return _local_report(current_platform, criteria, evidence_source)


def _local_report(
    current_platform: str,
    criteria: list[dict[str, str]],
    evidence_source: str,
) -> dict[str, object]:
    statuses = {item["status"] for item in criteria}
    if "failed" in statuses:
        status = "failed"
    elif "not_verified" in statuses:
        status = "not_verified"
    else:
        status = "passed"
    return {
        "platform": current_platform,
        "evidence_source": evidence_source,
        "status": status,
        "criteria": criteria,
        "summary": f"{current_platform} local verification",
    }


def _not_verified_report(blockers: list[str]) -> dict[str, object]:
    return {"status": "not_verified", "criteria": [], "blockers": blockers}


def _read_report(path: str) -> tuple[dict[str, object] | None, str | None]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, f"invalid platform report: {Path(path).name}"
    if not isinstance(value, dict):
        return None, f"invalid platform report: {Path(path).name}"
    return value, None


def aggregate_reports(paths: list[str]) -> tuple[dict[str, object], int]:
    blockers: list[str] = []
    reports: dict[str, dict[str, object]] = {}
    for path in paths:
        report, error = _read_report(path)
        if error:
            blockers.append(error)
            continue
        name = report.get("platform")
        if not isinstance(name, str) or name not in PLATFORMS:
            blockers.append(f"invalid platform report: {Path(path).name}")
            continue
        if name in reports:
            blockers.append(f"duplicate platform report: {name}")
            continue
        if not isinstance(report.get("status"), str) or report["status"] not in VALID_STATUSES:
            blockers.append(f"invalid report status: {name}")
            continue
        evidence_source = report.get("evidence_source")
        if not isinstance(evidence_source, str) or evidence_source not in VALID_EVIDENCE_SOURCES:
            blockers.append(f"invalid evidence source: {name}")
            continue
        reports[name] = report

    criteria: list[dict[str, str]] = []
    required_by_platform = {
        name: (*COMMON_CRITERIA, *(f"{workflow}-{name.lower()}" for workflow in PRACTICAL_METHODS))
        for name in PLATFORMS
    }
    for name in PLATFORMS:
        report = reports.get(name)
        if report is None:
            blockers.append(f"missing platform report: {name}")
            for criterion_id in required_by_platform[name]:
                criteria.append(_criterion(
                    criterion_id,
                    "not_verified",
                    name,
                    "missing platform report",
                    "not_available",
                    f"missing platform report: {name}",
                ))
            continue

        entries = report.get("criteria")
        if not isinstance(entries, list):
            entries = []
            blockers.append(f"invalid criteria in {name} report")
        by_id: dict[str, dict[str, object]] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                blockers.append(f"invalid criterion in {name} report")
                continue
            criterion_id = entry.get("criterion_id")
            if not isinstance(criterion_id, str) or entry.get("platform") != name:
                blockers.append(f"mismatched criterion in {name} report")
                continue
            if entry.get("evidence_source") != report["evidence_source"]:
                blockers.append(f"mismatched evidence source in {name} report: {criterion_id}")
                continue
            if criterion_id in by_id:
                blockers.append(f"duplicate criterion in {name} report: {criterion_id}")
                continue
            if not isinstance(entry.get("status"), str) or entry["status"] not in VALID_STATUSES:
                blockers.append(f"invalid criterion status in {name} report: {criterion_id}")
                continue
            by_id[criterion_id] = entry

        for criterion_id in required_by_platform[name]:
            entry = by_id.get(criterion_id)
            if entry is None:
                blockers.append(criterion_id)
                criteria.append(_criterion(
                    criterion_id,
                    "not_verified",
                    name,
                    "missing criterion",
                    str(report["evidence_source"]),
                    "required criterion missing",
                ))
            else:
                criteria.append({
                    "criterion_id": criterion_id,
                    "status": str(entry["status"]),
                    "platform": name,
                    "evidence": str(entry.get("evidence", "")),
                    "evidence_source": str(entry["evidence_source"]),
                    **({"blocker": str(entry["blocker"])} if entry.get("blocker") else {}),
                })

        if report["status"] == "failed" and not any(
            item["status"] == "failed" for item in criteria if item["platform"] == name
        ):
            blockers.append(f"platform report failed: {name}")
        elif report["status"] == "not_verified" and not any(
            item["status"] == "not_verified" for item in criteria if item["platform"] == name
        ):
            blockers.append(f"platform report not verified: {name}")

    blockers.extend(
        item["criterion_id"]
        for item in criteria
        if item["status"] == "failed"
    )
    statuses = {item["status"] for item in criteria}
    if "failed" in statuses or any(blocker.startswith("platform report failed:") for blocker in blockers):
        status, exit_code = "not_ready", 1
    elif blockers or "not_verified" in statuses:
        status, exit_code = "not_verified", 2
    else:
        status, exit_code = "ready", 0
    return {
        "status": status,
        "criteria": criteria,
        "blockers": sorted(set(blockers)),
    }, exit_code


def _emit(report: dict[str, object], as_json: bool, *, aggregate: bool) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2))
        return
    if aggregate:
        print(f"Release readiness: {report['status']}")
    else:
        print(f"Local verification - {report['platform']}: {report['status']}")
    for criterion in report.get("criteria", []):
        detail = criterion.get("blocker") or criterion.get("evidence", "")
        print(f"{criterion['criterion_id']}: {criterion['status']} ({detail})")
    for blocker in report.get("blockers", []):
        print(f"Blocker: {blocker}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable JSON report")
    parser.add_argument(
        "--aggregate",
        nargs=2,
        metavar=("LINUX_REPORT", "WINDOWS_REPORT"),
        help="aggregate per-platform JSON reports",
    )
    args = parser.parse_args(argv)
    if args.aggregate:
        report, code = aggregate_reports(args.aggregate)
        _emit(report, args.json, aggregate=True)
        return code

    report = run_local_verification()
    _emit(report, args.json, aggregate=False)
    return {"passed": 0, "failed": 1, "not_verified": 2}[str(report["status"])]


if __name__ == "__main__":
    sys.exit(main())
