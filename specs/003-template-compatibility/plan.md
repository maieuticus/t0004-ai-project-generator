# Implementation Plan: Template Compatibility

**Branch**: `feature/template-compatibility-003` | **Date**: 2026-11-22 |
**Spec**: [spec.md](spec.md)

**Status**: Architectural direction and the Analyze gate were approved by the
user on 2026-11-22; implementation is in progress.
This document was written directly from the specification and repository
evidence. The Spec Kit setup script was not executed because it evaluates
dynamically constructed shell content. This is not a completed `/speckit-plan` run.

## Summary

Add the candidate template state as a separately verified compatibility profile
while preserving the previously verified state and existing transaction semantics.
The profile is based on exact, jointly verified capability files, not the release
label or an automatically advancing branch. A profile is accepted only after the
required integration and safety evidence exists.

## Technical Context

- **Project**: Python 3.11+ CLI, standard library, existing Format-4 engine.
- **Historical compatible commit**: `6e8363a7ac7d99220d743eea077dcd5cefda9042`.
- **Candidate commit**: `8ee48ed15eea629e51c8e4a64102c6a06cf8726a`.
- **Published release**: `964de8538d19cefcb483faff38f10124615a9783`; not a
  substitute for either compatibility finding.
- **Targets**: Linux and Windows; local Python unit tests, real-commit integration
  and existing GitHub Actions checks. Missing evidence remains explicitly open.
- **Constraints**: No network, renderer, project command, or package installation
  during plan/apply. No automatic template update, historical projection rewrite,
  new permissions, or private access.

## Constitution Check

| Principle | Design response |
|---|---|
| Existing engine and simplicity | Extend the existing capability checks and transaction preconditions; no new write engine. |
| Historical states | Preserve historical capability profiles, generated CI bytes, snapshot validation and restore semantics. |
| Plan and confirmation | Bind the actual verified files and attributes to the plan; revalidate before the first project write. |
| Conflict safety | Unknown, missing, changed or stale dependencies fail closed; no silent overwrites. |
| Bounded scope | Strategy-B package changes and wholesale adoption of template updates remain out of scope. |
| Human gates | Produce tasks and pass the human Analyze gate before implementation; Review gate and separate publication approval remain required. |

The user approved the architectural direction and Analyze gate, not a claim of
verified template support. The constitution was rechecked during Analyze; no
conflict was found. Candidate retrieval, compatibility and safety checks now
pass locally against the pinned historical and candidate commits. The candidate
is not accepted as a supported or released reference until hosted Linux and
Windows evidence and the human Review gate are complete.

## Design and Alternatives

1. **Recommended: explicit compatible capability profiles.** Keep the old exact
   check, configuration and CI states. Add the independently verified candidate
   check and its required code dependencies, including `scripts/diagrams.py`,
   as a coherent profile. Reuse the known language CI projections where their
   bytes are unchanged. Plan binding includes every required profile file and
   its access attributes. The old profile retains its existing precondition
   shape so previously generated plan identities are not changed unnecessarily.
   The design must explicitly determine which inputs are executable capability
   code and which are user-maintained diagram data; do not pin all diagram
   content to the pristine template or execute it during planning.
2. **Replace the historical hash with the new one.** Rejected: existing projects
   would become unsupported and prior plan compatibility could change.
3. **Accept arbitrary checks or follow `main`.** Rejected: an unknown or modified
   check could bypass the verified capability and stale-plan protections.

The candidate's exact accepted file set and any permitted historical/new
combinations require investigation and tests before approval. Do not infer
compatibility merely from matching `template.release`.

### Profile evidence and proposed boundaries

The following SHA-256 values were computed from Git objects fetched from the
public `maieuticus/t0003-ai-project-template` repository on 2026-11-22:

| File | Historical | Candidate | Published release |
|---|---|---|---|
| `scripts/check.py` | `08be5d0fc5bddb6bbd9209c659a77456c785bfaa3ee24ebb06c20d390d6a2d4e` | `4a9dd7519b7973442d570743685eaa5184242d80b7554f6d26645ae599b1721b` | same as historical |
| `scripts/projectcfg.py` | `f446580597e0c3e7c46ab20cd31e8bbc609316a5a8ae65696da8814244832d20` | same | same |
| `scripts/diagrams.py` | absent | `79b7482172ba7460b057a94ed9dcf31d13109ed098f267a7e28546f13fd06ee7` | absent |
| `.github/workflows/ci.yml` | `f54914e7f43f14acde14b33693abdbc303784c90c84c87e6bdd7f385e22731cd` | same | `18a51ef1b44f6b7bb2347c289b2195a4e3744f910a40f3a0378cf03b2c8c0a21` |

The candidate check imports `projectcfg` and `diagrams`; `diagrams.py` imports
standard-library modules and does not import another local module. Its check
reads the diagram manifest, version pins, sources, rendered outputs and Markdown
as project data. Those user-maintained data files must not be required to match
the initial template bytes. Diagram validation is performed by the project
check, not by generator planning or application.

