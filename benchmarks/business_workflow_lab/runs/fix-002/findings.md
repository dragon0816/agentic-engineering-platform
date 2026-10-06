# fix-002: findings

Setup:
- AEP `27e4379`: 20 tool calls per turn, a tool record carried across turns, the operator replying 繼續 at the budget, and coding 1.3.0.
- Grader 1.1.

Result: **5 PASS of 16 runs** (fix-001: 4):
- **D01:** the Expense app driven through UI Automation, a correct workbook, and a rerun with E002/2026-08 on the same Workflow digest.
- **D02** and **D04**, including D04's injected export failure, retried.
- **C03.**
- **C04-force_exit2.**

| Cause | Tasks | Follow-up |
|---|---|---|
| Scripts fetched the SAP-like site with urllib; the browser tool was not used | W01 W02 W03 W04 X01 | The Agent knew only run-python as a Workflow step. The draft guide now shows browser/operate and desktop/operate as steps. desktop/operate fills `{placeholders}`. coding 1.4.0 and the tool texts say a system the person signs in to is never fetched by a script (`6340327`). |
| `desktop_app_not_allowed`: asked for `Expense`, registered `expense` | D03 | Names match regardless of case, and the tool text lists the apps (`1c68fe7`). |
| The rerun request dictated an output path the Workflow had no parameter for; the Agent rightly refused to change code | C01 | The operator now asks for new values only and grades the workbook the rerun wrote; the first result is kept aside (`a1e1990`). |
| Column widths changed; `N/A` written for a missing ProjectID | C02, C04, X02 | The templates' Instructions did not state these rules. They now say layout stays as is and missing values stay blank (`a1e1990`). |
| A reply with several tool calls ended the turn (`multiple_tool_calls_not_supported`) | X02 | The Gateway now runs each call in order (`a1e1990`). |
| No clarifying question; wrong rows included | X02 | This is the Agent's own error: the task tests whether it asks first. X02 used all three interfaces. |
| Runner had no `tzdata` (zoneinfo Asia/Taipei failed) | C01 (first run) | `tzdata` installed into the coding runner. |
