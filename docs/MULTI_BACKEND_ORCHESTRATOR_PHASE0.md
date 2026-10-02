# Multi-backend Agent Orchestrator — Phase 0 audit

Status: repository-grounded audit for owner review, 2026-10-02. No runtime code
was changed in this phase. The downloaded
`CODEX_AEP_MULTI_BACKEND_ORCHESTRATOR_HANDOFF.md` supplies the proposed target,
not a substitute for this repository's contracts or approval policy.

## Scope and owner decision

The requested order is (1) strengthen the Agent harness and backend boundary,
(2) migrate and exercise the source Workflows and their parameter UX, (3) put
validated Skills and Workflows in the Marketplace, then (4) run SOP, Knowledge,
and ordinary-skill integration cases. These are separate implementation tracks
and must not become one big-bang source copy.

The owner chose the conservative initial data rule: existing unclassified data
may use only an internal Gateway explicitly approved for the relevant class;
Codex and Claude Code receive data only when the full transferred context is
explicitly `PUBLIC`. An unavailable Gateway never makes an unclassified or
sensitive run eligible for an external backend.

## Current execution paths

| Entry | Current path | Implication |
|---|---|---|
| Web slash command | `AgentWeb.conversation_turn` -> `parse_slash_command` -> exact Workflow/Knowledge handler | Deterministic, but `/run` requires `workflow namespace/name@version`; numeric aliases are unsupported. |
| Web ordinary Gateway chat | `AgentWeb.conversation_turn` -> `LocalAgent.converse` -> `Gateway.converse` -> `ModelClient.generate` -> installed command binding -> `BridgeExecutor` or `WorkflowEngine` | Five model turns and four tool calls at most. Tool authorization stays in Bridge policy. |
| Web Codex/Claude/Copilot chat | `AgentWeb.conversation_turn` -> `LocalConversationBackends.complete` -> fixed CLI command | Text-only restricted conversation. It does not enter `LocalAgent`, select AEP Skills, run AEP tools, or return governed task evidence. |
| Other local/remote work | `LocalAgent.handle/execute/execute_workflow` -> `Gateway.handle/execute_workflow` -> Bridge/Workflow engine | Exact routes and device admission already exist; they must remain the common execution boundary. |
| Coding Harness | `harness.runtime.CodingHarness` -> bounded workspace, declared validation commands, structured changes and repair | This is a distinct, already implemented coding/validation vertical. It is not a multi-backend orchestrator or general chat harness. |

`Gateway.converse` currently exposes every installed Skill command as a model
tool, embeds each Skill's instructions in the tool description, and uses fixed
loop limits. `AgentProfile` has Skill/Knowledge references and turn/retry fields,
but only its installed-asset filters are active on this path; the model loop
does not derive its limits or task completion criteria from the profile.

## Contracts and boundaries to preserve

- `src/agent/contracts.py`: `AgentProfile`, `ActiveAgentProfile`, deterministic
  router protocol.
- `src/agent/skills.py`: versioned `SkillManifest`, exact command bindings,
  trusted regex rules. Skills provide guidance and routes, not permissions.
- `src/common/assets.py`: versioned `TaskManifest` and `WorkflowManifest` with
  execution location, dependencies and `SecretRef`; Workflow steps name exact
  capabilities. `input_contract` is currently an identifier, not a field-level
  form/parameter schema.
- `src/workflow/engine.py` and `src/workflow/dispatch.py`: installed-only runs,
  durable progress/checkpoints, typed outputs, per-step Bridge dispatch.
- `src/capabilities/runtime.py`: default-deny `LocalPolicy` grant with actor,
  asset, permissions, policy refs and approval ref. This does not classify the
  content sent to a model or CLI.
- `src/knowledge/`: Drop/Raw/Wiki provenance and cited query behavior exist;
  Knowledge manifests and queries do not yet assign data classification to
  passages before backend routing.
- `src/host_runtime/`: device membership, local state, Web/Telegram ingresses,
  model catalog/SecretRef resolution and install/authorization projection.
  Shared Registry publication still grants no local execution permission.

## Source and Marketplace inventory

The private [source repository](https://github.com/dragon0816/rs_workflow_system)
has a local read-only checkout at
`C:\Users\Chi_L\Documents\claude\n8n_workflow_system`, revision
`896046e8fe2170d21f9213e56e5ce2f93c05ba43`, matching the pinned Phase 7
source. It contains 10 n8n Workflow JSON files and 15 top-level Host Bridge job
modules. They are not one-to-one: some jobs have no n8n graph and some old
Jira/GitHub variants overlap. The current remote HEAD could not be verified
with the available GitHub REST credential scope; pin the exact import revision
before migrating additional jobs.

The source's `PARAMS_SCHEMA` and `x-ui` define six answer kinds (`text`, `list`,
`toggle`, `file`, `folder`, `upload`), ordering, dependent options and UI hints.
Its `SettingField` separately defines persistent per-machine settings, including
privileged changes and input versus output paths. These are useful source
contracts for a shared parameter schema, but their source Python jobs and
privileged settings must not be installed as unreviewed shared code.

The Hermes Skill installation directory on this workstation contains 67
`SKILL.md` manifests across 12 top-level categories. Inventory and review must distinguish
owned guidance from third-party content, machine-specific paths, scripts,
credentials and dependencies before packaging. AEP's current preview catalog
publishes two harmless Skills, two read-only Workflows and one inert Extension;
it is not the requested default production catalog.

## Gaps, conflicts and risks

