# Workflow 11 source chart and Issue identity parity

Approved owner direction: use the proven `rs_workflow_system` Workflow 11 as
the visible-output baseline. This slice adapts its `jira_weekly_email.py`
composite chart to AEP's GitHub Project input while retaining the existing
Bridge authorization, Outlook-draft-only effect and Excel copyback policy.
The pinned source revision is
`896046e8fe2170d21f9213e56e5ce2f93c05ba43d`; the source tree stays
read-only. Strategy: **ADAPT** the source renderer at the chart boundary and
reuse AEP's already-tested `effort` data functions. AEP's hand-written pie is
kept for existing callers but is no longer the Workflow 11 mail image.

Acceptance criteria:

1. A Project Issue's `assignees` connection supplies both mail statistics and
   the workbook's Assignee cell. All Issue assignees are represented; an empty
   connection is Unassigned. The Project's free-text `SDE Assignee` cannot
   silently override the Issue connection. The row's Key hyperlink uses the
   Issue URL already returned by GitHub.
2. One inline PNG carries both the instrument pie and stacked per-member bars,
   as in the source. Labels show each instrument, count and share. Every
   comma-split Production value survives as its own slice and bar segment;
   there is no Other bucket. A source-matched sequential blue ramp drives
   both panels, extending within the blue family when there are more than
   seven instruments. The HTML totals remain readable if the image is blocked.
3. Mail generation requires the optional plotting dependency. The Windows
   offline preview ships every wheel needed for it and checks that set before
   packaging. The chart is generated headlessly without a display and no
   mail-send operation is introduced.
4. Characterization tests cover Issue-to-workbook mapping, URL preservation,
   multi-instrument/multi-assignee chart dimensions and series, coherent
   palette and closed offline bundle. Existing weekly report and bundle tests
   still pass. A live Outlook draft and saved workbook-copy comparison remain
   separate acceptance evidence, not implied by unit tests.
