# Handoff — Phase 7 slice 2i, authenticated shared-platform transports

Updated: 2026-09-23 (Asia/Taipei).
Branch: `phase-7/platform-transport`, ahead of `main` by this slice's commit.

Progress across every phase is in `docs/TASKS.md`. This file is only where
the current work stopped and how to resume it, and is rewritten each time.

## Goal

The wire between a Bridge and the shared platform, which migration step 4
named and slices 2d and 2e left for last: Registry package synchronization,
authorization delivery, capability advertisement, a read-only connectivity
probe, Bridge job polling and snapshot reporting, over a transport that
presents the Bridge access token of slice 2b. The invariant carried from the
pinned Host Bridge: unreachable is never treated as revoked.

Requirements: the "Slice 2i" section of `docs/phases/PHASE_7_MIGRATION.md`.
Contracts: `docs/CONTRACTS.md`, "Shared-platform transport". Source
characterization and decisions: `docs/PHASE_7_MIGRATION.md`, same heading.

## What this slice added

- `src/common/sync.py` — the six-operation wire, closed contracts only.
- `src/control_plane/service.py` — `ControlPlaneService`, the platform's side,
  transport-agnostic, over the in-memory references.
- `src/control_plane/http.py` — `ControlPlaneServer`, that service on the
  standard library's `ThreadingHTTPServer`; `POST /v1/<op>` with
  `Authorization: Bearer <token_id>:<secret>`, `GET /v1/health` open.
- `src/host_runtime/sync.py` — `PlatformClient`, the Bridge's side, with the
  five-way classification of every answer and a sync that verifies everything
  before writing anything.
- `CompanyHostConfiguration.platform` (`PlatformBinding`), `aep-host
  probe|sync|jobs`, and a `platform` doctor check. `HostLayout` moved to
  `host_runtime.contracts` and is re-exported from `host_runtime.host`.
- `RemoteJobRecord` final states and `settle`; `RemoteWorkflowJob.on_behalf_of`;
  `InMemoryEnrollmentRegistry.advertise`.

## Verification

Run on Windows in `.venv` (Python 3.12) at the head of this branch:

- `python -m pytest -q -p no:cacheprovider` — **806 passed, 4 skipped**. Three
  skips need symbolic-link privileges and one needs an IPv6 loopback; all
  four run on Linux CI.
- `ruff check .` — clean. `ruff format --check .` — 165 files formatted.
- `mypy` — no issues in 131 source files.
- `pip check` — no broken requirements. `git diff --check` — clean.

## Where this stopped

The work is complete and verified locally. Not yet done:

1. Open the pull request from `phase-7/platform-transport` into `main`.
2. Run `/code-review` on it and apply the findings, as every earlier slice did.
3. Watch CI, then merge, and set the `2i` row in `docs/TASKS.md` to `done`
   with its pull request number.

## What is deliberately not here

- A durable platform store. The server serves the in-memory references and
  loses them on restart; an operator can run it from a Python script that
  builds the references, and a platform host with durable state is a later
  slice.
- A member sign-in. Invitation, registration, binding and token issue are
  trusted-host calls on the platform; nothing member-facing is on this wire.
- TLS termination as tested code. `ControlPlaneServer` takes an
  `ssl.SSLContext` and wraps its socket; that path is not exercised by the
  suite, because generating a certificate needs a tool the repository does
  not carry. The client refuses plain http beyond loopback.
- Job leases and concurrent job runs (the pinned source's heartbeat and pool).
  Deferred until the first workflow that needs them; the settle-or-re-offer
  rule with the job id as idempotency key is correct without them.

## Next

Migration step 5, workflow 7 parity (`docs/TASKS.md` row 3): the Jira team
tickets report against a test workbook, compared with the working old Host
Bridge. This needs capabilities the package does not yet ship (Jira, Excel)
and evidence from a real company Bridge; CI stays inert and never claims live
parity. Then workflow 13, knowledge parity, and controlled cutover.

## Open item for the owner

The pinned `telegram-local-agent` source's `config.yaml` commits a Telegram bot
token and a GitLab personal access token. Neither was copied into this
repository. Revoking them is an action in that repository, not this one.
