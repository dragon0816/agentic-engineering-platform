# Handoff

Date: 2026-09-30 (Asia/Taipei)
Branch: `codex/local-worker-result-diagnostics`
Base: `origin/main` at `4664a358cebcea9eba9efa361dadc76f3887feac`

## Goal

Recover the trusted Local Codex Pro repair worker after Issue #132 reached it
successfully but stopped with `FileNotFoundError` before writing a structured
result or opening a Draft PR.

## Completed

- Confirmed the Hermes-to-GitHub handoff completed: #132 contains trusted
  failure evidence, `codex-fix`, and bot-authored request
  `codex-local-132-d6e5edb4a9385e4a`.
- Confirmed the development-computer worker created its isolated worktree and
  result schema, but no `result.json`; no PR or merge occurred.
- Added deterministic Codex executable resolution that prefers `codex.exe`,
  then `codex.cmd`, before the generic name.
- Converted a missing structured result into an explicit `CommandFailure`
  rather than an unclassified `FileNotFoundError`.
- Allowed an explicitly re-queued failed request to run once more. Claiming it
  removes the queue label, so failure does not create a retry loop.
- Preserved and reused a failed worker worktree only when its complete Git
  status is clean; partially modified workspaces remain refused for review.
- Documented the retry and executable/result boundaries.

## In Progress

- Repair commit `26f7cf9` is pushed and open for review as PR #133:
  https://github.com/dragon0816/agentic-engineering-platform/pull/133

## Remaining

1. Review and merge PR #133.
2. After merge, update the resident worker checkout to `main`, recreate its
   broken Python 3.12 virtual environment, and restart the
   `AEP Local Codex Worker` Scheduled Task so its in-memory code is current.
3. Re-add `codex-local-queued` to #132 once. The same trusted request and clean
   preserved worktree should be reused.
4. Confirm the worker either opens a Draft PR or emits a bounded evidence
   request; it must not produce another unclassified failure.

## Architecture decisions made

- GitHub remains the durable queue; retry does not create a new Issue or request
  identity.
- A retry is operator-triggered by the queue label and bounded to one claim. It
  is not an automatic loop.
- Failed work is never silently discarded or reused after mutation.
- The Codex subprocess still receives no GitHub token or OpenAI API key and has
  no delivery authority; the deterministic outer worker verifies and delivers.

## Verification

Supported target: Windows, Python 3.12. Browser tests excluded per owner
instruction.

```text
python -m pytest tests/test_codex_remote_test_workflow.py -q
19 passed

python -m pytest --ignore=tests/test_browser.py -q
1344 passed, 4 skipped

python -m ruff check src/development/codex_worker.py tests/test_codex_remote_test_workflow.py
All checks passed

python -m ruff format --check src/development/codex_worker.py tests/test_codex_remote_test_workflow.py
2 files already formatted (after applying the formatter)

python -m mypy src tests
Success: no issues found in 224 source files
```

## Known issues

- The resident scheduled process was launched from an older worker checkout and
  must be restarted after this repair merges. Its existing `.venv` points to a
  removed Windows Store Python path and must be recreated with Python 3.12.
- Issue #132 remains `codex-local-failed`; it has not been re-queued while the
  repair is unmerged.
- Hermes' separate cron crash still needs its own runner-side traceback and fix;
  it must not replay #132 while the Local Codex worker is being repaired.

## Next Recommended Action

Review and merge PR #133, then update and restart the development computer's
worker and re-add `codex-local-queued` to Issue #132 exactly once.
