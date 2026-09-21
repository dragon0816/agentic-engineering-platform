# Handoff — Phase 3 checkpoint retention (slice 14, closes Phase 3)

Updated: 2026-09-21 (Asia/Taipei).
Branch: `phase-3/checkpoint-retention`, based on `main` at `7416baf` (PR #20 merged).

## Goal

Close the last known operational gap of Phase 3: since slice 12 the checkpoint
store's capacity bounds the production start path, and the store had no
deletion at all. The owner asked for everything listed to be finished and Phase
3 confirmed complete, then Phase 4 begun. Requirements:
`docs/phases/PHASE_3_WORKFLOW.md` (slice 14); decision and alternatives:
`docs/PHASE_3_MIGRATION.md` (slice 14); plan: `docs/WORKFLOW_CHECKPOINTS.md`
("Retention").

## Completed

- `CheckpointStore.retire(owner, run_id)` on both backends. Legal for a record
  that is no longer executing — a `succeeded` run, or a `suspended` run whether
  continued or not — and `invalid_transition` for a `running` one (`check_retire`
  is a shared rule like the others). An unseen run is `missing`.
- **A retired idempotency key never executes again.** Retiring a keyed record
  leaves a tombstone; `create` under that key is the new closed code
  `key_retired` whatever the intent, `find_key` no longer finds a record, and
  tombstones do not count toward capacity.
- SQLite schema version `2` (`retired_keys` table). A version-`1` file is migrated
  in place; any other version refuses to open, so older code fails closed on a
  file it does not fully understand.
- `WorkflowEngine.retire` and `Gateway.retire` (new `retire` action on
  `RunControlResult`), refusing a run alive in that engine like `suspend`, with
  `missing` folded into `unknown` for the same indistinguishability rule. The
  engine maps `key_retired` to `checkpoint_key_retired` through the existing
  store-error path, so a retired key resubmitted after a restart is refused
  without dispatch.
- 22 tests (`tests/test_checkpoint_retention.py`), parametrized over both
  backends where they apply: freeing a slot, the tombstone under the same and a
  different intent, a running record never being history, giving up on a
  suspended run, a continued parent, tombstone and schema survival across a
  restart, the version-`1` migration, the database-level refusal, an ambiguous
  commit leaving the record, and the engine/Gateway paths: a failed run leaving
  without running again, a continued run and its parent, another owner unable
  to learn a run is alive, a retired run becoming an ordinary in-memory one, a
  live run, a retired key resubmitted after a restart, and an unjournalled
  engine.
- Docs: checkpoint plan "Retention" plus its three stale "no deletion" sentences,
  `docs/CONTRACTS.md`, phase spec slice 14 and sequence, migration decision
  (with the alternatives not taken), README.

- PR #21 opened; pre-merge review applied (9 findings, three of them real
  defects): `retire` now checks ownership before liveness, so another owner's
  live run is `missing` rather than a hint it exists; **any suspended run is
  retirable, continued or not** — the first draft required a continuation,
  which would have leaked one slot per deterministic failure, whereas now a run
  that failed for good leaves by `suspend` then `retire` without ever running
  again; a retired run's in-memory record drops its journal so `resume` no
  longer dead-ends at `use_recovery`; the SQLite database refuses a retired key
  itself through a trigger, not only the application; keyed `create` probes
  the live key before the tombstone; `entry_of` is the one name for the
  journal's metadata view; tombstone growth is documented as the price of the
  guarantee; and the stale `docs/CONTRACTS.md` sentences were reconciled.

## In Progress

- PR #21 is open with the review posted; merge on green CI is authorized by the
  owner once Phase 3 is confirmed complete.

## Remaining

- Merge this PR once review findings are applied and CI is green.
- **Phase 3 is then complete** against `docs/ROADMAP.md`: deterministic
  commands and Agents trigger workflows through one contract; n8n, when enabled,
  uses the same contract; runs are journalled, recoverable across restarts and
  retirable without a used key ever running again.
- Next phase: Phase 4, knowledge platform (`docs/ROADMAP.md`). It has no phase
  specification yet; the first action is to write
  `docs/phases/PHASE_4_KNOWLEDGE.md` from the architecture and the source
  repositories, then slice it.
- Deferred, each needing its own scope: a payload sweep (removing what no
  retained record references), process-liveness or lease-based suspension, and
  the earlier deferred reviews (bounded Bridge event history, SkillRegistry parse
  cost, MCP installation round trips, Review `not_required` semantics, generic
  top-level package names, repeated RequestContext validation).

## Architecture decisions made

- Explicit per-run retirement over TTL or oldest-first eviction: silent
  deletion is what the plan forbids, and age says nothing about whether a run is
  finished.
- Tombstones over "never delete keyed records": the record goes, the key binding
  stays, capacity counts records only.
- Payloads are not removed with the record: a continuation shares its parent's
  payloads, so a sweep needs reference counting across records and is its own
  policy.
- A `running` record is never retirable, however old: the platform still cannot
  know a foreign process is dead, the same reason suspension is manual.

## Exact verification commands and results

Windows, Python 3.12.14, repository root:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 472 tests (450 prior + 22 retention)
.venv/Scripts/python.exe -m ruff check .
# PASS
.venv/Scripts/python.exe -m ruff format --check .
# PASS
.venv/Scripts/python.exe -m mypy
# PASS: 60 source/test files
.venv/Scripts/python.exe -m pip check
# PASS
.venv/Scripts/python.exe -m build
# PASS: sdist and wheel
git diff --check
# PASS
```

One existing test simulated an unknown schema version with `'2'`, which is now
the current version; it uses `'99'`. One new test expected `unavailable` from a
fabricated lock error and learned the store's classification is stricter: an
error without SQLite's "definitely not committed" name is `commit_unknown`, and
the test now asserts that. Checkpoint files and payloads live under pytest's
temporary directory. No production service, database server, transport, model,
job or n8n instance was invoked. Local pytest uses `-p no:cacheprovider`
because of temporary-directory ACLs on this machine; CI runs ordinary pytest.

## Known issues / limitations

- Payload storage grows until a payload sweep exists.
- Retention is manual and per run; a host that wants a policy (for example,
  retire every succeeded run older than a week) writes that loop itself.
- `Gateway.watch` remains memory-only; suspension remains manual, single-Bridge
  and single-writer by approved scope.

## Next Recommended Action

Open the PR for `phase-3/checkpoint-retention` against `main`, run the review,
apply confirmed findings, merge on green CI (authorized), then start Phase 4 by
writing its phase specification.
