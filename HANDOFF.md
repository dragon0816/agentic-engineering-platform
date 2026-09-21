# Handoff — Phase 6 evaluation, slice 2 (observable execution)

Updated: 2026-09-22 (Asia/Taipei).
Branch: `phase-6/observable-execution`, based on `main` after PR #40 merged.

Progress across every phase is in `docs/TASKS.md`. This file is only where
the current work stopped and how to resume it, and is rewritten each time.

## Goal

Close the one grader slice 1 left unable to fail, before adding any new
category of case. Requirements: `docs/phases/PHASE_6_EVALUATION.md` (slice 2);
contracts: `docs/CONTRACTS.md` ("Evaluation harness").

## Owner decisions in force

Listed with their dates in `docs/TASKS.md`. The one that shapes this phase:
**Codex and Claude Code are out of scope for Phase 6 entirely** (2026-09-22),
so they are not evaluated, not driven and not a capability the platform
invokes.

## The gap this slice closed

Slice 1's review found that `no_execution` passed for four of the six cases
without being able to fail: their observations came from a bare `RequestRouter`
or the registry proof, neither of which can execute anything, so an empty
effect list was not evidence, it was the absence of a witness.

## Completed

- `ObservedRun.observable` names the effects a run could detect, and
  `ObservedRun.dispatched` names every capability the Bridge was asked to run.
  `no_execution` now fails when `execute` was not observable, and the
  always-on forbidden check fails for any forbidden effect the run could not
  have seen. Absence of evidence stopped counting as evidence of absence.
- `CaseRunner` and `run_cases(cases, runner)` move the wiring out of the
  contract: the harness grades what a runner returns and does not decide how a
  case is exercised.
- `tests/evaluation_runner.py` is the repository's runner. One `Gateway` holds
  all three shipped skill manifests, the release workflow, and a Bridge whose
  `events` supply both `dispatched` and the declared side effect of anything
  that ran. Every routed case goes through it.
- 18 test cases in `tests/test_evaluation.py`, including: every case still
  passing through the shared runner; every routed case dispatching something
  except the one that refuses; `legacy/run-testing` dispatched and recorded
  although the repository deliberately installs no implementation for it; and
  a check that could not have seen its evidence failing rather than passing.

## In Progress

- Opening the review PR for this branch; review and CI results are recorded on
  the PR once available.

## Remaining

Listed in `docs/TASKS.md`. Next is slice 3, the first `scenario` case with its
forbidden outcomes checked as evidence.

## Architecture decisions made

- The Bridge already records every dispatch in `events`, so no recording
  wrapper was added. The evidence the harness needs was already produced by
  the platform.
- Effects are read from the installed capability's declared `side_effect` for
  anything that ran, not from what a handler did. A route to a capability
  declared `execute` is caught by the declaration, which is what a case
  forbids.
- The filesystem capability is installed but never granted. A case about
  routing must not touch this machine's disk in order to prove that routing
  executed nothing.
- The registry proof claims full observability only after checking that
  neither the registry nor the advertisement exposes a way to execute, so the
  claim is verified rather than asserted.

## Exact verification commands and results

Windows, Python 3.12.14, repository root, with the `office` extra installed:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 630 passed, 3 skipped (link privileges)
.venv/Scripts/python.exe -m ruff check .
# PASS
.venv/Scripts/python.exe -m ruff format --check .
# PASS
.venv/Scripts/python.exe -m mypy
# PASS
.venv/Scripts/python.exe -m pip check
# PASS
.venv/Scripts/python.exe -m build
# PASS: sdist and wheel
git diff --check
# PASS
```

No model, gateway, network, real vault, job or n8n instance was invoked.

## Known issues / limitations

- `observable` is declared by the runner, not derived. A runner that wires no
  Bridge and still claims to watch everything would be believed. The claim is
  checked for the registry proof, which verifies there is no execution
  surface; for the Gateway runner it rests on the Bridge recording every
  dispatch, which the tests exercise.
- All six cases remain category `deterministic`. No `agent` or `scenario` case
  exists yet.
- Two test modules still load individual case files for their own unit
  assertions. That overlap is deliberate: they test one component, the suite
  is the cross-cutting gate.

## Next Recommended Action

Open the PR for `phase-6/observable-execution`, run the review, apply
confirmed findings and merge on green CI. Then write the slice 3 requirements
and add the first `scenario` case.
