# Handoff — Phase 3 progress streaming

Updated: 2026-09-21 (Asia/Taipei).
Branch: `phase-3/progress-streaming`, based on `main` at `0bc5556` (PR #13 merged).

## Goal

Complete Phase 3 slice 7: bounded progress streams so a run's owner can follow
every state change through the same engine/Gateway contracts, without reporting
ever changing a run's outcome. Requirements: `docs/phases/PHASE_3_WORKFLOW.md`
(slice 7); source decision: `docs/PHASE_3_MIGRATION.md` (slice 7).

## Completed

- Characterized the source `StepTable.on_change` semantics on the existing pinned
  excerpt: every transition is reported with the table, and a raising hook never
  fails the step (`test_source_reports_every_transition_and_never_fails_a_step_over_reporting`).
- Contract (`common/execution.py`, additive): `ProgressEvent` and `RunProgress`
  (`sequence`, `run_id`, `workflow`, `event`, `status`, `completed_steps`,
  `step_index`, `code`, `lagged`) with shape validation; identities, statuses and
  codes only.
- Engine: `_Watcher` bounded queues; `_emit` at launch (`started`), before/after
  each step (`step_started`/`step_finished`) and at completion (`finished`, then
  end-of-stream); `watch(context, run_id)` returns an async iterator for the
  owner — a live run yields a `snapshot` then changes then `finished`; a finished
  run yields one terminal `snapshot`; unknown/evicted/other actors' runs return
  None. A full queue drops events and marks `lagged` on the next delivered one;
  the terminal event always arrives (older queued events are dropped to make
  room) so a consumer cannot hang. At most 16 watchers per run; excess
  subscriptions get one `rejected/watch_capacity` event. `WorkflowEngine(
  watch_queue_size=256)` (minimum 2). Emission is wrapped so reporting can never
  change a run's outcome; a live run reports `running`.
- `Gateway.watch(request, run_id)` passes through with no added authority.
- 16 progress tests (`tests/test_workflow_progress.py`): contract validation and
  round trip, live stream ordering/sequence/no payloads, finished snapshot,
  ownership, slow consumer (lag + guaranteed terminal), watcher capacity,
  cancellation, queue-size guard, Gateway pass-through.
- Docs: phase spec slice 7, migration slice-7 decision, `docs/CONTRACTS.md`
  "Phase 3 progress streaming", README.
- PR #14 opened; pre-merge review applied: a consumer that stops iterating now
  releases its watcher slot (`_stream` finally); a finished run's terminal
  snapshot carries its failure code; `Gateway.watch` validates `RunId` like
  `inspect`/`resume`; the unreachable `started` event was removed (a watcher
  cannot exist before a run id does); `_emit` isolates each watcher so one
  failure cannot starve the rest; `watch_queue_size` is guarded on assignment
  and in `_Watcher`; replays and rejections no longer advance `sequence`; the
  timing-dependent tests now gate handlers on an `asyncio.Event` instead of
  sleeping.

## In Progress

- PR #14 is open with the review posted; CI results for the final head are
  recorded on the PR.

## Remaining

- Review and merge the progress-streaming PR after the posted review.
- Later Phase 3 slices: the durable step-state/persistence contract (must be
  scoped explicitly with the owner before any persistence code) and the optional
  n8n adapter invoking the same Gateway/engine contracts (it could consume
  `watch` streams for notifications).
- Earlier deferred reviews remain: bounded Bridge event history, SkillRegistry
  parse cost, MCP installation round trips, Review `not_required` semantics,
  generic top-level package names, repeated RequestContext validation.

## Architecture decisions made

- ADAPT the source's "report every transition, never fail the run" semantics into
  in-process bounded streams; the ops dashboard transport is not migrated.
- Best-effort delivery is explicit, not silent: bounded queues, `lagged` marking,
  guaranteed terminal delivery, bounded watchers with a typed capacity rejection.
- Streams are owner-scoped like `inspect`/`resume`, carry no payloads, report a
  live run as `running`, and end with the run. No persistence or replay history.

## Exact verification commands and results

Windows, Python 3.12.14, repository root:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 294 tests (277 prior + 1 characterization + 16 progress)
.venv/Scripts/python.exe -m ruff check .
# PASS
.venv/Scripts/python.exe -m ruff format --check .
# PASS: 66 files
.venv/Scripts/python.exe -m mypy
# PASS: 45 source/test files
.venv/Scripts/python.exe -m build
# PASS: sdist and wheel
git diff --check
# PASS
```

The characterization test was added before the engine changes. No production
service, transport, model, job or n8n instance was invoked; inert doubles only.
Local pytest uses `-p no:cacheprovider` because of temporary-directory ACLs on
this machine; CI runs ordinary pytest.

## Known issues / limitations

- Streams are in-memory and end with the run; there is no replay of events
  emitted before a watcher attached (the initial `snapshot` covers the gap).
- Events are emitted only for run-level state changes; retry attempts are
  visible in `WorkflowRunSnapshot.attempts`, not as stream events.
- Progress tests gate handlers on an `asyncio.Event`, so event order does not
  depend on scheduler timing.

## Next Recommended Action

Open the PR for `phase-3/progress-streaming` against `main`, run the review,
apply confirmed findings and let the owner merge. Then choose with the owner
between the durable step-state contract (scope first) and the n8n adapter.
