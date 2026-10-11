# Phase 2 — Agent and capability layer

Implementation scope derived from the approved Roadmap and Architecture. Phase 1
PR #4 is still open; `phase-2/implementation` stacks on commit `006e5b6`. Neither
PR is to be merged by the coding agent.

## Requirements and acceptance

1. Preserve channel-neutral request/trace identity and add opaque attachment metadata.
2. Register governed Skill procedures separately from executable capabilities.
   Explicit installed Skill aliases select exact scoped versions, never implicit latest.
3. Resolve dot commands and ordered known keyword/workflow routes before any model.
   Missing/invalid explicit commands return needs-input without attempting execution.
4. Allow one provider-neutral model selection for otherwise ambiguous requests.
   Validate its proposed route against installed candidates; it cannot grant authority.
5. Register explicit typed handlers in the execution plane. Bridge dispatch must
   enforce host-configured actor/asset permissions and execution approval independently
   of publication or business review, validate inputs/outputs, and bound async calls.
6. Adapt MCP discovery/calls through an injected client boundary. Discovery alone
   cannot install or authorize tools. Transport implementations remain external.
7. Keep attachment refs intact through dispatch; do not read/upload/write attachment
   contents or put attachment references into model prompts automatically.
8. Exercise source-characterization, deterministic routing, model failure, authorization,
   input/output errors, dependency availability and MCP call paths with inert doubles.
   All Phase 1 tests, lint, strict types, packaging and CI must continue to pass.

## Incremental sequence

- Pin and inspect source; commit a reproducible characterization excerpt and tests.
- Add typed Skill/routing/attachment contracts and regression tests, then implement
  installed Skill discovery and deterministic/model selection.
- Add permission/dependency/timeout tests, then implement Bridge dispatch and the
  injected MCP adapter. No production handler or provider is installed by default.
- Verify, commit coherent slices, update HANDOFF, push and open a stacked review PR.

No production workflow engine (Phase 3), device controls, channel server/UI,
provider integration (Phase 5), RBAC server, secret backend, or specialist agents.
The synchronous model client must enforce its own I/O deadline; this layer performs
one selection with bounded output and no retry loop. Async handler deadlines are
cooperative cancellation, not process isolation or rollback.
