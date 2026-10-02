# Handoff

Date: 2026-10-02 (Asia/Taipei)

Branch: `main`; local-only work, no push.

Status: multi-backend Agent Orchestrator slice 1 complete. The overall harness,
Workflow migration, Marketplace and E2E program is still active.

## Goal and approved boundary

The owner approved the incremental design in
`docs/MULTI_BACKEND_ORCHESTRATOR_PHASE0.md` and
`docs/superpowers/specs/2026-10-02-multi-backend-orchestrator-design.md`.
Strengthen the Agent first, then migrate the pinned source Workflows with
standardized parameter UI, publish reviewed defaults and prove user-level
SOP/Knowledge/Skill scenarios. Unclassified data may use only a suitably
approved internal Gateway; native Codex/Claude task backends require the full
transferred context to be explicitly PUBLIC. No availability fallback may
override eligibility. `docs/DECISIONS.md` records this choice.

## Completed in slice 1

- Added closed backend profile and health contracts, a generic execution
  protocol and exact-selection router. Inconsistent model/native harness pairs,
  duplicate IDs, ineligible/unavailable/mismatched selections are rejected.
- Wrapped existing `Gateway.converse` in `GatewayModelBackend` and routed
  admitted `LocalAgent.converse` requests through it. Gateway remains the sole
  eligible registered backend. Existing response, tool evidence, durable run
  recording and Bridge policy continue unchanged. Deterministic paths were not
  modified.
- Added contract, adapter and admission regression tests. Recorded approved
  requirements, architecture decision and revised prerequisites for the
  pre-existing product E2E order.

## Verification

- Full local test selection with `PYTHONUTF8=1`, `-p no:cacheprovider`, a fresh
  `.scratch` basetemp, `--ignore=tests/test_browser.py`, and the two existing
  machine-specific exclusions: 1,516 passed, 4 skipped, 2 deselected.
- `.venv/Scripts/python -m ruff check src tests`: passed.
- `.venv/Scripts/python -m mypy src tests`: passed, 276 source files.
- `.venv/Scripts/python -m build --no-isolation --outdir
  .scratch/dist-backend-20261002`: sdist and wheel built.
- `git diff --check`: passed. The initial unspecialized browser test failed
  because local Chromium closed its WebSocket. The first complete run had an
  incorrect new test expectation and a CP950 subprocess decode failure;
  both focused reruns and the final full selection passed with UTF-8 mode.

## Still to do

The current router accepts an eligibility set supplied by its caller, but no
data classifier exists yet. Do not register a native task backend until slice
2 denies unclassified/non-PUBLIC outbound context before sending any bytes and
records why. After that, add portable task/run state and independent
completion validation, then native adapters with workspace and credential
containment. The existing Codex/Claude restricted CLI text-chat feature is a
separate path and does not satisfy those gates.

The private source Workflow repository is available as a read-only pinned local
checkout at `C:\Users\Chi_L\Documents\claude\n8n_workflow_system`, revision
`896046e8fe2170d21f9213e56e5ce2f93c05ba43`; current remote HEAD was not
verified with available REST scope. Source jobs and Hermes Skills still need
individual provenance, license, dependency and policy review before migration
or publication. No source repository file was modified.

Next action: design and test the fail-closed data classification/eligibility
contract for all outbound context, then attach it to backend selection before
any native task adapter is enabled.
