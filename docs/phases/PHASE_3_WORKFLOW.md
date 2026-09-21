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

## Requirements and acceptance (slice 5 — bounded resumable state)

1. Every declared step of a run is classified from recorded evidence as
   `completed` (terminal success), `never_started` (no handler ran — the Bridge
   records `handler_invoked` on every result and attempt, so this is evidence,
   not a code table) or `uncertain` (any attempt invoked a handler without
   terminal success, or the run was interrupted at that step). A live run
   reports `running`. `inspect(context, run_id)` returns this `ResumePlan` only
   to the owning actor/namespace; it carries codes and indices, never payloads.
2. `resume(context, run_id, policy)` continues a finished run as a **new** run from
   its first non-completed step. Completed steps are never repeated; their
   recorded results feed later step inputs. The original run is immutable history
   and the new run records `resumed_from`.
3. An uncertain step is replayed only under an explicit `ResumePolicy`: the
   default rejects with `needs_input/uncertain_side_effect`; `replay_read_only`
   replays only when the host-installed capability is classified `read`;
   `replay_side_effects` is an explicit acceptance of a possible duplicate side
   effect. Publication metadata and workflow manifests cannot grant replay.
4. Resumption adds no authority: the requesting actor and namespace must match the
   original run, every remaining step is re-authorized by `LocalPolicy` before a
   run exists and again at dispatch, and the workflow's pre-flight checks rerun.
   Running and complete runs are rejected; unknown, evicted and other actors'
   runs are indistinguishable (None). A run can be continued once — resume its
   continuation afterwards — so a retried host call never re-executes
   never-started side effects. Pre-flight rejections, including `StepInput`
   references into completed results, create no run record.
5. Resumption is in-memory only: it shares the 50-run history, bounded logs and
   caller-wait timeout semantics, never consults or consumes idempotency keys and
   provides no persistence, crash recovery or durable step-state store.
6. Characterize the pinned source step table (linear steps, no re-entry, pending
   after failure, no resume) before implementing; regression tests cover every
   classification, policy branch, re-authorization, chaining, repeated resumption,
   cancellation, eviction and key independence with inert doubles.

## Requirements and acceptance (slice 6 — Gateway run control)

1. `Gateway.inspect(request, run_id)` and `Gateway.resume(request, run_id,
   policy=...)` are the host-facing run-control entry points, so CLI, Agent
   runtime and a future n8n adapter trigger resumption through the same Gateway
   and engine contracts as routed workflows. Results are a typed
   `RunControlResult`; both payload fields None means the run is unknown to
   this caller (missing, evicted or owned by another actor).
2. The Gateway adds no authority and no parsing: ownership, pre-flight and
   per-step re-authorization stay in the engine, and `ResumePolicy` is a
   host/caller option never derived from the request message or a model.
3. Run control is not a Skill route. No deterministic or model-selected route
   can inspect or resume a run; a model proposing such a route fails closed as
   before, and routed workflow arguments cannot smuggle a resumption.
4. Regression tests cover the result contract, inspect-then-resume with policy,
   no-authority (denied then granted), other-actor indistinguishability, message
   and model isolation. This composes already-characterized behavior; no new
   source excerpt is required.

## Requirements and acceptance (slice 7 — progress streaming)

1. `WorkflowEngine.watch(context, run_id)` (and `Gateway.watch`) returns a bounded
   progress stream of typed `RunProgress` events for the run's owner: a snapshot
   of the current state, then every state change (`step_started`,
   `step_finished`), then the terminal `finished` event. A finished run yields
   one terminal snapshot carrying its status and code. Unknown, evicted and
   other actors' runs return None; malformed ids fail validation.
2. Events carry identities, statuses, step indices and failure codes only —
   never arguments, payloads or exception text — and report a live run as
   `running` (the caller-wait overlay is not evidence).
3. Reporting never changes a run's outcome (preserved from the source's
   `on_change`/ops mirroring): each watcher has a bounded queue, a slow consumer
   never blocks the run, dropped events are surfaced as `lagged` on the next
   delivered event instead of silently, and the terminal event always arrives so
   a consumer cannot hang. Watchers per run are bounded; excess subscriptions get
   a single `rejected/watch_capacity` event rather than an unbounded queue, and
   a consumer that stops iterating releases its slot.
4. Streams are in-memory and end with the run; no persistence, replay history,
   transport or dashboard is provided. Characterize the source `on_change`
   semantics first; regression tests cover contract validation, live and finished
   streams, ownership, lag, capacity, cancellation and Gateway pass-through.

## Requirements and acceptance (slice 8 — optional offline n8n adapter)

