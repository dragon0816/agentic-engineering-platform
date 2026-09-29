# Handoff — local Codex Pro repair worker

Updated: 2026-09-29 (Asia/Taipei).
Branch: `codex/local-codex-worker`.
Base: `origin/main` at `8df437bac9d74572f38c74326cf961029d824674`.

## Goal

Replace the API-billed GitHub Codex Action with a trusted development-computer
worker that uses `codex login`/ChatGPT Pro, while keeping GitHub as the durable
queue and Hermes as the exact-SHA real-environment validator.

```text
Hermes FAIL -> GitHub typed queue -> local Codex -> Draft PR + CI
     ^                                             |
     +---------- exact-SHA Hermes retest <---------+
```

## Completed

- Replaced `.github/workflows/codex-remote-test-fix.yml` with a queue-only
  workflow. It accepts `codex-fix` only from `HERMES_GITHUB_BOT_USER` while
  `CODEX_EXECUTION_MODE=local-worker`, fingerprints the default-branch SHA,
  Issue body and bounded Hermes comments, and writes one bot-authored
  `codex-local-request/v1` payload per fingerprint.
- Added typed strict queue/result contracts and the local worker in
  `development.codex_worker`. It accepts only `github-actions[bot]` payloads,
  keeps durable local state, uses isolated Git worktrees, and bounds retries by
  request fingerprint.
- Codex runs through `codex exec --ephemeral --sandbox workspace-write` with a
  fixed repository-owned prompt and output schema. GitHub/OpenAI/AEP tokens,
  GitHub CLI auth configuration, Git askpass and SSH agent variables are removed
  from the Codex environment. An empty Git/GitHub configuration is supplied to
  the subprocess while `CODEX_HOME` remains available for ChatGPT Pro auth.
- Deterministic wrapper code refuses deletion/rename/conflict states and changes
  outside `src/`, `tests/`, `docs/` and `HANDOFF.md`; it runs pytest (excluding
  the known local Edge-only module), Ruff, format check, mypy and `git diff
  --check` before commit/push/Draft PR creation.
- Added `.github/workflows/codex-local-fix-handoff.yml`. A same-repository worker
  PR from `CODEX_LOCAL_WORKER_USER` receives a bot-authored exact-SHA
  `hermes-next-action/v1` retest payload. No workflow merges.
- Added `.github/workflows/codex-local-evidence-handoff.yml`. When Codex names a
  specific missing fact, the worker posts `codex-local-result/v1`; GitHub turns
  it into a bot-authored bounded `collect_evidence` payload for Hermes. New
  Hermes evidence changes the fingerprint and permits one new repair attempt.
- Added an ignored per-computer `.env/local.yaml` flow. The tracked example is
  empty and accepts only `GH_TOKEN` and `AEP_GITHUB_TOKEN`; the local worker uses
  Codex subscription login, not an OpenAI API key.
- Added foreground and Windows logon-task scripts. The resident worker polls
  every 60 seconds and uses `gh auth setup-git` only in the outer deterministic
  process.
- Updated architecture, README, task record and operational documentation.

## In Progress

- Implementation and local verification are complete. The branch still needs a
  commit, push, Draft PR and GitHub Windows/Python 3.12 verification.

## Remaining

1. Commit and push `codex/local-codex-worker`; open a Draft PR against `main`.
2. Review and merge the PR only after Platform verification is green.
3. Set repository variables `CODEX_EXECUTION_MODE=local-worker` and
   `CODEX_LOCAL_WORKER_USER=dragon0816`. Preserve the already configured exact
   Hermes bot and merge-reviewer variables.
4. On the trusted development computer, copy `.env/example.yaml` to
   `.env/local.yaml`, set a repository-limited `GH_TOKEN`, run `codex login`,
   then run `scripts/run-local-codex-worker.ps1 -Once`.
5. Install/start `scripts/install-local-codex-worker-task.ps1` and execute the
   documented harmless dummy Issue test end to end.
6. Delete the GitHub repository secret `OPENAI_API_KEY` only after one dummy
   request produces a Draft PR and GitHub produces the exact-SHA Hermes payload.

## Architecture decisions

- GitHub remains control plane/queue; the trusted development PC is the coding
  execution plane; the company Bridge/Hermes environment remains the real
  integration-validation plane.
- ChatGPT authentication is local machine state and is never copied into a
  GitHub-hosted runner, Issue, repository file or Hermes host.
- Reasoning cannot deliver its own GitHub changes. Codex edits a token-free
  worktree; deterministic code separately validates, commits, pushes and opens a
  Draft PR.
- Issue and comment prose remains untrusted data even when a trusted workflow
  copies it. Only fixed schemas/actions cross machine boundaries.
- Human review remains the only merge authority.

## Verification

```text
C:\Users\OpenLab\Documents\workspace\agentic-ai-team-platform\.venv\Scripts\python.exe -m pytest tests/test_codex_remote_test_workflow.py tests/test_local_developer_environment.py -q --basetemp .scratch\pytest-local-codex-worker-5
21 passed in 1.17s

C:\Users\OpenLab\Documents\workspace\agentic-ai-team-platform\.venv\Scripts\python.exe -m pytest --ignore=tests/test_browser.py -q --basetemp .scratch\pytest-local-worker-full-2
1323 passed, 4 skipped in 34.20s

C:\Users\OpenLab\Documents\workspace\agentic-ai-team-platform\.venv\Scripts\python.exe -m ruff check .
All checks passed!

C:\Users\OpenLab\Documents\workspace\agentic-ai-team-platform\.venv\Scripts\python.exe -m ruff format --check .
280 files already formatted

C:\Users\OpenLab\Documents\workspace\agentic-ai-team-platform\.venv\Scripts\python.exe -m mypy
Success: no issues found in 222 source files

Workflow YAML parsed through PyYAML; every embedded `actions/github-script`
program parsed through `node --check`; both PowerShell entry scripts parsed
through the PowerShell AST parser.
```

## Known issues

- PR #125 is a separate green, open PR for fixture-scoped personal-proof
  authorization. This branch deliberately does not include it.
- The current GitHub CLI credential can read Issues/PRs but receives HTTP 403
  when reading repository Actions variables. A replacement `GH_TOKEN` needs
  repository Metadata read, Contents read/write, Issues read/write, Pull requests
  read/write and Variables read/write before Codex can configure those variables.
- Full local pytest includes nine existing Edge/browser failures on this machine;
  per owner direction the applicable baseline excludes `tests/test_browser.py`.
- `.claude/` in the primary checkout is user-owned local state and was not
  touched.

## Next recommended action

Commit, push and open the Draft PR. If GitHub rejects the push/PR or variable
configuration, put a replacement token only in `.env/local.yaml`; never paste it
into chat or commit it.
