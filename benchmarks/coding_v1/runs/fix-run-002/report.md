# coding_v1 report — fix-run-002

Generated 2026-10-06T12:28:52+00:00 from `results.jsonl`.

Evidence per task: `T??/prompt.md`, `T??/trace.json`, `T??/result.json`, `T??/workspace/`. Rerun: `python benchmarks/coding_v1/run.py --run-id <new-id> --tasks all` (see README.md).

## Setup

- Repository commit: `8442255c4d97d2109f4b43cc4e6f70967dfbbb61`
- Entry point: Agent Web chat (`/api/conversations/turn`), one new session per task
- Model: {'alias': 'company', 'model': 'gpt-5.5', 'provider': 'openai_compatible'}
- Fixture manifest SHA-256: `a869d5fb693fc6b59d2be57c61b5337ef262ce6c512c06f3232e6ddf1633d633`; validator 1.0
- Budget: 600 s per task; tool calls bounded by the Gateway loop (4 per turn)

## Results

| Task | Status | Tool calls | Script runs (exit codes) | Derived repair loops | Seconds | Interventions | Observed cause |
|---|---|---|---|---|---|---|---|
| T01 | PASS | 1 | [0] | 0 | 11.69 | 0 |  |
| T02 | PASS | 1 | [0] | 0 | 14.3 | 0 |  |
| T03 | BLOCKED | 0 |  |  | 8.41 | 0 | D3 the Gateway model returned an empty answer |
| T04 | PASS | 1 | [0] | 0 | 12.8 | 0 |  |
| T05 | BLOCKED | 0 |  |  | 10.62 | 0 | D3 the Gateway model returned an empty answer |
| T06 | BLOCKED | 0 |  |  | 8.61 | 0 | D3 the Gateway model returned an empty answer |
| T07 | PASS | 2 | [0, 0] | 0 | 19.3 | 0 |  |
| T08 | BLOCKED | 0 |  |  | 11.73 | 0 | D3 the Gateway model returned an empty answer |
| T09 | BLOCKED | 4 | [0, 0, 0, 1] | 0 | 29.28 | 0 | G3 the conversation loop's tool budget (4 calls per turn) ended the turn |
| T10 | BLOCKED | 1 | [0] | 0 | 14.59 | 0 | D3 the Gateway model returned an empty answer |
| T11 | BLOCKED | 0 |  |  | 8.22 | 0 | D3 the Gateway model returned an empty answer |
| T12 | BLOCKED | 1 | [0] | 0 | 17.41 | 0 | D3 the Gateway model returned an empty answer |
| T13 | BLOCKED | 0 |  |  | 10.8 | 0 | D3 the Gateway model returned an empty answer |
| T14 | BLOCKED | 0 |  |  | 8.16 | 0 | D3 the Gateway model returned an empty answer |
| T15 | PASS | 1 | [0] | 0 | 12.33 | 0 |  |
| T16 | BLOCKED | 0 |  |  | 8.81 | 0 | D3 the Gateway model returned an empty answer |
| T17 | BLOCKED | 0 |  |  | 10.66 | 0 | D3 the Gateway model returned an empty answer |
| T18 | PASS | 4 | [0, 1, 1, 0] | 2 | 35.62 | 0 |  |
| T19 | PASS | 1 | [0] | 0 | 11.95 | 0 |  |
| T20 | BLOCKED | 2 | [0, 0] | 0 | 23.98 | 1 | D3 the Gateway model returned an empty answer |

## KPIs

- Status counts: {'PASS': 7, 'FAIL': 0, 'BLOCKED': 13, 'TIMEOUT': 0, 'NOT_RUN': 0}
- Main success rate PASS/20: 7/20
- PASS/(PASS+FAIL+TIMEOUT): 7/7
- Median duration: 11.8 s
- Median tool calls: 1.0
- First-attempt success (derived: PASS with no failing script run): 6/7
- Repair loops above are derived from script exit codes (a failing run followed by another run); `results.jsonl` keeps them null because the trace has no explicit edit events.

