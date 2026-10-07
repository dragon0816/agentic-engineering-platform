# coding_v1 report — fix-run-010

Generated 2026-10-07T04:53:44+00:00 from `results.jsonl`.

Evidence per task: `T??/prompt.md`, `T??/trace.json`, `T??/result.json`, `T??/workspace/`. Rerun: `python benchmarks/coding_v1/run.py --run-id <new-id> --tasks all` (see README.md).

## Setup

- Repository commit: `c87508a99483086c622a2e1ccae9c523e241ec18`
- Entry point: Agent Web chat (`/api/conversations/turn`), one new session per task
- Model: {'alias': 'company', 'model': 'gpt-5.5', 'provider': 'openai_compatible'}
- Fixture manifest SHA-256: `a869d5fb693fc6b59d2be57c61b5337ef262ce6c512c06f3232e6ddf1633d633`; validator 1.4
- Budget: 600 s per task; tool calls bounded by the Gateway loop (4 per turn before commit fea13ff, 8 from it on: fix-run-003 and later)

## Results

| Task | Status | Tool calls | Script runs (exit codes) | Derived repair loops | Seconds | Interventions | Observed cause |
|---|---|---|---|---|---|---|---|
| T01 | PASS | 2 | [0, 0] | 0 | 30.59 | 0 |  |
| T02 | PASS | 2 | [0, 0] | 0 | 25.14 | 0 |  |
| T03 | PASS | 2 | [0, 0] | 0 | 30.55 | 0 |  |
| T04 | PASS | 3 | [0, 0, 0] | 0 | 32.64 | 0 |  |
| T05 | PASS | 3 | [0, 0, 0] | 0 | 35.92 | 0 |  |
| T06 | PASS | 2 | [0, 0] | 0 | 21.36 | 0 |  |
| T07 | PASS | 2 | [0, 0] | 0 | 27.0 | 0 |  |
| T08 | PASS | 2 | [0, 0] | 0 | 29.41 | 0 |  |
| T09 | NOT_RUN |  |  |  |  |  | not run |
| T10 | NOT_RUN |  |  |  |  |  | not run |
| T11 | NOT_RUN |  |  |  |  |  | not run |
| T12 | NOT_RUN |  |  |  |  |  | not run |
| T13 | NOT_RUN |  |  |  |  |  | not run |
| T14 | NOT_RUN |  |  |  |  |  | not run |
| T15 | NOT_RUN |  |  |  |  |  | not run |
| T16 | NOT_RUN |  |  |  |  |  | not run |
| T17 | NOT_RUN |  |  |  |  |  | not run |
| T18 | NOT_RUN |  |  |  |  |  | not run |
| T19 | NOT_RUN |  |  |  |  |  | not run |
| T20 | NOT_RUN |  |  |  |  |  | not run |

## KPIs

- Status counts: {'PASS': 8, 'FAIL': 0, 'BLOCKED': 0, 'TIMEOUT': 0, 'NOT_RUN': 12}
- Main success rate PASS/20: 8/20
- PASS/(PASS+FAIL+TIMEOUT): 8/8
- Median duration: 30.0 s
- Median tool calls: 2.0
- First-attempt success (derived: PASS with no failing script run): 8/8
- Repair loops above are derived from script exit codes (a failing run followed by another run); `results.jsonl` keeps them null because the trace has no explicit edit events.

