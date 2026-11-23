# Quickstart: Release Readiness Verification

## Prerequisites

- Python 3.11 or newer and Git.
- Node.js and Java only for the existing module checks that require them.
- For pinned integration tests, a fresh credential-free mirror prepared from the
  public pinned t0003 references, or both mirror environment variables set to a
  complete local mirror.
- No private token is needed or used by this feature.

## Local Verification

From the repository root:

```text
python scripts/verify.py
```

For automation:

```text
python scripts/verify.py --json
```

The report covers the current host only. Missing pinned sources or test
prerequisites must be shown as not verified; a local result does not establish
the other operating system's status.

## Aggregate Reports

After collecting one JSON report from Linux and one from Windows, combine them
from the repository root:

```text
python scripts/verify.py --aggregate linux-report.json windows-report.json --json
```

The aggregate is ready only when both platform reports and every required
criterion are present and passed. GitHub Actions performs this aggregation from
the two matrix artifacts.

## Cross-Platform Release Gate

Run the existing GitHub Actions workflow on both Ubuntu and Windows. The
release-readiness check is complete only when both matrix jobs pass the local
verification and pinned integration/practical-test scenarios and the final
aggregate job succeeds. Review each platform's report; do not infer Windows
success from a Linux run or vice versa.

The practical scenarios are:

1. Python-module `new` on Linux.
2. Python-module `new` on Windows.
3. `migrate` on Linux, including read-only inventory and strategy comparison.
4. `migrate` on Windows, including read-only inventory and strategy comparison.

This gate does not publish a release or establish private template
authentication or GitHub “Use this template” repository creation.
