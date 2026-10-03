# Handoff

Date: 2026-10-03 (Asia/Taipei). Branch: `main`. No push or TypeSafe request
was made in this checkpoint. `docs/TASKS.md` remains the cumulative progress
record; `docs/DECISIONS.md` holds the architecture decisions.

## Latest checkpoint: Workflow 11 source-style chart and Issue identity

- The owner asked to continue development after the local Laya checkpoint
  download was denied by Zscaler. The next independent slice uses the pinned
  `rs_workflow_system@896046e8fe2170d21f9213e56e5ce2f93c05ba43d`
  Workflow 11 mail renderer as the baseline; see
  `docs/superpowers/specs/2026-10-03-workflow11-source-chart-parity.md`.
- `weekly_report.chart.composite_for` now draws the original one-image
  instrument pie and stacked bars per member using AEP's existing counted
  GitHub Issue assignees and comma-split Project Production. The original
  seven blue shades are retained; additional instruments remain blue and are
  not folded into `Other`. The mail keeps its HTML totals when images are
  blocked. A rendered sample was inspected at ignored
  `.scratch/workflow11-composite-preview-final.png` (integer x-axis ticks).
- The workbook Assignee value now joins the Issue's assignees instead of
  preferring the Project's free-text `SDE Assignee`. Empty Issue connections
  stay empty/Unassigned; Key hyperlinks retain GitHub Issue URLs. Existing
  project-read contract already refuses omitted or truncated Issue assignee
  connections.
- Matplotlib, NumPy and their transitive wheels are an optional `weekly-mail`
  extra carried by the Windows offline preview. A real wheel and offline
  bundle were built in ignored `.scratch/wf11-wheel` and
  `.scratch/wf11-preview-bundle-closed`; bundle revision is the pre-commit
  HEAD. A real offline installation into ignored `.scratch/wf11-offline-env`
  succeeded, and Matplotlib, NumPy, tzdata, pywin32 and openpyxl imported with
  `pip check` clean. The first dry-run caught a pre-existing missing `tzdata`
  wheel in the preview manifest; it is now required and downloaded by CI.
  Focused tests: 49 passed; the amended bundle tests: 8 passed. Ruff, strict
  mypy (338 files), and `pip check` passed. The full non-browser suite passed:
  1,733 passed, 5 platform skips, 26 browser deselections. Its first run hit
  an unrelated intermittent Windows Knowledge `os.replace` permission error;
  that test passed alone and the clean full rerun passed.
- Live parity remains open: compare a newly saved Outlook draft with the
  owner's reference and inspect an isolated copy of the real workbook. This
  shell cannot jointly read the company GitHub Project and Issue content, so
  no live-source assertion has been made. Do not send the draft or mutate the
  production workbook just to close this test.

## Previous checkpoint: local Laya comparison preparation

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
- At the previous checkpoint, Workflow 11 remained separate unfinished work: the owner wanted original
  `rs_workflow_system` statistics, blue chart, GitHub Issue key hyperlinks and
  Issue Assignees. Its source snapshot is pinned at
  `896046e8fe2170d21f9213e56e5ce2f93c05ba43d`; use original scripts as
  the baseline. The current code already pulls Issue URL and assignees for
  mail statistics, but workbook Assignee still used the Project's `SDE
  Assignee` field. The latest checkpoint above changes that mapping. This shell's GitHub tokens cannot jointly read the Project
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

Commit and review the Workflow 11 chart/identity slice, then refresh a test
Agent preview from the verified offline wheel and compare a new unsent Outlook
draft and workbook copy with the owner's source reference. Do not claim live
parity from synthetic tests alone. Run the documented Laya benchmark on a
computer with sufficient free RAM and permitted model access, then compare
its per-type results with the unchanged NONE baseline. The exact Knowledge
market question's post-fix live answer remains unverified. Do not ask the
owner to re-enter the LiteLLM key; inspect the environment of the process
doing the test. Workflow 10/13 source parity and other open work remain in
`docs/TASKS.md`.
