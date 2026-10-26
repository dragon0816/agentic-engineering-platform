# AEP Multi-Agent Auto Discovery: development plan and review brief (v0, source)

> **Source.** The owner's plan, drafted with ChatGPT and handed over on 2026-10-26, recorded verbatim as the
> input to the Phase 0 review. It is **not** a verified assessment of the repository.
>
> **Status.** Proposal, review required.
>
> **Reviewed by.** `docs/proposals/MULTI_AGENT_PHASE0_REVIEW.md`.

**Owner:** Leo
**Target repository:** dragon0816/agentic-engineering-platform
**Scope:** Session, Agent Registry, Auto Discovery, Orchestrator, Model/Gateway Profiles, permissions, observability.

## 1. Goals and non-goals

### Goals

- Users define, version, discover and reuse specialist Agent Definitions.
- A Session owns conversations. Each Run records its execution and can choose direct execution, sub-agent delegation or workflow orchestration.
- Agents share the existing AEP runtime primitives, while each agent can have its own context, model, tool, skill and validation policies.
- Auto Discovery chooses eligible agents based on declared capabilities, availability, performance and permissions, with no privilege escalation.
- Several gateways (on-premises and cloud) are supported through profiles, without embedding secrets in definitions.
- Multi-user and multi-bridge operation is supported, with explicit device and resource authorization and traceable outcomes.

### Non-goals (V1)

- Rewriting the existing six-layer Harness or replacing the existing workflow engine.
- Unbounded recursive agent spawning, or production agents registering themselves.
- Automatic PR merges, unapproved external transmission of internal data, or unapproved physical instrument control.
- Assuming Hermes or Muse feature parity without validating the upstream implementations.

## 2. Mandatory discovery and review before coding

Inspect:

- `AGENTS.md`, `CLAUDE.md`, `ARCHITECTURE.md`, `docs/phases/`;
- application entry points and Session/Run storage;
- the six-layer Harness, intent and skill routing, and the Skill Registry;
- MCP integration, Bridge adapters, the model gateway and the workflow engine;
- auth/policy, telemetry, CI and tests.

Verify the actual paths rather than assuming these names exist.

Deliver a current-state architecture map with file paths and line references for each identified component. Prepare a reuse/gap matrix (existing, extend, new, defer) and an ADR comparing:

1. direct Tool/Skill execution, sub-agent delegation and workflow;
2. a persistent Agent Definition and an ephemeral Agent Instance;
3. per-agent model policy and gateway routing;
4. the multi-user permission model and resource-level checks;
5. context and artifact isolation, and delegation depth and limits.

**Stop at Gate 0.** Submit the review findings and recommended ADRs to Leo. Do not modify the core runtime, Bridge contracts, permissions or public APIs before approval. Small read-only probes and isolated tests are allowed.

## 3. Proposed logical architecture (subject to review)

```
User / Agent Web -> Session Manager -> Run / Execution Strategy Router
  -> Direct: existing Harness
  -> Delegation Orchestrator -> Agent Discovery + Registry -> Policy Eligibility Filter
     -> Candidate Ranker -> Ephemeral Agent Instances -> shared AEP Harness
  -> existing Workflow Engine -> shared AEP Harness
Harness -> existing Tool Abstraction -> MCP | Bridge
Harness -> Model / Gateway Router
Session, Orchestrator, Harness -> Audit / Telemetry / Atlas
```

These terms are distinct:

- A Session is not the Orchestrator.
- An Agent Definition is not an Agent Instance.
- Skills are reusable instructions and capabilities; Tools are callable operations.
- MCP and Bridge are integration and execution paths, not alternatives to Skills.
- The Registry is discovery metadata, not an authorization authority.

## 4. Candidate data contracts (validate against the current code)

- **AgentDefinition:** id, version, owner, visibility, status, description, domains, capabilities, skill_refs, tool_refs, model_policy_ref, context_policy, validation_policy, requested_permissions, resource_limits, created_at, updated_at.
- **Session:** session_id, user_id, tenant/team_id, mode, context_refs, created_at.
- **Run:** run_id, session_id, request, strategy, plan, policy_snapshot, status, trace_id, cost/latency, artifacts.
- **AgentInstance:** instance_id, run_id, definition_id/version, context_scope, workspace_ref, effective_permissions, model_resolution, status, step_budget, timeout.
- **DelegationTask:** task_id, parent_run_id, agent_instance_id, objective, input_artifact_refs, dependencies, deadline, result_ref, status, retry_count.
- **ModelPolicy:** allowed providers and models, preferred route, fallbacks, max cost, data residency and classification rules.
- **GatewayConfig:** endpoints and secret references (never raw keys in definitions).

Use schema migrations and backward-compatible API versioning. Reuse existing models where possible and avoid duplicate registries.

## 5. Execution and discovery algorithm

1. Authorize the user and establish the Session/Run scope.
2. The existing intent and skill router decides whether direct execution is enough.
   - Delegate only when a separate context, specialist reasoning, concurrency, or model/tool isolation materially helps.
   - Use a workflow for deterministic dependencies, resumability and approvals.
3. Discover Agent Definitions through capability and domain metadata. Filter them by published status, visibility, allowed skills and tools, model and gateway availability, and resource access.
4. Rank the eligible candidates by explainable capability fit, historical quality, latency, cost and health. Treat all permissions as hard gates, not score modifiers.
5. Create bounded instances: delegation depth at most 1 in V1, and a configurable maximum of concurrent agents, step budget, token/cost budget and timeout.
6. Dispatch structured tasks with the minimal required context and artifact references. Run independent work in parallel, and collect typed results with their provenance.
7. Validate the outputs and retry within bounds if needed. Use the existing workflow checkpoints for durable multi-stage jobs.
8. Emit structured telemetry and a readable execution summary for the user.

