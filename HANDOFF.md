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
- e564e1ad navigation repair: exact actor-owned form identity, persisted
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

## Release completed
Owner-requested local Windows Agent+Bridge offline bundle built from clean
committed e564e1ad35a259b998936f672a3b43163c91bf78.
Command: python -u scripts/release_windows.py --quick --no-tag --notes-since
b1dd4cf85179d75b163d75e70fb2ccff9be63a56. Exit0; --quick reused completed exact-source
full above; builder reran Ruff and mypy before git archive HEAD export.
Log .scratch/codex-lead-release.log.

Folder: dist/releases/20261108-0234-e564e1ad/
Zip: aep-windows-preview-0.1.0-e564e1ad35a2.zip (189186782 bytes).
SHA256: 2aea35ba3e1e2e47d49b466a5389fe39c6ff35ec2dcf0f9f5b1fc3fc2b6d86a1
SHA256SUMS, zip integrity, all manifest file hashes/sizes and source revision
independently verified. Inner wheel verified to contain workflow_form_runs.py,
durable form contract/state transaction and queued-send UI guard.
Release includes installation/user guides, notes and BI SOP images. latest.json
points to this artifact. No tag/push/publish/shared copy/install/owner restart.

Next: owner may install/review the local package. Wait for explicit owner word
before integration/push. Documentation-only release record commit follows the
packaged revision; package remains pinned to tested e564e1ad.
