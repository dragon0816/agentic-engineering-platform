# fix-run-008: findings

Setup: AEP `befb1a3`. The shared conversation prompt now has the ask-first rule (owner, 2026-10-07): when a request for work leaves open a rule that would change the result, ask that question first.

Result: **18 PASS of 20**. No task asked a needless question; the rule did not make clear tasks stall.

| Task | Status | Cause |
|---|---|---|
| T13 | FAIL | CPU was parsed wrongly from the detail pages. This is an Agent error; the task passed in fix-run-006 and fix-run-007. |
| T14 | FAIL (validator) | The Overall values were all correct (10000/7500/2500/0.75/5.5), laid out as name/value rows. The owner's acceptance names the values, not a layout. Validator 1.4 accepts name/value rows, and the self-test covers it. |
