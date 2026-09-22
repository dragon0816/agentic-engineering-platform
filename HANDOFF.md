# Handoff — Phase 7 slice 2h, identity-derived entitlement

Updated: 2026-09-22 (Asia/Taipei).
Branch: `main`, after PR #60 (slice 2h) merged with its review applied.

Progress across every phase is in `docs/TASKS.md`. This file is only where
the current work stopped and how to resume it, and is rewritten each time.

## Goal

Implement the owner's rule of 2026-09-22: a Bridge is bound to a user, and the
user's authentication decides which Workflows and Skills they may use.
Requirements: the "Slice 2h" section of `docs/phases/PHASE_7_MIGRATION.md`;
contracts: `docs/CONTRACTS.md` ("Identity-derived entitlement"); decisions:
`docs/PHASE_7_MIGRATION.md` (same heading).

## Owner decisions in force

Listed with their dates in `docs/TASKS.md`. The three that shape this part of
the phase: a member decides what their own devices may run; a Bridge is bound
to a user and that user's authentication decides what they may use; and the
shared platform runs on an internal-network shared workstation.

## Completed

- `Invitation.groups` and `PlatformUser.groups`, carried through `accept`,
  with `InMemoryEnrollmentRegistry.user` to read them back. Both default to
  none, so every record written before this slice stays valid.
- `src/common/identity.py`: `AuthenticatedActor` (actor, method,
  authenticated_at, expires_at, `valid_at`; no credential and no group) and
  `entitled(metadata, actor, groups)`.
- `InMemoryAuthorizationRegistry.select` and `revoke` take an
  `AuthenticatedActor` and refuse `session_expired`, `actor_mismatch` and
  `asset_not_entitled`; `available(identity)` lists what a member may use.
- `tests/test_member_authorization.py` grew to 15 tests, as listed at the end
  of the slice 2h requirements section.
- PR #60 review (4 findings) applied: `available` answered for an expired
  session, an uninvited stranger and a disabled member, and offered kinds a
  decision cannot name; and the `team` branch of `entitled` was unreachable,
  which is now said plainly instead of written twice.

## In Progress

- Nothing. `main` is the state to resume from.

## Remaining

- Slices 2b and 2i are blocked on one remaining owner decision: what a Bridge
  presents to the shared platform to prove it is acting for its bound user,
  and what the control plane checks and stores. Everything else about who may
  do what is now settled. `AuthenticatedActor` is where the answer lands,
  whatever the entry point does to decide.
- A second question the owner may want to answer with it: on a shared test
  workstation several members share one Windows account with no OS isolation,
  so a credential held there for one member is readable by the others. Either
  each request carries its own proof, or a shared device acts only as its
  registering owner. This needs deciding before a shared device gets a
  transport.
- Then migration steps 3 to 6 in `docs/TASKS.md` (workflow 7, workflow 13,
  knowledge, controlled cutover).

## Architecture decisions made

- Groups live on the platform's record of a user, not on the authentication:
  an authentication that carries its own group list is an authorization
  whoever issues it can widen.
- Entitlement is checked when a decision is made, not when a run happens, so
  a Bridge never depends on a control plane it is built to work without. The
  cost is staleness until an authorization is reissued.
- A member decides as themselves, with a session that is still valid.

## Exact verification commands and results

Windows, Python 3.12.14, repository root, with the `office` extra installed:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 774 passed, 3 skipped (link privileges)
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

- Nothing authenticates anybody yet. `AuthenticatedActor` is the shape of an
  entry point's answer; producing one is slice 2b.
- A member whose entitlement is withdrawn keeps their device's existing
  authorization until a new one is issued. Reissuing on a change belongs
  with delivery in slice 2i.
- Group membership changes only through a new invitation today: there is no
  way to add an existing user to a group.
- The registries are in memory. They are the reference model for the shared
  platform's rules, not a database.

## Next Recommended Action

Put the two questions under "Remaining" to the owner: what a Bridge presents
to prove it is acting for its bound user, and whose identity a shared test
workstation acts as when several members share one Windows account. They are
the last thing between this phase and the transports every later slice needs.
