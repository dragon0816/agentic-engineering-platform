# Handoff — Phase 3 bounded resumable state

Updated: 2026-09-21 (Asia/Taipei).
Branch: `phase-3/resumable-state`, based on `main` at `be8c968`.
PR #10 (step inputs) and PR #11 (retries/idempotency) are both merged into `main`;
the previous handoff's "PR #11 open" statement was reconciled against GitHub at
takeover.

## Goal

Complete Phase 3 slice 5: inspect a finished run's step states and resume it from
its first non-completed step, replaying an uncertain-effect step only under an
explicit policy, without persistence or backend guarantees. Requirements are in
`docs/phases/PHASE_3_WORKFLOW.md` (slice 5); source decisions in
`docs/PHASE_3_MIGRATION.md` (slice 5 section).

## Completed

- Takeover reconciliation: local `main` verified at `be8c968` (249 tests, ruff,
  mypy) before starting.
- Pinned `host-bridge/jobs/_steps.py` from the same `rs_workflow_system` commit as
  `tests/fixtures/source_steps.txt` (checksums in the fixtures README) and added
  4 characterization tests: linear steps with no re-entry, pending-after-failure /
  `never_run()`, skip-needs-reason, and no resume transition in the source.
- Contracts (`common/execution.py`, additive): `WorkflowRun.resumed_from`,
  `StepState`/`StepStateRecord`, `ResumePolicy` (`uncertain`: `reject` default,
  `replay_read_only`, `replay_side_effects`) and `ResumePlan` with a
  linear-progress validator.
- Engine (`workflow/engine.py`): records keep manifest/arguments/actor/namespace;
  `_preflight` factored out of `execute` unchanged; `inspect(run_id)` classifies
  steps from recorded evidence (Bridge codes raised before a handler ran are
  `never_started`; anything after a handler ran or an interruption is
  `uncertain`); `resume(context, run_id, policy)` starts a new run from the first
  non-completed step, copies completed results for input chaining, re-authorizes
  remaining steps before creating a run and again at dispatch, requires matching
  actor/namespace, rejects running/complete runs, returns None for unknown or
  evicted runs, and never touches idempotency keys. `_drive` gained a start index.
- 18 resume tests covering contracts, every classification and policy branch,
  re-authorization after a later grant, result chaining without re-running,
  repeated resumption, cancellation, eviction, key independence, once-only
  continuation, prior-result pre-flight, live-run inspection and handler
  evidence surviving a later pre-handler denial.
- Docs: phase spec slice 5, migration slice-5 decision, `docs/CONTRACTS.md`
  "Phase 3 bounded resumption", README, fixtures README.
- PR #12 opened; pre-merge review applied (commit after `c2bed5b`):
  classification is now evidence-based — the Bridge records `handler_invoked`
  on every `CapabilityResult`/`StepAttempt` instead of the engine keeping a
  failure-code table; a run can be continued once (`needs_input/already_resumed`
  afterwards) so a retried host call cannot re-execute never-started side
  effects; `inspect` takes the requesting context and, like `resume`, returns
  None for other actors' runs (indistinguishable from unknown); a live run is
  reported as `running` rather than the caller-wait overlay; `StepInput`
  references into completed results are pre-flighted so no doomed run record is
  created; the retained manifest drives both plan and continuation; launch logic
  is shared by `execute` and `resume`.

## In Progress

- PR #12 is open with the review posted; CI results for the final head are
  recorded on the PR.

## Remaining

- Review and merge the resumable-state PR. Merges follow a posted review per
  repository convention.
- Later Phase 3 slices: durable step-state/persistence contracts (a separate,
  explicitly scoped decision), progress streaming, a Gateway resume trigger, and
  the optional n8n adapter through the same execution contracts.
- Earlier deferred reviews remain: bounded Bridge event history, SkillRegistry
  parse cost, MCP installation round trips, Review `not_required` semantics,
  generic top-level package names, repeated RequestContext validation.

## Architecture decisions made

- ADAPT the source's pending/never-run distinction into an effect classification;
  resumption itself is new platform semantics (the source has none), never a
  source-parity claim.
- Classification uses recorded evidence only: the Bridge marks `handler_invoked`
  at dispatch time, and a step is `uncertain` unless a terminal success was
  recorded or no attempt ever invoked a handler. Uncertainty is never resolved by
  guessing; only an explicit host policy may replay it, and read-only replay is
  gated by the installed capability's side-effect classification, not by
  manifests or publication metadata.
- Resumption grants nothing and creates a new run; the original run is immutable
  history and can be continued exactly once (linear, like the source's step
  table). It shares the 50-run history, bounded logs and caller-wait timeout
  semantics, ignores idempotency keys by design (a keyed re-submission still
  returns the original run), and never reveals other actors' runs.
- No persistence: keys, history and resumability all end with the engine
  instance. Durable state needs its own approved contract before any backend.

## Exact verification commands and results

Windows, Python 3.12.14, repository root:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 271 tests (249 prior + 4 step-table characterization + 18 resume)
.venv/Scripts/python.exe -m ruff check .
# PASS
.venv/Scripts/python.exe -m ruff format --check .
# PASS: 64 files
.venv/Scripts/python.exe -m mypy
# PASS: 43 source/test files
.venv/Scripts/python.exe -m pip check
# PASS
.venv/Scripts/python.exe -m build
# PASS: sdist and wheel; source_steps.txt ships in the sdist
git diff --check
# PASS
```

Characterization tests ran green against the pinned excerpt before the engine was
changed; one resume test fixture was corrected during development (a read handler
that was wrongly configured to fail). No production service, transport, model, job
or n8n instance was invoked; inert doubles only.

## Known issues / limitations

- In-memory only: evicted or engine-replaced runs cannot be inspected or resumed.
- `uncertain` is deliberately conservative; a read-only handler interrupted before
  doing anything is still `uncertain` and needs `replay_read_only`.
- The Gateway has no resume trigger yet; resumption is an engine API for hosts.
- Local pytest needs `-p no:cacheprovider` because of temporary-directory ACLs on
  this machine; CI runs ordinary pytest.

## Next Recommended Action

The owner reviews and merges PR #12 (`phase-3/resumable-state`). Then decide the
next slice with the owner: either a Gateway resume trigger (small, same
contracts) or the durable step-state contract, which must be scoped explicitly
before any persistence code.
