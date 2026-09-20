# Development Handoff

## Current phase and branch

Phase 3 — Workflow platform, second slice (Gateway dispatch through one contract).
Branch: `phase-3/gateway-dispatch`, based on `main` commit `ac2e312`.
`main` contains the merged Phase 1 baseline (PR #4), the Phase 2
routing/dispatch/MCP slice (PR #6, which superseded auto-closed PR #5), the
`filesystem/read-file` adapter (PR #7) and the Phase 3 workflow engine (PR #8).
Review evidence lives in the PR #4, #5, #7 and #8 comment threads.

## Goal

Wire routed requests to execution through one Gateway contract so deterministic
commands and model-selected (Agent) routes trigger the same capability/workflow
paths, satisfying the Roadmap Phase 3 exit criterion's trigger requirement. Scope
and acceptance: `docs/phases/PHASE_3_WORKFLOW.md` (slice 2); source decisions:
`docs/PHASE_3_MIGRATION.md`.

## Completed

- Slice 1 (merged as PR #8): characterized and adapted the pinned
  `rs_workflow_system` job runner (`896046e`) into `src/workflow/engine.py` —
  explicit workflow installation, sequential step dispatch through
  `BridgeExecutor` with per-step LocalPolicy authorization, comprehensive
  pre-flight checks without ghost runs, 50-run history, 5000-line capped logs,
  caller-wait timeouts overwritten by the final state, and final-state recording
  on cancellation. CI branch filter extended to `phase-*/**`.
- Slice 2 (this branch): `src/agent/gateway.py` — `Gateway.handle` pairs a
  routing outcome with exactly the execution its decision names (needs-input
  returns unexecuted; capability via Bridge; workflow via engine), enforced by
  the `GatewayResult` contract validator. The Gateway adds no authority and
  holds no domain logic; a denied route fails exactly as a direct invocation.
- Added the `release` Skill manifest (workflow and capability command bindings)
  and `evaluation/cases/phase3-workflow-trigger.json`: a dot command and a
  Chinese keyword each trigger a workflow run deterministically with zero model
  calls; a model-selected route is proven to dispatch through the same contract.
- 7 gateway regression tests; phase spec extended with slice 2 requirements.

## Remaining

- Later Phase 3 slices: step argument chaining and per-step inputs,
  retry/idempotency, resumable state, progress streaming, and the optional n8n
  adapter invoking the same Gateway/engine contracts.
- Host Bridge HTTP surface, terminal/excel/email/browser capability adapters,
  production jobs, scheduling and persistence are not migrated.
- Follow-ups recorded in PR #4/#5 review comments remain open (bounded
  `BridgeExecutor` event log, SkillRegistry re-parse cost, MCP install
  round-trips, Review `not_required` semantics, generic top-level package names).

## Architecture decisions made

- ADAPT job-runner run-tracking semantics; explicit installed manifests replace
  `jobs/` directory scanning, lazy import and mtime reload. The engine never
  imports job code.
- Steps are governed capabilities: every step is independently authorized by
  LocalPolicy through BridgeExecutor; the workflow itself grants no authority.
- Caller-wait timeouts bound only the caller's wait (preserved from the source);
  a timed-out run reports `failed`/`workflow_timeout` until the driving task
  records the final state. Cooperative asyncio tasks replace threads; cancellation
  is not attempted.
- Logs carry identities, statuses and codes only; step results carry validated
  outputs for the caller. Ops mirroring/step tables/x-ui are not migrated.

## Exact verification commands and results

Run from repository root with the existing .venv (Windows, Python 3.12.14).

```powershell
.venv/Scripts/python.exe -m pytest -q
# PASS: 164 tests (157 prior + 7 gateway)
.venv/Scripts/python.exe -m ruff check .
# PASS
.venv/Scripts/python.exe -m ruff format --check .
# PASS
.venv/Scripts/python.exe -m mypy
# PASS: 37 source/test files
.venv/Scripts/python.exe -m pip check
# PASS
.venv/Scripts/python.exe -m build
# PASS; the release Skill manifest and phase3 evaluation cases ship in the sdist
git diff --check
# PASS
```

No production service, transport, model, job or n8n instance was invoked; tests
use inert doubles only.

## Known issues / limitations

- Cooperative deadlines are not process isolation; a blocking step handler still
  freezes its task. Production handlers must offload blocking work (see
  `docs/CONTRACTS.md` and the `filesystem/read-file` precedent).
- Run history and logs are in-memory only; persistence/resumability is a later
  Phase 3 slice.
- The same run arguments go to every step; chaining is deliberately deferred.

## Next Recommended Action

Review and merge the `phase-3/gateway-dispatch` PR against `main`. After merge,
continue Phase 3 with step argument chaining and per-step inputs (the engine
currently passes the same run arguments to every step), then retry/idempotency
and resumable state per the phase specification.
