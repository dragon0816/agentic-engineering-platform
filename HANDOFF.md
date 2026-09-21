# Handoff — Phase 3 Gateway run control over the journal (slice 13)

Updated: 2026-09-21 (Asia/Taipei).
Branch: `phase-3/gateway-journal`, based on `main` at `6c51679` (PR #19 merged).

## Goal

Phase 3 slice 13, chosen by the owner: let the Gateway's existing run-control
entry points reach durable evidence, so a host uses one API whether or not a run
outlived the process that started it. Requirements:
`docs/phases/PHASE_3_WORKFLOW.md` (slice 13); contracts:
`docs/CONTRACTS.md`; plan: `docs/WORKFLOW_CHECKPOINTS.md` ("Engine recovery").

## Completed

- `RunControlResult` gained `source` (`memory` / `journal` / `unknown`), a
  `suspend` action and `suspended_by`, with validators pinning what each action
  may report and keeping `unknown` empty.
- `Gateway.inspect` asks this process's history first and falls back to the
  journal, so a run that predates a restart is still reachable; `source` says
  which answered.
- `Gateway.suspend(request, run_id, confirmation)` records a person's
  `SuspensionConfirmation` against the durable record. A run this caller cannot
  see is `unknown` like everywhere else; a live or already suspended run raises
  the engine's own closed code rather than a vocabulary invented at this layer.
- `Gateway.resume` continues a journalled run through `recover` and any other
  run through the in-memory path, so the durable "continued once" guard always
  applies and a journalled continuation is itself journalled.
- The engine now records *why* a step is uncertain: the Bridge failure code is
  written onto the still-`started` evidence (`RunJournal.step_failed`). This is
  the one journal write whose failure changes nothing — the step already ran and
  `started` is already the conservative truth — so a refusing store only costs
  the explanation, never the outcome.
- 10 tests (`tests/test_gateway_journal.py`) over a real restart: the result
  contract, memory-then-journal fallback, an unjournalled engine, unknown and
  foreign runs, suspend-then-resume across processes, continue-once, resuming
  without a confirmation, a live run, and denied authorization after a restart.
- Docs: phase spec slice 13, `docs/CONTRACTS.md`, checkpoint plan, README.

## In Progress

- Opening the review PR for this branch; review and CI results are recorded on
  the PR once available.

## Remaining

- Review and merge this PR.
- **Checkpoint retention is the one known operational gap.** The store has no
  TTL, eviction or deletion by design, and since slice 12 its capacity bounds
  the production start path: at capacity, new journalled runs fail
  `checkpoint_capacity` permanently and across restarts. A retention policy —
  what may be pruned, and how without making a used idempotency key executable
  again — needs its own scope before any long-lived deployment.
- Optional later work: process-liveness or lease-based suspension if
  single-Bridge manual recovery stops being enough.
- Earlier deferred reviews remain: bounded Bridge event history, SkillRegistry
  parse cost, MCP installation round trips, Review `not_required` semantics,
  generic top-level package names, repeated RequestContext validation.

## Architecture decisions made

- One API, two sources of evidence. The Gateway chooses between memory and the
  journal and says which answered; callers do not branch on deployment shape.
- The Gateway still invents no vocabulary: ownership, policy, pre-flight and the
  closed store codes all stay in the engine and the store. `missing` becomes
  `unknown` only to preserve the indistinguishability rule that already applies
  to inspect and resume.
- Recording a step's failure code is explanation, not evidence: the
  classification is already correct without it, so its write is allowed to fail.

## Exact verification commands and results

Windows, Python 3.12.14, repository root:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 450 tests (440 prior + 10 Gateway journal)
.venv/Scripts/python.exe -m ruff check .
# PASS
.venv/Scripts/python.exe -m ruff format --check .
# PASS
.venv/Scripts/python.exe -m mypy
# PASS: 59 source/test files
.venv/Scripts/python.exe -m pip check
# PASS
.venv/Scripts/python.exe -m build
# PASS: sdist and wheel
git diff --check
# PASS
```

The 440 existing tests passed unchanged before any new test was written. One
test then showed that the durable plan classified a failed step correctly but
could not explain it, which is why `step_failed` exists. Checkpoint files and
payloads live under pytest's temporary directory. No production service,
database server, transport, model, job or n8n instance was invoked. Local pytest
uses `-p no:cacheprovider` because of temporary-directory ACLs on this machine;
CI runs ordinary pytest.

## Known issues / limitations

- `Gateway.watch` is still memory-only: progress streams belong to a live run,
  and a run that outlived its process has no stream to join. `inspect` is the
  durable equivalent.
- Suspension remains manual, single-Bridge and single-writer by approved scope.
- A journalled run pays a durable write before and after every step.

## Next Recommended Action

Open the PR for `phase-3/gateway-journal` against `main`, run the review, apply
confirmed findings and let the owner merge. Then scope checkpoint retention with
the owner — it is the last known gap in the durability work — or move to the next
Roadmap phase (Phase 4, knowledge platform).
