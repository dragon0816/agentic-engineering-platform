# Handoff — fixture-scoped Personal Proof authorization

Updated: 2026-09-29 (Asia/Taipei).
Branch: `codex/personal-proof-fixture-policy`.
Base merged into branch: `origin/main` at
`5b6c3b1bcdf118319e07c4235f6678c291a39b35`.

## Goal

Allow the fixed Hermes deployment profile to execute `personal.proof` without
turning its validation grant into general workspace filesystem access.

```text
main artifact -> Hermes exact-SHA install -> fixture-only local grant
-> personal.proof -> sanitized evidence
```

## Completed

- Added `company-agent/personal-proof-fixture-read@1.0.0`, a distinct local
  capability requiring `filesystem.read` but wired by the trusted host only to
  `<workspace>\hermes-fixtures\personal-proof`.
- Changed `company-agent/personal-proof@1.0.0` to call the fixture reader. A
  grant for the general `filesystem/read-file` asset cannot authorize it.
- Changed the deployment payload to request only the fixture-reader asset.
- Added tests for allowed fixture reads, traversal/out-of-root refusal,
  default-deny behavior and asset-specific authorization.
- Preserved the local Codex Pro worker merged in PR #126 while merging current
  `main` into this branch. The only merge conflicts were the accumulating
  `HANDOFF.md` and `docs/TASKS.md`; both now contain current state.
- Issue #127 installed the PR #126 main artifact successfully after an initial
  local ZIP lock. It remains correctly blocked because this fixture capability
  is not yet on `main`.

## In Progress

- PR #125 is updated locally to current `main`. Its prior CI was green, but the
  refreshed merge commit still needs to be pushed and checked by GitHub.

## Remaining

1. Push this branch and wait for the refreshed PR #125 Platform verification.
2. Review and merge PR #125 only after CI is green.
3. Let the successful main build create a new artifact-pinned deployment
   request. Hermes must install that exact SHA and grant only
   `company-agent/personal-proof-fixture-read@1.0.0` to `leo.chi`.
4. Hermes retries the fixed profile once after the artifact/setup fingerprint
   changes and records run/trace IDs and sanitized evidence.
5. Separately fix Hermes lifecycle concurrency: one resident poller, a
   per-request lease, no replay of superseded payloads, artifact-specific temp
   paths, and one terminal evidence comment per fingerprint.

## Architecture decisions

- Registry publication, local capability installation and local execution
  authorization remain separate.
- The fixture root is fixed by trusted host wiring. GitHub Issue prose, model
  output and workflow arguments cannot widen it.
- A separate asset identity gives the local policy an enforceable boundary;
  hidden path conditions are not added to a broad filesystem grant.
- The proof remains read-only and local. No model, Knowledge, browser, Git,
  network, email, DUT, filesystem-write or production side effect is added.
- Hermes environment/setup failures remain BLOCKED and do not receive
  `codex-fix` unless evidence proves a repository implementation defect.

## Verification

```text
.venv\Scripts\python.exe -m pytest tests\test_personal_proof_fixture_policy.py tests\test_company_agent_assets.py tests\test_host_wiring.py tests\test_dispatch.py tests\test_deployment_validation_loop.py tests\test_platform_transport.py tests\test_codex_remote_test_workflow.py tests\test_local_developer_environment.py -q --basetemp .scratch\pytest-pr125-main-merge-focused
89 passed, 1 skipped in 15.15s

.venv\Scripts\python.exe -m pytest --ignore=tests\test_browser.py -q --basetemp .scratch\pytest-pr125-main-merge-full
1326 passed, 4 skipped in 35.03s

.venv\Scripts\python.exe -m ruff check .
All checks passed!

.venv\Scripts\python.exe -m ruff format --check .
281 files already formatted

.venv\Scripts\python.exe -m mypy
Success: no issues found in 223 source files
```

## Known issues

- `.claude/` is user-owned untracked state and must not be added or modified.
- Pytest could not write `.pytest_cache` in this checkout; explicit
  `--basetemp` was used and all applicable tests completed.
- Hermes reported `[WinError 32]` for an old artifact path and then posted
  repeated #127 evidence. The trusted current #127 payload is
  `deployment-personal-proof-36541643800`, target SHA `5b6c3b1...`, artifact
  `11020643502`; old payload `deployment-personal-proof-36456543696` must not be
  replayed.

## Next Recommended Action

Commit and push the current merge resolution, wait for PR #125 CI, then merge
only when green. Hermes should remain quiet for #127 until a new successful
main artifact changes the deployment fingerprint.
