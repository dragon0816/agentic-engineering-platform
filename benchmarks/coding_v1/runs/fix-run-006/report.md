# coding_v1 report — fix-run-006

Generated 2026-10-06T15:56:34+00:00 from `results.jsonl`.

Evidence per task: `T??/prompt.md`, `T??/trace.json`, `T??/result.json`, `T??/workspace/`. Rerun: `python benchmarks/coding_v1/run.py --run-id <new-id> --tasks all` (see README.md).

## Setup

- Repository commit: `99ddff1f7a82abed7da1041ae201f10320f12256`
- Entry point: Agent Web chat (`/api/conversations/turn`), one new session per task
- Model: {'alias': 'company', 'model': 'gpt-5.5', 'provider': 'openai_compatible'}
- Fixture manifest SHA-256: `a869d5fb693fc6b59d2be57c61b5337ef262ce6c512c06f3232e6ddf1633d633`; validator 1.3
- Budget: 600 s per task; tool calls bounded by the Gateway loop (4 per turn before commit fea13ff, 8 from it on: fix-run-003 and later)

## Results

| Task | Status | Tool calls | Script runs (exit codes) | Derived repair loops | Seconds | Interventions | Observed cause |
|---|---|---|---|---|---|---|---|
| T01 | PASS | 2 | [0, 0] | 0 | 20.77 | 0 |  |
| T02 | PASS | 2 | [0, 0] | 0 | 22.33 | 0 |  |
| T03 | PASS | 2 | [0, 0] | 0 | 29.78 | 0 |  |
| T04 | PASS | 3 | [0, 1, 0] | 1 | 38.08 | 0 |  |
| T05 | PASS | 2 | [0, 0] | 0 | 33.92 | 0 |  |
| T06 | PASS | 2 | [0, 0] | 0 | 19.03 | 0 |  |
| T07 | PASS | 2 | [0, 0] | 0 | 23.45 | 0 |  |
| T08 | PASS | 2 | [0, 0] | 0 | 26.48 | 0 |  |
| T09 | PASS | 9 | [0] | 0 | 119.42 | 3 |  |
| T10 | PASS | 2 | [0, 0] | 0 | 30.8 | 0 |  |
| T11 | PASS | 3 | [0, 0, 0] | 0 | 55.92 | 0 |  |
| T12 | PASS | 2 | [0, 0] | 0 | 33.81 | 0 |  |
| T13 | PASS | 2 | [0, 0] | 0 | 50.47 | 0 |  |
| T14 | PASS | 2 | [0, 0] | 0 | 28.02 | 0 |  |
| T15 | PASS | 2 | [0, 0] | 0 | 19.94 | 0 |  |
| T16 | PASS | 2 | [1, 0] | 1 | 24.25 | 0 |  |
| T17 | PASS | 2 | [0, 0] | 0 | 31.0 | 0 |  |
| T18 | PASS | 1 | [0] | 0 | 25.42 | 0 |  |
| T19 | PASS | 2 | [0, 0] | 0 | 22.89 | 0 |  |
| T20 | PASS | 12 | [0, 0, 0] | 0 | 165.64 | 3 |  |

## KPIs

- Status counts: {'PASS': 20, 'FAIL': 0, 'BLOCKED': 0, 'TIMEOUT': 0, 'NOT_RUN': 0}
- Main success rate PASS/20: 20/20
- PASS/(PASS+FAIL+TIMEOUT): 20/20
- Median duration: 28.9 s
- Median tool calls: 2.0
- First-attempt success (derived: PASS with no failing script run): 18/20
- Repair loops above are derived from script exit codes (a failing run followed by another run); `results.jsonl` keeps them null because the trace has no explicit edit events.

