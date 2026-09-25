# Agentic Engineering Platform

Unified engineering automation platform for agentic reasoning, deterministic workflows, enterprise knowledge, tools/MCP capabilities, and evaluation.

The product direction is defined in [Product Vision](docs/PRODUCT_VISION.md).
The required product gates and implementation order are defined in
[Product Acceptance Tests](docs/PRODUCT_ACCEPTANCE_TESTS.md).
The approved [Personal Agent and Coding Harness proposal](docs/AGENT_HARNESS_ARCHITECTURE_PROPOSAL.md)
compares that vision with the implemented architecture and fixes the incremental
product gate order.

Phase 7 is active with invitation-only platform enrollment and separate Bridge
device identity as its first slice. Production-like validation will run on an
enrolled company Agent + Bridge, beginning with the GTM weekly report (source workflow 11) and release
package workflow 13; CI and this shared-platform host remain side-effect-free.

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

CI verifies on Windows with Python 3.12. The package still declares Python 3.11+
compatibility; the narrower CI target is an explicit owner decision. The pure proof is in
`workflow.proof.advertise_sample`; `tests/test_registry.py::test_vertical_proof`
loads the sample manifest and Bridge fixture and exercises the complete chain.

The first product gate, E2E-02, proves that a Personal Agent can turn a bounded
SOP into a typed draft Workflow, validate it through the normal
Gateway/Workflow/Bridge path against an independent fixture, and replay an
approved installation deterministically with the model disabled. It has no
production side effects. Reproduce the full positive and negative gate with:

```sh
python -m pytest tests/test_product_e2e_02.py -q
```

See [the E2E-02 implementation record](docs/phases/E2E_02_SOP_WORKFLOW.md).

E2E-03 adds a bounded Coding Harness behind the same resident Agent, Gateway and
Bridge path. Its first parser/transformation proof pins the workspace revision,
records the plan and actual patch separately, runs only an injected declared
validator, repairs one rejected candidate within budget, and requires both new
and regression cases to pass. It never commits, pushes or publishes. Reproduce
the gate with:

```sh
python -m pytest tests/test_product_e2e_03.py -q
```

See [the E2E-03 implementation record](docs/phases/E2E_03_CODING_HARNESS.md).

E2E-05 proves the first governed Knowledge improvement loop. A Personal Agent
queries an exact published version with Raw citations, captures incomplete-answer
feedback, and creates a separately approved candidate workspace through the
Bridge. The candidate must keep Raw byte-identical and pass the new question plus
existing regressions before a domain owner can approve a new version. The prior
version remains queryable for rollback. Reproduce the gate with:

```sh
python -m pytest tests/test_product_e2e_05.py -q
```

See [the E2E-05 implementation record](docs/phases/E2E_05_KNOWLEDGE_EVOLUTION.md).

E2E-04 proves governed Software evolution without moving source code into the
Share Platform. A user reports a failure against an exact Software version; the
platform derives its owner and repository, reproduces the failure before any
change, invokes the bounded Coding Harness, requires the issue case and existing
regressions to pass, and prepares an inert PR/MR review artifact. Human review,
merge, release and platform republish remain explicit transitions. Reproduce
the gate with:

```sh
python -m pytest tests/test_product_e2e_04.py -q
```

See [the E2E-04 implementation record](docs/phases/E2E_04_SOFTWARE_EVOLUTION.md).

E2E-01 adds the provider-neutral device/chipset development boundary. The
existing Coding Harness performs a bounded change and a simulator independently
checks the new case plus regressions. Physical validation is a separate,
high-risk Bridge capability installed only from trusted company-host
configuration. It pins the exact Skill, DUT, firmware, optional instrument and
fixed local driver; typed state and measurement limits decide success. CI can
exercise only simulator or recording adapters and cannot produce
production-like evidence. Reproduce the inert gate with:

```sh
python -m pytest tests/test_product_e2e_01.py tests/test_dut_host.py -q
```

See [the E2E-01 implementation and owner-run gate](docs/phases/E2E_01_DUT_ENGINEERING.md).
The product gate remains pending until its Windows bundle is run on the enrolled
company Bridge with real DUT/instrument evidence and accepted by a human reviewer.

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
require runtime edits. Production host distribution remains outside this preview.

The Phase 7 Windows company-host technical preview is built with
`scripts/build_windows_preview.py`. It installs a local `aep-host` CLI from bundled
Python 3.12 wheels, validates the host with `aep-host doctor`, and exports an empty,
credential-free Bridge enrollment request. See `deploy/windows-preview/README.md`.
It has no shared-platform transport and cannot execute workflow 13 yet.

Phase 7 keeps the Personal Agent, installed assets and authoritative run state on
each Bridge computer. The shared platform distributes published packages and holds
timestamped status projections. Remote jobs are actor/device scoped: a company
computer accepts its bound owner, a shared test computer accepts its bound users,
and future Telegram polling maps a sender to the same platform actor before routing.
