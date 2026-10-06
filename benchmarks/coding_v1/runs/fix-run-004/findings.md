# fix-run-004: findings

Changes since fix-run-003:
- coding Skill 1.2.0 (look at the inputs first, check the outputs);
- G4 conversational authoring with owner approval buttons;
- the operator approves the Agent's requests (each one is recorded as an intervention), runs T09's always_fail scenario, and injects T20's write fault;
- validator 1.1, which changes only T20's fault check.

Result: 16 PASS, 4 FAIL, 0 BLOCKED.

| Task | Status | Cause |
|---|---|---|
| T09 | FAIL | The Agent wrote `workflow.json` with `coding__run` and answered "已使用平台 runtime 實際執行", which is false: no authoring tool was used and no platform run exists. |
| T20 | FAIL | It drafted the Workflow and requested a run. The injected fault (`failures.xlsx` held open) failed the first approved run with `PermissionError`. The Agent then redid the work with `coding__run` instead of running the Workflow again. |
| T13 | FAIL | The failing detail page got 6 requests instead of 3: the page was requested again while exploring and verifying. |
| T12 | FAIL | The output was CSV and JSON with correct rows. The owner's T12 acceptance names rows and values, not a file format; validators 1.0 and 1.1 wrongly required `.xlsx` (operator defect). Checked under validator 1.2, the same output passes. |

## Follow-up (next run ID)

- coding 1.3.0 and the authoring tool texts (`f2cf3eb`):
  - a platform Workflow is drafted and run with the authoring tools, and never claimed from a file a script wrote;
  - a failed platform run is fixed and run again on the platform;
  - outputs are verified from the saved files, because a request limit set in the task counts for the whole conversation.
- Validator 1.2 for T12 (`42bfe23`).
