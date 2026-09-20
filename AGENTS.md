# AGENTS.md

Instructions for coding agents and human contributors working in this repository.

## Mission

Build a multi-user, contribution-driven agentic engineering platform without sacrificing deterministic reliability. Preserve proven behaviour from source repositories before refactoring it. Team members must be able to develop, validate, publish, discover, reuse and evolve Tasks, Workflows, Skills, Knowledge and Agent profiles without requiring changes to the core runtime.

## Architectural rules

1. **Agent decides WHAT / WHY / WHICH.** Do not embed deterministic execution details in prompts when code/workflows can own them.
2. **Workflow defines HOW EXACTLY.** Repeatable engineering operations belong in deterministic workflows/jobs.
3. **n8n is optional event/business automation integration.** Use it for schedules, triggers, coarse orchestration and notifications when useful; Agent, n8n and CLI must call the same underlying Workflow/Capability contracts. Keep detailed engineering logic outside n8n.
4. **Skills are procedures and domain guidance.** They are not synonymous with Python functions.
5. **Tools are atomic executable capabilities.** Give them explicit input/output contracts and side-effect classification.
6. **MCP exposes capabilities.** It is an integration boundary, not a replacement for agent or workflow runtime.
7. **Knowledge owns grounded enterprise context.** Raw sources are immutable and provenance must survive transformation.
8. **Prefer deterministic routing.** Known commands and workflows must bypass LLM intent selection where possible.
9. **Bound agent loops.** On missing information, policy boundary or repeated failure, return a structured needs-input/failure state.
10. **Every new agent capability needs evaluation cases.** Every migrated deterministic behaviour needs regression tests.
11. **Contributions are first-class platform assets.** Tasks, Workflows, Skills, Knowledge and Agent profiles need stable manifests/contracts so they can evolve without core-runtime changes.
12. **Registry is control plane, Bridge is execution plane.** Publishing/discovery/versioning are centralized concerns; local Bridges/workers execute capabilities near required resources.
13. **Publishing does not grant execution permission.** Distribution, authorization and approval are separate concerns.
14. **Shared assets are governed.** Require owner, version, lifecycle, dependencies, compatibility and permission metadata appropriate to the asset type.

## Migration rules

- The source repositories are reference implementations. Do not modify them as part of this repository's migration.
- Before migrating a component, document its current contract/invariants and add tests for behaviour that must survive.
- Prefer adapters around proven components before rewriting them.
- Never copy two overlapping implementations merely because they exist in two source repositories; identify lineage and choose one source of truth.
- Each migration PR should be narrow, reversible and independently testable.
- Do not start a broad refactor in the same PR that first establishes behavioural coverage.

## Safety / side effects

Classify capabilities as `read`, `write`, `execute`, or `external_side_effect`. Destructive, release, deployment, message-sending, production, credential and external-system write operations require an explicit approval policy. Do not let an LLM silently bypass tests, approval gates, version rules or protected release semantics.

Secrets must come from environment variables, secret stores or runtime configuration. Never commit live tokens, passwords, bot tokens, JWTs or API keys. Logs/traces must redact them.

## Knowledge rules

Target pipeline:

```text
Drop -> Document Processor -> Raw Markdown -> Curation -> Wiki -> Retrieval
```

Drop contains originals. Raw preserves extracted text/tables/images plus source file and page/slide relationships. Wiki is curated knowledge. Do not allow the curation layer to become the only copy of source evidence. Conflicts and human decisions must be persisted so later ingestion does not reintroduce rejected claims.

## Definition of done for a migrated capability

A migration is not complete because code was copied. It is complete when the contract is explicit, tests/evaluation pass, observability exists, failure behaviour is defined, required approvals are enforced, and the source implementation can be deprecated without losing a verified capability.


## Coding-agent-neutral development workflow

Codex, Claude Code and human contributors are replaceable workers. GitHub and committed repository artifacts are the persistent project state; never rely on one coding agent's conversation history.

Required implementation sequence:

```text
Architecture -> Requirements -> Contracts -> Tests -> Implementation
             -> Verification -> Commit -> Handoff
```

Before modifying implementation code, read `ARCHITECTURE.md`, `docs/MIGRATION_PLAN.md`, the active phase specification and `HANDOFF.md`.

Use repository procedures under `.agents/skills/`:
- `architecture-guard` before implementation or architectural changes;
- `implementation-planning` to convert requirements into small implementation slices;
- `contract-development` for shared platform contracts;
- `code-change-verification` before completion/commit/handoff;
- `migration` when adapting source-repository behavior;
- `handoff` whenever ownership may transfer between Codex, Claude Code or a human.

`CLAUDE.md` is the Claude Code entry point and must remain aligned with these shared rules. Do not create a separate architecture or workflow specifically for one coding agent.
