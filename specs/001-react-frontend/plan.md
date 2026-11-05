# Implementation Plan: Optional React Frontend

**Branch**: `feature/react-frontend-135a` | **Date**: 2026-11-05 | **Spec**:
[spec.md](spec.md)

**Input**: Feature specification from `/specs/001-react-frontend/spec.md`

## Summary

Add a fixed, optional React frontend that can be installed without the existing
TypeScript console module. The generator will emit a separately locked, locally
startable browser example, register it as a new fixed Format-4 module, and preserve
all existing generated states. The user approved the React identity `react@0.1.0`,
the TSX/Node 24/React/ReactDOM/Vite direction, manual browser review with automated
build and starter checks, and coexistence with existing Docker/PostgreSQL projections.
React adds no container service and does not satisfy Docker's existing console-module
prerequisite. Exact package pins were reviewed in T001 and used for the accepted
starter increment.

The implementation is an independent `react/` package with the approved toolchain
direction. Its exact package versions are pinned in its own lockfile; no existing
TypeScript package files or lockfile are reused or modified.

## Technical Context

**Language/Version**: Generator Python 3.11+; frontend uses Node.js `24.22.2` and
strict TypeScript/TSX, as recorded in `research.md`.

**Primary Dependencies**: Approved dependency families are React, ReactDOM,
TypeScript, Vite, and the Vite React integration. Exact direct versions are recorded
in `research.md` and pinned in the starter package. No UI test framework is planned.

**Storage**: No persistent application data. Project files, metadata and snapshots
use the existing filesystem and Format-4 transaction contract.

**Testing**: Generator `unittest` suite; React typecheck, production build and focused
starter tests through the configured project check; manual browser interaction at the
first-increment review gate; Linux and Windows CI. Browser automation is excluded by
the user's decision.

**Target Platform**: Generated project checks on the existing Linux/Windows CI
matrix; local preview in a current desktop browser. No production hosting target.

**Project Type**: Python generator extension plus a local-only browser frontend
starter.

**Performance Goals**: No product-scale or runtime performance target; build and
local preview must complete successfully on the supported Node environment.

**Constraints**:
- Plan and apply remain read-only with respect to package installation and execution.
- Dependencies are exact-pinned in `react/package-lock.json`; CI installs with
  lifecycle scripts disabled.
- Existing Python, TypeScript, Java, Docker and PostgreSQL projections stay unchanged
  except for the additive React CI/module state when React is selected.
- React adds no Dockerfile, Compose service, published port, secret, backend, or
  production deployment.

**Scale/Scope**: One fixed frontend module; the three existing language modules plus
React yield 16 supported module subsets. Existing eight subsets without React must
remain byte-identical.

## Constitution Check

| Principle | Design response | Result |
|---|---|---|
| Reuse the existing generator engine | Use `module_plan_target`, Format 4, `apply_multi`, and existing restore flow; no new writer. | Pass |
| Simple and deterministic | One fixed React projection, one package/lockfile, closed module list; no plugin API. | Pass |
| Preserve historical states | Append React to canonical module order and add conditional CI bytes; assert all eight old CI projections remain unchanged. | Pass |
| Plan and confirm before writes | Reuse read-only plan, explicit plan ID confirmation and preflight checks; no npm execution in plan/apply. | Pass |
| Reversible and conflict-safe | Reuse snapshots, stale-plan checks, foreign-file conflicts and reverse-order restore. | Pass |
| Bounded scope and authority | No Docker service, production deployment, external publishing, credentials or new permissions. | Pass |
| Incremental, verifiable workflow | Starter review, generator integration review, then cross-platform compatibility review before final Review gate. | Pass |

No constitution conflict is known. The material Analyze decisions and exact dependency
pins are recorded in `spec.md` and `research.md`. The user approved the human Analyze
gate on 2026-11-05; implementation of T005 and later work still requires its own
authorization.

## Repository Evidence and Design

Current code uses a closed `MODULES` mapping in
`src/project_generator/module_states.py`; `src/project_generator/python_module.py`
contains the shared file planner and fixed template lookup; `src/project_generator/cli.py`
and `src/project_generator/transaction.py` enforce the same closed module list. The
module planner binds config, CI, existing module files and, when Docker is present,
the Docker projection. Infrastructure derives Docker files from the same module set.

The React implementation must therefore:

1. Add the approved fixed module identity `react@0.1.0` in canonical order after
   Python, TypeScript and Java, with a separate template under
   `src/project_generator/templates/react/`.
2. Keep the React package and lockfile independent of `typescript/`; selecting React
   does not select or alter `typescript@0.1.0`.
3. Generate additional fixed CI states only when React is selected. The eight
   previously supported CI byte strings remain identical; the complete closed state
   set becomes 16.
4. Add the React project check after dependencies are installed in CI. The existing
   workflow already sets up Node 24 on Ubuntu and Windows; no extra runner or
   permission is required.
5. Separate modules that have Docker console services from modules that merely
   contribute to CI. Docker and PostgreSQL projections continue to use only the
   existing Python, TypeScript and Java service set. React is allowed alongside an
   existing valid Docker/PostgreSQL installation but is not a Docker service and
   cannot be the only prerequisite for adding Docker.
6. Preserve canonical metadata/check ordering, deterministic bytes, conflict
   detection, no-op behavior, and reverse-apply restore. Existing snapshots and
   infrastructure projection path lists retain their current meaning.

### React starter layout (T002)

```text
src/project_generator/templates/react/
├── .gitignore
├── index.html
├── package.json
├── package-lock.json
├── tsconfig.json
├── vite.config.ts
├── docs/
│   └── REACT.md
├── src/
│   ├── App.tsx
│   ├── counter.ts
│   ├── main.tsx
│   └── style.css
└── test/
    └── app.test.mjs

tests/test_react_module.py
```

