# fix-010: findings

**Setup.**
- Agent Web was restarted at 18:52 on `db38f28`. This is the final build of the stage: every fix of 2026-10-07, coding Skill 1.7.0, Knowledge Skill 1.5.0 and rs-knowledge 1.0.2.
- Grader 1.3.
- The run was made while the owner was away from the computer, under the GUI rule.

**Result: 14 PASS of 16**, the best so far:
- W01–W04;
- D01–D04;
- C01, C03, C04 and C04-force_exit2;
- X01;
- **X03, for the first time**.

**Reruns.** Every task with a parameter rerun (W01, D01, C01, X01) reran the installed Workflow unchanged, with 0 revisions after the request. Three changes made this possible:
- the draft guide and coding Skill 1.7.0, which say to run the installed version before calling it reusable;
- continued version numbers, so no `workflow_version_exists`;
- failure locations on desktop steps.

X03 reused X01's Workflow with new values and wrote `october_P003.xlsx`.

| Task | Status | Cause |
|---|---|---|
| C02 | FAIL | Agent variance against the template rules. It overwrote the `Summary!B2` formula with a label and wrote `N/A` for missing ProjectIDs, where the template's Instructions say missing values stay blank. It passed in every earlier run. |
| X02 | FAIL | The same reading as fix-008. It asked first and got the scripted rule, then missed invoice `0090000201`: dated 2026-08-06, due 2026-08-21, unpaid at 2026-09-30. The rule asks for every invoice overdue and unpaid as of 2026-09-30. The expected answer is unchanged. |

The desktop `save_as` anomaly seen in fix-009 D01 (an export written to an existing `tny.xlsx`) did not recur, and no output folder holds a stray file.
