# Agentic Engineering Platform — Architecture

Status: Approved architecture baseline; Phases 1–6 implemented, Phase 7 not started

## 1. Purpose

This repository unifies the proven capabilities currently spread across five source repositories without blindly merging their implementations. The target is an engineering platform in which AI reasoning is used where judgement is needed, while deterministic execution remains deterministic.

Core rule:

> Agent decides **WHAT / WHY / WHICH**. Workflow defines **HOW EXACTLY**. n8n coordinates **WHEN**. Skills teach **HOW TO REASON/PROCEED**. Tools perform atomic actions. MCP exposes capabilities. Knowledge provides grounded context. Models are replaceable infrastructure. Evaluation proves behaviour remains acceptable.

## 2. Core requirements

### Multi-user and contribution-driven platform

The platform is designed as a **multi-user, contribution-driven engineering automation platform**. Team members can develop, validate, publish, discover, reuse and evolve **Tasks, Workflows, Skills, Knowledge and Agent profiles**. Platform capability grows through team contributions **without requiring changes to the core runtime**.

The platform therefore provides shared mechanisms for ownership, versioning, validation, review and approval, publishing, discovery, dependency management, permissions and lifecycle management.

A contribution is developed and validated in an isolated workspace before it becomes a shared platform asset:

```text
Engineer A        Engineer B        Engineer C
    |                 |                 |
    +------- develop / contribute ------+
                      |
                      v
              Platform Registry
        +-------------+-------------+
        |             |             |
        v             v             v
      Tasks       Workflows       Skills
        |             |             |
        +-------------+-------------+
                      |
             Knowledge / Agents
                      |
                      v
                Shared Platform
                      |
          +-----------+-----------+
          |           |           |
          v           v           v
       Bridge A    Bridge B    Bridge C
```

The **Platform Registry** is the shared control plane for published assets and their metadata. It is distinct from execution. A **Host Bridge / worker** advertises installed capabilities and local resources and executes Tasks/Workflows close to Windows COM, browsers, DUTs, instruments, files or other local dependencies.

Publishing an asset does not automatically grant execution permission. Registry/distribution and capability authorization are separate concerns. Shared assets must support explicit owner, version, lifecycle state, dependencies, compatibility requirements and permission/approval metadata.

**n8n is optional integration infrastructure**, not a mandatory core execution layer. n8n, Agent and CLI integrations should invoke the same Workflow/Capability contracts rather than implementing parallel business logic.

### Personal engineering workspace and capability growth

Each engineer works through a **Personal Engineering Workspace** composed of the engineer, a Personal AI Agent and a Host Bridge/worker. The Bridge is the engineer's local executable toolbox: it can expose personal/team Tools and Tasks plus local resources such as files, shells, browsers, Office/COM automation, DUTs and instruments. The Personal AI Agent reasons over the engineer's request and may combine local Bridge capabilities with shared Skills, Workflows and Knowledge discovered from the Platform Registry.

~~~text
                              Team Platform
                    +---------------------------+
                    |     Platform Registry     |
                    | Tasks / Workflows / Skills|
                    | Knowledge / Agent profiles|
                    +-------------^-------------+
                                  |
                         publish / discover
                                  |
          +-----------------------+-----------------------+
          |                       |                       |
+---------+---------+   +---------+---------+   +---------+---------+
| Engineer A        |   | Engineer B        |   | Engineer C        |
| Personal AI Agent |   | Personal AI Agent |   | Personal AI Agent |
|        <->        |   |        <->        |   |        <->        |
| Bridge A          |   | Bridge B          |   | Bridge C          |
| Tools / Tasks     |   | Tools / Tasks     |   | Tools / Tasks     |
| Local resources  |   | Local resources  |   | Local resources  |
+-------------------+   +-------------------+   +-------------------+
~~~

The engineer/agent/Bridge relationship is intentionally local while reusable capability is intentionally shareable. A Bridge may contain capabilities that remain private to one engineer, capabilities installed from the team registry, and capabilities being developed for later publication.

### Continuous capability learning / Engineering Capability Flywheel

