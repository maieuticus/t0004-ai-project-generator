# React Frontend

This optional frontend is an independent React package. It does not require the
generator's TypeScript console module, Docker, a backend, or project secrets.

## Requirements

- Node.js `24.22.2`
- npm `11.19.1`
- A current browser

The package versions are pinned in `package.json` and `package-lock.json`. Run the
commands below from the generated project's `react/` directory.

## Install and verify

Install exactly from the lockfile without running dependency lifecycle scripts:

```text
npm ci --ignore-scripts --no-audit --no-fund --strict-peer-deps
npm run verify
```

Verification type-checks the TSX sources, runs the focused starter test, and builds
the production assets into the ignored `dist/` directory.

## Start locally

```text
npm start
```

Open the local URL printed by Vite (normally `http://localhost:5173/`). Stop the
server with `Ctrl+C`.

## Open the preview in GitHub Codespaces

From the repository checkout, the starter template is in
`src/project_generator/templates/react/`. After the React module is generated in a
project, use that project's `react/` directory instead.

1. In a Codespaces terminal, change to the starter directory and install/verify:

   ```text
   cd src/project_generator/templates/react
   npm ci --ignore-scripts --no-audit --no-fund --strict-peer-deps
   npm run verify
   ```

2. Start Vite on the Codespace network interface so Codespaces can forward the port:

   ```text
   npm start -- --host 0.0.0.0 --strictPort
   ```

3. Open the **Ports** tab in the Codespaces panel. Wait for port `5173`, keep its
   visibility **Private**, then choose **Open in Browser** (or use the browser icon).
   If the port is not listed, forward port `5173` from the Ports tab.
4. In the page, select **Add a step**. The displayed count should increase and be
   announced as a live update. Check that the page loads without console errors.
   Edit a source file and save to confirm Vite hot reloads the preview.
5. Return to the terminal and press `Ctrl+C` to stop Vite.

Do not change the forwarded port to public. The starter needs no container,
database, or external service.

## Preview a production build

```text
npm run build
npm run preview
```

Vite prints the preview URL (normally `http://localhost:4173/`). In Codespaces, run
`npm run preview -- --host 0.0.0.0 --strictPort` and open forwarded port `4173` as
private. Stop the preview with `Ctrl+C`.

Build output and installed dependencies are ignored by Git.
