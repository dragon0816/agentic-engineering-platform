# Phase 1 — Foundation Specification

## Goal

Create the smallest typed, testable and side-effect-free foundation that proves the architecture can support a multi-user, contribution-driven platform without committing to a concrete LLM provider, UI, registry database or production execution backend.

## Scope

Phase 1 establishes repository structure, shared contracts, one Engineering Agent profile contract, deterministic routing interfaces, model abstraction contracts, registry interfaces, Bridge/worker advertisement contracts, evaluation case schema, tests and CI.

Do not migrate production implementations from source repositories in this phase.

## Required contracts

Implement minimal typed contracts for:

- `RequestContext`
- `RouteDecision`
- `CapabilitySpec`
- `CapabilityResult`
- `WorkflowRun`
- `ApprovalRequest`
- `KnowledgeSource`
- `TaskManifest`
- `WorkflowManifest`
- `AgentProfile`
- registry asset metadata
- Bridge/worker registration and capability advertisement
- model request/response and model requirement abstractions
- evaluation case schema
- trace identifiers

Registry asset metadata must support owner/contributors, semantic version, lifecycle, provenance/source, dependencies, compatibility, permission/approval classification, validation/evaluation references and deprecation/replacement metadata where applicable.

## Architecture constraints

- Team Platform Plane is the shared control plane.
- Personal Engineering / Execution Plane hosts the normal Personal Engineering Agent and Bridge.
- Registry/distribution and execution authorization are separate.
- Bridge contracts describe execution capabilities but Phase 1 performs no production side effects.
- Known deterministic routes bypass LLM reasoning.
- Platform modules depend on provider-neutral model contracts.
- Phase 1 defines one `engineering` Agent Profile; specialist agents are extension points only.
- n8n integration is not required.
- Normal contribution of Tasks/Workflows/Skills/Knowledge must not require modifying the core runtime.

## First vertical proof

Provide one side-effect-free sample Task represented by a `TaskManifest`, register it in an in-memory registry, discover it by contract, advertise it from a sample Bridge/worker registration and verify behavior through tests.

This proof demonstrates the control-plane/execution-plane contracts without building a production registry or Bridge runtime.

## Required engineering quality

- Python package installs cleanly.
- pytest coverage exists for shared contracts and the first vertical proof.
- lint and type checking are configured.
- CI runs the same verification.
- no live credentials or production side effects.
- public contracts have concise documentation.
- failures are explicit and typed where practical.

## Out of scope

- production database/registry service;
- Web/Desktop UI;
- real DUT/instrument control;
- full Personal Agent reasoning loop;
- specialist multi-agent implementation;
- n8n integration;
- production model provider integration;
- source-repository big-bang migration.

## Exit criteria

Phase 1 is complete when the skeleton installs, CI passes, contracts are documented and tested, the sample Task is discoverable through an in-memory Registry, a Bridge can advertise it through typed contracts, model interfaces remain provider-neutral, and no production side effect is required.
