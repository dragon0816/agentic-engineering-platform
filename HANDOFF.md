# Handoff — fixture-scoped personal-proof authorization

Updated: 2026-09-29 (Asia/Taipei).
Branch: `codex/personal-proof-fixture-policy`.
Base: `origin/main` at `8df437bac9d74572f38c74326cf961029d824674`.

## Goal

Complete the first automatic development-to-company-computer validation path
without allowing its read-only test grant to become a general filesystem grant.

```text
main CI artifact -> GitHub payload comment -> Hermes discovery
-> exact bundle install -> fixture-scoped personal.proof -> evidence
```

## Completed

- PR #121 and its payload-comment correction are merged. GitHub now creates
  trusted `hermes-validation/v1` comments before adding queue labels.
- Hermes generically discovered and installed the exact deployment artifact for
  Issue #124. It verified the bundle revision, Bridge/agent readiness and
  shipped `company-agent/personal-proof@1.0.0` asset.
- Hermes correctly blocked before execution because AEP had only the general
  `filesystem/read-file` handler rooted at the whole workspace. It refused to
  substitute a broad grant for fixture-only authorization.
- Added `company-agent/personal-proof-fixture-read@1.0.0`. It requires the
  ordinary `filesystem.read` permission but is a distinct capability asset,
  handled only under `<workspace>\hermes-fixtures\personal-proof`.
- Changed the Personal Proof workflow to call that capability, rather than the
  general workspace reader. A grant for general `filesystem/read-file` cannot
  authorize it.
- Changed the generated GitHub deployment payload to require the exact fixture
  capability grant; no longer names the incorrect `platform/filesystem.read`
  asset identity.
- Added fixture-boundary tests and updated deployment/Company Agent docs and
  `docs/TASKS.md`.

## In Progress

- The fixture-scoped authorization implementation is uncommitted on this
  branch and needs a review PR.

## Remaining

1. Push, review and merge this branch.
2. Hermes updates/reinstalls the exact new main artifact through its normal
   generic deployment discovery.
3. Hermes' fixed profile writes or verifies one pre-approved local grant only
   for `company-agent/personal-proof-fixture-read@1.0.0`, actor `leo.chi`, and
   the controlled fixture. It must not create a general filesystem grant.
4. The changed local setup fingerprint causes the blocked deployment payload to
   retry once. Hermes records a run ID, trace IDs and sanitized result, then
   adds `hermes-validation-passed` only on success.

## Architecture decisions

- Registry/control-plane publication remains separate from local execution
  authorization. This change supplies a local capability boundary; it does not
  grant it automatically.
- A capability grant is asset-specific. A new fixture-only capability is safer
  than adding hidden path fields to the existing general filesystem grant.
- The handler's allowed root is fixed by trusted host wiring, not a GitHub Issue
  payload, model output or workflow argument. Paths outside the fixture return
  a closed read outcome and reveal no data.
- No model, Knowledge, browser, Git, DUT, email, network or write capability is
  added by this slice.

## Verification

```text
.venv\Scripts\python.exe -m pytest tests/test_personal_proof_fixture_policy.py tests/test_company_agent_assets.py tests/test_host_wiring.py tests/test_dispatch.py tests/test_deployment_validation_loop.py -q --basetemp .scratch\pytest-fixture-policy-final
52 passed in 0.92s

.venv\Scripts\python.exe -m ruff check .
All checks passed!

.venv\Scripts\python.exe -m ruff format --check .
277 files already formatted

.venv\Scripts\python.exe -m mypy
Success: no issues found in 220 source files

git diff --check
passed
```

## Known issues

- `.claude/` is user-owned local state; do not add, remove or modify it.
- Issue #124 remains correctly blocked until a bundle containing this change is
  merged and Hermes sees the changed fixture-policy setup fingerprint.
- Full local pytest cannot be reported as green: it hits an unrelated existing
  Edge browser startup failure in this environment. GitHub Windows/Python 3.12
  CI is required for the PR.

## Next recommended action

Run final diff verification, commit and push this branch, then create a review
PR. After merge, Hermes should resume through generic discovery rather than an
Issue-number-specific instruction.
