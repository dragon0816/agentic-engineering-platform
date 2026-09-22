# Handoff — Phase 7 slice 2e, Telegram ingress

Updated: 2026-09-22 (Asia/Taipei).
Branch: `main`, after PR #54 (slice 2e) merged with its review applied.

Progress across every phase is in `docs/TASKS.md`. This file is only where
the current work stopped and how to resume it, and is rewritten each time.

## Goal

Telegram as an ingress to the resident local Agent, adapted from the pinned
`telegram-local-agent` channel: outbound polling, a numeric sender mapped to
exactly one platform actor, slash commands reaching the deterministic router,
the token through `SecretRef`. Requirements: the "Slice 2e" section of
`docs/phases/PHASE_7_MIGRATION.md`; contracts: `docs/CONTRACTS.md` ("Telegram
ingress"); source characterization and decisions: `docs/PHASE_7_MIGRATION.md`
("Telegram ingress").

## Owner decisions in force

Listed with their dates in `docs/TASKS.md`. The ones that shape this slice:
the local-first deployment decision, member-scoped remote control, and that a
Telegram adapter may deliver commands to the resident Agent only after mapping
the sender to a platform actor (Architecture, "Team Platform Plane").

## Completed

- Source inspected read-only at `4b40a215909e4fdd4b65519d70669a84e9abd43d`
  (`.scratch/telegram-source`, ignored by Git); the behaviour table and the
  ADAPT/REFUSE decisions are in `docs/PHASE_7_MIGRATION.md`.
- `src/channels/telegram.py`: `TelegramIngressConfig`, `TelegramSender`,
  `TelegramDelivery`, `TelegramPollResult`, `TelegramIngress` (`poll_once`,
  `run`), `command_to_message`, `chunks`. No Telegram library; the wire is
  `models.wire.Transport` with the standard-library default.
- `common.assets`: the Telegram bot token shape added to `SECRET_PATTERN`
  and `bot_token` to `SECRET_KEYS`, so the registry, the evidence grader,
  the trace, the model adapters and this adapter all refuse or redact it.
- `models.wire`: `transport_failure` and `status_failure` take a code
  `prefix`, and `redacted` redacts before it trims.
- `tests/test_telegram_ingress.py`, 13 tests, as listed at the end of the
  slice 2e requirements section. The slice 2d row flipped to `done` in
  `docs/TASKS.md`.
- PR #54 review (10 findings) applied. The serious ones: an exception in
  handling killed the poll loop and lost the update; the loop re-polled a
  revoked token forever; the shared error redaction trimmed before it
  redacted; an unmapped sender was answered, so a stranger could drive
  unbounded outbound calls; `/status` read the store on the event loop.

## In Progress

- Nothing. `main` is the state to resume from.

## Remaining

- Slice 2f, authenticated shared-platform transports: Registry package
  synchronization, Bridge job polling and snapshot reporting, and loading an
  installed package's manifest into the engine so the durable inventory and
  the engine's registry become one record. Needs an authentication design
  (what a Bridge presents, what the control plane checks) before any code;
  that design is an owner decision.
- Wiring the Windows preview CLI (`aep-host`) to the resident Agent and the
  Telegram ingress, so a company computer can run them; a durable poll
  offset beside the durable local state.
- Then migration steps 5 to 9 as listed in `docs/TASKS.md`.

## Architecture decisions made

- The adapter adds no authority: mapping decides which actor a sender is;
  the Agent's membership rule and the Gateway decide everything after.
- An empty sender map admits nobody, inverting the source's default.
- The token is resolved per call and held nowhere; its shape is credential
  material everywhere in the repository.
- A slash command is translated to the platform's `skill.command` form rather
  than to a hard-coded table of skills.

## Exact verification commands and results

Windows, Python 3.12.14, repository root, with the `office` extra installed:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 738 passed, 3 skipped (link privileges)
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

- The poll offset lives in memory. A batch handled just before a restart may
  be redelivered once; within a process a redelivered id is not handled
  again. A durable offset belongs with `SqliteLocalState`.
- Attachments are `unsupported_content`. The source stored them on disk and
  attached them to the next command; that needs its own storage rule.
- `/status` reads the Agent's snapshot at the wall clock; the Agent's own
  `clock` is not used there because the snapshot contract requires a real
  observation time.
- The source repository's `config.yaml` commits a Telegram bot token (marked
  expired there) and a GitLab personal access token. They were not copied.
  The owner was told; revoking and removing them is the owner's action in
  that repository.

## Next Recommended Action

Put the slice 2f authentication design to the owner before writing its
requirements: what a Bridge presents to the shared platform (a device
credential issued at enrollment, or a per-request signature), what the
control plane checks and stores, how membership is delivered to the Bridge
and kept current, and where the shared platform runs. Until then, work is
what the owner asks for plus the open items in `docs/TASKS.md`.
