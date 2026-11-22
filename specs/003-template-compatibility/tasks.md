# Tasks: Template Compatibility

**Input**: [spec.md](spec.md), [plan.md](plan.md)

Generated from the approved planning basis and feature artifacts on 2026-11-22.
The prerequisite investigations are complete: the historical, candidate and
release commit evidence and file hashes are recorded in `plan.md`; candidate
check dependencies and project-maintained diagram data are distinguished; the
existing integration-source access limitation is documented; and the proposed
capability profiles and rejected states are described. The user approved the
Analyze gate on 2026-11-22; implementation is authorized to proceed under the
scope and constraints recorded below.

## Phase 1: Setup

**Purpose**: Establish repository and feature inputs. This phase is complete;
the verified prerequisites are summarized above.

## Phase 2: Foundation and Analyze Gate

**Purpose**: Review the completed design artifacts and obtain the required
human gate before implementation.

- [x] T005 Review `specs/003-template-compatibility/spec.md`, `specs/003-template-compatibility/plan.md` and `specs/003-template-compatibility/tasks.md` for consistency, unresolved choices, security and constitution compliance; document findings before human Analyze approval.
- [x] T006 Record the user's explicit Analyze approval, given on 2026-11-22 after reviewing the analysis report, in `specs/003-template-compatibility/tasks.md` before beginning implementation.

**Analyze findings (2026-11-22)**: No constitution conflict or critical issue was
found. The candidate source is now pinned to the reachable public commit for
test-only retrieval; private authentication remains unchanged. T008/T012 name
all four modules on their respective template states, and T008 includes explicit
read-only/no-side-effect assertions. The user approved the Analyze gate on
2026-11-22; implementation may proceed, while the Review gate remains open.

## Phase 3: User Story 1 - Use the Current Template

**Goal**: Support four module plans and confirmed transactions on the verified
candidate without automatically modifying the template.

**Independent test**: For each module, plan on the candidate; perform applicable
apply, no-op, project check and restore tests on the candidate.

- [x] T007 [US1] Add focused candidate-profile and verified-file tests in `tests/test_python_compat.py`, including prerequisites and accepted CI projections.
- [x] T008 [US1] Add candidate-commit integration coverage in `integration/test_t0003_integration.py` for Python, TypeScript, Java and React: plan each module; apply, run its applicable project check, confirm no-op and restore; assert planning leaves target bytes unchanged; preserve historical and release references. Process/network side-effect traps are covered in `tests/test_python_module.py`.
- [x] T009 [US1] Implement the approved exact candidate capability profile and file/attribute fingerprints in `src/project_generator/python_compat.py`, preserving historical capability state shape.
- [x] T010 [US1] Bind and revalidate the candidate profile through `src/project_generator/plan.py`, `src/project_generator/python_module.py` and `src/project_generator/transaction.py` without executing project checks during planning or applying.
- [x] T011 [US1] Add a credential-free, test-only public mirror in `scripts/prepare_candidate_ci.py` with tests in `tests/test_prepare_candidate_ci.py`; fetch the exact historical, release and candidate commits, verify each commit and its required file hashes, and fail closed without branch/tag fallback; wire candidate and historical pinned integration into the Linux/Windows baseline job in `.github/workflows/ci.yml`; do not change `scripts/gh_access.py`, `scripts/prepare_template_ci.py`, private retrieval, `GH_TOKEN` handling or private-authentication reporting.

## Phase 4: User Story 2 - Preserve Existing Projects

**Goal**: Retain the historical profile, output projections and snapshot semantics.

**Independent test**: Compare established module/CI states and exercise existing
snapshot and historical-plan behavior before and after the change.

- [x] T012 [US2] Add or extend historical planning coverage for Python, TypeScript, Java and React, plus profile identity and generated CI byte-regression cases in `tests/test_python_compat.py`, `tests/test_python_module.py` and `integration/test_t0003_integration.py`.
- [x] T013 [US2] Verify historical snapshot and reverse-order restore behavior with existing fixtures in `tests/test_safety_core.py` and `integration/test_t0003_integration.py`; add focused cases only where missing.
- [x] T014 [US2] Verify representative module combinations and Docker/PostgreSQL coexistence retain established projections in `src/project_generator/module_states.py`, `src/project_generator/infrastructure.py` and corresponding tests under `tests/`.
- [x] T015 [US2] Resolve any regressions identified by T012-T014 in the directly affected files without rewriting historical states or snapshots.

## Phase 5: User Story 3 - Reject Unsafe Changes

**Goal**: Fail closed for unknown or changed capabilities and retain migration
preflight guarantees.

**Independent test**: Tamper with each relevant prerequisite before planning
and after plan approval; confirm conflict and no target write.

- [x] T016 [US3] Add missing, unreadable, substituted, mixed-profile and modified dependency conflict tests in `tests/test_python_compat.py`.
- [x] T017 [US3] Add stale file and attribute cases before apply and after snapshot in `integration/test_t0003_integration.py`, asserting no project write.
- [x] T018 [US3] Add selective-migration destination capability and stale-precondition cases for both template profiles in `tests/test_migration_plan.py` or the existing migration test module.
- [x] T019 [US3] Apply the approved capability checks and pre-write revalidation to selective migration in `src/project_generator/migration_plan.py` and its existing transaction path, keeping the operation read-only until confirmed.

## Phase 6: Cross-Cutting Verification and Review

- [x] T020 Run `python scripts/check.py`, focused tests in `tests/`, and real-pinned integration in `integration/test_t0003_integration.py`; record exact results and skips in `docs/PROJECT_HANDOFF.md`.
- [ ] T021 Obtain Linux and Windows CI evidence for both supported bases and document missing or blocked evidence in `docs/PROJECT_HANDOFF.md`; publication requires separate approval. Hosted run `45052518437` passed on Ubuntu and Windows on `9e3f09b00ff84855ef531a0f7dc089b69562c7e1`, including five candidate and 33 historical pinned integrations per platform. Docker validation `45052518454` and secret scan `45052518444` also passed on that head, but the later mirror-hardening change is local and has not been run in hosted CI. Private authentication remains **NOT VERIFIED**; no PR, merge or release was performed.
- [x] T022 Update supported states and verification limits in `docs/GENERATOR_CONTRACT.md` and `README.md` only after evidence exists; update `docs/DV_KONZEPT.md` only for an approved decision. The docs describe the historical and candidate profiles, exact verification boundaries, and the still-unverified private-authentication and GitHub template-creation paths.
- [ ] T023 Review the final diff, converge outstanding requirements and record human Review-gate outcome in `docs/PROJECT_HANDOFF.md`; do not merge without explicit separate approval.

## Dependencies and Execution Order

The completed prerequisite investigations establish evidence for the design.
T005 reviews that design and T006 records explicit approval; no implementation
begins before T006. US1 establishes the candidate profile; US2 and US3 verify
compatibility and safety around that implementation. T020-T023 depend on all
three stories. The feature is not releasable with only US1 because historical
safety is mandatory.

## Parallel Opportunities

- No implementation tasks are marked parallel: compatibility-profile tests
  share files, while candidate and historical integration tests share the
  integration suite. Keep those edits serialized to avoid conflicts.

## Implementation Strategy

The first demonstrable increment is US1 on the candidate. US2 and US3 are
mandatory before review or merge. Existing user files and historical state remain
protected throughout; unavailable Windows or private-access checks remain open.
