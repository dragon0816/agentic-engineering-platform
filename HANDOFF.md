# Handoff — Phase 3 engine recovery (slice 12)

Updated: 2026-09-21 (Asia/Taipei).
Branch: `phase-3/engine-recovery`, based on `main` at `8a3345a` (PR #18 merged).

## Goal

Phase 3 slice 12 under the owner-approved scope (option A of three, recorded in
`docs/phases/PHASE_3_WORKFLOW.md`, slice 12): wire the checkpoint contracts,
SQLite backend and payload store into the real execution path, with **purely
manual** suspension — a person confirms the owning process is gone; the platform
never probes processes, reads PIDs or takes leases. Normative plan:
`docs/WORKFLOW_CHECKPOINTS.md` ("Engine recovery"); source decision:
`docs/PHASE_3_MIGRATION.md` (slice 12).

## Completed

- `workflow/journal.py`: `RunJournal` joins a `CheckpointStore` and a
  `PayloadStore` into the documented write-ahead ordering (`begin`,
  `step_started`, `step_completed`, `read`, `suspend`, `continuation`,
  `restore`), plus `SuspensionConfirmation` (whose `process_confirmed_stopped`
  must be exactly `True`), `JournalEntry` and the shared `intent_signature`
  helper the engine already used for in-memory keys.
- `workflow/engine.py`: optional `journal=` argument (absent → unchanged, in
  memory only). The run record and its arguments commit before execution; a step
  is not dispatched without an acknowledged `started`; a result payload commits
  before the step is recorded complete; the final completion and the terminal
  marker are one write, because a run whose every step is completed *is*
  succeeded. New entry points: `inspect_journal`, `suspend` (refused while the
  run is alive here) and `recover`.
- `recover` continues a suspended run in any process: the stored manifest must
  still be installed and identical (`manifest_changed` otherwise), the completed
  prefix is restored from verified payloads and never re-run, pre-flight and
  per-step authorization run again now, and an uncertain step obeys the existing
  `ResumePolicy`. The continuation is reserved atomically via `continue_run`.
- An idempotency key that already names a durable run conflicts rather than
  starting a second one, even after a restart clears the in-memory key table.
- 21 tests (`tests/test_engine_recovery.py`) over a real restart (a new engine
  built on the same SQLite file and payload directory): evidence after success
  and failure, journal-free parity, manual suspension and its validation, refused
  suspension of a live run, continuation across processes with chained inputs,
  a restored prefix that is not repeated, refusals (not suspended, uncertain
  effect, denied authorization, unknown run, changed manifest), a step that is
  never dispatched without its acknowledgment, and a journal that cannot start a
  run starting none.
- Docs: phase spec slice 12 (approved scope and why A over B/C), checkpoint plan
  "Engine recovery", `docs/CONTRACTS.md`, migration slice-12 decision, README.

- PR #19 opened; pre-merge review applied (9 findings, three reproduced by the
  reviewer): the in-memory `resume()` now refuses a journalled run
  (`use_recovery`), which closes both the double-continuation hole and the
  unjournalled-continuation hole, since only `recover()` reserves the durable
  "continued once" guard; `SuspensionConfirmation` is written into the
  checkpoint (`suspended_by`/`suspension_note`, required by the contract for
  every suspended record and not rewritable) instead of being validated and
  discarded; every durable write runs off the event loop via `asyncio.to_thread`
  and the SQLite store serialises access so it stays a single writer;
  `recover()` validates its timeout and, with `inspect_journal`, returns None
  instead of letting store errors escape; `suspend()` checks ownership before
  liveness; and a durable idempotency conflict names the existing run so the
  caller can inspect it. The capacity finding is recorded under limitations.

## In Progress

- PR #19 is open with the review posted; CI results for the final head are
  recorded on the PR.

## Remaining

- Review and merge the engine recovery PR after the posted review.
- Phase 3 is functionally complete against the Roadmap. Later work, each needing
  explicit scope: a Gateway surface for journal-backed run control (the Gateway
  currently exposes in-memory `inspect`/`resume`/`watch` only), and
  process-liveness or lease-based suspension if single-Bridge manual recovery
  stops being enough.
- Earlier deferred reviews remain: bounded Bridge event history, SkillRegistry
  parse cost, MCP installation round trips, Review `not_required` semantics,
  generic top-level package names, repeated RequestContext validation.

## Architecture decisions made

- Manual suspension (option A) over process liveness (B) or leases (C): the
  platform cannot honestly claim to know a foreign process is dead. PIDs are
  recycled and clocks drift; a person claims it and the claim is recorded with
  their name. B and C can be layered on this later without changing the contract.
- The journal is optional and additive. Every preserved source behavior —
  bounded in-memory history, caller-wait timeouts that do not finalize a run,
  first-failed-step termination — is untouched, and 419 existing tests passed
  unchanged before any new test was written.
- A failed or ambiguous acknowledgment forbids the next action rather than
  guessing: no dispatch without `started`, and a step whose completion could not
  be recorded stays `started` (uncertain), which is the truth.
- The stored manifest is provenance, not authority: recovery refuses a changed
  definition instead of executing a run the operator did not approve.

## Exact verification commands and results

Windows, Python 3.12.14, repository root:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 440 tests (419 prior, unchanged, + 21 recovery)
.venv/Scripts/python.exe -m ruff check .
# PASS
.venv/Scripts/python.exe -m ruff format --check .
# PASS
.venv/Scripts/python.exe -m mypy
# PASS: 58 source/test files
.venv/Scripts/python.exe -m pip check
# PASS
.venv/Scripts/python.exe -m build
# PASS: sdist and wheel; the journal ships in the sdist
git diff --check
# PASS
```

During development the contract taught a correction: `RunCheckpoint` requires
`succeeded` exactly when every step is completed, so the last completion and the
terminal marker had to become one write instead of two. Checkpoint files and
payloads live under pytest's temporary directory. No production service,
database server, transport, model, job or n8n instance was invoked. Local pytest
uses `-p no:cacheprovider` because of temporary-directory ACLs on this machine;
CI runs ordinary pytest.

## Known issues / limitations

- Recovery is an engine API. The Gateway's `inspect`/`resume`/`watch` still read
  the in-memory history only, so a host recovering across a restart calls the
  engine directly.
- Single Bridge, single writer: two engines over one checkpoint file are refused
  by the store, not coordinated. Nothing detects an abandoned run automatically.
- A journalled run pays a durable write before and after every step; this is the
  correctness gate, not a performance path.
- **The checkpoint store's capacity now bounds the production start path.** It
  has no TTL, eviction or deletion by design, so a host must size `capacity`
  for its retention needs; at capacity, new journalled runs fail
  `checkpoint_capacity` permanently and across restarts. A retention policy
  (what may be pruned, and how without making a used key executable again) is
  required before any long-lived deployment and needs its own scope.
- The in-memory `resume()` is unavailable on a journalled engine by design; use
  `suspend` + `recover`.

## Next Recommended Action

Open the PR for `phase-3/engine-recovery` against `main`, run the review, apply
confirmed findings and let the owner merge. Then agree with the owner what Phase
3 completion means for the Roadmap — whether to open a Gateway surface for
journal-backed run control, or to move to the next Roadmap phase.
