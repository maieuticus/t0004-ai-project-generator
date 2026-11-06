# Feature Specification: Private GitHub Usage of Template and Generator

**Feature Branch**: `nicht angelegt (nur Spezifikation; Branch am Umsetzungs-Gate)`

**Created**: 2026-11-05

**Status**: Draft

**Input**: User description: "Meilenstein 1 – Spezifikation der privaten GitHub-Nutzung (Variante V1, Authentifizierung an den Systemgrenzen)"

## Clarifications

### Session 2026-11-05 (user decisions)

- Q: Welche Architekturvariante? → A: V1. Authentication only at the system boundaries (helper scripts, tests, CI). Generator core, plan/apply/restore and all historical states stay unchanged and network-free.
- Q: Welche Authentifizierung? → A: Existing GitHub authentication for interactive use. For CI, if needed, a fine-grained token with read-only content access limited to the private template; a read-only deploy key only after a documented comparison. No write tokens without concrete need.
- Q: Welche Template-Referenz? → A: `main` of the template remains the source for "Use this template". Automated tests use an explicitly pinned compatible reference.
- Q: Versionsunterschied? → A: Template commit `6e8363a` (compatible) and release `964de85` (rejected) stay distinct and documented.
- Q: Wo entstehen private Testkopien? → A: In the existing GitHub account, never in production repositories.
- Q: Öffentliche Forks und Kopien? → A: Treated as already published content; later privacy does not retract them.
- Q: Wann werden t0003/t0004 privat? → A: Only after complete acceptance, including a real end-to-end run.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Use the System with a Private Template (Priority: P1)

A developer with read access to a private template creates a private project from it,
installs the generator and adds modules. Every step that reads the template works with
the developer's existing GitHub sign-in and never prompts for a password or token.

**Why this priority**: Making the system private is only valid if the existing flow
works end to end without public access.

**Independent Test**: With a private test copy of the template, create a private test
project and complete plan, apply, no-op and restore for each supported module; then
repeat the read step without access and verify it is refused.

**Acceptance Scenarios**:

1. **Given** a private template copy and a signed-in developer with read access, **When** the documented steps run, **Then** the project is created private and all steps complete without public access.
2. **Given** the same setup, **When** the compatibility reference is retrieved, **Then** exactly the pinned compatible state is used, not the release state.
3. **Given** a developer without read access, **When** a step needs the template, **Then** it stops with a clear "access missing, not checked" message and a non-success result.

---

### User Story 2 - Run Verification in CI Without Over-Privileged Secrets (Priority: P1)

The generator's automated checks retrieve the private template with the smallest read
permission, only for trusted runs, and report untrusted runs honestly as not executed.

**Why this priority**: A private template breaks today's anonymous retrieval; a careless
fix would expose credentials.

**Independent Test**: Run checks for a trusted and an untrusted change; the first passes
with the read permission, the second reports "skipped, not verified"; no credential
appears in any output.

**Acceptance Scenarios**:

1. **Given** a trusted run with the read credential, **When** integration checks run, **Then** they retrieve only the pinned reference and pass on all supported operating systems.
2. **Given** an untrusted run without secret access, **When** checks run, **Then** template-dependent checks are reported skipped or not verified, never passed.
3. **Given** a missing, expired or insufficient credential, **When** checks run, **Then** they fail or skip with a non-secret message naming the cause category (missing, expired, forbidden, not found).

---

### User Story 3 - Check for Updates and Retrieve a Versioned Base Securely (Priority: P2)

A developer of a private project checks for newer template versions and retrieves a
specific versioned base for comparison, without automatic changes or credential leaks.

**Why this priority**: Updates need authenticated reads but stay manual by design.

**Independent Test**: With and without access, run the update check; with access it
reports versions, without access it reports "not checked", never "current".

**Acceptance Scenarios**:

1. **Given** access, **When** the update check runs, **Then** versions are compared and no project file changes.
2. **Given** no access, **When** it runs, **Then** it reports "not checked (access missing)" and never "up to date".
3. **Given** a project with local changes, **When** a base is retrieved for update planning, **Then** local changes are preserved and conflicts are reported before any write.

---

### User Story 4 - Prove Safe Private Operation Before Changing Visibility (Priority: P1)

The maintainer receives an evidence package from a real end-to-end run on private test
copies and decides whether to make the production repositories private.

**Why this priority**: Existing public copies cannot be retracted; the change must follow proof.

**Independent Test**: Review the acceptance matrix, negative permission cases and leak scan.

**Acceptance Scenarios**:

1. **Given** private test copies, **When** the run completes, **Then** the matrix shows every positive and negative case with result and date.
2. **Given** all gate conditions are met, **When** the maintainer approves, **Then** the visibility change is a separate step with its own approval and rollback plan.
3. **Given** any condition fails, **When** the maintainer reviews, **Then** production visibility stays unchanged.

### Edge Cases

