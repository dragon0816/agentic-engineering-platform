# Handoff

Date: 2026-10-02 (Asia/Taipei)

Branch: `main`; local-only work, no push. Backend boundary is commit
`4f5b92c`; data trust is commit `c15d8d0`. The portable task/state slice
described below is the current handoff.

Status: multi-backend Agent Orchestrator slices 1–2 and the portable task/state
contract subset of slice 3 are complete in source. Normal Agent ingress is not
yet connected to portable task state; backend re-authorization, native task
adapters, Workflow migration, Marketplace defaults and product E2E remain.

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

## Verification

- Full local selection on the final task result and classification contract,
  using `PYTHONUTF8=1`, fresh `.scratch/pytest-task-3b-full-20261002`, no
  pytest cache, `--ignore=tests/test_browser.py` and two existing
  machine-specific exclusions: **1,531 passed, 4 skipped, 2 deselected**.
- `.venv/Scripts/python -m ruff check src tests`: passed.
- `.venv/Scripts/python -m mypy src tests`: passed, 283 source files.
- `.venv/Scripts/python -m build --no-isolation --outdir
  .scratch/dist-task-3b-20261002`: sdist and wheel built.
- The earlier slice-2 inline Web JavaScript passed `node --check`.
- The real-Chromium UI test still fails before navigation because this
  machine closes its CDP WebSocket; no visual interaction result is claimed.

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
