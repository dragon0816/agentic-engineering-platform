# fix-005: findings

Setup:
- AEP `1c5d54d`: `clear_dialogs`, coding 1.5.0 (ask about open rules), a fresh SAP sign-in per task, and a data bypass counted as FAIL.
- Grader 1.2.

Result: **11 PASS of 16 runs** (fix-004: 9):
- W02, W03 and W04; W04 met the injected expiry and signed in again;
- D01, including its rerun through the same Workflow with E002/2026-08; D02; D03;
- C01 to C04;
- C04-force_exit2.

| Task | Status | Cause | Follow-up |
|---|---|---|---|
| W01 | FAIL | It built its own "Sales Orders Report" workbook instead of filling `sales_template.xlsx`. On the rerun it stopped to ask for an output file name. | coding 1.6.0 says to fill a copy of a given template, never a look-alike (`f82e593`). The rerun request leaves the output name to the Agent (`839b958`). |
| D04 | FAIL | `model_output_truncated`: one reply passed 8000 tokens and ended the turn. | The Gateway now retries a cut reply twice within the turn, with a notice to answer more briefly (`f69ee2c`). |
| X01 | FAIL | All three interfaces were used, and the numbers and the rerun were right. It listed its three sources one per row, overwriting the fixed label A9; the template says to separate sources with `;` in B7/D7. | coding 1.6.0: follow the template's instructions. |
| X02 | FAIL | All three interfaces were used, but it did not ask about the open rules. It included other projects' expenses and the cancelled order. | coding 1.5.0's "ask first" did not change this. A stronger rule belongs in the shared system prompt, which also governs Knowledge asking, so it waits for the owner. |
| X03 | BLOCKED | Depends on X01. | |

Interventions: approval presses, 繼續 replies and rerun requests, each recorded per task.
