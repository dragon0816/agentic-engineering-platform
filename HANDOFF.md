# Handoff

Updated 2026-11-06 by the Codex same-card worker. This is the worker branch handoff, not a release authorization. The BI orchestrator owns integration, installer checks and publishing. Do not push.

## Goal and branch

Worktree: `C:/Users/Chi_L/.paseo/worktrees/2qnenase/bi-share-step`.
Branch: `bi-same-card`, based on local main `7be9daaa` at the orchestrator's request.
Implement the owner's same-card rule before release, and repair three outdated tests assigned by the orchestrator. Both scopes are now complete. Never access the owner's real vault. All work so far used synthetic data and temporary workspaces.

## Completed

- `398dbad2`: independently fix the pre-existing card-model-shape staging test to the F19 import-isolation rule. It fails unchanged against 7be9daaa; after the fix all 20 tests in the file pass.
- `743dcbbf`: same-card implementation: store fill-only summary/usage/scope; extraction alternatives retain evidence; one BI operation projection for push, sync, state_at, log and pushed share replay. Wiki does not opt in. New evidence ops carry optional validated context; appends merge only their new rows, preserving concurrent evidence review. Reference identity deduplicates rows; later reference time then canonical JSON is the deterministic tie-break. Stale evidence against a replaced value conflicts. Ambiguous old operations keep existing conflict handling.
- `updated` takes the maximum; model version 12 rebuilds BI materialization. Repository replay policy 1 is persisted separately in repo.sqlite user_version, so incomplete files do not repeatedly trigger migration. Opening an old BI database first replays its repository cache.
- Contracts, decisions (including the 11-05 reference identity clarification), card model, design same-card table and task record are updated. Source-in-two-homes folder conflict is explicitly out of scope and remains open.

## Verification

Interpreter: `C:/Users/Chi_L/Documents/ChatGPT/agentic-engineering-platform/.venv/Scripts/python`; `PYTHONPATH=src`.

- Baseline 7be9daaa source archive: four import/chunk tests fail; all six original two-PC race cases fail. New duplicate-reference and stale-review cases were also observed red before their fixes.
- `python -m pytest tests/test_bi_same_card.py tests/test_bi_extract.py tests/test_bi_cards.py tests/test_bi_vault.py tests/test_bi_accept_evidence.py tests/test_bi_replaced_evidence.py tests/test_bi_correction.py tests/test_bi_share_step.py tests/test_bi_card_model_shape.py tests/test_bi_feed_fixtures.py tests/test_bi_feed_api.py tests/test_bi_feed_server.py tests/test_knowledge_repo.py tests/test_knowledge_repo_wiki.py -q --basetemp .scratch/same-card-verified`: 228 passed (before the final reference/delta and upgrade-opening additions).
- Latest evidence/sync group: `python -m pytest tests/test_bi_same_card.py tests/test_bi_accept_evidence.py tests/test_bi_replaced_evidence.py tests/test_bi_correction.py tests/test_bi_vault.py tests/test_bi_share_step.py -q --basetemp .scratch/same-card-dedup-final`: 109 passed.
- Latest `python -m pytest tests/test_bi_same_card.py -q --basetemp .scratch/same-card-commit-check`: 25 passed, including complete SQL iterdump byte comparison (all tables and sqlite_sequence), visible push rebases and delayed arrivals, immutable input operations, old sequential commits, old ambiguous evidence, reference deduplication, stale-review preservation and opening an old materialization.
- `python -m ruff format --check src tests`, `python -m ruff check src tests`, `python -m mypy src tests`: passed; mypy checked 1047 source files.
- Feed fixtures and goldens are unchanged. The baseline validator was also run against an op with the new key: rejects with `op 0: not a unit operation`. Collaborators must use the same release.
- Synthetic copy benchmark: 760 cards, 15,964 units including 7,600 evidence units; forced policy replay 1.461 seconds, exit 0. This measures repository replay only, not BI materialization, and is not a measurement of the owner's real vault.
- No full repository suite or browser run for this backend slice. The release integration/full suite remains with the orchestrator. `graphify update .` was attempted but warned that pypdf was missing and did not finish; interrupted its own process. No tracked graph changes.

## Release-test follow-ups completed

- `2db4fa82`: migrate-domains vault test expects exact content-derived version 5.1.118005 and identical schema refs on both PCs. The direct-dataset 5.1.0 check stays. Complete file: 3 passed, basetemp `.scratch/same-card-migrate-domains`.
- `917e257b`: Atlas answer cites `Feed Fixture Market (fictional)` plus the version, matching 7c6a5e04. Complete file: 54 passed with `AEP_ATLAS_REPO=C:/Users/Chi_L/.paseo/worktrees/09o4151g/atlas-embed`, basetemp `.scratch/same-card-atlas-embed`.
- The last commit updates the F26 follow-up test (3b5c460a): assert readiness, queue/flush hooks and that a non-ready submit queues before clearing the text. Complete `tests/test_agent_web_followups_ui.py`: 6 passed, basetemp `.scratch/same-card-followups-ui`.
- Atlas and follow-up UI browser files ran one at a time. Both completed successfully with their browser fixtures closing normally. No real server restart, real vault access, source-repository change or push.
- Final `ruff format --check src tests`, `ruff check src tests`, `mypy src tests`: pass (1093 formatted files, 1047 mypy files).

## Next actions

1. The orchestrator can integrate the five ordered commits on `bi-same-card` after reviewing `git log`. The branch is based on `7be9daaa`; it was not pushed.
2. Run release-wide integration/full-suite and installer checks on the combined head. This worker's scoped tests pass; the whole repository suite was not run here.
3. The same-file-in-two-homes `source:` folder conflict remains open in TASKS and the design document. Do not describe it as fixed by the same-card field policy.
4. If a graph update is needed, repair the local graphify environment first (its pypdf dependency was missing and the attempted update did not finish). Graph output is local/ignored.
5. Do not access the owner's real vault or push. The BI orchestrator owns release approval and further work.
