# Personal Agent and Coding Harness architecture proposal

Status: proposed for owner review. This document records analysis and a
recommended evolution; it does not amend `ARCHITECTURE.md` or approve runtime
implementation.

## Decision summary

The current architecture is directionally aligned with the Product Vision. Its
control/execution-plane split, local Bridge, provider-neutral model contracts,
deterministic Workflows, governed assets, Knowledge provenance, policy and
evidence model are the right foundation. A rewrite would discard useful and
tested boundaries.

Development priority has drifted. Phase 7 has necessarily invested in migration,
Windows packaging, a weekly-report vertical, local UI and browser integration,
while the repository still lacks the Personal Agent reasoning runtime and Coding
Harness that the Product Vision names as the first product milestone. The
SOP-to-Workflow author is a useful slice, but it deliberately is not a general
Coding Harness. More one-off UI or business integration work should wait unless
it directly closes a V1 benchmark or an active production-parity gate.

## Current architecture

The Team Platform Plane is the control plane for identity, governance,
publication, discovery, distribution, evaluation summaries and status
projections. The Personal Engineering / Execution Plane contains the resident
Agent, installed assets, authoritative local run state and Bridge access to local
resources. A Gateway normalizes requests and selects deterministic routes before
model reasoning. Every capability declares side effects and remains subject to
actor, device, grant and approval policy. Workflows define exact repeatable
execution. Knowledge preserves immutable Raw evidence and curated Wiki content.

This separation already supports the Product Vision's central requirement: a
shared catalog can improve and distribute capabilities while sensitive execution
stays near the device, credentials and company resources.

## Reusable components

| Existing component | Disposition | Role in the V1 milestone |
|---|---|---|
| Asset identity, governance, `SecretRef`, trace and execution contracts | Keep | Stable boundary for every Harness input, action and result |
| `AgentProfile`, deterministic router and Gateway | Extend | Configure one Personal Engineering Agent and admit its requests |
| Capability registry, Bridge executor and approval policy | Keep | Only route to local tools; model output never grants permission |
| Workflow engine, journal, payload and progress contracts | Keep | Execute validated deterministic Workflows and reusable build/test jobs |
| Model catalog and `ModelClient` | Keep | Provider-neutral reasoning with per-request secret resolution |
| Evaluation cases, graders and `ExecutionTrace` | Extend | Supply benchmark acceptance and evidence, distinct from the Coding Harness |
| Knowledge Drop/Raw/Wiki/query pipeline | Extend | Provide cited context to the Personal Agent and Knowledge benchmark later |
| Installed Skill registry | Extend | Load versioned guidance, constraints, examples and evaluation references |
| Registry/distribution/enrollment and local host package | Keep | Deliver reviewed capabilities to enrolled Bridges |
| SOP Workflow authoring | Extend | Starting point for benchmark 2, with stronger executable acceptance |
| Browser, Office, filesystem-read and migrated domain rules | Keep | Typed tools available to benchmark tasks under policy |

## Architectural gaps

1. `AgentProfile` is a contract and sample asset; no runtime instantiates it as a
   bounded reasoning loop with context, budgets and structured completion.
2. `LocalAgent` is a durable authenticated ingress around the Gateway, not yet
   the Personal Agent described by the Vision.
3. There is no workspace model, repository snapshot, change plan, controlled
   file-write/shell/Git layer or code-change result contract.
4. There is no validation plan that binds acceptance criteria to executable
   checks, nor a bounded repair controller driven by their failures.
5. Existing evaluation proves platform behavior but has no datasets and runners
   for the three V1 Coding Harness benchmarks.
6. Skills are discoverable routing/procedure assets, but exact Skill versions are
   not assembled into an Agent/Harness context or recorded on a run.
7. Knowledge query is not wired into the Personal Agent's context path.
8. The Registry has no Software capability manifest that points to externally
   hosted source and releases.
9. Feedback has no standardized `ImprovementRequest` contract or governed triage
   integration point.
10. Several future specialist-agent and delegation extension points exist in the
    architecture. Implementing them now would dilute the single useful Personal
    Agent milestone.

