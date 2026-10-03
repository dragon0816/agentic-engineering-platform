# Handoff

Date: 2026-10-03 (Asia/Taipei). Branch: `main`. This is a local checkpoint for
the owner's Agent, Workflow and Knowledge program. The repository was not
pushed. Source repositories and the original `RS_Knowledge` tree were not
modified. The owner previously authorized local per-slice merges; the current
implementation commits are on `main`.

## Goal and owner decisions

- Preserve original `rs_workflow_system` behavior as the migration baseline;
  record and test any user-visible adaptation (see `docs/CONTRACTS.md`).
- Workflow 11 uses the GitHub Project. Workflow 7 uses company Jira at
  `https://jira.rsint.net/`, project `MRT1CV`. The owner will grant that
  project Browse permission. Do not substitute GitHub for Workflow 7.
- The entire queryable `RS_Knowledge` corpus may be staged for the approved
  internal Gateway. Keep the source unchanged and Ground answers in Raw
  evidence. The approved default Gateway is `http://127.0.0.1:4000/v1`.
- Agent scheduling is requested, but only the inert foundation is implemented;
  no schedule should execute until worker/admission/approval and controls exist.

## Completed and verified

- Workflow 7's first read-only preview uses the source Jira adapter and exact
  `/run 7` asset (`66a5680`). A fresh Windows User `AEP_JIRA_TOKEN` now
  authenticates: `/rest/api/2/myself` returned HTTP 200. `MRT1CV` returns
  HTTP 404 until project access is granted; live preview is pending.
- Local schedules have typed exact-version Workflow/Agent Task targets,
  timezone-aware daily/weekly recurrence, SQLite persistence and atomic due
  claims (`8092949`). No worker, recovery, Agent Web/CLI control or automatic
  execution exists yet.
- Workflow 11 statistics use GitHub Issue Assignees for member grouping and
  split comma-separated GitHub Project Production values into individual
  instruments; the chart no longer collapses them into `Other` (`9d8e82d`).
  A live Project read confirmed Issue assignees and a comma-separated
  Production value. The Outlook draft mail Workflow was run through the
  installed Agent: three steps succeeded. Its saved draft was verified in
  Drafts, unsent, with the expected subject, one To, eight CC, a chart image
  and no `Other` aggregate. No send operation was invoked. Diagnostic runs may
  have created more than one unsent draft for `2026_40W`; reconcile them with
  the owner's reference before deleting any.
- Workflow 11 Excel apply was run twice for `2026_40W`: first to apply the
  corrected Comments and Status formatting, then after fixing colour sorting
  around hidden rows (`6810555`). The real workbook is
  `C:\Users\Chi_L\OneDrive - Rohde & Schwarz\Stuff\Report\SDE_Weekly_Report.xlsx`.
  Workflow backups were created beside it, and an additional pre-apply copy
  is in ignored `.scratch/workflow11-redesign/`. Saved-workbook inspection
  confirmed 22 highlighted Key rows contiguous at rows 2–23, all 22 current
  Comments blocks red with older text black, all 19 highlighted `In Progress`
  cells `#F8AD3E`, and all 241 Comments cells aligned top-left. Untouched
  historical Status fills are preserved. The hidden-row sort was first proven
  on an isolated Excel copy; the original hidden-record multiset, AutoFilter
  range and column count were retained.
- The owner-authorized Knowledge corpus was staged at
  `C:\Users\Chi_L\AppData\Local\AEP\rs-k` with exact digests; 560 Raw files
  and 2007 Wiki pages are queryable, while 673 Drop originals were not copied.
  A private `engineering/rs-knowledge@1.0.0` manifest, Knowledge Skill,
  binding, grant and profile authorization were installed in the Host. Source
  Vault remains untouched. Host model credential plumbing was fixed
  (`956b9b5`) and citation validation now accepts a citation after sentence
  punctuation (`d66b78b`). Installed Agent asking answered a narrow CMX500
  version question with “CSW 9.20.0 and higher” and one Raw citation.
  Broad market mapping still needs retrieval and grounding quality work;
  unsupported answers return an insufficient-evidence state.
- The Host wheel was rebuilt and installed locally. Agent Web is running on
  `http://127.0.0.1:53582/`. This bare route intentionally returns 401 without
  the session token; the authenticated UI is reached via the launcher.
- `scripts/set-jira-token.ps1` is an interactive helper that prompts for a
  secure PAT and stores `AEP_JIRA_TOKEN` for the Windows User. It contains no
  token value. The owner's one-line `Read-Host` command already worked.

## Verification

- The relevant Excel adapter and apply tests: 38 passed, one deliberately
  deselected machine-absence test. Ruff across `src` and `tests` passed;
  mypy passed for 300 source files. A wheel build succeeded.
- Full non-browser suite: 1605 passed, four skipped, two deselected; one
  unrelated loopback transport case failed once with Windows socket abort and
  passed immediately in isolation. The unrestricted full run had 1618 passed,
  four skipped, one deselected and ten Chromium browser-CDP connection failures
  on this machine. Do not describe the unrestricted suite as green.
- An isolated real-Excel copy demonstrated 22 highlighted rows at the top
  while retaining each hidden record and the original AutoFilter range.
  The actual saved workbook and Outlook draft were checked read-only afterward.

## Next work

1. After the owner grants Jira `MRT1CV` Browse access, run the exact Workflow
   7 read-only preview with the User PAT and compare source-derived fixtures.
   Excel write parity is a separate slice.
2. Evaluate the broad `RS_Knowledge` product/option question with source
   evidence and improve retrieval or curation only where supported. Convert,
   ingest and lint integration tests still need a complete user-level pass.
3. Complete Workflow 11 visual draft comparison against the owner's reference,
   then decide what to do with extra diagnostic drafts. Keep send permission
   separate from draft permission.
4. Implement the schedule worker with claim reconciliation, exact installed
   Task/Workflow admission, Bridge grants, approval checks, history and user
   controls. No scheduler may run before those protections exist.
5. Continue default Marketplace asset review and broader Agent evaluations
   (SOP-to-Workflow and natural-language Skill selection). Update
   `docs/TASKS.md` as these slices land.

Key references: `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/TASKS.md`,
`docs/DECISIONS.md`, `docs/CONTRACTS.md`,
`docs/WORKFLOW_7_SOURCE_CONTRACT.md`, and
`docs/MARKETPLACE_DEFAULTS_SOURCE_AUDIT_2026-10-03.md`.
