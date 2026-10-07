# fix-run-009: findings

Setup: AEP `d52b3c7`, with the tuned ask-first rule ("a request that names no filter means no filter"), field-level invalid-input messages and `authoring__get_workflow`. Validator 1.4.

Result: **19 PASS of 20**.

| Task | Status | Cause |
|---|---|---|
| T08 | FAIL | Values from the CSV report stayed strings. This is an Agent error; it passed in fix-run-004 to fix-run-008. |

No task asked a needless question.

Recent results on the current harness: fix-run-006 20/20, fix-run-007 20/20, fix-run-008 18/20 (one Agent error, one validator layout defect fixed in 1.4), fix-run-009 19/20. The remaining failures are scattered Agent errors (T08, T13), not a fixed gap.
