# Handoff — Phase 6 evaluation, slice 4 (model-involving evaluation)

Updated: 2026-09-22 (Asia/Taipei).
Branch: `phase-6/model-evaluation`, based on `main` after PR #42 merged.

Progress across every phase is in `docs/TASKS.md`. This file is only where
the current work stopped and how to resume it, and is rewritten each time.

## Goal

Run the same case across configured model aliases, repeated, and compare them
on correctness, reliability, latency and usage. Requirements:
`docs/phases/PHASE_6_EVALUATION.md` (slice 4); contracts:
`docs/CONTRACTS.md` ("Model-involving evaluation").

## Owner decisions in force

Listed with their dates in `docs/TASKS.md`. The one that shapes this phase:
**Codex and Claude Code are out of scope for Phase 6 entirely** (2026-09-22).

## Completed

- `model_selected_route`, the `agent` category's grader: the route was reached
  with origin `model` and a model really was asked. An observation claiming a
  model chose while never calling one fails, as does a deterministic route.
- `ObservedRun` carries `duration_ms`, `input_tokens` and `output_tokens` from
  the Phase 5 response, so an alias is rankable on cost and speed.
- `Attempt`, `AliasTrial` and `ModelEvaluation`, and
  `compare_aliases(case, aliases, run, repeat=)`. An empty alias list is
  skipped rather than passed, the contract refuses to call a comparison
  measured when it holds no trials, and `repeat` below two raises.
- `evaluation/cases/agent-ambiguous.json`, the first `agent` case: a request
  no deterministic rule resolves, routed by a model whose proposal the router
  validates against what is installed.
- `AgentRunner` in `tests/evaluation_runner.py` drives the **real** Phase 5
  `OpenAICompatible` adapter over a stub transport, so the wire format, the
  structured-output parse and the router's validation all run without a
  provider existing.
- 46 test cases in `tests/test_evaluation.py`, including two aliases compared
  on a case they disagree about, an alias that is right half the time showing
  a reliability of 0.5, the skipped result, and a single attempt refused.

- PR #43 review (9 findings) applied, all fixed. The alias under comparison
  never reached the model request, so two aliases would have been the same
  endpoint under two labels; it is passed explicitly and a test reads it back
  off the reply. A `run` that raised aborted the whole comparison, discarding
  every completed attempt; it is a failed attempt now. Durations were totalled
  over different numbers of measured calls, so an alias that refused twice
  read as faster; `mean_duration_ms` and `unmeasured` replace that, and a
  total exists only when everything was measured. The two-attempt minimum
  lived only in the function, not the contract. A skipped result carried
  `detail="measured"`. Duplicate aliases were not refused. The stub proposal
  was inferred onto every agent case rather than named per case. A model call
  that raised counted as zero calls. And `docs/TASKS.md` recorded this PR as
  merged before it was; a row now says `in review` until its PR merges.

## In Progress

- Nothing; the PR is open with the review applied.

## Remaining

Listed in `docs/TASKS.md`. Next is slice 5, trace capture with redaction,
after which Phase 6's exit criteria should be reviewed and the phase closed.

## Architecture decisions made

- Model evaluation is a separate class of test and is not the CI gate. The
  deterministic suite blocks regressions; a comparison reports, and reports
  `skipped` when no alias is configured.
- A single attempt is refused rather than reported. The source repository's
  benchmark states the rule outright, and a number nobody may trust is worse
  than no number.
- `compare_aliases` takes a `run` callable rather than building clients, so
  nothing in the evaluation layer decides how a model is reached. A host
  passes live clients; the tests pass adapters over an injected transport.
- The agent case's model answers through the real adapter rather than a fake
  `ModelClient`, so a change to the wire format or to structured-output
  parsing breaks this case too.

## Exact verification commands and results

Windows, Python 3.12.14, repository root, with the `office` extra installed:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 661 passed, 3 skipped (link privileges)
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

- No comparison has been run against a live model. The machinery is exercised
  with a stub transport, which proves the harness rather than any alias.
- `duration_ms` for an agent case is the model call's, not the whole request's.
  A comparison therefore ranks aliases on the part they are responsible for,
  which is the intent, but it is not end-to-end latency.
- The comparison is not wired into CI and produces no stored report. Where a
  result should live is a host concern and is deliberately unanswered.
- One `agent` case exists. Comparing aliases over a case set, rather than one
  case, is a loop a host writes today.

## Next Recommended Action

Open the PR for `phase-6/model-evaluation`, run the review, apply confirmed
findings and merge on green CI. Then write the slice 5 requirements, add trace
capture with redaction, and close Phase 6 against its exit criteria.
