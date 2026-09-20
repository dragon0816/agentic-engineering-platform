# Development Handoff

## Current phase and branch

Phase 3 — Workflow platform, first slice (deterministic workflow engine).
Branch: `phase-3/workflow-engine`, based on `main` commit `c45515e`.
`main` contains the merged Phase 1 baseline (PR #4), the Phase 2
routing/dispatch/MCP slice (PR #6, which superseded auto-closed PR #5) and the
`filesystem/read-file` adapter (PR #7). Review evidence for those slices lives
in the PR #4, #5 and #7 comment threads.

## Goal

Adapt the run-tracking and execution semantics of the pinned `rs_workflow_system`
Host Bridge job runner into a typed deterministic `WorkflowEngine` that executes
installed `WorkflowManifest` steps through the shared Bridge policy path. Scope
and acceptance: `docs/phases/PHASE_3_WORKFLOW.md`; source decisions:
`docs/PHASE_3_MIGRATION.md`.

## Completed

- Pinned `rs_workflow_system` commit `896046e8fe2170d21f9213e56e5ce2f93c05ba43`;
  inspected the job runner, routers and services. Source unchanged.
- Committed a checksum-verified excerpt of the job runner's run-tracking core and
  7 characterization tests (bounded history/logs, caller-wait timeout that never
  finalizes a run, no ghost runs, structured failure recording, non-dict result
  wrapping) before implementing.
- Implemented `src/workflow/engine.py`: `InstalledWorkflows` (explicit exact-version
  installation, no discovery or code import) and `WorkflowEngine` (sequential step
  dispatch through `BridgeExecutor`, per-step LocalPolicy authorization, pre-flight
  secret/connectivity checks without ghost runs, 50-run history, 5000-line capped
  logs with one truncation marker, caller-wait timeout overwritten by the final
  state, logs free of arguments/payloads/exception text).
- 10 engine regression tests mirror the characterized semantics with inert doubles.
- Updated ROADMAP/ARCHITECTURE status lines and the CLAUDE.md active-phase pointer
  to Phase 3.

## Remaining

- Later Phase 3 slices: step argument chaining and per-step inputs,
  retry/idempotency, resumable state, progress streaming, wiring deterministic
  command and Agent workflow routes to the engine through one contract, and the
  optional n8n adapter invoking that same contract.
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
# PASS: 155 tests (138 prior + 7 job-runner characterization + 10 engine)
.venv/Scripts/python.exe -m ruff check .
# PASS
.venv/Scripts/python.exe -m ruff format --check .
# PASS
.venv/Scripts/python.exe -m mypy
# PASS: 35 source/test files
.venv/Scripts/python.exe -m pip check
# PASS
.venv/Scripts/python.exe -m build
# PASS; source_jobrunner.txt ships in the sdist
git diff --check
# PASS
```

Characterization tests were written and run against the pinned excerpt before the
engine was implemented. No production service, transport, model, job or n8n
instance was invoked; tests use inert doubles only.

## Known issues / limitations

- Cooperative deadlines are not process isolation; a blocking step handler still
  freezes its task. Production handlers must offload blocking work (see
  `docs/CONTRACTS.md` and the `filesystem/read-file` precedent).
- Run history and logs are in-memory only; persistence/resumability is a later
  Phase 3 slice.
- The same run arguments go to every step; chaining is deliberately deferred.

## Next Recommended Action

Open the review PR for `phase-3/workflow-engine` against `main`, run the review,
and after merge continue with the next Phase 3 slice: wire `RouteDecision`
workflow intents from the Phase 2 router to `WorkflowEngine.execute` through one
contract, with an evaluation case proving a deterministic command triggers a
workflow without a model call.
