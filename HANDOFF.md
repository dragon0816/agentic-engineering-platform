# Handoff — Phase 4 ingest planning (slice 5)

Updated: 2026-09-21 (Asia/Taipei).
Branch: `phase-4/ingest-planning`, based on `main` after PR #27 merged.

## Goal

Phase 4 slice 5: from one Raw document to a `WritePlan` through the model
interface, in the two passes the source tooling found cheaper and more accurate
than one, with condensation cached by content. The owner asked for all of Phase
4 (slices 3–9) to be completed without check-ins unless something cannot be
decided; each slice is reviewed, merged on green CI and followed by the next.
Requirements: `docs/phases/PHASE_4_KNOWLEDGE.md` (slice 5); source decision:
`docs/PHASE_4_MIGRATION.md` (slice 5); contracts: `docs/CONTRACTS.md` ("Ingest
planning").

## Completed

- `knowledge/planning.py`: `IngestPlanner(model, vault, alias=, conventions=,
  max_output_tokens=, condense_over=, chunk_chars=)`. `plan(document, today=,
  decisions=)` runs relevance (inventory of wiki paths and titles → existing
  pages, capped at 8) then the writes (related pages in full, `index.md`,
  settled decisions, source text), each a `ModelRequest` with a system message
  (the conventions), `structured_output=True` and an output contract. A long
  source is condensed chunk by chunk first and cached under
  `.ingest-cache/<sha256>.md`. The answer is `structured_output` or JSON
  extracted from fences/prose, validated loosely (`IngestProposal`) then
  strictly (`WritePlan`), repaired to carry the provenance lines
  (`ensure_provenance`), and validated by a vault dry run. `PlanningOutcome`
  statuses: `planned`, `invalid` (plan + problems), `model_failed` (an adapter
  that raises included), `unparseable`; plus `relevant`, `condensed`,
  `cache_hit`. The planner writes nothing but the cache.
- `Vault.wiki_pages()` (path, title from frontmatter or stem), `cache_read` /
  `cache_write` confined to `.ingest-cache/` and keyed by a content hash.
- `source_text(document)`: sections in order, each image as
  `[image on page N: description]` or `(no description)`.
- 8 tests (`tests/test_planning.py`) with a fake model: source text, JSON
  extraction, provenance repair, both passes and their prompts with a plan the
  vault applies end to end, prose answers, invalid and malformed plans,
  failures on either pass and an adapter that raises, condensation with chunk
  count and cache reuse across planners (and no partial cache on failure), and
  the cache's confinement.
- Docs: phase spec slice 5 requirements, `docs/CONTRACTS.md`, migration slice 5
  decision (ADAPT the passes, condensation cache, JSON extraction and decision
  injection; do not migrate the HTTP client, review output or runtime schema).

## In Progress

- Opening the review PR for this branch; review and CI results are recorded on
  the PR once available. Merge on green CI is authorized for Phase 4 slices.

## Remaining

- Slice 6: static lint as a typed report (pin `brain.py`'s `scan` first).
- Slice 7: conflicts and decisions (the `decisions` text the planner takes).
- Slice 8: query with provenance. Slice 9: migration adapter for an existing
  vault.
- Deferred from Phase 3, each needing its own scope: a payload sweep,
  process-liveness or lease-based suspension, and the earlier deferred reviews.

## Architecture decisions made

- The model proposes; the vault disposes. The plan goes back through
  `Vault.apply`, which is slice 1's whole point; the planner never writes wiki
  content.
- Provenance lines are repaired in, not demanded of the model: they are
  deterministic, and a rejected plan wastes the condensation.
- Conventions are a platform default a host may replace; the planner does not
  read a vault schema file and does not care which language the conventions
  are in.
- Every failure is a closed status, including an adapter that raises.

## Exact verification commands and results

Windows, Python 3.12.14, repository root, with the `office` extra installed:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 543 tests (535 prior + 8 planning; 1 skipped on Windows without symlink
#       privileges, runs on Linux CI)
.venv/Scripts/python.exe -m ruff check .
# PASS
.venv/Scripts/python.exe -m ruff format --check .
# PASS
.venv/Scripts/python.exe -m mypy
# PASS: 71 source/test files
.venv/Scripts/python.exe -m pip check
# PASS
.venv/Scripts/python.exe -m build
# PASS: sdist and wheel
git diff --check
# PASS
```

No model, gateway, network, real vault, job or n8n instance was invoked; the
model in tests is a fake. Local pytest uses `-p no:cacheprovider` because of
temporary-directory ACLs on this machine; CI runs ordinary pytest.

## Known issues / limitations

- The relevance pass sees at most `condense_over` characters of the source;
  the plan pass sees the whole (condensed) text.
- The condensation cache has no size bound or expiry; it is keyed by content,
  so it never goes stale, only large.
- One plan per source; batching several sources into one plan is not offered.

## Next Recommended Action

Open the PR for `phase-4/ingest-planning`, run the review, apply confirmed
findings, merge on green CI, then pin `brain.py`'s static `scan` and write the
slice 6 requirements (static lint).
