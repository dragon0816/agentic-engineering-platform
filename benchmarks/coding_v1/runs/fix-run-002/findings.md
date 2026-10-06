# fix-run-002 — findings

Same fixtures (manifest SHA-256 unchanged), prompts and validator 1.0 as
`baseline-run-001`. Changes since the baseline, all approved by the owner on
2026-10-06:
- G1: the conversation tool `coding__run` (Workflow `engineering/run-python`).
- D1: messages that name local work no longer go to the Knowledge intent route.
- A Skill selector can no longer narrow the tools to coding alone.
- The runner folder's leftover access entry was removed (D4, see
  `../fix-run-001/INVALID.md`).

Result: 7 PASS, 13 BLOCKED, 0 FAIL (baseline: 0 PASS, 20 BLOCKED). Every PASS
was produced by the Agent's own scripts in the restricted runner; the
validators re-checked the outputs, and for T18 they ran the fixed CLI
independently.

## Remaining defects and gaps

| Code | What happens | Evidence | Tasks |
|---|---|---|---|
| D3 | The conversation asks the model for at most 1024 output tokens. A tool call carrying a longer script is cut off (`finish_reason: length`, 1024 completion tokens), parses as neither text nor a tool call, and the turn fails with `empty_model_answer`. | Reproduced on the T03 prompt: cap 1024 → `length`, empty; cap 8000 → `coding__run` called and the turn answered. Same prompt, model and tools. | T03 T05 T06 T08 T10 T11 T12 T13 T14 T16 T17, and T20's second turn |
| G3 | The conversation loop allows 4 tool calls per turn; a task needing more exploration ends with `tool_loop_limit`. | T09: 4 runs, the last searching the AEP repository for a Workflow format, then `tool_loop_limit`. | T09 (T18 passed on its 4th call) |
| G4 | No chat tool installs or runs a drafted platform Workflow, so T09 and T20 cannot meet "a platform workflow ran in the AEP runtime". | All `aep_workflow_runs` empty. | T09 T20 |
| G5 | A script cannot start a subprocess (one-process Job object), so "run the CLI" happens in-process. | T18 runs 2 and 3: `WinError 1816`; run 4 imported and ran `main()` instead. | T18 (passed) |

## Observations

- T20 asked for the threshold before doing anything (the check passed), got
  the scripted answer once, then hit D3.
- T10 and T12 fetched the fixture pages over loopback successfully, then hit
  D3 while writing the workbook script.
- Security note: in T09 a script listed and read files in the AEP
  repository outside the task workspace (read access is an accepted residual
  risk of the runner; writes were confined).
- Knowledge asking, Workflow 14 dry run and `run-task` were checked live
  before this run and behaved as before (`docs/TASKS.md`).

## Next

Fixing D3 (raise the conversation output cap, and report `length` as its own
failure) changes every conversation turn, including Knowledge asking, so it
waits for the owner. A rerun after it gets a new run ID.
