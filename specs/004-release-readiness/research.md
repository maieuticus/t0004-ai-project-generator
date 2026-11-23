# Research: Release Readiness Verification

## Repository-Level Verification Boundary

**Decision**: Implement `verify` as a repository-level script and run it inside
the existing Linux/Windows CI matrix. Each host emits a JSON report; a final
aggregate mode consumes exactly one report from each platform and produces the
criterion-level release outcome. A single-host invocation reports only the
checks run on that host.

**Rationale**: `src/project_generator/cli.py` currently exposes target-project
operations (`check`, `plan`, `new`, and `migrate`) and is installed through the
package entrypoint. Repository tests and integration fixtures are not package
resources. Keeping release verification in `scripts/` avoids coupling an
installed target-project command to repository-only tests.

**Alternatives considered**:
- Add `verify` to the installed target-project CLI. Rejected for this feature
  because it cannot truthfully establish repository-wide Linux/Windows and
  pinned-template release evidence from a single target-project invocation.
- Query GitHub from the local command to combine remote results. Rejected because
  that would add credentials/API dependencies; CI artifacts provide explicit
  reports without a local GitHub API dependency.

## Existing Validation and Integration

**Decision**: Reuse `scripts/check.py`, the existing template and generator test
suites, and the pinned public integration suite. Make the `new` and `migrate`
acceptance scenarios explicit in the integration coverage rather than creating a
second test harness. The `new` scenario uses the supported Python module as the
representative end-to-end case.

**Rationale**: `.github/workflows/ci.yml` already runs Python checks and tests on
Ubuntu and Windows and supports credential-free public mirrors for historical
and candidate t0003 references. `scripts/check.py` validates repository files
and runs configured project checks. The integration suite already creates
isolated test projects and invokes the installed CLI.

**Alternatives considered**:
- Add another workflow solely for release verification. Rejected unless CI
  evidence shows the existing matrix cannot express the gate; it would duplicate
  platform setup. Replace duplicate validation steps rather than running the
  same suites twice.
- Treat a local run as proof for both platforms. Rejected because it would
  violate the explicit `not verified` behavior for absent evidence.

## Credentials and External Sources

**Decision**: Use only the already approved immutable public template references
and their credential-free mirrors. Keep private authentication and GitHub
repository creation outside this feature.

**Rationale**: The project contract requires missing or inaccessible sources to
be non-success, and the current CI keeps private authentication on a separate
manual path. Release readiness must not turn a public-mirror result into a claim
about private access.

**Alternatives considered**:
- Reuse a private token in the gate. Rejected as outside the approved scope and
  unnecessary for the four required practical tests.

## Runtime and Evidence Format

**Decision**: Use the Python standard library and existing unittest conventions;
report criterion identifiers, status, platform, and concise evidence references.
Do not persist raw test output or credentials as verification data.

**Rationale**: The package has no runtime dependencies, the repository already
uses Python 3.11+ and unittest, and CI exposes platform-specific job results.
Small status records are sufficient to distinguish passed, failed, and
not-verified criteria.

**Alternatives considered**:
- Add a reporting/database dependency or long-lived evidence store. Rejected as
  unnecessary for a CI-gated release decision.
