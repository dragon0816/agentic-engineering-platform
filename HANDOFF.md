# Handoff

Date: 2026-09-30 (Asia/Taipei)
Branch: `codex/telegram-control-bot`
Base: `origin/main` merge commit `72a7c3d7c1638b5e9e704288fd8a286e8267af9d`

## Goal

Remove the owner's manual copy-and-paste step between the Validation Agent and
Coding Agent by letting their dedicated Telegram bots coordinate in one shared
group, without moving implementation queue authority, code execution or merge
authority out of GitHub. Hermes and Local Codex fill those roles today but are
replaceable.

## Completed

- Confirmed PR #135 merged with green Platform verification and based this slice
  on its merge commit.
- Added `development.telegram_control` with a closed non-secret configuration,
  strict owner/Validation Agent/chat identity binding and token resolution through
  `SecretRef` at Bot API call time.
- Added owner-only `/status` and `/status <issue-number>` reads. No Telegram
  command changes GitHub or starts Codex.
- Added role-neutral `aep-agent-coordination/v1` validation events, GitHub Issue
  read-back, terminal `aep-agent-coordination-ack/v1`, `hop` loop bounds, a 25-update poll
  bound, durable offset and a 200-event replay bound.
- Added bounded `MechanismProblem` events for validation/deployment/polling
  blockers that do not yet belong in a code Issue. The last 20 are retained for
  Coding Agent review, with deterministic continue/resume/review acknowledgements.
- Added best-effort `aep-telegram-worker-event/v1` notifications for Local Codex
  `running`, `waiting_evidence`, `failed` and `completed` states.
- Integrated Telegram into the existing Local Codex Worker process. Telegram
  configuration and transport failure cannot stop GitHub polling; there is no
  second Scheduled Task and no inbound port.
- Added all four Telegram settings to the explicit local YAML allowlist and
  removed the token and identity settings from every Codex subprocess.
- Documented the group protocol, trust boundary, configuration and Hermes loop
  rules. Added contract and regression tests.
- Verified the actual ignored `local.yaml` loads all configured GitHub and
  Telegram names without printing any value.
- Committed implementation as `c11fa34` and opened PR #137:
  https://github.com/dragon0816/agentic-engineering-platform/pull/137

## In Progress

- PR #137 is open with green Platform verification and awaiting review/merge.

## Remaining

1. Confirm PR #137 Platform verification is green and merge it.
2. Update the resident checkout at
   `C:\Users\OpenLab\.codex\worktrees\local-codex-worker\agentic-ai-team-platform`
   to the new `main`, refresh its Python 3.12 environment if required, and
   restart the existing `AEP Local Codex Worker` Scheduled Task once.
3. Confirm only one process polls the dedicated Local Codex bot; HTTP 409 means
   another process is using the same bot token.
4. Send `/status` in the configured group and confirm a reply within one worker
   interval (currently 60 seconds).
5. Have the Validation Agent post one implementation event only after it has written the corresponding
   evidence/result to GitHub. Confirm one terminal ack appears and a duplicate
   `event_id` produces no second ack.
6. Have it post one `mechanism_blocked` event without an Issue and confirm the
   Coding Bot retains it and replies `coding_agent_review_required`.
7. Run one controlled failure loop and confirm Coding worker state changes
   appear in the group while GitHub remains the durable record.

## Architecture decisions made

- Validation and coding are roles. Hermes is the current Validation Agent and
  Local Codex the current Coding Agent; either implementation may later change.
- The Telegram group is an immediate coordination layer. GitHub Issue comments,
  labels and exact-SHA payloads remain the persistent control plane for code work.
- This is separate from the existing Personal Agent Telegram ingress. It cannot
  route natural-language work, invoke a capability, mutate a repository or merge.
- Bot-to-bot messages use fixed JSON rather than free-form conversation. The
  Coding bot accepts only the configured Validation bot with `is_bot=true` in
  the exact configured chat. The owner and Hermes bot IDs are distinct.
- Hermes event `hop=0` receives at most one terminal ack with `hop=1`. Hermes
  must ignore acknowledgements and Local Codex worker events, preventing loops.
- An absent four-value Telegram configuration disables the optional channel. A
  partial/invalid configuration logs only the error type and leaves the GitHub
  worker running.
- No new architecture component is needed on GitHub and no API-billed OpenAI
  action is reintroduced.
- PR #137 persists and acknowledges mechanism blockers but does not feed their
  prose to Codex. A later bounded diagnosis handler may automate that review.

## Verification

Supported target: Windows, Python 3.12. Browser tests excluded per owner
instruction.

```text
python -m pytest tests/test_local_codex_telegram_control.py \
  tests/test_local_developer_environment.py \
  tests/test_codex_remote_test_workflow.py -q
34 passed

python -m pytest --ignore=tests/test_browser.py -q
1354 passed, 4 skipped

python -m ruff check .
All checks passed

python -m ruff format --check .
290 files already formatted

python -m mypy src tests
Success: no issues found in 226 source files

python -m build
Successfully built agentic_engineering_platform-0.1.0.tar.gz and
agentic_engineering_platform-0.1.0-py3-none-any.whl

GitHub Actions Platform verification run 36660449473
PASS: pytest, Ruff check/format, mypy, build, pip check, Windows offline
preview build/install and artifact upload

scripts/import-local-env.ps1 against the actual ignored local.yaml
Loaded names: GH_TOKEN, AEP_GITHUB_TOKEN, TELEGRAM_BOT_TOKEN,
TELEGRAM_HERMES_BOT_ID, TELEGRAM_CONTROL_CHAT_ID,
TELEGRAM_OWNER_USER_ID; no values printed
```

## Known issues

- The resident Local Codex Worker still runs the pre-#137 checkout until this PR
  merges and that checkout is updated/restarted. Restarting it before updating
  would make the older loader reject the new Telegram YAML fields.
- Bot API connectivity, group visibility and bot-to-bot delivery require one
  live post-merge Telegram check. Unit tests use an injected transport and make
  no network or messaging side effects.
- Telegram worker-state messages are best effort. A missed Telegram message does
  not lose work because GitHub remains authoritative.

## Next Recommended Action

Review and merge PR #137. Then update/restart the one resident Local Codex Worker
and run the two-message group smoke test:
owner `/status`, followed by one Validation Agent implementation event whose
GitHub evidence already exists and one Issue-free `mechanism_blocked` event.