Owner selected this direction after PR #14 merged. Persistence remains unscoped.

1. An optional Python adapter accepts a closed `N8nSubmission` (stable operation
   id plus JSON arguments). Trusted host configuration binds one exact workflow
   version and a stable binding id. The host supplies authenticated RequestContext
   separately; payloads cannot supply actor, target, policy, resume or transport.
2. Add `Gateway.execute_workflow` as the shared exact-target entry point. Routed
   workflows and the adapter both call it, preserving the engine/Bridge contracts.
   Adapter submission never parses commands, calls a model, adds permissions or
   implements engineering logic. Return the existing WorkflowRunSnapshot unchanged.
3. Derive an engine idempotency key from binding id and operation id. Re-delivery
   of the same intent joins/returns the same run; changed arguments/context/target
   conflict. New operation ids are new work. No adapter-level retry, resume, cache
   or idempotency store. Existing engine-lifetime/capacity limits remain explicit.
4. Adapter inspect/watch reuse Gateway owner checks and restrict results to the
   bound workflow. Unknown, other-owner and other-workflow ids remain undisclosed.
   Progress remains bounded and payload-free; consumers must close streams.
5. Characterize the pinned n8n source graph: trigger -> parameters -> Bridge
   dispatch -> success/failure branch. No HTTP, n8n runtime, production job, model,
   notification, transport or secret is connected. Package an offline submission
   example and document the host seam, status mapping and deployment limitations.
6. Tests first: input validation, direct/routed/n8n path parity, explicit binding,
   denial/dependencies, duplicate/conflicting/concurrent submissions, timeout,
   changed identity, owner isolation and progress through inert handlers. Full
   regression/lint/types/build and Windows/Linux CI must pass.

Plan: pin a source-graph projection and regression tests; add optional
`integrations.n8n` and shared Gateway exact-workflow dispatch; document the offline
host wiring; verify, commit, PR and handoff. No persistence code in this slice.

## Requirements and acceptance (slice 9 — checkpoint contracts)

Owner approved single-Bridge manual restart recovery scope after PR #15 merged.
The first slice defines contracts and a memory reference model, not disk storage
or engine recovery. See `docs/WORKFLOW_CHECKPOINTS.md` for the normative plan,
retention, sensitive-data boundary, write ordering and failure semantics.

- Add versioned owner-scoped run/step evidence and opaque protected payload refs.
- Define atomic creation/key binding, revision checks and parent/continuation creation.
- Completed results are immutable; incomplete started steps are uncertain on restart.
- No automatic resume; retain existing ResumePolicy and fresh Bridge authorization.
- Tests precede implementation, including validation and failed/ambiguous write windows.
- Preserve all existing engine/Gateway/n8n behavior; full tests, lint, types and build.

## Requirements and acceptance (slice 10 — SQLite checkpoint backend)

Owner approved scope (2026-09-21): a single local SQLite file per Bridge using
the standard library only; one transaction per `create` / `replace` /
`continue_run`, acknowledged only after commit; the `CheckpointStore` protocol
only — no engine wiring, no payload storage, no automatic recovery.

1. `SqliteCheckpointStore` implements the same protocol and passes the same
   contract suite as the memory reference model; the transition rules are shared
   code so the two backends cannot drift.
2. Every write is one `BEGIN IMMEDIATE` … `COMMIT` transaction. A failure before
   commit rolls back and reports `unavailable` (known not committed); a failure
   during commit reports `commit_unknown`, and the caller must read back before
   proceeding. A second writer on the same file is refused (`unavailable`), never
   waited for.
3. Evidence, key bindings, continuation links and capacity survive closing and
   reopening the file; an unknown schema version refuses to open. Records hold
   checkpoint evidence and `PayloadRef`s only.
4. The file location is host configuration; nothing is written inside the
   project. All slice-9 invariants (owner isolation, no TTL/eviction/deletion,
   capacity rejection, write-ahead ordering) apply unchanged.
5. Tests: the parametrized contract suite over both backends plus SQLite
   durability tests (restart, capacity after restart, key reuse after restart,
   schema refusal, second writer, closed store, commit failure before/after the
   real commit, failure inside a transaction).

## Requirements and acceptance (slice 11 — protected payload storage)

Owner approved scope (2026-09-21): a content-addressed local store beside the
checkpoint file (file name is the digest), schema validated before writing,
digest and contract verified on reading, owner-isolated directories whose
permissions are the host's responsibility; no secrets, no TTL/deletion, no
engine wiring.

