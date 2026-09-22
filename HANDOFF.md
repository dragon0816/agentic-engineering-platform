# Handoff — Phase 7 slice 2g, member-decided asset authorization

Updated: 2026-09-22 (Asia/Taipei).
Branch: `phase-7/member-authorization`, based on `main` after PR #57 merged.

Progress across every phase is in `docs/TASKS.md`. This file is only where
the current work stopped and how to resume it, and is rewritten each time.

## Goal

Implement the owner's rule of 2026-09-22: a platform user decides, for each
device they may use, which Workflows, which Skills and which tools that device
may run for them. Requirements: the "Slice 2g" section of
`docs/phases/PHASE_7_MIGRATION.md`; contracts: `docs/CONTRACTS.md`
("Member-decided asset authorization"); decisions:
`docs/PHASE_7_MIGRATION.md` (same heading).

## Owner decisions in force

Listed with their dates in `docs/TASKS.md`. The two recorded today: the rule
above, and that the shared platform runs on an internal-network shared
workstation, reachable from company computers, signed in to by several people,
and still unable to use company LDAP.

## Completed

- `src/common/authorization.py`: `DeviceAssetSelection` (one member's decision
  about one asset on one device, naming no permission and no policy reference)
  and `DeviceAuthorization` (the decisions in force for one device at one
  moment, with `for_actor`, `installable`, `tools` and `allows`).
- `src/control_plane/authorization.py`: `InMemoryAuthorizationRegistry` with
  `select`, `revoke`, `authorization` and `grants`, refusing a decision the
  member may not make, and `grant_from(spec, selection)` deriving a grant from
  the capability's own declaration.
- `control_plane.enrollment.advertisement` and
  `control_plane.distribution.get`, the two accessors the registry needed.
- `host_runtime.host`: `authorization.json` in the layout, `load_authorization`,
  and `build_gateway` installing only the chosen Workflows and Skills and
  deriving grants from the chosen tools against the installed
  `CapabilitySpec`. `grants.json` still works; both at once is refused.
- `tests/test_member_authorization.py` (7) and 4 more in
  `tests/test_host_wiring.py`, as listed at the end of the slice 2g
  requirements section.
- The Windows preview README documents `authorization.json`.

## In Progress

- PR #58 open for review. Nothing else uncommitted.

## Remaining

- Slice 2h, authenticated shared-platform transports: Registry package
  synchronization, delivering an authorization to a device, Bridge job polling
  and snapshot reporting. Still blocked on the authentication design: what a
  Bridge presents to the shared platform, what the control plane checks and
  stores, and how an authorization reaches a device and stays current. Slice
  2b (authenticated enrollment) is blocked on the same design.
- Then migration steps 3 to 6 in `docs/TASKS.md` (workflow 7, workflow 13,
  knowledge, controlled cutover).

## Architecture decisions made

- A selection names an asset and nothing else; the capability's own
  specification stays the only place that says what a tool may do.
- The three lists are enforced in different places: Workflows and Skills
  decide what a device installs, tools decide what its policy grants.
- Each plane derives the grant from the declaration it holds, rather than
  sharing a derivation across the boundary the architecture keeps apart.
- A bundle carries only the decisions in force.

## Exact verification commands and results

Windows, Python 3.12.14, repository root, with the `office` extra installed:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 764 passed, 3 skipped (link privileges)
.venv/Scripts/python.exe -m ruff check .
# PASS
.venv/Scripts/python.exe -m ruff format --check .
# PASS
.venv/Scripts/python.exe -m mypy
# PASS
.venv/Scripts/python.exe -m pip check
# PASS
.venv/Scripts/python.exe -m build
# PASS: sdist and wheel
git diff --check
# PASS
```

No socket, Telegram call, model, gateway, network, real vault, job or n8n
instance was invoked.

## Known issues / limitations

- On a company workstation the single member approves their own irreversible
  tools, because nobody else is bound to that device. The record names the
  approver and the time. Whether such a tool should need a second approver is
  an open question for the owner.
- Nothing delivers an authorization to a device yet. The control plane can
  issue one and a host can read one from its workspace; the transport between
  them is slice 2h, so today an operator copies the file.
- A tool a member chose that is not installed on the device grants nothing,
  silently. `doctor` does not yet report the difference between what was
  chosen and what is installed.
- The registry is in memory. It is the reference model for the shared
  platform's rules, not a database.

## Next Recommended Action

Merge PR #58 on green CI and flip its row in `docs/TASKS.md` to `done`. Then
put the remaining authentication design to the owner: it is the only thing
blocking slices 2b and 2h, and every later slice depends on them.
