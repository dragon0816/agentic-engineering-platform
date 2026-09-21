# Phase 6 — Evaluation, policy and observability

Implementation scope derived from the approved Roadmap (Phase 6) and
Architecture ("Evaluation / harness"). The three categories to reach:

```text
1. deterministic regression tests   (a known request must route and execute exactly so)
2. agent routing/planning evaluation (a model is involved; repetition is required)
3. end-to-end scenario evaluation    (a whole task, with forbidden outcomes named)
```

Exit criterion from the Roadmap: the evaluation suite runs in CI without
production side effects and blocks known regressions.

## What already exists, and the gap

`common.evaluation.EvaluationCase` has been in the repository since Phase 1,
and six cases live under `evaluation/cases/`, all of category `deterministic`.
Five test modules load them and re-implement a subset of their meaning by
hand.

Nothing interprets `EvaluationCase.assertions`. A case may declare
`no_execution` while the test that loads it never checks for execution, and a
misspelled assertion is indistinguishable from a satisfied one. That is the
gap Phase 6 closes first: the declarations in a case must be what decides
whether it passed.

## Invariants

1. **A declaration is checked or the case fails.** An assertion with no grader
   registered fails its case. A harness that silently ignores what it does not
   understand reports a perfect score and is believed.
2. **Graders are proven to reject.** Every grader has a case in the suite where
   a deliberately wrong observation must fail it. This is the one idea worth
   keeping from the source's benchmark, whose `selftest.py` exists because a
   grader that passes anything measures nothing.
3. **Evidence, not claims.** A grader reads primitive evidence of what
   happened, never a flag asserting that the thing it is checking happened.
4. **The suite runs in CI with no production side effects.** No model, no
   network, no host process. A category that needs a live model is reported as
   skipped rather than quietly passing.
5. **Deterministic and probabilistic evaluation are separate classes.** A
   deterministic case that fails is a platform regression. A model-involving
   case that fails once is not a verdict; the source's benchmark states the
   rule plainly, that a single run is not a measurement.

## Requirements and acceptance (slice 1 — the grading harness)

1. `common.evaluation.ObservedRun` records what actually happened when a case
   was exercised: the route taken and whether it was reached deterministically,
   how many model calls were made, the side effects observed, the run status
   and completed steps, the assets discovered with their lifecycle states, and
   what a bridge advertised. Every field is evidence a grader can check, not a
   claim that an assertion holds.
2. A `Grader` takes a case and an `ObservedRun` and returns `None` when it is
   satisfied or a reason when it is not, so a failure always says why.
   `GRADERS` registers one per assertion name used by the cases in the
   repository: `no_model_call`, `no_execution`, `exact_scoped_target`,
   `deterministic_trigger`, `fail_closed`, `workflow_succeeds`,
   `scoped_identity`, `published_discovery` and `bridge_advertisement`.
3. `grade(case, observed, graders=)` returns a `CaseResult`: the route must
   match the case's `expected_route`, no forbidden side effect may appear,
   every named assertion must be satisfied, and an assertion with no grader is
   reported in `unknown_assertions` and fails the case.
4. `load_cases(directory)` reads every `.json` file, accepting a single case or
   a list, in a stable order, refusing a duplicate `case_id` where the cases
   are loaded rather than at the first confusing result. `report(results)`
   summarizes, naming every failure and its reason.
5. Tests: the whole case directory loaded and graded against the real platform,
   so a routing or workflow regression fails CI; each grader rejecting a
   deliberately wrong observation; an unknown assertion failing its case; a
   duplicate case id refused; and the report naming failures.

## Later slices (each needs its own requirements section before work starts)

- Slice 2 — policy and forbidden outcomes: a scenario case's `Forbidden` list
  (overwrite a released tag, skip mandatory tests, modify an unrelated
  repository, expose credentials) checked as evidence rather than intent.
- Slice 3 — model-involving evaluation: the same case set across configured
  aliases, with repetition, comparing quality, latency (`duration_ms` from
  Phase 5), reliability and usage. Reported as skipped when no alias is
  configured, never quietly passed.
- Slice 4 — trace capture with redaction: route, plan, tool and workflow calls,
  approvals, duration, model usage and final status.

## Out of scope for Phase 6

Codex and Claude Code, in every form. The owner excluded them from Phase 5 as
model providers on 2026-09-21 and from Phase 6 entirely on 2026-09-22: they are
not evaluated, not driven, and not a capability the platform invokes.

Also out of scope: the source's coding benchmark itself (see
`docs/PHASE_6_MIGRATION.md`), any sandbox for executing generated code, a
results database or dashboard, and cost accounting against a price table.
