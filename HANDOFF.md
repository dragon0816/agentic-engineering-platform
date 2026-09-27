# Handoff — bounded Hermes validation lifecycle

Updated: 2026-09-27 (Asia/Taipei).
Branch: `feature/hermes-validation-lifecycle`.
Base: `origin/main` at `0659ea8d881d256240d1d0f32323032225730682`.
Pull request: #109, https://github.com/dragon0816/agentic-engineering-platform/pull/109.

## Goal

Complete the GitHub control-plane portion of the continuous Hermes validation
loop:

```text
Hermes validation request -> GitHub queue -> Hermes preflight/test
  -> remote failure -> Codex repair -> Draft PR -> Hermes retest
  -> human merge decision
```

Hermes is the execution/test worker. GitHub only emits authenticated,
versioned queue messages and records state. Codex may prepare a bounded Draft
PR; no workflow grants access, changes Bridge configuration, approves, or
merges code.

## Completed

- PR #105 established the narrow `codex-fix` Issue trigger and separated
  read-only Codex analysis from Issue-comment writes.
- PR #107 is merged at `0659ea8`. It adds restricted Draft PR delivery,
  `hermes-next-action/v1` handoffs, and `hermes-retest-passed` reviewer
  notification. A human still merges.
- The repository variable `HERMES_GITHUB_BOT_USER` is set to `dragon0816` and
  `HERMES_MERGE_REVIEWER` is set to `dragon0816` for the current setup.
- Added `validation.contracts` with serializable `ValidationRequest`,
  `ValidationTarget`, `ValidationExecution`, and `OwnerDecision` contracts.
  The request pins capability identity, 40-character source commit, build,
  test profile, Bridge/actor, declared prerequisites, acceptance criteria and
  bounded repair/retest counts.
- Added `.github/workflows/hermes-validation-lifecycle.yml`. It emits
  `hermes-validation/v1` payloads only when the expected bot/reviewer applies
  the exact lifecycle label. It has no checkout, no token secret, no code
  execution, and no merge operation.
- A `manual_review` outcome from the Codex failure workflow now always creates
  a trusted `owner_decision_required` Hermes payload and the
  `hermes-owner-decision-requested` label. This replaces the previous
  no-action comment that left Issue #108 idle.
- Added the `Hermes validation request` Issue template and lifecycle
  documentation. Updated the shared contract and progress records.

## In Progress

- PR #109 first CI run `36298521674` failed only because mypy rejected two
  negative-test expressions in `tests/test_validation_contracts.py`; the
  implementation was not reached. The tests now use Pydantic validation for
  the deliberately incomplete fixture, focused pytest/Ruff/mypy pass, and a
  replacement CI run is pending.

## Remaining

- The lifecycle labels have been created in GitHub:
  `hermes-validation-requested`, `hermes-preflight-requested`,
  `hermes-owner-decision-requested`, `hermes-owner-decision-approved`,
  `hermes-owner-decision-rejected`, `hermes-validation-passed`, and
  `hermes-validation-failed`.
- Update Hermes to poll only trusted JSON payload comments, persist payload
  ids, perform predefined preflight/test/retest actions, and never execute
  Issue/payload prose as a command. The exact pasteable prompt is supplied in
  the Codex final response for this slice.
- Hermes must apply `hermes-validation-requested` only after it creates a
  complete request manifest. On a preflight failure it must attach sanitized
  evidence and use the existing `codex-fix` repair path only when an
  implementation defect is supported.
- A reviewer must perform any real grant/routing/Knowledge configuration
  change before adding `hermes-owner-decision-approved`; the label merely
  queues another preflight.
- Execute one end-to-end dry validation request after merge. CI stays inert;
  live company resources stay on the enrolled Bridge.

## Architecture decisions made

- This is a GitHub control-plane adapter. It does not replace Registry,
  Bridge, Gateway, workflow execution, or authorization.
- Validation requests declare prerequisites. They never grant a listed asset,
  configure a model route, install Knowledge, or expose a secret.
- Issue text, test logs and JSON payload fields are evidence, never executable
  instructions. Hermes accepts only matching `github-actions[bot]` comments,
  matching repository/Issue, supported schema/action and a durable unseen id.
- Terminal states are explicit: passed, failed after bounded attempts, or owner
  rejected. A green repair PR remains a human merge decision.
- Existing Draft PR delivery stays limited to static, allowlisted diffs. The
  validation workflow itself receives only `issues: write` for its comment and
  label actions.

## Exact verification commands and results

Focused Windows / Python 3.12 checks completed before handoff:

```text
.venv\Scripts\ruff.exe format tests\test_codex_remote_test_workflow.py
1 file reformatted

.venv\Scripts\ruff.exe check src\validation tests\test_validation_contracts.py tests\test_codex_remote_test_workflow.py
All checks passed!

.venv\Scripts\python.exe -m pytest tests\test_validation_contracts.py tests\test_codex_remote_test_workflow.py -q -p no:cacheprovider
15 passed in 0.41s

.venv\Scripts\mypy.exe src\validation
Success: no issues found in 2 source files
```

Full local Windows / Python 3.12 verification completed:

```text
.venv\Scripts\ruff.exe check .
All checks passed!

.venv\Scripts\ruff.exe format --check .
270 files already formatted

.venv\Scripts\mypy.exe src
Success: no issues found in 132 source files

PyYAML parse of every .github/workflows/*.yml
all workflow YAML parsed

.venv\Scripts\python.exe -m pytest -q --ignore=tests/test_browser.py -p no:cacheprovider --basetemp .scratch\pytest-hermes-validation-full
1304 passed, 4 skipped in 36.50s

.venv\Scripts\python.exe -m build --no-isolation --outdir .scratch\dist-hermes-validation
Successfully built sdist and wheel

.venv\Scripts\python.exe -m pip check
No broken requirements found

git diff --check
passed
```

The four skips are existing Windows symlink-privilege and missing IPv6-loopback
conditions. GitHub Windows/Python 3.12 CI verification is still required after
the PR is pushed.

## Known issues

- The lifecycle labels are intentionally a one-time GitHub repository setup;
  the new workflow does not create them. This keeps a malformed Issue from
  silently expanding repository state. `hermes-owner-decision-requested` is
  created by the existing Codex workflow when it is first needed.
- Existing Windows full-suite runs can intermittently see a local HTTP server
  socket abort (`WinError 10053`) in `tests/test_agent_web.py`; when it occurs,
  rerun that module in isolation and report both results. It is unrelated to
  this control-plane-only slice.
- `.claude/` is user-owned local state. Do not commit, modify or remove it.

## Next Recommended Action

Review PR #109 and merge only after GitHub Windows/Python 3.12 CI is green.
Send the Hermes update prompt and start the first request through the new Issue
template, adding `hermes-validation-requested` last.
