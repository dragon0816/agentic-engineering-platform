# Handoff

Date: 2026-10-01 (Asia/Taipei)
Branch: `codex/personal-agent-conversations`
Base: `main` at `ac95c00eb3195e020c6cca62b1e475abb3a3e2ae`
PR: pending

## Goal

Complete Productization 4 slice 3: make the Personal Agent Web a durable local
conversation workspace while preserving the existing Agent/Gateway/Bridge
routing and authorization boundaries.

## Completed

- Productization 4 slices 1–2 merged in PR #179 as `ac95c00e`. The main
  verification succeeded and produced Windows preview artifact 11137482418.
- Added closed, secret-rejecting conversation contracts for creation, turns,
  messages and bounded records.
- Migrated the Bridge SQLite local-state schema from v2 to v3 with an additive
  conversations table; v1/v2 files migrate on writable open.
- Conversation ownership is fixed to the running host actor. Updates preserve
  the complete prior message prefix and monotonic timestamps.
- Added authenticated Web APIs to create, list/select and submit turns.
- Every turn passes the stable session id through the existing
  `LocalAgentRequest`, then records human-readable result status and trace.
- Updated Ask with a conversation selector, New action and restart-persistent
  history. Listing, selecting and refreshing cause no execution.
- Updated Productization 4 requirements, contracts, roadmap and task progress.

## In Progress

- Open, validate and merge the slice 3 PR.

## Remaining

1. Productization 4 slice 4: provider-neutral bounded tool loop with explicit
   maximum turns, installed-tool allowlist, Bridge policy on every call,
   progress/evidence and structured stop reasons.
2. Slice 5: standardized feedback and candidate Skill/Workflow generation with
   validation, review and publishing gates.
3. The deployed Gateway's model id must be entered by its operator; the URL
   alone does not identify the served model.

## Architecture decisions made

- Conversation history is local Bridge evidence, not shared-platform content.
- Transcript text grants no authority and does not alter actor, namespace,
  Bridge identity, model configuration or capability policy.
- The durable record is bounded to 100 messages; list projection is bounded to
  50 recent conversations.
- Slice 3 records and displays history but does not yet feed arbitrary prior
  transcript text to the routing model. Context use belongs to the bounded tool
  loop contract in slice 4.

## Verification

Supported target: Windows, Python 3.12 only. Browser automation was not run.

```text
Focused Web/local-state suite:
63 passed

python -m pytest --ignore=tests/test_browser.py -q
1457 passed, 4 skipped in 63.94s

python -m ruff check .
All checks passed!

python -m ruff format --check .
324 files already formatted

python -m mypy
Success: no issues found in 255 source files

python -m pip check
No broken requirements found.

python -m build --no-isolation --outdir <scratch>/build-conversations
Successfully built sdist and wheel.

git diff --check
PASS
```

## Known issues

- The current model path makes one route-selection request. Durable conversation
  history does not yet provide Hermes-style iterative tool use.
- Conversations have no delete/archive UI yet; retrieval and each record are
  bounded, but records remain in local state.
- Bridge Extension activation remains behind the existing device-admin/policy
  gate and outside Personal Agent Web.

## Next Recommended Action

Merge slice 3 after exact-head CI, then define the slice 4 tool-loop contract
from existing `ModelRequest.tools`, installed capability contracts and Bridge
policy. Do not encode workflow steps or permissions in the model prompt.
