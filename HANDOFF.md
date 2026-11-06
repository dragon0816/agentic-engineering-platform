# Handoff

Updated 2026-11-06 by the Codex same-card worker. This is the worker branch handoff, not a release authorization. The BI orchestrator owns integration, installer checks and publishing. Do not push.

## Goal and branch

Worktree: `C:/Users/Chi_L/.paseo/worktrees/2qnenase/bi-share-step`.
Branch: `bi-same-card`, based on local main `7be9daaa` at the orchestrator's request.
Implement the owner's same-card rule before release, then repair three outdated tests assigned by the orchestrator. Never access the owner's real vault. All work so far used synthetic data and temporary workspaces.

## Completed

- `398dbad2`: independently fix the pre-existing card-model-shape staging test to the F19 import-isolation rule. It fails unchanged against 7be9daaa; after the fix all 20 tests in the file pass.
- Same-card implementation: store fill-only summary/usage/scope; extraction alternatives retain evidence; one BI operation projection for push, sync, state_at, log and pushed share replay. Wiki does not opt in. New evidence ops carry optional validated context; appends merge only their new rows, preserving concurrent evidence review. Reference identity deduplicates rows; later reference time then canonical JSON is the deterministic tie-break. Stale evidence against a replaced value conflicts. Ambiguous old operations keep existing conflict handling.
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

## Next actions

1. Commit the verified same-card implementation on this branch (if it is not already in git log).
2. As separate commits, repair and run each complete file requested by the orchestrator:
   - `tests/test_bi_migrate_domains.py`: vault migration uses a content-derived schema version (BI_CARD_MODEL section 4.3), not 5.1.0.
   - `tests/test_bi_atlas_embed.py`: citations name the vault title, per 7c6a5e04. Run with `AEP_ATLAS_REPO=C:/Users/Chi_L/.paseo/worktrees/09o4151g/atlas-embed`.
   - `tests/test_agent_web_followups_ui.py`: F26 (3b5c460a) queues early messages; assert the readiness and queue/flush hooks rather than the retired early-return condition.
3. Browser files run one at a time with this worker's own basetemp; close browsers started by the tests. Report commit hashes and exact results to orchestrator agent `1c2694f9-300d-4869-998b-4d33e40561e1` using Paseo send_agent_prompt. Do not push or modify any source repository or real vault.
