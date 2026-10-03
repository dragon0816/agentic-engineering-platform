# Handoff

Date: 2026-10-03 (Asia/Taipei). Branch: `main`. Local commits:
`ede8bc0` (schedule CLI), `b4f23a4` (private Marketplace candidate), and
`1a3c1ad` (Workflow 10/13 migration). The source repositories, real release
checkout, and production Excel workbook were not changed in this slice. No
push was made. `docs/TASKS.md` is the cumulative progress record.

## Current owner direction

- Pause Workflow 7. The Windows User `AEP_JIRA_TOKEN` authenticates to Jira
  (`/rest/api/2/myself` was HTTP 200), but `MRT1CV` returned 404. This is a
  Project-access question, not a missing-token question. The owner asked to
  migrate Workflows 10 and 13 first.
- Use original `dragon0816/rs_workflow_system` behavior as the migration
  baseline. The source was pinned read-only at
  `896046e8fe2170d21f9213e56e5ce2f93c05ba43d`; no source file was edited.
- The owner previously requested parallel independent slices. The local
  schedule control and private Marketplace-candidate slices are present, but
  neither starts an unattended job nor publishes an asset.

## Implemented in this checkpoint

- Workflow 10: static Host source/target/rules configuration; installed
  `/run 10` read-only preview and `chipset` Skill; source-order transformation
  with source/drop/count/digest evidence; a separate exact write Workflow;
  guarded staged Excel COM temp-sheet replacement with backup, stale-plan,
  open-workbook, other-sheet and VBA checks; source snapshot baseline commits
  only after verified copyback. Agent/Bridge tests cover denied and approved
  execution. See `docs/WORKFLOW_10_HOST.md` and `docs/CONTRACTS.md`.
- Workflow 13: pinned source characterization and pure release-file planning;
  installed `/run 13` read-only preview; separate no-alias isolated preparation
  Workflow enabled only by explicit Host settings. The latter requires an
  exact write grant and approval, a marked allowed root and a no-remote Git
  checkout. It does not run Git, commit, push or network calls. See
  `docs/WORKFLOW_13_SOURCE_CONTRACT.md`.
- Manual `aep-host schedules --config ...` create/list/pause/resume/history
  controls for saved exact Workflow schedules. They do not auto-start a worker
  or grant execution. Agent Task scheduling still requires trusted templates.
- One Workflow 11 preview Marketplace candidate is staged as a private draft.
  It is not published, installed or authorized. Hermes Skills remain pending
  source pinning and licensing review.
- Updated stale asset-export assertions and made the Excel-absence and
  PowerShell-output tests independent of host installation and cp950 locale.

## Verification and limits

- Workflow 10/13/schedule/Marketplace focused selection: 221 passed, one
  directory-symlink case skipped. After the W13 Host integration, its focused
  selection: 27 passed, one skipped. Ruff passed; strict mypy passed on 325
  source and test files; offline wheel built in `.scratch/wheel-final`.
- Broad non-browser run outside the filesystem sandbox: 1,690 passed, five
  platform skips, one deselected (`tests/test_browser.py` ignored, the real
  Agent Web browser case deselected). Two earlier sandboxed runs each had one
  unrelated, transient Windows directory-rename permission error; both cases
  passed immediately in isolation. Unrestricted Chromium/CDP tests fail on
  this host because the browser connection closes; do not call the
  unrestricted suite green.
- Workflow 10 real parity is open. The actual FY source workbooks and team
  `chipset-map.json` were unavailable. Excel opened a synthetic workbook as
  read-only in this sandbox, so real COM write/copyback against a workbook
  copy was not verified. Do not apply to the production macro workbook yet.
- Workflow 13 full parity is open: published-version/readiness lookup,
  upload transfer, branch/template creation, queued serialization, Git status,
  commit and push remain separate governed steps. No real release happened.
- The owner was asked asynchronously for Workflow 10 source/rules/target paths
  and Workflow 13 release checkout/inbox paths. Await these before real-file
  parity; do not invent paths.
- Workflow 11 Outlook draft visual parity and robust broad RS Knowledge
  grounding remain separate open tasks in `docs/TASKS.md`. The previous
  handoff's live Workflow 11/Knowledge evidence is preserved in that progress
  record and the source-specific docs.

## Next sequence

1. With owner-provided files, compare Workflow 10 preview and staged Excel
   output with the pinned source job on a disposable workbook copy. Then do a
   company-host Workflow 13 read-only preview and isolated source comparison.
2. Only after parity and explicit release policy work, implement Workflow 13
   remote dependency and commit/push steps. Keep Workflow 7 paused until the
   owner reopens it.
