# Handoff — Product Vision and Agent/Harness proposal

Updated: 2026-09-24 (Asia/Taipei).
Branch: `codex/product-vision-proposal`.
Base: `main` at merge commit `d98f939` (PR #96).
Pull request: #97, open against `main` for owner review.

Progress across all phases remains in `docs/TASKS.md`. This file records the
current stopping point and the evidence needed to continue without chat history.

## Completed

- PR #96 was merged only after all eight CI matrix jobs passed on Ubuntu and
  Windows with Python 3.11 and 3.12. The reviewed head was `ac013c0`; the merge
  commit is `d98f939`.
- Added `docs/PRODUCT_VISION.md` as a product-level design constraint. It makes
  the Personal Engineering Agent and Coding Harness, measured by three V1
  benchmark categories, the first product milestone.
- Added `docs/AGENT_HARNESS_ARCHITECTURE_PROPOSAL.md` with the current
  architecture summary, reusable components, gaps, proposed boundary, benchmark
  paths, integration models, implementation slices, risks and recommended
  architecture amendments.
- Updated README, Roadmap and Tasks so the Vision and proposal are discoverable
  and PR #96 is recorded as merged.

## In progress

- Owner review of the proposed Agent/Harness boundary and implementation order.
  No runtime or shared contract has changed on this branch.

## Remaining

- After owner approval, amend `docs/ARCHITECTURE.md`, `docs/ROADMAP.md` and an
  active phase specification in a small architecture-only PR.
- Then implement benchmark contracts and inert fixtures, Harness contracts, and
  the parser/transformation vertical.
- Phase 7 production validation remains: company-workstation Outlook/model/
  browser checks, workflow 11 workbook recovery and parity, workflow 10 slices
  4b–4d, workflow 13 and Knowledge-copy parity.

## Architecture decisions proposed, not yet approved

- Keep the control-plane/Bridge split and existing governance, model, Workflow,
  Knowledge, evaluation and trace contracts.
- Place the Coding Harness in the Personal Engineering / Execution Plane as a
  bounded service used by one Personal Engineering Agent.
- Let external validators decide completion; model confidence is never evidence.
- Defer specialist agents, the full Continuous Evolution Engine and more one-off
  integrations until the three V1 benchmarks pass.
- Add Software and Improvement Request contracts later at their defined seams.

## Verification

```text
GitHub Actions runs 36004616007 and 36004621522
8/8 jobs passed: Ubuntu/Windows x Python 3.11/3.12
merged exact head: ac013c08fc168439d690918bbc903afaaacd770a
git diff --check
documentation link/existence check
```

## Known issues

- This proposal does not resolve the remaining Phase 7 production validation.
- PR #96's slowest Windows 3.11 CI job passed in 10m06s; browser lifecycle tests
  are integration-heavy and vary substantially in duration.
- `.claude/` is untracked user-owned state and must not be committed or removed.

## Next recommended action

Review `docs/PRODUCT_VISION.md` and
`docs/AGENT_HARNESS_ARCHITECTURE_PROPOSAL.md`. If the boundary and sequence are
accepted, approve a narrow architecture-baseline update before new Harness
runtime implementation.
