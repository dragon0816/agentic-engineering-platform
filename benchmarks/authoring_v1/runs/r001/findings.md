# authoring_v1 r001 (2026-10-08, build 059f54c)

| Agent | W1 | W2 | S1 |
|---|---|---|---|
| Claude Code 2.1.263 | PASS (279 s, 28 turns, $1.74) | PASS (233 s, 25 turns, $1.81) | PASS |
| Codex | NOT_RUN: CLI not installed | NOT_RUN | NOT_RUN |
| Copilot | NOT_RUN: CLI not installed | NOT_RUN | NOT_RUN |

## What Claude Code did

Claude Code worked headless with only the creator skills and the `aep` MCP server, and
completed each task through MCP in this order:

1. catalog;
2. check;
3. submit;
4. one test run (it waited, polling `aep_status`, while the operator approved);
5. install request.

Both Workflows passed the first test run. Each installed Workflow was then run from its
installed file with hidden values and produced exactly the expected output. W1's
script rounds half up with `Decimal`.

The S1 Skill:

- binds `totals` to `engineering/csv-category-totals@1.0.0` and makes it the default command;
- has instructions that ask for `input_file` and `output_name`, never guess a value,
  wait for the approval, report the output file, and never state a total the run did not
  return;
- loads beside the 11 other installed Skills.

## Runner faults found and fixed (no effect on the agent's work)

- **S1 transcript lost.** S1 had no inputs to prepare, so its folder did not exist and
  writing the transcript failed after the session. S1 was graded afterwards with
  `--grade-only`. The runner now always creates the folder.
- **Ambiguous rounding in W1's grader.** The hidden CSV includes `1.005`, and the grader
  totalled with floats. It now uses `Decimal` half-up, as two-decimal money is
  usually rounded. The agent's output is identical under both.

## Not yet shown

- Codex and Copilot: install the CLIs and sign in, then run
  `run.py --run-id r002 --agents codex,copilot`.
- A Skill authored outside AEP, used by the resident Agent in a conversation. The host
  loads Skills at start, so that needs a restart of a host that has it installed.
