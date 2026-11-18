# Baseline failures isolated from Harness work

2026-11-18. The baseline ad532e2db3acd04c11289145665a62353eddcc79 in
`C:/Users/OpenLab/Documents/Codex/2026-11-04/task/aep-inspect` was tested read-only
with the reliability branch's dedicated Python, PYTHONDONTWRITEBYTECODE=1,
`-B -p no:cacheprovider` and temporary fixture roots. PYTHONPATH explicitly named
the baseline's src. No baseline source or real BI vault was changed.

## Long fixture paths

The first full run used the worktree's `.scratch/pytest-full-reliability` base.
Seven test_bi_correction.py cases failed with FileNotFoundError on long synthetic
`knowledge-repos/.../work/files/.../correction-...md` paths. On unchanged baseline,
the long-base group gave 8 failed/31 passed. Using
`C:/tmp/aep-reliability-141/baseline-short-1`, all seven correction cases passed:
the same group gave 2 failed/37 passed. This isolates those seven failures to the
test environment/path length rather than these Harness modifications. Final S2
full-suite execution uses a short base.

## Existing BI findings to keep separate

1. `test_bi_card_rename.py::test_a_rename_and_a_new_card_with_that_name_settle_the_same_on_each_pc`:
   baseline short-path run failed because `kept['id']` was the newly created card
   instead of the expected older card. An earlier baseline run passed. This is
   an observed nondeterministic test result, not a confirmed root cause; timestamp
   precision/ordering is only a hypothesis. Do not change merge semantics here.
2. `test_bi_r6_page_fixes.py::test_a_folder_in_another_home_is_refused_and_none_means_the_sources_own`:
   unchanged baseline reproduces IndexError at model.requests[0]; no model request
   was recorded where the test expected one. Cache/profile behavior needs the BI
   owner's investigation; no cause is assumed or BI source modified.
3. `test_bi_build_flow_ui.py::test_the_whole_build_flow`: unchanged baseline,
   short temporary path, real headless browser: failed in 249.78 seconds. The
   result remained in the method stage with zero candidates, cached answer and
   a message saying no profile applied. There were no open/failed network
   requests or page errors in the reported browser diagnostics. This is evidence
   of the baseline test failure, not proof of a particular BI defect.

Machine logs (ignored): `.scratch/pytest-baseline-bi.log`,
`.scratch/pytest-baseline-bi-short.log`, `.scratch/pytest-baseline-ui.log`.
These findings should be handed to the separate BI Knowledge work rather than
fixed inside the reliability branch. No full-suite pass is claimed with them.
