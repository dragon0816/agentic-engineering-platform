# Handoff — Phase 4 image description (slice 4)

Updated: 2026-09-21 (Asia/Taipei).
Branch: `phase-4/image-description`, based on `main` at `12efefd` (PR #26 merged).

## Goal

Phase 4 slice 4: image sections get a description through the model
interface, at intake time, with no vision provider named in knowledge code.
The owner asked for all of Phase 4 (slices 3–9) to be completed without
check-ins unless something cannot be decided; each slice is reviewed, merged on
green CI and followed by the next. Requirements:
`docs/phases/PHASE_4_KNOWLEDGE.md` (slice 4); decision:
`docs/PHASE_4_MIGRATION.md` (slice 4); contracts: `docs/CONTRACTS.md` ("Image
description").

## Completed

- `knowledge/describe.py`: `ImageDescriber(model, alias=, prompt=,
  max_output_tokens=, max_bytes=)` builds a `ModelRequest` with
  `ModelRequirements(vision=True)` and one user `ModelMessage` carrying the
  picture as a `data:` URI; `describe_sections` gives every image section
  without text one attempt, memoised per `image_ref`.
- `knowledge/raw.py`: `ImageDescription` contract (closed `status`:
  `described`, `too_large`, `unsupported_type`, `model_failed` with the
  model's `Failure`, `empty_answer`, `missing_bytes`; `text` tied to
  `described`, `failure` to `model_failed`); `Describer` protocol;
  `DropIntake(vault, extractors, describer=None)` describes on apply before the
  Raw file is written; `IntakeOutcome.descriptions` (apply only) and
  `images_to_describe` (distinct images an apply would describe; a dry run
  spends no tokens).
- 5 tests (`tests/test_describe.py`) with a fake vision model: request shape,
  every status, memoisation and trace ids, the intake in both modes, a failing
  model still writing the document, and an intake without a describer asking
  nothing.
- Docs: phase spec slice 4 requirements, `docs/CONTRACTS.md`, migration slice 4
  decision (why intake time, why inline `data:` URIs, why no provider).

## In Progress

- Opening the review PR for this branch; review and CI results are recorded on
  the PR once available. Merge on green CI is authorized for Phase 4 slices.

## Remaining

- Slice 5: ingest planning through `ModelClient` — two passes (relevance over
  a wiki inventory, then writes), chunked condensation cached by content hash,
  structured output validated into a `WritePlan` that slice 1 applies.
- Slice 6: static lint as a typed report. Slice 7: conflicts and decisions.
  Slice 8: query with provenance. Slice 9: migration adapter for an existing
  vault.
- Deferred from Phase 3, each needing its own scope: a payload sweep,
  process-liveness or lease-based suspension, and the earlier deferred reviews.

## Architecture decisions made

- Describe at intake, because Raw is write-once: a description is part of the
  document or it is not in Raw. Describing already-written Raw is deferred.
- The image travels inline as a `data:` URI in the provider-neutral message,
  so adapters need no file access and staged (not yet written) bytes work.
- Rule 6 held literally: the request declares `vision=True`; no provider,
  endpoint or credential appears in knowledge code. The alias is host config.
- A dry run spends no tokens and therefore cannot show the description text an
  apply would write; it reports the count and the spec says so.

## Exact verification commands and results

Windows, Python 3.12.14, repository root, with the `office` extra installed:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 532 tests (527 prior + 5 describe; 1 skipped on Windows without symlink
#       privileges, runs on Linux CI)
.venv/Scripts/python.exe -m ruff check .
# PASS
.venv/Scripts/python.exe -m ruff format --check .
# PASS
.venv/Scripts/python.exe -m mypy
# PASS: 69 source/test files
.venv/Scripts/python.exe -m pip check
# PASS
.venv/Scripts/python.exe -m build
# PASS: sdist and wheel
git diff --check
# PASS
```

No model, gateway, network, real vault, job or n8n instance was invoked; the
vision model in tests is a fake. Local pytest uses `-p no:cacheprovider`
because of temporary-directory ACLs on this machine; CI runs ordinary pytest.

## Known issues / limitations

- Only intake-time description exists; Raw files written before a describer was
  configured keep their image sections without text.
- One request per distinct image; no batching, no retries beyond what the
  model adapter does.
- `max_bytes` (5 MB) and the media-type table are fixed defaults; a host may
  pass others to `ImageDescriber`.

## Next Recommended Action

Open the PR for `phase-4/image-description`, run the review, apply confirmed
findings, merge on green CI, then write the slice 5 requirements (ingest
planning through `ModelClient`) and implement it.
