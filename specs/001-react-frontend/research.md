# Research: Optional React Frontend

**Scope**: Internal repository evidence, official release/package metadata, and
design options for the approved React extension. Versions were checked on
2026-11-05; no third-party source code was added to the repository.

## Existing Module Model

- `src/project_generator/module_states.py` defines a closed language-module set and
  deterministically generates all eight CI projections for Python, TypeScript and
  Java. Four independent modules imply 16 subsets; appending a React-only CI step
  preserves all eight non-React results if old templates and insertion points remain
  unchanged.
- `src/project_generator/python_module.py` contains the shared fixed-template lookup,
  module planner, canonical metadata/check ordering, and Docker preflight. It is
  reused by TypeScript and Java rather than creating a second writer.
- `src/project_generator/cli.py`, `src/project_generator/transaction.py`, and
  `src/project_generator/plan.py` each validate the fixed module name. All must
  recognize the new module before Format-4 Apply/Restore can accept it.
- `tests/test_typescript_module.py` and `tests/test_java_module.py` verify no-op,
  conflict, reverse restore, order invariance and CI bytes.

## TypeScript Relationship

**Decision recorded by the user**: React is independently installable; the existing
`typescript@0.1.0` console module is not a prerequisite.

This keeps the frontend optional for projects that do not want the console starter.
Its package, lockfile, checks and files must be separate; implementation may use
TypeScript without installing the existing console module.

## Existing Infrastructure Interaction

- `src/project_generator/infrastructure.py`,
  `src/project_generator/infrastructure_states.py`, and
  `src/project_generator/docker_files.py` assume a module set whose members have
  Dockerfiles and console services.
- `src/project_generator/plan.py` binds the module set and current Docker files into
  Format-4 preconditions. A React addition must not cause these checks to expect a
  React Dockerfile or rewrite historical Compose projections.
- The minimal design is to distinguish the fixed language-module set from the fixed
  console-service set used by Docker/Compose. React may coexist with an already valid
  Docker/PostgreSQL projection, but cannot provide the existing Docker prerequisite
  by itself. PostgreSQL remains independent of React.

## Frontend Tooling Options

| Option | Benefits | Costs/Risks | Assessment |
|---|---|---|---|
| TypeScript/TSX with Vite | Reuses the existing Node 24 CI environment and strict TypeScript prior art; provides a local preview and production build. | Adds React, ReactDOM, types, Vite and potentially a Vite React plugin; exact pins need review. | Recommended for review; does not reuse or alter the existing TypeScript package. |
| JavaScript/JSX with Vite | Fewer compile-time dependencies and simpler starter. | Less type safety and less alignment with the existing TypeScript module. | Viable fallback if minimizing dependencies is prioritized over typed examples. |
| React appended to `typescript/` | Smaller public module/state surface. | Mixes console and browser artifacts, alters TypeScript's established projection and conflicts with the user's independent-module approval. | Rejected. |
| Browser automation (Playwright or similar) in CI | Automated end-to-end rendering and interaction evidence. | Adds browser binaries, installation time, runner maintenance and several dependencies. | Not selected; the user approved manual browser review plus automated starter checks. |

## Confirmed Decisions for the Analyze Gate

1. Module identity: fixed `react@0.1.0`, appended after the existing modules
   (user-confirmed 2026-11-05).
2. Frontend: own `react/` directory, TSX, Node 24, React/ReactDOM and Vite
   (user-confirmed 2026-11-05); exact versions are pinned and reviewed before starter
   implementation. Source templates belong under
   `src/project_generator/templates/react/`.
3. Local validation: automated install/typecheck/build/starter tests plus manual
   browser interaction at Review Gate 1; no browser automation (user-confirmed
   2026-11-05).
4. CI: conditional lockfile install before the project check on existing Linux and
   Windows jobs.
5. Docker: React may coexist with existing Docker/PostgreSQL projections but adds no
   service or Dockerfile; existing console-module prerequisites and projections
   remain unchanged (user-confirmed 2026-11-05).

The decisions above resolve the Analyze questions. Exact package versions remain a
review item before the first starter source change; a material change to the approved
module identity, toolchain direction, container boundary or browser-acceptance method
requires renewed user approval.

## T001 — Exact Toolchain Pins

The following exact versions are approved for the starter package. Node.js is the
current Node 24 LTS patch on the verification date; npm is the version bundled with
that distribution. TypeScript intentionally matches the existing TypeScript starter
instead of introducing a major-version change. Runtime packages are production
dependencies; compiler, Vite, plugin, and declaration packages are development
dependencies.

