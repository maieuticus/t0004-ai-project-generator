# Data Model: Release Readiness Verification

Verification data is transient. The implementation must not persist source
contents, raw logs, credentials, or private authentication details.

## Platform Verification Report

Represents one repository verification invocation on a single operating system.

| Field | Meaning |
|---|---|
| `platform` | Operating system on which this invocation ran |
| `evidence_source` | `local` or `hosted`, copied onto each criterion |
| `status` | Local result: `passed`, `failed`, or `not_verified` |
| `criteria` | Results for the required checks executed on this host |
| `summary` | Concise human-readable result without raw output |

One report is not proof of cross-platform readiness. It is an input to the
aggregate release report.

## Aggregate Release Report

Combines exactly one platform report for Linux and one for Windows.

| Field | Meaning |
|---|---|
| `status` | Overall `ready`, `not_ready`, or `not_verified` |
| `criteria` | Combined criterion results, including the source platform/evidence |
| `blockers` | Failed, missing, duplicate, or mismatched evidence |

The aggregate is `ready` only when both platform reports are present and all
required checks pass. Missing reports or criteria are `not_verified`; failed
criteria make the result `not_ready`. Duplicate or misidentified platform
reports are rejected.

## Criterion Result

Represents one required check or practical-test scenario.

| Field | Meaning |
|---|---|
| `criterion_id` | Stable identifier for the requirement or scenario |
| `status` | `passed`, `failed`, or `not_verified` |
| `platform` | Required or executing platform |
| `evidence` | Short command/job/test reference sufficient to locate evidence |
| `evidence_source` | `local`, `hosted`, or `not_available` when the platform report is missing |
| `blocker` | Concise reason when failed or not verified; absent on success |

The aggregate preserves the platform report's evidence source on every criterion
and rejects missing or inconsistent source labels. `not_verified` is never treated
as success. A failed or missing required result prevents the release gate from
passing.

## Required Practical-Test Results

The required matrix has four distinct criterion identities:

| Workflow | Platform |
|---|---|
| `new` | Linux |
| `new` | Windows |
| `migrate` | Linux |
| `migrate` | Windows |

Migration evidence also confirms the source project remains unchanged.
