# coding_v1 report — fix-run-016

Generated 2026-10-09T06:54:51+00:00 from `results.jsonl`.

Evidence per task: `T??/prompt.md`, `T??/trace.json`, `T??/result.json`, `T??/workspace/`. Rerun: `python benchmarks/coding_v1/run.py --run-id <new-id> --tasks all` (see README.md).

## Setup

- Repository commit: `b363f500e8166f35a1715d99e501c8ed701fcc95`
- Entry point: Agent Web chat (`/api/conversations/turn`), one new session per task
- Model: {'alias': 'company', 'model': 'gpt-5.5', 'provider': 'openai_compatible'}
- Fixture manifest SHA-256: `a869d5fb693fc6b59d2be57c61b5337ef262ce6c512c06f3232e6ddf1633d633`; validator 1.4
- Budget: 600 s per task; tool calls bounded by the Gateway loop (4 per turn before commit fea13ff, 8 from it on: fix-run-003 and later)

## Results

| Task | Status | Tool calls | Script runs (exit codes) | Derived repair loops | Seconds | Interventions | Observed cause |
|---|---|---|---|---|---|---|---|
| T01 | PASS | 2 | [0, 0] | 0 | 27.31 | 0 |  |
| T02 | PASS | 3 | [0, 1, 0] | 1 | 54.49 | 0 |  |
| T03 | PASS | 2 | [0, 0] | 0 | 42.45 | 0 |  |
| T04 | PASS | 2 | [0, 0] | 0 | 34.91 | 0 |  |
| T05 | PASS | 2 | [0, 0] | 0 | 39.26 | 0 |  |
| T06 | PASS | 2 | [0, 0] | 0 | 24.83 | 0 |  |
| T07 | PASS | 2 | [0, 0] | 0 | 29.72 | 0 |  |
| T08 | PASS | 2 | [0, 0] | 0 | 50.75 | 0 |  |
| T09 | PASS | 12 | [0, 0, 1, 1, 0] | 2 | 226.56 | 3 |  |
| T10 | PASS | 2 | [0, 0] | 0 | 29.38 | 0 |  |
| T11 | PASS | 3 | [0, 0, 0] | 0 | 63.58 | 0 |  |
| T12 | PASS | 2 | [0, 0] | 0 | 41.0 | 0 |  |
| T13 | PASS | 2 | [0, 0] | 0 | 71.75 | 0 |  |
| T14 | PASS | 2 | [0, 0] | 0 | 39.17 | 0 |  |
| T15 | PASS | 2 | [0, 0] | 0 | 27.39 | 0 |  |
| T16 | PASS | 3 | [0, 0, 0] | 0 | 40.45 | 0 |  |
| T17 | PASS | 2 | [0, 0] | 0 | 32.48 | 0 |  |
| T18 | PASS | 2 | [0, 0] | 0 | 35.14 | 0 |  |
| T19 | PASS | 2 | [0, 0] | 0 | 31.77 | 0 |  |
| T20 | PASS | 13 | [0, 0, 0, 0] | 0 | 180.05 | 3 |  |

## KPIs

- Status counts: {'PASS': 20, 'FAIL': 0, 'BLOCKED': 0, 'TIMEOUT': 0, 'NOT_RUN': 0}
- Main success rate PASS/20: 20/20
- PASS/(PASS+FAIL+TIMEOUT): 20/20
- Median duration: 39.2 s
- Median tool calls: 2.0
- First-attempt success (derived: PASS with no failing script run): 18/20
- Repair loops above are derived from script exit codes (a failing run followed by another run); `results.jsonl` keeps them null because the trace has no explicit edit events.

