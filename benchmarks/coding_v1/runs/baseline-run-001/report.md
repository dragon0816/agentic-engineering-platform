# coding_v1 report — baseline-run-001

Generated 2026-10-06T11:46:55+00:00 from `results.jsonl`. Defects, gaps and priorities: [findings.md](findings.md).

Evidence per task: `T??/prompt.md`, `T??/trace.json`, `T??/result.json`, `T??/workspace/`. Rerun: `python benchmarks/coding_v1/run.py --run-id <new-id> --tasks all` (see README.md).

## Setup

- Repository commit: `3208619ab86d2886af4d5571162443bf62cf5f2e`
- Entry point: Agent Web chat (`/api/conversations/turn`), one new session per task
- Model: {'alias': 'company', 'model': 'gpt-5.5', 'provider': 'openai_compatible'}
- Fixture manifest SHA-256: `a869d5fb693fc6b59d2be57c61b5337ef262ce6c512c06f3232e6ddf1633d633`; validator 1.0
- Budget: 600 s per task; tool calls bounded by the Gateway loop (4 per turn)

## Results

| Task | Status | Tool calls | Seconds | Interventions | Observed cause |
|---|---|---|---|---|---|
| T01 | BLOCKED | 0 | 11.08 | 0 | G1 no tool to read the workspace, write files or run code; the reply explained this and offered code for a person to run |
| T02 | BLOCKED | 0 | 5.95 | 0 | G1 no tool to read the workspace, write files or run code; the reply explained this and offered code for a person to run |
| T03 | BLOCKED | 0 | 11.0 | 0 | D3 the Gateway model returned an empty answer |
| T04 | BLOCKED | 0 | 7.11 | 0 | G1 no tool to read the workspace, write files or run code; the reply explained this and offered code for a person to run |
| T05 | BLOCKED | 0 | 9.38 | 0 | G1 no tool to read the workspace, write files or run code; the reply explained this and offered code for a person to run |
| T06 | BLOCKED | 1 | 14.83 | 0 | G2 tried coding/change, refused (workflow_choice_unavailable): it only changes a configured repository against existing pytest tests |
| T07 | BLOCKED | 0 | 45.55 | 0 | D1 routed to the Knowledge harness; the model never saw the task |
| T08 | BLOCKED | 1 | 18.09 | 0 | D3 the Gateway model returned an empty answer |
| T09 | BLOCKED | 0 | 7.0 | 0 | G1 no tool to read the workspace, write files or run code; the reply explained this and offered code for a person to run |
| T10 | BLOCKED | 0 | 52.14 | 0 | D1 routed to the Knowledge harness; the model never saw the task |
| T11 | BLOCKED | 0 | 85.61 | 0 | D1 routed to the Knowledge harness; the model never saw the task |
| T12 | BLOCKED | 0 | 51.8 | 0 | D1 routed to the Knowledge harness; the model never saw the task |
| T13 | BLOCKED | 0 | 53.22 | 0 | D1 routed to the Knowledge harness; the model never saw the task |
| T14 | BLOCKED | 0 | 9.14 | 0 | G1 no tool to read the workspace, write files or run code; the reply explained this and offered code for a person to run |
| T15 | BLOCKED | 0 | 8.28 | 0 | G1 no tool to read the workspace, write files or run code; the reply explained this and offered code for a person to run |
| T16 | BLOCKED | 0 | 9.95 | 0 | G1 no tool to read the workspace, write files or run code; the reply explained this and offered code for a person to run |
| T17 | BLOCKED | 0 | 9.67 | 0 | G1 no tool to read the workspace, write files or run code; the reply explained this and offered code for a person to run |
| T18 | BLOCKED | 0 | 11.03 | 0 | G1 no tool to read the workspace, write files or run code; the reply explained this and offered code for a person to run |
| T19 | BLOCKED | 0 | 7.64 | 0 | G1 no tool to read the workspace, write files or run code; the reply explained this and offered code for a person to run |
| T20 | BLOCKED | 1 | 19.84 | 0 | G2 tried coding/change, refused (workflow_choice_unavailable): it only changes a configured repository against existing pytest tests |

## KPIs

- Status counts: {'PASS': 0, 'FAIL': 0, 'BLOCKED': 20, 'TIMEOUT': 0, 'NOT_RUN': 0}
- Main success rate PASS/20: 0/20
- PASS/(PASS+FAIL+TIMEOUT): no attempted task
- Median duration: 11.0 s
- Median tool calls: 0.0
- First-attempt success and repair loops: null for every task (not observable; see limitations)

