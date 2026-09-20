# Agentic Engineering Platform

Unified engineering automation platform for agentic reasoning, deterministic workflows, enterprise knowledge, tools/MCP capabilities, and evaluation.

Phase 1 provides validated contracts and an in-memory Task discovery / Bridge
advertisement proof. Phase 2 adds deterministic-first routing, installed Skills,
permission-checked local dispatch and an injected MCP client adapter. No production
handler, transport, model provider or service is installed by default.

## Development

Python 3.11 or newer:

```sh
python -m venv .venv
# Activate .venv (Windows: .venv\Scripts\Activate.ps1; POSIX: source .venv/bin/activate)
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m build
python -m pip check
```

CI verifies on Windows and Linux with Python 3.11 and 3.12. The pure proof is in
`workflow.proof.advertise_sample`; `tests/test_registry.py::test_vertical_proof`
loads the sample manifest and Bridge fixture and exercises the complete chain.

Phase 2 entry points are `agent.routing.RequestRouter`, `agent.skills.SkillRegistry`,
`capabilities.runtime.InstalledCapabilities`, `workflow.dispatch.BridgeExecutor`
and `capabilities.mcp.MCPAdapter`. See
`tests/test_dispatch.py::test_end_to_end_route_then_authorized_bridge_dispatch`
for a complete inert example. Host code must authenticate the request actor and
supply trusted policy grants; never construct grants from model output.

The sample `skills/source-routing.json` preserves source command routing only;
it does not install release/build/test implementations or authorize production actions.
See [Phase 2 scope](docs/phases/PHASE_2_AGENT_CAPABILITIES.md) and
[migration decisions](docs/PHASE_2_MIGRATION.md).

Phase 3 adds `agent.gateway.Gateway` and `workflow.engine.WorkflowEngine`.
Workflows can pass all run arguments to legacy steps or explicitly select inputs
from run arguments and earlier validated step outputs. Each step still requires
its own Bridge authorization. See [workflow input contracts](docs/CONTRACTS.md#phase-3-workflow-inputs)
and `tests/test_gateway_inputs.py` for a complete inert Gateway-to-Bridge chain.
Explicit steps may opt into bounded retries for typed transient read failures.
Caller-supplied workflow idempotency keys suppress duplicate submissions within
one engine instance; they are not durable exactly-once guarantees. Run history is
in memory. Finished runs can be inspected and resumed from their first
non-completed step under an explicit uncertain-effect policy, still in memory,
through `Gateway.inspect`/`Gateway.resume` or the engine directly, and owners can
follow a run's progress through bounded `watch` streams;
durable state and production jobs remain deferred.

See [contract semantics](docs/CONTRACTS.md), [implementation/source decisions](docs/PHASE_1_PLAN.md),
[Phase 1 requirements](docs/phases/PHASE_1_FOUNDATION.md) and [handoff](HANDOFF.md).
Profiles and sample assets remain outside package code so contributions do not
require runtime edits. Future package distribution is outside this slice.
