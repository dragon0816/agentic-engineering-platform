# Handoff

Date: 2026-10-03 (Asia/Taipei). Branch: `main`. No push or TypeSafe request
was made in this checkpoint. `docs/TASKS.md` remains the cumulative progress
record; `docs/DECISIONS.md` holds the architecture decisions.

## Latest checkpoint: local Laya comparison preparation

- The owner selected `NandhaKishorM/laya`, not the same-named notification
  project, and approved an offline decision comparison. Added
  `src/evaluation/laya_offline.py`, its fake-router tests, the design spec and
  a reproducible setup in `evaluation/jev/README.md`. The diagnostic maps all
  four types in the pinned 16-case PUBLIC synthetic corpus to typed `choice`
  questions and preserves the existing NONE baseline. It imports Laya only
  when explicitly run; Agent Web and production routing are unchanged.
- Package version is pinned to 0.3.24. Model input truncation, malformed or
  low-confidence answers abstain. The aggregate report records checkpoint
  revision and warm-up separately from measured latency, without request text.
  Its model-call environment forces Hugging Face offline mode. No real Laya
  checkpoint was run on this computer. At the owner's request, an isolated
  ignored `.scratch/laya-venv` now has Laya 0.3.24 and CPU-only PyTorch 2.7.1;
  memory available after installation was about 5.4 GiB. The company Zscaler
  proxy returned HTTP 403 for the public Hugging Face checkpoint. Windows
  truststore resolved TLS validation but not this block. Offline CLI reports
  `LocalEntryNotFoundError` because the model was not cached. Run the
  documented diagnostic on a machine with permitted model access and enough
  free RAM; no model accuracy or latency number exists yet.
- Focused Laya/JEV tests: 11 passed. Ruff and strict mypy (338 source files)
  passed. The final full non-browser rerun passed: 1,731 passed, 5 platform
  skips, 26 deselected. The first run had one known intermittent Windows
  Extension staging `os.replace` permission failure; that test passed alone
  and in the final complete rerun. `python -m build --wheel --no-isolation`
  passed with a unique output directory; `git diff --check` passed.
- Workflow 11 remains separate unfinished work: the owner wants original
  `rs_workflow_system` statistics, blue chart, GitHub Issue key hyperlinks and
  Issue Assignees. Its source snapshot is pinned at
  `896046e8fe2170d21f9213e56e5ce2f93c05ba43d`; use original scripts as
  the baseline. The current code already pulls Issue URL and assignees for
  mail statistics, but workbook Assignee still uses the Project's `SDE
  Assignee` field. This shell's GitHub tokens cannot jointly read the Project
  and Issue content, so no live parity claim is justified. Do not request the
  owner's LiteLLM key again; this Laya slice does not use it.

## Current owner direction

- The previous Agent Web context/session Settings slice is complete. Context
  limits and existing session records are configurable; cross-session memory
  was deferred by the owner. The preview is still running on `127.0.0.1:53582`.
- Make RS_Knowledge asking useful and verify answer quality before comparing
  TypeSafe JEV. The owner classified this complete Vault `public` in its exact
  Host binding, while other Vaults default to `private` and are owner-editable.
- For this round, the owner chose a **local Laya offline decision comparison**
  in place of a TypeSafe call. The TypeSafe adapter remains unwired to Agent
  Web; neither decision model is a Knowledge answer generator.
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
  live answer has not yet been tested**. A prior source-runtime attempt
  returned `knowledge_model_failed` because that process did not inherit the
  LiteLLM credential; the already-running Web process did answer with its own
  credential. The owner has since confirmed the key was set. Check the actual
  test process's inherited environment instead of asking for the key again.

## JEV offline result

- Reran `evaluation.jev_benchmark` on the pinned 16-case PUBLIC synthetic
  corpus. The unchanged `NONE` Skill baseline returned candidates for 4/4
  cases and matched the exact expected set in 1/4. Intent, retrieval and
  failure classification have no baseline and remain `unavailable`.
- No TypeSafe request or cost estimate was made. The owner superseded the
  pending live TypeSafe comparison with the local Laya benchmark preparation.

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

Run the documented Laya benchmark on a computer with sufficient free RAM,
then compare its per-type results with the unchanged NONE baseline. In parallel,
refresh the installed preview from the verified offline wheel and retest the
exact Knowledge market question through the running Web process; that post-fix
live answer is still unverified. Do not ask the owner to re-enter the LiteLLM
key; inspect the environment of the process doing the test. Workflow 11 visual
parity, Workflow 10/13 source parity and other open work remain in
`docs/TASKS.md`.
