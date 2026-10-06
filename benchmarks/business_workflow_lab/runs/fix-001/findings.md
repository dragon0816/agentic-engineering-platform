# fix-001: findings

Setup:
- AEP `0999b4a`: conversation output cap of 8000 tokens and 8 tool calls per turn; G4 authoring with approval buttons; the `browser__operate` (Edge) and `desktop__operate` (UI Automation) tools; run-python with child processes; coding Skill 1.3.0.
- Mocks 59/59 smoke checks, including Edge and the WinForms app through UI Automation.
- The SAP-like site signs in by SSO button.
- Grader 1.0. The run was reclassified after the classification fix: a tool that existed but was not used is FAIL, not BLOCKED.

Result: **4 PASS of 16 runs** (baseline-001: 0):
- **W03:** Edge, the template filled correctly.
- **C03 and C04:** the CLI ran as a real process from the runner.
- **C04-force_exit2:** the error was reported, and no false report was produced.

The other 12 runs: 11 FAIL and 1 BLOCKED (X03, which depends on X01).

## What stopped the rest

| Cause | Tasks | Notes |
|---|---|---|
| Tool budget (8 calls per turn) | W01 W02 W04 D01 D02 D04 X01 X02 | These tasks need exploring, then extraction, Excel, checking, drafting the Workflow and running it. The turn ends with `tool_loop_limit` before a workbook exists. |
| The next turn does not know what the last one did | all of the above | Agent Web keeps only each turn's text. After `tool_loop_limit` that text is the generic "I need more information …", so a follow-up turn starts without the tool results. |
| The rerun did not produce the second workbook | C01 | The first platform run succeeded, but the rerun with new values produced no `output/rerun` workbook. |
| Template column widths changed | D01 | The Agent auto-fitted the Details columns; the template fixes the widths. A real error. |
| Grader defect | C02 | Grader 1.0 required a per-currency Summary that C02 does not ask for. Grader 1.1 checks a grouped Summary only where the request asks for one. |
| App not operated | D03 | The desktop tool existed; the Agent did not use it this time. |

Bypass signals: X01 read `expense_app` source.

## Owner decisions needed before the next run

1. Raise the tool budget for long business tasks. All conversations share it.
2. Carry a summary of a turn's tool results into the conversation history, so a follow-up turn can continue.
