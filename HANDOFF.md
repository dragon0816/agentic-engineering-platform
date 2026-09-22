# Handoff — Phase 7 slice 2b, Bridge access tokens

Updated: 2026-09-23 (Asia/Taipei).
Branch: `phase-7/bridge-access-tokens`, based on `main` after PR #61 merged.

Progress across every phase is in `docs/TASKS.md`. This file is only where
the current work stopped and how to resume it, and is rewritten each time.

## Goal

Implement the owner's rule of 2026-09-23: binding a user to a machine issues
an access token for that pair, kept on the Bridge, and a Bridge presents one
to authenticate with the shared platform. Requirements: the "Slice 2b"
section of `docs/phases/PHASE_7_MIGRATION.md`; contracts: `docs/CONTRACTS.md`
("Bridge access tokens"); source characterization and decisions:
`docs/PHASE_7_MIGRATION.md` (same heading).

## Owner decisions in force

Listed with their dates in `docs/TASKS.md`. The four that settle who may do
what: a member decides what their own devices may run; a Bridge is bound to a
user and that user's authentication decides what they may use; group
membership comes from the invitation; and binding issues a per-member,
per-machine access token. With this one, nothing about identity or
authorization is still open.

## Completed

- Source inspected read-only at `896046e8` (`.scratch/rs-source`, ignored by
  Git). The behaviour table and the PRESERVE/ADAPT/REFUSE decisions are in
  `docs/PHASE_7_MIGRATION.md`.
- `common.identity.BridgeAccessGrant` (the platform's record: member, device,
  fingerprint, issue and expiry, status) and `IssuedAccessToken` (the one
  moment the secret exists outside the Bridge, deliberately not a `Contract`,
  with a redacting `repr` and no attribute to put a secret in).
- `control_plane.identity.InMemoryAccessTokens`: `issue` for an admitted
  member only, one active token per pair, a generated secret and a minimum
  length for a supplied one; `authenticate` verifying the secret before the
  state, with an unknown token and a wrong secret giving one answer;
  `grants_for`, `revoke`, `revoke_for`.
- `InMemoryEnrollmentRegistry.unbind`, so a binding can be withdrawn and the
  tokens it justified revoked with it.
- `tests/test_access_tokens.py`, 9 tests, as listed at the end of the slice
  2b requirements section, including the whole chain: a secret becomes an
  identity, an identity decides entitlement, entitlement allows a decision.

## In Progress

- PR #62 open for review. Nothing else uncommitted.

## Remaining

- Slice 2i, the transports, is now unblocked and is the next thing to build:
  Registry package synchronization, delivering an authorization to a device,
  capability advertisement, a read-only connectivity probe, Bridge job polling
  and snapshot reporting, over a transport that presents an access token. Two
  invariants come from the source: unreachable is never treated as revoked,
  and re-binding needs a person at that keyboard.
- Wiring the token into the host: the Bridge holds the secret through a
  `SecretRef` and the host's `CredentialResolver`, as the Telegram token does,
  and `host.json` carries the non-secret `token_id`. That belongs with the
  transport, since nothing presents a token until there is somewhere to
  present it.
- Then migration steps 3 to 6 in `docs/TASKS.md` (workflow 7, workflow 13,
  knowledge, controlled cutover).

## Architecture decisions made

- The platform keeps a fingerprint and never a secret, so its own store is
  not worth stealing.
- The secret is verified before anything is said about the token's state: an
  unknown token and a wrong secret are one answer.
- A plain SHA-256 is used because the secret is 32 random bytes rather than a
  password, which is also why a short supplied secret is refused.
- One token per member and machine, not one per machine: that is what makes
  several members on one machine distinguishable and separately revocable.

## Exact verification commands and results

Windows, Python 3.12.14, repository root, with the `office` extra installed:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 783 passed, 3 skipped (link privileges)
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

No socket, model, gateway, network, real vault, job or n8n instance was
invoked, and no token was written to any file.

## Known issues / limitations

- **The shared workstation.** Tokens live on the Bridge, and a shared test
  workstation's members share one Windows account with no OS-level isolation,
  so one member can read another's token and act as them. One token per
  member and machine makes their requests distinguishable and separately
  revocable, which a single shared token never could, but not unforgeable
  between people who already share that account. Narrowing it needs
  per-member Windows accounts or a proof that cannot be replayed from a file.
  This is the owner's to decide before a shared device gets a transport.
- Nothing presents a token yet: there is no transport, and the host does not
  hold one.
- The registries are in memory. They are the reference model for the shared
  platform's rules, not a database.
- Issuing is a trusted host call. What a person types to prove who they are
  before the platform issues them a token, the source's ops username and
  password, is the entry point's business and is not modelled here.

## Next Recommended Action

Merge PR #62 on green CI and flip its row in `docs/TASKS.md` to `done`. Then
write the slice 2i requirements: the transport that presents these tokens,
starting with the read-only connectivity probe and the authorization delivery,
since those are the two a company host needs before anything else.
