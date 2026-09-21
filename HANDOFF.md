# Handoff — Phase 4 office extraction (slice 3)

Updated: 2026-09-21 (Asia/Taipei).
Branch: `phase-4/office-extraction`, based on `main` at `41ed9a6` (PR #23 merged).

## Goal

Phase 4 slice 3: PDF, PPTX and DOCX originals round-trip to Raw with their
page/slide/image relationships, behind the `Extractor` protocol and an optional
dependency extra. The owner asked for all of Phase 4 (slices 3–9) to be
completed without check-ins unless something cannot be decided; each slice is
reviewed, merged on green CI and followed by the next. Requirements:
`docs/phases/PHASE_4_KNOWLEDGE.md` (slice 3); libraries and licenses:
`docs/PHASE_4_MIGRATION.md` (slice 3); contracts: `docs/CONTRACTS.md`
("Office extraction").

## Completed

- Optional extra `office` = `pypdf>=6,<7` (BSD-3-Clause), `python-pptx>=1,<2`
  (MIT), `python-docx>=1,<2` (MIT); transitive deps all permissive; versions,
  release cadence and typing recorded before adoption. CI installs
  `.[dev,office]`.
- `Extractor` protocol gained an `AssetSink`: `extract(data, assets)` hands
  image bytes to `assets.put(data, suffix)` and receives the `image_ref`.
  `StagedAssets` names each by content under the Raw document's own
  `<stem>/assets/` directory; the intake fixes the Raw name before extraction,
  lists asset refs in `written`, and writes them only on apply through the new
  `Vault.write_raw_bytes` (exclusive create; same bytes at the same name a
  no-op; different bytes `raw_exists`).
- `knowledge/office.py`: `PdfExtractor` (text and images per page; encrypted
  PDFs an empty password does not open are `undecodable`), `PptxExtractor`
  (text frames, tables, pictures per slide in shape order), `DocxExtractor`
  (paragraphs with headings as `#`, tables, inline pictures in body order; no
  page). `table_markdown` renders GitHub-style tables. Any library exception on
  a corrupt original maps to the closed status `undecodable`.
- 5 tests (`tests/test_office.py`) that generate the corpus in the test itself
  — a PDF with a real xref and an embedded image, a PPTX, a DOCX — and show it
  round-tripping to Raw with relationships intact, a repeated picture stored
  once, dry run and apply agreeing on every path, assets write-once, and Drop
  untouched. `test_raw.py` updated for the sink.
- Docs: phase spec slice 3 requirements, `docs/CONTRACTS.md`, migration slice 3
  decision with the license table and rejected alternatives (`PyMuPDF` is AGPL),
  README.

## In Progress

- Opening the review PR for this branch; review and CI results are recorded on
  the PR once available. Merge on green CI is authorized for Phase 4 slices.

## Remaining

- Slice 4: image description through `ModelClient` with `vision=True`,
  attached at intake time (Raw is write-once, so a description must be part of
  the document when it is written).
- Slice 5: ingest planning through `ModelClient` (two passes, condensation
  cache, structured output into a `WritePlan`).
- Slice 6: static lint as a typed report. Slice 7: conflicts and decisions.
  Slice 8: query with provenance. Slice 9: migration adapter for an existing
  vault.
- Deferred from Phase 3, each needing its own scope: a payload sweep,
  process-liveness or lease-based suspension, and the earlier deferred reviews.

## Architecture decisions made

- Extractors never write; the intake owns every byte that reaches disk, so
  dry run stays exact and Raw stays write-once even for images.
- Assets are content-named under the document's own directory, so a repeated
  image is stored once and a re-intake of identical bytes is a no-op.
- A broad exception boundary in extractors is deliberate: third-party parsers
  raise an open set on corrupt input, and the intake promises closed statuses.
- `PyMuPDF` was excluded on license (AGPL); the chosen libraries are all
  permissive.

## Exact verification commands and results

Windows, Python 3.12.14, repository root, with the `office` extra installed:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 524 tests (519 prior + 5 office; 1 skipped on Windows without symlink
#       privileges, runs on Linux CI)
.venv/Scripts/python.exe -m ruff check .
# PASS
.venv/Scripts/python.exe -m ruff format --check .
# PASS
.venv/Scripts/python.exe -m mypy
# PASS: 67 source/test files
.venv/Scripts/python.exe -m pip check
# PASS
.venv/Scripts/python.exe -m build
# PASS: sdist and wheel
git diff --check
# PASS
```

The office tests `importorskip` the libraries, so the core suite still passes
without the extra. No model, gateway, network, real vault, job or n8n instance
was invoked. Local pytest uses `-p no:cacheprovider` because of
temporary-directory ACLs on this machine; CI runs ordinary pytest.

## Known issues / limitations

- PDF tables arrive as text in reading order; PPTX speaker notes are not
  extracted; DOCX sections carry no page number.
- Images are stored as the library provides them; pypdf converts raw image
  streams to PNG. No image is resized or re-encoded by the platform.
- Extraction reads the whole original into memory; very large originals are a
  host concern for now.

## Next Recommended Action

Open the PR for `phase-4/office-extraction`, run the review, apply confirmed
findings, merge on green CI, then write the slice 4 requirements (image
description through `ModelClient`) and implement it.
