# fix-009: stopped partway (owner request)

Build `4becd6b`. Agent Web was restarted on it. Grader 1.2.

The owner asked to stop the tests that drive the GUI (Edge and the Expense desktop app) during working hours. Those tests now run only when the owner is away from the computer. The run was stopped while D02 was in progress. D02's folder is incomplete and has no result.

| Task | Status | Note |
|---|---|---|
| W01 | PASS | Its parameter rerun passes for the first time, with unchanged Workflow code. |
| W02, W03, W04 | PASS | |
| D01 | FAIL (rerun) | The new failure location worked. The Agent saw `desktop_control_missing: Refused at action 1 (set)` and `desktop_not_enabled: Refused at action 6 (invoke)`, then fixed the Workflow until a run succeeded (`fc8943b6`). Before the rerun it revised the Workflow once more (`263b2616`), so it fails "same code". This is the same Agent pattern as fix-008 W01. |
| D02 to X03, C01 to C04 | NOT_RUN | Stopped. |
