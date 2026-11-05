# React Frontend Acceptance Quickstart

This guide describes validation scenarios for implementation; it does not claim that
the feature is implemented. No Docker daemon, secrets, external project, or production
resource is required.

## Prerequisites

- Python 3.11+ and the generator test dependencies.
- Node.js 24 and npm for the generated React package.
- A current desktop browser for the manual preview checkpoint.
- A temporary t0003-based project, isolated from productive repositories.

## React Starter Review (Increment 1)

1. Install the React package from its committed lockfile with lifecycle scripts
   disabled.
2. Run the package verification command (typecheck, build, and focused tests).
3. Start the documented local preview and open its local URL in a browser.
4. Perform the example's primary interaction and record the visible response.
5. Stop the local preview. Confirm no Docker or backend service was required.

**Expected**: The browser displays the example; the documented interaction changes
visible state; verification and preview errors are surfaced; generated build output is
ignored. Review Gate 1 passed on 2026-11-05; this section records the accepted evidence.

## Generator Transaction Review (Increment 2)

Use a disposable supported project. Replace `TARGET` with its absolute path:

```text
t0004-generator plan TARGET --module react --json
t0004-generator apply TARGET --plan PLAN.json --confirm PLAN_ID
npm ci --ignore-scripts --prefix TARGET/react
npm run verify --prefix TARGET/react
npm start --prefix TARGET/react -- --host 127.0.0.1
t0004-generator plan TARGET --module react --json
t0004-generator restore TARGET --backup BACKUP_ID
```

Save and inspect the plan before Apply; use its actual plan ID and the backup ID
reported by Apply. Confirm the first plan is read-only, the repeated plan has no
operations, and restore returns only managed files to their prior state. Repeat on a
project with the existing TypeScript module and confirm its files and lockfile are
byte-identical.

## Compatibility Review (Increment 3)

Run focused module, transaction, CI-state and infrastructure tests; then run the
complete generator suite, configured project check and t0003 integration suite. Verify
all 16 fixed module subsets and both install orders for relevant pairs. Specifically
test React alongside an existing valid Docker/PostgreSQL projection: it must add no
React Dockerfile/service and must not change existing infrastructure files.

Run the existing GitHub Actions matrix on Ubuntu and Windows. CI must install the React
lockfile only for states containing React, and all eight pre-React CI byte states must
remain exact.

**Out of scope**: Docker image builds for React, Docker-based preview, production
deployment, external repositories, and changes to t0003 or historical generator data.
