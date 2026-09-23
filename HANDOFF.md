# Handoff — Phase 7 slice 3b, writing the weekly report

Updated: 2026-09-23 (Asia/Taipei).
Branch: `phase-7/weekly-report-writer`, ahead of `main` by this slice's work.

Progress across every phase is in `docs/TASKS.md`. This file is only where
the current work stopped and how to resume it, and is rewritten each time.

## Goal

Slice 3a stopped at the plan. This is the other half: executing it against
the team's workbook, with the parity gate's evidence on both sides of the
write.

Requirements: the "Slice 3b" section of `docs/phases/PHASE_7_MIGRATION.md`.
Contracts: `docs/CONTRACTS.md`, "Workflow 7: writing the plan into the
workbook". Source characterization and decisions: `docs/PHASE_7_MIGRATION.md`,
"Workflow 7".

## The decision that was taken, and by whom

The owner was given both options and a recommendation, and asked for the
slice to be finished. **Excel through COM on the company workstation** is
what the writer does, recorded as a delegated owner decision in
`docs/TASKS.md`. It is reversible: the executor writes through a
`WorkbookWriter` protocol and knows nothing about COM, so another adapter
replaces it and nothing else changes.

## What this slice added

- `src/integrations/excel_writer.py` — the typed operations, the
  `WorkbookWriter` protocol, the staging helpers, and `ExcelComWriter`.
- `src/capabilities/weekly_report/apply.py` — the ordered executor and
  `evidence_lines`.
- `WeeklyReportApplied` and `FailedComment`; `WeeklyReportPlan` gained
  `scratch_present`, `seed_sheet`, `browse_base`; settings gained
  `local_staging`.
- `APPLY_SPEC` / `ApplyHandler`, the `engineering/jira-weekly-report`
  Workflow, and `weekly apply` on the Skill.
- `capabilities.runtime.CapabilityRefused` — a handler may now name its own
  refusal, and `BridgeExecutor` puts that code on the failed step.
- `pywin32` in a new `windows` extra.

## Verification

Run on Windows in `.venv` (Python 3.12) at the head of this branch:

- `python -m pytest -q -p no:cacheprovider` — **913 passed, 4 skipped**. Three
  skips need symbolic-link privileges and one needs an IPv6 loopback; all
  four run on Linux CI.
- `ruff check .` — clean. `ruff format --check .` — clean.
- `mypy` — no issues in 147 source files.
- `pip check` — no broken requirements. `python -m build` — both artifacts
  built. `git diff --check` — clean.

## Where this stopped

The work is complete and verified locally. Not yet done:

1. Open the pull request from `phase-7/weekly-report-writer` into `main`.
2. Run `/code-review` on it and apply the findings, as every earlier slice did.
3. Watch CI, then merge, and set the `3b` row in `docs/TASKS.md` to `done`
   with its pull request number.

## The one thing only the owner can do next

**`ExcelComWriter` has never been run.** There is no Excel in CI and none on
this machine, so it is written to the documented COM object model and
exercised only through a recording writer — exactly as the pinned source's
own tests exercised its Bridge, and the same caveat the model adapters carry
(`docs/TASKS.md`, open items). Migration step 5's parity evidence needs a
company workstation with Excel and Jira credentials:

1. Install with `pip install "agentic-engineering-platform[office,windows]"`.
2. Configure `integrations.jira` and `integrations.weekly_report` in
   `host.json` (`deploy/windows-preview/README.md` has the shape), pointing
   `workbook_path` at **a copy** of `SDE_Weekly_Report.xlsx`.
3. `aep-host ask --config host.json "weekly.preview 2026_31W"` and read the
   plan; then `weekly.apply` against the copy.
4. Run the old Host Bridge's `jobs.jira_weekly_report` for the same week
   against another copy, and compare against the parity gate in
   `docs/phases/PHASE_7_MIGRATION.md`: the same Jira key set, only
   `weekly report temp` changed, rows upserted by key, blocks prepended once
   in red with the older text black, a repeat run duplicating nothing, and
   the marks retired.
5. The evidence is in the run's own output: `WeeklyReportApplied` carries the
   digests before and after, the backup's path and every count;
   `evidence_lines(applied, plan)` renders what the gate reads.

Whatever that run finds comes back here as the next slice's requirements.

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

The weekly-report tests need the `office` extra (`openpyxl`); none of them
needs Excel.

## Open items for the owner

- The leaked credentials in the pinned `telegram-local-agent` source were
  checked on 2026-09-23 and the finding is recorded in `docs/TASKS.md`: the
  Telegram bot token is already dead, and the GitLab one is for a local WSL2
  Docker instance that is not running. Neither is live, and this repository
  never carried either. What remains is that both sit in that repository's
  history; scrubbing it would move the commit the Phase 7 rollback baseline
  is pinned to, so it belongs with the cutover.
- Whether a tool approval must come from a second person is still an owner
  policy decision nobody has asked for (`docs/TASKS.md`, open items).
