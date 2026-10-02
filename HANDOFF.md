# Handoff

Date: 2026-10-02 (Asia/Taipei)

Branch: `main`

Status: multi-backend Agent Orchestrator Phase 0 audit complete; design review
pending. No runtime implementation changed in this phase.

## Current goal and sequence

The owner wants to strengthen the Agent harness first, then migrate every
relevant Workflow/job from `dragon0816/rs_workflow_system`, provide standardized
per-user static and per-run parameter forms in Web and Telegram, publish
reviewed Hermes Skills and migrated Workflows as Marketplace defaults, and
validate SOP-to-Workflow, Knowledge and natural-language Skill use end to end.
The detailed repository map and proposed slices are in
`docs/MULTI_BACKEND_ORCHESTRATOR_PHASE0.md`.

## Completed in this phase

- Read the downloaded multi-backend handoff as proposed requirements and
  inspected the current architecture, Agent, Gateway, local CLI backends,
  coding Harness, Workflow/Bridge policy, Knowledge and Marketplace code.
- Verified that the private source Workflow repository has a local read-only
  checkout at `896046e8fe2170d21f9213e56e5ce2f93c05ba43`, matching the
  pinned Phase 7 revision. It contains 10 n8n graph files and 15 top-level
  Host Bridge job modules. No source repository file was modified.
- Counted 67 Hermes `SKILL.md` manifests in the workstation's Skills
  installation directory across 12 categories; enabled state and content have
  not been reviewed for Marketplace publication.
- Recorded the owner decision that unclassified material may use only a
  suitably approved internal Gateway; external Codex/Claude backends require
  the entire transferred context to be explicitly PUBLIC. Backend availability
  never overrides this rule.
- Identified the current Codex/Claude path as restricted text chat, not native
  AEP task execution, and the absence of classification before backend dispatch.
  Recommended incremental orchestration around existing Gateway/Bridge
  contracts, with data policy before native Agent adapters.

## Verification

- No implementation code changed. Baseline local test selection: 1,509 passed,
  4 skipped, 2 environment-specific deselected, 1 intermittent Windows
  `os.replace` access-denied failure in extension staging. The exact failed
  test passed alone on a fresh directory. The preceding verified full run at
  the same runtime code had 1,510 passed, 4 skipped and 2 deselected.
- The current Agent Web and Shared Platform preview were left running; this
  phase did not change their installed packages or local credentials.
- `git diff --check` passed and the audit was reviewed for placeholders and
  internal contradictions before committing.

## Outstanding work and risks

- Review the recommended backend/data-policy architecture in the audit. The
  downloaded handoff describes a target, while the older repository Harness
  proposal is stale relative to current code and `PRODUCT_ACCEPTANCE_TESTS.md`
  has a different product-gate order. Update approved architecture/requirements
  explicitly before implementation.
- The available GitHub REST credential cannot read the private source repo's
  current HEAD. The pinned local checkout is a valid initial comparison base;
  confirm a newer exact revision before claiming complete migration.
- `docs/REQUIREMENTS.md` and `docs/DECISIONS.md` do not yet exist. Create them
  for approved multi-backend requirements and lasting security decisions.
- External native Agent CLIs cannot receive confidential or unclassified
  content. Workspace, environment, credential and Bridge containment require
  tests before allowing them to execute tools.
- Source `PARAMS_SCHEMA`/`x-ui` and `SettingField` use distinct per-run and
  persistent settings semantics; preserve approval and path boundaries when
  adapting them to shared parameter contracts. Do not publish all Skills or
  jobs by copying files directly into the Marketplace.

## Recommended next steps

1. Obtain owner review of `docs/MULTI_BACKEND_ORCHESTRATOR_PHASE0.md` and the
   incremental orchestrator direction.
2. Write the approved design/spec and update the product acceptance order,
   architecture and task contracts in a narrow documentation slice.
3. Add Gateway-only backend abstraction with behavior-equivalence tests.
4. Add data classification and backend trust with fail-closed payload-denial
   tests before Codex/Claude native task adapters.
5. Continue the remaining slices in the audit order, each with contract,
   regression, verification, commit and handoff evidence.
