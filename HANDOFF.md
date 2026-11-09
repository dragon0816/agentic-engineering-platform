# C4C live Workflow validation — 2026-11-09

## Goal and branch

Continue the owner-approved PDF/XLSX/DOCX SOP authoring and reply numbering work
(commits 59320b68 and 77f5477e on main) with a real automatic C4C run. The owner
confirmed SSO and explicitly requested execution. Final TWD rate is 0.02712085
EUR/TWD (the later explicit yes supersedes the earlier pending clarification).

## Completed

- Browser trusted pointer press/release, hidden-target filtering and role=option
  labels; origin/read-mode checks precede pointer dispatch.
- Optional split header selector, typed bounded pagination, stable page snapshots
  and unique key columns. Frozen SAP ID cells lag the other cells; changing rows
  alone is insufficient. Limits/stalls refuse without partial exports.
- Bounded wait_for target/text regex action. C4C retains old tables/page counts
  during queries; the recorded procedure awaits loading and numeric completion.
- Actual SSO and All / Document Date Between 01.07.2026 and 30.06.2027 query,
  all pages, restricted Python and Excel executed through WorkflowEngine,
  Bridge and the shared Workflow Harness. No SAP HTTP/API or application state.
- The installed network-blocked runner Python (openpyxl 3.1.5) is used with its
  existing firewall requirement and allowed Documents/aep-workflows root.
- Independent verification: 750 raw rows match browser output, 750 unique IDs,
  all dates in range, all EUR conversions, all 106 monthly groups and all mapped
  departments reconcile. 173 rows have no matching Owner in the supplied lookup;
  originals/totals remain and Exceptions identifies them. No guessed departments.
- Actual view has no Export/Spreadsheet button. SOP says copy its table, so the
  Workflow reads the visible table into Excel rather than inventing an Export.

## Private artifacts and replay

User package: %USERPROFILE%/Documents/aep-workflows/c4c-sales-order-report/.
workflow.json contains the deterministic steps/scripts; input/ contains the
unchanged owner lookup; output/c4c_sales_orders_fy2026_analysis.xlsx contains raw,
EUR detail, monthly summary and exceptions. These business files are not in Git.
The unused draft output_basename parameter was removed; output filename is fixed.

Private .scratch/run_c4c_workflow.py rebuilds/checks and executes the manifest;
.scratch/verify_c4c_live.py independently verifies the result/workbook. Evidence:
.scratch/c4c-live-validation/workflow-run.json and independent-verification.json.
Final successful live run: run-e390791473b84a95af7cbb43b6bfa923.
The private browser is closed. Resident AEP config/service/workspace are untouched;
no update/restart/install/publish/push was performed. Source features require an
updated Host before this manifest can be installed into the resident service.

## Final verification

- Browser, web-script and session whole files: 39 passed in 262.65s.
- Authoring conversation and Workflow preview whole files: 8 passed in 55.74s.
- Final independent workbook/source/mapping/aggregate check passed.
- Ruff check ., Ruff format --check . (1398 files), mypy src tests (1052 files)
  passed. build --no-isolation produced sdist/wheel; pip check passed.
- Full suite: .scratch/run_c4c_suite.py, four disjoint file sets from normal
  collection, 6026 items/524 modules, AEP_GUI_TESTS=0. Initial 6013 passed,
  10 skipped, 3 failed (no errors); optional av also skips collection. Shards:
  1453 passed/2 skipped (4197.81s); 1402/2 +1 fail (2547.37s);
  1631/5 +1 fail (2864.71s); 1527/1 +1 fail (4353.56s).
- All initial failures inspected and unchanged whole modules rerun successfully:
  test_script_tools.py 6 passed in 12.38s (initial script_timeout);
  test_library_content_web.py 6 passed in 95.95s (initial wide layout measured
  narrow; same failure occurred before this change in the document full run);
  test_web_capabilities.py 4 passed in 45.25s (profile_in_use while asserting
  origin refusal). No weakened assertion, enlarged timeout or speculative fix.
  Do not claim the original full command was first-pass green.
- Final normal collection 6028/524; original case multiplicities preserved, only
  two later readiness/frozen-key regressions added, both in final 39-test pass.
  .scratch/c4c-coverage-delta.json verifies this without dynamic token labels.
  c4c-shard-N.log/.xml and c4c-suite-result.json preserve original outcomes.
- Final diff architecture guard: pass, unchanged authorization/plane boundaries;
  no SAP-specific core routing or provider details, no secrets/new dependency.
  All test/build/private browser processes completed. No push.

## Remaining / next action

The source change and live acceptance are complete, with the concurrent full-run
failures transparently reconciled above. Before enabling this saved manifest in
the resident AEP, update the Host through the normal active-work/restart policy
and install through its approval flow. Neither is performed by this source-only
verification. The owner may extend the supplied lookup for the 173 unmapped rows
and rerun; no Workflow rebuild is needed.

Architecture decision: docs/DECISIONS.md; typed contract: docs/CONTRACTS.md;
phase: docs/phases/C4C_LIVE_WORKFLOW_VALIDATION.md; detailed evidence:
docs/evaluations/C4C_LIVE_WORKFLOW_2026-11-09.md. Earlier attachment/numbering
acceptance remains in CHAT_DOCUMENT_ATTACHMENTS_2026-11-09.md and the two commits
named above. Next deployment is separate from this local source commit.
