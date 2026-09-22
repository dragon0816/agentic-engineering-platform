# Handoff — Phase 7 enrollment foundation

Updated: 2026-09-22 (Asia/Taipei).
Branch: `phase-7/enrollment-foundation`, based on `main` at `201071e`.
Implementation commit: `de1f1b2`.
PR: https://github.com/dragon0816/agentic-engineering-platform/pull/48 (open).

Progress across phases is in `docs/TASKS.md`. This file records only where the
current work stopped and how to resume it.

## Goal

Start Phase 7 from the owner's resolved deployment and migration decisions. Define
invitation-only platform users and independent Bridge device identity for a one-user
company workstation and a multi-user shared test workstation, without claiming OS
isolation or adding a production authentication/RBAC server. Record explicit parity
gates for source workflows 7 and 13 before their implementation migration.

Active specification: `docs/phases/PHASE_7_MIGRATION.md`.
Source decision: `docs/PHASE_7_MIGRATION.md`.

## Completed

- Reconciled Phase 6 closure and the accumulating progress record on main.
- Recorded owner decisions: invitation-only registration; shared platform as control
  plane; real validation on a company Agent + Bridge; company workstation single
  employee; shared test workstation multiple platform users on one Windows account;
  workflow 7, then 13, then knowledge; inert CI and retained old paths for rollback.
- Inspected pinned `rs_workflow_system` workflow 7/workflow 13 graphs and their
  `jira_weekly_report.py` / `release_package.py` jobs at
  `896046e8fe2170d21f9213e56e5ce2f93c05ba43` without changing the source.
- Added the Phase 7 specification with normalized, harness-checkable report/package
  parity gates, company/test workstation boundaries, migration order and rollback.
- Added closed contracts: Invitation, PlatformUser, BridgeDevice, BridgeBinding and
  BridgeExecutionSubject. They contain no invitation token, password, session,
  credential, permission grant, capability grant or SecretRef value.
- Added `InMemoryEnrollmentRegistry`, a side-effect-free trusted-host reference for
  issuing/accepting one-time invitations, enrolling Bridge advertisements, binding
  one/many users by device kind, use-time admission and independent disable state.
- Added 18 tests before/with implementation. Initial collection failed because the
  contract did not exist; focused and full suites now pass.
- Updated Architecture/Roadmap/Contracts/README/CLAUDE/TASKS so Phase 7 is active
  and a later agent does not rely on this conversation.

## In Progress

- PR #48 is open for review and cross-platform CI. This follow-up records the PR
  number in the persistent progress and handoff files.

## Remaining

- Review and merge the enrollment foundation after cross-platform CI.
- Slice 2: define/package the company Agent + Bridge installation, authenticated
  invitation acceptance/device enrollment host flow and read-only connectivity
  probe. This requires a deployment design; this slice is not an installer/server.
- Slice 3: characterize and adapt workflow 7 through typed Jira/Excel capabilities,
  inert fixtures first, then production-like comparison on the company computer.
- Slice 4: characterize and adapt workflow 13 through typed Git/file capabilities,
  dry-run and an isolated test repository before any approved push.
- Knowledge parity, model live smoke checks and controlled cutover follow in the
  order specified. No source entry point is deprecated yet.
- Existing carried items remain in `docs/TASKS.md`.

## Architecture decisions and invariants

- Invitation identifiers are metadata, not bearer secrets. A future host validates
  out-of-band proof and authenticates callers before invoking registry methods.
- Platform user, Bridge device, runtime capability authorization and external-system
  credentials are distinct. Enrollment never grants a workflow/capability or secret.
- The shared test computer's per-user workspaces are cooperative organization only;
  a shared Windows account provides no confidentiality from other local users.
- `interactive_slots=1` records the initial serialized-interaction requirement; no
  runtime scheduler/lease is implemented by this slice.
- The shared platform does not execute Jira/Excel/Git work. Company resources and
  their credentials remain on the company Bridge.
- Preserve and adapt source behavior; keep the old Host Bridge as parity baseline
  and rollback until candidate-specific gates and rollback rehearsal pass.

## Exact verification commands and results

Windows, Python 3.12.14, repository root, office extra installed:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_enrollment.py -q -p no:cacheprovider
# RED before implementation: ModuleNotFoundError: common.enrollment
# PASS after implementation: 18 passed
.venv/Scripts/python.exe -m pytest tests/test_enrollment.py tests/test_contracts.py tests/test_registry.py -q -p no:cacheprovider
# PASS: 61 passed
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 695 passed, 3 skipped (Windows symlink privileges)
.venv/Scripts/python.exe -m ruff check .
# PASS
.venv/Scripts/python.exe -m ruff format --check .
# PASS: 133 files
.venv/Scripts/python.exe -m mypy
# PASS: 101 source/test files
.venv/Scripts/python.exe -m pip check
# PASS
.venv/Scripts/python.exe -m build
# PASS: sdist and wheel; new common/control_plane modules included
.scratch/wheel-env/Scripts/python.exe -m pip install --no-deps --force-reinstall dist/agentic_engineering_platform-0.1.0-py3-none-any.whl
# PASS
.scratch/wheel-env/Scripts/python.exe -I -c "from common.enrollment import BridgeDevice; from control_plane.enrollment import InMemoryEnrollmentRegistry; item=BridgeDevice(bridge_id='bridge-test',registered_by='engineer',device_kind='shared_test_workstation',windows_account_mode='shared_user',resource_scope='external_only',local_isolation='cooperative_workspace'); assert BridgeDevice.model_validate_json(item.model_dump_json()) == item; assert InMemoryEnrollmentRegistry(administrators=('admin',)); import control_plane; print(control_plane.__file__); print('phase7 wheel smoke passed')"
# PASS from isolated wheel site-packages
git diff --check
# PASS
```

No LDAP, network service, live model, Jira, Excel, Git write, production Bridge or
n8n instance was invoked by the implementation or tests. Source inspection was
read-only through GitHub.

## Known issues / limitations

- This is contract/reference behavior only: no login UI, invitation-token storage,
  password/session service, durable enrollment DB, device certificate or installer.
- Registry methods assume a trusted authenticated host. Calling them directly is
  not proof of identity and must not become a public API unchanged.
- Interactive serialization is declared but not enforced by a scheduler/lease.
- Shared Windows users can inspect local files/processes regardless of platform
  membership. Sensitive corporate data must not be placed on that workstation.
- Real parity evidence does not exist yet; inert CI must not be reported as parity.
- User/Claude's untracked `.claude/` directory remains untouched and uncommitted.

## Next Recommended Action

After review/merge, scope Phase 7 slice 2 around an installable company Agent +
Bridge host and authenticated enrollment protocol. Prove a read-only connection and
capability advertisement before migrating workflow 7.
