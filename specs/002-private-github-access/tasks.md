# Tasks: Private GitHub Usage of Template and Generator

**Input**: `specs/002-private-github-access/spec.md`, `plan.md`, `checklists/requirements.md`

**Architecture**: V1 – Authentication only at system boundaries. `src/project_generator/**` stays unchanged (FR-001); every increment verifies this with `git diff --stat -- src/`.

**Tests**: Written before or together with the code they cover. Increment 1 needs no private repository and no real token (local bare repositories and stub executables only).

**Conventions**: `[P]` = parallelizable. `[USn]` = user story of the spec. `STOPP` = hard human stop; nothing after it starts without a separate LOS. No task is marked done yet.

## Increment 1: Access foundation (no private repository, no token)

**Goal**: One reusable boundary helper that reads a repository reference with a per-command credential source, classifies failures and never leaks credentials.

- [ ] T001 [US1] Decide before start (human): helper location `scripts/gh_access.py` and failure categories `missing`, `expired`, `forbidden`, `not_found`, `network`, `unknown`; record in `specs/002-private-github-access/plan.md`.
- [ ] T002 [P] [US1] Add failing tests `tests/test_gh_access.py` for failure classification from git/gh stderr and exit codes (401, 403, 404, expired, no credential, offline); each category must yield a non-success result and never "compatible"/"current" (FR-007).
- [ ] T003 [P] [US1] Add failing tests in `tests/test_gh_access.py` using a local bare repository and a stub credential helper: success path, `GIT_TERMINAL_PROMPT=0` with no prompt, `GIT_CONFIG_NOSYSTEM`/`GIT_CONFIG_GLOBAL` isolation, no change to global git config and no credential in the stored remote address (FR-003).
- [ ] T004 [P] [US1] Add failing tests `tests/test_leak_scan.py` for `scripts/leak_scan.py`: a fake token pattern in logs, `.git/config`, plan JSON, snapshot and backup directories is detected; clean trees pass (FR-004).
- [ ] T005 [US1] Implement `scripts/gh_access.py` (per-command credential helper, no prompts, no persisted credential, redacted messages, classified results) until T002–T003 pass.
- [ ] T006 [US1] Implement `scripts/leak_scan.py` until T004 passes.
- [ ] T007 [US1] Add a test that the helper accepts the pinned reference `6e8363a` and still resolves, but reports the release reference `964de85` as not compatible, using local fixture repositories (FR-008, SC-006).
- [ ] T008 [US1] Run the generator suite, integration suite, template tests, `python scripts/check.py`, `git diff --check`; confirm `git diff --stat -- src/` is empty and the 16 module states and eight historical byte states pass (FR-016, SC-005).

**Review Gate 1** (human): Review test evidence per failure category, the leak-scan results, the empty `src/` diff and the redaction behaviour. Without approval, nothing from Increment 2 starts.

---

## Increment 2: CI and integration on private-capable retrieval (public template still used)

**Goal**: Tests, update check and CI use the helper, a pinned reference and a trusted/untrusted split; behaviour against the public template is unchanged.

**Prerequisite decision (human, before T009)**: deploy key versus fine-grained token comparison (see Open Decisions D1) – may remain open until T015.

- [ ] T009 [US2] Add tests that `integration/test_t0003_integration.py` uses the helper and the pinned reference, keeps `COMPATIBLE`/`RELEASE` distinct, and reports missing access as skipped/not verified, never passed (FR-006, FR-007, FR-008).
- [ ] T010 [US2] Change `integration/test_t0003_integration.py` to use `scripts/gh_access.py` (mirror hook `T0004_T0003_MIRROR` preserved).
- [ ] T011 [P] [US3] Add tests for `scripts/update_check.py` in `tests/`: no access → "nicht geprüft (Zugriff fehlt)", never "aktuell"; access → versions compared, no file written (FR-007).
- [ ] T012 [US3] Change `scripts/update_check.py` to use the helper.
- [ ] T013 [P] [US2] Change `scripts/docker_ci.py` to use the helper and the pinned reference; add a test for the fetch behaviour.
- [ ] T014 [US2] Update `.github/workflows/ci.yml` and `.github/workflows/docker-validation.yml`: credential only in the retrieval step via a secret, `persist-credentials: false` kept, no `pull_request_target`, template-dependent steps skipped with an explicit "not verified" message when the secret is absent (FR-005, FR-006). With no secret configured and the public template, behaviour stays identical.
- [ ] T015 [US2] Add a workflow/template test in `.github/template-tests/` that asserts: no `pull_request_target`, SHA-pinned actions, minimal `permissions`, secret scoped to the step.
- [ ] T016 [US2] Run all local suites again (as T008) plus `git diff --stat -- src/`.

**STOPP before any token**: Creating or configuring any token, secret or deploy key requires a separate human LOS.

**Review Gate 2** (human): Four green hosted jobs (Ubuntu/Windows baseline, Docker Linux/Windows) for push and PR, plus a deliberate untrusted run (fork or secret-less) that shows "skipped/not verified". Decision D1 documented.

---

## Increment 3: Private test copies and acceptance run (requires human actions)

**Goal**: Real end-to-end proof on private test copies for scenarios A–D, including negative permission tests.

**STOPP 3a**: Naming and account of the private test copies decided (D2); user creates the private copies himself or explicitly authorizes it. No creation before this LOS.

**STOPP 3b**: Token creation (fine-grained, `Contents: read`, single repository, short expiry) only on an explicit LOS; the token is never shown in agent context (FR-014).

- [ ] T017 [US4] Verify the permissions for creating a private repository from a private template (`POST /repos/{template}/generate`) separately from read access with a throwaway private copy; record the required credential type and permission in `specs/002-private-github-access/research.md` (FR-012). Mark anything not confirmed as unverified.
- [ ] T018 [US4] Populate private test copies only from reviewed, pinned commits (no `--mirror`, no all-branches/all-tags transfer); document commit SHAs in `specs/002-private-github-access/research.md` (FR-010).
- [ ] T019 [P] [US1] Scenario A (public template → private project) and B (private template → private project): create, install modules, plan, apply, no-op, restore.
- [ ] T020 [P] [US1] Scenario C (private generator → private template → private project) and D (authenticated versioned base retrieval and update of an existing private project with local changes).
- [ ] T021 [US2] Negative tests: no access, wrong repository scope, expired credential, missing secret, untrusted run; each must end non-successfully or "not verified" (SC-002).
- [ ] T022 [US4] Run the leak scan over logs, git config, remote addresses, plans, snapshots, backups of all acceptance runs (SC-003).
- [ ] T023 [US4] Compile the acceptance matrix `specs/002-private-github-access/acceptance.md` (case, expected, observed, date, evidence).
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
- Gate 1 → T009; T010 after T009; T012 after T011 and T005; T014 after T010, T012, T013; T015 after T014; T016 last.
- Gate 2 and STOPP 3a/3b → T017; T018 after T017; T019–T021 after T018; T022 after T019–T021; T023 after T022; T024 after T023.
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
- **D3** t0003 `main` vs. release tag handling – must be decided before Increment 2 (affects pinning in T009–T014).
- **D4** Separate private p9999 copy – may stay open until Increment 3.