- Credential expires between planning and use: clean failure, no partial state.
- Credential valid but scoped to another repository: reported forbidden or not found, never success.
- Template default branch moved after pinning: pinned reference still resolves; drift is reported, never silently used.
- Release and compatible reference differ: both addressable; only the compatible one is accepted for module installation.
- Interactive credential prompts in non-interactive runs must not occur.
- A credential appearing in a remote address, configuration, log, plan, snapshot or backup fails the run.
- Fork or external contribution runs: no secrets; checks marked not verified.
- Creating a private repository from a template needs more than reading it (FR-012); read-only credentials must not be assumed sufficient.
- Public forks or copies made before the switch remain public.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Authentication MUST occur only at system boundaries (helper scripts, tests, CI). The generator core, `plan`, `apply`, `restore`, `new`, `migrate` and all historical states MUST remain unchanged and network-free.
- **FR-002**: Interactive use MUST prefer the developer's existing GitHub authentication and MUST NOT introduce a separate credential store.
- **FR-003**: Retrieval of private content MUST use a per-command credential source, MUST NOT modify global configuration or stored remote addresses, and MUST NOT prompt interactively.
- **FR-004**: No credential MUST appear in remote addresses, logs, error messages, commits, project files, plans, snapshots, backups or repository configuration; an automated scan MUST verify this in every acceptance run.
- **FR-005**: CI credentials MUST grant read-only content access limited to the single private template (or an equivalent read-only deploy key chosen after a documented comparison) and MUST be exposed only to the retrieval steps, never to a whole job or to untrusted runs.
- **FR-006**: Untrusted runs MUST NOT receive secrets and MUST report template-dependent checks as skipped or not verified.
- **FR-007**: Missing, expired or insufficient credentials, forbidden access and missing repositories MUST end non-successfully with a message naming the cause category, and MUST NEVER be reported as passed, compatible or up to date.
- **FR-008**: Automated tests MUST use the explicitly pinned compatible reference (`6e8363a`); the release reference (`964de85`) MUST remain addressable and rejected for module installation.
- **FR-009**: "Use this template" MUST continue to use the template's default branch; the system MUST detect and report when it differs from the pinned compatible reference.
- **FR-010**: Private test copies MUST be created without unreviewed transfers: only reviewed, pinned commits may be placed in a copy; no bulk mirroring of arbitrary references.
- **FR-011**: Production repositories (template, generator, existing test repository) MUST remain unchanged, including visibility, until the acceptance gate is approved.
- **FR-012**: The requirements for creating a private repository from a template MUST be documented and verified separately from those for reading it, stating credential type and permission for each.
- **FR-013**: No write credential MUST be introduced without a documented concrete need and explicit approval.
- **FR-014**: Agents MUST NOT receive credentials in their context nor gain broader repository rights; credential use in agent-run commands requires an explicit user instruction.
- **FR-015**: Documentation MUST state minimal permissions per step, rotation and revocation, manual steps, and that public forks and copies made before the change remain public.
- **FR-016**: Existing tests, the 16 module states and the eight historical CI byte states MUST pass unchanged on all supported operating systems.
- **FR-017**: A real end-to-end acceptance on private test copies, including negative permission tests, MUST pass before any visibility change.

### Key Entities

- **Template Reference**: A named, pinned template state (compatible, release, default branch) with an explicit compatibility verdict.
- **Access Credential**: A narrowly scoped read credential with source (existing sign-in, CI secret, deploy key), scope and expiry; never stored in the project.
- **Boundary Step**: Any helper, test or CI step that reads a private repository.
- **Private Test Copy**: A private, disposable copy of template, generator or project used only for acceptance.
- **Acceptance Matrix**: Table of positive and negative cases with expected and observed results and the visibility gate.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer with read access completes plan, apply, no-op and restore for all supported modules on a private test project with no credential entry beyond the existing sign-in.
- **SC-002**: 100% of defined negative cases (no access, wrong scope, expired credential, missing secret, untrusted run) end non-successfully or as "not verified", with zero reports of passed, compatible or current.
- **SC-003**: Zero credential occurrences are found by the automated scan across logs, configuration, plans, snapshots, backups and remote addresses in the full acceptance run.
- **SC-004**: CI uses exactly one read-only credential scoped to one repository, exposed to no more than the retrieval steps.
- **SC-005**: All existing tests, the 16 module states and the eight historical byte states pass unchanged, with no change to generator core files.
- **SC-006**: Both compatible and release references are retrievable in the acceptance run; only the compatible one is accepted.
- **SC-007**: The maintainer can decide on the visibility change from one evidence package in one review session; production visibility is unchanged until approval.

## Assumptions

- Private test copies live in the existing GitHub account; no new organisation or account.
- The generator core stays network-free.
- Interactive developers already use GitHub CLI sign-in or an equivalent credential helper.
- A fine-grained read-only token is the default CI credential; a deploy key only if a documented comparison shows a concrete advantage (decided at the planning gate).
- Creating a repository from a private template depends on GitHub's rules and the creator's read access; exact permission needs are verified in acceptance, not assumed (the repository-creation API endpoint is documented separately from content reads; its fine-grained permission mapping is still to be verified).
- Hosted GitHub Actions remains the only CI.
- GitHub Apps, token services and other new infrastructure are out of scope.
- Public forks and copies made earlier cannot be retracted.

## Out of Scope

- Changes to generator core, engine, plan formats or historical states.
- Changes to t0003 or the existing test repository.
- Creation of tokens, keys or private repositories during specification.
- Release automation, a `verify` command and update features beyond read-only checks.

## Planned Increments (draft)

1. **Access foundation**: shared boundary retrieval with cause-classified failures and leak-scan tests, verified against the current public template without behaviour change. *Gate 1:* test evidence, unchanged core.
2. **CI and integration**: pinned reference, trusted/untrusted separation, skip semantics; still against the public template. *Gate 2:* four green hosted jobs plus a deliberate untrusted run.
3. **Private test copies and acceptance**: user-created private copies, read-only credential, negative permission tests, leak scan, real project creation. *Gate 3:* acceptance matrix and evidence.
4. **Documentation and visibility decision**: minimal-permission guide, rotation/revocation, public-fork note, switch plan with rollback. *Gate 4:* approval; visibility change executed as a separate step.
