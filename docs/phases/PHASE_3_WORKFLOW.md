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
   deterministic triggers never invoke a model, and the synchronous model client
   never runs on the event loop. Route arguments pass through unchanged and no
   attachment content is read: a capability that accepts raw dot-command
   arguments declares an `args` field on its input contract, and closed input
   contracts fail closed on unexpected arguments (no guessing, per the Phase 2
   migration record).
4. Keyword-triggered execution is preserved source behavior and stays
   policy-gated: routing grants nothing, so an incidental keyword match can only
   execute what the actor's LocalPolicy grants already allow, and production
   side-effecting workflows must bind approval-required capabilities.
5. Evaluation cases prove a deterministic command (dot form and keyword form)
   triggers a workflow run with no model call and no forbidden side effect.
   This satisfies the Roadmap Phase 3 exit criterion's deterministic-command and
   Agent trigger paths; the n8n adapter remains a later slice against this same
   contract.
6. This slice composes behaviors already characterized in Phases 2 and 3;
   no new source excerpt is required. All existing tests, lint, strict types,
   packaging and CI must continue to pass.

## Requirements and acceptance (slice 3 — step inputs)

1. Preserve identity-only steps and their unchanged run-argument pass-through.
   An explicit step instead declares a capability and a closed input mapping.
   Each input selects run arguments or a prior step's validated result data using
   a tuple of exact object keys / zero-based array indices. No expressions,
   implicit merging, templates, literal credentials or secret resolution.
2. Reject self/future/negative step references and malformed selectors at manifest
   validation. Missing run input is `needs_input/workflow_input_missing` before
   creating a run; missing result data stops the existing run with the same code,
   without invoking that step or subsequent steps. JSON null is a present value.
3. Every resolved step still passes through Bridge input/output validation and
   LocalPolicy. Mapping never changes authority, dependencies or trace identity.
4. Snapshot run arguments and copy selected values so caller/handler/snapshot
   mutation cannot alter subsequent inputs. Logs and failure messages omit values
   and paths. Existing timeout, cancellation and bounded history behavior stays.
5. Tests precede implementation and cover legacy compatibility, serialization,
   invalid manifests, chaining across different contracts, denied/failed steps,
   missing paths, null/arrays and Gateway integration with inert capabilities.

Implementation plan: extend `common/assets.py`; add contract/runtime tests in
`tests/test_workflow_inputs.py`; add deterministic resolution in
`workflow/engine.py`; exercise Gateway composition; then full verification,
commit and handoff. This adds no new production side effects or infrastructure.

## Requirements and acceptance (slice 4 — bounded retries and duplicate submission)

1. Legacy and explicit steps default to one attempt. Explicit steps may request
   1–3 attempts with a fixed 0–10000 ms delay (default 100 ms). Only host-installed
   `read` capabilities may request retries; reject other retry plans before any
   step executes. A trusted handler must raise `TransientCapabilityError` to mark
   a failure retryable. Timeouts, unknown exceptions, validation, missing inputs,
   authorization and dependency failures never retry.
2. Each attempt uses the same selected inputs and the same Bridge authorization
   path. Never repeat successful prior steps. Keep one terminal result per step
   for output references, plus bounded attempt metadata (no payloads). Caller
   timeout/cancellation behavior remains unchanged.
3. Optional idempotency keys belong to the caller/Gateway/engine, not model output
   or workflow metadata. Scope keys by actor and namespace in one engine instance.
   Same key and same workflow, arguments and non-trace request context reuse the
   original run (including original trace). Changed execution intent fails closed.
   Concurrent submissions and resubmission after caller timeout never start another
   task. Cached results require current authorization for all workflow capabilities.
4. Retain key records for the engine lifetime, including failures/cancellation and
   runs evicted from normal history. Bound the key table (50 by default); reject
   new keyed runs at capacity instead of silently evicting keys and risking replay.
   This is in-memory duplicate suppression, not durable exactly-once execution or
   backend idempotency. No key means a deliberate new run; no automatic whole-run
   retries, persistence, key expiry, distributed coordination or recovery.
5. Add source characterization for one-call-on-failure and independent repeated
   submissions, then contract/runtime tests for retry limits, safety/policy checks,
   chaining, payload ownership, concurrent duplicates, conflicts, history eviction,
   caller timeouts, denied replay and Gateway pass-through. Verify all existing
   contracts and cross-platform CI.

Plan: document source disposition; tests first; additive contracts in `assets.py`
and `execution.py`, typed transient error in capability runtime, retry marking in
Bridge, bounded engine orchestration, Gateway key pass-through; full verification,
small commits, PR and handoff. No production side effects are exercised.

## Incremental sequence

- Slice 1: pin and inspect the source; commit a reproducible characterization
  excerpt and tests, then implement the engine against them.
- Slice 2: add the Gateway dispatch contract with regression and evaluation
  coverage.
- Slice 3: explicit per-step inputs and prior-result chaining.
- Slice 4: bounded read retries and in-memory duplicate submission suppression.
- Later Phase 3 slices: resumable state, progress streaming, and the optional n8n
  adapter invoking the same Gateway/engine contracts.

No HTTP server, n8n integration, COM/browser/terminal services, production jobs,
scheduling or persistence are migrated by this slice. Cooperative asyncio tasks
replace fire-and-forget threads; a hung step still holds its task (the source
cannot kill threads either) and cancellation is not attempted.
