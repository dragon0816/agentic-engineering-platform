# Migration Plan

Status: Phase 1 foundation

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

Define the first Platform Registry contracts for contribution lifecycle: owner, semantic version, lifecycle state (`draft`, `validated`, `published`, `deprecated`), dependencies, compatibility, permissions/approval classification and discoverability. Define Bridge/worker registration contracts so execution nodes can advertise installed capabilities and local resources. Registry/distribution must remain separate from execution authorization.

Before implementation migration, add characterization tests around selected source behaviours.

Exit criteria: skeleton installs cleanly; CI passes; contracts are documented; a side-effect-free sample Task can be represented by a manifest and discovered through an in-memory registry; Bridge/worker capability advertisement has a typed contract; no production side effects.

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

Preserve immutable raw/source semantics, dry-run/apply separation, backups, source provenance, conflict decisions and static lint. Add the currently missing query layer and image-aware ingestion.

Exit criteria: PDF/PPT/DOCX sample corpus round-trips to Raw with traceable source/page/slide/image relationships; Wiki generation cannot mutate Raw; query answers can cite source provenance.

## Phase 5 — Model gateway

Extract the LiteLLM/company-model gateway from the mixed knowledge repository into `src/gateway/` or a separately deployable package under this repo. Keep provider-specific patches isolated. Agent/knowledge/evaluation consume a model interface rather than importing gateway internals.

Exit criteria: at least local Ollama and the internal OpenAI-compatible gateway can satisfy the same model client interface; credentials are externalized.

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

## Phase 7 — End-to-end migration and deprecation

Run representative production-like scenarios against old and new paths. Deprecate source components only after parity/acceptance criteria are met. Keep rollback documentation during transition.

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

## Open decisions for later phases

- exact agent runtime/SDK implementation;
- which business/event integrations justify enabling the optional n8n adapter;
- storage/index technology for knowledge retrieval;
- approval UX across Telegram/Web/other channels;
- deployment topology for gateway, Agent runtime and Host Bridge;
- when `customized_llm_proxy` can be formally archived after lineage/history verification.
