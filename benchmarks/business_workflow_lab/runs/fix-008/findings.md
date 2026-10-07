# fix-008: findings

Setup: AEP `1f413da`, which includes the `invalid_input` field locations, `authoring__get_workflow`, the "no filter named means none" prompt rule, and an Expense app restart before each task. Grader 1.2. Agent Web was restarted on this build before the run.

Result: **12 PASS of 16 runs**:
- W02, W03, W04;
- D02, D03, D04;
- C01 to C04;
- C04-force_exit2;
- **X01, for the first time**: all three interfaces, a correct workbook, and a parameter rerun with unchanged Workflow code.

| Task | Status | Cause | Follow-up |
|---|---|---|---|
| W01 | FAIL (rerun) | The first and rerun workbooks were both correct. The Agent installed 1.0.0. The next install, 1.0.1, failed with `workflow_version_exists`, so it installed and used 1.0.2. The rerun therefore used a digest that no first-phase run had used. The Workflow was revised, not reused. | Agent behaviour. There is no harness change; the "same workflow code" rule stays strict. |
| D01 | FAIL (rerun) | The workbook was correct. Every run of the platform Workflow failed with `desktop_dialog_missing`, because the step waited for an "Expense Viewer" dialog after Query that the app shows only on export. The Agent saw only the generic "Capability invocation did not complete", so it could not tell which action failed. It retried the same code three times, then revised the Workflow twice. | `CapabilityRefused` now takes an optional `where` built from the request's structure. The desktop handler reports `action N (kind)`, and the Bridge returns "Refused at action N (kind)". The helper's message, which can quote titles or values, still never travels. The desktop guide says to wait for a dialog only where a trial showed one. |
| X02 | FAIL | It asked first, as expected. It then missed invoice `0090000201` (dated 2026-08-06, due 2026-08-21, balance 47,947.50 TWD at 2026-09-30). The clarified rule asks for all invoices overdue and unpaid as of 2026-09-30, but the Agent kept only invoices dated in September. | This is the Agent's reading. The expected answer is unchanged. |
| X03 | FAIL | It asked instead of running. X01's Workflow takes `customer_id` and fixes the output name as `project_report_{customer_id}_{from}_{to}_TWD.xlsx`, so "only P003, output october_P003.xlsx" could not be done without a revision. The question was honest, and the operator does not answer X03. | X01's design decided this. The draft guide already says run values belong in file names, so nothing more is added here. |

## Operator note

The bypass scan matched `expense_app` inside `expense_approved_*.csv`, the export the Agent made through the GUI. That flagged D02 and X01 as "direct read of mock internals". The flag was a note only: a status fails only for `source.json` or `operator/` reads, so no status changed. The pattern is now `expense_app\b`.

## Regrade note (grader 1.3, 2026-10-07)

The trace shows the Agent bumped W01's version from 1.0.1 to 1.0.2 only because the install hit `workflow_version_exists`: a 1.0.1 of that name was left from an earlier lab run. It said it was "the same verified Workflow, re-versioned". The rerun then used installed 1.0.2 without any revision. Grader 1.3 (owner approved) accepts a version that was run *or installed* before the rerun request, as long as no draft follows the request. Under 1.3, W01 is PASS and this run is **13 PASS of 16**. The recorded results above stay as graded by 1.2.
