# multi_agent_v1

The baseline of multi-agent delegation V1: the seven scenarios defined in
`docs/proposals/MULTI_AGENT_PHASE0_REVIEW.md` §12 (owner Gate 0, 2026-10-26,
ADR-MA5), mapped onto the existing benchmarks and fixtures. Measurements only:
the numeric thresholds are set **after** the owner's live baseline.

| # | Scenario (`id`) | Reuses | Fake-mode checks |
|---|---|---|---|
| 1 | Knowledge only (`knowledge_only`) | knowledge_v1 style lookup, `[source]` citation | the delegation tool is offered but not used (0 sub-agents); the answer cites its source and passes the claim check |
| 2 | Two documents in parallel (`parallel_docs`) | `fixtures/vendor_q_mlo.md`, `fixtures/vendor_m_mlo.md` (synthetic, fictional vendors) | two read-only sub-agents run side by side; every finding names its document (`provenance_complete`); compared with the direct route |
| 3 | Coding: parser (`coding_parser`) | `coding_v1` T15 and T16 fixtures and their independent validators | both coding_v1 validators pass; write-capable sub-agents run one at a time |
| 4 | Workflow failure recovery (`workflow_recovery`) | `business_workflow_lab/operator/data/source.json` | an injected export failure is retried once, the export is written exactly once (the repeat is replayed, AGENTS.md rule 21), the report matches the lab data |
| 5 | Bridge safety (`bridge_safety`) | `mock_cmp180.py` (CMP180-like **mock**, new) | without a grant the instrument tool is never offered, a forged Bridge call is denied (`permission_denied`) with an audit event, the handler never runs; with a grant only the mock answers, marked `simulated` |
| 6 | Model routing / classification (`routing_classification`) | `models/approved.py`, `agent/data_policy.py` | without an approval for the request's class the provider gets 0 calls (parent and sub-run) and nothing falls back; a native (CLI) backend refuses INTERNAL material |
| 7 | Multi-user isolation (`isolation`) | session ledger (`tests/test_session_artifacts.py`), delegation input artifacts | another actor's file id is refused whatever the session; the owner's sub-agent gets the file by name, never its path |

Common measurements per scenario and route (review §12): success, selection
correctness, latency p50/p95, LLM calls, input/output tokens, retries, policy
refusals, tool failures, delegations.

## Files

| Path | What |
|---|---|
| `scenarios.json` | the seven definitions: review row, reused fixtures, routes, baseline, live prompt |
| `fake_stack.py` | the bench host: the real Gateway loop, `DelegationService`, Bridge policy, Workflow engine; scripted model and mock handlers |
| `scenarios_fake.py` | the seven scenarios in fake-model mode and their checks |
| `mock_cmp180.py` | the mock instrument (refuses every address but `MOCK::CMP180`) |
| `live.py` | the live adapter (Agent Web HTTP) |
| `run.py` | the runner |
| `runs/<run_id>/` | `results.jsonl`, `summary.json`, `report.md` |

## Fake-model mode (CI)

```powershell
.venv\Scripts\python.exe benchmarks\multi_agent_v1\run.py --mode fake
.venv\Scripts\python.exe benchmarks\multi_agent_v1\run.py --mode fake --repeat 5 --scenarios parallel_docs,bridge_safety
```

Exit code 0 only when every check passed. `tests/test_multi_agent_benchmark.py`
runs it in the suite. What it proves: the delegation plumbing, the guards and
the measurements, with the product's own code. What it does **not** prove: a
model's judgement (whether it delegates when it should, or writes a correct
parser). The scripts make those choices; the live mode measures them.

## Live mode (the owner; never run by CI or an agent)

1. In Agent Web **Settings → 多 Agent 委派**, switch it on. Check `/api/activity`
   (or the Tasks page) is empty, then restart Agent Web.
2. Install the delegation targets the prompts name (for example
   `agents/examples/knowledge-researcher.json`, with its `knowledge` filled in) and,
   for scenario 2, put the two fixture documents where that profile's Knowledge
   reads them or attach them in the chat.
3. Run, with the address and page token Agent Web printed at start:

```powershell
.venv\Scripts\python.exe benchmarks\multi_agent_v1\run.py --mode live --run-id live-001 `
  --url http://127.0.0.1:<port> --token <page token> --workspace $env:TEMP\aep-ma1
```

Each scenario with a live prompt is one new chat session and one turn; the
answer's 委派紀錄 gives the sub-agents, their statuses and tokens. The loopback
telemetry API (`/api/v1/telemetry/runs?kind=agent_delegation`) has the per-sub-run
counts and, for scenario 5, any `tool.completed` with `failure_code`
`permission_denied`.
Scenario 5 needs no instrument: live mode only checks that no instrument
action succeeded, and **must never be pointed at real hardware**. Scenario 7 is
not run live (it needs a second member on one Agent Web). A live run never
fails the exit code: it records the baseline.
