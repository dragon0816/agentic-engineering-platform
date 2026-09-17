# Agentic Engineering Platform — Architecture

Status: Phase 0 draft

## 1. Purpose

This repository unifies the proven capabilities currently spread across five source repositories without blindly merging their implementations. The target is an engineering platform in which AI reasoning is used where judgement is needed, while deterministic execution remains deterministic.

Core rule:

> Agent decides **WHAT / WHY / WHICH**. Workflow defines **HOW EXACTLY**. n8n coordinates **WHEN**. Skills teach **HOW TO REASON/PROCEED**. Tools perform atomic actions. MCP exposes capabilities. Knowledge provides grounded context. Evaluation proves behaviour remains acceptable.

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
                                              |
                                      +-------v-------+
                                      | Tool / MCP    |
                                      | Capability    |
                                      +-------+-------+
                                              |
                         +--------------------+------------------+
                         |                    |                  |
                    Host Bridge          APIs/Git          Office/DUT/etc.

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

## 4. Platform boundaries

### Agent platform
Owns conversation/request context, intent resolution, planning, tool selection, bounded reasoning loops, approvals and agent lifecycle. It must not embed Windows/Office automation or workflow-specific business logic.

### Skills
Human- and model-readable procedures, domain rules, constraints, examples and acceptance criteria. A skill is not the executable implementation. Skills may reference tools/workflows but should not hide side effects.

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

### Model gateway
Provider abstraction and company/internal-model access belong in infrastructure, separate from knowledge and evaluation. The existing LiteLLM gateway is a migration source for this boundary.

### Evaluation / harness
Owns benchmark cases, expected outcomes, graders, regression tests and trace-based quality checks. Every new agent capability requires evaluation coverage. Deterministic workflow tests and probabilistic agent evaluation are separate test classes.

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
│   ├── gateway/
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
3. Side-effecting operations must have explicit policy and approval classification.
4. Workflows must be independently executable/testable where practical.
5. Raw knowledge is immutable; generated/curated knowledge preserves provenance.
6. Secrets never live in committed configuration.
7. New capabilities require regression/evaluation cases.
8. Migration is incremental; do not perform a five-repository big-bang merge.
9. Observability must record route/plan/tool/workflow outcome without logging secrets.
10. Agent loops are bounded and must surface a structured failure/needs-input result rather than spin indefinitely.

## 8. Migration strategy

Phase 0: architecture, contracts, migration inventory.

Phase 1: common contracts + platform skeleton + CI/evaluation baseline.

Phase 2: agent runtime/routing/skills/tools/MCP.

Phase 3: deterministic workflow + Host Bridge integration.

Phase 4: knowledge Drop -> Raw -> Wiki, including multimodal ingestion/provenance.

Phase 5: model gateway and external integrations.

Phase 6: guardrails, approvals, tracing and full evaluation harness.

Phase 7: end-to-end validation and controlled deprecation of source repositories.
