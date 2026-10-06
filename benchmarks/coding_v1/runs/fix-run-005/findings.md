# fix-run-005: findings

Setup: coding Skill 1.3.0, the authoring tool texts from `f2cf3eb`, and validator 1.2.

Result: 18 PASS, 2 FAIL. T20 passed for the first time, end to end:
- the Agent asked for the threshold;
- it drafted a platform Workflow and ran it after approval;
- the injected write fault (`failures.xlsx` held open) failed that run;
- the Agent fixed the Workflow and ran it again on the platform, and that run succeeded.

| Task | Status | Cause |
|---|---|---|
| T09 | FAIL | The Agent did the task correctly on the platform:
  - Success scenario: 3 logins, then `/data`, then `data.json` written.
  - always_fail scenario: 3 failed logins, then a stop with the reason reported.
  - It then removed the stale `data.json` at the start of that second run.
  
  The validator looked for `data.json` only after both scenarios, so it found none. This is an operator measurement defect. |
| T13 | FAIL | The 500 page was requested 6 times in the session. The delivered program ran twice, and each run tried the page exactly 3 times. The owner's acceptance, "500 頁請求 3 次", describes the program's retry behaviour. |

## Follow-up (validator 1.3, next run ID)

- **T09:** `data.json` is checked as the success scenario left it. The operator snapshots it before the always_fail run.
- **T13:** the requests are counted during the delivered program's final run, which is the last coding run that exited 0, timed from its run folder. The whole-session total is reported beside it.
  - Recomputed for this run: 3 in the final run, 6 in the session.