## Proposed Personal Agent and Harness boundary

```text
User / CLI / Web / Telegram
          |
          v
Resident Personal Agent runtime
  - AgentProfile, request context, bounded reasoning and escalation
  - Skill and Knowledge context assembly
  - deterministic-first selection through the existing Gateway
          |
          v
Coding Harness (personal execution plane)
  Requirement + WorkspaceSnapshot + ChangePlan + ValidationPlan
          |
          +--> typed workspace / Git / shell / build / test capabilities
          |         through Bridge policy and approvals
          +--> existing deterministic Workflows
          +--> Validator -> structured failures -> bounded repair controller
          |
          v
HarnessResult + ChangeSet + validation evidence + ExecutionTrace
```

The Coding Harness is a bounded execution service used by the Personal Agent. It
is not another autonomous agent, a second Workflow engine or a control-plane
service. It composes existing contracts and executes only declared commands and
workspace-scoped capabilities through the Bridge. Its state and evidence remain
local; publishable metadata and approved artifacts may be projected to the Team
Platform.

Recommended future contracts, introduced only as each slice needs them:

- `HarnessTask`: bounded objective, inputs, expected artifacts, budgets and
  approval requirements;
- `WorkspaceRef` and `WorkspaceSnapshot`: repository/root identity, revision,
  relevant files and dependency evidence;
- `ChangePlan` and `ChangeSet`: intended and actual workspace mutations;
- `ValidationPlan` and `AcceptanceCriterion`: commands or validators whose
  observed outcomes decide completion;
- `HarnessRun`, `IterationRecord` and `HarnessResult`: bounded attempts,
  structured failures, artifacts and evidence references;
- `SkillBinding`: exact identity/version used by the run;
- `SoftwareManifest`: Registry metadata pointing to external source, release and
  integration interfaces;
- `ImprovementRequest`: target asset/version, evidence, reproduction and proposed
  acceptance criteria, added after the Harness milestone.

These contracts must preserve current invariants: publication grants no execution
permission; a Skill cannot authorize tools; secret references never contain
values; business approval differs from technical policy; central service
dependencies are explicit; the Harness cannot mark itself successful without
validator evidence.

## V1 benchmark execution

### Device and chipset development

The Personal Agent receives a bounded requirement, workspace and target device.
It pins the vendor/domain Skill, snapshots the repository, proposes a change and
runs pure/unit or simulated checks first. Authorized build and device actions go
through the company or shared-test Bridge and its existing policy. Real DUT and
instrument validation runs on the enrolled machine, never on the shared control
plane. The result contains the patch, exact Skill and dependency versions,
commands, device evidence and acceptance status for human review.

### SOP to deterministic Workflow

The Personal Agent turns an SOP and installed capability inventory into a typed
Workflow candidate using the existing authoring slice. Contract, dependency,
policy and static reviews reject an invalid candidate. A dry run and fixture
execution validate data flow and expected outputs. A human reviews the candidate
before publication. Subsequent runs use the existing deterministic Workflow
engine without reinterpreting the SOP.

### Parser and transformation development

The user supplies representative input, output expectations or golden files and
a bounded workspace. The Harness generates or modifies the transformation,
executes it only inside the workspace, compares schema/content and declared
properties, feeds structured failures into a limited repair loop, and runs a
regression corpus before returning a patch and evidence. This is the first
general Coding Harness vertical after E2E-02 because it needs neither production
credentials nor physical hardware.

## Skill integration model

A Skill is a governed, versioned context bundle: procedure, domain facts,
constraints, examples, tool guidance and linked evaluations. AgentProfile and
task requirements select Skills deterministically where possible. The runtime
records the exact identity and version in `HarnessRun`, loads only bounded
relevant content, and preserves citations to source Knowledge when present. A
Skill can influence planning but cannot implement an atomic tool, grant a
permission or replace a Workflow.

## Workflow generation and execution

