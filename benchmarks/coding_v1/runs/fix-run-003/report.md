# coding_v1 report — fix-run-003

Generated 2026-10-06T14:26:37+00:00 from `results.jsonl`.

Evidence per task: `T??/prompt.md`, `T??/trace.json`, `T??/result.json`, `T??/workspace/`. Rerun: `python benchmarks/coding_v1/run.py --run-id <new-id> --tasks all` (see README.md).

## Setup

- Repository commit: `fea13ffb5317155d62ff35dac34942a28ff66d98`
- Entry point: Agent Web chat (`/api/conversations/turn`), one new session per task
- Model: {'alias': 'company', 'model': 'gpt-5.5', 'provider': 'openai_compatible'}
- Fixture manifest SHA-256: `a869d5fb693fc6b59d2be57c61b5337ef262ce6c512c06f3232e6ddf1633d633`; validator 1.0
- Budget: 600 s per task; tool calls bounded by the Gateway loop (4 per turn)

## Results

| Task | Status | Tool calls | Script runs (exit codes) | Derived repair loops | Seconds | Interventions | Observed cause |
|---|---|---|---|---|---|---|---|
| T01 | PASS | 1 | [0] | 0 | 15.27 | 0 |  |
| T02 | PASS | 1 | [0] | 0 | 12.91 | 0 |  |
| T03 | PASS | 1 | [0] | 0 | 19.73 | 0 |  |
| T04 | PASS | 1 | [0] | 0 | 13.91 | 0 |  |
| T05 | FAIL | 1 | [0] | 0 | 26.42 | 0 | see trace |
| T06 | PASS | 1 | [0] | 0 | 20.06 | 0 |  |
| T07 | PASS | 1 | [0] | 0 | 24.52 | 0 |  |
| T08 | FAIL | 3 | [0, 0, 0] | 0 | 36.38 | 0 | see trace |
| T09 | BLOCKED | 8 | [0, 0, 0, 0, 0, 0, 0, 0] | 0 | 67.62 | 0 | G3 the conversation loop's tool budget (4 calls per turn) ended the turn |
| T10 | PASS | 2 | [0, 0] | 0 | 34.42 | 0 |  |
| T11 | PASS | 1 | [0] | 0 | 25.2 | 0 |  |
| T12 | PASS | 2 | [0, 0] | 0 | 30.28 | 0 |  |
| T13 | FAIL | 1 | [0] | 0 | 40.52 | 0 | see trace |
| T14 | PASS | 2 | [1, 0] | 1 | 32.84 | 0 |  |
| T15 | PASS | 1 | [0] | 0 | 10.52 | 0 |  |
| T16 | PASS | 1 | [0] | 0 | 14.09 | 0 |  |
| T17 | PASS | 1 | [0] | 0 | 19.61 | 0 |  |
| T18 | PASS | 2 | [1, 0] | 1 | 42.97 | 0 |  |
| T19 | PASS | 1 | [0] | 0 | 18.62 | 0 |  |
| T20 | BLOCKED | 2 | [0, 0] | 0 | 18.97 | 0 | see trace |

## KPIs

- Status counts: {'PASS': 15, 'FAIL': 3, 'BLOCKED': 2, 'TIMEOUT': 0, 'NOT_RUN': 0}
- Main success rate PASS/20: 15/20
- PASS/(PASS+FAIL+TIMEOUT): 15/18
- Median duration: 22.3 s
- Median tool calls: 1.0
- First-attempt success (derived: PASS with no failing script run): 13/15
- Repair loops above are derived from script exit codes (a failing run followed by another run); `results.jsonl` keeps them null because the trace has no explicit edit events.

