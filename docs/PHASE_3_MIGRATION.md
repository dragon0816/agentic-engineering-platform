# Phase 3 source inspection and disposition

## Slice 9 source-first decision

Re-inspected pinned `tests/fixtures/source_jobrunner.txt` and `source_steps.txt`
from the revision below. JobRegistry retains only in-memory runs; StepTable marks
pending/running/success/failure and prohibits re-entry; on_change/reporting is
best-effort. These boundaries contain no durable checkpoint, restart loader,
idempotency transaction or atomic continuation implementation to wrap.

Decision: **ADAPT** existing platform evidence/identity/ResumePolicy semantics in
an additive checkpoint contract and isolated memory reference model. Keep source
characterization tests, existing engine and source repositories unchanged. Durable
write acknowledgment is a new correctness gate, deliberately separate from source
best-effort reporting. No source deprecation or disk durability parity is claimed.
Rollback removes the new checkpoint modules/tests/docs; no runtime imports them.

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

## Slice 5 source-first decision

Inspected `host-bridge/jobs/_steps.py` at the same pinned revision and pinned it
as `tests/fixtures/source_steps.txt` (the module without its docstring; checksums
in the fixtures README). Characterized: steps are linear and a finished, failed or
skipped step can never be entered again; after a failing step the remaining
declared steps stay `pending` and `never_run()` lists them; skipping requires a
reason; the failed row records exception text; and the source offers **no resume**
— a failed run is terminal, and the runner's only step-state use is logging
"declared but never run" after success.

Decision: **ADAPT** the pending/never-run distinction into a typed effect
classification and add resumption as new platform semantics, not source parity:

- `never_started` corresponds to the source's `pending` rows, extended to steps
  the Bridge rejected before invoking any handler. The Bridge records
  `handler_invoked` on each result and attempt at dispatch time, so the
  classification is evidence, not a maintained list of failure codes.
  `completed` is a terminal success. Everything else — any attempt whose handler
  ran without terminal success, or an interruption at that step — is
  `uncertain`, because the engine cannot know what effect it had.
- The source's "no re-entry" rule is preserved for completed steps: resumption
  never repeats them and reuses their recorded results, and a run itself can be
  continued only once (its continuation is what gets resumed next). Re-entry of
  an uncertain step is the one deliberate extension, gated by an explicit host
  `ResumePolicy` and re-authorization of every remaining step; publication and
  manifests cannot grant it.
- Exception text is never recorded (unchanged platform rule); classifications carry
  failure codes only.
- Resumption is bounded to the in-memory run history; there is no durable step
  state, crash recovery or persistence, matching the source, which has none.

Rollback: remove `inspect`/`resume`, the resume contracts and the step-table
fixture; runs remain terminal as before. Source repositories remain unchanged.

## Slice 7 source-first decision

Re-inspected the pinned `jobs/_steps.py` excerpt (`tests/fixtures/source_steps.txt`)
and the runner: `StepTable.on_change` is called after every transition, outside
the lock, and the runner posts the whole run snapshot to the ops dashboard on each
change; `_changed` swallows hook exceptions and `_report` never raises, so
reporting can never fail a step or change a run's outcome. Characterized by
`test_source_reports_every_transition_and_never_fails_a_step_over_reporting`.

Decision: **ADAPT** the "report every transition, never fail the run" semantics
into bounded in-process progress streams; the ops transport is not migrated:

- Typed `RunProgress` events replace whole-run snapshot dicts; they carry
  identities, statuses, step indices and codes only, consistent with the log and
  trace rules, and a live run reports `running`.
- Best-effort delivery is made explicit instead of implicit: each watcher has a
  bounded queue, a full queue drops the event and marks `lagged` on the next one
  delivered, and the terminal event always arrives. The source's dashboard client
  also "queues and drops rather than waiting"; the adaptation tells the consumer.
- Watchers are owner-scoped like `inspect`/`resume` and bounded per run;
  capacity is reported as a `rejected/watch_capacity` event, never a silent drop.
- No persistence, replay, transport or dashboard; streams end with the run.

Rollback: remove `watch`, `_Watcher`, `RunProgress` and the emit calls; runs behave
exactly as before. Source repositories remain unchanged.
## Slice 8 source-first decision

Inspected `workflows/13_release_package.json` at the pinned
`rs_workflow_system@896046e8fe2170d21f9213e56e5ce2f93c05ba43` revision. The graph
is manual trigger -> parameters -> one Bridge HTTP POST -> IF -> success/failure
summary. The body selects `release_package`, passes `params`, caller workflow /
execution metadata and wait options; the IF requires both `ok === true` and
`data.status === 'success'`. No HTTP-node automatic retry is enabled. Pinned
projection and checksum: `tests/fixtures/source_n8n_release.json` and its README.

Decision: **ADAPT** this dispatch/status boundary, preferring the newer Host Bridge
lineage over historical `n8n_work_flow` prototypes. Preserve parameter pass-through,
one underlying workflow execution path, no business logic in the adapter and success
branching only on terminal success. Do not migrate the production release job, HTTP
headers/URLs, worker selection, notifications or a live n8n graph.

Intentional changes: exact workflow binding replaces payload-selected job; trusted
RequestContext replaces untrusted identity metadata; stable operation ids map to
existing engine idempotency. Gateway returns shared WorkflowRunSnapshot directly:
consumers branch on `run.status == 'succeeded'`, not source `ok/data.status`. A caller
timeout is not terminal evidence; use inspect/watch rather than creating new work.
The adapter is an offline host seam, not a server or installed n8n node. Rollback:
remove optional `integrations.n8n` and its fixtures; ordinary Gateway paths remain.

## Slice 10 source-first decision

The pinned source Bridge keeps runs in memory only; durable run history lives in
the separate ops dashboard reached by best-effort mirroring (`_report`), which is
neither a checkpoint store nor a restart contract, and no source module wraps a
local transactional store. There is nothing to ADAPT for durability itself.

Decision: **new platform semantics**, bounded by the owner-approved scope — a
single-writer local SQLite file using the standard library, one transaction per
write acknowledged only after commit, and the slice-9 rules shared as code
between backends. The source's best-effort mirroring remains the model for
progress reporting, not for checkpoints. No source deprecation is claimed;
rollback removes `workflow/checkpoints_sqlite.py` and its tests.
