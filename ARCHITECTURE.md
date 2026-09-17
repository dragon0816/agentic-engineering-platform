# Agentic Engineering Platform — Architecture

Status: Phase 0 draft

## 1. Purpose

This repository unifies the proven capabilities currently spread across five source repositories without blindly merging their implementations. The target is an engineering platform in which AI reasoning is used where judgement is needed, while deterministic execution remains deterministic.

Core rule:

> Agent decides **WHAT / WHY / WHICH**. Workflow defines **HOW EXACTLY**. n8n coordinates **WHEN**. Skills teach **HOW TO REASON/PROCEED**. Tools perform atomic actions. MCP exposes capabilities. Knowledge provides grounded context. Models are replaceable infrastructure. Evaluation proves behaviour remains acceptable.

## 2. Target architecture

```text
User / Telegram / Web UI / Event
              |
              v
+-------------------------------+
| Agent Gateway                 |
| intent / planning / context   |
| policy / approval / tracing   |
+---------------+---------------+
                |
      +---------+---------+------------------+
      |                   |                  |
      v                   v                  v
+-----------+       +-----------+      +------------+
| Knowledge |       | Skills    |      | Workflows  |
| retrieval |       | procedure |      | deterministic|
+-----------+       +-----------+      +------+-----+
      |                 |                     |
      +--------+--------+                     |
               |                              |
               v                              v
       +---------------+              +---------------+
       | Model Router  |              | Tool / MCP    |
       +-------+-------+              | Capability    |
               |                      +-------+-------+
        +------+------+                       |
        |      |      |          +-------------+----------------+
        v      v      v          |             |                |
     OpenAI  Ollama  Company  Host Bridge   APIs/Git      Office/DUT/etc.
      /other  local   gateway

Cross-cutting: Evaluation · Guardrails · Observability · Configuration · Secrets
```

## 3. Routing policy

```text
Request
  |-- known command / exact tool --> deterministic dispatch
  |-- known workflow -------------> workflow engine
  `-- ambiguous / complex --------> agent reasoning
```

Do not put an LLM in front of operations that already have a reliable deterministic route. This preserves the strongest property already present in `telegram-local-agent`: cheap deterministic routing before LLM parsing.

Request routing and model routing are separate decisions. The Agent Gateway decides whether reasoning is needed and which capability/workflow should own the request. Only when a model call is required does the Model Router choose a model that satisfies the task requirements and policy.

## 4. Platform boundaries

### Agent platform
Owns conversation/request context, intent resolution, planning, tool selection, bounded reasoning loops, approvals and agent lifecycle. It must not embed Windows/Office automation, provider-specific model APIs or workflow-specific business logic.

### Skills
Human- and model-readable procedures, domain rules, constraints, examples and acceptance criteria. A skill is not the executable implementation. Skills may reference tools/workflows but should not hide side effects. Skills may declare model capability requirements such as reasoning level, tool calling, vision, context size or local-only processing; they should not normally hard-code a specific provider/model.

### Tools
Atomic executable capabilities with typed inputs/outputs and explicit side-effect classification. Tools should be independently testable. Existing plain async tool functions are a useful migration source, but their contracts should become explicit.

### MCP
Capability exposure/discovery boundary. MCP is not the workflow engine and not the agent itself. Existing MCP registry/server work should migrate behind the tool/capability layer.

### Workflow platform
Owns deterministic multi-step execution, retry/idempotency, progress, state and resumability. Existing Host Bridge remains a first-class infrastructure capability because container/agent runtimes cannot replace Windows COM, authenticated browser profiles or local hardware access.

### n8n
Event/business orchestration: schedules, triggers, coarse branching, notifications and integration glue. Do not move detailed engineering logic into n8n nodes when it can live in testable workflow/jobs code.

### Knowledge platform
Owns Drop -> Raw -> Wiki and retrieval. Raw sources are immutable. Document ingestion must preserve provenance. Phase 1+ should extend ingestion to extract text, tables and images from PDF/PPT/DOCX and preserve page/slide/image relationships in Raw Markdown before curation into Wiki.

### Model interface
The rest of the platform depends on one provider-neutral model contract rather than directly importing OpenAI, Ollama, LiteLLM or another provider SDK. The contract should represent platform needs such as text generation, structured output, tool calling, streaming and multimodal input without leaking provider-specific request objects into agent/knowledge code.

### Model router
Chooses a model only when a model is actually required. Selection is based on declared requirements and policy, for example:

```yaml
requirements:
  reasoning: high
  tool_calling: true
  vision: false
  local_only: true
```

Routing policy may additionally consider availability, latency, cost/quota, privacy/data classification and evaluation results. Model routing must be observable so evaluations can compare providers/models for the same cases.

### Provider adapters / model gateway
Provider adapters implement the common model interface for OpenAI-compatible APIs, Ollama, company/internal gateways and future providers. Provider-specific authentication, wire formats and compatibility workarounds stay here. The existing LiteLLM gateway is a migration source, not the abstraction consumed directly by the rest of the platform.

A provider/model change should normally be configuration, not a code change in Agent, Skill, Workflow or Knowledge.

Example configuration:

```yaml
models:
  local_reasoning:
    provider: ollama
    model: qwen3:8b
    capabilities: [text, tools]
    local_only: true

  company_reasoning:
    provider: company_gateway
    model: gpt-5.5
    capabilities: [text, tools, structured_output]

  cloud_coding:
    provider: openai
    model: <configured-model>
    capabilities: [text, tools, structured_output]

