# Documentation index

One line per document. Completed phase plans, one-off reports and superseded proposals are
in [archive/](archive/); they are kept for history, not for current work.

## Start here (read before changing code)

| Document | What it is for |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | The implementation architecture |
| [PRODUCT_VISION.md](PRODUCT_VISION.md) | Product direction |
| [PRODUCT_ACCEPTANCE_TESTS.md](PRODUCT_ACCEPTANCE_TESTS.md) | The required E2E order and gates |
| [ROADMAP.md](ROADMAP.md) | Phases and their state |
| [TASKS.md](TASKS.md) | Progress record: what is done and what is next |
| [DECISIONS.md](DECISIONS.md) | Technical and owner decisions, with reasons |
| [REQUIREMENTS.md](REQUIREMENTS.md) | Active requirements |
| [CONTRACTS.md](CONTRACTS.md) | Foundation contract semantics |
| [../HANDOFF.md](../HANDOFF.md) | Where the current work stopped |

## Knowledge

| Document | What it is for |
|---|---|
| [phases/KNOWLEDGE_PIPELINE_RELEASE.zh-TW.md](phases/KNOWLEDGE_PIPELINE_RELEASE.zh-TW.md) | Release plan for convert, ingest, query and lint/conflict (K1–K6) |
| [phases/KNOWLEDGE_COLLAB.md](phases/KNOWLEDGE_COLLAB.md) | Multi-maintainer workflow: pull, benchmark, push |
| [../src/knowledge/skill_guide/GUIDE.zh-TW.md](../src/knowledge/skill_guide/GUIDE.zh-TW.md) | How to write ingest and answer skills (also shown on the Knowledge page), with templates |
| [phases/KNOWLEDGE_K1.md](phases/KNOWLEDGE_K1.md) | K1: the pipeline in the Agent, sandboxes |
| [phases/KNOWLEDGE_K2.md](phases/KNOWLEDGE_K2.md) | K2: layered bilingual index and its measurement |
| [phases/KNOWLEDGE_K3.md](phases/KNOWLEDGE_K3.md) | K3: vault rules, section-level writes, merge and publish |
| [phases/KNOWLEDGE_MULTI_ROUND_RETRIEVAL.md](phases/KNOWLEDGE_MULTI_ROUND_RETRIEVAL.md) | Model-directed search rounds for queries |
| [phases/E2E_05_KNOWLEDGE_EVOLUTION.md](phases/E2E_05_KNOWLEDGE_EVOLUTION.md) | Product gate E2E-05 |

## Proposals (awaiting owner review)

| Document | What it is for |
|---|---|
| [proposals/KNOWLEDGE_STRATEGY_v1.3.md](proposals/KNOWLEDGE_STRATEGY_v1.3.md) | **Current.** Knowledge Strategy v1.3 (awaiting owner review): BI Schema v1 from the real `bi_schema.py` (N1 resolved), the BI data-processing pipeline mapped onto Strategy = Workflow + Skills + Config, data-quality rules, Case A first flow, new ADR-K11 judgement fields and field-level provenance |
| [proposals/KNOWLEDGE_STRATEGY_v1.3_DIFF.md](proposals/KNOWLEDGE_STRATEGY_v1.3_DIFF.md) | What changed from v1.2 to v1.3 and why (including findings taken from the owner-shared Codex brief) |
| [proposals/bi_schema_v1/README.md](proposals/bi_schema_v1/README.md) | BI Schema v1 (`bi.schema/v1`, PoC contract) generated from `tests/fixtures/bi_vault_example/tools/bi_schema.py`, every name with its code line; v0 → v1 upcast |
| [proposals/knowledge_benchmark_v0/README.md](proposals/knowledge_benchmark_v0/README.md) | 25-question BD / Marketing benchmark draft on Schema v1 (unreviewed), supplemental SUP-01, and the separate 8-question vault-example set |
| [proposals/KNOWLEDGE_STRATEGY_v1.2.md](proposals/KNOWLEDGE_STRATEGY_v1.2.md) | Superseded by v1.3; kept for history |
| [proposals/KNOWLEDGE_STRATEGY_v1.2_DIFF.md](proposals/KNOWLEDGE_STRATEGY_v1.2_DIFF.md) | What changed from v1.1 to v1.2 and why, with the issue renumbering |
| [proposals/bi_schema_v0/README.md](proposals/bi_schema_v0/README.md) | BI Schema v0 from the BI Knowledge Base slides; superseded by v1, kept unchanged for history |
| [contracts/knowledge-api/README.md](contracts/knowledge-api/README.md) | Knowledge API contract v0.1 for Atlas: OpenAPI 3.1, JSON Schemas, synthetic mock data |
| [proposals/KNOWLEDGE_STRATEGY_v1.1.md](proposals/KNOWLEDGE_STRATEGY_v1.1.md) | Superseded by v1.2; kept for history |
| [proposals/K01_AS_IS_GAP_ANALYSIS.md](proposals/K01_AS_IS_GAP_ANALYSIS.md) | K01 audit behind v1.1, including the Knowledge tool-path investigation |
| [proposals/KNOWLEDGE_STRATEGY_v1.1_DIFF.md](proposals/KNOWLEDGE_STRATEGY_v1.1_DIFF.md) | What changed from v1.0 to v1.1 and why |
| [proposals/KNOWLEDGE_STRATEGY_v1.0_original.md](proposals/KNOWLEDGE_STRATEGY_v1.0_original.md) | The original v1.0 proposal, verbatim |