Reasoning produces a reviewable Workflow candidate. Deterministic validators
check its contracts, dependencies, side effects and permissions; fixture/dry-run
execution checks behavior; governance publishes a version. The Workflow engine
then owns exact normal execution. The Coding Harness may invoke validated
Workflows for build, test or transformation steps and may author a new candidate,
but it does not duplicate Workflow scheduling, journaling or recovery.

## Continuous Evolution integration points

Later, user feedback attaches to an asset identity/version and the originating
run, trace and evidence. The Personal Agent clarifies it into an
`ImprovementRequest`. Governance approves, rejects or requests evidence. An
approved request becomes a Harness task; its output is a candidate version or
source-control PR plus validation evidence. Human review and release publish the
new version. Usage and feedback contribute evaluation cases, never automatic
production mutation.

Only these seams should be defined now. A triage service, dashboard, automated
release system and full multi-agent development organization are deferred until
the Personal Agent and Harness pass all three V1 benchmarks.

## Incremental implementation plan

The product gate order is fixed by `PRODUCT_ACCEPTANCE_TESTS.md`:

1. **E2E-02 — SOP-to-Workflow.** Connect existing authoring to semantic
   acceptance, fixture execution, regression evidence, human review and a
   deterministic no-model replay.
2. **E2E-03 — coding/transformation.** Add the minimum workspace, plan, change,
   validation and bounded-repair contracts plus scoped file write, command and
   Git-diff capabilities. Prove them with a parser/transformation fixture.
3. **E2E-05 — Knowledge continuous evolution.** Turn a deficient cited answer
   and user feedback into a governed improvement request, candidate, expanded
   evaluation set and versioned republish without changing Raw evidence.
4. **E2E-04 — Software continuous evolution.** Add external Software repository
   metadata and use the proven Harness to reproduce, change, regress and prepare
   a reviewable source-control candidate through an inert adapter.
5. **E2E-01 — physical DUT/chipset capability.** Prove the same development path
   with a simulator, then collect the required production-like evidence on an
   enrolled company or shared-test Bridge.

Only the minimum contracts needed by the current E2E are introduced. The next
E2E runtime does not begin until the current one has its reproducible passing
path.

Each slice follows architecture -> requirements -> contracts -> tests ->
implementation -> verification -> commit -> handoff and remains independently
reversible.

## Risks and trade-offs

- Arbitrary shell and file write are powerful. Start with workspace roots,
  allowlisted commands, explicit side-effect classes and approval policy.
- A model can optimize to weak tests. Acceptance criteria need independent
  graders, golden data, negative cases and regression evidence.
- Device results are environment-specific. Record hardware, firmware, Skill,
  dependency and Bridge identities so evidence can be reproduced.
- Context can become large and stale. Pin versions, load only relevant sections
  and include provenance rather than silently copying mutable content.
- Implementing all UI, memory and specialist agents together would obscure
  whether the core Harness works. One engineering profile and three benchmarks
  provide a clear gate.
- The current evaluation harness and proposed Coding Harness solve different
  problems. Reuse evidence contracts while keeping their runtimes separate.

## Recommended `ARCHITECTURE.md` changes after approval

1. Add `PRODUCT_VISION.md` as the product-priority input above phase planning.
2. Define the Coding Harness inside the Personal Engineering / Execution Plane
   and distinguish it from both the Workflow engine and evaluation harness.
3. State the externally validated completion rule and bounded repair budgets.
4. Add workspace/change/validation/result boundaries and show that all execution
   passes through Bridge policy.
5. Add Software as a Registry asset whose source and release may remain in
   GitHub/GitLab.
6. Add `ImprovementRequest` and the Continuous Evolution Engine as future
   integration points, not current runtime requirements.
7. Change sequencing language to make one useful Personal Engineering Agent and
   the three V1 benchmarks the next milestone; retain multi-agent/delegation only
   as future extension points.
8. Add benchmark-specific acceptance paths, including real device validation on
   an enrolled Bridge and inert CI substitutes.

## Review decisions requested

Owner review should decide whether this boundary and sequence become the next
architecture baseline. Approval would authorize a small follow-up PR that amends
`ARCHITECTURE.md`, `ROADMAP.md` and the active phase specification. It would not
authorize the whole Harness implementation in one change.
