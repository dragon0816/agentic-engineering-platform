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

The optional [n8n adapter](integrations/n8n/README.md) accepts operation IDs and
arguments for a host-bound workflow through `Gateway.execute_workflow`; normal
routed workflows share this entry point. Offline tests cover delivery deduplication,
policy and progress. No n8n runtime, HTTP endpoint or production connection is installed.
[Workflow checkpoints](docs/WORKFLOW_CHECKPOINTS.md) define the owner-scoped restart
evidence and store contract that manual recovery would rely on, with a bounded
in-memory reference store, a single-writer SQLite backend and a content-addressed
payload store for what those references point at. Giving the engine a
`RunJournal` records write-ahead evidence on the real execution path, so a run
interrupted by a restart can be inspected, suspended by a person who confirms the
old process is gone, and continued from its completed prefix — through the same
`Gateway.inspect`/`suspend`/`resume` entry points a host already uses, and
finished history can be retired without a used idempotency key ever running again.

Phase 4 (knowledge platform, `src/knowledge/`) is complete
(`docs/phases/PHASE_4_KNOWLEDGE.md`). The vault safety model never writes `drop/`
or `raw/`, defaults to a dry run, backs up every overwrite and rejects a rule-breaking
write plan whole. Originals dropped into `drop/` become write-once Raw Markdown whose
identity is its content; PDF, PPTX and DOCX are extracted with page/slide/image
relationships kept when the `office` extra is installed (`pip install -e ".[dev,office]"`),
and images are described through the `ModelClient` interface at intake. Ingest
planning, static lint, conflict markers with an append-only `decisions.md`, and
query with citations that name the source (BM25 with CJK support, optional strict
synthesis) build on that. An existing Obsidian vault is adopted by content hash
through a ledger, with snapshot and restore of the generated half, without a byte
of `raw/` changing. No model provider is named anywhere in knowledge code.

Phase 5 (model gateway, `src/models/`) is complete
(`docs/phases/PHASE_5_GATEWAY.md`). A catalog maps a stable alias to a
provider, a model id and the capabilities that endpoint actually has, and
selection matches declared `ModelRequirements` against them deterministically,
so changing a provider or a model is configuration rather than a code change.
Two adapters implement the same `ModelClient`: one for any OpenAI-compatible
endpoint, including an internal company gateway, and one for a local Ollama
over its own wire format. Every provider failure is a typed status rather than
an exception, no credential leaves a request header, and a `SecretRef` becomes
a value only in a resolver the host supplies, once per request. HTTP sits
behind an injected transport whose default is the standard library, so the
runtime install is still `pydantic` alone and no test opens a socket.
`models.proof` is a complete inert example a host can copy.

Phase 6 (evaluation, policy and observability, `src/common/evaluation.py` and
`src/common/trace.py`) is complete (`docs/phases/PHASE_6_EVALUATION.md`). The
cases under `evaluation/cases/` are graded by what they declare, every grader
is proven to reject, every routed case runs through a real `Gateway` where
execution can be seen, and every run leaves an `ExecutionTrace` that is
redacted by construction. The suite runs on every CI push with no model,
network or host process; the criteria-by-criteria record is in
[the Roadmap](docs/ROADMAP.md#phase-6--evaluation-policy-and-observability).

See [contract semantics](docs/CONTRACTS.md), [implementation/source decisions](docs/PHASE_1_PLAN.md),
[Phase 1 requirements](docs/phases/PHASE_1_FOUNDATION.md) and [handoff](HANDOFF.md).
Profiles and sample assets remain outside package code so contributions do not
require runtime edits. Future package distribution is outside this slice.