1. There is no backend-neutral task contract, backend profile/eligibility
   router, portable run state or independent completion validator around the
   conversation paths. `src/harness` supplies only the coding vertical.
2. There is no code-enforced classification gate before Codex/Claude receive
   conversation history. The current restricted CLI path relies on fixed
   no-tool flags and a bounded prompt, so it must not simply be relabeled a
   full native Agent backend.
3. Bridge authorization protects capability calls, but it does not make
   arbitrary native CLI file, command or network access safe. Native Agent
   adapters require tested workspace/environment/credential isolation and
   fail-closed behavior before tools are enabled.
4. The older `AGENT_HARNESS_ARCHITECTURE_PROPOSAL.md` describes missing
   behavior that later commits implemented (a bounded Gateway conversation
   loop and coding Harness). It is a historical proposal, not a current map.
5. `PRODUCT_ACCEPTANCE_TESTS.md` fixes an E2E order beginning with SOP-to-
   Workflow, while the owner now prioritizes the multi-backend harness first.
   After design approval, update that gate explicitly rather than silently
   contradicting it. The repository migration rule still requires narrow,
   reversible source adapters and parity tests, even though the long-term
   target covers every Workflow/job.
6. Shared per-user static settings, run-time parameters, file paths and
   uploaded content have different persistence, classification and permission
   rules. A field-level contract must keep those differences visible across
   Web, Telegram and Marketplace package boundaries.
7. This repository has no `docs/REQUIREMENTS.md` or `docs/DECISIONS.md` yet;
   requirements are spread across product/phase documents and owner decisions
   in `docs/TASKS.md`. Establish these continuity files for the approved
   orchestrator design rather than leaving its security choices in chat.

## Phase 0 verification

At the unchanged code baseline, the full local test selection completed with
1,509 passed, 4 skipped, 2 environment-specific deselected and one intermittent
Windows `os.replace` access-denied failure in extension staging. The same test
passed alone on a fresh temporary directory. The previous verified local run
at commit `3596c85` had 1,510 passed, 4 skipped and 2 deselected. This audit
does not claim production workflow parity or a live multi-backend security test.

## Architecture choices for review

1. **Incremental orchestrator around existing boundaries (recommended).**
   Wrap the current Gateway as a Model backend, introduce explicit backend
   profiles and data policy, then add native Agent adapters only after denial
   tests and containment checks pass. This preserves deterministic Workflow and
   Bridge behavior and provides reviewable rollback points. It takes more
   slices before Codex/Claude can perform tasks.
2. **Replace Gateway and Web backend handling in one pass.** This reaches a
   uniform UI sooner, but couples security policy, CLI execution and old
   Workflow behavior in one high-risk migration and obscures regressions.
3. **Add classification checks only in Web.** This is quick for one page but
   leaves CLI, Telegram and remote ingresses with different rules; it cannot
   serve as the platform's backend authorization boundary.

The first choice is the proposed design direction. The next design review
should settle the exact backend profile, classification provenance and
validation contracts before implementation.

## Recommended implementation sequence

| Slice | Contract and test first | Main files or boundaries |
|---|---|---|
| 1. Backend abstraction | Backend type/profile/health and Gateway adapter equivalence tests; route only to existing Gateway | Add `src/agent/backend_contracts.py`, `src/agent/backends/` and `src/agent/orchestrator.py`; reuse `Gateway`, `ModelClient`, `LocalAgent` |
| 2. Data trust | Classification order, effective context class, allowed backend set and audit reason; negative tests prove denied payload never reaches a backend | Add `src/agent/data_policy.py`; extend Knowledge/resource projections only as needed |
| 3. Portable task/state | Task objective, exact Skill/resources, expected outputs, completion checks, observations and artifact refs without raw reasoning; persisted resume/transition tests | Add `src/agent/task_contract.py`, `src/agent/run_state.py`; adapt local state |
| 4. Orchestrator ingress | Deterministic commands retain their path; ordinary requests pass admission, policy, backend eligibility and independent validation on Web/CLI/Telegram | Change `src/host_runtime/agent.py`, `web.py`, conversation backend adapter and tests |
| 5. Native Agent adapters | PUBLIC-only Codex then Claude; native harness owns its inner loop; policy-authorized material only, workspace/command/environment containment, no blind history failover | Add fixed adapters under `src/agent/backends/`; no CLI syntax in orchestrator |
| 6. Workflow parameter contract | Per-install/user static settings versus per-run values, typed controls and validated dynamic option providers; same schema renders Web and Telegram | Extend Workflow assets/config, Host settings, Web/Telegram forms; adapt source `PARAMS_SCHEMA`/`SettingField` with parity fixtures |
| 7. Workflow migration and commands | Inventory all 10 graphs/15 jobs, choose one lineage per behavior, migrate each behind typed capabilities and parity gates; resolve `/run workflow 11`, `/run 11` to exact installed identities | `src/workflow/`, `src/capabilities/`, `src/host_runtime/slash_commands.py`, migration fixtures |
| 8. Default catalog | Governed package/version, license/provenance/dependency scan, category and authorization checks for 67 Hermes Skills and validated Workflows | `src/control_plane/` import/seed path and Marketplace tests |
| 9. Product evidence | User-level SOP PDF/text -> executable draft, wiki convert/ingest/query/lint with cited answers, natural-language Skill selection for document/email/web tasks; negative security and side-effect cases | Committed E2E fixtures plus an enrolled-Bridge parity run where real company access is needed |

Each slice remains independently testable and reversible. External Agent
backends are not enabled for task execution before slice 2 policy tests pass;
Marketplace publication follows migration validation and separate governance.
