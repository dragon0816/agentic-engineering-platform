# Handoff — Phase 7 Windows company-host preview

Updated: 2026-09-22 (Asia/Taipei).
Branch: `phase-7/windows-preview-bundle`, stacked on
`phase-7/enrollment-foundation` at `552e04a`.
Implementation commits: `633e4e3`, `36edaff`.
PR: https://github.com/dragon0816/agentic-engineering-platform/pull/49 (open,
base PR #48 must merge first).

Progress across phases is in `docs/TASKS.md`. This file records only where the
current work stopped and how to resume it.

## Goal

Give the owner a real Windows artifact to carry to the company computer while the
authenticated enrollment transport and workflow 7/13 capability adapters are still
pending. Prove offline installation, local company-device configuration, host
preflight and credential-free enrollment-request export without claiming that this
preview is a running Agent/Bridge service.

Active specification: `docs/phases/PHASE_7_MIGRATION.md`.
Source decision: `docs/PHASE_7_MIGRATION.md`.

## Completed

- Inspected the pinned `rs_workflow_system` deployment scripts at
  `896046e8fe2170d21f9213e56e5ce2f93c05ba43` without modifying the source.
- Decision **ADAPT**: retained its no-credential offline bundle, recorded target,
  integrity verification, per-user install and safe uninstall invariants. Did not
  copy token login, HTTP server, jobs, browser state, prerequisites or autostart.
- Added closed `CompanyHostConfiguration`, `HostDoctorReport` and
  `EnrollmentRequest` contracts. They cannot carry invitation proof, credentials,
  permissions or capability grants.
- Added the `aep-host` CLI. `doctor` checks Windows, Python 3.12, the approved company
  device profile and workspace without network/capability calls. `enrollment-request`
  exports matching `BridgeDevice` and empty `BridgeRegistration` metadata.
- Added a deterministic bundle builder and Windows cmd/PowerShell install, verify
  and uninstall entry points. Install verifies SHA-256 for every payload before an
  offline wheel install. Uninstall is dry-run by default and path constrained.
- The installer requires only `-Actor` for identity input. It derives
  `bridge-<normalized-computer-name>` by default, prints it, and retains optional
  `-BridgeId` for a collision. The name is metadata, never authentication proof.
- Added nine contract/bundle tests and Windows CI that builds, installs, checks,
  exports and removes the preview locally, then uploads its ZIP artifact for 14 days.
- Performed a real local offline install from the extracted ZIP, received four
  passing doctor checks, exported and inspected enrollment JSON, exercised dry-run
  uninstall, and removed the isolated installation.
- Local deliverable (ignored by Git):
  `dist/agentic-engineering-platform-windows-preview-0.1.0-d1a97fbda097.zip`.
  SHA-256: `18A24BBC1782BF326CD993D439CE289647A1D7E0C651C62CB71364884958A370`.

## In Progress

- PR #49 is awaiting stacked review. Its base PR #48 is the enrollment foundation
  and must merge before #49 is retargeted or merged. All eight reported matrix
  checks passed (duplicate push/pull-request runs for four matrix cells).
- The owner can copy the local ZIP to a company computer now. CI will also expose a
  fresh ZIP under `windows-company-host-preview-<commit>` for 14 days; the successful
  run is https://github.com/dragon0816/agentic-engineering-platform/actions/runs/35696109156.

## Remaining

- On the company computer, confirm 64-bit Python 3.12, extract the ZIP, run
  `install.cmd -Actor <platform-actor>`, confirm the printed computer-name-derived
  Bridge ID, retain the complete doctor output and inspect the enrollment request.
- Slice 2b: implement the shared-platform authenticated invitation/device enrollment
  endpoint and Bridge client, then add a read-only connectivity probe. Do not treat
  the JSON exported by this preview as authentication proof.
- Add governed Jira/Excel capabilities and migrate workflow 7 only after enrollment
  and connectivity evidence. Workflow 13 and knowledge remain later in the approved
  order. The old Host Bridge stays available as parity baseline and rollback.

## Architecture decisions and invariants

- This is explicitly an installation/device preflight, not a production Agent or
  Bridge. It has no server transport and cannot execute workflows 7 or 13.
- The ZIP targets Windows AMD64 and CPython 3.12 exactly because `pydantic-core` is
  platform/Python-specific. The target is recorded in its manifest and checked.
- The bundle carries code and dependency wheels only. Actor/Bridge ID and workspace
  configuration are created during installation; passwords and tokens are forbidden.
- An enrollment request is an inspectable advertisement with no capabilities. It
  grants neither device membership nor workflow/capability execution permission.
- Installation is per Windows user because later Excel/browser work needs an
  interactive user session. No autostart or service is installed by this preview.
- CI and doctor stay inert. Real company-resource verification occurs only on the
  company computer after capability adapters and explicit authorization exist.

## Exact verification commands and results

Windows, Python 3.12.14, repository root:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_host_runtime.py tests/test_windows_preview_bundle.py -q -p no:cacheprovider --basetemp .scratch/pytest-preview
# 9 passed

.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp .scratch/pytest-full
# 704 passed, 3 skipped (Windows symbolic-link privileges)

.venv/Scripts/python.exe -m ruff check .
# All checks passed
.venv/Scripts/python.exe -m ruff format --check .
# 141 files already formatted
.venv/Scripts/python.exe -m mypy
# Success: no issues found in 107 source files
.venv/Scripts/python.exe -m build
# Successfully built wheel and sdist
.venv/Scripts/python.exe -m pip check
# No broken requirements found
git diff --check
# clean
```

Bundle verification used `scripts/build_windows_preview.py`, expanded the result,
ran `install.ps1` with an isolated LocalAppData install root, ran `aep-host doctor`
and `enrollment-request`, then ran `uninstall.ps1` first without and then with
`-Apply`. Result: offline dependencies installed, host status `ready`, all four
checks passed, empty advertisement exported, dry-run reported the exact target and
apply removed it.

PR #49 CI: Ubuntu 3.11/3.12 and Windows 3.11/3.12 all passed. The Windows
3.12 job also passed the bundle build, offline install, doctor, enrollment export,
dry-run uninstall, applied uninstall and artifact upload steps.

## Known issues

- PR #49 is stacked on unmerged PR #48; review/merge must preserve that dependency.
- Python 3.11 and ARM64 are unsupported by this artifact. The library remains tested
  on Python 3.11/3.12, but the offline dependency wheel fixes this ZIP to 3.12 AMD64.
- There is no shared-platform login/enrollment server, persistent device record,
  Bridge pull loop, capability adapter, service/autostart or connectivity probe yet.
- `verify.cmd` uses the default versioned install location. A custom `-InstallRoot`
  must be checked by invoking its installed `aep-host.exe` directly.
- `.claude/` is user-owned, remains untracked and was not modified or committed.

## Next Recommended Action

Merge PR #48 after review, let PR #49 rebase/retarget to `main`, wait for all CI
checks, then use its Windows artifact (or the local ZIP above) for the company-PC
installation preflight. Record that output before designing slice 2b transport.
