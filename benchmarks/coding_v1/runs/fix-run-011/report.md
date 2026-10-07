# coding_v1 report — fix-run-011

Generated 2026-10-07T05:47:37+00:00 from `results.jsonl`.

Evidence per task: `T??/prompt.md`, `T??/trace.json`, `T??/result.json`, `T??/workspace/`. Rerun: `python benchmarks/coding_v1/run.py --run-id <new-id> --tasks all` (see README.md).

## Setup

- Repository commit: `fa09c03d5d8cfe9866cc3c191bb45a07030c3e96`
- Entry point: Agent Web chat (`/api/conversations/turn`), one new session per task
- Model: {'alias': 'company', 'model': 'gpt-5.5', 'provider': 'openai_compatible'}
- Fixture manifest SHA-256: `a869d5fb693fc6b59d2be57c61b5337ef262ce6c512c06f3232e6ddf1633d633`; validator 1.4
- Budget: 600 s per task; tool calls bounded by the Gateway loop (4 per turn before commit fea13ff, 8 from it on: fix-run-003 and later)

## Results

| Task | Status | Tool calls | Script runs (exit codes) | Derived repair loops | Seconds | Interventions | Observed cause |
|---|---|---|---|---|---|---|---|
| T01 | PASS | 2 | [0, 0] | 0 | 23.16 | 0 |  |
| T02 | PASS | 2 | [0, 0] | 0 | 22.11 | 0 |  |
| T03 | PASS | 2 | [0, 0] | 0 | 33.09 | 0 |  |
| T04 | PASS | 2 | [0, 0] | 0 | 26.52 | 0 |  |
| T05 | PASS | 2 | [0, 0] | 0 | 32.28 | 0 |  |
| T06 | PASS | 2 | [0, 0] | 0 | 21.47 | 0 |  |
| T07 | PASS | 2 | [0, 0] | 0 | 42.03 | 0 |  |
| T08 | PASS | 2 | [0, 0] | 0 | 31.88 | 0 |  |
| T09 | PASS | 11 | [0, 0, 0, 0] | 0 | 195.16 | 3 |  |
| T10 | PASS | 2 | [0, 0] | 0 | 32.59 | 0 |  |
| T11 | PASS | 2 | [0, 0] | 0 | 45.27 | 0 |  |
| T12 | PASS | 2 | [0, 0] | 0 | 42.3 | 0 |  |
| T13 | PASS | 2 | [0, 0] | 0 | 40.31 | 0 |  |
| T14 | PASS | 2 | [0, 0] | 0 | 31.25 | 0 |  |
| T15 | PASS | 2 | [0, 0] | 0 | 29.01 | 0 |  |
| T16 | PASS | 3 | [0, 0, 0] | 0 | 38.14 | 0 |  |
| T17 | PASS | 2 | [0, 0] | 0 | 35.2 | 0 |  |
| T18 | PASS | 2 | [0, 0] | 0 | 29.48 | 0 |  |
| T19 | PASS | 2 | [0, 0] | 0 | 27.42 | 0 |  |
| T20 | PASS | 13 | [0, 0, 0, 0] | 0 | 191.89 | 3 |  |

## KPIs

- Status counts: {'PASS': 20, 'FAIL': 0, 'BLOCKED': 0, 'TIMEOUT': 0, 'NOT_RUN': 0}
- Main success rate PASS/20: 20/20
- PASS/(PASS+FAIL+TIMEOUT): 20/20
- Median duration: 32.4 s
- Median tool calls: 2.0
- First-attempt success (derived: PASS with no failing script run): 20/20
- Repair loops above are derived from script exit codes (a failing run followed by another run); `results.jsonl` keeps them null because the trace has no explicit edit events.

