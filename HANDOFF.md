# Handoff — Phase 3 checkpoint contracts (slice 9)

Updated: 2026-09-21 (Asia/Taipei).
Branch: `phase-3/checkpoint-contracts`, based on `main` at `85a463f` (PR #15 merged).

## Takeover note

This slice was started by another coding session in this same checkout (branch
created, files written, uncommitted) and taken over by Claude Code at the owner's
request after that session went idle. Takeover reconciliation: PR #15 (optional
n8n adapter) was already merged, not "open" as the previous handoff said; the
uncommitted checkpoint work passed the full verification baseline unchanged
(363 tests, ruff, format, mypy 52 files) before any takeover edits. The owner's
scope approval ("single-Bridge manual restart recovery") had only existed in the
uncommitted phase-spec draft; committing this slice makes it durable.

## Goal

Phase 3 slice 9: a versioned, owner-scoped checkpoint contract and a bounded
in-memory single-writer reference store that define what manual restart recovery
would rely on — without a disk backend, engine integration or automatic recovery.
Normative plan: `docs/WORKFLOW_CHECKPOINTS.md`. Requirements:
`docs/phases/PHASE_3_WORKFLOW.md` (slice 9). Source decision:
`docs/PHASE_3_MIGRATION.md` (slice 9).

## Completed

- `common/checkpoints.py`: `CheckpointOwner`, `PayloadRef` (opaque protected
  payload reference: id, SHA-256, contract — never inline data), `StepCheckpoint`
  (`never_started` / `started` / `completed` with a result reference only when
  completed), `RunCheckpoint` v1 (owner, trace, exact manifest snapshot, runtime
  contract, intent digest, ordered step evidence, revision, key, parent /
  continuation links) with linear-evidence validation and a metadata-only
  `recovery_plan()` in which a started step is `uncertain`.
- `workflow/checkpoints.py`: `CheckpointStore` protocol (`get`, `find_key`,
  `create`, `replace` with revision compare-and-swap, `continue_run` atomic
  parent/child reservation), closed `CheckpointStoreError` codes including
  `unavailable` vs `commit_unknown`, and `MemoryCheckpointStore` (bounded, no
  eviction or deletion, owner-isolated reads, immutable intent and completed
  results, one step transition per write, atomic continuation).
- 40 tests: JSON/version/shape validation, invalid step evidence, key scoping and
  capacity, revision conflicts, immutability, deep-copy isolation, write-ahead
  ordering, atomic continuation and half-link prevention, injected fault windows
  (`unavailable` before/after an effect, `commit_unknown`) proving recovery never
  claims an effect was not invoked, terminal success, stale writers and lost
  acknowledgments.
- Docs: `docs/WORKFLOW_CHECKPOINTS.md`, `docs/CONTRACTS.md` "Checkpoint
  persistence boundary", migration slice-9 decision, phase spec slice 9 and
  sequence, README pointer.
- PR #16 opened; pre-merge review applied: `recovery_plan` reports a `running`
  record as `running` (only `suspended` needs input); a continuation keeps the
  parent's first unresolved step's evidence so a started step stays uncertain
  until the child re-acknowledges it; run identifiers are owner-scoped so one
  owner can neither observe nor block another's; a keyed `create` compares the
  intent fields as well as the digest; a two-node parent/continuation cycle is
  rejected; `replace` keys its compare-and-swap on `expected_revision` only;
  TypeAdapters are hoisted and redundant copies removed; the contract heading
  is an H2; tests assert exact error codes.

## In Progress

- PR #16 is open with the review posted; CI results for the final head are
  recorded on the PR.

## Remaining

- Review and merge the checkpoint-contracts PR after the posted review.
- Next Phase 3 slices (each needs explicit scope): a local durable backend with
  real transaction/restart tests, protected payload storage, and engine recovery
  wired through the existing Gateway/Bridge policy path with fresh authorization.
- Earlier deferred reviews remain: bounded Bridge event history, SkillRegistry
  parse cost, MCP installation round trips, Review `not_required` semantics,
  generic top-level package names, repeated RequestContext validation.

## Architecture decisions made

- Checkpoints are private execution-plane evidence: never a Registry asset, an
  execution grant, a model route or an n8n runtime. A stored manifest is
  provenance, not authority; recovery must re-check installed definitions,
  compatibility, schemas, dependencies and authorization.
- Durable acknowledgment is a correctness gate (write-ahead `started` before
  dispatch, `completed` only after the validated payload is committed) and is
  deliberately separate from the best-effort progress/log reporting hook.
- At restart, `started` means `uncertain` even if dispatch may not have happened;
  no step resumes automatically; the existing `ResumePolicy` and fresh Bridge
  authorization govern any continuation. Caller-wait timeout is not abandonment.
- No TTL, eviction or deletion in v1; capacity rejects new runs; keys and
  continuation links are retained for the store lifetime so history deletion can
  never silently make a used key executable again.

## Exact verification commands and results

Windows, Python 3.12.14, repository root:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 363 tests (323 prior + 40 checkpoint)
.venv/Scripts/python.exe -m ruff check .
# PASS
.venv/Scripts/python.exe -m ruff format --check .
# PASS: 75 files
.venv/Scripts/python.exe -m mypy
# PASS: 52 source/test files
.venv/Scripts/python.exe -m pip check
# PASS
.venv/Scripts/python.exe -m build
# PASS: sdist and wheel; checkpoint modules, tests and doc ship in the sdist
git diff --check
# PASS
```

Memory tests simulate fault windows; they do not prove filesystem crash
durability. No production service, transport, model, job, database or n8n
instance was invoked. Local pytest uses `-p no:cacheprovider` because of
temporary-directory ACLs on this machine; CI runs ordinary pytest.

## Known issues / limitations

- `MemoryCheckpointStore` is a reference model on one owning thread; nothing in
  the running platform reads or writes checkpoints yet.
- `PayloadRef` integrity and access control are host obligations; the store
  cannot verify a payload it never sees.
- Two coding sessions sharing one checkout is unsafe; the takeover was only
  possible because the other session had gone idle. Prefer separate worktrees.

## Next Recommended Action

Open the PR for `phase-3/checkpoint-contracts` against `main`, run the review,
apply confirmed findings and let the owner merge. Then scope the next slice with
the owner: the local durable backend (storage choice, transaction and restart
tests) before any engine wiring.
