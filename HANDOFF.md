# Handoff — Phase 4 static lint (slice 6)

Updated: 2026-09-21 (Asia/Taipei).
Branch: `phase-4/static-lint`, based on `main` after PR #28 merged.

## Goal

Phase 4 slice 6: everything about the wiki that can be established by reading
it, as a typed report, with the one mechanical repair the source made. The
owner asked for all of Phase 4 (slices 3–9) to be completed without check-ins
unless something cannot be decided; each slice is reviewed, merged on green CI
and followed by the next. Requirements: `docs/phases/PHASE_4_KNOWLEDGE.md`
(slice 6); source decision: `docs/PHASE_4_MIGRATION.md` (slice 6); contracts:
`docs/CONTRACTS.md` ("Static lint").

## Completed

- Pinned `brain.py`'s static half as `tests/fixtures/source_vault_lint.txt`
  (checksums in the fixtures README); 3 characterization tests
  (`tests/test_source_lint.py`) execute it with the pinned ingest and conflicts
  excerpts supplying what it imported.
- `knowledge/lint.py`: `LintReport` (pages, types, orphans, dangling ranked,
  path_links, missing_frontmatter, broken_source_path, unknown_source_id,
  pending_sources, open_conflicts; `clean`), `scan(vault)`, `page_name`,
  `fix_links(vault, report, stamp=)` writing through `Vault.write` with a
  backup and keeping aliases and anchors. Nothing calls a model.
- 7 regression tests (`tests/test_lint.py`): every finding as typed values
  (including typed provenance and pending Raw sources), lenient frontmatter,
  nothing a page contains aborting the report, a superseded Raw not pending,
  the repair with aliases, anchors, backups and untouched line endings,
  `page_name`, and a link leaving the vault as a finding.
- Docs: phase spec slice 6 requirements, `docs/CONTRACTS.md`, migration slice 6
  decision, fixtures README.

- PR #29 opened; pre-merge review applied (10 findings, seven of them ways a
  page could abort or mislead the report): an empty `[[ ]]`, a bare `⚠️`, a
  malformed `source_id` and a non-UTF-8 page each raised out of `scan` — now
  findings (`unreadable` added, `UnknownSource.source_id` is `Text`, a bare
  marker reads `(marker without text)`); the strict Raw frontmatter reader
  called ordinary Obsidian frontmatter missing — `head_fields` reads it as
  leniently as the source did; a superseded Raw was pending forever — the
  `supersedes` chain excludes it; `Vault.write`/`append` translated line
  endings on Windows so a repair rewrote whole pages — `\n` everywhere;
  pages are read once (`Vault.wiki_files`) and `fix_links` reads only the
  flagged ones; the symlink test skips instead of silently passing and uses
  its own temp dir; the duplicated page text in the tests is one dict.
  Three regression tests added.

## In Progress

- PR #29 is open with the review posted; merge on green CI is authorized for
  Phase 4 slices.

## Remaining

- Slice 7: conflicts and decisions — append-only `Decision` record (the
  `decisions` text the planner injects), resolving a conflict, page-hash state
  and manual-edit detection added to the lint report.
- Slice 8: query with provenance. Slice 9: migration adapter for an existing
  vault (adopts legacy Raw so `pending_sources` and `broken_source_path` cover
  it).
- Deferred from Phase 3, each needing its own scope: a payload sweep,
  process-liveness or lease-based suspension, and the earlier deferred reviews.

## Architecture decisions made

- Computed, not modelled: the report is exact and free; judgement is a later,
  optional pass that takes the report as context.
- The source's rules are kept exactly where they encode a lesson (`.md` only,
  the root-file exception, entry points, flagged-only repair with case
  correction).
- Typed provenance (`source_id`) is checked against the Raw index; the legacy
  `source_path` check stays for an existing vault's pages.

## Exact verification commands and results

Windows, Python 3.12.14, repository root, with the `office` extra installed:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 554 tests (544 prior + 3 characterization + 7 regression; 2 skipped on
#       Windows without symlink privileges, run on Linux CI)
.venv/Scripts/python.exe -m ruff check .
# PASS
.venv/Scripts/python.exe -m ruff format --check .
# PASS
.venv/Scripts/python.exe -m mypy
# PASS: 74 source/test files
.venv/Scripts/python.exe -m pip check
# PASS
.venv/Scripts/python.exe -m build
# PASS: sdist and wheel
git diff --check
# PASS
```

Two expectations in the first draft of the tests were wrong and the pinned
excerpt corrected them: names match case-sensitively, so `[[Openhands]]` leaves
`OpenHands.md` an orphan until `fix_links`; and `[[CLAUDE.md]]` dangles because
it is not a wiki page, even though it is not a path violation. Vault
directories live under pytest's temporary directory; no model, gateway,
network or real vault touched. Local pytest uses `-p no:cacheprovider` because
of temporary-directory ACLs on this machine; CI runs ordinary pytest.

## Known issues / limitations

- `scan` reads every wiki page in full once per call; fine for hundreds of
  pages.
- A legacy Raw file without provenance frontmatter is not in the Raw index and
  so is not reported as pending; slice 9 adopts it.
- No judgement pass yet; the report is the computed half only.

## Next Recommended Action

Open the PR for `phase-4/static-lint`, run the review, apply confirmed
findings, merge on green CI, then write the slice 7 requirements (conflicts and
decisions) and implement it over the pinned conflicts excerpt.
