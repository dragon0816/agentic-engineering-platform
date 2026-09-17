# AGENTS.md

Instructions for coding agents and human contributors working in this repository.

## Mission

Build an agentic engineering platform without sacrificing deterministic reliability. Preserve proven behaviour from source repositories before refactoring it.

## Architectural rules

1. **Agent decides WHAT / WHY / WHICH.** Do not embed deterministic execution details in prompts when code/workflows can own them.
2. **Workflow defines HOW EXACTLY.** Repeatable engineering operations belong in deterministic workflows/jobs.
3. **n8n coordinates WHEN.** Use it for schedules, triggers, coarse orchestration and notifications; keep detailed business/engineering logic testable outside n8n.
4. **Skills are procedures and domain guidance.** They are not synonymous with Python functions.
5. **Tools are atomic executable capabilities.** Give them explicit input/output contracts and side-effect classification.
6. **MCP exposes capabilities.** It is an integration boundary, not a replacement for agent or workflow runtime.
7. **Knowledge owns grounded enterprise context.** Raw sources are immutable and provenance must survive transformation.
8. **Prefer deterministic routing.** Known commands and workflows must bypass LLM intent selection where possible.
9. **Bound agent loops.** On missing information, policy boundary or repeated failure, return a structured needs-input/failure state.
10. **Every new agent capability needs evaluation cases.** Every migrated deterministic behaviour needs regression tests.

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
