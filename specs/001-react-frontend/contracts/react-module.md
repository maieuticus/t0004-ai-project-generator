# React Module Contract (Approved Design)

This contract describes the approved public and generated-project behavior. The user
approved the Analyze gate on 2026-11-05. Generator integration remains unimplemented.

## Selection and transaction

- Planned selector: `--module react` on the existing `plan` and `new` commands.
- Approved metadata identity: `react@0.1.0`, stored in the existing ordered
  `generator.modules` list.
- Planning is read-only and reports conflicts before any operation.
- Apply accepts only the saved plan and its explicit confirmation through the existing
  Format-4 command.
- Every Apply snapshots its original state. Restore checks generator-managed and
  user-modified paths and is performed in reverse Apply order.
- A complete, unchanged React installation is a no-op without a new snapshot.

## Generated project behavior

- The React frontend resides in its own `react/` directory and does not require or
  modify the existing `typescript/` console module.
- A package lockfile fixes the frontend dependency graph.
- Documentation explains local dependency installation, starting and stopping the
  preview, and running the project check.
- The example renders in a browser and includes a visible response to a user action.
- React introduces no backend, authentication, production deployment, Dockerfile,
  Compose service, port publication, or secret.

## CI and compatibility

- The existing project check validates the React package after its dependencies are
  installed.
- The existing Linux/Windows CI jobs install the lockfile only when React is selected.
- The 8 existing module-only CI byte states remain unchanged; the fixed set becomes
  16 states with React.
- Existing TypeScript files/bytes and Docker/PostgreSQL projections remain unchanged.
- Docker's supported service set remains Python, TypeScript and Java. React may
  coexist with an already valid Docker/PostgreSQL installation but is not a service
  and cannot satisfy the prerequisite for Docker by itself.

## Failure behavior

- Existing foreign paths, changed managed files, unsupported metadata, stale plans,
  or incomplete prerequisites produce explicit conflicts.
- Failed dependency installation, verification, or preview must not be reported as a
  successful project check.
- No npm, build, Docker, or application command is executed by planning or Apply.