Real work is a source of reusable engineering capability. During problem solving, an engineer and Personal AI Agent may discover a repeatable procedure, automation or decision pattern. The platform should be able to capture this as a **candidate asset** rather than losing it in a chat transcript or one-off script.

~~~text
Engineer work
     |
     v
Personal AI Agent <-> Bridge / local tools
     |
     v
Solve real engineering problem
     |
     v
Capture successful experience / pattern
     |
     +----------------+----------------+
     |                |                |
     v                v                v
Skill Candidate   Task Candidate   Workflow Candidate
     |                |                |
     +----------------+----------------+
                      |
                      v
             Validate / Evaluate
                      |
                      v
                Human Review
                      |
                      v
                  Publish
                      |
                      v
              Platform Registry
                      |
                      v
        Discover / reuse by the team
                      |
                      v
             Better team agents
                      |
                      +--------------------> more work -> repeat
~~~

This creates an **Engineering Capability Flywheel**: individual work improves the individual's agent/toolbox; validated contributions improve the shared platform; shared capabilities improve other engineers' agents; their work produces further contributions. The platform, team and individual engineering work therefore evolve together.

Capability learning is **not unrestricted self-modification**. An Agent may propose or draft a new Skill, Task or Workflow, but a candidate must not become a trusted shared capability merely because an LLM generated it. The normal lifecycle is:

~~~text
experience -> candidate -> draft -> validation/evaluation -> human review
           -> published -> observed usage -> improvement -> new version
~~~

Production-impacting capabilities may require stronger approval and validation gates. Publication and execution authorization remain separate.

### Contribution provenance and lifecycle

To support this growth model, registry assets should preserve enough metadata to answer who created a capability, why it exists, how it was validated and how it has evolved. Common metadata should support, where applicable: author and contributors; semantic version and lifecycle status; source/provenance; validation and human-review status; dependencies and runtime/Bridge compatibility; required permissions and approval classification; evaluation references/results; usage/observability references; and deprecation/replacement information.

Usage statistics are evidence for maintenance and evaluation, not automatic proof that a capability is correct. Improvements are released as explicit versions so teams can validate, roll back and reproduce prior behaviour.


### Scoped asset identity and ownership

Shared assets use a stable scoped identity rather than a flat department-specific name. The scope is called a **namespace** because it may represent a team, department, project, site, shared platform area or private workspace.

```yaml
namespace: rf-team
name: wifi-release-validation
version: 1.2.0
owner:
  type: team
  id: rf-team
visibility: team
```

`namespace` identifies the asset scope, `owner` identifies who is accountable for it, and `visibility` controls discovery. These are separate concepts. A stable namespace also allows assets from separate department servers to be imported, federated or referenced later without ambiguous names or dependencies.

### Agent-assisted contribution and layered review

Contribution must not assume that every contributor writes code. A Personal Engineering Agent may use local Skills and Bridge capabilities to turn successful real work into a Skill, Task or Workflow candidate. The candidate remains untrusted until validation and review.

```text
Real work -> Personal Agent -> candidate -> automated validation
                                     |
                                     v
                              business review
                           (department owner)
                                     |
                                     v
                              technical policy
                         (risk/capability checks)
                                     |
                                     v
                                  publish
```

Business review answers whether the procedure represents the department's intended work. Technical policy answers whether the requested capabilities, data access and side effects are allowed. Low-risk candidates may pass technical policy automatically; privileged, cross-scope or high-impact candidates may require technical review. Publication never grants runtime execution authorization.

### Execution dependencies and local-first contract

Local-first behavior is explicit metadata, not an implicit runtime guess. Tasks and Workflows declare local capability requirements and any required central services. A capability whose required central dependencies are unavailable returns a structured unavailable/needs-connectivity result rather than silently changing behavior.

```yaml
execution:
  mode: local
dependencies:
  central_required: false
requires:
  capabilities:
    - filesystem.read
  services: []
```

Already-installed assets may continue locally when `central_required: false` and all required local capabilities and authorization are available.

### Secret boundary

Registry assets never contain secret values. They may declare symbolic secret requirements through provider-neutral references such as `SecretRef(name="github_token")`. Resolution belongs to the execution environment through a Bridge/runtime secret resolver. The concrete backend may later be an OS credential store, environment-backed development provider or enterprise vault; Phase 1 does not choose that infrastructure.

