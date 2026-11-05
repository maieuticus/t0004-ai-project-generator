# Tasks: Optional React Frontend

**Input**: Design documents from `/specs/001-react-frontend/`

**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md`,
`contracts/react-module.md`, and `quickstart.md`

**Tests**: Focused template, transaction, compatibility, integration and CI tests are
required by the specification.

**Organization**: Tasks are ordered by the three independently reviewable user
stories and the approved incremental delivery plan.

## Phase 1: Setup

**Purpose**: Record the approved decisions and review exact dependency pins before
changing generator contracts or adding third-party dependencies.

- [x] T001 Record the confirmed `react@0.1.0` identity, TSX/Node 24/Vite toolchain,
  manual browser-smoke acceptance, Docker/PostgreSQL coexistence policy and
  Constitution ratification; pin and review exact dependency versions in
  `specs/001-react-frontend/research.md` before starter source changes. Verified
  official version metadata and strict peer resolution on 2026-11-05; full lockfile
  generation and clean install are deferred to T002.

**Checkpoint**: Human Analyze approval is required before starting implementation.

---

## Phase 2: User Story 1 - Start a React Example (Priority: P1) - MVP

**Goal**: Deliver a visible, interactive frontend that runs locally in a browser
without Docker or generator integration.

**Independent Test**: Install from the committed lockfile, run the starter
verification, start the documented preview, and verify one visible interaction in a
browser.

- [x] T002 Create the independent TSX starter, exact-pinned package and lockfile,
  local preview/build configuration, ignored outputs, and focused starter tests in
  `src/project_generator/templates/react/`. Clean npm install, strict peer
  resolution, TypeScript compile, starter test, production build and local server
  smoke check passed on 2026-11-05.
- [x] T003 Add the generated setup, preview, stop, and verification instructions in
  `src/project_generator/templates/react/docs/REACT.md` and include all React template
  files in `pyproject.toml` package data. Added Codespaces browser-forwarding steps;
  documentation/package-data checks passed on 2026-11-05.
- [x] T004 Add `tests/test_react_template.py` to verify the packaged starter's
  lockfile, verification command, build output and documented local preview. The
  isolated lockfile install and `npm run verify` passed on 2026-11-05; the user
  accepted the manual browser review with the counter interaction.

**Review Gate 1**: Show the running browser example and review its dependency list.
Proceed to generator integration only after the user accepts the visible example and
the exact toolchain choices recorded by T001.

**Status (2026-11-05): PASSED.** The user accepted the React example after manually
opening it in a browser and verifying the counter interaction. The T001-T004
technical evidence, including exact dependency pins, lockfile install, verification,
build, package contents, and local preview, was reviewed and accepted. This closes
the first-increment gate; subsequent work began after separate authorization and is
recorded under Review Gate 2.

---

## Phase 3: User Story 2 - Add the Frontend to an Existing Project (Priority: P2)

**Goal**: Make React a separately selectable fixed module managed by the existing
Format-4 planner and transaction behavior.

**Independent Test**: Install React without the TypeScript module into temporary
supported projects; verify read-only planning, confirmed apply, no-op, conflicts,
stale-plan rejection and reverse-order restore.

- [x] T005 Add public-CLI tests for `--module react`, independent installation,
  canonical metadata/checks and React-specific operations in
  `tests/test_react_module.py`. Both public tests pass now that T007 enables the
  React CLI selection and Format-4 module transaction validation.
- [x] T006 Register the fixed React files, check and metadata ordering in
  `src/project_generator/python_module.py`; register `react` in the closed module
  mapping and add conditional CI states in `src/project_generator/module_states.py`,
  while asserting all eight pre-React CI byte states stay unchanged. Added the
  React projection and check, canonical module/check ordering, 16 unique CI states,
  and Docker/PostgreSQL service exclusion tests; all eight historical CI hashes
  match their pre-React byte states.
- [x] T007 Extend accepted module selections and Format-4 Apply/Restore validation
  for `react` in `src/project_generator/cli.py`, `src/project_generator/plan.py`,
  and `src/project_generator/transaction.py`. React is accepted by the public
  `plan`/`new` CLI, and existing Format-4 apply, confirmation, preflight, backup
  validation and restore handle it; focused React safety checks passed.
- [x] T008 Complete `tests/test_react_module.py` with Apply/no-op, stale and tampered
  plans, foreign-path conflicts, metadata/config conflicts, snapshot/restore, pairwise
  installation-order invariance, and all 16 canonical module/CI states. The React
  transaction suite passed; the complete 262-test generator suite and all 29 t0003
  integration tests passed. A generated temporary React project passed `npm ci`,
  `npm run verify` and the repeated-plan no-op check.

**Review Gate 2**: Generate a disposable project without `typescript@0.1.0`, inspect
the plan and output, run the browser preview, and verify the existing TypeScript
projection remains byte-identical where present. Approve before compatibility work.

**Status (2026-11-05): PASSED.** The user accepted the generated React application
after opening it in a browser and verifying that **Add a step** increments the
displayed counter. The user confirmed the T005-T008 technical checks passed.
Browser reload and browser-console inspection were not separately confirmed. The
Codespaces preview instructions are recorded in `quickstart.md`. T009-T013 remain
unchecked; their full task-level acceptance criteria remain incomplete (T009-T012 were later completed in Increment 3).

---

## Phase 4: User Story 3 - Verify Compatibility (Priority: P3)

**Goal**: Prove React composes with existing modules, Docker/PostgreSQL metadata and
the supported CI platforms without adding React container support.

**Independent Test**: Verify the full 16-state module matrix, unchanged legacy
projections, Docker/PostgreSQL coexistence and the existing Linux/Windows CI.

- [x] T009 Add compatibility tests in `tests/test_infrastructure.py` and
  `tests/test_react_module.py` for React with existing Docker/PostgreSQL projects,
  React-only Docker prerequisite rejection, and installing a console module after
  React without changing existing Compose files or services.
- [x] T010 Separate Docker-capable console modules from all generator modules in
  `src/project_generator/module_states.py`, `src/project_generator/infrastructure.py`,
  `src/project_generator/infrastructure_states.py`, `src/project_generator/docker_files.py`,
  and `src/project_generator/plan.py`; keep Compose and PostgreSQL projections limited
  to Python, TypeScript and Java.
- [x] T011 Extend `integration/test_t0003_integration.py` to verify the React starter
  against the compatible t0003 base, reject unsupported historical bases, and prove
  a fresh React installation reaches a no-op without changing existing template files.
- [x] T012 Update `docs/GENERATOR_CONTRACT.md`, `README.md`, and
  `docs/DV_KONZEPT.md` with the fixed React contract, independent TypeScript
  relationship, local-only preview, compatibility behavior and Docker exclusion.
- [ ] T013 Run focused and full checks from `scripts/check.py`,
  `tests/test_react_module.py`, `tests/test_infrastructure.py`,
  `integration/test_t0003_integration.py`, and the existing Ubuntu/Windows GitHub
  Actions; record exact results and residual risks in `docs/PROJECT_HANDOFF.md`.

**Review Gate 3**: Review the browser example, full test/CI evidence, historical-byte
checks, infrastructure coexistence and unresolved risks. The feature is complete only
after explicit human Review approval.

---

## Dependencies and Execution Order

- T001 and the human Analyze approval precede all implementation.
- User Story 1 (T002-T004) is the first visible increment and must pass Review Gate 1.
- User Story 2 (T005-T008) depends on the reviewed starter and must pass Review Gate 2.
- User Story 3 (T009-T013) depends on the generator module and must pass Review Gate 3.
- These increments are intentionally sequential: they share the template, module
  registry, CI state projection and infrastructure preconditions.
- No tasks are marked parallel because the principal changes touch shared fixed
  projections or depend on the preceding acceptance gate.

## Incremental Strategy

1. Complete T001 after the human Analyze gate; implement T002-T004 and review the
   browser-visible MVP.
2. After Review Gate 1, implement T005-T008 and review a generated project with
   React independent of the existing TypeScript module.
3. After Review Gate 2, implement T009-T013, run cross-platform compatibility checks,
   and submit the result for the human Review gate.

## Notes

- Every task uses the Spec Kit checkbox/ID/story-label format and names its target
  path.
- Tests are required by the user and specification; no implementation is authorized
  before Analyze approval.
- Docker integration for React, publication and deployment are not tasks in this
  feature.
