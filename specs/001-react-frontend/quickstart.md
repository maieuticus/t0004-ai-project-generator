# React Frontend Acceptance Quickstart

This guide records React acceptance scenarios and the validated workflow for the
current increment. No Docker daemon, secrets, external project, or production
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

### Browser preview in GitHub Codespaces

Run the preview from the generated project's `react/` directory, or use
`TARGET/react` from the repository root. Keep this Vite process running while using
the browser:

```text
npm start -- --host 0.0.0.0 --strictPort
```

In another Codespaces terminal, retrieve the complete forwarded address for port
5173 and confirm it is private:

```text
gh codespace ports --codespace "$CODESPACE_NAME" --json sourcePort,browseUrl,visibility --jq '.[] | select(.sourcePort == 5173) | {browseUrl, visibility}'
```

Open the `browseUrl` value in a browser signed in to GitHub, or use **Open in
Browser** for port 5173 in the Codespaces **Ports** tab. Do not use the Vite
`localhost` URL in a browser outside the Codespace; it refers to the Codespace
itself, not the browser's machine. If the command returns no port, add 5173 in the
Ports tab and keep its visibility **Private**. Stopping Vite also stops the preview.
If the browser reports that `localhost` could not be forwarded, verify that Vite is
still running and port 5173 appears in the Ports tab; open its `browseUrl` instead
of the local `localhost` address.

The forwarding workflow is reusable for other frontend projects: run their
development server, use that server's port and host-binding option, then open its
private `browseUrl`. The port, start command, and host option remain
framework/project-specific, so this React quickstart does not prescribe them for
other projects.

Automatic forwarding could be configured with `"forwardPorts": [5173]` in a
`devcontainer.json`; GitHub documents this setting, and existing Codespaces need a
rebuild after such a configuration change. This repository currently has no
`devcontainer.json`, and forwarding a React-only port by default is not appropriate
for every project generated here. Keep forwarding manual for this review; no
Codespaces configuration is changed.

**Review Gate 2 (2026-11-05): PASSED.** The user confirmed opening the generated
React application in a browser and verified that **Add a step** increments the
displayed counter. The user also confirmed the T005-T008 technical checks passed.
Browser reload and browser-console inspection were not separately confirmed.

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
