# Handoff — remote Hermes failure feedback in PR #105

Updated: 2026-09-25 (Asia/Taipei).
Branch: `feature/codex-remote-test-feedback`.
Pull request: #105, https://github.com/dragon0816/agentic-engineering-platform/pull/105.
Implementation commit: `1df61b619aa4f8380eacf2447ffcd235015c9d92`.

## Completed

- Added `.github/workflows/codex-remote-test-fix.yml`. It listens only for an
  Issue `labeled` event and runs only when the newly applied label is exactly
  `codex-fix`.
- Used the current official `openai/codex-action@v1` contract: checkout first
  with credentials disabled, `permission-profile: ":workspace"`,
  `safety-strategy: drop-sudo`, a 30-minute limit and structured output.
- Kept Issue content untrusted. A trusted `github-script` reads the event
  object, strips control characters, applies size bounds, parses the optional
  Hermes fields, and serializes the report into a clearly marked JSON evidence
  block. No Issue text is interpolated into a shell command.
- Kept GitHub write permission outside the Codex job. Codex is the last step in
  the analysis job, which has only `contents: read` and `issues: read`; a second
  job has only `issues: write` and posts the result to the same Issue.
- Required the action's default write-access check for the labeler. An optional
  repository variable, `HERMES_GITHUB_BOT_USER`, can name one exact GitHub App
  bot through `allow-bot-users`; broad user or bot allowlists are absent.
- Required the Issue comment to contain `Codex Analysis`, `Root Cause`,
  `Changes`, `Local Test Result`, and `Next Action`. When a fix is justified,
  Codex prepares and tests it in the ephemeral workspace and reports a unified
  diff where practical. It has no credentials or network path to push, open a
  PR, or merge.
- Added `.github/ISSUE_TEMPLATE/hermes-remote-test-failure.md` and
  `docs/remote-testing-codex-loop.md`, including the Hermes payload, security
  model, manual GitHub settings, retest lifecycle and exact dummy-Issue test.
- Added contract tests for the narrow trigger, permission separation, secure
  action configuration, output documentation and Hermes template.

## In Progress

- PR #105 is open. Its first GitHub Actions verification run was pending when
  this handoff update was prepared. Recheck the exact final head after this
  handoff commit is pushed.

## Remaining

- Review and merge PR #105 after its exact-head Windows/Python 3.12 CI passes.
- In repository Actions settings, add the secret `OPENAI_API_KEY`.
- Ensure the `codex-fix` label exists. Ensure the human or Hermes identity that
  applies it has repository write access. If Hermes is a GitHub App bot that
  the action cannot classify, set `HERMES_GITHUB_BOT_USER` to its exact login.
- After the workflow is on the default branch, create a dummy Issue without the
  label, then apply `codex-fix`. Verify the same Issue receives the five-section
  comment and that no branch, PR, or merge is created.
- Existing product work is unchanged: the E2E-01 real company-host DUT run and
  human acceptance recorded by the previous handoff remain pending.

## Architecture decisions made

- This is a governed feedback/integration entry point, not a new Registry,
  Bridge execution path or authorization path. It does not change the platform
  contracts or grant execution permission from publication.
- The Issue label is the automation trigger, while the action's actor check is
  the authorization gate. Ordinary Issue edits never invoke Codex.
- The secure first version deliberately has no repository write token in the
  Codex job. The runner's tested workspace changes are represented in the
  structured comment so a human can create and review the normal PR.
- Remote hardware evidence remains authoritative. GitHub CI can run local and
  unit tests, but cannot claim that a hardware failure is resolved until Hermes
  rebuilds and reruns it.

## Exact verification commands and results

Local Windows / Python 3.12:

```text
.venv\Scripts\python.exe -m pytest tests\test_codex_remote_test_workflow.py -q -p no:cacheprovider --basetemp .scratch\pytest-codex-workflow-green
3 passed in 0.02s

.venv\Scripts\python.exe -m pytest -q --ignore=tests/test_browser.py -p no:cacheprovider --basetemp .scratch\pytest-codex-remote-full
1292 passed, 4 skipped in 34.32s

.venv\Scripts\python.exe -m ruff check .
All checks passed

.venv\Scripts\python.exe -m ruff format --check .
265 files already formatted

.venv\Scripts\python.exe -m mypy
Success: no issues found in 212 source files

.venv\Scripts\python.exe -m build --no-isolation --outdir .scratch\build-codex-remote
Successfully built sdist and wheel

.venv\Scripts\python.exe -m pip check
No broken requirements found

PyYAML safe-load of .github/workflows/codex-remote-test-fix.yml
YAML syntax valid; jobs: analyze, comment

node --check on both extracted actions/github-script blocks
passed

git diff --check
passed after removing the template's extra trailing blank line
```

The four skips are the existing Windows link-privilege and IPv6-loopback
cases. The known local Edge remote-debug suite was not rerun; the change is
limited to GitHub workflow, Markdown and its static contract tests. No Ubuntu
or Python 3.11 validation was run, per owner instruction.

## Known issues

- The workflow cannot be triggered live until it is merged to the default
  branch and `OPENAI_API_KEY` is configured.
- The Codex workspace intentionally has no network. Artifact URLs are reported
  for follow-up; Hermes should include a bounded log excerpt or a path already
  present in the repository when Codex must inspect the content directly.
- Workspace edits are ephemeral because giving Issue-driven analysis a push
  token would materially expand the trust boundary. The structured response
  asks for a complete unified diff where practical.
- `.claude/` is user-owned local state. Do not commit, modify or remove it.

## Next Recommended Action

Wait for the exact-head check on PR #105, fix any failure caused by this change,
then review and merge the PR. Configure `OPENAI_API_KEY`, add the optional exact
Hermes bot variable only if required, and follow
`docs/remote-testing-codex-loop.md` with a dummy Issue. Do not use the first
live run for a production hardware failure.
