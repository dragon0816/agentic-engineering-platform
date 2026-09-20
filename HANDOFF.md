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
- 14 resume tests covering contracts, every classification and policy branch,
  re-authorization after a later grant, result chaining without re-running,
  repeated resumption, cancellation, eviction and key independence.
- Docs: phase spec slice 5, migration slice-5 decision, `docs/CONTRACTS.md`
  "Phase 3 bounded resumption", README, fixtures README.

## In Progress

- Opening the review PR for this branch; review and CI results are recorded on
  the PR once available.

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
- Classification uses recorded evidence only: a step is `uncertain` unless a
  terminal success was recorded or a pre-handler rejection code proves no handler
  ran. Uncertainty is never resolved by guessing; only an explicit host policy
  may replay it, and read-only replay is gated by the installed capability's
  side-effect classification, not by manifests or publication metadata.
- Resumption grants nothing and creates a new run; the original run is immutable
  history. It shares the 50-run history, bounded logs and caller-wait timeout
  semantics, and ignores idempotency keys by design (a keyed re-submission still
  returns the original run).
- No persistence: keys, history and resumability all end with the engine
  instance. Durable state needs its own approved contract before any backend.

## Exact verification commands and results

Windows, Python 3.12.14, repository root:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 267 tests (249 prior + 4 step-table characterization + 14 resume)
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

Open the PR for `phase-3/resumable-state` against `main`, run the review, apply
confirmed findings and let the owner merge. Then decide the next slice with the
owner: either a Gateway resume trigger (small, same contracts) or the durable
step-state contract, which must be scoped explicitly before any persistence code.
