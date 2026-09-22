# Handoff — Phase 7 slice 2f, company host runtime

Updated: 2026-09-22 (Asia/Taipei).
Branch: `main`, after PR #56 (slice 2f) merged with its review applied.

Progress across every phase is in `docs/TASKS.md`. This file is only where
the current work stopped and how to resume it, and is rewritten each time.

## Goal

Make the two pieces built in slices 2d and 2e usable on a real company
computer: assemble the resident Agent from files in the host's workspace and
drive it from `aep-host`, and keep the Telegram poll offset in the Bridge's
durable state instead of in memory. Requirements: the "Slice 2f" section of
`docs/phases/PHASE_7_MIGRATION.md`; contracts: `docs/CONTRACTS.md` ("Company
host runtime"); decisions: `docs/PHASE_7_MIGRATION.md` (same heading).

## Owner decisions in force

Listed with their dates in `docs/TASKS.md`. The ones that shape this slice:
the local-first deployment decision (installed assets, run state and
credentials stay on the Bridge computer) and member-scoped remote control.

## Completed

- `src/host_runtime/host.py`: `HostLayout` (every file a host reads, under
  one workspace), `build_runtime` returning a `HostRuntime` (Agent, durable
  state, optional Telegram ingress), `build_gateway` (skills and workflows
  from the assets directory, the one shipped capability handler rooted at the
  workspace, grants from the grants file, deterministic routing only),
  `load_membership`, `inspect_runtime` and `host_report`. Every failure is a
  `HostError` with a closed code and the path at fault, never its contents.
- `aep-host` gains `ask`, `status` and `telegram`; `doctor` now reports
  `membership`, `assets` and `state` beside the device checks and prints
  `resident agent: ready|pending`. Reporting writes nothing.
- `CompanyHostConfiguration` gains `namespace` (no default; the platform does
  not guess) and `credentials` (`CredentialBinding`: a secret's name and the
  environment variable holding its value). `workspace_root` accepts an
  absolute path of the running platform as well as a Windows one, so the
  wiring is exercised on Linux CI too.
- `SqliteLocalState` gains a `channel_cursor` table with `cursor` and
  `advance_cursor` (no rewind), schema version 2 migrated from 1.
  `TelegramIngress.offset()` reads it, so a restart resumes where the last
  confirmed batch ended.
- `deploy/windows-preview`: the installer creates the asset directories,
  accepts `-Namespace`, and tells the operator the Agent is pending until
  membership exists. The README documents the workspace layout, the
  membership record, `ask`/`status`, grants and the Telegram setup.
- CI's Windows preview step now writes a membership record, asserts `doctor`
  moves from `pending` to `ready`, and runs `ask` and `status` on a real
  Windows machine.
- `tests/test_host_wiring.py`, 13 tests, and 2 more in
  `tests/test_telegram_ingress.py`, as listed at the end of the slice 2f
  requirements section.
- PR #56 review (5 findings) applied. The serious ones: `doctor` created
  tables and migrated the schema version of the file it was only meant to
  report on, so `SqliteLocalState` gained a read-only mode; a corrupt file
  escaped as a SQLite exception because the opening `PRAGMA` runs outside
  the write transaction; and the new checks were allowed to change the
  device preflight `status`, which would abort a reinstall over a stale
  membership record.

## In Progress

- Nothing. `main` is the state to resume from.

## Remaining

- Slice 2g, authenticated shared-platform transports: Registry package
  synchronization, Bridge job polling and snapshot reporting, and loading an
  installed package's manifest into the engine so the durable inventory and
  the engine's registry become one record. Blocked on the owner's
  authentication design: what a Bridge presents, what the control plane
  checks and stores, how membership reaches the Bridge and is kept current,
  and where the shared platform runs.
- Then migration steps 5 to 9 in `docs/TASKS.md` (workflow 7, workflow 13,
  knowledge, live model smoke checks, controlled cutover).

## Architecture decisions made

- The host layout is convention under one configured workspace, and the
  layout itself is a contract so `doctor` can show it.
- The host installs exactly one capability handler, the one the package
  ships. A manifest naming another capability installs but fails closed.
- A company host configures no model; routing there is deterministic only.
- `doctor` distinguishes `pending` from `failed`, so a freshly installed host
  is not reported as broken.

## Exact verification commands and results

Windows, Python 3.12.14, repository root, with the `office` extra installed:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 753 passed, 3 skipped (link privileges)
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
instance was invoked. The state files and workspaces live under pytest's
temporary directory.

## Known issues / limitations

- Membership is a file the operator writes. How it is delivered from the
  control plane and kept current is slice 2g.
- The engine's `InstalledWorkflows`, not the durable inventory, decides what
  may run. Packages obtained from the Registry and manifests loaded into the
  engine are still two records; joining them is slice 2g.
- The engine is built without a `RunJournal`, so a run interrupted by a
  restart is not recoverable on a company host yet. The checkpoint store
  exists (Phase 3); wiring it to the host is a later slice.
- `aep-host telegram` runs in the foreground until interrupted. There is no
  service, autostart or supervision, deliberately: the pinned source's
  autostart was declined in slice 2a.
- A host with no namespace must be told one per request. The installer
  records one only when `-Namespace` is passed.

## Next Recommended Action

Put the slice 2g authentication design to the owner before writing its
requirements: what a Bridge presents to the shared platform, what the control
plane checks and stores, how membership reaches the Bridge and is kept
current, and where the shared platform runs. Until then, work is what the
owner asks for plus the open items in `docs/TASKS.md`.
