# Main synchronization verification — 2026-10-21 UTC

Merged main `20351c96e58fbc906879a94eb2f46eeae1312dac` into feature head `385d7ea0`
with merge commit `0f4a78e39a1b05f8d33aeb4465897030771a4ab4` (two parents, no rebase).
Only HANDOFF/TASKS conflicted. The entire upstream files are byte-for-byte prefixes of the
resolved files; Voice records follow. `git diff origin/main -- src .github` is empty.
PR #240 remained Draft and became mergeable. No main push, force push or PR merge.

Pre-merge 77 related tests passed in 8.75s. Post-merge isolated venv:

```sh
python -m venv /tmp/aep-sync-venv
/tmp/aep-sync-venv/bin/pip install -q -e '.[dev,office]'
/tmp/aep-sync-venv/bin/python -m pytest tests/test_voice_*.py \
  tests/test_telegram_ingress.py tests/test_telegram_attachments.py \
  tests/test_knowledge_pipeline.py tests/test_knowledge_publish.py tests/test_knowledge_push.py \
  tests/test_tool_input_bounds.py tests/test_chat_authoring.py tests/test_draft_install_cards.py \
  tests/test_memory_preferences.py tests/test_memory_quality_web.py tests/test_outlook_com_threads.py -q
```

**134 passed, 1 skipped in 21.99s**. Skip: Chromium not installed.

```sh
/tmp/aep-sync-venv/bin/python -m ruff check .
/tmp/aep-sync-venv/bin/python -m ruff format --check .
/tmp/aep-sync-venv/bin/python -m mypy --platform win32
/tmp/aep-sync-venv/bin/python -m mypy --explicit-package-bases --follow-imports=silent \
  benchmarks/voice_to_knowledge tests/test_voice_*.py
/tmp/aep-sync-venv/bin/python -m pip check
/tmp/aep-sync-venv/bin/python -m build --outdir /tmp/aep-sync-dist
```

All pass: repository ruff/format (992 files), Windows-target mypy (734 files), focused strict
mypy (10 files), pip dependency consistency, wheel and sdist build.
Default `python -m mypy` on Linux fails with 26 errors in four files. Detached main
`20351c96` produces the **identical 26 diagnostic lines** (730 files before four Voice tests).
These concern Windows APIs/types in llm_gateway/control.py, harness/restricted_runner.py,
integrations/mcp_client.py and tests/test_filesystem.py. No existing runtime was changed.

## Full Linux suite — not green

```sh
/tmp/aep-sync-venv/bin/python -m pytest -q --junitxml=/tmp/aep-sync-pytest.xml
```

**3690 passed, 130 skipped, 3 failed in 250.49s**. Three failures:

| Test | Failure | Pure main result |
|---|---|---|
| test_conversation_harness.py::test_a_named_output_that_is_missing_or_empty_is_caught | expected 3 model calls, got 2 | same failure |
| test_gateway_link.py::test_autostart_from_the_card_uses_the_injected_scheduler | no winreg on Linux | same failure |
| test_release_windows.py::test_colleagues_get_a_manual_and_double_click_scripts | .cmd checkout has LF, test expects CRLF | same failure |

Reproduction against detached upstream, explicitly selecting upstream src (not editable feature):

```sh
git worktree add --detach /tmp/aep-upstream-check origin/main
cd /tmp/aep-upstream-check
PYTHONPATH=src /tmp/aep-sync-venv/bin/python -m pytest \
  tests/test_conversation_harness.py::test_a_named_output_that_is_missing_or_empty_is_caught \
  tests/test_gateway_link.py::test_autostart_from_the_card_uses_the_injected_scheduler \
  tests/test_release_windows.py::test_colleagues_get_a_manual_and_double_click_scripts -q
```

**3 failed in 1.54s**, same assertions/exceptions. Tested files and all src/deploy files are
unchanged versus main. These are baseline/platform failures, not evidence of a Voice regression;
this work does not patch Core/Harness to suppress them. Chromium/GUI/Windows/optional dependency
skips are not live acceptance. Local logs remain at /tmp/aep-sync-pytest.log,
/tmp/aep-upstream-pytest.log and /tmp/aep-{upstream,baseline}-mypy.log in this environment.

## GitHub CI at evidence collection

- Initial docs-only run 39533933211: cancelled when superseded, not passed or failed.
- Merged head 0f4a78e3 run 39535239198: in progress at pytest, no failed step reported yet.
- Later evidence-only push may supersede it; consult PR #240 checks for newest head.
- No completed failing GitHub CI result was available to attribute or fix. Do not substitute
  Linux checks for Windows CI or claim CI passed while pending.

Real STT still NOT_RUN: no artifact access approval; no retry of the denied metadata operations.
See docs/voice-to-knowledge/VOICE_NETWORK_REQUIREMENTS.md for exact denied host and required files.
