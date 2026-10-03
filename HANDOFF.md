# Handoff

Date: 2026-10-03 (Asia/Taipei). Branch: `main`. No push or TypeSafe request
was made in this checkpoint. `docs/TASKS.md` remains the cumulative progress
record; `docs/DECISIONS.md` holds the architecture decisions.

## Current owner direction

- The previous Agent Web context/session Settings slice is complete. Context
  limits and existing session records are configurable; cross-session memory
  was deferred by the owner. The preview is still running on `127.0.0.1:53582`.
- Make RS_Knowledge asking useful and verify answer quality before comparing
  TypeSafe JEV. The owner classified this complete Vault `public` in its exact
  Host binding, while other Vaults default to `private` and are owner-editable.
- For this round, the owner explicitly chose **offline-only JEV validation**.
  Do not call TypeSafe yet. The official TypeSafe adapter is a bounded Skill
  selector, not a Knowledge answer generator, and remains unwired to Agent Web.
- n8n is not a required development item. Migrate remaining proven Workflow
  jobs by reuse or a thin Bridge wrapper first. Workflow 7 remains paused.

## Knowledge source-backed evaluation slice

- Added `evaluation/knowledge/rs-market-v1.json` with SHA-256 pins and exact
  text anchors for the staged Vault's market note, CMX500/CMX-B200A
  specification and SMBV100B specification. The market note names
  800G/1.6T; the product excerpts establish digital I/Q or RF wireless
  capability, not 800G/1.6T qualification. The source files remain outside
  the repository and unchanged.
- Added `evaluation.knowledge_market` and regression tests. The read-only CLI
  verifies pinned Raw bytes and retrieval, and can inspect a saved
  `KnowledgeAnswerRecord`. It flags a narrow affirmative product-to-market
  link without one reviewed cited Raw passage naming both. It always reports
  `semantic_entailment_proven: false`; clean output still needs human review.
- The installed Agent Web returned an `answered` record for the owner's exact
  high-speed-market question. It cited the three expected Raw sources but
  claimed the products could directly address the 800G/1.6T market. The new
  diagnostic correctly marked two linked assertions `failed`. The record is
  kept only in ignored `.scratch/market-live-record.json`, not committed.
- `QueryEngine` now adds market-fit guidance to broad Raw-only market answers
  and, on an affirmative product-to-rate assertion supported only by separate
  market and product sources, retries once and then refuses the assertion.
  The regression proves an overclaim is retried/refused and a qualified answer
  can pass. This is deliberately a narrow lexical safeguard, not full semantic
  entailment. See the new decision in `docs/DECISIONS.md`.
- The running preview still has the prior installed wheel, so its **post-fix
  live answer has not yet been tested**. A standalone source-runtime attempt
  returned `knowledge_model_failed` because this shell does not have
  `LITELLM_MASTER_KEY` in User/Process environment; the already-running Web
  process did successfully answer with its existing credential. Do not claim
  the new prompt has live model parity until preview refresh/retest.

## JEV offline result

- Reran `evaluation.jev_benchmark` on the pinned 16-case PUBLIC synthetic
  corpus. The unchanged `NONE` Skill baseline returned candidates for 4/4
  cases and matched the exact expected set in 1/4. Intent, retrieval and
  failure classification have no baseline and remain `unavailable`.
- No TypeSafe request or cost estimate was made. `AEP_JEV_API_KEY` is absent
  from this Host's User environment, and the owner chose offline-only testing
  for this round. Keep the TypeSafe comparison task open.

## Verification and known limits

- Focused Knowledge tests: 18 passed. Full non-browser suite, using the
  normal Windows temp directory: **1,727 passed, 5 platform skips, 1 CDP
  browser test deselected**. Two preceding complete runs encountered the
  known intermittent Windows `os.replace` permission failure in unrelated
  Extension staging fixtures; those three affected tests passed in isolation
  and the final complete rerun passed. Do not attribute that flake to this
  Knowledge change.
- `ruff check src tests`, strict `mypy src tests` (336 files), offline wheel
  build and `git diff --check` passed. The CDP browser test was not run because
  its Chromium WebSocket closes on this Host.
- The source-backed diagnostic against the actual staged Vault verified all
  three Raw hashes/anchors and retrieved 3/3 expected sources. With the saved
  pre-fix live answer, it exited failed with two unsupported market links.

## Next action

Refresh the installed preview from the verified offline wheel, restart its
Web process with a valid LiteLLM credential, and ask the exact market question
again. Save its `KnowledgeAnswerRecord` locally, run the pinned source-backed
diagnostic and review each claim/citation manually. If the model still makes
the market leap, improve the bounded retry or report `knowledge_not_grounded`
without inventing fit. Keep TypeSafe offline until the owner changes that
preference and supplies its key. Workflow 10/13 parity and other open work
remain in `docs/TASKS.md`.
