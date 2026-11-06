# Handoff

Updated 2026-11-06 by the same-card regression worker. No push, real vault access, server restart or installer action.

## Goal and branch

Branch `bi-same-card-fix`, based on `3167044b`, in `C:/Users/Chi_L/.paseo/worktrees/2qnenase/bi-share-step`.
The BI orchestrator reported 5939 passes and four failures on that main; two passed alone under less load, while the summary-chunk and coverage-golden failures reproduced alone. This branch fixes those two regressions without changing any golden.

## Changes and decisions

- `24a94a01`: within one extraction run, inferred summary/usage/scope variants keep the first reading, retain the other with evidence as an alternative, and do not emit value_conflict. Normal chunking should not alarm. Sourced summary facts and ordinary fields still warn. Tests cover all three reading fields, retained evidence and sourced/ordinary conflicts.
- Timestamp correction: use one UTC instant comparison for updated-field maxima, duplicate reference times and derived card.updated. Date-only/naive dates compare in UTC on every PC; undated legacy text ranks below valid times. Field/reference ties still use canonical JSON. A derived card timestamp takes history's representation when instants tie, preserving legacy formatting.
- Replay policy 2 and MODEL_VERSION 13 cause one correction replay/rebuild. Existing commits are immutable and the evidence-operation context format is unchanged. Decision and contract details are in docs/DECISIONS.md, docs/CONTRACTS.md and docs/phases/BI_CARD_MODEL.md.

## Exact coverage difference and resolution

Only four coverage latest-update strings changed on 3167044b:

| Cell | Count, unchanged |
|---|---:|
| aidc-computing / high-speed-io | 1 |
| aidc-power / rf | 1 |
| aidc-power / power-generic-io | 3 |
| aidc-power / emc | 1 |

The golden value `2026-11-01T01:00:00+00:00` became `2026-11-01T09:00:00+08:00`: exactly the same instant. Lexical max had let commit.created's local offset text beat history.at's UTC text. Coverage ratios, counts and missing-field descriptions did not change. The correct fix is chronological comparison and history formatting on equality, not a new analysis answer. Every feed/default-pack golden remains untouched.

## Verification

Interpreter: `C:/Users/Chi_L/Documents/ChatGPT/agentic-engineering-platform/.venv/Scripts/python`; PYTHONPATH=src.

- Before implementation: both reported failing files reproduced 2 failed / 11 passed; four new cross-offset chronology/equal-instant tests reproduced four failures.
- `python -m pytest tests/test_bi_card_summaries.py tests/test_bi_same_card.py tests/test_bi_pack_chains.py tests/test_bi_default_pack.py tests/test_bi_feed_fixtures.py tests/test_bi_feed_api.py tests/test_bi_feed_server.py -q --basetemp .scratch/same-card-fix-final`: 69 passed.
- After the final extra sourced-summary and duplicate-reference timezone cases, `python -m pytest tests/test_bi_card_summaries.py tests/test_bi_same_card.py -q --basetemp .scratch/same-card-fix-complete`: 45 passed.
- All files matching test_bi_pack_* are included (currently test_bi_pack_chains.py); test_bi_default_pack.py additionally checks the pack's other fixtures.
- `python -m ruff check .`, `python -m ruff format --check .`, `python -m mypy`: passed; mypy checked 1047 source files.
- `python -m pip check`: passed, no broken requirements.
- `python -m build --no-isolation --outdir .scratch/same-card-fix-dist`: successfully built the sdist and wheel. The final wheel-only rebuild passed; all four changed source modules inside the wheel match the final worktree byte for byte.
- No golden files changed. No browser files touched or browser tests required for this slice. No complete repository suite rerun or Windows installer/preview build here; release-wide integration remains with the orchestrator.

## Next actions

1. Both fixes are committed on bi-same-card-fix (first 24a94a01 for quiet chunk alternatives, then the timestamp correction carrying this handoff). Review git log for their hashes and report to BI orchestrator agent 1c2694f9-300d-4869-998b-4d33e40561e1.
2. The orchestrator integrates this branch and runs final combined-head/full-suite and installer checks. Do not push or access the owner's real vault.
3. The separate same-file-in-two-homes source.folder conflict remains open in TASKS; this patch does not claim to fix it.
