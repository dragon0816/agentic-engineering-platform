# Handoff

Date: 2026-10-01 (Asia/Taipei)
Branch: `codex/personal-agent-tool-loop`
Base: `main` at `1f26f2e9f4b6b0bc7eedc0fbba60800420017d21`
PR: pending

## Goal

Complete Productization 4 slice 4: make Personal Agent Web natural-language
turns capable of bounded, policy-enforced tool use through the existing
Agent/Gateway/Workflow/Bridge boundaries.

## Completed

- Added approved provider rendering for `platform.command-arguments.v1` and
  OpenAI-compatible tool-call request, response and replay support.
- Added a bounded Gateway conversation loop: five model turns, four tool calls,
  twelve recent messages, 4,000 characters per message and 16,000 characters
  per tool observation.
- Projected tools only from commands in installed Skill manifests. Stable
  `<skill alias>__<command>` names resolve back to one exact manifest target.
- Unknown or invented tools never execute. Multiple simultaneous calls and
  repeated calls stop with typed reasons.
- Every accepted capability call uses `BridgeExecutor`; every Workflow call
  uses `WorkflowEngine`; Local Agent admission and durable Workflow run records
  remain in effect.
- Preserved deterministic command bypass: known dot commands do not ask the
  model to choose a route.
- Personal Agent Web conversation turns now use the bounded tool loop for
  ordinary language and retain final answer, trace and complete execution
  evidence through the existing local conversation API.
- Documented the fixed normal company Gateway URL
  `http://127.0.0.1:4000/v1`; the served model id remains explicit setup.

## In Progress

- Open, validate and merge the slice 4 PR.

## Remaining

1. Productization 4 slice 5: standardized improvement feedback and candidate
   Skill/Workflow creation with validation, review and publishing gates.
2. Ollama tool-call wire support and streaming tool-call deltas remain outside
   this OpenAI-compatible first path.
3. The deployed Gateway's model id must be entered by its operator; the URL
   alone does not identify the served model.

## Architecture decisions made

- Tool visibility comes from installed Skill manifests, never shared catalog
  publication or free-form prompt content.
- Provider tool schemas transport arguments only. Installed capability and
  Workflow contracts remain authoritative for validation.
- A model-selected target grants no authority. Bridge policy runs on every
  capability dispatch, including every step of a selected Workflow.
- Conversation transcript and observations are bounded and cannot carry
  identity, authorization or configuration changes.
- This first loop executes one call at a time to keep ordering deterministic.

## Verification

Supported target: Windows, Python 3.12 only. Browser automation was not run.

```text
python -m pytest --ignore=tests/test_browser.py -q
1461 passed, 4 skipped in 63.80s

python -m ruff check .
All checks passed!

python -m ruff format --check .
324 files already formatted

python -m mypy
Success: no issues found in 255 source files

python -m pip check
No broken requirements found.

python -m build --no-isolation --outdir <scratch>/build-tool-loop
Successfully built sdist and wheel.

git diff --check
PASS
```

## Known issues

- Tool calling is implemented for the configured OpenAI-compatible company
  Gateway. Ollama still returns the existing typed `tools_not_supported`.
- Tool progress is returned as structured API evidence after the synchronous
  turn; incremental browser streaming is not included.
- The provider schema accepts a JSON object because current Skill commands name
  symbolic contracts rather than carrying JSON Schema. The real target still
  performs closed validation and may refuse model-supplied fields.

## Next Recommended Action

Merge slice 4 after exact-head CI, then implement Productization 4 slice 5 as a
separate review: conversation feedback becomes a standardized, reproducible
improvement request or an unpublished candidate asset. It must not modify or
publish a production capability directly.
