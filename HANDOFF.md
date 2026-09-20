# Handoff — Phase 3 workflow step inputs

Updated: 2026-09-21 (Asia/Taipei).
Branch: `phase-3/step-inputs`, based on `main` at `25a3105` (Gateway PR #9 already merged).
Implementation commit: `dec744b`.
PR: https://github.com/dragon0816/agentic-engineering-platform/pull/10 (open, not merged).

## Goal

Complete Phase 3 slice 3: explicit per-step inputs and prior-result chaining,
following `docs/phases/PHASE_3_WORKFLOW.md`. Preserve the existing Gateway,
Bridge policy, source-characterized runner semantics and legacy manifests.

## Completed

- Reconciled Claude's handoff with actual GitHub state: Phase 1/2, filesystem
  adapter, workflow engine and Gateway PRs are already merged. Baseline: 164 tests.
- Added `WorkflowStep`, `RunInput` and `StepInput` contracts. Identity-only steps
  still receive all run arguments; explicit steps receive only their mapped fields.
- Exact object-key / zero-based array-index selectors support run arguments or
  earlier successful step result data. Empty paths select the whole source.
  Invalid/self/future references are rejected before installation.
- Missing run references return needs-input before a stored run exists. Missing
  result references stop the run before the unresolved capability is dispatched.
  Null remains a present value; Bridge validates the selected value's type.
- Each step still enforces Bridge authorization, dependencies and input/output
  validation. Chaining does not grant execution authority or resolve secrets.
- Isolated manifest, argument and snapshot ownership so callers or handlers
  cannot mutate inputs used by subsequent steps, including after a wait timeout.
- Added 35 contract/runtime/integration cases (199 total tests). Gateway tests
  exercise different contracts, deterministic dot/keyword triggers, model-selected
  routing and denial of the second step. Existing evaluation cases are executed
  against the composed chain with inert handlers and zero production side effects.
- Updated contracts, Phase 3 requirements/plan, source-first decision and README.

## In Progress

- None in this implementation slice. PR #10 is ready for review; it has not been merged.

## Remaining

- Review/merge this slice after remote verification.
- Next Phase 3 slices: retry/idempotency, resumability, progress streaming and the
  optional n8n adapter invoking the same Gateway/engine contracts.
- No Host Bridge HTTP server, terminal/Excel/email/browser adapter, production job,
  scheduler, database or persistence was added. Production source paths stay active.
- Prior deferred reviews remain: bounded Bridge execution event history, repeated
  SkillRegistry parsing, MCP installation round trips, Review `not_required`
  semantics and generic top-level package names. Do not broaden this PR for them.

## Architecture decisions made

- ADAPT the installed workflow engine, preserving the pinned runner behavior.
  `_job_callable` in `tests/fixtures/source_jobrunner.txt` calls job code with
  params; that boundary has no declarative input mapping to wrap. This slice adds
  typed selection only, not migration or reimplementation of production job logic.
- Structured steps coexist with identity-only steps; no implicit field merging,
  expression evaluation, templates, static literal values or secret resolution.
  Configuration values are supplied as run arguments. References stay within the
  same run and target validated result data, never status/authorization metadata.
- Input failures use `needs_input/workflow_input_missing`, with no payload or path
  in errors/logs. This is terminal for a run, not an automatic retry/resume signal.
- Registry publication, routing, business review and runtime authorization remain
  separate. The engine dispatches every step through the same Bridge policy path.
- Caller-wait timeout does not cancel execution; final outcomes overwrite it.
  History/log bounds and cancellation handling from earlier slices are preserved.

## Exact verification commands and results

Run from repository root, Windows/Python 3.12.14:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 199 tests
.venv/Scripts/python.exe -m ruff check .
# PASS
.venv/Scripts/python.exe -m ruff format --check .
# PASS: 60 files already formatted (includes local ignored scratch files)
.venv/Scripts/python.exe -m mypy
# PASS: 39 source/test files
.venv/Scripts/python.exe -m pip check
# PASS: no broken requirements
.venv/Scripts/python.exe -m build
# PASS: sdist and wheel
.scratch/wheel-env/Scripts/python.exe -m pip install --no-deps --force-reinstall dist/agentic_engineering_platform-0.1.0-py3-none-any.whl
# PASS: installed into the existing isolated wheel environment
.scratch/wheel-env/Scripts/python.exe -I -c "import common.assets, workflow.engine, agent.gateway; from common.assets import WorkflowStep; s = WorkflowStep.model_validate({'capability': {'namespace': 'sample', 'name': 'count', 'version': '1.0.0'}, 'inputs': {'count': {'source': 'run', 'path': ['count']}}}); assert WorkflowStep.model_validate_json(s.model_dump_json()) == s; print(common.assets.__file__); print('wheel imports and structured step round-trip passed')"
# PASS: imports came from wheel-env/Lib/site-packages, round trip passed
git diff --check
# PASS
```

Tests were written before implementation: after correcting the test fixture,
10 expected failures and 13 passes confirmed structured steps were unsupported.
The baseline normal pytest invocation passed 164 tests but reported a cache-write
warning. The existing temp/cache directory ACLs require elevated test execution
locally; final verification disables only the optional pytest cache provider.
CI continues to run ordinary pytest on fresh Windows/Linux workers.

Remote implementation verification:
`gh api repos/dragon0816/agentic-engineering-platform/actions/runs/35521571558/jobs --jq '.jobs[] | {name,status,conclusion}'`
confirmed all four jobs completed successfully: Windows/Linux, Python 3.11/3.12.
Run: https://github.com/dragon0816/agentic-engineering-platform/actions/runs/35521571558
(implementation `dec744b9c9aa9c721159e90d1d9600a40450baa0`). This handoff-only
follow-up triggers a fresh PR check; inspect PR #10 for the latest merge checks.

## Known issues / limitations

- Run records and logs are in memory only. Cooperative asyncio timeouts are not
  process isolation; production handlers must offload blocking I/O.
- References cannot perform transforms, fallbacks, retries or cross-run lookup.
  Manifest input/output contract labels remain descriptive; installed capability
  model classes enforce the actual per-step types.
- Snapshots include validated outputs; they require appropriate caller access
  controls if a future transport exposes them. Logs deliberately omit payloads.
- User/Claude's untracked `.claude/` directory was preserved and is not committed.

## Next Recommended Action

Review the step-inputs PR and merge after CI passes. Then plan a bounded
retry/idempotency contract before implementation: characterize the relevant source
behavior, define which read versus side-effecting capabilities may be retried and
how duplicate side effects are prevented. Do not enable generic automatic retries.
