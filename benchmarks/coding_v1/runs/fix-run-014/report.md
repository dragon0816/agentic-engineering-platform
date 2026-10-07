# coding_v1 report — fix-run-014

Generated 2026-10-07T14:59:46+00:00 from `results.jsonl`.

Evidence per task: `T??/prompt.md`, `T??/trace.json`, `T??/result.json`, `T??/workspace/`. Rerun: `python benchmarks/coding_v1/run.py --run-id <new-id> --tasks all` (see README.md).

## Setup

- Repository commit: `06d1ebf48b0e2040f6875d08c2e782d0d33452b1`
- Entry point: Agent Web chat (`/api/conversations/turn`), one new session per task
- Model: {'alias': 'company', 'model': 'gpt-5.5', 'provider': 'openai_compatible'}
- Fixture manifest SHA-256: `a869d5fb693fc6b59d2be57c61b5337ef262ce6c512c06f3232e6ddf1633d633`; validator 1.4
- Budget: 600 s per task; tool calls bounded by the Gateway loop (4 per turn before commit fea13ff, 8 from it on: fix-run-003 and later)

## Results

| Task | Status | Tool calls | Script runs (exit codes) | Derived repair loops | Seconds | Interventions | Observed cause |
|---|---|---|---|---|---|---|---|
| T01 | PASS | 2 | [0, 0] | 0 | 28.88 | 0 |  |
| T02 | PASS | 2 | [0, 0] | 0 | 34.92 | 0 |  |
| T03 | PASS | 2 | [0, 0] | 0 | 43.12 | 0 |  |
| T04 | PASS | 2 | [0, 0] | 0 | 74.83 | 0 |  |
| T05 | PASS | 3 | [0, 0, 0] | 0 | 161.91 | 0 |  |
| T06 | PASS | 2 | [0, 0] | 0 | 90.45 | 0 |  |
| T07 | PASS | 2 | [0, 0] | 0 | 37.61 | 0 |  |
| T08 | PASS | 2 | [0, 0] | 0 | 36.23 | 0 |  |
| T09 | PASS | 8 | [0, 0] | 0 | 115.74 | 3 |  |
| T10 | PASS | 2 | [0, 0] | 0 | 36.14 | 0 |  |
| T11 | PASS | 3 | [0, 0, 0] | 0 | 319.2 | 0 |  |
| T12 | PASS | 2 | [0, 0] | 0 | 44.88 | 0 |  |
| T13 | PASS | 2 | [0, 0] | 0 | 46.33 | 0 |  |
| T14 | PASS | 2 | [0, 0] | 0 | 57.72 | 0 |  |
| T15 | PASS | 2 | [0, 0] | 0 | 131.25 | 0 |  |
| T16 | FAIL | 2 | [0, 0] | 0 | 107.64 | 0 | see trace |
| T17 | PASS | 3 | [0, 0, 0] | 0 | 78.11 | 0 |  |
| T18 | PASS | 2 | [0, 0] | 0 | 31.99 | 0 |  |
| T19 | PASS | 2 | [0, 0] | 0 | 34.88 | 0 |  |
| T20 | PASS | 9 | [0, 0, 0, 0] | 0 | 115.89 | 3 |  |

## KPIs

- Status counts: {'PASS': 19, 'FAIL': 1, 'BLOCKED': 0, 'TIMEOUT': 0, 'NOT_RUN': 0}
- Main success rate PASS/20: 19/20
- PASS/(PASS+FAIL+TIMEOUT): 19/20
- Median duration: 52.0 s
- Median tool calls: 2.0
- First-attempt success (derived: PASS with no failing script run): 19/19
- Repair loops above are derived from script exit codes (a failing run followed by another run); `results.jsonl` keeps them null because the trace has no explicit edit events.

