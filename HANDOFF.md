# Handoff — Phase 3 SQLite checkpoint backend (slice 10)

Updated: 2026-09-21 (Asia/Taipei).
Branch: `phase-3/checkpoint-sqlite`, based on `main` at `64a9521` (PR #16 merged).

## Goal

Phase 3 slice 10 under the owner-approved scope (recorded in
`docs/phases/PHASE_3_WORKFLOW.md`, slice 10): a single-writer local SQLite
backend for the `CheckpointStore` protocol — one transaction per write,
acknowledged only after commit, standard library only — with no engine wiring,
payload storage or automatic recovery. Normative plan:
`docs/WORKFLOW_CHECKPOINTS.md` ("SQLite backend"); source decision:
`docs/PHASE_3_MIGRATION.md` (slice 10).

## Completed

- `workflow/checkpoints.py`: the slice-9 transition rules are now shared
  functions (`check_create`, `check_replace`, `check_continue`, `same_intent`,
  `linked_parent`, validators) used by both backends, so they cannot drift;
  `MemoryCheckpointStore` is unchanged in behavior.
- `workflow/checkpoints_sqlite.py`: `SqliteCheckpointStore(path, capacity=50)` —
  schema with a `schema_version` meta row (unknown versions refuse to open),
  owner/run/key-indexed rows holding the checkpoint JSON, `synchronous=FULL`,
  `BEGIN IMMEDIATE` … `COMMIT` per write, `timeout=0` so a second writer is
  refused (`unavailable`) rather than waited for, `unavailable` for any failure
  before commit (rolled back) and `commit_unknown` when `COMMIT` itself raises,
  owner-scoped reads outside transactions, capacity counted over persisted rows.
- Tests: the contract suite in `tests/test_checkpoints.py` is parametrized over
  both backends (`make_store` fixture); `tests/test_checkpoints_sqlite.py` adds
  restart persistence of evidence/keys/links/capacity, key reuse after restart,
  evidence-only rows, schema refusal, second-writer refusal, closed store,
  invalid capacity, commit failure before and after the real commit (read back
  decides), and a failure inside a transaction leaving nothing written and
  allowing a plain retry.
- Docs: phase spec slice 10 (approved scope) and sequence, checkpoint plan
  "SQLite backend" section, `docs/CONTRACTS.md`, migration slice-10 decision,
  README.

## In Progress

- Opening the review PR for this branch; review and CI results are recorded on
  the PR once available.

## Remaining

- Review and merge the SQLite backend PR after the posted review.
- Next Phase 3 slices (each needs explicit scope): protected payload storage
  (what `PayloadRef` points at, access control, digest verification) and engine
  recovery wired through the existing Gateway/Bridge policy path with fresh
  authorization; a coordinator that marks abandoned runs `suspended` only with
  exclusive ownership.
- Earlier deferred reviews remain: bounded Bridge event history, SkillRegistry
  parse cost, MCP installation round trips, Review `not_required` semantics,
  generic top-level package names, repeated RequestContext validation.

## Architecture decisions made

- Durability is new platform semantics, not source parity: the source Bridge
  keeps runs in memory and mirrors them best-effort to a dashboard, which is
  neither a checkpoint store nor a restart contract.
- One backend rule set: legality lives in shared functions; a backend only
  decides how to commit atomically. The memory model stays the executable
  specification the durable backend must match.
- Failure vocabulary is the contract: `unavailable` = known not committed
  (retry is safe), `commit_unknown` = read back before proceeding; a second
  writer is refused, never queued; an unknown schema version fails closed.
- The file path is host configuration and never inside the project; rows hold
  evidence and payload references only.

## Exact verification commands and results

Windows, Python 3.12.14, repository root:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 394 tests (366 prior; contract suite now runs on both backends, plus 9 SQLite durability tests)
.venv/Scripts/python.exe -m ruff check .
# PASS
.venv/Scripts/python.exe -m ruff format --check .
# PASS
.venv/Scripts/python.exe -m mypy
# PASS: 54 source/test files
.venv/Scripts/python.exe -m pip check
# PASS
.venv/Scripts/python.exe -m build
# PASS: sdist and wheel; the SQLite backend ships in the sdist
git diff --check
# PASS
```

Tests were written together with the backend and two test fixtures were
corrected during development (a manifest field name `secrets` tripped a
too-broad assertion; fault-injecting subclasses must not fail the schema
commit). No production service, database server, transport, model, job or n8n
instance was invoked; SQLite files live under pytest's temporary directory.
Local pytest uses `-p no:cacheprovider` because of temporary-directory ACLs on
this machine; CI runs ordinary pytest.

## Known issues / limitations

- Single process, single owning thread, single file; no WAL, no multi-process
  coordination, no leases. Crash durability relies on SQLite's journal with
  `synchronous=FULL`; the tests simulate commit failures rather than power loss.
- Still no TTL, eviction, deletion, payload storage, engine wiring or automatic
  recovery.

## Next Recommended Action

Open the PR for `phase-3/checkpoint-sqlite` against `main`, run the review, apply
confirmed findings and let the owner merge. Then scope the next slice with the
owner: protected payload storage or engine recovery wiring (the latter needs the
coordinator/ownership semantics from `docs/WORKFLOW_CHECKPOINTS.md` item 5).
