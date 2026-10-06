# coding_v1 report — fix-run-004

Generated 2026-10-06T15:15:10+00:00 from `results.jsonl`.

Evidence per task: `T??/prompt.md`, `T??/trace.json`, `T??/result.json`, `T??/workspace/`. Rerun: `python benchmarks/coding_v1/run.py --run-id <new-id> --tasks all` (see README.md).

## Setup

- Repository commit: `3b0bfc6623ea37e1520a4c1f8e00448835735b1a`
- Entry point: Agent Web chat (`/api/conversations/turn`), one new session per task
- Model: {'alias': 'company', 'model': 'gpt-5.5', 'provider': 'openai_compatible'}
- Fixture manifest SHA-256: `a869d5fb693fc6b59d2be57c61b5337ef262ce6c512c06f3232e6ddf1633d633`; validator 1.1
- Budget: 600 s per task; tool calls bounded by the Gateway loop (4 per turn before commit fea13ff, 8 from it on: fix-run-003 and later)

## Results

| Task | Status | Tool calls | Script runs (exit codes) | Derived repair loops | Seconds | Interventions | Observed cause |
|---|---|---|---|---|---|---|---|
| T01 | PASS | 1 | [0] | 0 | 16.22 | 0 |  |
| T02 | PASS | 2 | [0, 0] | 0 | 24.52 | 0 |  |
| T03 | PASS | 2 | [0, 0] | 0 | 29.92 | 0 |  |
| T04 | PASS | 2 | [0, 0] | 0 | 31.14 | 0 |  |
| T05 | PASS | 3 | [0, 0, 0] | 0 | 39.19 | 0 |  |
| T06 | PASS | 2 | [0, 0] | 0 | 26.17 | 0 |  |
| T07 | PASS | 2 | [0, 0] | 0 | 28.3 | 0 |  |
| T08 | PASS | 2 | [0, 0] | 0 | 22.7 | 0 |  |
| T09 | FAIL | 2 | [0, 0] | 0 | 44.05 | 0 | see trace |
| T10 | PASS | 2 | [0, 0] | 0 | 25.48 | 0 |  |
| T11 | PASS | 3 | [0, 0, 0] | 0 | 59.72 | 0 |  |
| T12 | FAIL | 2 | [0, 0] | 0 | 35.0 | 0 | see trace |
| T13 | FAIL | 3 | [0, 0, 0] | 0 | 46.06 | 0 | see trace |
| T14 | PASS | 2 | [0, 0] | 0 | 29.88 | 0 |  |
| T15 | PASS | 2 | [0, 0] | 0 | 22.19 | 0 |  |
| T16 | PASS | 2 | [0, 0] | 0 | 26.09 | 0 |  |
| T17 | PASS | 2 | [0, 0] | 0 | 34.14 | 0 |  |
| T18 | PASS | 2 | [0, 0] | 0 | 28.95 | 0 |  |
| T19 | PASS | 2 | [0, 0] | 0 | 32.05 | 0 |  |
| T20 | FAIL | 7 | [0, 0, 0, 0, 0] | 0 | 100.88 | 2 | G1 no tool to read the workspace, write files or run code; the reply explained this and offered code for a person to run |

## KPIs

- Status counts: {'PASS': 16, 'FAIL': 4, 'BLOCKED': 0, 'TIMEOUT': 0, 'NOT_RUN': 0}
- Main success rate PASS/20: 16/20
- PASS/(PASS+FAIL+TIMEOUT): 16/20
- Median duration: 29.9 s
- Median tool calls: 2.0
- First-attempt success (derived: PASS with no failing script run): 16/16
- Repair loops above are derived from script exit codes (a failing run followed by another run); `results.jsonl` keeps them null because the trace has no explicit edit events.

