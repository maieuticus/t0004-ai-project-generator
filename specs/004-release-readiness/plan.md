# Implementation Plan: Release Readiness Verification

**Branch**: `feature/verify-release-prerequisites` | **Date**: 2026-11-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-release-readiness/spec.md`

## Summary

Add a repository-local `verify` entrypoint that runs the existing local checks and
the release-gate test suites, including the four `new`/`migrate` scenarios. Each
Linux/Windows CI matrix job emits a JSON evidence report; a final aggregate job
combines both reports into the single criterion-level release outcome. A local
invocation reports only evidence from its own platform and must not claim the
other platform passed. Reuse the pinned credential-free template mirrors and
existing test infrastructure; do not make verification depend on private
authentication or publish release artifacts.

The proposed entrypoint is `python scripts/verify.py`, not an installed
`t0004-generator verify` target-project command. This keeps repository-wide
release verification separate from the installed CLI's operations on a user's
project; this interface choice is an explicit design point for the Analyze gate.

## Technical Context

**Language/Version**: Python 3.11+ (CI currently uses Python 3.13)

**Primary Dependencies**: Python standard library for the runner; Git for pinned
integration fixtures; existing Node.js 24 and Java 25 toolchains for relevant
template checks. No new runtime package dependencies.

**Storage**: No persistent storage. Tests and mirrors use temporary directories or
explicitly supplied local mirror paths.

**Testing**: `unittest`; existing static/project check; pinned t0003 integration
tests; Linux/Windows GitHub Actions matrix.

**Target Platform**: Linux and Windows are required for the release matrix.
Codespaces remains an additional platform check when its execution is available.

**Project Type**: Python CLI/generator repository with repository-level validation
scripts and installed target-project commands.

**Performance Goals**: No interactive latency target. Verification may run the
complete repository and integration suites and must report which checks ran.

**Constraints**: Do not run or report private template authentication, read
credentials, create PRs/tags/releases, or alter release metadata. Missing pinned
source, report, or platform evidence is not a pass. The aggregate must reject
duplicate, mismatched, or missing platform reports. Use existing validation
commands and argument lists rather than dynamically executing shell text.
Verification may create temporary fixtures but must not write to real target
projects.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|---|---|
| I. Reuse the Existing Generator Engine | Pass. The gate invokes existing checks and workflows; it adds no project-write engine. |
| II. Keep Architecture Simple and Deterministic | Pass. One repository script and existing CI matrix; no runtime dependency or persistent state. |
| III. Preserve Historical States | Pass. Pinned historical and candidate states remain unchanged and continue to be tested. |
| IV. Plan Before Writing; Require Explicit Confirmation | Pass. Verification is separate from plan/apply and does not write target projects or release metadata. |
| V. Make Transactions Reversible and Conflict-Safe | Pass. No generator transaction is performed; test fixtures are isolated and temporary. |
| VI. Keep Scope and Authority Bounded | Pass. No private credentials or publication; only approved public pinned references are used. |
| VII. Use Incremental, Verifiable Development | Pass. Focused acceptance scenarios, CI matrix evidence, and human Analyze/Review gates remain required. |

No constitution violations identified.

## Phase 0: Outline & Research

See [research.md](research.md). Repository evidence establishes Python 3.11+,
standard-library runtime dependencies, unittest, and an existing Linux/Windows
matrix. The repository-local release-gate boundary and its per-platform JSON
reports plus aggregate mode are defined here; the command boundary remains
visible for human Analyze approval.

## Phase 1: Design & Contracts

- [Data model](data-model.md): per-platform and aggregate reports with criterion results.
- [Command contract](contracts/verify.md): local invocation, evidence semantics,
  aggregate input, exit behavior, and CI boundary.
- [Quickstart](quickstart.md): local and hosted validation scenarios.

Re-check after design: all seven Constitution principles still pass. Reports
contain status and evidence references only, never raw secrets or
private-authentication results. Cross-platform readiness is established by
aggregating successful Linux and Windows reports, not inferred from one host.

## Project Structure

### Documentation (this feature)

```text
specs/004-release-readiness/
├── plan.md
├── research.md
├── data-model.md
├── contracts/
│   └── verify.md
├── quickstart.md
└── tasks.md
```

### Source Code (repository root)

```text
scripts/
└── verify.py                       # Repository-level validation entrypoint

tests/
└── test_verify.py                  # Status, missing-evidence, and safety behavior

integration/
└── test_t0003_integration.py       # Four explicit new/migrate platform scenarios

.github/workflows/
└── ci.yml                          # Runs the gate in the existing Linux/Windows matrix

README.md
docs/GENERATOR_CONTRACT.md          # Command semantics and verification boundaries
docs/PROJECT_HANDOFF.md             # Evidence and remaining limitations
```

**Structure Decision**: Reuse the existing `scripts/`, `tests/`, `integration/`,
and `.github/workflows/ci.yml` layout. The existing CI matrix emits one report
per platform and a final job aggregates them. Replace duplicate check/test
steps with the verifier while retaining toolchain setup, mirror preparation,
unique CLI smoke checks, and the separate manual private-auth path. Keep
repository release verification outside `src/project_generator/cli.py`, whose
current commands operate on a target project and are installed as a package.

## Complexity Tracking

No constitution violations requiring justification.
