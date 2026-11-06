# Release blocker fixed — release-test-ids

Base: `ce924e5b`; branch: `release-test-ids`. No push. Next action: orchestrator reviews/merges this commit, then retries the normal release verification on main. The existing leaked release log was not inspected, copied or published by this worker.

## Changes

- Every parametrized case in `tests/test_bi_atlas_file_import.py` now has a short explicit ID. The 100,000-character malformed input remains intact, as do every input, test body and assertion. An AST comparison against ce924e5b, excluding only the new `ids` keyword, is identical.
- `scripts/release_windows.py::run` no longer forwards the last 25 lines of failed child stdout/stderr into ReleaseError. It reports command and exit code; failure still stops the release, successful output still reaches internal revision/build consumers. This prevents arbitrary pytest OS tracebacks from rendering inherited environment values into release logs. No attempt to guess secret names/patterns.
- Added synthetic-only release regressions: failure never echoes child stdout/stderr, while successful output is returned unchanged. Before implementation, the failure test failed and success test passed; both pass after the fix.
- Audit found the sign-in test serialized the inherited environment into an assertion operand. It now computes exactly the same JSON containment predicate before asserting its boolean, so a failing check cannot print the environment string. No weakening of the condition.
- Test helper/script searches found no other explicit whole-environment print. The restricted-runner test prints variable names only. Ordinary pytest argument rendering was the original indirect source; the release runner now excludes all failed child output.
- Release guide explains the diagnostic behavior; DECISIONS appends the rationale and rejected pattern-redaction alternative; TASKS marks completion. No runtime/BI model/feed-golden change.

## Verification (Windows)

Python: `C:/Users/Chi_L/Documents/ChatGPT/agentic-engineering-platform/.venv/Scripts/python`; `PYTHONPATH=src` for pytest.

- `python -m pytest tests/test_bi_atlas_file_import.py -q --tb=short --basetemp C:/Temp/release-test-ids-atlas`: 13 passed in 31.91s, including the real headless browser test, no setup/teardown errors. Browser tests ran one file at a time with private basetemps.
- `python -m pytest tests/test_release_windows.py -q --tb=short`: 10 passed in 13.97s.
- `python -m pytest tests/test_agent_code.py -q --tb=short --basetemp C:/Temp/release-test-ids-agent-code`: 8 passed in 48.92s, including its browser case.
- Full repository collection through a local audit plugin: exit 0, 5,997 items, longest full node ID 316 characters, no IDs over 1,000, no collection errors. It reports test names without parameter values and numeric lengths only; does not print environment values. No other huge generated IDs found.
- `python -m ruff check .`: passed.
- `python -m ruff format --check .`: 1389 files already formatted.
- `python -m mypy`: no issues in 1047 source files.
- `python -m build`: wheel and sdist built successfully.
- `python -m pip check`: no broken requirements.
- `git diff --check`: passed.
- An extra mypy invocation explicitly naming the script alongside src/tests reported the same module under two names (namespace scripts); the repository's configured CI command above passes. An initial scratch collection runner lacked the repository import path; corrected it and obtained the successful complete collection above. No such tooling workaround changes shipped code or tests.

## Scope and safety

No full test-suite execution or actual release.cmd/package/tag/publish run here; the requested files and CI checks passed, and full collection audits all generated IDs. No credentials, environment values or incident-log content were printed; regression fixtures contain fictional text only. Own focused browser tests close their browsers normally. Owner Agent Web and real vault were not touched.

Previous completed SOP remains in ce924e5b: 98 fresh, reviewed screenshots plus the Traditional Chinese guide. Its temporary servers/browsers were already shut down; they were not restarted for this task. Local audit/build/test artifacts stay ignored under `.scratch` or task-specific temp folders.
