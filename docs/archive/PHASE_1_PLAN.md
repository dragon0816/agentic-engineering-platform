# Phase 1 implementation plan

Architecture review: preserve the approved control/execution split. The active phase
specification limits this slice to contracts and a side-effect-free proof; no reasoning
loop, provider adapter, execution backend or source production migration is included.

## Requirements and slices

1. Establish the `src/common`, `src/agent`, `src/capabilities`, `src/workflow`,
   `src/knowledge`, `src/models` package boundaries, packaging and verification tools.
2. Document contract semantics; write validation/round-trip/invariant tests; implement
   provider-neutral governance, execution, model, evaluation and trace contracts.
3. Write Registry/proof tests; implement exact-version, in-memory Task discovery and
   explicit Bridge advertisement. No callable loading, execution or secret resolution.
4. Verify installation, full pytest, Ruff and strict mypy locally and in CI; commit
   coherent slices; update HANDOFF and open a PR against main without merging.

Acceptance follows `docs/phases/PHASE_1_FOUNDATION.md`. Tests cover ambiguous identity,
invalid nested metadata, secrets, central dependencies, distinct review layers and
publication without authorization. Fixtures represent a read-only sample and one
engineering profile. Public interfaces and limitations live in `docs/CONTRACTS.md`.

## Source-first decisions

Inspected on 2026-09-20 via read-only GitHub API:

- `telegram-local-agent` tree `4b40a215909e4fdd4b65519d70669a84e9abd43d`:
  `core/task_router.py` tries dot commands, then keyword routes, then Ollama parsing;
  `core/tool_registry.py` imports callables and invokes sync/async tools. **ADAPT** the
  deterministic-before-model boundary as a protocol only. **REWRITE** Registry metadata
  storage as a tiny in-memory proof because the source registry loads executable code,
  lacks scoped/versioned governance, and is an execution-plane component. No source
  routing/execution behavior is replaced; characterization of those implementations
  remains mandatory before Phase 2 migration.
- `rs_workflow_system` tree `896046e8fe2170d21f9213e56e5ce2f93c05ba43`:
  `host-bridge/app/models.py` returns `ok/data/warnings` envelopes;
  `app/routers/jobs.py` separates request routing from jobrunner;
  `app/services/workflow_deps.py` reports unresolved dependencies and excludes real
  secret-bearing config from bundles. **ADAPT** boundary semantics into typed results,
  explicit dependencies and SecretRef metadata; no jobrunner, HTTP routes, filesystem
  resolver or production jobs are copied. Tests assert explicit dependencies and
  secret-reference-only manifests; these are architecture tests, not source parity.
- `knowledge_management` tree `2f5e6d0431c5b6af8fbee05c6c0a5779e1a84bb9`:
  inspected `agent/agent.py` model/tool-call boundary and `bench/run.py` evaluation
  flow. **ADAPT** only neutral request/result and evaluation intent; provider wire
  formats, subprocess evaluation and gateway code remain deferred to their phases.
  No duplicate lineage from `customized_llm_proxy` or n8n prototypes is imported.

Rollback is removal of the new foundation modules; all source repositories remain
unchanged. No migrated production behavior is claimed or deprecated.