Secret references are metadata requirements, not authorization. A Bridge must still decide whether the requesting identity is permitted to resolve and use the secret for the requested operation.


## 3. Target architecture

The deployment model is explicitly split into two planes:

1. **Team Platform Plane** — shared control plane for team assets, governance, discovery, distribution, evaluation and observability.
2. **Personal Engineering / Execution Plane** — one per engineer, normally running on the engineer's own Bridge computer. It contains the user-facing UI, Personal Engineering Agent and local Bridge capabilities.

**Reasoning is personal and distributed; capabilities and knowledge are shared and continuously evolved by the team.**

~~~text
                         TEAM PLATFORM PLANE
                  Shared Team Platform / Server

              +----------------------------------+
              | Platform Registry                |
              | Tasks / Workflows / Skills       |
              | Knowledge / Agent Profiles       |
              | Versions / Owners / Permissions  |
              +----------------+-----------------+
                               |
              Package Repository / Evaluation
              Observability / Team Governance
                               |
                    publish / discover / sync
                               |
          +--------------------+--------------------+
          |                    |                    |
          v                    v                    v

                 PERSONAL ENGINEERING / EXECUTION PLANES

+----------------------+ +----------------------+ +----------------------+
| Engineer A PC        | | Engineer B PC        | | Engineer C PC        |
|                      | |                      | |                      |
| Web UI / CLI         | | Web UI / CLI         | | Web UI / CLI         |
|       |              | |       |              | |       |              |
|       v              | |       v              | |       v              |
| Personal Engineering | | Personal Engineering | | Personal Engineering |
| Agent A              | | Agent B              | | Agent C              |
|       |              | |       |              | |       |              |
|       v              | |       v              | |       v              |
| Bridge A             | | Bridge B             | | Bridge C             |
| Tools / Tasks        | | Tools / Tasks        | | Tools / Tasks        |
| DUT / Instrument     | | DUT / Instrument     | | DUT / Instrument     |
| Files / Office / Git | | Files / Office / Git | | Files / Office / Git |
+----------------------+ +----------------------+ +----------------------+
~~~

### Personal Engineering Agent

The **Engineering Agent is not primarily a central-server agent**. Each engineer normally runs a Personal Engineering Agent on the same computer/network execution boundary as that engineer's Bridge. The agent is the engineer's AI work partner and owns reasoning, planning, context assembly, Skill/Knowledge use, capability selection and bounded delegation.

The Engineering Agent does **not** directly own hardware or operating-system execution. It requests deterministic Tasks/Workflows/Tools through the Bridge and receives structured results.

~~~text
Engineer request
      |
      v
Personal Engineering Agent
      |
      +--> discover/use Knowledge
      +--> discover/use Skills
      +--> select Task / Workflow
      +--> reason / plan / request approval
      |
      v
Local Bridge
      |
      +--> Files / Shell / Git
      +--> Office / COM / Browser
      +--> DUT / Instrument
      +--> local engineering tools
~~~

This separation keeps reasoning replaceable while preserving reliable local execution boundaries.

### Team Platform Plane

The shared Team Platform is primarily a **control plane**, not the default location where every engineer's reasoning executes. It owns shared capability/knowledge management such as:

- Platform Registry and package distribution;
- shared Skills, Tasks, Workflows, Knowledge and Agent Profiles;
- ownership, versions, lifecycle and permissions;
- evaluation and validation records;
- team observability and governance;
- discovery, installation, update and publishing services.

A future centralized/service agent may exist for use cases such as scheduled background work or team-wide services, but it must use the same Agent/Workflow/Capability contracts. It is not a prerequisite for Personal Engineering Agents.

### Local-first resilience

The Personal Engineering Plane should continue operating with already-installed capabilities when the Team Platform is temporarily unavailable, provided the requested operation has no required central dependency.

~~~text
Team Platform unavailable
        X
        |
Engineer -> Personal Agent -> Local Bridge -> installed Skill/Task/Workflow
                                      |
                                      v
                               local resources
~~~

