# Handoff — Phase 6 evaluation, slice 1 (the grading harness)

Updated: 2026-09-22 (Asia/Taipei).
Branch: `phase-6/harness`, based on `main` after PR #38 merged.

## Goal

Phase 6 slice 1: make a case's declarations decide whether it passed.
Requirements: `docs/phases/PHASE_6_EVALUATION.md` (slice 1); decisions:
`docs/PHASE_6_MIGRATION.md`; contracts: `docs/CONTRACTS.md` ("Evaluation
harness").

## Owner decisions in force

1. **Codex and Claude Code are out of scope for Phase 6 entirely**
   (2026-09-22). They were already excluded from Phase 5 as model providers;
   they are now also not evaluated, not driven and not a capability the
   platform invokes. The phase specification records this.
2. Provider adapters are in-process code and the platform never starts a
   provider process (2026-09-21).
3. Remaining slices are completed without check-ins unless something cannot be
   decided (2026-09-22).

## The gap this slice closed

`EvaluationCase.assertions` had named what must hold since Phase 1, and
nothing read it. Five test modules loaded the six cases and re-implemented a
subset of their meaning by hand, so a case could declare `no_execution` while
the test that loaded it never looked for execution, and a misspelled assertion
was indistinguishable from a satisfied one.

## Completed

- `src/common/evaluation.py`: `ObservedRun` (evidence of what happened, never a
  claim that an assertion holds), the `Grader` protocol and nine graders, one
  per assertion the repository's cases declare; `grade` (expected route when
  the case names one, forbidden side effects always, each named assertion, and
  an unknown assertion **failing** its case); `load_cases` (stable order, a
  file holding one case or many, a duplicate id refused where cases are
  loaded); `report`.
- `EvaluationCase.expected_route` is now optional, because a discovery case is
  not a routed request. `evaluation/cases/discover-task.json` drops the route
  it could never have been graded against, keeping the four assertions that
  carry its meaning; `tests/test_registry.py` checks that instead.
- `tests/test_evaluation.py`: the six cases graded against the real platform
  (router, gateway and the registry proof), every declared assertion having a
  grader and every grader being exercised, each grader rejecting a
  deliberately wrong observation, an unrecognized assertion failing, the
  always-on route and side-effect checks, stable loading with a duplicate
  refused, and the report naming failures. 15 test cases.
- `CLAUDE.md`, `docs/ROADMAP.md` and `docs/ARCHITECTURE.md` now name Phase 6 as
  the active phase.

## In Progress

- Opening the review PR for this branch; review and CI results are recorded on
  the PR once available.

## Remaining

- Slice 2: policy and forbidden outcomes for scenario cases (the Roadmap's
  release example: never overwrite a released tag, skip mandatory tests,
  modify an unrelated repository or expose credentials), checked as evidence.
- Slice 3: model-involving evaluation across configured aliases with
  repetition, comparing quality, latency (`duration_ms` from Phase 5),
  reliability and usage. Reported as skipped when no alias is configured,
  never quietly passed.
- Slice 4: trace capture with redaction.
- Deferred from Phase 3: a payload sweep, process-liveness or lease-based
  suspension, and the earlier deferred reviews.
- Deferred from Phase 4: a retrieval cache, host wiring that plans from an
  adopted document, a size-and-mtime shortcut for adopted-file drift checks,
  and image description for legacy `raw/`.
- Deferred from Phase 5: tool calling in either adapter, reading `tool_calls`
  back off a response, retry behaviour, a pooled or async transport, and a
  production credential backend. The Ollama adapter and the company gateway
  have still never been exercised against a live endpoint.

## Architecture decisions made

- An unrecognized assertion fails its case. The source repository's benchmark
  shipped a selftest because a grader that accepts anything is
  indistinguishable from a working one; the same exposure here is sharper,
  since the assertions are free symbols.
- A grader reads evidence, never a claim. `ObservedRun` therefore carries
  counts, effects and identities rather than booleans named after assertions.
- Not every evaluation case is a routed request, so `expected_route` is
  optional. The alternative was to keep it mandatory and satisfy it for the
  discovery case by copying the case's own `reason` into the observation,
  which would have made the check vacuous.

## Exact verification commands and results

Windows, Python 3.12.14, repository root, with the `office` extra installed:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 627 passed, 3 skipped (link privileges)
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

- All six cases are category `deterministic`. No `agent` or `scenario` case
  exists yet, so those categories are declared in the contract and unexercised.
- `tests/test_evaluation.py` chooses how to exercise a case by its id prefix
  and namespace. That is host wiring living in a test; when a scenario case
  arrives it will need a better home than a chain of conditionals.
- `bridge_advertisement` is weaker for a case with no expected route: it
  requires that something was discovered and that a Bridge advertised
  something, not that the two correspond. Strengthening it needs the
  discovered task's capability identity in `ObservedRun`.
- The five existing test modules still load cases themselves. They are unit
  tests of each component and the suite is the cross-cutting gate, so the
  overlap is deliberate, but a future slice could let them share one runner.

## Next Recommended Action

Open the PR for `phase-6/harness`, run the review, apply confirmed findings
and merge on green CI. Then write the slice 2 requirements section and add the
first `scenario` case with its forbidden outcomes.