## Harness and authoring

| Document | What it is for |
|---|---|
| [HARNESS_DESIGN.zh-TW.md](HARNESS_DESIGN.zh-TW.md) | Harness design for review |
| [HARNESS_6_LAYER_STATUS.md](HARNESS_6_LAYER_STATUS.md) | Six-layer harness status |
| [phases/HARNESS_6_LAYER_INCREMENTAL.md](phases/HARNESS_6_LAYER_INCREMENTAL.md) | Six-layer harness plan |
| [phases/HARNESS_UNIFICATION.md](phases/HARNESS_UNIFICATION.md) | One harness skeleton, domains as Skills and adapters |
| [phases/EXPERIENCE_REVIEW.md](phases/EXPERIENCE_REVIEW.md) | Learning from use: failures become reviewed, versioned proposals (design) |
| [phases/COPILOT_INTEGRATION.md](phases/COPILOT_INTEGRATION.md) | GitHub Copilot as an agent mode using AEP's tools |
| [phases/CODING_ON_BRIDGE.md](phases/CODING_ON_BRIDGE.md) | Coding on the Bridge |
| [phases/CONVERSATIONAL_AUTHORING.md](phases/CONVERSATIONAL_AUTHORING.md) | Conversational authoring and candidates |
| [phases/EXTERNAL_AUTHORING.md](phases/EXTERNAL_AUTHORING.md) | External coding agents author Skills and Workflows |
| [phases/NL_WORKFLOW_AUTHORING.md](phases/NL_WORKFLOW_AUTHORING.md) | Natural-language Workflow authoring |
| [phases/SOP_TO_WORKFLOW.md](phases/SOP_TO_WORKFLOW.md) | SOP to Workflow |
| [phases/ASSET_OWNERSHIP.md](phases/ASSET_OWNERSHIP.md) | Asset ownership and versions |

## Product gates and productization

| Document | What it is for |
|---|---|
| [phases/E2E_01_DUT_ENGINEERING.md](phases/E2E_01_DUT_ENGINEERING.md) … [E2E_04](phases/E2E_04_SOFTWARE_EVOLUTION.md) | Product gates E2E-01 to E2E-04 |
| [phases/PRODUCTIZATION_1_AGENT_WEB_MARKETPLACE.md](phases/PRODUCTIZATION_1_AGENT_WEB_MARKETPLACE.md) … [5](phases/PRODUCTIZATION_5_AGENT_WEB_EXPERIENCE.md) | Productization stages 1–5 |

## Migration and workflows

| Document | What it is for |
|---|---|
| [phases/PHASE_7_MIGRATION.md](phases/PHASE_7_MIGRATION.md), [PHASE_7_MIGRATION.md](PHASE_7_MIGRATION.md) | Active Phase 7 migration: plan and source decisions |
| [PHASE_2_MIGRATION.md](PHASE_2_MIGRATION.md) … [PHASE_6_MIGRATION.md](PHASE_6_MIGRATION.md) | Source decisions of Phases 2–6 (referenced by code and tests) |
| [SOURCE_REPOSITORIES.md](SOURCE_REPOSITORIES.md) | Source repositories to check before re-implementing |
| [phases/RS_WORKFLOW_MIGRATION.md](phases/RS_WORKFLOW_MIGRATION.md) | rs_workflow_system migration |
| [WORKFLOW_7_SOURCE_CONTRACT.md](WORKFLOW_7_SOURCE_CONTRACT.md), [WORKFLOW_10_HOST.md](WORKFLOW_10_HOST.md), [WORKFLOW_13_SOURCE_CONTRACT.md](WORKFLOW_13_SOURCE_CONTRACT.md), [WORKFLOW_CHECKPOINTS.md](WORKFLOW_CHECKPOINTS.md) | Per-workflow contracts and checkpoints |

## Operations and integrations

| Document | What it is for |
|---|---|
| [telemetry/AEP_ATLAS_TELEMETRY_CONTRACT.md](telemetry/AEP_ATLAS_TELEMETRY_CONTRACT.md) | Telemetry contract with Atlas (v0.3) |
| [shared-platform-preview.md](shared-platform-preview.md) | Shared Platform reference process |
| [deployment-validation-loop.md](deployment-validation-loop.md) | Deployment validation loop |
| [remote-testing-codex-loop.md](remote-testing-codex-loop.md) | Remote testing and local Codex repair loop |
| [JEV_ADAPTER_READINESS.md](JEV_ADAPTER_READINESS.md) | JEV adapter readiness audit |
| [phases/LAYA_ACCELERATION.md](phases/LAYA_ACCELERATION.md) | Where Laya decisions could save time; on hold for shadow data |
