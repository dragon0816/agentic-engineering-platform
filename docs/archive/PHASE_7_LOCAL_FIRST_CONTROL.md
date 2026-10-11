# Phase 7 local-first control implementation plan

Owner decision: 2026-09-22. This plan implements the already-approved Personal
Engineering Plane and Team Platform Plane boundaries in `docs/ARCHITECTURE.md`.

## Requirements

- Company workstations operate through a local Agent and Bridge. Installed assets,
  complete run state and corporate credentials remain local.
- The shared platform distributes governed, versioned assets. Publication and an
  installation plan grant no execution authorization.
- A company computer may be controlled remotely only by its single bound owner. A
  shared test computer may be controlled by its bound platform users. Both accept
  only typed, authorized Workflow jobs.
- Telegram is a future ingress to the resident local Agent. Its sender must map to a
  bound platform actor and pass the same authorization rules as platform ingress.
- Shared status is a timestamped projection. Local Bridge state is authoritative and
  a disconnected projection is visibly stale.
- Remote control excludes arbitrary shell/desktop access and production side effects
  in this slice. CI and the reference implementation remain inert.

## Contract-first slice

1. Add package, installation, local inventory, local run summary, Bridge snapshot,
   projected status and channel-explicit remote Workflow job contracts.
2. Test closed validation, exact hashes, whole-plan install refusal, offline local
   inventory, stale projections, actor/authorization matching and device membership
   enforcement before implementing the references.
3. Implement an in-memory package Registry/local verified inventory and an in-memory
   member-scoped job queue with bounded polling. No artifact is imported or run.
4. Verify the complete suite and leave the local UI, authentication and network
   transports for the next independently reviewable slice.

## Reversibility

The slice adds new contracts/reference modules and documentation only. Removing them
does not alter the existing workflow engine, Bridge executor, enrollment reference,
Windows preview package or source repositories.
