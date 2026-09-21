# Handoff — Phase 4 Drop → Raw with provenance (slice 2)

Updated: 2026-09-21 (Asia/Taipei).
Branch: `phase-4/drop-intake`, based on `main` at `a59ef7f` (PR #22 merged).

## Goal

Phase 4 slice 2: originals under `drop/` become Raw Markdown that carries its
own provenance, with identity by content rather than path. Requirements:
`docs/phases/PHASE_4_KNOWLEDGE.md` (slice 2); source decision:
`docs/PHASE_4_MIGRATION.md` (slice 2); contracts: `docs/CONTRACTS.md`
("Drop → Raw").

## Completed

- `knowledge/raw.py`: `RawSection` (kind `text`/`table`/`image`, text, optional
  `page`/`slide`, `image_ref` under `raw/` exactly for images) and
  `RawDocument` (document-level `KnowledgeSource` with `raw_ref`, `extractor`,
  `created`, ≥1 section); `render`/`parse` round-trip the Markdown form
  exactly — provenance frontmatter plus numbered section markers carrying
  page/slide/image. `source_for(bytes, original_ref)` derives `sha256` and
  `source_id` from content.
- `Vault.write_raw` (create, never replace: `raw_exists`; `outside_raw`
  otherwise), `Vault.read_original` (`outside_drop`, `missing_original`),
  `Vault.raw_files`, `Vault.exists`. Raw is write-once; Drop is read-only.
- `DropIntake(vault, extractors).intake(drop_rel, mode, today)` with closed
  statuses `written` / `duplicate` / `drifted` / `unsupported` / `undecodable`
  / `empty`, dry run by default, a drifted original keeping the old Raw and
  writing the new one as `<stem>--<8 hex>.md` with `supersedes` naming the old
  source. `Extractor` protocol; `PlainTextExtractor` and `MarkdownExtractor`
  (drops the original's own frontmatter) with no new dependency. `raw_index`
  skips Raw files without provenance so an existing vault is never rewritten.
- 15 tests (`tests/test_raw.py`): content identity, contract refusals, the
  round trip with pages/slides/images, parse refusals, both extractors, every
  intake status in both modes, drift, write-once Raw and read-only Drop, the
  index skipping legacy files, honest outcomes, any text and any line ending
  round-tripping byte for byte, equivalent path spellings, drift chains and
  batch dry runs, and legacy files in other encodings or in the way.
- Docs: phase spec slice 2 requirements, `docs/CONTRACTS.md`, migration slice 2
  decision (ADAPT the intent of `collect.py`; do not migrate path-keyed dedup).

- PR #23 opened; pre-merge review applied (10 findings, most of them real):
  an original containing marker-like text raised an uncaught `ValidationError`
  out of `intake` — body lines are now escaped so any text is representable,
  and `unrepresentable` is a closed status for anything the contracts still
  refuse; CRLF originals were stored corrupted on Windows and any `\r`, form
  feed or Unicode separator broke the round trip — line endings are
  normalized on entry, `parse` splits on `\n` only, and `write_raw` writes
  `\n` on every platform; a legacy Raw file in another encoding crashed every
  intake — the index reads only each file's head and skips what it cannot
  decode; `supersedes` named an arbitrary earlier version after repeated drift
  — each Raw records what it supersedes and the latest is found by following
  links; `drop/./d.txt` was a different identity from `drop/d.txt` — paths are
  canonical; the hash-suffixed name was never checked for existence — it is
  escalated past any file already there so dry run and apply agree; an image
  reference with whitespace could not be parsed back — refused; `write_raw`
  was check-then-act — exclusive creation now; one frontmatter reader and the
  shared `provenance_lines` serve both `parse` and the index; `intake_all`
  runs a batch over one index scan. Four regression tests added.

## In Progress

- PR #23 is open with the review posted; CI results for the final head are
  recorded on the PR.

## Remaining

- Review and merge this PR (owner says "merge #N").
- Slice 3 next: office extraction (PDF/PPTX/DOCX) behind `Extractor` as an
  optional dependency extra — record license and maintenance status of each
  library before adoption (owner's rule); tables as Markdown, images saved
  beside Raw with page/slide relationships. Write its requirements first.
- Slices 4–9 as outlined in the phase spec.
- Deferred from Phase 3, each needing its own scope: a payload sweep,
  process-liveness or lease-based suspension, and the earlier deferred reviews.

## Architecture decisions made

- Identity is the content (`sha256` of the original's bytes); the source's
  `source_path` dedup is not migrated. Same content anywhere is one source; a
  changed original is a new source and reported as drift.
- Raw is write-once. `Vault.write_raw` is the only writer and refuses an
  existing file, which is the only immutability a pipeline can enforce.
- A drifted original never replaces the old Raw; the new Raw lives beside it
  under a hash-suffixed name so nothing collides and history stays readable.
- Provenance and relationships live in the Raw file itself (frontmatter and
  section markers), so lint (slice 6) and query (slice 8) recover them from
  the file alone.

## Exact verification commands and results

Windows, Python 3.12.14, repository root:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 519 tests (504 prior + 15 raw; 1 skipped on Windows without symlink
#       privileges, runs on Linux CI)
.venv/Scripts/python.exe -m ruff check .
# PASS
.venv/Scripts/python.exe -m ruff format --check .
# PASS
.venv/Scripts/python.exe -m mypy
# PASS: 65 source/test files
.venv/Scripts/python.exe -m pip check
# PASS
.venv/Scripts/python.exe -m build
# PASS: sdist and wheel
git diff --check
# PASS
```

Vault directories live under pytest's temporary directory. No model, gateway,
network, real vault, job or n8n instance was invoked. Local pytest uses
`-p no:cacheprovider` because of temporary-directory ACLs on this machine; CI
runs ordinary pytest.

## Known issues / limitations

- Only `.txt` and `.md` originals are supported; anything else is
  `unsupported` until slice 3.
- A single `intake` scans the index once per call; a batch should use
  `intake_all`, which scans once and keeps the index current with its writes.
- Drift is detected per `original_ref`; renaming an original and changing it
  looks like a fresh source, which is correct by the content rule but loses
  the "supersedes" link.

## Next Recommended Action

Open the PR for `phase-4/drop-intake` against `main`, run the review, apply
confirmed findings and let the owner merge. Then write the slice 3 requirements
(office extraction) and record the candidate libraries' licenses before adding
any dependency.
