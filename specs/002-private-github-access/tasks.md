# Tasks: Private GitHub Usage of Template and Generator

**Input**: `specs/002-private-github-access/spec.md`, `plan.md`, `checklists/requirements.md`

**Architecture**: V1 – Authentication only at t0004 system boundaries. `src/project_generator/**` stays unchanged (FR-001); the inherited t0003 `scripts/update_check.py` remains independently runnable and has no t0004-helper dependency. Every increment verifies this with `git diff --stat -- src/`.

**Tests**: Written before or together with the code they cover. Increment 1 needs no private repository and no real token (local bare repositories and stub executables only).

**Conventions**: `[P]` = parallelizable. `[USn]` = user story of the spec. `STOPP` = hard human stop; nothing after it starts without a separate LOS. No task is marked done yet.

## Increment 1: Access foundation (no private repository, no token)

**Goal**: One reusable boundary helper that reads a repository reference with a per-command credential source, classifies failures and never leaks credentials.

- [x] T001 [US1] Fix the t0004-only boundary contract for `scripts/gh_access.py`: failure categories are `missing`, `expired`, `forbidden`, `not_found`, `network`, `unknown`; the inherited t0003 `scripts/update_check.py` has no import or runtime dependency on it (FR-001).
- [x] T002 [P] [US1] Add failing tests `tests/test_gh_access.py` for failure classification from git/gh stderr and exit codes (401, 403, 404, expired, no credential, offline), including Windows-compatible environment setup; each category must yield a non-success result and never "compatible"/"current" (FR-007).
- [x] T003 [P] [US1] Add failing tests in `tests/test_gh_access.py` using a local bare repository and a stub of the existing credential helper: success path, `GIT_TERMINAL_PROMPT=0` with no prompt, `GIT_CONFIG_NOSYSTEM`/`GIT_CONFIG_GLOBAL` isolation, no new credential store or credential-like argument, no change to user/global Git configuration and no credential in the stored remote address (FR-002, FR-003, FR-014).
- [x] T004 [P] [US1] Add failing tests `tests/test_leak_scan.py` for `scripts/leak_scan.py`: a fake token pattern in logs, subprocess output, `.git/config`, plan JSON, snapshot and backup directories is detected and redacted; clean trees pass (FR-004, FR-014).
- [x] T005 [US1] Implement `scripts/gh_access.py` (per-command use of the existing credential helper, no prompts, token arguments or persisted credential, redacted messages and classified results) until T002–T003 pass.
- [x] T006 [US1] Implement `scripts/leak_scan.py` until T004 passes.
- [x] T007 [US1] Add local-fixture tests with an independent generated-project Git history: identify `6e8363a` as the compatible basis and `964de85` as rejected by checking existing contract-file digests, project metadata and permitted historical module/CI states; do not copy Git history. Resolve the default branch and report drift from `6e8363a` without writes (FR-008, FR-009, SC-006).
- [ ] T008 [US1] Run the generator suite, integration suite, template tests, `python scripts/check.py`, `git diff --check`; confirm `git diff --stat -- src/` is empty and the 16 module states and eight historical byte states pass (FR-016, SC-005).

**Review Gate 1** (human): Review test evidence per failure category, the leak-scan results, the empty `src/` diff and the redaction behaviour. Without approval, nothing from Increment 2 starts.

---

## Increment 2: CI and integration on private-capable retrieval (public template still used)

**Goal**: Tests and CI use the helper, a pinned reference, default-branch drift detection and a trusted/untrusted split; the inherited t0003 update check remains separately runnable and behaviour against the public template is unchanged.

**Prerequisite decision (human, before T014)**: deploy key versus fine-grained token comparison (see Open Decision D1); document the result in T015.

- [ ] T009 [US2] Add tests that `integration/test_t0003_integration.py` uses the helper and the pinned reference, keeps `COMPATIBLE`/`RELEASE` distinct, detects default-branch drift, and reports missing access as skipped/not verified, never passed (FR-006, FR-007, FR-008, FR-009).
- [ ] T010 [US2] Change `integration/test_t0003_integration.py` to use `scripts/gh_access.py` (mirror hook `T0004_T0003_MIRROR` preserved).
- [ ] T011 [P] [US3] Add a contract test proving that the inherited `scripts/update_check.py` remains independently runnable, has no `scripts/gh_access.py` import or invocation and reports an unreachable source as "nicht geprüft"; defer private authenticated operation to Increment 3 (FR-001, FR-007).
- [ ] T013 [P] [US2] Change `scripts/docker_ci.py` to use the helper and the pinned reference; add a test for the fetch behaviour.
- [ ] T014 [US2] Update `.github/workflows/ci.yml` and `.github/workflows/docker-validation.yml`: credential only in the retrieval step via a secret, `persist-credentials: false` kept, no `pull_request_target`, template-dependent steps skipped with an explicit "not verified" message when the secret is absent on Linux and Windows (FR-005, FR-006, FR-013).
- [ ] T015 [US2] Add a workflow/template test in `.github/template-tests/` that asserts: no `pull_request_target`, SHA-pinned actions, minimal read permissions, no workflow/job-level secret environment, secret scoped to the retrieval step and no secret in fork pull-request jobs (FR-005, FR-006, FR-013, FR-014).
- [ ] T016 [US2] Run all local suites again (as T008) plus `git diff --stat -- src/`.

