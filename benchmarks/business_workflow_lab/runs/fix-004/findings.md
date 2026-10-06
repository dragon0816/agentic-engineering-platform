# fix-004: findings

Setup: AEP `9f335c2`, which adds the recovery for a leftover Edge, Telegram approvals and several tool calls per reply. Grader 1.1.

Result: **9 PASS of 16 runs**:
- W02 and W03, both in Edge;
- D02 and D04, on the WinForms app through UI Automation;
- C01, C02, C03 and C04, with a real CLI subprocess;
- C04-force_exit2.

| Task | Status | Cause |
|---|---|---|
| W01 | TIMEOUT | The first workbook was right early on. The Agent then revised its platform Workflow five times (1.0.0 to 1.0.5); one failure was a script whose newlines were written as literal `\n`. It also stopped to ask for an output file name on the rerun. 15 minutes ran out. |
| W04 | FAIL (grader) | The Agent was correct: the injected expiry happened and it signed in again. Grader 1.1 wanted two sign-ins, but the shared Edge was already signed in from W03. Grader 1.2 checks for a sign-in after the expiry, and the site now signs everybody out at each reset. |
| D01 | FAIL | The first run passed. On the rerun, the Workflow's desktop step met a message box left open by the previous run (`desktop_not_enabled`). Fix: `desktop/operate` gains `clear_dialogs`, and the guide says to start a step with it and end with every dialog closed. |
| D03 | FAIL (grader) | The data was right. The Summary group labels were "E001 陳怡君 …", and grader 1.1 wanted the cell to be exactly "E001". Grader 1.2 accepts a key inside a label; this output passes 1.2. |
| X01 | FAIL | It used all three interfaces and its numbers were right. It wrote its notes into the fixed label A9 instead of B9, which is an Agent error. A script also read the Tk app's source; this is noted, not counted as a data read. |
| X02 | FAIL | It again did not ask about the open rules, and included other projects' expenses and a cancelled order. coding 1.5.0 now asks the Agent to list the open rules and ask before assuming. |
| X03 | BLOCKED | Depends on X01. |

Operator changes for the next run:
- Grader 1.2.
- Every reset signs everybody out of the SAP-like site.
- A script that read the mocks' data (`operator/` or `source.json`) is FAIL, not only a note.
