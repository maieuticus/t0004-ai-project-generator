# Feature Specification: Template Compatibility

**Feature Branch**: `feature/template-compatibility-003`

**Created**: 2026-11-22

**Status**: Draft

**Input**: Support the renewed `t0003-ai-project-template` in the generator without
losing compatibility with the previously verified template state.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Use the Current Template (Priority: P1)

A developer creates a project from the renewed template and selects a generator
module. The generator produces a safe, reviewable plan instead of rejecting the
project solely because its verified template checks have changed.

**Why this priority**: New projects must be able to use the current template and
the generator together.

**Independent Test**: For each supported module, plan and explicitly apply the
module in a fresh project created from the identified template state, run its
appropriate project checks, and restore the change.

**Acceptance Scenarios**:

1. **Given** a fresh project at the identified renewed template state, **When** a
   developer plans any of the four supported language modules, **Then** the plan
   does not report the verified template check as an unknown state.
2. **Given** an approved plan for that project, **When** the developer applies it
   and subsequently restores it, **Then** the affected project files return to
   their prior state and unrelated files remain unchanged.
3. **Given** a project with an installed unchanged module, **When** the developer
   plans that module again, **Then** the result is a no-op.

### User Story 2 - Preserve Existing Projects (Priority: P1)

A developer with a project based on the historically verified template can keep
using the generator without an automatic template upgrade or changed recovery
semantics.

**Why this priority**: Supporting new projects must not break projects and backups
that users already rely on.

**Independent Test**: Exercise representative historical projects and existing
snapshots using the established compatibility and restore checks.

**Acceptance Scenarios**:

1. **Given** a project at the historically verified template state, **When** a
   supported module is planned and applied, **Then** the existing supported
   behavior and generated file states are preserved.
2. **Given** a valid historical snapshot and its expected target state, **When**
   it is restored, **Then** its established restore behavior is preserved.
3. **Given** a historical project or snapshot, **When** the generator is used,
   **Then** it does not silently replace the template or rewrite existing files.

### User Story 3 - Reject Unsafe Changes (Priority: P1)

A developer receives an explicit conflict when a required template capability
is missing, altered, or changed after planning, rather than having the generator
write to an unverified project.

**Why this priority**: Compatibility must not weaken the existing safety boundary.

**Independent Test**: Alter each required capability before planning and between
planning and application, then confirm that no project write occurs.

**Acceptance Scenarios**:

1. **Given** an unknown or modified required template capability, **When** a
   developer plans a module, **Then** the generator reports a conflict and does
   not produce an executable module change.
2. **Given** a previously approved plan whose required capability changes,
   **When** the developer applies it, **Then** the generator rejects it before
   the first project write.
3. **Given** a project with the renewed template, **When** a developer plans a
   permitted selective migration, **Then** the same verified compatibility
   boundary is applied to the destination.

### Edge Cases

- The original release state remains distinct from the historically verified
  compatible state and is not accepted merely because its release label matches.
- Missing, unreadable, substituted, or modified required check dependencies are
  not treated as verified.
- A changed target, stale plan, conflicting existing file, or modified snapshot
  continues to be rejected according to the existing safety contract.
- Existing language-module combinations and supported infrastructure continue to
  coexist without silently changing their established projections.
- A later template commit is not automatically considered compatible with the
  specifically verified renewed state.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The generator MUST support the historically verified template state
  and the specifically verified renewed template state for all four existing
  language modules.
- **FR-002**: The generator MUST preserve established behavior for existing
  projects, generated states, snapshots, and restore operations.
- **FR-003**: The generator MUST verify the required check and CI capabilities,
  including dependencies required by the renewed template check, before accepting
  a project for module planning or selective migration.
- **FR-004**: A module plan MUST bind its required verified capabilities to the
  project state, and application MUST reject a changed prerequisite before the
  first project write.
- **FR-005**: Unknown, missing, or modified required capabilities MUST produce an
  explicit conflict rather than an automatic update or an executable module plan.
- **FR-006**: Planning MUST remain read-only and MUST NOT run project checks,
  render diagrams, install tools, or contact external services.
- **FR-007**: Application and restoration MUST retain explicit confirmation,
  conflict detection, protected snapshots, and existing recovery rules.
- **FR-008**: Existing module combinations and supported infrastructure MUST
  retain their established projections and compatibility behavior.
- **FR-009**: Selective migration into the renewed template MUST enforce the same
  verified destination capabilities and safety boundaries as module planning.
- **FR-010**: Compatibility evidence MUST distinguish the historical compatible
  commit, the renewed compatible commit, and the published release; it MUST NOT
  imply that unverified template states are compatible.
- **FR-011**: Documentation MUST state the supported template states, their
  verification limits, and any checks not performed.

### Key Entities

- **Template state**: A specific, verifiable set of template capabilities used
  as the basis for a project.
- **Project plan**: A reviewable set of proposed operations bound to the target
  and required project state.
- **Snapshot**: A protected record used to restore changes under the existing
  safety contract.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All four existing language modules can be planned on both the
  historical verified state and the renewed verified state without a template
  compatibility conflict.
- **SC-002**: Representative apply, no-op, and restore scenarios succeed on the
  renewed state, and historical regression scenarios retain their expected results.
- **SC-003**: Each tested missing, altered, or stale required capability is rejected
  without a project write; no unknown template state is silently accepted.
- **SC-004**: Compatibility evidence covers Linux and Windows, with any unavailable
  check explicitly identified rather than reported as passed.

## Assumptions

- The historical compatible state is commit `6e8363a7ac7d99220d743eea077dcd5cefda9042`;
  the renewed candidate is `8ee48ed15eea629e51c8e4a64102c6a06cf8726a`.
  The candidate becomes supported only after the required verification.
- Existing module and infrastructure selections remain unchanged. Automatically
  updating existing projects, adopting all new template rules in this repository,
  and changing the strategy-B migration package are outside this feature.
- Existing approval gates and the separation between published release and
  independently verified compatibility remain in force.
