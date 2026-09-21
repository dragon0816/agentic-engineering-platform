# Handoff — Phase 4 migration adapter (slice 9, the last Phase 4 slice)

Updated: 2026-09-21 (Asia/Taipei).
Branch: `phase-4/migration`, based on `main` after PR #31 merged.

## Goal

Phase 4 slice 9: adopt an existing Obsidian vault under the platform's
provenance and immutability rules without treating it as a greenfield corpus
and without rewriting `raw/` — the Roadmap's "explicit migration adapter/path
for existing Obsidian vault content, existing Raw data, images and metadata".
The owner asked for all of Phase 4 (slices 3–9) to be completed without
check-ins unless something cannot be decided; each slice is reviewed, merged
on green CI and followed by the next. Requirements:
`docs/phases/PHASE_4_KNOWLEDGE.md` (slice 9); decision:
`docs/PHASE_4_MIGRATION.md` (slice 9); contracts: `docs/CONTRACTS.md`
("Migration adapter").

## Completed

- `knowledge/migrate.py`: `adopt(vault, mode=, today=, stamp=, readopt=)`
  returning an `AdoptionReport` (adopted, re-adopted, drifted and skipped Raw;
  migrated, unresolved and skipped pages; the exact write list; the snapshot
  name on an apply that wrote), `source_for_legacy`, `legacy_raw`, `snapshot`,
  `snapshots`, `restore` (adapted from the pinned `snapshot.py`).
- `knowledge/vault.py`: `LEDGER_FILE` (`.ingest-adopted.json`),
  `SNAPSHOT_DIR` (`.ingest-snapshot`), `Vault.ledger_read` / `ledger_write`
  sharing the state file's JSON reader.
- `knowledge/raw.py`: `RawEntry.adopted`, `RawIndex.scan(vault, ledger=True)`
  including ledger files whose bytes still hash to what was adopted,
  `adopted_document` / `load_document` so an adopted file is a `RawDocument`
  (paragraph sections, extractor `adopted.v1`) for planning and query.
- `knowledge/query.py`: the corpus reads every entry through `load_document`,
  so adopted files are cited by paragraph.
- 3 tests (`tests/test_migrate.py`): adoption in both modes over a legacy
  vault (CRLF sources page, Big5 file, empty file, stale path, unclosed
  frontmatter), Raw bytes unchanged, index/lint/planning/query seeing the
  adopted file, idempotence, drift and re-adoption, ingested and adopted Raw
  side by side, corrupt ledgers, snapshot/restore round trips.
- Docs: phase spec slice 9 requirements (and the Phase 4 exit-criteria
  note), `docs/CONTRACTS.md`, migration slice 9 decision (ADAPT `snapshot.py`;
  ledger over rewriting Raw or re-dropping it).

## In Progress

- Opening the review PR for this branch; review and CI results are recorded on
  the PR once available. Merge on green CI is authorized for Phase 4 slices.

## Remaining

- After this PR merges: a Phase 4 closure change — `docs/ROADMAP.md` status,
  `README.md` Phase 4 paragraph, `CLAUDE.md` active-phase pointer — and the
  Phase 5 specification (model gateway) before any Phase 5 code.
- Deferred from Phase 3, each needing its own scope: a payload sweep,
  process-liveness or lease-based suspension, and the earlier deferred reviews.
- Deferred from Phase 4: a retrieval cache (the corpus is rebuilt per query),
  planning driven from an adopted document by a host (the planner takes any
  `RawDocument` already; no host wiring exists yet).

## Architecture decisions made

- Legacy Raw is adopted through a ledger keyed by path with the content hash,
  never by rewriting the file or re-dropping it; drift is reported and
  re-adopted only by name.
- The generated half (wiki, root files, state, ledger) is snapshotted before
  an apply that writes; `raw/` and `drop/` are never part of a snapshot.
- An adopted file is a document whose sections are its paragraphs, so every
  consumer of Raw sees one shape.

## Exact verification commands and results

Windows, Python 3.12.14, repository root, with the `office` extra installed:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 564 passed, 2 skipped (symlink privilege)
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

No model, gateway, network, real vault, job or n8n instance was invoked. Local
pytest uses `-p no:cacheprovider` because of temporary-directory ACLs on this
machine; CI runs ordinary pytest.

## Known issues / limitations

- `RawIndex.scan` hashes every adopted file on each scan to detect drift;
  fine for hundreds of files, a size-and-mtime shortcut is a later concern.
- Images under a legacy `raw/` are not described or indexed by adoption; an
  adopted file is text only. Describing them would mean writing a Raw file,
  which adoption never does; a host can drop the originals instead.
- A drifted file re-adopted by name gets a new `source_id`; a sources page
  carrying the old id is then `unknown_source_id` in lint, by design.

## Next Recommended Action

Open the PR for `phase-4/migration`, run the review, apply confirmed findings,
merge on green CI, then make the Phase 4 closure change and write the Phase 5
specification.