The generated project receives the starter and its operational documentation from
this template under `react/`, plus the canonical metadata and conditional
`.github/workflows/ci.yml` state. Generator registration and projection are later
tasks and are not part of the accepted first increment.

## Interface and Transaction Design

- Public selection is proposed as `new|plan --module react`, followed by the existing
  `apply --plan ... --confirm ...` and `restore --backup ...` interfaces; registration
  for this interface is planned in T005-T007 and is not implemented yet.
- The fixed identifier is `react@0.1.0`; its public name/version is user-confirmed.
- `generator.modules` remains a closed, canonically ordered list. No extension
  discovery or automatic upgrades are introduced.
- React's local `verify` check performs type validation, production build and focused
  tests. CI installs the exact lockfile with scripts disabled before `scripts/check.py`.
  The generator never invokes npm.
- Apply snapshots all modified and created paths before writes. An unchanged installed
  React projection is a no-op; stale plans, collisions, missing or changed managed
  files are conflicts. Restore must be performed in reverse apply order and must not
  remove foreign files or build outputs.
- With Docker already installed, React changes only the language CI/config projection.
  Compose and Docker documentation remain exactly as generated for the existing
  console modules. Tests must cover adding React to an existing Docker/PostgreSQL
  project and installing a console module after React without changing the existing
  infrastructure service set.

## Compatibility and Validation Strategy

### Focused generator tests

- React-only and all 16 supported module subsets produce canonical metadata, checks
  and the expected CI bytes.
- All eight legacy CI states remain byte-identical; existing TypeScript files,
  lockfile, check command and starter remain byte-identical.
- React and each existing module compose in both pairwise install orders; the final
  projection is equal and restores succeed only in reverse order.
- React can be installed in projects with existing Python/TypeScript/Java and valid
  Docker/PostgreSQL states without adding or changing Docker/Compose files.
- React alone does not satisfy the existing Docker console-service prerequisite.
- Plan does not write; explicit Apply, no-op, foreign path, tampered/stale plan,
  snapshot, restore, and partial/conflict cases are covered.
- Project checks report dependency/build failures; no module command runs during plan
  or apply.

### CI and user acceptance

- Run focused module, infrastructure, configuration, transaction and CI-projection
  tests, then the full generator suite and configured project check.
- Run existing Linux and Windows GitHub Actions. Node 24 is already provisioned in
  the base workflow; the React dependency-install step runs only for React states.
- Perform a manual browser preview and interaction at the first-increment review gate.
- Run integration tests against the exact supported t0003 commits, including the
  original release rejection and current compatible base.
- Do not repeat Docker image builds. If Docker daemon testing is later required, it
  needs separate authorization and remains outside this React feature.

## Incremental Delivery and Human Gates

| Increment | Goal and scope | Evidence/tests | Human checkpoint and transition criteria | Effort estimate |
|---|---|---|---|---|
| 1. Browser starter | Deliver the independent React example, pinned package, local preview instructions and focused starter verification, without public generator selection. | Install from lockfile, typecheck/build, starter tests, local browser interaction. | Review the browser-visible example, exact dependency pins and test evidence. Proceed only after human acceptance. | 1-2 engineering days |
| 2. Safe generator integration | Add the fixed module projection, CLI selection, metadata/check/CI additions and Format-4 apply/no-op/conflict/restore behavior. | Focused plan/apply/restore tests, state and historical-byte checks, independent React installation and pairwise orders. | Review a generated temporary project and its preview, verify TypeScript remains untouched, approve before broad matrix/infra work. | 3-5 engineering days |
| 3. Compatibility and final acceptance | Close module/CI combinations, Docker/PostgreSQL coexistence, Linux/Windows CI and integration evidence; update contract and user docs. | All 16 states, legacy eight bytes, cross-module order/restore, Docker/PG projection checks, full test/check suite, Linux/Windows CI and integration. | Human Review gate confirms all acceptance criteria and residual risks; no merge or release without separate approval. | 2-4 engineering days |

## Risks and Review Controls

| ID | Decision/risk | Confirmed direction | Remaining control |
|---|---|---|---|
| D1 | Public module identifier/version | User approved `react@0.1.0` on 2026-11-05. | Preserve this identifier in the contract and tests. |
| D2 | React source/toolchain | User approved TSX, Node 24, React/ReactDOM and Vite on 2026-11-05; exact pins were recorded in T001. | Keep React's package and lockfile separate from TypeScript's. |
| D3 | Browser behavior evidence | User approved automated install/typecheck/build/starter tests plus manual browser interaction; no browser automation. | Review Gate 1 passed on 2026-11-05; preserve the recorded browser and test evidence. |
| R1 | Docker code currently assumes every module maps to a Docker service. | User approved React coexistence with existing Docker/PostgreSQL projections, without a React service or Dockerfile. | Keep a separate console-service set; test coexistence and unchanged projections. |
| R2 | Module state count doubles from 8 to 16. | Closed deterministic enumeration; no dynamic plugin or generalized framework. | Preserve all prior output bytes and verify new state uniqueness/order invariance. |
| R3 | React transitive dependencies can drift. | Exact package versions and lockfile integrity; `npm ci --ignore-scripts`. | Review lockfile and dependency changes at the starter gate. |

## Complexity Tracking

| Addition | Why needed | Simpler alternative rejected because |
|---|---|---|
| Sixteen fixed module/CI states | React is independently installable alongside each existing language module. | Merging React into TypeScript would alter its existing projection and violate the approved independent extension. |
| Separate Docker service-module set | React is not containerized, while React must coexist with existing Docker projects. | Treating every generator module as a Docker service would accidentally expand Docker scope and change Compose behavior. |
