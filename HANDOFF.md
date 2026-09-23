# Handoff — Phase 7, workflow 7 needs its run on a company workstation

Updated: 2026-09-23 (Asia/Taipei).
Branch: `phase-7/weekly-report-grants`, slice 3e committed and in review.

Progress across every phase is in `docs/TASKS.md`. This file is only where
the current work stopped and how to resume it, and is rewritten each time.

## Where this stopped

Workflow 7 is complete in code and the Windows preview bundle now carries it.
A company host can resolve the week, fetch the week's Jira issues with their
comment threads, read the scratch sheet without Excel, plan every row and cell
operation, and write that plan into the workbook through Excel. `weekly
preview` is the dry run and its own asset; `weekly apply` writes.

Slices 3c and 3d fixed the install, not the behaviour. **This platform is
published to no package index**, so every earlier instruction of the form
`pip install agentic-engineering-platform[...]` was impossible; the owner hit
exactly that on a company computer, against the corporate index. The offline
bundle is the supported install, it now carries the `excel` and `windows`
extras as wheels, the builder refuses a bundle missing one, and CI imports
them out of the installed bundle.

The owner's first download of that bundle then failed with a missing wheel,
because two of its files exceeded Windows' 260-character path limit where it
had been extracted and Explorer left them out in silence. Slice 3d shortens
the bundle and artefact names, refuses at build time any name that would not
survive the download, and makes the installer name the path limit instead of
reporting a missing file.

**What is left cannot be done from here.** Migration step 5 is a parity gate,
and its evidence comes from a real company workstation with Excel and Jira
credentials, compared against the working old Host Bridge. CI never claims
it, and this machine cannot produce it.

## The one thing only the owner can do next

`ExcelComWriter` has never been run: there is no Excel in CI and none on this
machine, so it is written to the documented COM object model and exercised
only through a recording writer — the same caveat the model adapters carry
(`docs/TASKS.md`, open items). To close step 5:

1. Install the offline bundle on the company workstation: take the
   `aep-windows-preview-*.zip` from the run's artefacts (or build it with
   `scripts/build_windows_preview.py`), extract it **somewhere short such as
   `C:\aep`** (Windows refuses a path of 260 characters or more and Explorer
   leaves out what will not fit), and run `install.cmd -Actor <your.id>`. It installs with `--no-index`
   from its own `wheels/`, so a company pip index is neither needed nor
   consulted, and no pip setting has to change. **The platform is not
   published to any package index**, so `pip install
   agentic-engineering-platform` cannot work and never could.
2. Configure `integrations.jira` and `integrations.weekly_report` in
   `host.json` (`deploy/windows-preview/README.md` has the shape), with
   `workbook_path` pointing at **a copy** of `SDE_Weekly_Report.xlsx`, and
   map the Jira token to an environment variable.
3. Write `workspace\membership.json` naming you as this device's bound
   member, and `workspace\grants.json` with all five grants exactly as
   `deploy/windows-preview/README.md` shows them. **Every grant needs an
   `approval_ref`, the four reads included**, or the run stops at the first
   step with `permission_denied`. Then `aep-host export-assets --out
   workspace\assets`.
4. `aep-host doctor --config host.json` — `host status` should be `ready` and
   the `integrations` check should say the site, the secret, the library and
   the workbook are all in place, and whether it can write.
5. `aep-host ask --config host.json "weekly.preview 2026_31W"`, read the
   plan, then `weekly.apply 2026_31W` against the copy. A failed run reports
   how many steps finished, which is where it stopped: none is the grants,
   one is Jira, two is the workbook.
6. Run the old Host Bridge's `jobs.jira_weekly_report` for the same week
   against a second copy and compare against the parity gate in
   `docs/phases/PHASE_7_MIGRATION.md`, "Workflow 7": the same Jira key set,
   only `weekly report temp` created or changed, rows upserted by key, a new
   ticket without marker content not added, blocks prepended once in red with
   the older text black, a repeat run duplicating nothing, and last week's
   marks retired.

The evidence is the run's own output: `WeeklyReportApplied` carries the
scratch sheet's digest before and after, the backup's path and every count,
and `evidence_lines(applied, plan)` renders what the gate reads. Whatever
that run finds comes back here as the next slice's requirements — expect the
COM adapter to need corrections, since nobody has run it.

## What to be ready for on that first run

- Every run retires last week's marks across the whole scratch sheet before
  making this week's, so a red `Comments` cell or a tinted `Key` cell applied
  by hand loses its colour — never its text. The member's own `Status`
  colours are left alone; only the job's own pink is cleared.
- Close the workbook first. A file Excel has open is refused before anything
  is copied.
- A plan is written only into the sheet it was made against: if somebody
  edits the scratch sheet between the preview and the apply, the run is
  refused (`sheet_changed`) rather than written.
- A run that does not finish leaves the real workbook exactly as it was and
  names the staged copy; `write_back_failed` means the report *was* written
  and only the copy back failed, so the staged file is the finished one.

## After step 5

Migration step 6, workflow 13 (`13_release_package.json` /
`release_package.py`): dry run first, then an isolated test repository, then
an explicitly approved non-production push. Then knowledge parity on a copy
(step 7), and the controlled cutover (step 9), which is also when the pinned
source repositories stop being the rollback baseline.

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

At this commit: 931 passed, 4 skipped, everything else clean. Three skips
need symbolic-link privileges and one an IPv6 loopback; all four run on Linux
CI, which runs the same chain on Windows and Ubuntu against Python 3.11 and
3.12. The weekly-report tests need a workbook reader (`openpyxl`, the `excel`
extra, which `office` also contains); none of them needs Excel or `pywin32`.

## Open items for the owner

- The leaked credentials in the pinned `telegram-local-agent` source were
  checked on 2026-09-23 and the finding is in `docs/TASKS.md`: the Telegram
  bot token is already dead and the GitLab one is for a local WSL2 Docker
  instance that is not running, so neither is live. This repository never
  carried either (`.scratch/` is gitignored). Revoking them is still the
  owner's to do: the Telegram token through @BotFather, the GitLab token in
  that instance once WSL2 is running. Both remain in that repository's
  history; scrubbing it would move the commit the Phase 7 rollback baseline
  is pinned to, so it belongs with the cutover.
- Whether a tool approval must come from a second person is an owner policy
  decision nobody has asked for.
- Taking somebody off a shared machine is still a host action, not a platform
  one (slice 2j).
