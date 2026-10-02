# Handoff

Date: 2026-10-02 (Asia/Taipei)

Branch: `main`; local-only work, no push. The prior backend-boundary slice is
commit `4f5b92c`; the data-trust slice described below is the current handoff.

Status: multi-backend Agent Orchestrator slices 1 and 2 complete in source.
Portable task state, native task adapters, Workflow migration, Marketplace
defaults and product E2E remain outstanding.

## Goal and decisions

The owner approved the incremental sequence in
`docs/MULTI_BACKEND_ORCHESTRATOR_PHASE0.md` and
`docs/superpowers/specs/2026-10-02-multi-backend-orchestrator-design.md`.
Strengthen the Agent first, then migrate pinned source Workflows with static
and runtime parameter UI, publish reviewed default assets and prove SOP,
Knowledge and ordinary Skill scenarios. `docs/DECISIONS.md` records the
owner's data boundary: UNCLASSIFIED data may use only a host-admin-approved
internal Gateway. Codex/Claude may receive only complete explicitly PUBLIC
context; availability never causes an ineligible fallback. The owner chose
explicit host-admin Gateway approval over trusting localhost.

## Completed

- Slice 1 added typed backend profiles/health, exact selection and a Gateway
  conversation adapter. Local Agent admission, deterministic routes, Bridge
  policy, result formats and durable Workflow evidence remain unchanged.
- Slice 2 added classified text/provenance contracts and a fail-closed data
  decision. `models.data_approval` names the exact routed Gateway alias and
  URL, allowed classes and approval reference. A host-built model client
  treats the entire request as UNCLASSIFIED and does not call provider generate
  or stream without matching approval. The doctor and Web Settings/Backend
  status show missing approval.
- Existing restricted Codex/Claude/Copilot CLI text chat now requires a new
  PUBLIC session declared before messages. The CLI adapter checks labels
  against every message actually sent; Web sends no local persona text and
  blocks slash commands in PUBLIC sessions. An old conversation cannot be
  relabeled PUBLIC; switching it to Gateway removes the PUBLIC declaration.
  This restricted text chat is still not governed native task execution.
- Added API, policy, host-wire and regression tests. The browser page has a
  confirmation dialog that creates a new PUBLIC session when needed. Source
  decisions, requirements and acceptance prerequisites were updated.

## Verification

- Full local selection with `PYTHONUTF8=1`, a fresh `.scratch` pytest
  basetemp, no pytest cache, `--ignore=tests/test_browser.py` and two existing
  machine-specific exclusions: **1,523 passed, 4 skipped, 2 deselected**.
- `.venv/Scripts/python -m ruff check src tests`: passed.
- `.venv/Scripts/python -m mypy src tests`: passed, 280 source files.
- `.venv/Scripts/python -m build --no-isolation --outdir
  .scratch/dist-data-final-20261002`: sdist and wheel built; wheel contains
  the new data-policy and model-approval modules and the Web page.
- Extracted inline Web JavaScript and ran `node --check`: passed.
- The header-auth Web test passed alone. The separate real-Chromium UI test
  failed before page navigation because this machine closed its CDP WebSocket;
  no visual interaction result is claimed.

## Outstanding work and risks

- Source enforcement is ready, but no actual preview host was newly approved.
  The owner has been asked to confirm whether this workstation's LiteLLM
  `http://127.0.0.1:4000/v1` may receive UNCLASSIFIED data. Until a host
  administrator records that exact approval in its `host.json` and restarts
  the Agent, the upgraded host will refuse ordinary Gateway model calls. The
  running preview has not been reinstalled or restarted with these changes.
- The current classifier conservatively treats every AEP model request as
  UNCLASSIFIED. Future per-source provenance must preserve Knowledge citation
  and attachment labels before native task backends receive any content.
  PUBLIC session declaration is an explicit operator statement, not a
  guarantee that human-entered text is actually public.
- `BackendRouter` currently registers only Gateway for governed conversation.
  Native task adapters still need workspace, environment, credential and
  side-effect containment plus portable task/state and independent validation.
- The private source Workflow checkout is read-only at
  `C:\Users\Chi_L\Documents\claude\n8n_workflow_system`, revision
  `896046e8fe2170d21f9213e56e5ce2f93c05ba43`. Remote HEAD could not be
  verified with available GitHub REST scope. Hermes Skills and migrated
  Workflows require individual provenance/license/dependency/policy review.

Next action: implement the portable task and run-state contracts with
persistence and independent completion validation tests, then attach them
without changing deterministic Workflow execution.
