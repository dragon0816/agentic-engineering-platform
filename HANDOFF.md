# Handoff — Phase 7 slice 2d, resident local Agent and durable local state

Updated: 2026-09-22 (Asia/Taipei).
Branch: `phase-7/local-agent`, based on `main` after PR #52 merged.

Progress across every phase is in `docs/TASKS.md`. This file is only where
the current work stopped and how to resume it, and is rewritten each time.

## Goal

Migration step 4 of `docs/phases/PHASE_7_MIGRATION.md` names a local Agent
interface, Registry synchronization and authenticated Bridge polling. This
slice is the first of those: the resident Agent on the Bridge computer and the
durable local state it owns, with no network at all. Requirements: the
"Slice 2d" section of the phase specification; contracts: `docs/CONTRACTS.md`
("Resident local Agent and durable local state"); decisions:
`docs/PHASE_7_MIGRATION.md` (same heading).

## Owner decisions in force

Listed with their dates in `docs/TASKS.md`. The ones that shape this slice: the
local-first deployment decision (installed assets, run state and credentials
stay on the Bridge computer), and that a company workstation is operated only
by its one bound owner while a shared test workstation is operated by its
bound platform users.

## Completed

- `src/common/local_agent.py`: `BridgeMembership` (the device's own copy of
  who may use it, with the company-owner rule in its validator) and
  `LocalAgentRequest` (one request from `local`, `shared_platform` or
  `telegram` ingress, closed, no credential material).
- `common.enrollment.admit_device`: the device half of admission, one function
  called by the control plane's remote-job reference and by the Agent.
- `src/host_runtime/agent.py`: `LocalAgent.admit`, `handle` (through the
  existing `Gateway`, ingress as channel) and `execute` (a `RemoteWorkflowJob`'s
  exact workflow through `Gateway.execute_workflow`, job id as idempotency
  key); runs recorded only when the engine started them; a timed-out run
  settled in the background (`settled()` waits); a record that cannot be
  written reported as `unrecorded` on the outcome. `LocalAgentOutcome`'s
  contract refuses a refusal that also reports a result, a run record that
  names another workflow, and `run` beside `unrecorded`.
- `src/host_runtime/state.py`: `SqliteLocalState`, single-writer, one committed
  transaction per write, reads under the same lock, `commit_unknown` kept
  apart from `unavailable`, file bound to one Bridge identifier, whole-plan
  install refusal, run ownership fixed and updates never backwards, UTC
  timestamps, and `snapshot()` for the control plane to project.
- `common.distribution.verify_installation` and `LocalStateError`: the
  installation rule lifted out of `InMemoryLocalInventory`, which now applies
  it and maps its codes.
- `tests/evaluation_runner.py` exposes `GatewayRunner.gateway()` so a host test
  can drive the repository's real wiring directly.
- `tests/test_local_agent.py`, 14 tests, as listed at the end of the slice 2d
  requirements section.
- PR #53 review (10 findings) applied. The serious ones: reads ran outside the
  writer's lock; the engine's pre-flight rejections were recorded as runs;
  a timed-out run was recorded once and never settled; a redelivered job ran
  twice; a state error was raised over a workflow result that had happened;
  and the device admission rule existed twice with two vocabularies.
- The "2d local Agent and transports" row split into 2d, 2e and 2f in
  `docs/TASKS.md`.

## In Progress

- PR #53 open for review. Nothing else uncommitted.

## Remaining

- Slice 2e, Telegram ingress: clone the pinned `telegram-local-agent`
  (`4b40a215909e4fdd4b65519d70669a84e9abd43d`) read-only and characterize its
  channel before writing the adapter. Outbound polling over an injected
  transport, bot token through `SecretRef`, a numeric sender mapped to exactly
  one bound actor, fail closed when the map is empty or the sender unmapped,
  then `LocalAgentRequest(ingress="telegram")` into the same `LocalAgent`.
  First prove an unmapped sender and an unbound actor are both refused.
- Slice 2f, authenticated shared-platform transports: Registry package
  synchronization, Bridge job polling and snapshot reporting. Needs an
  authentication design (what a Bridge presents, what the control plane
  checks) before any code; that design is an owner decision.
- Then migration steps 5 to 9 as listed in `docs/TASKS.md`.

## Architecture decisions made

- The Bridge admits from its own membership copy, never by asking the control
  plane, so company work continues while the shared platform is unreachable.
- The ingress is the request's channel and nothing more; one admission rule
  and one Gateway for every ingress.
- The installation rule lives in `common.distribution` and is shared by the
  in-memory reference and the durable store.

## Exact verification commands and results

Windows, Python 3.12.14, repository root, with the `office` extra installed:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 725 passed, 3 skipped (link privileges)
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
invoked. The SQLite files live under pytest's temporary directory.

## Known issues / limitations

- `LocalAgent` keeps run summaries, not full run history; the engine's journal
  and checkpoint store remain where a run's steps live. The summary is what
  the control plane projects.
- The Agent has no local interface beyond the Python API. The Windows preview
  CLI (`aep-host`) does not yet expose it; wiring the CLI to the Agent belongs
  with the Telegram or transport slice, whichever lands first.
- `SqliteLocalState` refuses a second writer with `unavailable` rather than
  waiting, like the checkpoint store; a host runs one Agent per state file.
- The engine's `InstalledWorkflows`, not the durable inventory, answers for
  what may run on this Bridge. Packages obtained from the Registry and
  manifests loaded into the engine are two records today; a test shows a
  workflow running with an empty inventory. Joining them (loading an
  installed package's manifest into the engine) is slice 2f work.
- Membership on the Bridge is a contract the host supplies. How it is
  delivered from the control plane and kept current is part of slice 2f.

## Next Recommended Action

Merge PR #53 on green CI and flip its row in `docs/TASKS.md` to `done`. Then
start slice 2e by cloning the pinned Telegram source read-only and writing its
requirements section before any adapter code.
