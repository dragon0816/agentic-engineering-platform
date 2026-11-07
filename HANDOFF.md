# Verified SDE navigation repair — local release build next

## Authority and scope
Owner delegated orchestration until 2026-11-10. Worktree codex-lead, base b9d96ac7.
Speak short Traditional Chinese. No merge/push/tag/publish/install/restart without
owner word. Atlas push only in its workspace after confirmation there. Owner alone
restarts gateway. Check /api/activity before any Agent Web restart; none needed.
No real owner Workflow/draft/mailbox operation was used. Never print secrets/env.
No AEP file permission controls; IT decides.

## Owner incident
Read-only preview-0.1.0 workspace: conversation-7ada60df63c54668bc50b9256013aa16.
2026-11-07 19:34:40+08 start, weekly-report/apply succeeded among five steps;
mail failed draft_failed after 392164.4ms, end19:43:03. Local run
run-ba011f34976f4392a29080dda5cc1850, telemetry run-61b986ea3fd24c99.
Navigation did not cancel it. Original adapter discarded underlying COM cause;
historical operation/HRESULT cannot be reconstructed. Do not claim no partial
draft exists or retry automatically. Owner noticed no prompt. Their 5:02pm/5:17pm
observations match successful 2026-11-06 SDE mail runs; already explained.
A separate existing 11-07 21:15–21:28 run timed out in mail, not launched here.

## Changes and decisions
- ae1becf3: safe Outlook diagnostic stage/numeric HRESULT/scode only, no exception
  text/traceback/content/paths/env; same failure behavior, no retry.
- 3b3da4d5: live Outlook tests opt in explicitly; collection never probes COM.
- c0553d76: keep queued-send promise when delayed readiness notice arrives.
- Navigation change pending commit: exact actor-owned form identity, persisted
  start/validated args before lock, duplicate replay, explicit failed/interrupted
  retry; narrow state transaction preserves transcript append-only contract.
  Same original Agent/Gateway/Harness/engine/Bridge path; no new executor/policy.
  Running/succeeded forms consumed; return/reload reconciles; queued launch counted
  by activity; unrelated drafts/focus retained. Lost HTTP reply reconciles state.
  Another host instance projects unfinished attempt interrupted, never resumes.
  Exact legacy inline results project consumed; no guessed truncated args/uploads.
- Crash after transcript result before terminal marker remains interrupted with
  inspect-effects warning, not executor crash recovery. No automatic partial writes.
See appended docs/DECISIONS.md and docs/CONTRACTS.md; evaluation contains proofs.
Read-only reviewer /root/review_navigation approved all deltas, no blockers.

## Verification complete
Python C:/Users/Chi_L/Documents/ChatGPT/agentic-engineering-platform/.venv/Scripts/python.
PYTHONPATH=src, AEP_GUI_TESTS=0, AEP_OUTLOOK_TESTS=0, PYTHONIOENCODING=utf-8.
Final full: python -u -m pytest -vv -x --tb=short
 --junitxml=.scratch/codex-lead-full-verified.xml
 --basetemp C:/Temp/codex-lead-full-verified
**6018 passed,13 skipped in7707.83s (2:08:27), exit0**; session19671 complete.
Log .scratch/codex-lead-full-verified.log. All browser tests serial/temp hosts.
Ruff format --check src tests (1099), ruff check src tests, mypy src tests (1053)
passed. python -u -m build --no-isolation passed final source (log
.scratch/codex-lead-final-build.log); pip check passed. git diff --check passed.
Architecture review: original deterministic execution and approval boundaries
preserved, no Registry/provider/dependency changes or new side effects.
AST-only graphify update completed45185 nodes139675 edges; three existing
benchmark generated-script syntax warnings, graph ignored cache only.

First full:6017 passed13 skipped1 failed (early-send promise overwritten).
Deterministic baseline proof failed on b9d96ac7; guard+turngroups9 passed.
All26 Workflow cases and both old remote CI failures passed in first and final run.
Remote main b9d96ac7 CI42360202085 failed version geometry/Member Portal; no new
remote CI until owner authorizes push. Do not claim local pass is remote green.

## Release next
Owner asked another local Windows Agent+Bridge offline package including fixes.
Official scripts/release_windows.py uses git archive HEAD and clean tracked tree.
Commit verified navigation/docs, then use --quick --no-tag --notes-since
b1dd4cf85179d75b163d75e70fb2ccff9be63a56. --quick reuses completed exact-source full
above; static checks still run. No allow-dirty/skip unfinished checks.
126 dependency/gateway wheels prepared in .scratch/release-prep, cache warmed.
Output local dist/releases/<timestamp>-<revision>, retain older releases.
Verify zip SHA256SUMS, manifest revision, platform wheel contains new module and
UI guard. Record actual artifact path/hash and update TASKS after success.
No publishing/shared copy/install/restart. Final reply link package, state tests,
briefly explain owner run continued then draft failed and cause remains unknown.
