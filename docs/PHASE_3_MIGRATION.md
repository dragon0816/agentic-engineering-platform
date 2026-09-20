# Phase 3 source inspection and disposition

Source: `dragon0816/rs_workflow_system`, commit
`896046e8fe2170d21f9213e56e5ce2f93c05ba43` (read-only inspection).

| Source | Observed behavior | Decision and preserved boundary |
| --- | --- | --- |
| `host-bridge/app/services/jobrunner.py` | module-per-job discovery with lazy import and mtime reload; `PARAMS_SCHEMA`/`STEPS`/`run(params, log)` contract; thread-pool execution; ring buffer of the last 50 runs; 5000-line capped logs with one truncation marker; caller-wait timeout that never finalizes the run; unknown jobs leave no ghost run; best-effort ops mirroring that may never change an outcome | ADAPT the run-tracking and execution semantics into a typed `WorkflowEngine` that executes installed `WorkflowManifest` steps through `BridgeExecutor`; explicit installation replaces filesystem discovery |
| `host-bridge/app/routers/*.py` (FastAPI surface) | HTTP endpoints for jobs, workflows, fs, terminal, excel, email, browser | NOT MIGRATED in this slice; platform contracts replace the HTTP shape, and a serving layer is separate later work |
| `host-bridge/app/services/` terminal/excel/email/browser | Windows COM, PowerShell and Playwright local capabilities | NOT MIGRATED; future capability adapters behind the shared Bridge policy path, one characterization-backed slice each |
| `workflows/*.json` | n8n workflow definitions and business automations | NOT MIGRATED; n8n remains an optional adapter that must invoke the same contracts (Roadmap Phase 3, later slice) |

## Characterization and intentional differences

`tests/fixtures/source_jobrunner.txt` is a verbatim line excerpt of the pinned
source's run-tracking core (imports, limits, `_now`, `Caller`, `JobRun`,
`JobRegistry`, `_job_callable`, `run_sync`, `run_async`, `get_run`). Discovery,
step-table, options/x-ui, telemetry and publishing helpers are excluded and
replaced by inert test doubles. The fixtures README records full-source and
excerpt checksums. Characterization runs inert callables on the excerpt's own
thread pool; no job module, network, dashboard or host capability executes.

Preserved semantics, each pinned by a characterization test and mirrored by an
engine regression test:

- Bounded in-memory run history (last 50 runs) and bounded run logs
  (5000 lines plus exactly one truncation marker).
- A caller-wait timeout bounds only how long the caller waits; the run keeps
  executing and its final state overwrites the timeout state.
- An unknown workflow/job leaves no ghost run record. The engine extends this
  load-before-create order to every statically checkable pre-flight: declared
  secrets, missing local capabilities, required central services and uninstalled
  step capabilities all reject before a run exists.
- Structured failure information on the run rather than raised into the caller's
  result path; recording/observability must never change a run's outcome.

Intentional differences:

- Explicit installed `WorkflowManifest`s replace `jobs/` directory scanning, lazy
  import, mtime-based reload and discovery-time validation. The platform Registry
  and installation lifecycle own asset validation; the engine never imports code.
- Steps are governed capabilities dispatched through `BridgeExecutor`, so every
  step is independently authorized by `LocalPolicy` grants; the workflow itself
  grants no authority. The source executed `module.run` directly with no
  per-operation authorization.
- Fire-and-forget threads become cooperative asyncio tasks. A hung step still
  holds its task — the source cannot kill threads either — and cancellation is
  not attempted. There is no separate `timeout` status: a timed-out run reports
  `failed` with code `workflow_timeout` until the driving task records the final
  state.
- Typed contracts replace stringly dicts: `WorkflowRun`/`CapabilityResult`
  snapshots instead of `snapshot()` dicts, `Failure` codes instead of
  `{"code", "message"}` with exception text. Logs carry identities, statuses and
  codes only; step arguments, payloads and exception text never enter logs.
- Non-dict result wrapping (`{"value": …}`) is not migrated; step outputs are
  validated typed contracts.
- `startedAt`/`finishedAt`/`durationMs` run timestamps are dropped from run
  tracking in this slice; timing belongs to trace/observability and persistence
  work in later slices rather than the in-memory run record.
- Ops mirroring, step tables, options menus, x-ui schemas, reference-set
  publishing and worker identity are dashboard concerns, not migrated. Trace
  events on the Bridge remain the observability hook.
- Per-run params go to every step unchanged in this slice; step argument
  chaining is deliberately deferred and recorded in the phase specification.

Rollback: remove `src/workflow/engine.py` and the Phase 3 tests/fixtures; Phase 1/2
contracts and the source repository remain untouched. No production parity claim.
## Slice 3 source-first decision

Decision: **ADAPT** the existing engine, retaining the characterized runner
semantics. Re-inspected the pinned `jobrunner.py` excerpt in
`tests/fixtures/source_jobrunner.txt`: `_job_callable` invokes
`module.run(dict(params or {}), run.append_log)`; parameter transformation inside
a job belongs to job code, not a declarative runner mapping contract. There is
no mapping implementation in that runner boundary to wrap. Add a small typed
selector at the manifest/engine boundary, while reusing Bridge dispatch and the
existing characterization suite. This is not migration of production job logic
or a claim of source-job parity; the source remains unchanged. Rolling back the
new structured steps leaves identity-only workflow manifests supported.

## Slice 4 source-first decision

Re-inspected full `host-bridge/app/services/jobrunner.py` and `host-bridge/jobs/_steps.py`
at the same pinned `896046e8fe2170d21f9213e56e5ce2f93c05ba43` revision.
`_job_callable` calls `module.run` once, `_wrap` records and rethrows failures,
and `_steps.run` records failure and rethrows rather than retrying. Repeated
`run_sync` submissions each create a new UUID/run; there is no idempotency-key
contract at that runner boundary. No production job or older n8n retry loop is
imported. Existing pinned excerpt covers the behavior under adaptation.

Decision: **ADAPT**, with source characterization preserving single-attempt
default and independent unkeyed submissions. Add opt-in read-only transient
retries and bounded duplicate submission suppression above the existing Bridge;
these are new platform semantics, not claims of source parity. Preserve failure
propagation, first-failed-step termination and nonfinal caller timeout behavior.
Do not infer retry safety for write/execute/external effects from publication or
an idempotency key. Durable backend idempotency remains future work. Rollback is
removing optional retry/key fields; source repositories remain unchanged.
