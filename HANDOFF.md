# Handoff — Phase 3 bounded retries and duplicate submissions

Updated: 2026-09-21 (Asia/Taipei).
Branch: `phase-3/retry-idempotency`, based on `main` at `f6b7587`.
Implementation commit: `c4c8b35`.
PR: https://github.com/dragon0816/agentic-engineering-platform/pull/11 (open, unmerged).

## Goal

Complete Phase 3 slice 4: opt-in bounded read retries and in-memory idempotency
keys, without enabling repeated production side effects. Requirements and source
inspection are in `docs/phases/PHASE_3_WORKFLOW.md` and `docs/PHASE_3_MIGRATION.md`.

## Completed

- Merged PR #10 after verifying its exact head and four passing PR CI jobs:
  https://github.com/dragon0816/agentic-engineering-platform/pull/10
  Merge commit: `f6b75878f60e25e0f8d171668027b5cd65598a15`.
- Re-inspected pinned rs_workflow_system runner and step helper. Added source
  characterization proving failures are not retried and repeated unkeyed
  submissions create independent runs. Source repositories remain untouched.
- Added RetryPolicy (1–3 attempts, fixed 0–10000 ms delay) to explicit steps.
  Default/legacy execution still attempts once. Multi-attempt side-effecting
  plans are rejected before the workflow starts.
- Added sanitized TransientCapabilityError handling. Only read failures of this
  exact kind are retryable; unknown errors/timeouts/validation/policy/dependency
  failures do not retry. Every attempt goes through Bridge policy and validation.
- StepAttempt metadata records outcomes without payloads. Each step keeps one
  terminal result for chaining; successful prior steps are never repeated.
- Added optional workflow idempotency keys. Same actor/namespace/key and same
  execution intent join or return the original run, including after caller wait
  timeout, terminal failure/cancellation and history eviction. Original trace is
  preserved. Changed intent fails closed; current authorization gates replay.
- Keys are retained for the engine lifetime, up to 50; capacity rejects new keyed
  runs instead of evicting keys. Preflight rejections do not consume keys.
- Gateway forwards caller workflow keys. A keyed direct capability route is
  rejected without dispatch rather than silently ignoring the key.
- Added 50 characterization/contract/runtime/Gateway cases: 249 total tests.
  Existing deterministic routing/evaluation and chained Gateway proofs still pass.
  New tests use inert handlers even for write/execute/external-effect classifications.
- Updated README, shared contracts, Phase 3 scope and migration decisions.

## In Progress

- No implementation work remains in this slice. PR #11 is open for review;
  final PR merge checks are visible on GitHub.

## Remaining

- Review and merge the new retry/idempotency PR after verification. Only PR #10
  was authorized for merge in this session; this new slice remains reviewable.
- Next Phase 3 slices: resumable state, progress streaming, optional n8n adapter
  through the same execution contracts. No production jobs, transport, database,
  durable idempotency backend or side-effecting automatic retries are implemented.
- Earlier deferred reviews remain: bounded Bridge event history, SkillRegistry
  parse cost, MCP installation round trips, Review not_required semantics and
  generic top-level package names. Do not broaden this slice to address them all.

## Architecture decisions made

- ADAPT existing runner/Bridge behavior; opt-in retry and keyed submission are new
  platform semantics. Default single attempt and unkeyed independent runs preserve
  the characterized source behavior. No job code or n8n business logic is imported.
- Registry publication/manifest metadata never grant runtime authority. Retry
  eligibility comes from trusted installed capability classification and a typed
  handler failure; every attempt is independently authorized.
- Idempotency means bounded duplicate suppression within one engine on one event
  loop, NOT durable exactly-once effects. Keys are caller options, not model output.
  Fingerprints include exact workflow, arguments and all non-trace request context;
  object key ordering is ignored, changed context/data conflicts. Keys/hashes are
  never logged. Replays check permissions before and after joining an active run.
- Keep key records even when runs fail or are evicted: earlier steps or interrupted
  handlers may have caused effects. Do not automatically clear capacity/restart
  the engine, retry the whole workflow or infer write safety from a key.
- Existing caller-wait timeout, cancellation tracking, 50-run history and bounded
  logs remain. Attempt metadata has at most three records per declared step.

## Exact verification commands and results

Windows, Python 3.12.14, repository root:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 249 tests
.venv/Scripts/python.exe -m ruff check .
# PASS
.venv/Scripts/python.exe -m ruff format --check .
# PASS: 62 files already formatted, including ignored local scratch files
.venv/Scripts/python.exe -m mypy
# PASS: 41 source/test files
.venv/Scripts/python.exe -m pip check
# PASS
.venv/Scripts/python.exe -m build
# PASS: sdist and wheel
.scratch/wheel-env/Scripts/python.exe -m pip install --no-deps --force-reinstall dist/agentic_engineering_platform-0.1.0-py3-none-any.whl
# PASS
.scratch/wheel-env/Scripts/python.exe -I -c "import agent.gateway, workflow.engine; from common.assets import RetryPolicy; from common.execution import StepAttempt; from capabilities.runtime import TransientCapabilityError; policy = RetryPolicy(max_attempts=3); assert RetryPolicy.model_validate_json(policy.model_dump_json()) == policy; assert StepAttempt(step_index=0, attempt=1, status='succeeded').code is None; print(workflow.engine.__file__); print('retry contracts and packaged runtime passed')"
# PASS: imports from wheel-env/Lib/site-packages, contract round-trip passed
git diff --check
# PASS
```

Tests were written first: initial collection failed on the absent transient-error
contract; after adding contracts, 17 runtime tests failed and 11 passed before
engine implementation. Final full suite passes. Local tests require elevation
because of existing temporary directory ACLs; optional pytest cache is disabled.
CI runs ordinary pytest on fresh workers. No production service/model/job invoked.

Remote implementation verification:
`gh api repos/dragon0816/agentic-engineering-platform/actions/runs/35522943129/jobs --jq '.jobs[] | {name,status,conclusion}'`
confirmed successful Windows/Linux jobs on Python 3.11/3.12 for implementation
`c4c8b355f4b965772dea4075cd5a633a970fbb5e`.
Run: https://github.com/dragon0816/agentic-engineering-platform/actions/runs/35522943129
This handoff-only follow-up triggers fresh checks; PR #11 contains the final
merge-check status and links for the latest head.

## Known issues / limitations

- Keys disappear when the engine process/instance is replaced. No crash recovery,
  shared store, expiry, key release or distributed lock is provided. New/no keys
  intentionally permit new runs. Key-table capacity is fail-closed by design.
- Write/execute/external side effects cannot opt into automatic retries. Durable
  backend idempotency requires a separate explicit contract and implementation.
- Caller timeouts do not preempt blocking or offloaded work. Snapshot outputs
  require caller access controls if a future transport exposes them.
- User/Claude's untracked `.claude/` directory remains untouched/uncommitted.

## Next Recommended Action

Review the retry/idempotency PR. After merge, define a bounded resumable-state
contract and inspect source progress/step-state behavior before coding: distinguish
completed, never-started and uncertain-effect steps, and require explicit policy
for resuming without replaying an uncertain side effect. Start with inert tests;
do not add production persistence or backend guarantees without approved scope.
