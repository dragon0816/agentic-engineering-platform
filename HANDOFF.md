# BI query complete; pre-existing review UI failure measured

Branch `bi-query-other-types`, base `b1dd4cf8`. Do not push. Owner/orchestrator approved count-only cross-filter hints, widening guidance, bounded matched body snippets, stub and real-model validation. No real vault or owner Web used.

## Implemented and verified

- service.query_cards keeps requested rows/total/limit unchanged; scope_note counts exact word matches excluded by active type/domain/field/value filters in the same store/version, groups other types/domains and tells the model to retry without filters. No extra card entries/links/evidence in the hint. No hint for no text/no filter/no excluded exact match.
- Only returned schema-visible bodies with a query-word match can emit body_snippet (field=body, text<=300 including ellipses, source=kind:ref), retaining card citation/sample/trust flags. Full fields.body remains excluded. Host approval gates every known source class; unresolved evidence IDs withhold the snippet, staged filename matches also use their classes, no source classification defaults to INTERNAL. No unknown approval. Staging.source_classes reads only id/name/classification in one metadata query.
- Chosen-version reading_tool inherits the installed query handler's host approval. It still reads the chosen store; raw passage rules unchanged. Widening instructions are in fresh tool descriptions, shipped Skill text and benchmark role, with a cross-type calibration example in question-generation guidance.
- New fictional regression tests include a real vault/stub harness starting with SupplyLink, following the hint, reading CustomerProduct body before answering; counts/limits, matched-only/bounded snippets, class gates, published-version isolation and sample flags.
- CONTRACTS/DECISIONS updated; evaluation report committed with eventual change. No persisted model version/commit changes, no new dependency, no feed golden edit.

Focused tests passed (PYTHONPATH=src, shared Python at C:/Users/Chi_L/Documents/ChatGPT/agentic-engineering-platform/.venv/Scripts/python):
- test_bi_query_other_types.py: 7 passed (C:/Temp/bi-other-types-unit-final)
- test_bi_query_retrieval.py, test_bi_query_analyses.py, test_bi_vault_bench.py: 33 passed (C:/Temp/bi-other-types-core-final)
- test_bi_cards.py, test_bi_feed_api.py, test_bi_feed_server.py, test_bi_feed_fixtures.py: 54 passed (C:/Temp/bi-other-types-feed)
- test_vault_asking_e2e.py: 6 passed (C:/Temp/bi-other-types-vault-asking)
- test_assistant_bi_query.py: 11 passed (C:/Temp/bi-other-types-assistant)
- test_bi_questions_session.py: 5 passed (C:/Temp/bi-other-types-questions)
- Browser-bearing files ran one at a time. Requested Ruff format --check src tests (1094 files), Ruff check src tests, mypy src tests (1048 files): passed. git diff --check passed after normalizing appended Markdown newlines.
- Tests first: 5 feature regressions failed on the base; the approval-negative case already passed. Initial fixture keyword/frozen-row mistakes were corrected without weakening assertions.

## Real model evidence

Private fictional SOP workspace copied to C:/Temp/bi-query-other-types/workspace. Script .scratch/bi_other_types_real.py; per-turn output before.json/after.json in that private root. No secret printed. Probe 2.0s/2.4s, no hang; gpt-5.5, exact question BW-200 的校準週期是多少？, five independent harness turns each, same copy/config. Before 0/5, tool calls [2,1,1,1,1]; after 5/5, [1,1,1,1,1]. All five positive answers read, affirm six months and cite the CustomerProduct card. This run's before model already queried all types, so body omission was independently causal; it does not isolate the count hint's effect. The stub exercises the filtered retry. Public reproducible description: docs/evaluations/BI_QUERY_OTHER_TYPES_2026-11-07.md.

## Full suite and completed comparison

Full suite: 5994 passed, 9 skipped, 2 failed in 6761.26s (C:/Temp/bi-other-types-full). This is not an all-green run. Failures:
- test_bi_review_table_ui.py::test_accepting_a_proposal_shows_what_it_loses_and_then_that_it_was_done: line 703, second confirmation click, BrowserError navigation_failed (JS exception).
- test_bi_sessions_ui.py::test_session_panels_in_a_browser: waiting for method revision 2. Whole file isolated: 1 passed (19.67s).

Review table whole-file isolated on this branch: 10 passed/1 failed (320.93s), then 10 passed/1 failed (248.24s), same case/error. That case alone: 1 passed (27.71s). Baseline b1dd4cf8 whole file: 11 passed (355.15s). These counts do not yet establish whether this is pre-existing. No UI/test assertion changes made. Baseline temporary worktree was removed after that run.

Query implementation commit: e9105373. Orchestrator requested committing first, then three more whole-file runs per version, alternating and serial, with the same temporary diagnostic plugin. Completed order/results:

| Run | Result | Seconds |
|---|---|---:|
| branch-1 | 11 passed | 281.18 |
| b1dd4cf8 base-1 | 11 passed | 279.81 |
| branch-2 | 11 passed | 321.04 |
| b1dd4cf8 base-2 | 11 passed | 397.85 |
| branch-3 | 11 passed | 586.50 |
| b1dd4cf8 base-3 | 10 passed, 1 failed | 500.60 |

New comparison failure counts: branch 0/3, baseline 1/3. Including preceding isolated whole-file runs: branch 2/5, baseline 1/4; full-suite failure is separate. Baseline base-3 failed at the exact same test and line 703. DevTools exceptionDetails captured without re-executing the expression: `TypeError: Cannot read properties of undefined (reading 'click')` at `<anonymous>:1:180`. The selector finds the FAKE-040 proposal row, then a button containing the explicit replacement confirmation label; that button is undefined at the click. This proves the UI failure exists before the query change, but does not establish equal failure rates or the exact refresh/race mechanism. No UI/test assertions changed.

Private reproducible artifacts: C:/Temp/bi-query-diagnostics (run_comparison.py, bi_js_diagnostics.py, six logs, base-3.jsonl, verified-results.json). Plugin only observes the original Runtime.evaluate response and records exception details for this test, with sensitive values redacted; it never repeats an expression or changes the response. All six runs used the same plugin and unique C:/Temp/bi-other-types-{branch,base}-{1,2,3} basetemps. Baseline detached worktree is removed after comparison; test fixture servers/browsers have ended.

Follow-up: separately fix the pre-existing review confirmation UI failure, preserving the second explicit press and strict assertions. This task does not include that UI change. Do not describe the original full suite as green; the final branch review file and sessions file do pass in isolation, and the baseline failure remains tracked in TASKS.

Final diff architecture review and staged credential/feed-path scan passed. Requested CI/focused 116 all passed. No actual release/tag/push. Real-check runtime contexts closed; no temp Web server was started for the real-model task. Test fixtures close their own servers/browsers.
