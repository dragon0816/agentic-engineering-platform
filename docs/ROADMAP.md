# Agentic Engineering Platform — Roadmap

Status: Phases 1–6 complete; Phase 7 — End-to-end migration and controlled deprecation active

## Product E2E milestone (approved and active)

The product-level direction is recorded in `PRODUCT_VISION.md`. The approved
next milestone is one useful Personal Engineering Agent with a bounded Coding
Harness that passes three executable benchmark categories: device/chipset
development, SOP-to-deterministic-Workflow, and parser/transformation
development. `AGENT_HARNESS_ARCHITECTURE_PROPOSAL.md` assesses the current
implementation and defines the incremental boundary approved by the owner.
The product E2E gate order and observable completion evidence are defined in
`PRODUCT_ACCEPTANCE_TESTS.md`; this Roadmap does not override them.

The fixed order is **E2E-02 → E2E-03 → E2E-05 → E2E-04 → E2E-01**. E2E-02
merged in PR #98, E2E-03 in PR #99 and E2E-05 in PR #100. The E2E-05 proof
reuses the resident Agent/Gateway/Bridge and Phase 4 Knowledge vault,
query, Raw provenance and decision records. The proof captures feedback against
an exact cited answer, creates an independently authorized candidate version,
runs the new case plus existing regressions, records separate domain approval,
publishes vNext and preserves the exact old version for rollback. Its boundary
is documented in `docs/phases/E2E_05_KNOWLEDGE_EVOLUTION.md`. E2E-04 is the
next approved product gate and has not started.

## Objective

Consolidate capabilities from the existing repositories into `agentic-engineering-platform` through contract-first, test-backed migration. This is not a source-tree merge.

The target is a **multi-user, contribution-driven engineering automation platform**. Team members can develop, validate, publish, discover, reuse and evolve Tasks, Workflows, Skills, Knowledge and Agent profiles. Platform capability grows through contributions without requiring changes to the core runtime.

## Source disposition

| Source | Primary value | Target | Initial disposition |
|---|---|---|---|
| `telegram-local-agent` | channels, deterministic-first router, skills/tools, MCP, Ollama | agent + capabilities | **Refactor / reuse** |
| `rs_workflow_system` | n8n orchestration, Host Bridge, jobs/services, deployment | workflow + integrations | **Reuse / adapt** |
| `n8n_work_flow` | prototypes, n8n agent experiments, concrete automations | workflow/integration knowledge | **Selectively migrate** |
| `knowledge_management` | LiteLLM gateway, agent, benchmark, vault/wiki | gateway + knowledge + evaluation | **Split by responsibility** |
| `customized_llm_proxy` | overlapping gateway/agent/bench/vault tree | lineage reference | **Do not duplicate; verify then retire/alias** |

## Phase 0 — Architecture and inventory

Deliverables:
- `ARCHITECTURE.md`
- `AGENTS.md`
- this migration plan
- source component inventory
- target contracts and acceptance criteria for Phase 1

No source repository modifications.

## Phase 1 — Foundation

Create repository skeleton and shared contracts. Establish `pyproject.toml`, test runner, lint/type checks and CI. Define core models such as `RequestContext`, `RouteDecision`, `CapabilitySpec`, `CapabilityResult`, `WorkflowRun`, `ApprovalRequest`, `KnowledgeSource`, `TaskManifest`, `WorkflowManifest`, `AgentProfile`, package/registry metadata and trace identifiers.

Define the first Platform Registry contracts for contribution lifecycle: scoped asset identity (`namespace`, `name`, semantic version), owner, visibility, lifecycle state (`draft`, `validated`, `published`, `deprecated`), dependencies, compatibility, layered business/technical approval metadata, permissions/risk classification and discoverability. Define local-vs-central execution dependency metadata and provider-neutral `SecretRef` requirements without implementing a production secret backend. Define Bridge/worker registration contracts so execution nodes can advertise installed capabilities and local resources. Registry/distribution must remain separate from execution authorization.

