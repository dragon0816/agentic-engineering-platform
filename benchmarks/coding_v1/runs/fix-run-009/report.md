# coding_v1 report — fix-run-009

Generated 2026-10-07T03:36:17+00:00 from `results.jsonl`.

Evidence per task: `T??/prompt.md`, `T??/trace.json`, `T??/result.json`, `T??/workspace/`. Rerun: `python benchmarks/coding_v1/run.py --run-id <new-id> --tasks all` (see README.md).

## Setup

- Repository commit: `af527d90034d9b77c145573e5f79d292cc40187d`
- Entry point: Agent Web chat (`/api/conversations/turn`), one new session per task
- Model: {'alias': 'company', 'model': 'gpt-5.5', 'provider': 'openai_compatible'}
- Fixture manifest SHA-256: `a869d5fb693fc6b59d2be57c61b5337ef262ce6c512c06f3232e6ddf1633d633`; validator 1.4
- Budget: 600 s per task; tool calls bounded by the Gateway loop (4 per turn before commit fea13ff, 8 from it on: fix-run-003 and later)

## Results

| Task | Status | Tool calls | Script runs (exit codes) | Derived repair loops | Seconds | Interventions | Observed cause |
|---|---|---|---|---|---|---|---|
| T01 | PASS | 2 | [0, 0] | 0 | 22.03 | 0 |  |
| T02 | PASS | 2 | [0, 0] | 0 | 25.56 | 0 |  |
| T03 | PASS | 2 | [0, 0] | 0 | 36.67 | 0 |  |
| T04 | PASS | 2 | [0, 0] | 0 | 28.59 | 0 |  |
| T05 | PASS | 2 | [0, 0] | 0 | 33.11 | 0 |  |
| T06 | PASS | 2 | [0, 0] | 0 | 20.45 | 0 |  |
| T07 | PASS | 2 | [0, 0] | 0 | 30.77 | 0 |  |
| T08 | FAIL | 2 | [0, 0] | 0 | 31.22 | 0 | see trace |
| T09 | PASS | 9 | [0, 0, 0] | 0 | 126.67 | 3 |  |
| T10 | PASS | 2 | [0, 0] | 0 | 28.34 | 0 |  |
| T11 | PASS | 2 | [0, 0] | 0 | 42.88 | 0 |  |
| T12 | PASS | 2 | [0, 0] | 0 | 36.12 | 0 |  |
| T13 | PASS | 4 | [0, 0, 0, 0] | 0 | 92.8 | 0 |  |
| T14 | PASS | 2 | [0, 0] | 0 | 32.97 | 0 |  |
| T15 | PASS | 2 | [0, 0] | 0 | 34.89 | 0 |  |
| T16 | PASS | 2 | [0, 0] | 0 | 41.23 | 0 |  |
| T17 | PASS | 2 | [0, 0] | 0 | 30.91 | 0 |  |
| T18 | PASS | 2 | [0, 0] | 0 | 40.81 | 0 |  |
| T19 | PASS | 2 | [0, 0] | 0 | 33.52 | 0 |  |
| T20 | PASS | 9 | [0, 0] | 0 | 119.47 | 3 |  |

## KPIs

- Status counts: {'PASS': 19, 'FAIL': 1, 'BLOCKED': 0, 'TIMEOUT': 0, 'NOT_RUN': 0}
- Main success rate PASS/20: 19/20
- PASS/(PASS+FAIL+TIMEOUT): 19/20
- Median duration: 33.3 s
- Median tool calls: 2.0
- First-attempt success (derived: PASS with no failing script run): 19/19
- Repair loops above are derived from script exit codes (a failing run followed by another run); `results.jsonl` keeps them null because the trace has no explicit edit events.

