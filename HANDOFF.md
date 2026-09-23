# Handoff — Phase 7 slice 3a, workflow 7 up to its plan

Updated: 2026-09-23 (Asia/Taipei).
Branch: `phase-7/weekly-report-plan`, ahead of `main` by this slice's commit.

Progress across every phase is in `docs/TASKS.md`. This file is only where
the current work stopped and how to resume it, and is rewritten each time.

## Goal

Migration step 5 is workflow 7, the GTM weekly report from Jira into the
team's workbook. This slice is everything up to the point where the workbook
is written: the week and its window, the Jira fetch, the reading of the
scratch sheet, and the plan — which is also the dry-run preview and the
evidence the parity gate names. Nothing in it writes a workbook, opens Excel
or touches Outlook.

Requirements: the "Slice 3a" section of `docs/phases/PHASE_7_MIGRATION.md`.
Contracts: `docs/CONTRACTS.md`, "Workflow 7: the weekly report up to its
plan". Source characterization and decisions: `docs/PHASE_7_MIGRATION.md`,
"Workflow 7".

## What this slice added

- `src/capabilities/weekly_report/` — `rules.py` (the source's pure rules,
  ported with its own tests as the oracle), `contracts.py`, `plan.py`
  (`resolve_window`, `build_plan`, `render_preview`), `handlers.py` (the four
  read capabilities and their specs), `manifest.py` (the `weekly` Skill, the
  `jira-weekly-report-preview` Workflow, `export_assets`).
- `src/integrations/jira.py` — `JiraConnection`, `JiraClient` over the
  platform's transport; `src/integrations/excel.py` — the `openpyxl` reader.
- `models.wire.MethodTransport` and `UrllibTransport.request`.
- `CompanyHostConfiguration.integrations` (`HostIntegrations`),
  `build_integrations`, `build_runtime(..., jira_transport=)`, the
  `integrations` doctor check, `aep-host export-assets`.
- `BridgeExecutor` validates step inputs strictly against JSON, so typed data
  (tuples, dates) can pass between steps.
- `openpyxl` in the `office` extra; `types-openpyxl` in `dev`.

## Verification

Run on Windows in `.venv` (Python 3.12) at the head of this branch:

- `python -m pytest -q -p no:cacheprovider` — **896 passed, 4 skipped**. Three
  skips need symbolic-link privileges and one needs an IPv6 loopback; all
  four run on Linux CI.
- `ruff check .` — clean. `ruff format --check .` — clean.
- `mypy` — no issues in 143 source files.
- `pip check` — no broken requirements. `python -m build` — both artifacts
  built. `git diff --check` — clean.

## Where this stopped

The work is complete and verified locally. Not yet done:

1. Open the pull request from `phase-7/weekly-report-plan` into `main`.
2. Run `/code-review` on it and apply the findings, as every earlier slice did.
3. Watch CI, then merge, and set the `3a` row in `docs/TASKS.md` to `done`
   with its pull request number.

## The decision the owner has to make before the next slice

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

## Next

Slice 3b, the writer, once the owner has chosen: the source's `_excel_upsert`
rules (used range, managed headers only, case-insensitive headers, hyperlink
formulas) carried forward; the reset, tint, border, recolour and rich-prepend
operations as a typed executor over the plan; staging and write-back; the
`after` digest beside the `before`; the parity evidence exported for the Phase
6 harness. Then the live comparison against the working old Host Bridge on
the company Bridge, which CI never claims.

## Open item for the owner

The pinned `telegram-local-agent` source's `config.yaml` commits a Telegram bot
token and a GitLab personal access token. Neither was copied into this
repository. Revoking them is an action in that repository, not this one.
