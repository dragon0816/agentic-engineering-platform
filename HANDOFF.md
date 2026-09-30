# Handoff

Date: 2026-09-30 (Asia/Taipei)
Branch: `codex/telegram-mechanism-guidance`
Base: `origin/main` merge commit `43d4b9a393ca11af8b59585685ee79fb27141a74`

## Goal

Continue the shared Validation/Coding Telegram loop after a trusted mechanism
blocker instead of stopping after `coding_agent_review_required`. Keep the
response deterministic and bounded: Telegram still cannot start Codex, execute
message text, mutate GitHub or grant access.

## Completed

- Reproduced the live gap with Issue #139. Hermes emitted
  `MODEL_ROUTING_NOT_CONFIGURED`; the Coding Bot persisted it and acknowledged
  it, but PR #137 intentionally had no diagnosis handler.
- Added the closed `MechanismGuidance` contract with schema
  `aep-agent-coordination-guidance/v1`.
- Added the first and only guidance mapping:
  `MODEL_ROUTING_NOT_CONFIGURED` -> `provision_profile_model_routing` ->
  `retry_same_validation_request`.
- Restricted guidance to unresolved `mechanism_blocked` records. A
  `mechanism_update` or `mechanism_resolved` record cannot request another retry.
- Added durable `guidance_event_ids` deduplication. Old PR #137 state remains
  valid because the new field defaults empty and old mechanism records default
  to `mechanism_blocked`.
- Confirmed the deployed worker state already retains
  `mechanism-blocked-139-43d4b9a-20260930T0645Z`, so updating the worker after
  merge will emit guidance without asking Hermes to resend the blocker.
- Documented the Coding and Validation Agent trust checks and the exact meaning
  of the model-routing guidance action in architecture, contracts and the remote
  loop runbook.
- Made outbound worker-state, acknowledgement and guidance payloads readable in
  Telegram with stable two-space JSON indentation while preserving the same
  machine-readable contracts and plain-text transport.
- Committed the slice as `854bf2f`, pushed it and opened PR #140:
  https://github.com/dragon0816/agentic-engineering-platform/pull/140

## In Progress

- PR #140 is open; Platform verification passed and owner review/merge remains.
- Issue #139 remains blocked until this slice is merged, the resident Local Codex
  worker is updated/restarted and Hermes implements the fixed guidance consumer.

## Remaining

1. Have the owner review and merge green PR #140.
2. Fast-forward the resident Local Codex worker checkout and restart the existing
   `AEP Local Codex Worker` Scheduled Task.
3. Confirm the shared group receives one guidance message for the retained #139
   event and no duplicate on later polls.
4. Hermes must accept guidance only from the configured Coding Bot in the exact
   group, match event/request/SHA, allowlist the action, persist the event id,
   provision only the credential-free model fixture from its fixed profile and
   retry the same validation request.
5. Hermes must report `mechanism_resolved` or a bounded `mechanism_update`; an
   implementation failure still goes through GitHub and `codex-fix`.

## Architecture decisions made

- Deterministic known-code guidance is the smallest reversible handler. The
  mechanism prose is never sent to Codex or a shell.
- The action is validation-environment setup, not production model
  configuration. It may use only the credential-free model fixture already
  declared by the allowlisted validation profile and its bounded loopback port
  policy.
- Unknown mechanism codes remain `coding_agent_review_required`.
- Guidance has `hop=1` and does not authorize a reply loop. Hermes reports a new
  `mechanism_update` or `mechanism_resolved` event with a new event id.
- A repository code change still requires a typed GitHub Issue. Human review
  remains the merge gate.

## Verification

Supported target: Windows, Python 3.12. Browser tests excluded per owner
instruction.

```text
python -m pytest tests/test_local_codex_telegram_control.py \
  tests/test_codex_remote_test_workflow.py \
  tests/test_local_developer_environment.py -q
38 passed

python -m pytest --ignore=tests/test_browser.py -q
1358 passed, 4 skipped

python -m ruff check .
All checks passed

python -m ruff format --check .
290 files already formatted

python -m mypy src tests
Success: no issues found in 226 source files

python -m build
Successfully built agentic_engineering_platform-0.1.0.tar.gz and
agentic_engineering_platform-0.1.0-py3-none-any.whl

python -m pip check
No broken requirements found

git diff --check
PASS
```

One earlier full-suite run hit the existing Windows loopback transport flake in
`tests/test_agent_web.py::test_every_api_call_needs_the_header` with WinError
10053. The test then passed three consecutive isolated runs, and the final full
suite passed as recorded above.

## Known issues

- Hermes currently replays historical Issue #120 payload
  `validation-36432983270` with the unchanged blocker `CI artifact unavailable`
  and emits repeated GitHub/Telegram messages. This is a Hermes poller
  idempotency defect: it must persist the blocker fingerprint, silently skip an
  unchanged blocked request and keep the global poller available for #139.
- Hermes does not yet consume `aep-agent-coordination-guidance/v1`; its local
  poller/skill must add this fixed schema and action before #139 can resume
  automatically.
- The live Coding Bot still runs merge commit `43d4b9a...`; do not restart it
  from this unmerged branch.
- Telegram delivery is best effort. Coding-side durable guidance ids plus
  Hermes-side event-id deduplication are both required across the rare boundary
  where a send succeeds but state persistence fails.
- The development `GH_TOKEN` lacks Issues write and Repository Variables read;
  the existing GitHub CLI keyring was used to create Issue #139. No token was
  printed or committed.

## Next Recommended Action

Review and merge green PR #140. Then update/restart the resident worker; it
should emit guidance for the already retained #139 blocker without another
Hermes message.