**STOPP before any token**: Creating or configuring any token, secret or deploy key requires a separate human LOS.

**Review Gate 2** (human): Four green hosted jobs (Ubuntu/Windows baseline, Docker Linux/Windows) for push and PR, plus a deliberate untrusted run (fork or secret-less) that shows "skipped/not verified". Decision D1 documented.

---

## Increment 3: Private test copies and acceptance run (requires human actions)

**Goal**: Real end-to-end proof on private test copies for scenarios A–D, including negative permission tests.

**STOPP 3a**: Naming and account of the private test copies decided (D2); user creates the private copies himself or explicitly authorizes it. No creation before this LOS.

**STOPP 3b**: Token creation (fine-grained, `Contents: read`, single repository, short expiry) only on an explicit LOS; the token is never shown in agent context (FR-014).

- [ ] T017 [US4] Verify the permissions for creating a private repository from a private template (`POST /repos/{template}/generate`) separately from read access with a throwaway private copy; record the required credential type, minimal permission and explicit approval in `specs/002-private-github-access/research.md` (FR-012, FR-013). Mark anything not confirmed as unverified.
- [ ] T018 [US4] Populate private test copies only from reviewed, pinned commits (no `--mirror`, no all-branches/all-tags transfer); document commit SHAs in `specs/002-private-github-access/research.md` (FR-010).
- [ ] T019 [P] [US1] Scenario A (public template → private project) and B (private template → private project): create, install every supported module, then plan, apply, no-op and restore.
- [ ] T020 [P] [US1] Scenario C (private generator → private template → private project) and D (authenticated versioned-base retrieval and read-only comparison of an existing private project with local changes).
- [ ] T021 [US2] Negative tests on Linux and Windows: no access, wrong repository scope, expired credential, missing secret and untrusted fork pull-request run; each must end non-successfully or "not verified" (SC-002, SC-004).
- [ ] T022 [US4] Run the leak scan over logs, git config, remote addresses, plans, snapshots, backups and command capture of all acceptance runs; human evidence confirms that no agent command received a credential and that exactly one read-only, single-repository credential was exposed only to retrieval steps (FR-004, FR-005, FR-013, FR-014, SC-003, SC-004).
- [ ] T030 [US3] Run the inherited t0003 `scripts/update_check.py` separately against the private test template with the user's existing sign-in; record its result as external acceptance evidence and confirm no t0004 helper was used (FR-001, FR-002, FR-007).
- [ ] T023 [US4] Compile the acceptance matrix `specs/002-private-github-access/acceptance.md` (case, expected, observed, date, evidence), including the checked unchanged visibility and state of the production template, generator and existing test repository (FR-011, FR-017, SC-007).
- [ ] T024 [US4] Remove or document the throwaway test credentials and copies (rollback; revoke token).

**Review Gate 3** (human): Acceptance matrix, negative cases, leak-scan evidence. Production repositories are still unchanged (FR-011).

---

## Increment 4: Documentation and visibility decision

**Goal**: Operable documentation and an approved switch plan; no visibility change inside this increment.

- [ ] T025 [P] [US4] Document the permission matrix per step, credential creation, rotation, revocation and the manual steps in `docs/QUICKSTART.md` and `README.md` (FR-015).
- [ ] T026 [P] [US4] Document in `docs/DV_KONZEPT.md` the decision, the compatible-vs-release template reference rule and that public forks/copies stay public (FR-015, FR-009).
- [ ] T027 [US4] Update `docs/GENERATOR_CONTRACT.md` with the boundary-only authentication rule and unchanged core guarantee.
- [ ] T028 [US4] Write the switch plan with preconditions, order (template, then generator), rollback and verification steps in `specs/002-private-github-access/switch-plan.md`.
- [ ] T029 [US4] Update `docs/PROJECT_HANDOFF.md`; run `python scripts/check.py` and `git diff --check`.

**STOPP 4a**: Any change to the visibility of t0003, t0004 or p9999 needs its own LOS after Review Gate 4 and is not part of these tasks.

**Review Gate 4** (human): Documentation review and approval of the switch plan.

---

## Dependencies

- T002–T004 before T005–T006; T005 before T007; T008 after all of Increment 1.
- Gate 1 → T009; T010 after T009; T011 remains independent of the t0004 helper; T014 after T010 and T013; T015 after T014; T016 last.
- Gate 2 and STOPP 3a/3b → T017; T018 after T017; T019–T021 and T030 after T018; T022 after T019–T021 and T030; T023 after T022; T024 after T023.
- Gate 3 → T025–T029; T028 after T025–T027.

## Estimated effort

| Increment | Effort |
|-----------|--------|
| 1 | 1–1.5 days |
| 2 | 1.5–2 days (plus ~15 min Windows CI per run) |
| 3 | 1–2 days plus waiting on human actions |
| 4 | 0.5–1 day |

## Open decisions

- **D1** Deploy key vs. fine-grained token – may stay open until Gate 2.
- **D2** Name and account of test copies – must be decided before Increment 3.
- **D4** Separate private p9999 copy – may stay open until Increment 3.