Before implementation migration, add characterization tests around selected source behaviours.

Exit criteria: skeleton installs cleanly; CI passes; contracts are documented; a side-effect-free sample Task can be represented by a scoped/versioned manifest and discovered through an in-memory registry; Bridge/worker capability advertisement has a typed contract; local-vs-central dependency and secret-reference contracts are validated; business approval and technical policy are represented as separate metadata concerns; no production side effects.

## Phase 2 — Agent and capability layer

Migrate/adapt from `telegram-local-agent`:
- channel-neutral request model
- deterministic command routing
- skill registry
- tool/capability registry
- MCP discovery/execution
- model-based fallback routing
- file attachment context

Keep the ordering deterministic command -> known workflow/capability -> model reasoning. Replace ad-hoc cross-module conventions with typed contracts while preserving existing user-visible behaviour where required.

Exit criteria: representative commands route without an LLM; ambiguous requests can use a model; capability permissions are enforced; router regression suite passes.

## Phase 3 — Workflow platform

Adopt the `rs_workflow_system` separation:

```text
orchestrator -> Host Bridge router -> service/job -> local capability
```

Preserve the ability to run jobs independently of n8n. The primary path is Agent/CLI -> Workflow or Capability contract -> Host Bridge/job. n8n is an optional event/business automation adapter that may invoke the same contract for schedules, triggers, notifications or SaaS integration. Do not fork separate Agent, CLI and n8n implementations for the same operation.

Selectively migrate business workflows from `n8n_work_flow`; where both repositories solve the same problem, prefer the Host Bridge/service/job architecture and retain older scripts only as behavioural references/tests.

Exit criteria: one representative engineering workflow can be triggered by deterministic command and Agent through one underlying contract; when n8n integration is enabled, it invokes that same contract without becoming a runtime dependency.

## Phase 4 — Knowledge platform

Start from the vault safety model in `knowledge_management` and evolve the pipeline:

```text
Drop originals
  -> extraction
     -> text
     -> tables
     -> images + vision description
     -> page/slide/source metadata
  -> Raw Markdown
  -> validation/conflict handling
  -> Wiki curation
  -> retrieval/query
```

Preserve immutable raw/source semantics, dry-run/apply separation, backups, source provenance, conflict decisions and static lint. Add the currently missing query layer and image-aware ingestion. Define an explicit migration adapter/path for existing Obsidian vault content, existing Raw data, images and metadata so provenance/immutability rules can be adopted without treating existing knowledge as a greenfield corpus.

Exit criteria: PDF/PPT/DOCX sample corpus round-trips to Raw with traceable source/page/slide/image relationships; Wiki generation cannot mutate Raw; query answers can cite source provenance.

Met 2026-09-21 in nine slices (`docs/phases/PHASE_4_KNOWLEDGE.md`, decisions in `docs/PHASE_4_MIGRATION.md`): vault safety model, Drop → Raw with content identity, office extraction, image description and ingest planning through the model interface, static lint, conflicts and decisions, query with provenance, and a migration adapter that adopts an existing vault without rewriting `raw/`.

## Phase 5 — Model gateway

Extract the LiteLLM/company-model gateway from the mixed knowledge repository into `src/gateway/` or a separately deployable package under this repo. Keep provider-specific patches isolated. Agent/knowledge/evaluation consume a model interface rather than importing gateway internals.

Exit criteria: at least local Ollama and the internal OpenAI-compatible gateway can satisfy the same model client interface; credentials are externalized.

Met 2026-09-22 in five slices (`docs/phases/PHASE_5_GATEWAY.md`, decisions in `docs/PHASE_5_MIGRATION.md`): a capability-checked model catalog with deterministic selection, an OpenAI-compatible adapter, an Ollama adapter over its own wire format, the credential resolution boundary and client construction from a catalog, and per-response latency with a worked example. The source's LiteLLM proxy was deliberately not migrated: it existed to terminate the Anthropic wire format for Claude Code, which the owner placed out of scope, and the company gateway is already OpenAI-compatible.

