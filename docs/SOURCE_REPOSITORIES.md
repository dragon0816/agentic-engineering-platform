# Source Repositories

These repositories are reference implementations for capabilities that already exist. Before implementing a capability that overlaps with one of these sources, inspect the source and preserve proven behavior rather than independently reinventing it.

## dragon0816/telegram-local-agent

**Role:** Personal/local agent reference implementation.

**Reuse candidates:** deterministic-first routing; Skill and Tool registries; MCP registry; Ollama integration; Telegram/browser channels; file handling; bounded/background task patterns.

**Target:** Phase 2 — Agent and capability layer.

**Default strategy:** ADAPT / MIGRATE. Characterize existing behavior before rewriting.

## dragon0816/rs_workflow_system

**Role:** Deterministic engineering workflow and Windows Host Bridge reference implementation.

**Reuse candidates:** Host Bridge; router/service/job separation; Windows-local execution; PowerShell; Office/COM; browser automation; deterministic jobs; progress/status patterns; workflows independently executable from n8n.

**Target:** Phase 3 — Workflow platform.

**Default strategy:** PRESERVE + ADAPT. Prefer wrappers/adapters around proven components before replacement.

## dragon0816/n8n_work_flow

**Role:** Historical workflow prototypes and event/business automation reference.

**Reuse candidates:** workflow intent; schedules/triggers; notifications; SaaS/integration patterns; local model/n8n experiments.

**Target:** Phase 3 — optional n8n integration.

**Default strategy:** SELECTIVE MIGRATION. Do not make n8n a mandatory execution layer and do not copy obsolete parallel implementations.

## dragon0816/knowledge_management

**Role:** Knowledge ingestion, model gateway, coding-agent and benchmark reference implementation.

**Reuse candidates:** Drop -> Raw -> Wiki concepts; immutable raw data; dry-run/apply separation; backups; provenance; conflict decisions; lint/evaluation; LiteLLM/company gateway patterns.

**Target:** Phase 4 — Knowledge; Phase 5 — model/provider integration; Phase 6 — evaluation where applicable.

**Default strategy:** PRESERVE SAFETY INVARIANTS + DECOMPOSE by platform boundary. Known gaps such as image handling/query should be addressed explicitly rather than hidden by migration.

## dragon0816/customized_llm_proxy

**Role:** Overlapping model gateway/agent/knowledge lineage.

**Reuse candidates:** provider compatibility behavior only where history proves it differs from `knowledge_management`.

**Target:** Phase 5.

**Default strategy:** VERIFY LINEAGE FIRST. Do not duplicate overlapping code merely because it exists in a separate repository.

## Mandatory source-first decision

Before implementing an overlapping capability:

1. Identify the source repository and relevant implementation.
2. Inspect its contracts, tests, behavior and known invariants.
3. Add characterization/regression coverage for behavior that must survive.
4. Record a decision: **REUSE**, **WRAP**, **ADAPT**, **MIGRATE**, or **REWRITE**.
5. Prefer the smallest reversible path.
6. Only rewrite when there is a documented architectural or quality reason.
7. Verify parity before deprecating the source path.

Source repositories remain unchanged during migration unless a separate explicit task authorizes changes to them.
