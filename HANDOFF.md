# Handoff

Date: 2026-10-02 (Asia/Taipei)

Branch: `main`; local-only work, no push. Backend boundary is commit
`4f5b92c`; data trust is `c15d8d0`; portable state is `c7c33d6` and
`222e851`. This handoff also covers the workstation Gateway default.

Status: multi-backend Agent Orchestrator slices 1–2 and the portable task/state
contract subset of slice 3 are complete in source. The owner-approved
`company` Gateway route is recorded in the installed preview configuration.
Normal Agent ingress is not yet connected to portable task state; backend
re-authorization, native task adapters, Workflow migration, Marketplace
defaults and product E2E remain.

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
explicit host-admin Gateway approval over trusting localhost. On 2026-10-02
the owner specifically approved this workstation's LiteLLM route
`http://127.0.0.1:4000/v1` for `UNCLASSIFIED` model requests and asked for an
editable configuration, so that decision is now recorded in `host.json`.

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
- Slice 3 added a serializable `TaskContract` with task type, initial data
  class, exact Skill/resource refs, requested capability scope, bounded
  constraints, expected outputs and repeatable checks. Durable `TaskRunState`
  keeps a canonical task digest, backend history, effective class and compact
  evidence, not objective or source text. Backend `completed` is only a
  candidate result; an evidence-backed classification can rise but never
  silently decrease.
  SQLite schema v5 adds an independent task-run table and migrates v4 and
  earlier files additively. The host-side validator reads actual artifact
  bytes and rejects absent, empty or wrong-digest artifacts. Restart, stale
  transition, ownership and migration tests are included. This is not yet
  wired into ordinary Agent execution.
- Added `deploy/windows-preview/gateway-default.json`, a secret-value-free
  fragment with the exact approved `company` route, `gpt-5.5`,
  `LITELLM_MASTER_KEY` environment-variable mapping and `UNCLASSIFIED`
  approval. The installed preview at
  `%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0` has been upgraded
  with the local wheel and its `host.json` now records that approval. Settings
  edits keep it only when the URL, alias, provider and credential mapping are
  unchanged; another route clears it. No token value was written to JSON.

## Verification

- The final full local selection, using `PYTHONUTF8=1`, fresh
  `.scratch/pytest-gateway-default-final-full-20261002`, no pytest cache,
  `--ignore=tests/test_browser.py` and two existing machine-specific
  exclusions: **1,534 passed, 4 skipped, 2 deselected**. The first run had
  one transient Windows `os.replace` access denial in extension staging; it
  passed both alone and in the final full run. Focused Gateway tests passed
  **16 tests**.
- `.venv/Scripts/python -m ruff check src tests` passed. Mypy passed for 283
  files. Final sdist and wheel built in
  `.scratch/dist-gateway-default-final-20261002`; the inline Web JavaScript
  passed `node --check` before the final Python-only edit.
- The installed `aep-host doctor` successfully parses the approved route.
  `models` reports that `LITELLM_MASTER_KEY` is absent in the Agent shell.
  A host-permission check later found LiteLLM listening on port 4000; its
  `/v1` root returns FastAPI's `{"detail":"Not Found"}`, as expected for an
  API root. A live authenticated model round trip was not possible.
- Agent Web itself was confirmed at the separate loopback Web port: an
  authenticated GET of the freshly started page and `/api/backends` both
  returned HTTP 200. On 2026-10-02 a fresh instance used port 53582 and its
  temporary tokenized launch address was opened in the default browser.
- The real-Chromium UI test still fails before navigation because this
  machine closes its CDP WebSocket; no visual interaction result is claimed.

## Outstanding work and risks

- The approval gate is configured and LiteLLM was listening on port 4000 at
  the latest host-permission check. The Agent Web instance started in this
  shell still reports its mapped credential unavailable. Give the Agent
  process `LITELLM_MASTER_KEY` and restart it before testing a real model
  answer. The Web URL is the temporary address printed by `aep-host web`,
  not the Gateway API's `http://127.0.0.1:4000/v1`. Do not copy this
  workstation's approval to another host without its own approval decision.
- The current classifier conservatively treats every AEP model request as
  UNCLASSIFIED. Future per-source provenance must preserve Knowledge citation
  and attachment labels before native task backends receive any content.
  PUBLIC session declaration is an explicit operator statement, not a
  guarantee that human-entered text is actually public.
- `BackendRouter` currently registers only Gateway for governed conversation.
  Native task adapters still need workspace, environment, credential and
  side-effect containment. Portable task state and independent validation
  exist as contracts but are not yet linked to Agent ingress or native adapters.
- The portable task state does not yet record task-specific completed steps,
  unresolved requirements or a re-authorized backend transition. These fields
  should be added when an actual orchestration path can populate and verify
  them; initial backend use history alone does not make failover safe.
- The initial independent validator covers artifact presence, non-empty bytes
  and an optional expected digest. Domain-specific content checks and
  evidence-only answers require later validators. The selected backend must
  never supply the host's trusted artifact reader.
- The data-class vocabulary recognizes RESTRICTED, but ordinary Gateway
  approvals cannot include it until a separately reviewed environment exists.
  Backend switching is disabled in portable state until full-context
  re-authorization is implemented.
- The private source Workflow checkout is read-only at
  `C:\Users\Chi_L\Documents\claude\n8n_workflow_system`, revision
  `896046e8fe2170d21f9213e56e5ce2f93c05ba43`. Remote HEAD could not be
  verified with available GitHub REST scope. Hermes Skills and migrated
  Workflows require individual provenance/license/dependency/policy review.

Next action: connect ordinary Agent ingress to admission, data policy,
portable run state and host-owned completion validation while preserving
deterministic slash/Workflow routes. Do not enable native task backends until
workspace, environment, credentials and side effects have denial tests.
