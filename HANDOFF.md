# Handoff

Date: 2026-09-30 (Asia/Taipei)
Branch: `codex/hermes-structured-evidence`
Base: `origin/main` at `127c69f059e470486ab44b63e964ce611dc6d018`

## Goal

Allow the trusted Hermes evidence response requested by Local Codex to become a
new queue item without weakening the fixed-schema, untrusted-evidence boundary.

## Completed

- Confirmed PR #133 merged, updated the OpenLab Local Codex Worker checkout to
  merge commit `127c69f`, rebuilt its Python 3.12 virtual environment, and
  restarted the `AEP Local Codex Worker` Scheduled Task.
- Re-queued Issue #132 once. The worker successfully replaced its earlier
  `FileNotFoundError` with a bounded evidence request.
- Confirmed Hermes returned complete evidence on both #132 and the newer #134.
- Diagnosed the apparent successful-but-idle queue run: the workflow's exact
  key allowlist rejected Hermes' new `evidence_details`, then selected the older
  valid failure and deduplicated its already-existing request.
- Added an optional structured evidence contract shared by GitHub validation and
  the Python worker. It requires exact artifact/request/profile/SHA identities,
  fixed top-level fields, JSON-only values, bounded depth/collections/strings,
  and a 48,000-character total cap.
- Replayed the actual latest #134 Hermes payload against the new Python contract;
  it was accepted at 7,202 JSON characters for target `127c69f`.

## In Progress

- The focused structured-evidence repair is verified locally and needs commit,
  push, PR review, and merge.

## Remaining

1. Commit, push, and open the focused repair PR.
2. After merge, reapply `codex-fix` to the newer Issue #134 once so GitHub queues
   its structured evidence for Local Codex. Keep #132 as historical evidence.
3. Confirm #134 becomes `codex-local-running` and then produces either a Draft
   repair PR or a bounded terminal result.
4. If a Draft repair PR appears, let CI pass and have Hermes retest its exact
   head SHA; human review remains required before merge.

## Architecture decisions made

- `evidence_details` is optional, preserving initial `hermes-failure/v1`
  payloads and existing producers.
- Structured evidence remains data inside the untrusted prompt block. It cannot
  provide commands, GitHub credentials, delivery authority, or merge authority.
- GitHub and the local worker both validate the contract; accepting it only at
  one boundary would leave the loop failing later or weaken defense in depth.
- #134 is the next active repair because it tests the latest merged main SHA;
  #132 is retained as auditable historical evidence.

## Verification

Supported target: Windows, Python 3.12. Browser tests excluded per owner
instruction.

```text
python -m pytest tests/test_codex_remote_test_workflow.py -q
21 passed

python -m pytest --ignore=tests/test_browser.py -q
1346 passed, 4 skipped

python -m ruff check .
All checks passed

python -m ruff format --check .
288 files already formatted

python -m mypy src tests
Success: no issues found in 224 source files

Live #134 contract replay
live_payload=accepted
target_sha=127c69f059e470486ab44b63e964ce611dc6d018
evidence_json_chars=7202
```

The first full-suite attempt used a workspace `.scratch` basetemp and produced
48 existing file-store failures with `unavailable`; the representative test and
the complete suite passed when rerun under the standard Windows TEMP root.

## Known issues

- Until this branch merges, reapplying `codex-fix` merely selects the older
  payload and reports workflow success without queueing the structured evidence.
- #132 and #134 still carry `codex-local-evidence-requested`; neither should be
  treated as a completed repair.
- Hermes reported consuming both trusted evidence requests in one poll. The
  latest-main #134 is the only Issue that should be advanced after this fix.

## Next Recommended Action

Review and merge the structured-evidence repair PR. Then reapply `codex-fix` to
Issue #134 exactly once and monitor the resident Local Codex Worker.
