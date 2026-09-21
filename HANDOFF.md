# Handoff — Phase 4 complete; next is the Phase 5 specification

Updated: 2026-09-21 (Asia/Taipei).
Branch: `phase-4/closure`, based on `main` after PR #32 merged.

## Goal

Close Phase 4 (knowledge platform) in the repository's status documents now
that its exit criteria are met, and leave the next phase's first step
explicit. No code changes in this handoff.

## Phase 4 summary (PRs #22–#32, all merged to `main`)

| Slice | PR | What landed |
|---|---|---|
| 1 vault safety model | #22 | `knowledge.vault`: `drop/`/`raw/` immutable, writes confined to `wiki/` and the root files, dry run default, backups, whole-plan rejection with rollback |
| 2 Drop → Raw | #23 | write-once Raw with content identity, section markers, drift chain (`supersedes`), `RawIndex` |
| 3 office extraction | #26 | PDF/PPTX/DOCX behind `Extractor` with page/slide/image relationships (`office` extra) |
| 4 image description | #27 | vision description through `ModelClient` at intake; `described_by` marks a model's words |
| 5 ingest planning | #28 | two-pass planning through `ModelClient`, condensation cache, `ensure_provenance`, plan validated by the vault |
| 6 static lint | #29 | `LintReport` (orphans, dangling, path links, frontmatter, provenance, pending sources, conflicts), `fix_links` |
| 7 conflicts and decisions | #30 | `decisions.md` append-only, conflict markers cleared in one write, manual-edit detection |
| 8 query with provenance | #31 | BM25 over Raw sections and Wiki paragraphs with CJK characters/bigrams, every passage cited, strict synthesis |
| 9 migration adapter | #32 | legacy Raw adopted by content hash through a ledger, `source_path` pages migrated, snapshot/restore, drift reported |

Exit criteria (Roadmap Phase 4): the office corpus round-trips to Raw with
traceable source/page/slide/image relationships (slices 2–4); Wiki generation
cannot mutate Raw (slices 1, 5, 9); query answers cite source provenance
(slice 8). Verified by the suite: 564 passed, 3 skipped on Windows (link
privileges); Linux CI runs every test.

## Completed in this handoff

- `docs/ROADMAP.md` status line, `docs/ARCHITECTURE.md` status line and the
  Phase 4 paragraph in `README.md` say Phase 4 is complete and what it holds.

## In Progress

- Nothing.

## Remaining

- Phase 5 specification (`docs/phases/PHASE_5_GATEWAY.md`) before any Phase 5
  code: extract the LiteLLM/company gateway behind the `ModelClient`
  interface, credentials externalized, provider patches isolated. Decisions
  to take with the owner first: where the gateway lives (`src/gateway/` or a
  separately deployable package), and which providers the first slice must
  satisfy (the Roadmap names local Ollama and the internal OpenAI-compatible
  gateway).
- Deferred from Phase 3, each needing its own scope: a payload sweep,
  process-liveness or lease-based suspension, and the earlier deferred reviews.
- Deferred from Phase 4: a retrieval cache (the corpus is rebuilt per query),
  host wiring that plans from an adopted document, a size-and-mtime shortcut
  for adopted-file drift checks, and image description for legacy `raw/`
  (adoption never writes a Raw file; a host drops the originals instead).

## Architecture decisions made

None in this handoff; Phase 4 decisions are in `docs/PHASE_4_MIGRATION.md`
(one section per slice).

## Exact verification commands and results

Windows, Python 3.12.14, repository root, with the `office` extra installed:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 564 passed, 3 skipped (link privileges)
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

See "Remaining". Nothing in Phase 4 is known to be broken.

## Next Recommended Action

Agree the two Phase 5 decisions above with the owner, then write
`docs/phases/PHASE_5_GATEWAY.md`, point `CLAUDE.md` at it, and start the
first Phase 5 slice on a `phase-5/...` branch.