## Phase 6 — Evaluation, policy and observability

Unify benchmark concepts into an engineering harness with three categories:

1. deterministic regression tests,
2. agent routing/planning evaluation,
3. end-to-end scenario evaluation.

Example scenario:

```text
Input: release a chipset package
Expected:
  - select release capability
  - obey version semantics
  - run required validation
  - create allowed artifact/tag
Forbidden:
  - overwrite released tag
  - skip mandatory tests
  - modify unrelated repository
  - expose credentials
```

Capture route, plan, tool/workflow calls, approvals, duration, model usage and final status with secret redaction.

Exit criteria: evaluation suite runs in CI without production side effects and blocks known regressions.

Met 2026-09-22 in five slices (`docs/phases/PHASE_6_EVALUATION.md`, decisions in `docs/PHASE_6_MIGRATION.md`): a case's declared assertions decide whether it passed and an unrecognized assertion fails it; every grader is proven to reject; every routed case is exercised through a real Gateway where execution could be seen, and a check that could not have seen its evidence does not pass; the scenario above is a case whose four prohibitions are checked as evidence of what happened; the `agent` category is routed by a model through the real Phase 5 adapter and compared across aliases with repetition, reported as skipped rather than passed when no alias is configured; and every run leaves an `ExecutionTrace` that joins to its request, keeps the Bridge's order, and is redacted by construction and refused if a credential remains. The suite runs on every CI push with no model, network or host process. The source's coding benchmark was deliberately not migrated: it measures a model, needs a live endpoint and executes generated code, which the exit criterion rules out. Codex and Claude Code were excluded from this phase entirely by the owner.

## Phase 7 — End-to-end migration and deprecation

Run representative production-like scenarios against old and new paths. Deprecate source components only after parity/acceptance criteria are met. Keep rollback documentation during transition.

Owner scope set 2026-09-22: the shared-platform computer is the control plane;
real validation runs on an enrolled company computer with Agent + Bridge. Start
with workflow 11 (the GTM weekly report), then workflow 13 (release package), then a copy of
the knowledge vault. Accounts are invitation-only. A company workstation is bound
to its one employee; a shared test workstation may bind several platform users
who share one Windows account and therefore have no OS-level isolation from each
other. CI remains inert and all source paths remain available for rollback.

Exit criteria: both priority workflows pass their explicit source/platform parity
gates on the company Bridge; knowledge passes on a copy; account/device/run identity
is attributable; rollback is rehearsed; and each retired entry point has owner
approval and retained source evidence. See `docs/phases/PHASE_7_MIGRATION.md`.

## First implementation slice after Phase 0

The recommended Phase 1 PR is intentionally small:

```text
repository skeleton
+ shared contracts
+ deterministic router interface
+ pytest/CI
+ evaluation case schema
```

Do **not** start by copying all source files. The first migrated behaviour should be a small, side-effect-free capability proving the contracts end to end.

## What the owner has asked the Agent to do

On 2026-09-24 the owner named five capabilities: a coding agent with a
harness, running Workflows and driving the computer's own tools, answering
questions from the Knowledge wiki, several agents on one machine each with
its own skills/model/memory, and a web interface to all of it.

`docs/AGENT_CAPABILITIES_REQUESTED.md` records the request, what already
exists, and the one thing that gates most of it: **no model is configured on
a company host at all today**. That file decides nothing; work appears in
`docs/TASKS.md` and architecture changes in `docs/ARCHITECTURE.md`.

## Open decisions for later phases

- exact agent runtime/SDK implementation;
- which business/event integrations justify enabling the optional n8n adapter;
- storage/index technology for knowledge retrieval;
- approval UX across Telegram/Web/other channels;
- deployment topology for gateway, Agent runtime and Host Bridge;
- when `customized_llm_proxy` can be formally archived after lineage/history verification.
