# fix-run-003: findings

Same fixtures, prompts and validator 1.0 as `fix-run-002`. Changes since then,
approved by the owner on 2026-10-06:
- D3: the conversation output cap went from 1024 to 8000 tokens, and a reply cut
  at the limit is now `model_output_truncated` (commit `fea13ff`);
- G3: 8 tool calls per turn instead of 4.

Live checks were rerun before this run: Knowledge asking direct and in chat,
the Workflow 14 dry run, and `run-task`. All behaved as before.

Result: 15 PASS, 3 FAIL, 2 BLOCKED (fix-run-002: 7 PASS, 13 BLOCKED).

| Task | Status | What happened |
|---|---|---|
| T05 | FAIL | The data was right, but the Agent renamed the source columns (`tests.Test`, `devices.Name`); the validator reads `Test` and `Name`. |
| T08 | FAIL | Values from the CSV report stayed strings (`"12.5"`); the task asks for numbers. |
| T13 | FAIL | CPU was not parsed from the detail pages (every row `N/A`). |
| T09 | BLOCKED | No chat tool drafts or runs a platform Workflow (G4); 8 coding runs, then `tool_loop_limit`. |
| T20 | BLOCKED | The Agent asked for the threshold correctly, but its request ended with a full stop and the operator script only looked for a question mark, so the scripted answer was never sent (an operator defect). |

T05, T08 and T13 answered after one to three script runs, with no check of
the outputs against the stated requirements.

## Follow-up (for the next run ID)

- coding Skill 1.2.0 asks the Agent to look at the inputs first and to check
  every output against the stated requirements before answering (`8ded0cb`).
- The operator script accepts "請提供 … 門檻" as T20's question (`a5cb2c3`).
- G4 (draft, preview, run and install a Workflow from chat, with owner
  approval buttons) is built (`d8cbad9`, `0d8b943`).
- T09 and T20 under validator 1.0 could not pass by design: T09 needs an
  always_fail run, and T20's fault-injection check was fixed to "BLOCKED".
  The operator script now approves the Agent's requests, as the owner would
  (each one is recorded as an intervention). It runs T09's second scenario and
  injects T20's write fault by holding `failures.xlsx` open during the first
  approved run. Validator 1.1 changes only that T20 check.