| Component | Exact pin | Basis |
|---|---:|---|
| Node.js | `24.22.2` | Node 24 LTS (Krypton), latest 24.x patch in the official release index on 2026-11-05. |
| npm | `11.19.1` | Bundled with Node.js `24.22.2`; record as `packageManager: npm@11.19.1`. |
| `react` | `19.3.1` | Current stable React release; matching DOM runtime uses the same version. |
| `react-dom` | `19.3.1` | Declares peer dependency `react: ^19.3.1`, satisfied by the exact matching pin. |
| `typescript` | `5.9.3` | Existing TypeScript starter pin; React declaration packages require TypeScript 5.6 or newer. |
| `@types/react` | `19.3.0` | React 19 declarations; minimum supported TypeScript is 5.6. |
| `@types/react-dom` | `19.3.0` | Its `@types/react: ^19.3.0` peer requirement is satisfied by the selected pin. |
| `vite` | `8.3.6` | Vite release whose Node engine permits Node 24; `@vitejs/plugin-react` accepts Vite `^8.0.0`. |
| `@vitejs/plugin-react` | `6.2.1` | Vite's React plugin; peer range `vite: ^8.0.0` matches the selected Vite pin. |
| `@types/node` | `24.19.2` | Node 24 declarations; matches the existing TypeScript starter's exact pin. |

Use exact versions (no ranges or tags) in the future `package.json`. T002 must
generate and commit the npm v3 lockfile with npm `11.19.1`; `npm ci` will then pin
the complete transitive graph by exact versions and registry integrity hashes.
Use `node: "24.22.2"` as the package engine constraint and configure CI/runtime
setup to use that same Node patch. The selected Vite and React plugin both declare
`^20.19.0 || >=22.12.0`, which includes Node `24.22.2`.

### Compatibility and reproducibility check

On the repository environment (`node v24.22.2`, `npm 11.19.1`), a temporary package
manifest containing these exact production and development dependency pins resolved
with:

```text
npm install --package-lock-only --ignore-scripts --no-audit --no-fund --strict-peer-deps
```

It produced lockfile version 3 with 51 package entries; all requested direct
versions matched exactly and strict peer-dependency resolution succeeded. The
temporary directory was removed. This initial T001 check validated metadata and
peer compatibility; the actual template lockfile, clean install, typecheck, build,
and server smoke check are recorded below under T002.

### Official sources checked

- Node release index, exact v24.22.2 entry and bundled npm version:
  <https://nodejs.org/dist/index.json>
- Node release/LTS table: <https://nodejs.org/en/about/previous-releases>
- React release history: <https://github.com/facebook/react/releases>
- Exact npm registry metadata: [react 19.3.1](https://registry.npmjs.org/react/19.3.1),
  [react-dom 19.3.1](https://registry.npmjs.org/react-dom/19.3.1),
  [TypeScript 5.9.3](https://registry.npmjs.org/typescript/5.9.3),
  [@types/react 19.3.0](https://registry.npmjs.org/@types%2freact/19.3.0),
  [@types/react-dom 19.3.0](https://registry.npmjs.org/@types%2freact-dom/19.3.0),
  [@types/node 24.19.2](https://registry.npmjs.org/@types%2fnode/24.19.2),
  [Vite 8.3.6](https://registry.npmjs.org/vite/8.3.6), and
  [@vitejs/plugin-react 6.2.1](https://registry.npmjs.org/%40vitejs%2fplugin-react/6.2.1).
- Vite's official compatibility guidance: <https://vite.dev/guide/>
- Existing repository precedent for TypeScript `5.9.3` and `@types/node` `24.19.2`:
  `src/project_generator/templates/typescript/package.json`.

### Remaining risks and boundaries

- The exact direct pins and generated transitive lockfile have passed a clean
  `npm ci`; future dependency changes must update the manifest and lockfile together.
- Node patch availability changes over time. T002 used the recorded exact runtime pin;
  future work must preserve it unless a compatibility or availability issue is
  reported for approval. Do not silently substitute a newer patch.
- Browser interaction remains a manual Review Gate 1 acceptance item. T002 did not
  interact with the page in a browser and did not add browser automation.

## T002 — Starter Verification

The starter template now contains an independent React/TSX browser example, a local
Vite server/build configuration, ignored build/dependency directories, and a focused
Node test for the counter behavior used by the UI. The UI assets use system fonts and
do not make third-party runtime requests.

The template's `package-lock.json` was generated with npm `11.19.1` using lockfile
version 3. A clean `npm ci --ignore-scripts --no-audit --no-fund --strict-peer-deps`
installed the locked graph; `npm ls --depth=0` showed the exact direct versions
listed above. `npm run verify` passed: TypeScript compile, one Node test, and Vite
production build. The Vite development server also returned HTTP 200 and served the
React entry module. Generated `node_modules/` and `dist/` are excluded by the
template `.gitignore`.

No human browser interaction was performed; that remains Review Gate 1. Generator
packaging and generated setup/preview documentation are T003, and the repository
template-verification test is T004; neither was included in T002.
