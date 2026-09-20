# Phase 3 — Workflow platform

Implementation scope derived from the approved Roadmap and Architecture. The first
slice adapts the run-tracking and execution semantics of the pinned
`rs_workflow_system` Host Bridge job runner into a deterministic workflow engine
that executes `WorkflowManifest` steps through the shared Bridge policy path.
Source decisions are recorded in `docs/PHASE_3_MIGRATION.md`.

## Requirements and acceptance (slice 1)

1. Workflows are explicitly installed `WorkflowManifest`s selected by exact scoped
   version. No directory scanning, module import, reload or discovery-time code
   execution; installation is trusted host configuration.
2. Executing an uninstalled workflow returns a typed unavailable result without
   creating a run record (the source's no-ghost-run invariant). Secret-dependent
   and centrally-dependent workflows fail unavailable before a run is created.
3. Steps execute sequentially through `BridgeExecutor`. Every step is authorized
   independently by `LocalPolicy`; the workflow itself grants no authority. The
   first non-succeeded step ends the run with that step's status and failure code.
4. Run tracking preserves the source semantics: bounded in-memory history (last
   50 runs), bounded log (5000 lines plus one truncation marker) and a caller-wait
   timeout that leaves the run running and is overwritten by the final state.
5. Run logs carry step identities, statuses and codes only — never arguments,
   payloads or exception text. Step results are returned in snapshots; logs never
   duplicate them.
6. Characterize the pinned source runner before implementing. Regression tests
   cover success, step failure, authorization denial, timeout-not-final, retention,
   log cap and ghost-run paths with inert doubles. All existing tests, lint,
   strict types, packaging and CI must continue to pass.

## Requirements and acceptance (slice 2 — Gateway dispatch)

1. One `Gateway.handle` contract dispatches a routed request: needs-input
   outcomes return unexecuted, capability targets dispatch through
   `BridgeExecutor`, workflow targets through `WorkflowEngine`. The result pairs
   the routing outcome with exactly the execution its decision names.
2. The Gateway adds no authority and contains no domain logic: step and
   capability authorization stay in `LocalPolicy`, workflow pre-flights in the
   engine. A denied route fails exactly as it would when invoked directly.
3. Deterministic and model-selected routes dispatch through the same contract;
   deterministic triggers never invoke a model. Route arguments pass through
   unchanged and no attachment content is read.
4. Evaluation cases prove a deterministic command (dot form and keyword form)
   triggers a workflow run with no model call. This satisfies the Roadmap
   Phase 3 exit criterion's deterministic-command and Agent trigger paths; the
   n8n adapter remains a later slice against this same contract.
5. This slice composes behaviors already characterized in Phases 2 and 3;
   no new source excerpt is required. All existing tests, lint, strict types,
   packaging and CI must continue to pass.

## Incremental sequence

- Slice 1: pin and inspect the source; commit a reproducible characterization
  excerpt and tests, then implement the engine against them.
- Slice 2: add the Gateway dispatch contract with regression and evaluation
  coverage.
- Later Phase 3 slices: step argument chaining and per-step inputs,
  retry/idempotency, resumable state, progress streaming, and the optional n8n
  adapter invoking the same Gateway/engine contracts.

No HTTP server, n8n integration, COM/browser/terminal services, production jobs,
scheduling or persistence are migrated by this slice. Cooperative asyncio tasks
replace fire-and-forget threads; a hung step still holds its task (the source
cannot kill threads either) and cancellation is not attempted.
