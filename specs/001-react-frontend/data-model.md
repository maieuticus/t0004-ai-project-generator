# Data Model: Optional React Frontend

This feature introduces no application database or persisted user data. The generator
manages only the existing project metadata, deterministic file projection, and
transaction snapshot.

| Entity/state | Representation | Invariants |
|---|---|---|
| React module identity | Proposed fixed `react@0.1.0` entry in `generator.modules` | Optional, unique, canonical order after Python/TypeScript/Java; no dynamic registration. |
| React file projection | Fixed template files and starter docs under generated `react/`, plus project-level `docs/REACT.md` | Deterministic bytes; no overwriting foreign paths; separate lockfile from `typescript/`. |
| Project check | Fixed check entry in `config/project.yaml` | Canonical module order; run only through the project check, never during plan/apply. |
| CI state | One deterministic CI result per subset of four fixed modules | Sixteen closed states; the existing eight states without React retain their exact bytes. |
| Docker-supported module subset | Existing Python, TypeScript and Java modules only | React adds no Docker service; React alone cannot satisfy the Compose prerequisite. |
| Format-4 plan and snapshot | Existing plan identity, preconditions, operations and protected backup manifest | Explicit plan confirmation; preflight revalidation; conflict-safe reverse-order restore. |

The React-to-TypeScript prerequisite is resolved as independent installation in
[Clarifications](spec.md#clarifications). No data migration is required.
