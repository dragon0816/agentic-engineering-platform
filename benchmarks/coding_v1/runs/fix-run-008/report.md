# coding_v1 report — fix-run-008

Generated 2026-10-07T02:02:29+00:00 from `results.jsonl`.

Evidence per task: `T??/prompt.md`, `T??/trace.json`, `T??/result.json`, `T??/workspace/`. Rerun: `python benchmarks/coding_v1/run.py --run-id <new-id> --tasks all` (see README.md).

## Setup

- Repository commit: `befb1a341bf4365a798e0e917b5255f9bbfd63f2`
- Entry point: Agent Web chat (`/api/conversations/turn`), one new session per task
- Model: {'alias': 'company', 'model': 'gpt-5.5', 'provider': 'openai_compatible'}
- Fixture manifest SHA-256: `a869d5fb693fc6b59d2be57c61b5337ef262ce6c512c06f3232e6ddf1633d633`; validator 1.3
- Budget: 600 s per task; tool calls bounded by the Gateway loop (4 per turn before commit fea13ff, 8 from it on: fix-run-003 and later)

## Results

| Task | Status | Tool calls | Script runs (exit codes) | Derived repair loops | Seconds | Interventions | Observed cause |
|---|---|---|---|---|---|---|---|
| T01 | PASS | 2 | [0, 0] | 0 | 22.78 | 0 |  |
| T02 | PASS | 2 | [0, 0] | 0 | 22.91 | 0 |  |
| T03 | PASS | 2 | [0, 0] | 0 | 35.39 | 0 |  |
| T04 | PASS | 2 | [0, 0] | 0 | 46.89 | 0 |  |
| T05 | PASS | 2 | [0, 0] | 0 | 38.67 | 0 |  |
| T06 | PASS | 2 | [0, 0] | 0 | 29.66 | 0 |  |
| T07 | PASS | 2 | [0, 0] | 0 | 58.94 | 0 |  |
| T08 | PASS | 2 | [0, 0] | 0 | 35.97 | 0 |  |
| T09 | PASS | 9 | [0] | 0 | 159.56 | 3 |  |
| T10 | PASS | 2 | [0, 0] | 0 | 30.12 | 0 |  |
| T11 | PASS | 3 | [0, 0, 0] | 0 | 59.11 | 0 |  |
| T12 | PASS | 2 | [0, 0] | 0 | 48.95 | 0 |  |
| T13 | FAIL | 3 | [0, 1, 0] | 1 | 80.56 | 0 | see trace |
| T14 | FAIL | 2 | [0, 0] | 0 | 34.05 | 0 | see trace |
| T15 | PASS | 2 | [0, 0] | 0 | 25.45 | 0 |  |
| T16 | PASS | 3 | [0, 0, 0] | 0 | 59.2 | 0 |  |
| T17 | PASS | 2 | [0, 0] | 0 | 30.58 | 0 |  |
| T18 | PASS | 2 | [0, 0] | 0 | 34.05 | 0 |  |
| T19 | PASS | 2 | [0, 0] | 0 | 34.75 | 0 |  |
| T20 | PASS | 10 | [0] | 0 | 176.47 | 4 |  |

## KPIs

- Status counts: {'PASS': 18, 'FAIL': 2, 'BLOCKED': 0, 'TIMEOUT': 0, 'NOT_RUN': 0}
- Main success rate PASS/20: 18/20
- PASS/(PASS+FAIL+TIMEOUT): 18/20
- Median duration: 35.7 s
- Median tool calls: 2.0
- First-attempt success (derived: PASS with no failing script run): 18/18
- Repair loops above are derived from script exit codes (a failing run followed by another run); `results.jsonl` keeps them null because the trace has no explicit edit events.

