# fix-run-006: findings

Setup:
- AEP at `16bc633`: D3/G3, G4, browser, desktop and runner tools, and coding Skill 1.3.0;
- validator 1.3;
- the same fixtures and prompts as the baseline.

Result: **20 PASS of 20.**

Human interventions, all recorded in each task's `result.json`:
- T09 (3): the operator pressed the owner's approve button twice, and asked for the second run in the always_fail scenario.
- T20 (3): the scripted threshold answer, given only after the Agent asked, and two approve-button presses.
- Every other task: none.

Evidence highlights:
- **T09.** The Agent drafted and ran a platform Workflow.
  - Success scenario: 3 logins and 1 `/data`; `data.json` matches.
  - always_fail scenario: 3 logins, 0 `/data`, and the reason was reported.
- **T13.** The delivered program requested the 500 page 3 times; the session total was also 3 this time.
- **T20.** The fault was injected: `failures.xlsx` was held open during the first approved run, and that run failed. The Agent fixed the Workflow and ran it again on the platform, and that run succeeded.

History: baseline 0/20, fix-run-002 7/20, fix-run-003 15/20, fix-run-004 16/20, fix-run-005 18/20, fix-run-006 20/20. One full pass is evidence the harness can do all 20; it is not a measured pass rate, because model runs vary (T12 and T13 changed between runs).
