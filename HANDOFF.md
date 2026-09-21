# Handoff — Phase 4 query with provenance (slice 8)

Updated: 2026-09-21 (Asia/Taipei).
Branch: `phase-4/query`, based on `main` after PR #30 merged.

## Goal

Phase 4 slice 8: questions over the vault answered with passages whose every
citation names where the words came from — the Roadmap's "query answers can
cite source provenance". The owner asked for all of Phase 4 (slices 3–9) to be
completed without check-ins unless something cannot be decided; each slice is
reviewed, merged on green CI and followed by the next. Requirements:
`docs/phases/PHASE_4_KNOWLEDGE.md` (slice 8); decision:
`docs/PHASE_4_MIGRATION.md` (slice 8); contracts: `docs/CONTRACTS.md` ("Query
with provenance").

## Completed

- `knowledge/query.py`: `tokens` (lowercased words, scripts split, CJK
  characters plus bigrams plus the run), `cited_numbers` (`[2]`, `[1, 3]`,
  `[1-3]`), `retrieve(vault, question, k=)` (BM25 over every section with
  text of every current Raw and every Wiki paragraph after its frontmatter,
  ties by corpus order), `Citation` (`raw`: source, file, section,
  page/slide; `wiki`: page and the source behind it when the page carries
  `source_id`), `Passage`, `Answer` with closed statuses (`retrieved`,
  `answered`, `unanswered`, `uncited`, `model_failed`, `no_match`), and
  `QueryEngine(vault, model=, alias=).ask(question, k=, trace=)` whose
  synthesis may cite only retrieved passages.
- `knowledge/modelcalls.py`: `failure_from_exception`, the one place an
  adapter's exception becomes a retryable `Failure`, used by description,
  planning and query. `knowledge.lint.body_of` splits a page's body from its
  frontmatter (CRLF tolerated; `head_fields` tolerates CRLF too).
- 4 tests (`tests/test_query.py`) over a small corpus with pages, slides, a
  CRLF sources page carrying provenance, an entity page without, and a
  superseded Raw version.
- Docs: phase spec slice 8 requirements, `docs/CONTRACTS.md`, migration slice 8
  decision (lexical first, bigrams over a segmenter, strict synthesis) with the
  review-driven changes recorded.
- PR #31 review (10 findings) applied: superseded Raw excluded; Latin glued to
  CJK tokenized; CJK unigrams; blank question is `no_match`, not a validation
  error; frontmatter split shared with lint and CRLF-safe; honest "no answer"
  is `unanswered`, not refused; `[1, 2]` and `[1-3]` citations; shared
  adapter-failure helper; a real image-section assertion; per-request default
  trace ids.

## In Progress

- Nothing; merge of PR #31 on green CI is authorized for Phase 4 slices.

## Remaining

- Slice 9: migration adapter for an existing vault — adopt legacy Raw (no
  provenance frontmatter) into the index without rewriting it, migrate
  `source_path` sources pages to typed provenance with backups, report
  path-versus-hash drift, snapshot and restore the generated half.
- Deferred from Phase 3, each needing its own scope: a payload sweep,
  process-liveness or lease-based suspension, and the earlier deferred reviews.

## Architecture decisions made

- Lexical, deterministic retrieval first; embeddings can come later behind the
  same `retrieve` shape.
- Words without a retrieved source behind them are not an answer: synthesized
  text is refused unless every citation is real.
- No provider named; synthesis is one `ModelRequest` like every other model
  call in knowledge code.

## Exact verification commands and results

Windows, Python 3.12.14, repository root, with the `office` extra installed:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 561 passed, 2 skipped (symlink privilege) in 4.7s
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

No model, gateway, network, real vault, job or n8n instance was invoked; the
model in tests is a fake. Local pytest uses `-p no:cacheprovider` because of
temporary-directory ACLs on this machine; CI runs ordinary pytest.

## Known issues / limitations

- Retrieval rebuilds the corpus on every call by reading every Raw and Wiki
  file; fine for hundreds of pages, a cache is a later concern.
- BM25 treats CJK as characters and character pairs; no stemming for any
  language.
- Legacy Raw files without provenance are not part of the corpus until slice 9
  adopts them.

## Next Recommended Action

Merge PR #31 on green CI, then write the slice 9 requirements (migration
adapter) and implement it on `phase-4/migration` — the last Phase 4 slice.
