# Handoff — Phase 7, next slice is 2i

Updated: 2026-09-23 (Asia/Taipei).
Branch: `main`, after PR #64 (slice 2j) merged with its review applied.

Progress across every phase is in `docs/TASKS.md`. This file is only where
the current work stopped and how to resume it, and is rewritten each time.

## Where this stopped

Slice 2j is merged and nothing is in flight. The repository is the state to
build on; no work is sitting on an unmerged branch.

## What slice 2j settled, because 2i builds on it

Every machine is bound to exactly one platform member, so a machine holds one
Bridge access token. A company workstation's member is the employee who
registered it. A shared test workstation is wired to particular instruments and
laid out as a test environment, so it belongs to that rig rather than to a
desk: it runs as a virtual member of its own, and no real employee binds to it.
Employees who need it drive it through the Telegram ingress; the run records
who asked in `on_behalf_of`, which is recorded and never consulted, because
admission, grants and entitlement all read the acting member.

Two consequences are documented rather than fixed, both following from owner
decisions, and both listed under "Open items carried forward" in
`docs/TASKS.md`:

1. The sender map in a Bridge's `telegram.json` is the access list for a shared
   machine. Disabling somebody on the shared platform does not close that door;
   removing their entry does. Slice 2i does not change this — moving the list
   into the authorization bundle would, and the owner decided against it.
2. An approval on a tool selection may still name the acting member. Whether an
   approval must come from a second person is an owner policy decision nobody
   has asked for.

## Next: slice 2i, authenticated shared-platform transports

Requirements: the "Slice 2i" section of `docs/phases/PHASE_7_MIGRATION.md`.
Scope: Registry package synchronization, authorization delivery, capability
advertisement, a read-only connectivity probe, Bridge job polling and snapshot
reporting, over a transport that presents a Bridge access token.

The invariant carried from the pinned source, recorded in
`docs/PHASE_7_MIGRATION.md`: **unreachable is never treated as revoked.** The
reference model already separates the two answers — `binding_withdrawn` against
everything else — and the transport must not collapse them.

After 2i, migration steps 3 to 6 in `docs/TASKS.md`: workflow 7 parity,
workflow 13 parity, knowledge parity, controlled cutover.

## How to verify

On Windows in `.venv` (Python 3.12), from the repository root:

```text
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe -m build
git diff --check
```

At this commit: 789 passed, 3 skipped, everything else clean. The three skips
need symbolic-link privileges and run on Linux CI. CI runs the same chain on
Windows and Ubuntu against Python 3.11 and 3.12.

## Open item for the owner

The pinned `telegram-local-agent` source's `config.yaml` commits a Telegram bot
token and a GitLab personal access token. Neither was copied into this
repository. Revoking them is an action in that repository, not this one.
