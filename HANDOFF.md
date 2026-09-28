# Handoff — deployment validation loop v1

Updated: 2026-09-29 (Asia/Taipei).
Branch: `codex/deployment-payload-comment`.
Base: `origin/main` at `90f4c7e486c77979981f3d23fa445933a155fafa`.

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
- PR #121 merged the first deployment-loop implementation. Its successful
  main CI created Issue #122 with a correct artifact identity, but placed the
  trusted payload in the Issue body. Hermes correctly refused it because its
  trust boundary accepts Actions comments only.
- The two repository variables are now configured:
  `HERMES_DEPLOYMENT_BRIDGE=bridge-tp401555` and
  `HERMES_DEPLOYMENT_ACTOR=leo.chi`.

## In Progress

- Correct the handoff format: this branch creates the Issue first, writes the
  `hermes-validation/v1` payload as a GitHub Actions comment with that exact
  source Issue number, and only then applies the queue labels.
- Hermes has implemented the fixed profile and generic poller, but it must
  accept GitHub's API author identifier `github-actions` (and the displayed
  `github-actions[bot]` equivalent) only for trusted action comments.

## Remaining

1. Push, review and merge the payload-comment correction PR.
2. Hermes accepts only the generated trusted action comment and performs the
   profile-owned install/update and read-only `personal.proof` verification.
3. The next successful `main` verification
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
  cannot supply arbitrary commands or configuration instructions. A queue
  label is applied only after a trusted action comment exists.

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

Payload-comment correction verification:

```text
.venv\Scripts\python.exe -m pytest tests/test_deployment_validation_loop.py tests/test_validation_contracts.py tests/test_codex_remote_test_workflow.py --basetemp .scratch\pytest-payload-comment -q
19 passed in 0.47s

.venv\Scripts\python.exe -m ruff check .
All checks passed!

.venv\Scripts\python.exe -m ruff format --check .
276 files already formatted

.venv\Scripts\python.exe -m mypy
Success: no issues found in 219 source files

Node.js syntax check of the new actions/github-script block
passed
```

The full local pytest suite was attempted with a workspace-local basetemp but
did not complete inside the 30-second command window. A separate full run first
stopped at existing `tests/test_browser.py` because Edge published no remote
debugging port (`browser_would_not_start`), after 57 passing tests. This branch
does not modify browser code. GitHub Windows/Python 3.12 CI remains required.

## Known issues

- `.claude/` is user-owned untracked state. Do not add, remove or modify it.
- Issue #122 is intentionally not consumed: it has no trusted payload comment.
  It is evidence of the pre-correction protocol mismatch, not a valid test.
- GitHub Actions evaluates a `workflow_run` workflow from the default branch.
  The successful `main` Platform verification created by merging this PR is
  expected to start the first deployment request automatically.
- GitHub's API reports GitHub Actions comments as author `github-actions`,
  whereas UI text may show `github-actions[bot]`; Hermes must use the fixed
  two-value canonical allowlist, never a broad bot allowlist.

## Next recommended action

Create and merge the correction PR from
`https://github.com/dragon0816/agentic-engineering-platform/compare/main...codex%2Fdeployment-payload-comment?expand=1`.
The successful `main` CI run created by that merge should then create a new
automatic Company Bridge deployment validation Issue with a trusted comment.
