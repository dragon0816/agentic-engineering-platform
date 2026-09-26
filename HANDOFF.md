# Handoff — remote Hermes repairs can create bounded Draft PRs

Updated: 2026-09-26 (Asia/Taipei).
Branch: `fix/codex-action-test-environment`.
Pull request: #107, https://github.com/dragon0816/agentic-engineering-platform/pull/107.
Base: `main` at `5dc6dffa3f144cd8d28f58d382157ed56cfd22a5`.

## Goal

Turn a qualified `codex-fix` remote Hermes failure report into a Codex analysis
and, only where evidence supports a narrow repair, a human-reviewable GitHub
Draft PR. Never auto-merge and never let untrusted Issue content gain Codex or
GitHub write access.

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

## In Progress

- PR #107 exact implementation head `a23a043` passed GitHub Actions run
  `36227946815` on Windows/Python 3.12 in 3m31s. It remains review-only and
  must not be merged automatically.

## Remaining

- In GitHub **Settings -> Actions -> General**, set workflow permissions to
  **Read and write permissions**. The delivery job otherwise cannot create the
  branch and Draft PR; `OPENAI_API_KEY` remains a separate repository secret.
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
  Human review, normal CI and Hermes rebuild/retest are required before merge.

## Exact verification commands and results

Windows / Python 3.12:

```text
.venv\Scripts\python.exe -m pytest tests\test_codex_remote_test_workflow.py -q -p no:cacheprovider
6 passed in 0.17s

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

GitHub Actions run 36227946815 at a23a043
passed in 3m31s on Windows/Python 3.12, including pytest, Ruff, mypy, build,
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
- `.claude/` is user-owned local state. Do not commit, modify or remove it.

## Next Recommended Action

Review and merge green PR #107. Then enable GitHub Actions read/write workflow
permissions and rerun one focused Hermes failure report to prove
analysis-to-Draft-PR delivery.
