# Handoff — Phase 7 local-first distribution and remote control

Updated: 2026-09-22 (Asia/Taipei).
Branch: `phase-7/local-first-control`, stacked on
`phase-7/windows-preview-bundle` at `cc7cfc9`.
Implementation commit: `88fec63`.
PR: https://github.com/dragon0816/agentic-engineering-platform/pull/50 (open;
PR #48 then PR #49 must merge first).

Progress across phases is in `docs/TASKS.md`. This file records only where the
current work stopped and how to resume it.

## Goal

Apply the owner's local-first deployment decision: the resident Personal Agent,
installed Skills/Workflows, complete run state and corporate credentials belong on
the Bridge computer. The shared platform distributes published assets and projects
Bridge state. Remote requests remain member-scoped: a company workstation accepts
its one bound owner and a shared test workstation accepts its bound platform users.
Telegram is a future ingress to the same resident Agent and policy path.

Active specification: `docs/phases/PHASE_7_MIGRATION.md`.
Implementation plan: `docs/PHASE_7_LOCAL_FIRST_CONTROL.md`.
Source decision: `docs/PHASE_7_MIGRATION.md`.

## Completed

- Reconciled the owner decision with the already-approved Personal Engineering Plane
  and Team Platform Plane. The shared platform's primary purposes are Registry/package
  distribution and remote control/status projection; it is not local run authority.
- Added `PublishedAssetPackage`, `InstallationPlan` and `InstalledAsset`. A published
  exact package can be discovered and planned, but neither action grants execution.
- Added an in-memory Registry and local inventory reference. It verifies every byte
  payload SHA-256 before one inventory mutation, records exact provenance, imports no
  code and remains readable after the Registry is unavailable.
- Added `BridgeStateSnapshot`, `LocalRunSummary` and `BridgeStatusProjection`. The
  Bridge snapshot is authoritative; the central projection preserves it and becomes
  `stale` after a declared interval rather than inventing current state.
- Added `RemoteWorkflowJob` with explicit `shared_platform`/`telegram` ingress,
  actor, Bridge, exact Workflow, arguments, trace and matching allowed runtime grant.
  Secret fields/values and arbitrary command/shell fields are refused.
- Added a bounded inert remote queue. It calls an enrollment admission boundary,
  enforces that company requests come from the registered/bound owner, permits bound
  users of a shared test computer, preserves actor/channel and models cancellation as
  a request rather than a false claim that an effect stopped.
- Strengthened `reject_embedded_secrets` to reject secret-named mapping fields, not
  only recognizable credential strings in their values.
- Inspected the pinned `telegram-local-agent` Telegram channel/handler at
  `4b40a215909e4fdd4b65519d70669a84e9abd43d`. Decision **ADAPT** outbound polling,
  numeric sender checking and deterministic direct commands in a later slice. Do not
  copy embedded token configuration, provider/UI coupling or its unsafe behavior
  that allows every sender when `allowed_users` is empty.
- Added seven tests after recording requirements; initial collection failed because
  `common.distribution` did not exist, then focused/full verification passed.

## In Progress

- PR #50 is open and stacked on PR #49. All eight reported matrix checks passed
  (duplicate push/pull-request runs for Linux/Windows and Python 3.11/3.12).

## Remaining

- Merge stack in order: enrollment PR #48, Windows preview PR #49, then local-first
  contracts PR #50. Retarget/rebase each dependent PR without flattening its scope.
- Slice 2d: implement a resident local Agent host/interface and durable local
  inventory/run-state adapter. Company work must remain usable offline for assets
  whose manifests do not require central services.
- Implement authenticated Registry synchronization/download around the exact package
  contract. Installation still must be explicit, digest verified and separate from
  execution authorization.
- Implement Telegram polling as an optional local ingress. Resolve bot token through
  `SecretRef`, fail closed when no numeric sender mapping exists, map one sender to a
  platform actor, then use the same routing, binding and policy path.
- Implement authenticated shared-platform Bridge polling/status transport. No
  arbitrary shell/desktop control. Then migrate workflow 7, workflow 13 and knowledge
  in the approved order.

## Architecture decisions and invariants

- Local installed assets and detailed run state are authoritative. Central status is
  a timestamped projection and must display stale when reports stop.
- A company workstation may be remotely operated, but only by its single bound owner.
  A shared test workstation may be operated by its active bound users.
- Telegram and shared-platform ingress converge before routing/authorization. A
  channel allowlist cannot replace platform actor/device admission.
- Telegram uses outbound polling and needs no inbound company firewall opening.
- Publication, package discovery, installation, device membership and execution
  authorization remain distinct decisions.
- Remote jobs name exact Workflows. The initial remote-control contract has no shell,
  desktop-control or raw capability-execution field.
- Tokens and corporate credentials stay local and are references/host configuration,
  never Registry packages, jobs, snapshots, traces or Git content.

## Exact verification commands and results

Windows, Python 3.12.14, repository root:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_local_first_control.py -q -p no:cacheprovider --basetemp .scratch/pytest-local-first
# 7 passed

.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp .scratch/pytest-local-control-full
# 711 passed, 3 skipped (Windows symbolic-link privileges)

.venv/Scripts/python.exe -m ruff check .
# All checks passed
.venv/Scripts/python.exe -m ruff format --check .
# 145 files already formatted
.venv/Scripts/python.exe -m mypy
# Success: no issues found in 110 source files
.venv/Scripts/python.exe -m build
# Successfully built wheel and sdist
.venv/Scripts/python.exe -m pip check
# No broken requirements found
git diff --check
# clean
```

All tests are inert. No socket, Telegram call, artifact download, executable import,
process launch, filesystem production write or Workflow execution occurred.

PR #50 CI: Ubuntu 3.11/3.12 and Windows 3.11/3.12 all passed.

## Known issues

- PR #50 is stacked and its two base PRs are unmerged.
- The reference stores are in memory. They are contract proofs, not a production
  Registry, installer, local run database or authenticated transport.
- Telegram is represented only as an ingress value and migration decision. There is
  no Telegram dependency, polling process, sender mapper or token resolver yet.
- The installed Windows preview remains preflight-only and does not contain this
  branch until the PR stack merges and a later preview package is built.
- `.claude/` is user-owned, remains untracked and was not modified or committed.

## Next Recommended Action

After the PR stack is merged, implement slice 2d as a resident local Agent host with
a minimal local interface and persistent local inventory/status. Add Telegram sender
mapping and outbound polling as a separate adapter over the same local Agent request
contract; first prove an unauthorized sender and an unbound actor are both refused.
