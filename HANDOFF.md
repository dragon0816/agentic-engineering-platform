# Handoff — deployment validation loop v1

Updated: 2026-09-28 (Asia/Taipei).
Branch: `codex/deployment-validation-loop`.
Base: `origin/main` at `fde0eea19cca455be462a8a26d3667f3292a3203`.

## Goal

Establish the first reproducible development-computer to company-computer loop
without trying to validate every Company Agent capability at once:

```text
merged main -> successful Platform verification -> exact Windows artifact
-> fixed Hermes personal.proof deployment profile -> evidence -> terminal result
```

The first profile is intentionally read-only and side-effect-free. SOP PDF
authoring, Knowledge asking, workflow 7/13 and DUT validation remain later
profiles after this path is proven green.

## Completed

- Added `DeploymentArtifact`, a serializable contract pinning repository,
  40-character package commit, successful workflow run, artifact ID, and
  artifact name. A differently named artifact is refused even if it exists.
- Added `.github/workflows/hermes-deployment-personal-proof.yml`.
  It runs only after successful `Platform verification` on `main`, locates
  only `aep-windows-preview-<head SHA>` from that exact run, and creates a
  machine-readable `hermes-validation/v1` deployment request Issue.
- The generated request is fixed to
  `aep-deployment-personal-proof-v1` and
  `company-agent/personal-proof@1.0.0`; it names the target Bridge and actor
  through repository variables, and includes immutable artifact metadata.
- Added `docs/deployment-validation-loop.md` with the handoff, required GitHub
  variables and Hermes acceptance requirements.
- Added contract/workflow tests in `tests/test_deployment_validation_loop.py`.
- Updated `docs/TASKS.md` with this active cross-cutting deployment slice.

## In Progress

- Commit `1fc2df9` is pushed to `origin/codex/deployment-validation-loop`.
  Local GitHub CLI authentication lacks the `public_repo` scope, so it cannot
  create the PR; use the direct compare URL instead.
- Hermes must implement/enable the fixed profile before it can consume the
  generated deployment request. Hermes code is outside this repository.

## Remaining

1. Configure repository Actions variables:
   - `HERMES_DEPLOYMENT_BRIDGE=bridge-tp401555`
   - `HERMES_DEPLOYMENT_ACTOR=leo.chi`
2. Have Hermes accept only the generated trusted payload and implement the
   profile-owned install/update and read-only `personal.proof` verification.
3. Push, review and merge this PR. The next successful `main` verification
   should automatically create exactly one deployment validation Issue.
4. Hermes installs the exact artifact, verifies the source revision,
   exports assets, runs `personal.proof` against its controlled local fixture,
   and records sanitized evidence plus a terminal label.
5. Only after this profile has a reproducible green path, add the SOP draft
   profile, then Knowledge, then side-effecting workflow/hardware profiles.

## Architecture decisions

- GitHub is the control-plane handoff. The enrolled Company Bridge remains the
  execution plane and enforces membership, grants and local resource access.
- A CI artifact is immutable deployment input, not a Registry asset,
  authorization grant, model configuration or secret.
- The first profile has no model or Knowledge dependency. It proves bundle
  delivery, Bridge/agent readiness, deterministic routing, workflow execution,
  trace evidence and GitHub reporting before wider features are introduced.
- The GitHub workflow does not check out source, run a Bridge command, download
  a bundle, execute Issue text, issue credentials, modify local configuration,
  or merge a pull request.
- Hermes must use fixed profile-owned code; Issue content is evidence only and
  cannot supply arbitrary commands or configuration instructions.

## Verification

Completed on this branch:

```text
.venv\Scripts\python.exe -m pytest tests/test_deployment_validation_loop.py tests/test_validation_contracts.py tests/test_company_agent_assets.py tests/test_host_runtime.py tests/test_local_agent.py tests/test_windows_preview_bundle.py tests/test_codex_remote_test_workflow.py --basetemp .scratch\pytest-deployment-verified -q
49 passed in 1.34s

.venv\Scripts\python.exe -m ruff check .
All checks passed!

.venv\Scripts\python.exe -m ruff format --check .
276 files already formatted

.venv\Scripts\python.exe -m mypy
Success: no issues found in 219 source files

Node.js syntax check of the new actions/github-script block
passed

git diff --check
passed
```

The full local pytest suite was attempted with a workspace-local basetemp but
did not complete inside the 30-second command window. A separate full run first
stopped at existing `tests/test_browser.py` because Edge published no remote
debugging port (`browser_would_not_start`), after 57 passing tests. This branch
does not modify browser code. GitHub Windows/Python 3.12 CI remains required.

## Known issues

- `.claude/` is user-owned untracked state. Do not add, remove or modify it.
- The new workflow cannot create a request until both required Actions variables
  exist and the usual `hermes-*` labels exist in the repository.
- GitHub Actions evaluates a `workflow_run` workflow from the default branch.
  The successful `main` Platform verification created by merging this PR is
  expected to start the first deployment request automatically.
- Hermes currently needs an update to recognize
  `install_and_personal_proof` and `aep-deployment-personal-proof-v1`.

## Next recommended action

Create the PR from
`https://github.com/dragon0816/agentic-engineering-platform/compare/main...codex%2Fdeployment-validation-loop?expand=1`.
Set the two repository variables before merging. The successful `main` CI run
created by the merge should then trigger the first automatic Company Bridge
deployment validation request.