During such a period, discovery, publishing, team synchronization and centrally required services may be unavailable, but local engineering work should not fail merely because the Registry cannot be reached.

### Shared runtime, distributed profiles

The platform still uses **one agent runtime architecture with N agent profiles**, not N independently implemented agent frameworks. Personal Engineering Agents instantiate the shared runtime with engineer/team-specific configuration, installed capabilities, local context and permissions.

Agent Profiles are shared/versioned through the Platform Registry; Agent Runtime instances are normally distributed to Personal Engineering Planes.

Cross-cutting concerns across both planes include Evaluation, Guardrails, Observability, Configuration, Secrets, Identity and Policy.


## 4. Routing policy

```text
Request
  |-- known command / exact tool --> deterministic dispatch
  |-- known workflow -------------> workflow engine
  `-- ambiguous / complex --------> agent selection + reasoning
```

Do not put an LLM in front of operations that already have a reliable deterministic route. This preserves the strongest property already present in `telegram-local-agent`: cheap deterministic routing before LLM parsing.

Request routing, agent selection and model routing are separate decisions:

```text
Gateway:      Does this require an agent? Which agent owns it?
Agent:        What should be done and should work be delegated?
Model Router: Which configured model satisfies this model call?
Workflow:     How exactly is the deterministic operation executed?
```

## 5. Platform boundaries

### Agent Gateway
The platform entry point. Owns request normalization, deterministic-first routing, top-level policy/approval checks, trace/session creation and selection of the owning agent when reasoning is needed. The Gateway should not contain specialist domain prompts or detailed workflow logic.

### Agent runtime
One shared execution engine for all agent profiles. Owns bounded reasoning loops, context assembly, skill use, capability invocation, delegation/handoff mechanics and structured completion/failure states. Adding a new agent should normally add configuration/profile content rather than another runtime implementation.

### Agent registry and profiles
The registry contains available agents and their bounded responsibilities. Each profile declares description, skills, allowed capabilities, knowledge scope, model requirements, delegation targets and policy constraints.

Example:

```yaml
agents:
  engineering:
    description: General engineering task coordinator
    skills: [debug, validation, release]
    capabilities: [git_read, log_parser, workflow_runner]
    knowledge: [engineering_wiki]
    model_requirements:
      reasoning: high
      tool_calling: true
    may_delegate_to: [coding, knowledge]

  coding:
    description: Software implementation specialist
    skills: [coding, code_review, unit_test]
    capabilities: [git, shell, pytest]
    model_requirements:
      reasoning: high
      tool_calling: true
```

Phase 1 implements only the `engineering` profile. `coding`, `knowledge`, `rf_expert` and other specialists are extension points, not Phase 1 requirements.

### Delegation vs handoff
Use **delegation / agent-as-tool** when the current agent remains responsible for the user's task and needs a bounded specialist result. The parent sends a structured subtask, receives a structured result, and continues orchestration.

Use **handoff** only when ownership of the conversation/task should move to another specialist. Handoff transfers the active owner and relevant context. Do not use handoff merely to call a specialist function.

Agent-to-agent communication must use explicit task/result contracts rather than unconstrained free-form conversations. Delegation depth, total turns and retries are bounded to prevent agent loops.

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

Multi-agent evaluation must additionally verify correct owner selection, allowed delegation targets, bounded delegation, context passed to specialists and prohibited cross-agent capabilities.

## 6. Proposed repository layout

```text
agentic-engineering-platform/
├── AGENTS.md
├── ARCHITECTURE.md
├── README.md
├── pyproject.toml
├── agents/
│   └── engineering.yaml
├── src/
│   ├── agent/
│   │   ├── gateway/
│   │   ├── runtime/
│   │   ├── registry/
│   │   ├── routing/
│   │   ├── delegation/
│   │   ├── handoff/
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

`agents/`, `skills/`, `workflows/` and `knowledge/` deliberately live outside Python package code so operational/domain configuration can evolve without requiring application-code changes.

## 7. Source-system findings

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

## 8. Non-negotiable engineering rules

