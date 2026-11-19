# Handoff

## Harness reliability on 141 — implementation checkpoint (2026-11-18)

- Worktree: C:/Users/OpenLab/Documents/workspace/aep-harness-reliability-141.
- Branch: harness/reliability-141; base ad532e2db3acd04c11289145665a62353eddcc79.
- User authorized implementation/testing. BI worktrees/vaults stay separate. No push, PR, merge or deployment.
- Read docs/proposals/harness-reliability/slice-1-design.md and slice-1-results.md.
- Implemented narrow task failure propagation retaining validated evidence, RunPython/Harness mapping, direct refusal/failure rendering and MCP error diagnosis.
- CLI non-success exit behavior is already fixed here. Older cd19a5b review inventory is not this baseline; current native loops, model author, telemetry and completion contracts already exist.
- Existing result wire-schema, permissions, framework and retry budgets are preserved; BI logic is unchanged.
- Final new regression file: 12 passed, including a real Windows restricted exit-1/no-Excel case. Earlier focused group 101 passed; restricted group 29 passed/1 skipped. Ruff lint/format, mypy (977 files), build, pip check and diff whitespace passed.
- First full S1 pytest: 5298 passed, 35 skipped, 10 BI failures. Seven long-path fixtures pass with a short base; remaining three failures reproduce on unchanged baseline. Final S2 full pytest completed 2026-11-19: 5315 passed, 35 skipped, 4 failed in 1723.74 s; .scratch/pytest-final-s2.log/xml. Three baseline BI failures and one obsolete schema assertion; see slice-2-results.md. No full-suite pass claimed.
- This local reliability-branch commit preserves implementation, tests and evidence with known baseline failures documented. Do not report the entire reliability program complete.
- Scratch experiment .scratch/timeout-ownership-repro.py reproduced two simultaneous untracked workers. The owner selected durable resource claims until confirmed finality; see slice-2-design.md and slice-2-results.md.
- Slice 2 implemented: existing SqliteLocalState schema 7, worker-owned completion, timeout/cancellation unknown state, conflicting workspace exclusion, explicit existing stopped confirmation, operations/reconcile-operation CLI. Python/CodingHarness adapters opt in; other handlers are not globally covered. No automatic retry or lease expiry.
- Slice 2 focused group: 105 passed/1 skipped; final ownership/reporting files: 22 passed including actual restricted-process timeout, rejected replay and exactly one scratch effect. Ruff/format (1319 files), mypy (980), build and pip check passed.
- Final full run also exposed test_portable_task's obsolete expected schema 6. Updated only that assertion to 7; fresh migration/ownership/reporting/host group: 56 passed in 5.47 s, Ruff and mypy passed again. Full raw result must still include this observed assertion failure; do not claim a clean full rerun after the test-only correction.
- Live gpt-5.6 native-loop controlled Excel trial: 3 model turns, 2 workers, injected real exit-1 failure followed by completion, independent workbook oracle passed. See controlled-excel-benchmark.md. Separate wrong-column Excel control passes existing generic checks but fails independent oracle; generic Excel semantics remain unverified.
- Owner supplied direction instead of historical private SAP input: build a fictional browser SAP OI case, preserve SOP/dialogue/generation evidence. Added benchmarks/harness_reliability_sap_oi with native browser/download/Python loop and benchmark-only typed exporter, sealed oracle and native pivot packaging. No src or BI edits in this slice.
- Final run6: gpt-5.6, 10 model turns/9 tools, 16 CSV rows ->12 valid details, TWD13580, actual normalization exit1 repaired by model, exporter+artifact+task acceptance passed. Excel Desktop is absent; open/refresh/recalc remains unverified. See benchmark RESULTS.md and outputs/harness-sap-oi-20261119/process-report.md.
- Artifact native export/import/render repeatedly crashed 0xC0000409 in this environment; final fallback uses installed openpyxl + narrow OOXML. Failed prototypes and all six raw attempts are preserved in full-review.zip. Run4 old report had artifact-only false-success aggregation; original frozen, explicitly superseded and negative-tested. Run6 reran corrected acceptance.
- New benchmark focused set 38 passed; Ruff lint/format1329, mypy981 passed. Existing ownership test helper default changed30ms->2s to avoid deadline races in non-timeout assertions; timeout-specific tests still use explicit short deadlines. No production timeout change. No new full-suite run.
- Deliver owner final Excel, SOP, dialogue and full review ZIP; next action is owner/company-PC Excel open/Refresh All acceptance, then authorized real SAP SOP parity. Do not claim original historical root cause or universal SOP/Excel capability. Keep BI separate; no push, PR, merge or deployment.
- Dedicated .venv and ignored .scratch only. Gateway http://172.25.228.59:4000/v1, model gpt-5.6. Credential via private delivery/environment; never persist its value or private file path in Git.
- Baseline BI/R6 handoff remains in Git history; no other checkout's HANDOFF changed.

- Owner restriction (2026-11-19): all 141 reliability tests must keep Telegram off. Do not load daily host config/copy telegram.json/start polling. Benchmark entry clears only its own TELEGRAM_*/AEP_TELEGRAM_* environment; no persistent tokens/services changed. Inspection found no active reliability process or Telegram config in test/preview workspace. Existing evidence ZIP remains frozen; see 141-test-environment.md.
- Telegram isolation verification: 13 benchmark tests passed; Ruff and mypy src/tests passed. No live model/bot calls were made for this change.
