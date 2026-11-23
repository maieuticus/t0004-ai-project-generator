# Repository Verification Contract

## Invocation

Run `python scripts/verify.py` from the repository root. `--json` writes a
machine-readable report for the current host to standard output. Use
`python scripts/verify.py --aggregate LINUX_REPORT WINDOWS_REPORT --json` to
combine one JSON report from each platform into the final release outcome.

## Behavior

- Run the repository checks and release-gate suites selected by the approved plan.
- Report the current host platform and each criterion's status as `passed`,
  `failed`, or `not_verified`.
- Include `evidence_source` (`local` or `hosted`) in each criterion and on the
  platform report. Determine `hosted` from the GitHub Actions runtime; local
  runs report `local`.
- Treat unavailable pinned sources, missing tests, and unrun platforms as
  `not_verified`; never convert them to a pass.
- Aggregate mode MUST require exactly one valid Linux report and one valid
  Windows report, preserve each criterion's evidence source, and reject
  missing or inconsistent source labels. Synthesized criteria for a missing
  platform report use `not_available`.
- Aggregate mode MUST reject missing or duplicate platform reports and MUST NOT
  report ready if a required criterion is missing or failed.
- Do not write to a real target project, publish a tag or release, create a pull
  request, or change version/changelog metadata.
- Do not use or report private authentication as verified.
- Keep test output concise and do not emit secrets or raw project content.
- Preserve `VERSION` and `CHANGELOG.md` byte-for-byte during local verification.

## Cross-Platform Gate

A local invocation reports only its own platform. CI uploads both reports and
runs aggregate mode in a final job. Both platform jobs and the required pinned
integration/practical-test steps must pass for release readiness. A single local
success cannot stand in for the other platform.

## Result Semantics

- Exit `0`: local mode's required checks passed, or aggregate mode produced a
  complete ready result.
- Exit `1`: an executed required check failed.
- Exit `2`: verification could not run because required setup or evidence was
  unavailable, or aggregate mode found missing/invalid platform reports.

An exit `0` from local mode is not, by itself, an overall release approval.
