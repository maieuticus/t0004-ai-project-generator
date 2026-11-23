# Tasks: Release Readiness Verification

**Input**: Design documents from `specs/004-release-readiness/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, and `quickstart.md`

**Tests**: Focused unit and integration tests are required because verification status and the four platform/workflow scenarios are part of the feature contract.

**Organization**: Tasks are grouped by user story. User Stories 2 and 3 add independent practical scenarios, but use the same integration test module and therefore must edit it sequentially.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with another task because files differ and dependencies are complete.
- **[Story]**: User-story label corresponding to `spec.md`.
- Each task names the exact file path to change or validate.

## Phase 1: Setup

**Purpose**: Reuse the existing Python, unittest, and CI setup; no dependency or project initialization changes are required.

No separate setup tasks.

---

## Phase 2: Foundational

**Purpose**: The shared verification report contract is established in User Story 1; there is no separate blocking infrastructure.

No separate foundational tasks.

---

## Phase 3: User Story 1 - Determine Release Readiness (Priority: P1) 🎯 MVP

**Goal**: Produce an explicit, safe repository-level verification result that reports only evidence available on the current host and never implies cross-platform readiness from a single local run.

**Independent Test**: Unit tests prove successful local results, failed checks, missing integration prerequisites, JSON output, and non-success behavior without invoking release or private-authentication paths.

### Tests for User Story 1

- [x] T001 [US1] Add tests in `tests/test_verify.py` for local and aggregate reports, passed/failed/not-verified criteria, missing or duplicate platform reports, JSON output, exit codes, unchanged `VERSION` and `CHANGELOG.md`, and the absence of publication or private-authentication operations.

### Implementation for User Story 1

- [x] T002 [US1] Implement local and `--aggregate LINUX_REPORT WINDOWS_REPORT` modes in `scripts/verify.py`; run approved checks using argument-list subprocess calls, report criterion evidence sources, reject missing/duplicate platform reports, preserve missing evidence as not verified, and leave target projects and release metadata unchanged.

**Checkpoint**: User Story 1 is testable locally; a single-host success is explicitly not an overall cross-platform release approval.

---

## Phase 4: User Story 2 - Validate New Projects on Both Platforms (Priority: P1)

**Goal**: Exercise the approved `new` workflow against supported pinned template sources and record its result on each CI platform.

**Independent Test**: The integration scenario passes on each matrix platform after creating and checking an isolated project through the `new` workflow.

### Tests and Implementation for User Story 2

- [ ] T003 [US2] Add a practical Python-module `new` integration scenario in `integration/test_t0003_integration.py` that uses an approved pinned source, creates an isolated project, applies the reviewed plan, passes the project check, and records the result on Linux and Windows. Implemented; the local Linux run passes. Windows evidence remains pending in T008.

**Checkpoint**: The `new` scenario is run by the verification suite on both operating systems; a missing platform result remains not verified.

---

## Phase 5: User Story 3 - Validate Migration on Both Platforms (Priority: P1)

**Goal**: Exercise `migrate` on both platforms and establish that the read-only inventory and strategy comparison do not change the source project.

**Independent Test**: The integration scenario records the inventory and strategy comparison on Linux and Windows and verifies the source state is unchanged.

### Tests and Implementation for User Story 3

- [ ] T004 [US3] Add a practical `migrate` integration scenario in `integration/test_t0003_integration.py` that records the read-only inventory and strategy comparison on both platforms and asserts the source project remains unchanged. Implemented; the local Linux run passes. Windows evidence remains pending in T008.

**Checkpoint**: The `migrate` scenario passes independently on both operating systems; any missing or changed-source result blocks readiness.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Wire the results into the hosted gate, document verification limits, and record evidence.

- [x] T005 Update `.github/workflows/ci.yml` to replace duplicate check/test/public-integration steps with `python scripts/verify.py` after preparing the credential-free pinned mirrors; upload one JSON report per platform; add a final job that runs aggregate mode; preserve toolchain setup, unique CLI smoke checks, and the separate private-authentication path. Workflow pins artifact actions to verified commit SHAs; hosted execution is tracked in T008.
- [x] T006 [P] Document the repository-level verification invocation, status meanings, and local-versus-hosted evidence boundary in `README.md`.
- [x] T007 [P] Document the verification contract, four practical scenarios, and unverified private-authentication boundary in `docs/GENERATOR_CONTRACT.md`.
- [ ] T008 Run `python scripts/check.py`, template tests, generator tests, pinned integrations, and `git diff --check`; record exact local and hosted evidence plus any unverified items in `docs/PROJECT_HANDOFF.md`. Local Linux verification passed all seven criteria with the pinned mirrors, and `git diff --check` passed. Hosted Linux/Windows evidence remains not verified until the authorized push and CI run.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; existing tooling is reused.
- **Foundational (Phase 2)**: No separate work; the report contract is established in User Story 1.
- **User Story 1 (Phase 3)**: Starts with focused tests and implements the local verification report.
- **User Story 2 (Phase 4)**: Adds the `new` integration scenario; relies on existing pinned-source fixtures.
- **User Story 3 (Phase 5)**: Adds the `migrate` integration scenario; follows User Story 2 because both edit `integration/test_t0003_integration.py`.
- **Polish (Phase 6)**: Depends on all three stories; hosted evidence is recorded only after both matrix reports and the aggregate CI job succeed.

### User Story Dependencies

- **User Story 1 (P1)**: Independent; defines the report contract and local gate behavior.
- **User Story 2 (P1)**: Uses existing pinned-source integration setup; no dependency on User Story 3.
- **User Story 3 (P1)**: Uses existing migration behavior; edits the same integration file as User Story 2 and therefore follows it.

### Within Each User Story

- User Story 1 tests (T001) precede implementation (T002).
- The `new` scenario (T003) precedes the `migrate` scenario (T004) because they share an integration file.
- CI wiring and documentation follow implementation and scenario coverage.

### Parallel Opportunities

- T006 and T007 can run in parallel because they update separate documentation files.
- No integration tasks are marked parallel because they modify the same file.

---

## Parallel Example: Documentation

```text
Task: T006 Document the verification boundary in README.md
Task: T007 Document the verification contract in docs/GENERATOR_CONTRACT.md
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete T001 and T002 to establish a safe, testable local verification report.
2. Validate the report against passed, failed, and missing-evidence cases.
3. Do not treat this MVP as release-ready until User Stories 2 and 3 and the Linux/Windows CI matrix are complete.

### Incremental Delivery

1. Complete User Story 1 and validate the local report.
2. Add and validate the `new` scenario on both platforms.
3. Add and validate the `migrate` scenario on both platforms.
4. Wire the full gate into CI, update documentation, and record evidence.
5. Keep private authentication and publication outside this feature.

## Notes

- `[P]` tasks touch different files and have no unfinished prerequisites.
- All test results must distinguish passed, failed, and not verified.
- A local success does not replace the required Windows CI evidence.
- Do not push or publish without the required explicit authorization.

## Phase 7: Convergence

- [x] T009 Add explicit local-versus-hosted evidence provenance to platform criteria in `scripts/verify.py`, preserve and validate it in aggregate reports, cover source classification in `tests/test_verify.py`, and align the report contract and user documentation per FR-002 and SC-001.
