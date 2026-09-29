# Handoff — machine-local developer credentials

Updated: 2026-09-29 (Asia/Taipei).
Branch: `codex/local-dev-secrets`.
Base: `origin/main` at `8df437bac9d74572f38c74326cf961029d824674`.

## Goal

Let each development computer provide its own GitHub/OpenAI/AEP access tokens
without committing them, repeatedly refreshing the shared GitHub CLI login, or
making platform runtime code discover credential files.

## Completed

- Added an empty tracked `.env/example.yaml` and ignored every other file below
  `.env/`, including the intended `.env/local.yaml`.
- Added `scripts/import-local-env.ps1`. It explicitly loads a flat YAML mapping
  into the current PowerShell process, accepts only `GH_TOKEN`,
  `OPENAI_API_KEY`, and `AEP_GITHUB_TOKEN`, ignores unused empty entries,
  rejects duplicates/unknown names, and prints loaded variable names only.
- Documented per-computer setup, minimum GitHub token permissions, verification,
  plaintext-at-rest risk, and the distinction from GitHub Actions secrets.
- Added tests for empty examples, ignore policy, real PowerShell loading,
  rejection of unknown names, and non-disclosure in output.

## In Progress

- The change is implemented and verified in its isolated worktree. It has not
  been rebased onto PR #125 because that PR is green but not yet merged.

## Remaining

1. Merge green PR #125.
2. Fetch/rebase this branch onto the resulting `origin/main` and resolve the
   expected `HANDOFF.md` replacement by keeping this handoff.
3. Push and open a narrow PR for the local YAML credential helper.
4. On each development computer, copy `.env/example.yaml` to
   `.env/local.yaml`, enter that computer/user's token, and dot-source
   `scripts/import-local-env.ps1` in the terminal that will run `gh`.

## Architecture decisions

- This is an explicit developer-shell helper outside the platform import path.
  Runtime code, Registry assets, Workflows, Issues and GitHub Actions never read
  the local YAML.
- Tokens remain environment values at execution time. The repository carries
  neither token values nor a production credential backend.
- The parser intentionally supports only a flat allowlisted YAML mapping. It is
  not a general YAML evaluator and cannot set arbitrary process variables.
- `.env/local.yaml` is plaintext at rest despite being ignored. It is suitable
  only for a trusted developer computer, with one narrow token per user and
  machine; it must not be copied to a shared test workstation.

## Verification

```text
C:\Users\OpenLab\Documents\workspace\agentic-ai-team-platform\.venv\Scripts\python.exe -m pytest tests\test_local_developer_environment.py -q --basetemp .scratch\pytest-local-env
4 passed in 1.06s

C:\Users\OpenLab\Documents\workspace\agentic-ai-team-platform\.venv\Scripts\python.exe -m ruff check .
All checks passed!

C:\Users\OpenLab\Documents\workspace\agentic-ai-team-platform\.venv\Scripts\python.exe -m ruff format --check .
278 files already formatted

C:\Users\OpenLab\Documents\workspace\agentic-ai-team-platform\.venv\Scripts\python.exe -m mypy
Success: no issues found in 220 source files

git check-ignore -v .env/local.yaml
.gitignore:11:.env/* .env/local.yaml

git check-ignore .env/example.yaml
not ignored (expected)

git diff --check
passed
```

## Known issues

- PR #125 is separate and currently green. Do not mix its fixture-scoped
  authorization changes into this branch before it merges.
- `.claude/` in the primary checkout is user-owned local state; do not add,
  remove or modify it.

## Next recommended action

Merge PR #125, then rebase and open the local developer credential PR.
