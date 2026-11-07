# Windows CI fixes verified on ci-fix

## Scope and integration

Branch ci-fix starts at 4fa5f600 (query implementation e9105373, comparison record 4fa5f600). Do not push. Owner Agent Web and real vault were not used. Fixes address Windows GitHub run 42311321089 on released b1dd4cf8. All local required checks and the full suite passed. The orchestrator should integrate the branch and rerun GitHub Windows verification; no remote CI run was launched for these unpushed commits.

## Commits / causes

| Commit | Change / evidence |
|---|---|
| 28b9150f | BI rename identity: raw timestamp/card-id sorting let a newer card win within the same second. Compare UTC instants, then first deterministic replay position, then id. New same-second regression failed before code; two-PC test freezes commit time; equivalent offsets and reversed unit insertion order covered. MODEL_VERSION 13 -> 14 forces one projection rebuild; immutable units and wiki policy unchanged. |
| 1d7ac809 | Business-card tests: CI crossed UTC midnight 23:21:13Z->00:44:50Z after collecting TODAY/LATER. Advancing edit day reproduced both original failures. A fixed edit day/clock replaces collection-time dates; strict same-day/newer/history/undo assertions remain. Product evidence ordering is unchanged. |
| 334ba3b5 | Vault arrival: automatic scope initialization cleared/replaced the success message. Stronger browser test waited for initialization and failed on the old code. Automatic choice now calls its handler directly, and guidance appends to success. |
| ffe88f4a | Share test: async tag suggestions could change the arranged duplicate name to date-2. Gate the confirmed POST/tag, let a colleague claim the captured name, then release. All step-order/failure/not-published assertions preserved; no share product change. |
| 48083923 | Version-link test: gate benchmark data to arrive last and wait for the same original spatial predicate before asserting it. Focus and commit/push assertions preserved. Exact CI coordinates were not reproduced under controlled response order or CPU6; no speculative product scroll change. |
| 8463c1cb | CI annotation: explicit UTF8 stdout prevents cp1252 failures on Chinese JUnit messages. New forced-legacy-console subprocess test failed before fix and passed afterward. |

CONTRACTS/BI_CARD_MODEL document creation-order ties; DECISIONS records rationale, rejected sleeps/id changes, fixed-day tests, stable feedback and UTF8 annotations. TASKS records completion. Prior review-confirmation flake remains a separate open item; baseline reproduction and six alternating runs are in docs/evaluations/BI_QUERY_OTHER_TYPES_2026-11-07.md.

## Verification

Python: C:/Users/Chi_L/Documents/ChatGPT/agentic-engineering-platform/.venv/Scripts/python; PYTHONPATH=src.

- Core files test_bi_card_rename.py, test_business_cards_new_evidence.py, test_business_cards_store.py, test_ci_annotate.py: UTC: 56 passed in 121.74s; Taipei: 56 passed in 93.87s; final-source Taipei repeat56 passed in 124.34s.
- Browser files each serial, separate basetemp: vault_create UTC: 1 passed in 28.60s/Taipei: 1 passed in 24.44s; share_step UTC: 1 passed in 57.59s/Taipei: 1 passed in 41.38s; version_link UTC: 1 passed in 19.93s/Taipei: 1 passed in 27.08s. Total59 tests per zone including the annotation regression.
- Ruff format --check src tests:1096 already formatted; Ruff check src tests:passed; mypy src tests:1050 files passed. All three also ran under verified UTC and Asia/Taipei process timezones.
- Related tests: test_bi_vault, test_bi_card_model_shape, test_bi_same_card, test_bi_replaced_evidence, test_bi_feed_api, test_bi_feed_server, test_bi_feed_fixtures:91 passed in 917.28s. Feed goldens untouched.
- Correct full suite: 5999 passed,9 skipped, exit 0,9692.84s (2h41m32s). Command: python .scratch/run_module_tz.py UTC pytest -q --tb=short --basetemp C:/Temp/ci-fix-full-final; log .scratch/ci-fix-full.log. AEP_GUI_TESTS=0; optional local Atlas repo used if present. Full suite uses Python process UTC without globally patching browser unit mocks; requested UI files separately use the matching browser timezone.
- Tests first: rename regression 1 failed; advancing edit day 2 failed; cp1252 annotation 1 failed; waiting for vault initialization before success notice 1 failed. No assertions removed or value conditions relaxed.
- Final architecture review: deterministic BI projection remains local and read-only; no new unit fields, external permissions, provider contracts, dependencies or wiki-policy changes. Staged credential scan and diff whitespace checks passed; feed fixture paths absent from changes.

## Reproduction and private artifacts

.scratch/run_pytest_tz.py <UTC|Asia/Taipei> tests/<file>.py -q --tb=short --basetemp C:/Temp/<unique-name> sets process CRT TZ with _putenv_s/_tzset and applies CDP Emulation.setTimezoneOverride to real browser pages. .scratch/run_module_tz.py <zone> <module> <args> does the process-only equivalent for Ruff/mypy/full pytest. Both prepend repo root to sys.path, as python -m does. Actual naive/aware/UTC-to-local offsets were checked as 0/+8; Windows global timezone never changed. These private helpers are not shipped; normal Windows CI already uses UTC. Tests/business_cards_clock.py is the committed fixed-day fixture.

The first full attempt stopped during collection (1 skipped/32errors85.87s) because the private runpy launcher initially omitted repository root, hiding scripts imports. That harness error was corrected before the successful full run; bad log .scratch/ci-fix-full-harness-error.log is retained, not counted as a product regression. Other private logs .scratch/ci-fix-*.log include focused runs and red probes. Original GH failure log .scratch/ci-42311321089-failed.log must never be printed raw: no environment or token values in reports.

All test processes have finished; their fixture servers/browsers closed normally. No persistent temp Web was started. No push/tag/release/restart performed. Remaining external validation: orchestrator reruns GitHub Windows CI after integration, especially original version geometry which was not directly reproduced locally. No further implementation work is pending on this branch.
