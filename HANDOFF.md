# Handoff — Phase 3 optional offline n8n adapter

Updated: 2026-09-21 (Asia/Taipei).
Branch: `phase-3/n8n-adapter`, based on merged `main` at `00ecabf` (PR #14).
Implementation commit: `e95c8e5`.
PR: https://github.com/dragon0816/agentic-engineering-platform/pull/15 (open, unmerged).

## Goal

Complete Phase 3 slice 8: optional n8n adapter through shared Gateway contracts,
with offline validation only. The owner explicitly chose this over the durable
step-state contract. No live n8n/production connection or persistence is authorized
by this slice. Requirements: `docs/phases/PHASE_3_WORKFLOW.md` (slice 8).

## Completed

- Reconciled Claude's latest handoff: PRs #12 (resumption), #13 (Gateway run control)
  and #14 (progress streaming) are already merged. Baseline actually passed 295
  tests, and main CI passed at `00ecabf9d08ad06d82fe1832d22d158e68b3f66e`.
- Inspected pinned rs_workflow_system `workflows/13_release_package.json` at
  `896046e8fe2170d21f9213e56e5ce2f93c05ba43`. Added a credential-free declarative
  graph projection and checksum-backed source characterization. No source modified.
- Added shared `Gateway.execute_workflow` exact-target entry point. Routed
  workflows and optional adapter submissions both use it; engine/Bridge still own
  validation, dependencies, permission checks, timeouts and idempotency.
- Added optional `integrations.n8n`: trusted N8nWorkflowBinding, closed
  N8nSubmission (operation_id + arguments), and N8nAdapter.submit/inspect/watch.
  Core Gateway does not import the adapter; no n8n SDK/dependency was added.
- Binding fixes the exact workflow; separately authenticated RequestContext fixes
  the caller. Payloads cannot specify identity, target, credentials, policy or
  execution-control options. Submission bypasses message routing/models.
- Stable binding/operation ids derive an engine key. Duplicate/concurrent delivery
  returns/joins the same run; changed arguments/context/target conflict. Failed
  deliveries are not retried/resumed automatically. Existing capacity/lifetime
  semantics apply. Inspection/progress require owner and bound workflow.
- Added offline host-wiring documentation and sample submission, included in sdist.
  Adapter returns existing WorkflowRunSnapshot without a new response wrapper;
  consumers use run.status == succeeded rather than the source HTTP envelope.
- Added 28 source/contract/runtime/integration tests (323 total). Existing routing,
  retry, resumption, run control and progress tests remain passing.

## In Progress

- No implementation work remains in this slice. PR #15 is open for review;
  final merge checks are visible on the PR.

## Remaining

- Review the n8n-adapter PR. No automatic merge of this new slice.
- Durable step-state/persistence contract remains unscoped: choose scope with the
  owner before implementation. No store, crash recovery or cross-process keys.
- A live adapter deployment would separately require an authenticated transport,
  reviewed host bindings, installed workflows/capabilities and n8n configuration.
  This slice is not an HTTP service, importable n8n node or production workflow.
- Existing deferred reviews remain: bounded Bridge event history, SkillRegistry
  parse cost, MCP installation round trips, Review not_required semantics, generic
  top-level package names and repeated RequestContext validation.

## Architecture decisions made

- ADAPT the newer source graph's one-dispatch/status boundary, preserving the
  Bridge/job separation instead of copying historical n8n business logic.
  `docs/PHASE_3_MIGRATION.md` records preserved and intentionally changed behavior.
- The host chooses binding and authenticates context; incoming JSON supplies only
  operation id/arguments. Publication/discovery never grants execution permission.
- No adapter retries, automatic resume, model selection, cache or key store.
  Workflow execution and run-control semantics remain shared Gateway contracts.
- Binding + operation id keys are scoped by engine actor/namespace. Context must
  remain stable across redelivery except trace; returned results keep the original
  trace. Retargeting a stable binding under the same operation conflicts.
- Status mapping is explicit: succeeded means success; workflow_timeout is a
  caller-wait overlay. Use inspect/watch or the same operation id rather than a
  fresh submission. Snapshots contain validated results; streams contain metadata.
- Optional means no n8n dependency or connection unless the host explicitly selects
  this integration. The fixture is for graph characterization, not n8n import.

## Exact verification commands and results

Repository root; Windows, Python 3.12.14:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 323 tests
.venv/Scripts/python.exe -m ruff check .
# PASS
.venv/Scripts/python.exe -m ruff format --check .
# PASS: 71 files (includes ignored local scratch files and Markdown code examples)
.venv/Scripts/python.exe -m mypy
# PASS: 49 source/test files
.venv/Scripts/python.exe -m pip check
# PASS
.venv/Scripts/python.exe -m build
# PASS: sdist and wheel
.scratch/wheel-env/Scripts/python.exe -m pip install --no-deps --force-reinstall dist/agentic_engineering_platform-0.1.0-py3-none-any.whl
# PASS
.scratch/wheel-env/Scripts/python.exe -I -c "import sys; import agent.gateway; assert 'integrations.n8n' not in sys.modules; from integrations.n8n import N8nSubmission; import integrations.n8n; item = N8nSubmission(operation_id='offline-1'); assert N8nSubmission.model_validate_json(item.model_dump_json()) == item; print(integrations.n8n.__file__); print('optional adapter wheel smoke passed')"
# PASS: core import does not load integration; explicit import from wheel site-packages
.venv/Scripts/python.exe -c "import tarfile; archive=tarfile.open('dist/agentic_engineering_platform-0.1.0.tar.gz'); names=archive.getnames(); assert any(n.endswith('/integrations/n8n/README.md') for n in names); assert any(n.endswith('/integrations/n8n/submission.json') for n in names); print('sdist offline docs and example included')"
# PASS: docs and sample present
git diff --check
# PASS
```

Tests preceded implementation: initial collection failed because integrations.n8n
was absent. Final full suite passed with inert handlers; no JS expression, HTTP
node, n8n instance, production job, notification or real model executed. Local
pytest and reading the built sdist required elevation due existing filesystem ACLs;
optional pytest cache is disabled locally. CI uses ordinary pytest on fresh workers.

Remote implementation verification:
`gh api repos/dragon0816/agentic-engineering-platform/actions/runs/35544570859/jobs --jq '.jobs[] | {name,status,conclusion}'`
confirmed all four Windows/Linux, Python 3.11/3.12 jobs passed on implementation
`e95c8e55f5d8c4b023d2f726f80e8e2c34cab6ff`.
Run: https://github.com/dragon0816/agentic-engineering-platform/actions/runs/35544570859
This handoff-only follow-up triggers fresh CI; PR #15 records the final head checks.

## Known issues / limitations

- Engine idempotency is in-memory, capped at 50 retained keys. Restarting/replacing
  it loses keys; new operation ids mean new work. Do not clear/restart automatically
  on capacity or timeout. This is not durable exactly-once execution.
- Host authentication and a network transport are intentionally absent. The adapter
  is an offline Python seam, not a deployed n8n integration or release implementation.
- Raw operation ids are caller data, never credentials; callers must keep them
  stable on redelivery. Shared snapshot payloads require appropriate access control.
- User/Claude's `.claude/` directory remains untouched and uncommitted.

## Next Recommended Action

Review the n8n-adapter PR and its final CI. After merge, scope the durable
step-state contract with the owner before persistence code: define retained data,
uncertain-effect recovery, ownership, key lifetime and restart behavior. Keep
production transports/jobs and durable guarantees outside that work until scoped.