**Fallback.** If no agent is eligible, use authorized direct Harness execution when viable. Otherwise ask for clarification or approval, or report that the capability is not supported. Never silently broaden permissions.

## 6. Security requirements

- Effective access is the intersection of the user/tenant grants, the Agent Definition's limits, the Run policy and resource authorization.
- Re-check authorization at every tool execution, especially Bridge commands and MCP actions. Registry visibility does not grant execution rights.
- Scope delegated credentials to specific tasks, with an expiry. Secrets stay server-side.
- Require explicit approval for physical DUT and instrument control, destructive writes, external data exfiltration, merges, and other operations the policy marks as sensitive.
- Apply tenant isolation, artifact ACLs, secret redaction, prompt-injection defences for retrieved content, audit logs and policy-denied traces.
- Fail closed when the policy service or identity information is unavailable.

## 7. Implementation phases and acceptance criteria

Basic auth checks and audit hooks begin in Phase 1; Phase 4 deepens them. Do not ship unsafe interim execution endpoints.

### Phase 0: repository audit and ADRs (no core changes)

- **Deliver:** the current-state architecture, the reuse/gap matrix, ADRs, a dependency graph, baseline tests, a risk register and a phased estimate.
- **Gate:** Leo approves the ADRs and the V1 scope.

### Phase 1: registry and configuration foundation

- **Build:** versioned Agent Definitions, metadata validation, ownership and visibility, skill and tool references, model profile references, an admin API and a migration.
- **Accept when:**
  - definitions can be created, listed, updated, versioned and disabled;
  - invalid and unauthorized definitions are rejected;
  - existing single-agent flows are unchanged.

### Phase 2: Session/Run and execution strategy

- **Build:** extend the existing Session/Run, and add a direct / delegation / workflow strategy choice with transparent reasons.
- **Accept when:**
  - the direct path matches the baseline;
  - the strategy is recorded and can be overridden under policy;
  - old clients keep working.

### Phase 3: Auto Discovery and bounded delegation

- **Build:** eligibility filters, the ranker, explainable selection, ephemeral instances, isolated context, parallel dispatch, cancellation, timeouts and structured results.
- **Accept when:**
  - specialist matching tests pass;
  - the no-eligible-candidate fallback works;
  - concurrency and recursion limits are enforced;
  - the parent receives the artifacts and errors.

### Phase 4: gateway profiles and authorization hardening

- **Build:** per-agent model policy with the existing gateway (provider/model allowlists, data-classification restrictions, fallback, cost budget), policy checks at every MCP and Bridge tool call, and an approval state machine.
- **Accept when:**
  - a disallowed provider, tool or device is blocked;
  - no secrets are exposed;
  - approvals and denials are audited;
  - fail-closed behaviour is tested.

### Phase 5: observability, benchmark and rollout

- **Build:** traces in the existing telemetry and Atlas, and a comparison of direct, delegation and workflow on curated scenarios.
- **Accept when** these are measured: success rate, selection precision, latency p50/p95, tokens and cost, retries, policy denials, tool failures, and context-leakage tests. Feature flags, rollback and user documentation are in place.

## 8. Benchmark scenarios

1. **Knowledge only:** answer an RF/Wi-Fi 8 specification question with the existing skill and citations, with no unnecessary sub-agent.
2. **Parallel analysis:** analyse Qualcomm and MTK test documents independently, then combine them with provenance.
3. **Coding:** generate a parser and tests from sample instrument logs, and run them in a sandbox.
4. **Workflow:** SOP → code → unit test → review, recovering from a simulated failed step.
5. **Bridge safety:** request a CMP180 action without a device grant, and verify the denial and its audit record. Repeat with an explicitly approved mock device only.
6. **Model routing:** internal-only content must not be routed to an unapproved cloud provider. Simulate a gateway outage and a permitted fallback.
7. **Multi-user isolation:** concurrent sessions cannot read each other's private artifacts or secrets.

Define the baseline before implementation, use representative curated datasets, and set numerical release thresholds only after the baseline is measured. Do not invent performance targets.

## 9. Collaboration, PRs and rollout

- Use the existing repository `agentic-engineering-platform`; do not create a new one.
- Respect the repository's `AGENTS.md`, `CLAUDE.md`, existing CI and branch protection, and reconcile any conflicts with Leo.
- Create a GitHub Issue per phase, with small PRs linked to the issues. No direct pushes to a protected branch. Claude Code and Codex must use the same contracts and test requirements.
- Each PR states its purpose, design impact, migrations, test evidence, security review, telemetry, rollback notes and documentation updates.
- Leo may approve his own changes if the repository policy allows it. Other contributors follow the configured reviewer requirements.
- Feature flags default to off, and the old single-agent path is preserved. Roll out in staging with a mocked Bridge and synthetic data before any production hardware.
- No automatic merge or production deployment without explicit authorization.

## 10. Deliverables requested from Claude Code

**Before coding:**

- `docs/architecture/multi-agent-current-state.md`
- `docs/architecture/multi-agent-gap-analysis.md`
- ADR proposals in `docs/adr/`
- `docs/plans/multi-agent-implementation-plan.md`
- a proposed Issue/PR breakdown, a risk list and the exact open questions.

**After Gate 0 approval:** code, migrations, tests, docs, sample configurations, a benchmark report, CI evidence, and release and rollback instructions.
