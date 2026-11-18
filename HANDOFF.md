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
- Next action: obtain original SOP/template/Excel calculation rules (requested asynchronously) before designing the mandatory artifact-check binding. This is the tested direction boundary: a wrong-column workbook passes current generic action/file checks, so business correctness cannot be inferred from exit 0/nonempty output. Parallel BI work remains separate; its three baseline failures are recorded for that owner.
- Dedicated .venv and ignored .scratch only. Gateway http://172.25.228.59:4000/v1, model gpt-5.6. Credential via private delivery/environment; never persist its value or private file path in Git.
- Baseline BI/R6 handoff remains in Git history; no other checkout's HANDOFF changed.