1. Existing source repositories remain unchanged during migration until replacement behaviour is validated.
2. Deterministic routes take precedence over LLM reasoning.
3. One shared agent runtime supports multiple bounded agent profiles; do not create a separate framework per specialist.
4. Agent profiles must explicitly declare allowed skills/capabilities/knowledge/delegation targets.
5. Agent-to-agent delegation uses structured contracts and bounded depth/turns/retries.
6. Agent/Skill/Workflow/Knowledge code must not depend directly on a concrete LLM provider SDK; use the model interface.
7. Model selection is policy/configuration driven and observable; logical model aliases are preferred over hard-coded model IDs.
8. Side-effecting operations must have explicit policy and approval classification.
9. Workflows must be independently executable/testable where practical.
10. Raw knowledge is immutable; generated/curated knowledge preserves provenance.
11. Secrets never live in committed configuration.
12. New capabilities require regression/evaluation cases.
13. Migration is incremental; do not perform a five-repository big-bang merge.
14. Observability must record route/agent/delegation/plan/model/tool/workflow outcome without logging secrets.
15. Agent loops are bounded and must surface a structured failure/needs-input result rather than spin indefinitely.
16. Team contributions must be publishable/discoverable through stable contracts without requiring core-runtime changes.
17. Shared assets must carry owner, version, lifecycle, dependency and permission metadata.
18. Registry/distribution is separate from execution authorization; publishing never implies unrestricted execution.
19. Bridges/workers execute locally and advertise installed capabilities/resources; the central registry is a control plane, not the mandatory execution host.
20. n8n is optional event/business automation integration; Agent, n8n and CLI must reuse the same underlying Workflow/Capability contracts.
21. Agents may propose new reusable assets from work experience, but shared publication requires explicit validation/evaluation and applicable human review.
22. Published assets preserve author/contributor provenance, version/lifecycle and validation metadata so capability evolution is auditable and reversible.
23. Personal Bridges may mix private, installed shared and in-development capabilities; publication to the Platform Registry is an explicit lifecycle transition.
24. Personal Engineering Agents normally run in the engineer's Personal Engineering/Execution Plane; the shared Team Platform is the control plane and is not the default host for personal reasoning.
25. Personal Engineering Agents own reasoning/planning/capability selection; Bridges own local deterministic execution and resource access.
26. Installed local capabilities should remain usable during temporary Team Platform outages when no central dependency is required.

### Coding-agent-neutral development

The development process follows the same replaceability principle as the runtime model layer: **coding agents are replaceable workers; the repository is persistent project state**. Codex, Claude Code and human engineers may alternate on the same implementation without depending on private conversation history.

Architecture, phase specifications, stable contracts, tests, repository Skills, commits and `HANDOFF.md` define the durable development context. Agent-specific entry files such as `AGENTS.md` and `CLAUDE.md` point to the same source-of-truth documents and engineering procedures rather than maintaining divergent workflows.

~~~text
                 GitHub Repository
                       |
      Architecture / Contracts / Tests
             Skills / HANDOFF
                       |
          +------------+------------+
          |            |            |
        Codex      Claude Code     Human
          |            |            |
          +------------+------------+
                       |
                same branch / PR
~~~

A coding-agent handoff is complete only when repository state is reproducible, verification status is explicit and the next action is recorded. Conversation memory is never required to resume development.

## 9. Migration strategy

Phase 0: architecture, contracts, migration inventory, including multi-agent extension points.

Phase 1: common contracts + model interface/router/provider adapter contracts + **single Engineering Agent profile/runtime** + platform skeleton + CI/evaluation baseline. Multi-agent contracts may exist, but no specialist-agent zoo is implemented.

Phase 2: agent routing/skills/tools/MCP and the first justified specialist agents using the same runtime/registry/delegation contracts.

Phase 3: deterministic workflow + Host Bridge integration.

Phase 4: knowledge Drop -> Raw -> Wiki, including multimodal ingestion/provenance through model capability requirements rather than a hard-coded vision provider.

Phase 5: provider adapters/model gateway and external integrations.

Phase 6: guardrails, approvals, tracing and full evaluation harness, including cross-model and multi-agent evaluation.

Phase 7: end-to-end validation and controlled deprecation of source repositories.