Proposed acceptance: the historical check plus historical `projectcfg.py` and a
known CI projection keeps its existing bound-file shape; the candidate check
requires the exact candidate `diagrams.py`, the same `projectcfg.py` and a known
CI projection. An unrelated extra `diagrams.py` does not change the historical
check's behavior. Unknown check/configuration/CI bytes, or the candidate check
with missing or changed `diagrams.py`, are conflicts. CI projections must match
the actually installed modules. Missing attributes or unsafe paths remain
conflicts under existing rules. The user approved these boundaries at the
Analyze gate. The completed local unit and real-commit integration evidence is
recorded in `docs/PROJECT_HANDOFF.md`; hosted cross-platform verification remains
open.

The existing integration source `maieuticus/t0003-private-access-test` returned
HTTP 404; its existence and the available access remain unresolved. Separately,
on 2026-11-22 the public GitHub API confirmed that candidate commit
`8ee48ed15eea629e51c8e4a64102c6a06cf8726a` is reachable in the canonical
`maieuticus/t0003-ai-project-template` repository.

Use that canonical public repository as a **test-only** source. The separate
credential-free mirror helper fetches the exact historical, release and candidate
commit IDs, verifies each commit and its capability-file hashes, and fails closed
without branch/tag fallback. The baseline workflow uses this mirror for pinned
historical and candidate integrations on Linux and Windows; generator plan/apply
remains offline. Do not change `scripts/gh_access.py`, the existing private
retrieval path, `GH_TOKEN` handling, or private-authentication status reporting.
Keep the private source's HTTP 404 explicitly unresolved. The local mirror and all
38 pinned integration tests pass. Review identified that reusing a bare mirror
could load repository-local Git configuration; the helper now requires a fresh
destination and removes `GIT_CONFIG_PARAMETERS` and `GIT_TEMPLATE_DIR`. Six
focused mirror tests pass locally. Commit
`3571d283b66da966899be0b94a7e20865471128c` passed hosted run `45056806327` on
Linux and Windows, with 308 generator tests per platform (7/17 skipped), five
candidate and 33 historical pinned integrations per platform. Docker validation
`45056806293` and secret scan `45056806307` also passed on that head. Private
authentication remains **NOT VERIFIED**. The candidate remains pending the
human Review gate.

## Affected Areas

- `src/project_generator/python_compat.py`: profile recognition, exact digests,
  capabilities, file and directory fingerprints.
- `src/project_generator/python_module.py`, `plan.py`, `transaction.py`:
  profile-bound module plans, existing preflight and historical snapshots.
- `src/project_generator/migration_plan.py`: consistent capability validation
  for selective migration, including pre-apply revalidation.
- `src/project_generator/module_states.py` and infrastructure planning: retain
  known CI and Docker/PostgreSQL projections; test module combinations and
  selective migration against both supported bases.
- `scripts/prepare_candidate_ci.py` (new),
  `tests/test_prepare_candidate_ci.py`,
  `integration/test_t0003_integration.py`, and the baseline job in
  `.github/workflows/ci.yml`:
  fetch and verify all three exact public commits into a credential-free mirror;
  pass it to the historical and candidate integration tests on Linux and Windows.
  Do not modify `scripts/gh_access.py` or the existing private
  `scripts/prepare_template_ci.py` path. The current private integration source
  is the separate `t0003-private-access-test` repository; do not assume it
  contains the candidate.
- `tests/test_python_compat.py` and existing integration/security tests: add
  focused positive, negative, stale-plan and restore cases.
- `docs/GENERATOR_CONTRACT.md`, `README.md`, and the handoff: document only
  proven support; update the DV concept only for an approved decision.

## Verification Plan

1. Verify exact bytes and dependencies from both pinned commits and the release;
   preserve existing CI projections and explicit release distinctions.
2. Test all four module plans on both bases; cover representative sequential
   combinations, no-op, application, reverse-order restore, and supported
   Docker/PostgreSQL coexistence. Include selective migration on both bases.
3. Reject missing or modified check dependencies, unknown combinations,
   changed attributes, and changes between planning and application. Verify no
   target writes. Exercise existing snapshot fixtures and historical plan
   identity/validation behavior; report any incompatibility before proceeding.
4. Run project checks, focused unit tests, and real-pinned integration tests;
   obtain Linux and Windows CI evidence. Explicitly report missing platform or
   private-access coverage rather than counting it as passed.
5. Inspect the final diff and complete human Review gate before any requested
   PR, merge or release.

## Scope and Open Gates

- The human Review gate was approved on 2026-11-22 after the final diff and
  verification evidence were reviewed. PR creation was authorized on 2026-11-22;
  merge and release were not authorized. The branch review alone does not claim
  a published support or release state.
- A strategy-B baseline update and adoption of the new diagram standard in this
  generator repository are separate scope decisions.
- Human Analyze approval is recorded; implementation and human Review remain
  open. The task list was generated through the Spec Kit tasks workflow.
- No production changes, tests of the new implementation, or merge have occurred.
