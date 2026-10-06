# coding_v1 report — fix-run-005

Generated 2026-10-06T15:37:26+00:00 from `results.jsonl`.

Evidence per task: `T??/prompt.md`, `T??/trace.json`, `T??/result.json`, `T??/workspace/`. Rerun: `python benchmarks/coding_v1/run.py --run-id <new-id> --tasks all` (see README.md).

## Setup

- Repository commit: `a5457a795523a676a5142de1ac7637d39e75bfca`
- Entry point: Agent Web chat (`/api/conversations/turn`), one new session per task
- Model: {'alias': 'company', 'model': 'gpt-5.5', 'provider': 'openai_compatible'}
- Fixture manifest SHA-256: `a869d5fb693fc6b59d2be57c61b5337ef262ce6c512c06f3232e6ddf1633d633`; validator 1.2
- Budget: 600 s per task; tool calls bounded by the Gateway loop (4 per turn before commit fea13ff, 8 from it on: fix-run-003 and later)

## Results

| Task | Status | Tool calls | Script runs (exit codes) | Derived repair loops | Seconds | Interventions | Observed cause |
|---|---|---|---|---|---|---|---|
| T01 | PASS | 2 | [0, 0] | 0 | 24.0 | 0 |  |
| T02 | PASS | 2 | [0, 0] | 0 | 24.72 | 0 |  |
| T03 | PASS | 2 | [0, 0] | 0 | 36.19 | 0 |  |
| T04 | PASS | 2 | [0, 0] | 0 | 25.45 | 0 |  |
| T05 | PASS | 2 | [0, 0] | 0 | 29.91 | 0 |  |
| T06 | PASS | 2 | [0, 0] | 0 | 20.42 | 0 |  |
| T07 | PASS | 2 | [0, 0] | 0 | 27.28 | 0 |  |
| T08 | PASS | 2 | [0, 0] | 0 | 23.58 | 0 |  |
| T09 | FAIL | 8 | [0] | 0 | 128.74 | 3 | G1 no tool to read the workspace, write files or run code; the reply explained this and offered code for a person to run |
| T10 | PASS | 2 | [0, 0] | 0 | 23.53 | 0 |  |
| T11 | PASS | 3 | [0, 0, 0] | 0 | 49.31 | 0 |  |
| T12 | PASS | 2 | [0, 0] | 0 | 35.2 | 0 |  |
| T13 | FAIL | 3 | [0, 0, 0] | 0 | 61.48 | 0 | see trace |
| T14 | PASS | 2 | [0, 0] | 0 | 31.31 | 0 |  |
| T15 | PASS | 2 | [0, 0] | 0 | 21.31 | 0 |  |
| T16 | PASS | 2 | [0, 0] | 0 | 24.2 | 0 |  |
| T17 | PASS | 2 | [0, 0] | 0 | 33.47 | 0 |  |
| T18 | PASS | 2 | [0, 0] | 0 | 23.14 | 0 |  |
| T19 | PASS | 2 | [0, 0] | 0 | 32.58 | 0 |  |
| T20 | PASS | 8 | [0] | 0 | 137.45 | 3 |  |

## KPIs

- Status counts: {'PASS': 18, 'FAIL': 2, 'BLOCKED': 0, 'TIMEOUT': 0, 'NOT_RUN': 0}
- Main success rate PASS/20: 18/20
- PASS/(PASS+FAIL+TIMEOUT): 18/20
- Median duration: 28.6 s
- Median tool calls: 2.0
- First-attempt success (derived: PASS with no failing script run): 18/18
- Repair loops above are derived from script exit codes (a failing run followed by another run); `results.jsonl` keeps them null because the trace has no explicit edit events.

