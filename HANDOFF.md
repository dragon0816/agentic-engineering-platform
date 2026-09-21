# Handoff — Phase 4 conflicts and decisions (slice 7)

Updated: 2026-09-21 (Asia/Taipei).
Branch: `phase-4/conflicts-decisions`, based on `main` after PR #29 merged.

## Goal

Phase 4 slice 7: the append-only decision record the planner injects, open
conflicts found by reading and cleared only with a reason on record, and
manual-edit detection computed into the lint report. The owner asked for all of
Phase 4 (slices 3–9) to be completed without check-ins unless something cannot
be decided; each slice is reviewed, merged on green CI and followed by the
next. Requirements: `docs/phases/PHASE_4_KNOWLEDGE.md` (slice 7); source
decision: `docs/PHASE_4_MIGRATION.md` (slice 7); contracts: `docs/CONTRACTS.md`
("Conflicts and decisions").

## Completed

- `knowledge/conflicts.py`: `Decision` (one of keep/reject/reason required),
  `append_decision` (header once, file never rewritten), `decisions_text`
  (what `IngestPlanner.plan(decisions=)` receives), `open_conflicts` (through
  the lint's `find_conflicts`), `clear_conflict` (exactly one marker line, with
  backup, refused when moved), `resolve` (decision recorded first, markers
  cleared bottom-up, `Resolution` with `cleared`/`missed`).
- `knowledge/lint.py`: `ManualEdits`, `page_hashes`, `record_state`,
  `manual_edits`; `LintReport.manual_edits` computed by `scan`.
- `Vault.state_read` / `state_write` for `.ingest-state.json` (`{}` when absent
  or corrupt).
- 3 regression tests (`tests/test_conflicts.py`); the pinned `conflicts.py`
  excerpt's characterization exists since slice 1.
- Docs: phase spec slice 7 requirements, `docs/CONTRACTS.md`, migration slice 7
  decision.

## In Progress

- Opening the review PR for this branch; review and CI results are recorded on
  the PR once available. Merge on green CI is authorized for Phase 4 slices.

## Remaining

- Slice 8: query with provenance — deterministic lexical retrieval over Raw
  sections and Wiki pages, answers whose every citation names a
  `KnowledgeSource` with page/slide where known; model synthesis optional and
  limited to what retrieval returned.
- Slice 9: migration adapter for an existing vault (adopt legacy Raw and Wiki
  under typed provenance, report drift, snapshot and restore).
- Deferred from Phase 3, each needing its own scope: a payload sweep,
  process-liveness or lease-based suspension, and the earlier deferred reviews.

## Architecture decisions made

- A marker is never cleared without its reason on record: `resolve` writes the
  decision before it removes anything.
- Manual-edit detection lives in `knowledge.lint` (computed by reading) and the
  report carries it; the decision record lives in `knowledge.conflicts`.
- The state file is the platform's own (`.ingest-state.json`, through the
  vault), chosen over git as the source did because a vault may live in a
  synced folder.

## Exact verification commands and results

Windows, Python 3.12.14, repository root, with the `office` extra installed:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 557 tests (554 prior + 3 conflicts; 2 skipped on Windows without
#       symlink privileges, run on Linux CI)
.venv/Scripts/python.exe -m ruff check .
# PASS
.venv/Scripts/python.exe -m ruff format --check .
# PASS
.venv/Scripts/python.exe -m mypy
# PASS: 76 source/test files
.venv/Scripts/python.exe -m pip check
# PASS
.venv/Scripts/python.exe -m build
# PASS: sdist and wheel
git diff --check
# PASS
```

No model, gateway, network, real vault, job or n8n instance was invoked. Local
pytest uses `-p no:cacheprovider` because of temporary-directory ACLs on this
machine; CI runs ordinary pytest.

## Known issues / limitations

- `decisions.md` grows without bound and enters every plan prompt in full, as
  in the source; a host that wants it condensed writes that itself.
- Manual-edit detection compares whole-page hashes; it says which pages
  changed, not what changed.

## Next Recommended Action

Open the PR for `phase-4/conflicts-decisions`, run the review, apply confirmed
findings, merge on green CI, then write the slice 8 requirements (query with
provenance) and implement it.