routes:
  default: local_reasoning
  coding: cloud_coding
  knowledge: company_reasoning
```

Configuration names such as `cloud_coding` are stable logical aliases; concrete model IDs may change without changing callers.

### Evaluation / harness
Owns benchmark cases, expected outcomes, graders, regression tests and trace-based quality checks. Every new agent capability requires evaluation coverage. Deterministic workflow tests and probabilistic agent evaluation are separate test classes. Model evaluation should be able to run the same case set across multiple configured model aliases and compare quality, latency, reliability and usage/cost without changing the Agent implementation.

## 5. Proposed repository layout

```text
agentic-engineering-platform/
├── AGENTS.md
├── ARCHITECTURE.md
├── README.md
├── pyproject.toml
├── src/
│   ├── agent/
│   │   ├── runtime/
│   │   ├── routing/
│   │   ├── guardrails/
│   │   └── approvals/
│   ├── capabilities/
│   │   ├── tools/
│   │   └── mcp/
│   ├── workflow/
│   │   ├── engine/
│   │   ├── jobs/
│   │   └── host_bridge/
│   ├── knowledge/
│   │   ├── ingestion/
│   │   ├── processing/
│   │   └── retrieval/
│   ├── models/
│   │   ├── interface/
│   │   ├── router/
│   │   └── providers/
│   │       ├── ollama/
│   │       ├── openai_compatible/
│   │       └── company_gateway/
│   └── common/
├── skills/
├── workflows/
├── knowledge/
│   ├── drop/
│   ├── raw/
│   └── wiki/
├── evaluation/
│   ├── cases/
│   ├── graders/
│   ├── model_comparison/
│   └── regression/
├── integrations/
│   └── n8n/
├── docs/
└── tests/
```

`skills/`, `workflows/` and `knowledge/` deliberately live outside Python package code so operational/domain content can evolve without requiring application-code changes.

## 6. Source-system findings

### telegram-local-agent
Strong migration candidates: deterministic-first three-tier routing, skill registry, tool registry, MCP registry, channel abstraction, file handling and local Ollama support. Its own project brief explicitly warns against replacing deterministic routes with an LLM-first pipeline. Main refactor: separate channel/runtime concerns from capability contracts and add formal tests/guardrails.

### rs_workflow_system
Strong migration candidates: Host Bridge, service/job separation, workflow API contracts, offline deployment patterns and deterministic job execution. Its architecture already enforces a valuable boundary: n8n handles control flow while Windows-local capabilities are exposed through Host Bridge; jobs can run independently of n8n. Preserve this principle.

### n8n_work_flow
Treat primarily as workflow prototypes and integration knowledge. It contains local-Ollama/n8n agent experiments and concrete business automations. Migrate reusable workflow intent and integration adapters, not every historical script/node verbatim. Prefer the newer Host Bridge boundary where overlapping approaches exist.

### knowledge_management
Current repository contains multiple concerns: model gateway, coding agent, benchmark suite and Obsidian knowledge ingestion. The vault implementation has valuable safety properties: immutable raw data, dry-run default, backups, whole-plan validation, provenance via `source_path`, explicit conflict decisions, static lint and model-assisted lint. Known gap: images in raw are ignored and query is not implemented.

### customized_llm_proxy
At the inspected `main` revision its repository tree SHA matches `knowledge_management`, and the visible content is effectively the same combined gateway/agent/bench/vault codebase. Treat it as overlapping lineage until commit history establishes a reason to preserve a separate implementation. Do not duplicate it into the new platform.

## 7. Non-negotiable engineering rules

1. Existing source repositories remain unchanged during migration until replacement behaviour is validated.
2. Deterministic routes take precedence over LLM reasoning.
3. Agent/Skill/Workflow/Knowledge code must not depend directly on a concrete LLM provider SDK; use the model interface.
4. Model selection is policy/configuration driven and observable; logical model aliases are preferred over hard-coded model IDs.
5. Side-effecting operations must have explicit policy and approval classification.
6. Workflows must be independently executable/testable where practical.
7. Raw knowledge is immutable; generated/curated knowledge preserves provenance.
8. Secrets never live in committed configuration.
9. New capabilities require regression/evaluation cases.
10. Migration is incremental; do not perform a five-repository big-bang merge.
11. Observability must record route/plan/model/tool/workflow outcome without logging secrets.
12. Agent loops are bounded and must surface a structured failure/needs-input result rather than spin indefinitely.

## 8. Migration strategy

Phase 0: architecture, contracts, migration inventory.

Phase 1: common contracts + **model interface/router/provider adapter contracts** + platform skeleton + CI/evaluation baseline.

Phase 2: agent runtime/routing/skills/tools/MCP using the provider-neutral model interface.

Phase 3: deterministic workflow + Host Bridge integration.

Phase 4: knowledge Drop -> Raw -> Wiki, including multimodal ingestion/provenance through model capability requirements rather than a hard-coded vision provider.

Phase 5: provider adapters/model gateway and external integrations.

Phase 6: guardrails, approvals, tracing and full evaluation harness, including cross-model comparison.

Phase 7: end-to-end validation and controlled deprecation of source repositories.
