# coding_v1 report — fix-run-001

Generated 2026-10-06T12:20:57+00:00 from `results.jsonl`.

Evidence per task: `T??/prompt.md`, `T??/trace.json`, `T??/result.json`, `T??/workspace/`. Rerun: `python benchmarks/coding_v1/run.py --run-id <new-id> --tasks all` (see README.md).

## Setup

- Repository commit: `ba91a4633850186e2897c3af0c41c8a13cd5c175`
- Entry point: Agent Web chat (`/api/conversations/turn`), one new session per task
- Model: {'alias': 'company', 'model': 'gpt-5.5', 'provider': 'openai_compatible'}
- Fixture manifest SHA-256: `a869d5fb693fc6b59d2be57c61b5337ef262ce6c512c06f3232e6ddf1633d633`; validator 1.0
- Budget: 600 s per task; tool calls bounded by the Gateway loop (4 per turn)

## Results

| Task | Status | Tool calls | Seconds | Interventions | Observed cause |
|---|---|---|---|---|---|
| T01 | BLOCKED | 3 | 32.5 | 0 | see trace |
| T02 | BLOCKED | 0 | 8.67 | 0 | D3 the Gateway model returned an empty answer |
| T03 | BLOCKED | 0 | 10.7 | 0 | D3 the Gateway model returned an empty answer |
| T04 | BLOCKED | 2 | 26.77 | 0 | see trace |
| T05 | BLOCKED | 0 | 11.88 | 0 | D3 the Gateway model returned an empty answer |
| T06 | BLOCKED | 0 | 9.38 | 0 | D3 the Gateway model returned an empty answer |
| T07 | BLOCKED | 0 | 12.17 | 0 | D3 the Gateway model returned an empty answer |
| T08 | BLOCKED | 0 | 11.61 | 0 | D3 the Gateway model returned an empty answer |
| T09 | FAIL | 4 | 31.88 | 0 | see trace |
| T10 | FAIL | 1 | 16.7 | 0 | D3 the Gateway model returned an empty answer |
| T11 | NOT_RUN |  |  |  | not run |
| T12 | NOT_RUN |  |  |  | not run |
| T13 | NOT_RUN |  |  |  | not run |
| T14 | NOT_RUN |  |  |  | not run |
| T15 | NOT_RUN |  |  |  | not run |
| T16 | NOT_RUN |  |  |  | not run |
| T17 | NOT_RUN |  |  |  | not run |
| T18 | NOT_RUN |  |  |  | not run |
| T19 | NOT_RUN |  |  |  | not run |
| T20 | NOT_RUN |  |  |  | not run |

## KPIs

- Status counts: {'PASS': 0, 'FAIL': 2, 'BLOCKED': 8, 'TIMEOUT': 0, 'NOT_RUN': 10}
- Main success rate PASS/20: 0/20
- PASS/(PASS+FAIL+TIMEOUT): 0/2
- Median duration: 12.0 s
- Median tool calls: 0.0
- First-attempt success and repair loops: null for every task (not observable; see limitations)

