# Handoff — Hermes retest notifies the human merge reviewer

Updated: 2026-09-26 (Asia/Taipei).
Branch: `fix/codex-action-test-environment`.
Pull request: #107, https://github.com/dragon0816/agentic-engineering-platform/pull/107.
Base: `main` at `5dc6dffa3f144cd8d28f58d382157ed56cfd22a5`.

## Goal

Turn a qualified `codex-fix` remote Hermes failure report into a Codex analysis
and, only where evidence supports a narrow repair, a human-reviewable GitHub
Draft PR. After Hermes retests a green repair, notify the configured reviewer;
the reviewer, never an Action, makes the merge decision.

## Completed

- PR #105 is merged. It provides the narrow Issue-label trigger, the bounded
  Hermes prompt, `openai/codex-action@v1` in a workspace-only/no-network job,
  structured Issue comments, an Issue template and documentation.
- Its live run on Issue #106 succeeded after the secret name and API billing
  were corrected (run `36159459225`). Codex correctly did not guess a code
  change because the report did not contain the tested commit or readable
  artifact evidence.
- PR #107 already adds a fixed Python 3.12 and `.[dev,office]` pre-Codex test
  environment. This fixes the live run's `No module named pytest` limitation.
- This branch now extends PR #107 with `deliver_draft`, an isolated GitHub
  Actions job. Codex emits `fix_ready` plus a complete bounded unified diff;
  delivery accepts only one to twelve non-binary, non-deleting, non-renaming
  diffs under `src/`, `tests/` or `docs/`, and requires `git apply --check` and
  `git diff --check` to pass.
- Delivery never executes a proposed patch, test, or Issue-provided command. It
  uses a fresh checkout, commits without repository hooks to a unique
  `codex/remote-test-issue-...` branch, and opens a Draft PR. It cannot mark a
  PR ready, approve it or merge it.
- The Codex analysis job retains `contents: read` and `issues: read`, no
  persisted checkout credential and no GitHub write capability. The delivery
  job has only `contents: write` and `pull-requests: write`, no OpenAI key and
  no Codex workspace. The final comment job alone has `issues: write`.
- Added static tests for delivery boundaries, restricted paths, Draft PR mode,
  and JavaScript parsing of every `actions/github-script` block. Documentation
  now describes the delivery security model, GitHub configuration and retest
  paths.
- Added `hermes-retest-ready-for-merge.yml`. It responds only to a newly added
  `hermes-retest-passed` PR label from the exact configured Hermes bot, on a
  same-repository `codex/remote-test-issue-...` branch targeting `main`.
  It verifies the exact head's `verify` check, marks an eligible Draft PR ready
  for review, requests the configured reviewer's review and posts the result.
  It has no checkout, OpenAI key, `contents: write`, or GitHub merge call.

## In Progress

- The new retest-notification implementation is ready to commit and push to
  PR #107. Its exact GitHub Actions result is pending the push.

## Remaining

- In GitHub **Settings -> Actions -> General**, set workflow permissions to
  **Read and write permissions**. The delivery job otherwise cannot create the
  branch and Draft PR; `OPENAI_API_KEY` remains a separate repository secret.
- In **Settings -> Secrets and variables -> Actions -> Variables**, set
  `HERMES_GITHUB_BOT_USER` to the exact GitHub App bot login that applies
  labels, and `HERMES_MERGE_REVIEWER` to the owner's GitHub username. Create
  the `hermes-retest-passed` label. The notification job intentionally does
  nothing if either variable is missing.
- After PR #107 merges, remove `codex-fix`, replace Issue #106 with one focused
  evidence-complete failure report, and add `codex-fix` again. Verify either:
  analysis-only for insufficient evidence, or exactly one Draft PR for a
  restricted patch with passing local tests.
- Keep Hermes artifacts bounded and safe: exact commit, expected/actual,
  failure excerpt and accessible repository paths. Hermes rebuild/retest remains
  required before a human merges any Draft PR.
- Existing product work is unchanged: E2E-01's real company-host DUT
  validation remains owner-run and pending; CI remains inert.

## Architecture decisions made

- The remote repair loop is a governed integration entry point, not a Registry,
  Bridge execution or runtime-authorization change.
- Issue data and Codex output are untrusted evidence. Codex runs last in its
  read-only analysis job; the write-capable delivery job never executes output
  code and has a strict patch allowlist.
- A Draft PR is a review artifact, not evidence that a remote failure is fixed.
  Normal CI and Hermes rebuild/retest are required before the human reviewer
  receives a merge notification. No Action approves or merges the PR.

## Exact verification commands and results

Windows / Python 3.12:

```text
.venv\Scripts\python.exe -m pytest tests\test_codex_remote_test_workflow.py -q -p no:cacheprovider
7 passed in 0.21s

.venv\Scripts\python.exe -m pytest -q --ignore=tests/test_browser.py -p no:cacheprovider --basetemp .scratch\pytest-codex-draft-pr-full
1295 passed, 4 skipped in 34.87s

.venv\Scripts\ruff.exe check .
All checks passed

.venv\Scripts\ruff.exe format --check .
265 files already formatted

.venv\Scripts\mypy.exe src
Success: no issues found in 130 source files

.venv\Scripts\python.exe -m build --no-isolation --outdir .scratch\dist-codex-draft-pr
Successfully built sdist and wheel

.venv\Scripts\python.exe -m pip check
No broken requirements found

PyYAML safe-load of .github/workflows/codex-remote-test-fix.yml
YAML parsed: analyze, deliver_draft, comment

Node syntax check of every actions/github-script block
passed through tests/test_codex_remote_test_workflow.py

git diff --check
passed

GitHub Actions run 36228162454 at c70d1ea
passed in 3m46s on Windows/Python 3.12, including pytest, Ruff, mypy, build,
pip check, offline preview installation and artifact upload
```

The four skips are existing Windows link-privilege and IPv6-loopback cases. No
Ubuntu or Python 3.11 validation was run locally, per owner instruction.

## Known issues

- Issue #106 is not suitable to prove Draft PR creation: it reports multiple
  failures and does not give Codex the exact checkout or readable artifacts.
- GitHub may deny Draft PR delivery if repository Actions workflow permissions
  stay read-only. The final Issue comment then reports delivery failure without
  rerunning or executing the patch.
- Two full local-suite attempts during this notification slice failed only on
  existing Windows HTTP test-server `ConnectionAbortedError: [WinError 10053]`
  cases while expecting a 404 (`test_platform_transport` once and
  `test_agent_web` once). Each affected module passed immediately in isolation;
  focused workflow tests, lint, formatting, mypy, build, pip check and YAML
  parsing passed. The pushed Windows/Python 3.12 CI result remains the
  authoritative full-suite check.
- `.claude/` is user-owned local state. Do not commit, modify or remove it.

## Next Recommended Action

Push the retest notification update to PR #107 and confirm its exact
Windows/Python 3.12 CI run. Then merge it manually. Configure the two repository
variables and label above, and have Hermes apply `hermes-retest-passed` only
after its retest and the exact PR `verify` check are green.
