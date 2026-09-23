# Handoff — Phase 7, the workbook writer waits on an owner decision

Updated: 2026-09-23 (Asia/Taipei).
Branch: `main`, after PR #68 (slice 3a) merged with two review rounds applied.

Progress across every phase is in `docs/TASKS.md`. This file is only where
the current work stopped and how to resume it, and is rewritten each time.

## Where this stopped

Slice 3a is merged and nothing is in flight. Workflow 7, the GTM weekly
report, runs on a company host up to its plan: the week resolved, the Jira
issues fetched with their comment threads, the scratch sheet read without
Excel, and every row and cell operation decided and previewed. Nothing yet
writes the workbook. The next slice, 3b, is the writer, and it cannot start
until the owner has chosen how the workbook is written.

## The decision the owner has to make

**How the platform writes the workbook.** The pinned Host Bridge drives Excel
through COM on the Windows machine: it upserts rows, resets and applies fills
and borders, prepends a red rich-text block with a black tail, and writes
`=HYPERLINK()` formulas, staging the workbook to a local copy and writing it
back once. Two ways to carry that here:

- **COM on the company Bridge** (`pywin32`, Windows only, Excel installed).
  Faithful to the source, including per-character colour runs and every
  workbook feature Excel preserves. Cannot run in CI; tested through a fake
  the way the source tested it.
- **A library (`openpyxl`)**, portable and testable in CI, already reading
  the workbook. Rewriting a 75-sheet, hand-formatted, 1.1 MB workbook with it
  risks dropping what `openpyxl` does not model (charts, images, some
  formatting); rich-text runs survive only when loaded with `rich_text=True`.

The parity gate says only `weekly report temp` changes and the other sheets
remain unchanged; that is easy to claim with COM and has to be measured with
a library. Recommendation: COM for the writer, behind the same typed plan,
with `openpyxl` kept for reading and for the sheet digests before and after.

## What 3a settled, because 3b builds on it

- `WeeklyReportPlan` is the contract a writer executes: rows to upsert by
  key, new and updated keys, the blocks to prepend with their markers, the
  blocks already present that only need their colour back, the keys to
  tint, and the digest of the scratch sheet as it stood when the plan was
  made. A writer that finds a different digest is looking at a sheet that
  changed since planning.
- The source's `_excel_upsert` rules are carried forward for the writer, not
  ported yet: the last data row from the used range (hidden rows count),
  only managed headers written, case-insensitive header matching, the key
  as a `=HYPERLINK()` formula; and the job's own order of operations: reset
  last week's marks across the whole sheet, tint, border and pink the new
  rows, recolour the blocks already present, link every key, rich-prepend
  with `tailColor` black.
- A step's handler that raises `ValueError` fails the step as
  `invalid_input`; a Jira outage is `TransientCapabilityError`; every other
  failure fails the step and so the run, with no false success.
- The host's step cap is `capability_timeout_seconds` (600) and a caller's
  wait `workflow_wait_seconds` (900); a step that outlives the cap keeps its
  thread until it ends.

## How to verify

On Windows in `.venv` (Python 3.12), from the repository root:

```text
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe -m build
git diff --check
```

At this commit: 897 passed, 4 skipped, everything else clean. Three skips
need symbolic-link privileges and one an IPv6 loopback; all four run on
Linux CI, which runs the same chain on Windows and Ubuntu against Python 3.11
and 3.12. The weekly-report tests need the `office` extra (`openpyxl`).

## Next, once the owner has chosen

Slice 3b, the writer: a `weekly-report/apply` capability with a side effect
and an approval, executing the plan through the chosen writer behind a typed
executor the way the source's `sync_sheet` did, staging and write-back, the
`after` digest beside the `before`, the Workflow `jira-weekly-report` with the
apply step after the plan, and the parity evidence exported for the Phase 6
harness. Then the live comparison against the working old Host Bridge on
the company Bridge, which CI never claims. Then workflow 13, knowledge
parity, and controlled cutover.

## Open item for the owner

The pinned `telegram-local-agent` source's `config.yaml` commits a Telegram bot
token and a GitLab personal access token. Neither was copied into this
repository. Revoking them is an action in that repository, not this one.
