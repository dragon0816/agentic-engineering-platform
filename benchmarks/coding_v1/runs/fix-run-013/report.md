# coding_v1 report — fix-run-013

Generated 2026-10-07T11:57:34+00:00 from `results.jsonl`.

Evidence per task: `T??/prompt.md`, `T??/trace.json`, `T??/result.json`, `T??/workspace/`. Rerun: `python benchmarks/coding_v1/run.py --run-id <new-id> --tasks all` (see README.md).

## Setup

- Repository commit: `041c7463cd9360f85539d7bc2c1f27d38eb9c0ed`
- Entry point: Agent Web chat (`/api/conversations/turn`), one new session per task
- Model: {'alias': 'company', 'model': 'gpt-5.5', 'provider': 'openai_compatible'}
- Fixture manifest SHA-256: `a869d5fb693fc6b59d2be57c61b5337ef262ce6c512c06f3232e6ddf1633d633`; validator 1.4
- Budget: 600 s per task; tool calls bounded by the Gateway loop (4 per turn before commit fea13ff, 8 from it on: fix-run-003 and later)

## Results

| Task | Status | Tool calls | Script runs (exit codes) | Derived repair loops | Seconds | Interventions | Observed cause |
|---|---|---|---|---|---|---|---|
| T01 | PASS | 2 | [0, 0] | 0 | 31.17 | 0 |  |
| T02 | PASS | 2 | [0, 0] | 0 | 28.59 | 0 |  |
| T03 | PASS | 3 | [0, 1, 0] | 1 | 44.28 | 0 |  |
| T04 | PASS | 3 | [0, 0, 0] | 0 | 31.19 | 0 |  |
| T05 | PASS | 2 | [0, 0] | 0 | 30.31 | 0 |  |
| T06 | PASS | 2 | [0, 0] | 0 | 21.86 | 0 |  |
| T07 | PASS | 2 | [0, 0] | 0 | 23.64 | 0 |  |
| T08 | PASS | 2 | [0, 0] | 0 | 29.16 | 0 |  |
| T09 | PASS | 10 | [0, 0, 0] | 0 | 132.48 | 3 |  |
| T10 | PASS | 2 | [0, 0] | 0 | 27.39 | 0 |  |
| T11 | PASS | 3 | [0, 0, 0] | 0 | 54.31 | 0 |  |
| T12 | PASS | 2 | [0, 0] | 0 | 41.31 | 0 |  |
| T13 | FAIL | 2 | [0, 0] | 0 | 37.19 | 0 | see trace |
| T14 | PASS | 3 | [0, 0, 0] | 0 | 34.62 | 0 |  |
| T15 | PASS | 2 | [0, 0] | 0 | 22.84 | 0 |  |
| T16 | PASS | 2 | [0, 0] | 0 | 29.95 | 0 |  |
| T17 | PASS | 3 | [0, 0, 0] | 0 | 40.8 | 0 |  |
| T18 | PASS | 2 | [0, 0] | 0 | 26.03 | 0 |  |
| T19 | PASS | 2 | [0, 0] | 0 | 25.55 | 0 |  |
| T20 | PASS | 9 | [0, 0] | 0 | 132.41 | 3 |  |

## KPIs

- Status counts: {'PASS': 19, 'FAIL': 1, 'BLOCKED': 0, 'TIMEOUT': 0, 'NOT_RUN': 0}
- Main success rate PASS/20: 19/20
- PASS/(PASS+FAIL+TIMEOUT): 19/20
- Median duration: 30.7 s
- Median tool calls: 2.0
- First-attempt success (derived: PASS with no failing script run): 18/19
- Repair loops above are derived from script exit codes (a failing run followed by another run); `results.jsonl` keeps them null because the trace has no explicit edit events.

