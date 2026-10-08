# authoring_v1

Can a connected coding agent (Claude Code, Codex, GitHub Copilot) build Skills and
Workflows this AEP Host can use? (owner 2026-10-08, `docs/phases/EXTERNAL_AUTHORING.md`)

Each agent works headless in its own project folder that holds only what
`aep-host assets connect` installs: the `aep-workflow-creator` and `aep-skill-creator`
skills and the `aep` MCP server. Every agent gets its own sandbox Host, a copy of the
live `host.json` whose workspace lies under the run. Nothing installs on the live Host.

| Task | What the agent builds | How it is checked |
|---|---|---|
| W1 | `csv-category-totals`: a CSV file in, totals per category out (coding/run-python) | The installed file is run with a hidden CSV and its output is compared |
| W2 | `sales-window-summary`: date and integer parameters, JSON out | The installed file is run with hidden dates and threshold, then compared |
| S1 | `csv-totals` Skill with a command bound to the installed W1 | Loads beside every installed Skill, targets W1's installed version, and its instructions ask for the inputs |

The prompts are PUBLIC and synthetic. The agent sees statuses and codes, never run data.
The runner acts as the owner: it approves each run or install the agent submitted, logging
each one to `runs/<id>/<agent>/approvals.jsonl`. It never writes assets for the agent.

```
.venv\Scripts\python.exe benchmarks\authoring_v1\run.py --run-id r001 --agents claude-code
.venv\Scripts\python.exe benchmarks\authoring_v1\run.py --run-id r002 --agents codex,copilot
```

`PASS` means every check passed. `FAIL` means some check failed. `TIMEOUT` means the
session ran over 25 minutes. `NOT_RUN` means the agent's CLI is not installed.
Results are in `runs/<id>/results.jsonl`, and transcripts in
`runs/<id>/<agent>/tasks/<task>/transcript.txt`.
