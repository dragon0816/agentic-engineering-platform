# Handoff — Phase 7 slice 2j, one member per machine, and who asked

Updated: 2026-09-23 (Asia/Taipei).
Branch: `phase-7/virtual-member`, ahead of `main` by this slice's commit.

Progress across every phase is in `docs/TASKS.md`. This file is only where
the current work stopped and how to resume it, and is rewritten each time.

## Goal

Implement the owner's rule of 2026-09-23: every machine is bound to exactly one
platform member. A shared test workstation gets a virtual member of its own —
it is wired to particular instruments and laid out as a test environment, so it
belongs to that rig rather than to a desk — and no real employee binds to it.
The employees who need it drive it through the Telegram ingress, and the record
says which of them asked.

Requirements: the "Slice 2j" section of `docs/phases/PHASE_7_MIGRATION.md`.
Contracts: `docs/CONTRACTS.md`, under "Resident local Agent and durable local
state", "Member-decided asset authorization" and "Bridge access tokens".
Owner decisions with their dates: `docs/TASKS.md`.

## What this slice changed

- `common.local_agent.BridgeMembership` refuses a second active binding on any
  device kind, not only a company workstation, and answers `member()` — who
  this machine runs as.
- `control_plane.enrollment.InMemoryEnrollmentRegistry.bind` refuses a second
  active binding with `device_single_user`, which replaces the company-only
  code.
- `LocalAgentRequest.on_behalf_of` and `LocalRunSummary.on_behalf_of` record
  who asked when that is not who runs. They are recorded and never consulted:
  admission, grants and entitlement all read the acting member. `state.py`
  fixes both for the life of a run record (`run_owner_fixed`).
- `host_runtime.agent.LocalAgent.admit` refuses delegation outright on a
  company workstation (`delegation_not_allowed`).
- `channels.telegram` runs a mapped sender's request as the machine's member,
  naming the sender in `on_behalf_of` when they are not that member.
- `control_plane.authorization` checks an approver against the platform's
  active members rather than the device's. One member per machine would
  otherwise leave `approved_by` able to name only the member giving the
  approval, which is no approval at all.

## Verification

Run on Windows in `.venv` (Python 3.12) at the head of this branch:

- `python -m pytest -q -p no:cacheprovider` — **788 passed, 3 skipped**. The
  skips need symbolic-link privileges and run on Linux CI.
- `ruff check .` — clean. `ruff format --check .` — 160 files formatted.
- `mypy` — no issues in 125 source files.
- `pip check` — no broken requirements. `python -m build` — both artifacts
  built. `git diff --check` — clean.

## Where this stopped

The work is complete and verified locally. Not yet done:

1. Open the pull request from `phase-7/virtual-member` into `main`.
2. Run `/code-review` on it and apply the findings, as every earlier slice did.
3. Watch CI, then merge, and set the `2j` row in `docs/TASKS.md` to `done`
   with its pull request number.

## Next after this slice

Slice 2i, authenticated shared-platform transports, which this slice unblocks:
Registry package synchronization, authorization delivery, capability
advertisement, a read-only connectivity probe, Bridge job polling and snapshot
reporting, over a transport that presents a Bridge access token. The invariant
carried from the source: unreachable is never treated as revoked. After that,
migration steps 3 to 6 in `docs/TASKS.md`.

## Open item for the owner

The pinned `telegram-local-agent` source's `config.yaml` commits a Telegram bot
token and a GitLab personal access token. Neither was copied into this
repository. Revoking them is an action in that repository, not this one.
