# fix-007: findings

Setup: AEP `befb1a3`, which adds the shared ask-first rule. Grader 1.2. coding_v1 on the same build passed 18/20 (fix-run-008).

Result: **12 PASS of 16 runs**:
- W02, W03, W04;
- D01, D02, D03;
- C01 to C04;
- C04-force_exit2.

| Task | Status | Cause | Follow-up |
|---|---|---|---|
| W01 | FAIL | The first result was correct. Every run of its platform Workflow failed at the browser step with a bare `invalid_input`, and the Agent could not see its own draft to fix it. | The Bridge now names the invalid fields and error kinds, never the values. `authoring__get_workflow` shows a draft's steps (`263e2c6`). |
| D04 | FAIL | It asked which status to include, because the desktop app still showed D03's Approved filter. | The prompt rule now says a request that names no filter means no filter, and a screen left from earlier use is not the person's choice (`7da8823`). The operator restarts the Expense app before each task (`d52b3c7`). |
| X01 | FAIL | It had the same Workflow problem as W01: all 7 platform runs failed. | Same as W01. |
| X02 | FAIL (environment) | **It asked first, correctly**: "需要關注的項目要用什麼規則標出？". After the scripted answer, it worked through all three interfaces until the model gateway returned `400 … The server had an error while processing your request`. | This is an upstream model service error, not an AEP defect. |
| X03 | BLOCKED | Depends on X01. | |
