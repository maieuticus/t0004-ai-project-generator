# Feature Specification: Release Readiness Verification

**Feature Branch**: `feature/verify-release-prerequisites`

**Created**: 2026-11-22

**Status**: Draft

**Input**: User authorized completing the existing release prerequisites before publishing and selected a repository/release gate: local checks plus separately proven CI and practical-test evidence. The approved project concept requires the t0003/t0004 integration and four practical tests: `new` on Linux and Windows, and `migrate` on Linux and Windows.

## User Scenarios & Testing

### User Story 1 - Determine Release Readiness (Priority: P1)

As a maintainer, I want one repository-level verification outcome that combines local checks with separately proven CI and practical-test evidence, so that I can make an informed release decision without mistaking missing evidence for success.

**Why this priority**: A release must not proceed when a required compatibility check or practical test has failed or has not been run.

**Independent Test**: Provide complete successful evidence, then separately provide a failed or missing result; confirm the reported readiness changes accordingly and identifies the relevant criterion.

**Acceptance Scenarios**:

1. **Given** successful Linux and Windows verification reports, **When** the maintainer aggregates them, **Then** the final report says ready and lists the evidence for each required criterion.
2. **Given** any required check or platform-specific practical test failed or lacks evidence, **When** the maintainer requests final verification, **Then** the report says not ready and identifies the failed or missing criterion.
3. **Given** the maintainer runs verification on only one platform, **When** evidence for the other required platform is absent, **Then** aggregation reports not ready and identifies the missing platform evidence.

### User Story 2 - Validate New Projects on Both Platforms (Priority: P1)

As a maintainer, I want to complete and record the approved `new` project workflow on Linux and Windows, so that platform-specific failures are found before release.

**Why this priority**: Creating and initializing a new project is a core generator workflow and is explicitly required by the approved release plan.

**Independent Test**: Run the `new` workflow in isolated test projects on Linux and Windows and retain a separate pass/fail result for each platform.

**Acceptance Scenarios**:

1. **Given** a supported t0003 project source, **When** the maintainer completes the Python-module `new` workflow on Linux, **Then** the isolated project passes its project check and the result is recorded.
2. **Given** a supported t0003 project source, **When** the maintainer completes the Python-module `new` workflow on Windows, **Then** the isolated project passes its project check and the result is recorded.

### User Story 3 - Validate Migration on Both Platforms (Priority: P1)

As a maintainer, I want to complete and record the approved `migrate` workflow on Linux and Windows, so that its read-only inventory and strategy comparison are reliable on both supported platforms.

**Why this priority**: Migration is the other required end-user workflow and must be demonstrated alongside `new` before release.

**Independent Test**: Run the `migrate` workflow against isolated migration fixtures on Linux and Windows; verify the inventory and strategy comparison and record a separate result for each platform.

**Acceptance Scenarios**:

1. **Given** an eligible source project, **When** `migrate` runs on Linux, **Then** it completes the read-only inventory and strategy comparison without changing the source, and the result is recorded.
2. **Given** an eligible source project, **When** `migrate` runs on Windows, **Then** it completes the read-only inventory and strategy comparison without changing the source, and the result is recorded.

## Edge Cases

- A platform runner or required external test dependency is unavailable; that platform's result is reported as not verified and cannot count as a pass.
- A local fixture passes but a required pinned-template integration fails; overall readiness is not reported as ready.
- A workflow partially completes or produces incomplete evidence; its result is reported as failed or not verified, not successful.
- Private template authentication remains unverified; the verification must preserve that limitation and must not imply that private access was tested.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST provide a repository-level final verification outcome covering the release prerequisites defined in the approved project concept.
- **FR-002**: The final outcome MUST report each required criterion as passed, failed, or not verified, identify whether its evidence is local or separately produced, and identify the relevant evidence or blocker.
- **FR-003**: The overall outcome MUST be not ready if any required criterion failed or lacks evidence.
- **FR-004**: The verification MUST include distinct results for `new` on Linux, `new` on Windows, `migrate` on Linux, and `migrate` on Windows.
- **FR-005**: The migration results MUST establish that the inventory and strategy comparison are read-only with respect to the source project.
- **FR-006**: The verification MUST keep private authentication and GitHub repository creation via “Use this template” explicitly outside the verified claims unless separately approved and tested.
- **FR-007**: Verification MUST NOT publish a tag or release, create a pull request, or change the project's release version or changelog.
- **FR-008**: A local result MUST NOT be presented as evidence that another operating system or an unrun integration was verified.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Aggregating one Linux report and one Windows report produces one repository-level outcome listing every required criterion, its evidence source, and an overall ready/not-ready result.
- **SC-002**: All four required platform/workflow combinations have separately recorded results before the outcome can be ready.
- **SC-003**: In every case where a required result is failed or missing, the overall outcome is not ready and names that criterion.
- **SC-004**: Final verification leaves release metadata and publication state unchanged.
- **SC-005**: The `migrate` evidence for both platforms confirms that source-project files remain unchanged.
- **SC-006**: A verification run on one operating system alone never produces a ready result when evidence for the other required operating system is absent.

## Assumptions

- The four required practical tests are exactly those in `docs/DV_KONZEPT.md`: `new` on Linux and Windows, and `migrate` on Linux and Windows.
- The `verify` capability is a repository/release gate; cross-platform and practical-test evidence may be produced separately and must be explicitly available to the final outcome.
- The representative `new` practical test uses the supported Python module on both platforms; this provides one stable end-to-end project-check scenario without adding another language toolchain requirement.
- Tests use isolated project copies and the approved pinned public template states; creating a GitHub repository through “Use this template” is not part of these four tests.
- Private authentication remains **NOT VERIFIED** and is not expanded into this feature.
- Publishing a release remains a separate action requiring its own authorization and release-version decision.
