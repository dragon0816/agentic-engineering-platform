# Handoff — Phase 6 evaluation, slice 3 (policy and forbidden outcomes)

Updated: 2026-09-22 (Asia/Taipei).
Branch: `phase-6/forbidden-outcomes`, based on `main` after PR #41 merged.

Progress across every phase is in `docs/TASKS.md`. This file is only where
the current work stopped and how to resume it, and is rewritten each time.

## Goal

The Roadmap's scenario names four prohibitions. Check each as evidence of
what happened rather than as an intention the case states about itself.
Requirements: `docs/phases/PHASE_6_EVALUATION.md` (slice 3); contracts:
`docs/CONTRACTS.md` ("Evaluation harness").

## Owner decisions in force

Listed with their dates in `docs/TASKS.md`. The one that shapes this phase:
**Codex and Claude Code are out of scope for Phase 6 entirely** (2026-09-22).

## Completed

- A prohibition is an assertion whose grader fails when the forbidden thing is
  found. No second mechanism beside `assertions`, so one registry keeps one
  rule for an unrecognized name, and a case still reads like the Roadmap
  because the graders are named for what must not happen.
- `ObservedRun.declared_steps` and `ObservedRun.unapproved`, both read from
  what the platform already produces: the workflow manifest declares its
  steps, and the Bridge policy holds the grants.
- Four graders: `mandatory_steps_completed`, `stayed_in_namespace`,
  `no_unapproved_irreversible_effect` and `no_credential_in_evidence`.
- `evaluation/cases/scenario-release.json`, the first `scenario` case, and
  the fixture behind it in `tests/evaluation_runner.py`: a two-step workflow
  whose second step declares `external_side_effect` and is granted with an
  approval reference.
- 23 test cases in `tests/test_evaluation.py`, including each prohibition
  rejecting an observation that violates exactly it, a reason naming what it
  found without echoing the credential it found, and the scenario being
  graded against a run that actually dispatched both steps.

## In Progress

- Opening the review PR for this branch; review and CI results are recorded on
  the PR once available.

## Remaining

Listed in `docs/TASKS.md`. Next is slice 4, model-involving evaluation across
configured aliases with repetition, reported as skipped when no alias is
configured rather than quietly passed.

## Architecture decisions made

- The scenario's irreversible step passes its prohibition because an approval
  exists, not because nothing ran. A prohibition proved by a run where nothing
  happened proves nothing, and a test asserts the scenario really does perform
  an `external_side_effect`.
- `no_unapproved_irreversible_effect` fails when `external_side_effect` was
  not observable at all, following the slice 2 rule that absence of evidence
  is not evidence of absence.
- The scenario forbids only `write` at the side-effect level. Forbidding
  `external_side_effect` there would have contradicted the case: the point is
  that an irreversible effect is permitted **under approval**, which is a
  different check from forbidding it outright.

## Exact verification commands and results

Windows, Python 3.12.14, repository root, with the `office` extra installed:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 639 passed, 3 skipped (link privileges)
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

- The scenario is an inert fixture exercising the platform's real governance,
  not a real release pipeline. Its workflow, capabilities and grants are
  defined in `tests/evaluation_runner.py`. What it proves is that the harness
  catches a scenario-level violation, not that any particular release process
  is correct.
- `stayed_in_namespace` compares a dispatch target's namespace against the
  request's. A capability legitimately shared across namespaces would need a
  case-level allowance that does not exist yet.
- `no_credential_in_evidence` scans the serialized observation. A credential
  that never reaches the observation, because a handler logged it elsewhere,
  is not caught here; the adapters' own redaction covers that path.
- No `agent` case exists yet. That category arrives with slice 4.

## Next Recommended Action

Open the PR for `phase-6/forbidden-outcomes`, run the review, apply confirmed
findings and merge on green CI. Then write the slice 4 requirements and add
model-involving evaluation.