1. `PayloadStore.put(owner, contract, payload)` canonicalises the value, stores
   it under its own SHA-256 and returns the `PayloadRef` a checkpoint records;
   equal values share one file, so repeated writes are idempotent.
2. Writes are atomic and never leave a partial payload; an oversized or
   unserializable value is refused before anything is written.
3. `get(owner, ref)` returns the payload only when the identifier is one this
   store issues, the bytes still hash to it, the payload hashes to `ref.sha256`
   and the stored contract matches; tampering, truncation, a swapped file, a
   wrong contract and an unknown reference each fail closed with a distinct
   closed code.
4. The owner is part of the stored record and is checked on every read, so one
   owner's reference cannot read another owner's payload even on a
   case-folding filesystem, and a file name is derived from a validated digest
   only, never from caller text.
5. Tests cover round trips for every JSON shape, deduplication, restart,
   tampering, mismatched references, owner isolation, limits and failed writes.

## Requirements and acceptance (slice 12 — engine recovery)

Owner approved scope (2026-09-21), option A of three: suspension is **purely
manual**. The platform never probes processes, reads PIDs or takes leases; a
person confirms that the owning process is gone and the confirmation is
recorded. B (process liveness) and C (leases) can be layered on later.

1. The journal is optional: without it the engine behaves exactly as before.
2. Write-ahead ordering on the real execution path: arguments and the run record
   commit before execution; `started` is acknowledged before each dispatch and a
   failed or ambiguous write forbids that dispatch; the result payload commits
   before the step is recorded complete; the final completion and the terminal
   marker are one write.
3. `suspend` requires a `SuspensionConfirmation` whose
   `process_confirmed_stopped` is exactly `True`, writes the operator and note
   into the checkpoint (which requires them for every suspended record), checks
   ownership before liveness, and is refused while the run is alive here. The
   in-memory `resume()` refuses a journalled run so the durable
   "continued once" guard is never bypassed.
4. `recover` continues a suspended run in any process: the stored manifest must
   still be installed and identical, the completed prefix is restored from
   verified payloads and never re-run, pre-flight and per-step authorization run
   again, and an uncertain step obeys the existing `ResumePolicy`.
5. Tests exercise a real restart (a new engine over the same files), evidence
   after success and failure, refused dispatch without acknowledgment, refused
   suspension of a live run, changed manifests, denied re-authorization and a
   key that already names a durable run.

## Requirements and acceptance (slice 13 — Gateway run control over the journal)

1. `Gateway.inspect` answers from this process's history first and falls back to
   the durable journal, reporting which in `source`; `unknown` still covers
   missing, evicted, never-journalled and other actors' runs alike.
2. `Gateway.suspend` records a `SuspensionConfirmation` against the durable
   record. A run this caller cannot see is `unknown`; a live or already
   suspended run raises the engine's closed code, not a new vocabulary.
3. `Gateway.resume` continues a journalled run through recovery and any other
   run in memory, so the durable "continued once" guard always applies.
4. The Gateway still adds no authority: ownership, policy and every pre-flight
   stay in the engine.
5. Tests cover the result contract, memory-then-journal fallback, an
   unjournalled engine, unknown and foreign runs, suspend-then-resume across a
   restart, continue-once, resuming without a confirmation, a live run, and
   denied authorization after a restart.

## Incremental sequence

- Slice 1: pin and inspect the source; commit a reproducible characterization
  excerpt and tests, then implement the engine against them.
- Slice 2: add the Gateway dispatch contract with regression and evaluation
  coverage.
- Slice 3: explicit per-step inputs and prior-result chaining.
- Slice 4: bounded read retries and in-memory duplicate submission suppression.
- Slice 5: bounded in-memory resumption with explicit uncertain-effect policy.
- Slice 6: Gateway run-control entry points (`inspect`/`resume`).
- Slice 7: bounded progress streaming (`watch`).
- Slice 8: optional offline n8n submission adapter through Gateway.
- Slice 9: checkpoint contracts and memory reference model for manual recovery.
- Slice 10: single-writer SQLite checkpoint backend.
- Slice 11: content-addressed protected payload storage.
- Slice 12: engine recovery with manual, human-confirmed suspension.
- Slice 13: Gateway run control over durable evidence.
- Later Phase 3 work (each needs explicit scope): a Gateway surface for run
  control over the journal, and process-liveness or lease-based suspension if
  single-Bridge manual recovery ever stops being enough.

No HTTP server, n8n integration, COM/browser/terminal services, production jobs,
scheduling or persistence are migrated by this slice. Cooperative asyncio tasks
replace fire-and-forget threads; a hung step still holds its task (the source
cannot kill threads either) and cancellation is not attempted.
