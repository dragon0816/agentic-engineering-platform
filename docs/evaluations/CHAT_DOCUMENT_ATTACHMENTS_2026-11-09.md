# Chat document attachment verification — 2026-11-09

## Scope

Owner-approved PDF/XLSX/DOCX chat attachment previews and numbered reply fixes.
Originals stay immutable, session ownership stays enforced, and existing model
egress, Workflow execution and install approval policies remain unchanged.

## Repeatable evidence

- Before implementation, the attachment/DOM regressions produced 9 failures and
  5 passes: missing PDF page/picture evidence, refused Office types, silent PDF
  failure, missing picker support and reset ordered-list start values.
- `tests/test_attachments.py`: 18 passed after adding PDF/DOCX links, original
  byte preservation, shared picture limits, formula/sheet/row previews, corrupt
  files, missing parser and visible long-cell truncation coverage.
- `tests/test_attachment_authoring.py`: real HTTP uploads of generated PDF,
  DOCX and XLSX, serialized model text plus two pictures, actual authoring tool
  dispatch, durable session-owned candidate, real Excel preview, explicit test
  actor installation and deterministic Workflow execution passed. The model
  transport is scripted; this does not prove SAP browser behavior.
- Original related test set (attachments, Telegram, authoring, preview,
  E2E-02 and Agent Web): 138 passed in 114.19 seconds.
- Attachment/authoring/offline-bundle set: 35 passed in 96.10 seconds before
  the final DOCX hyperlink test (which passed in the 18-test attachment run).
- The missing-Word-wheel regression failed before the builder change; the
  builder now requires python-docx/lxml wheels. The installer and CI wheel
  download use the existing approved parser dependencies; no new library.
- Final focused attachment/authoring/Markdown set: 20 passed in 47.19 seconds.
- Ruff check/format, Mypy (1052 files), pip check and sdist/wheel build passed.
- Full pytest ran in four isolated processes after a complete normal
  collection: 6021 items in 524 modules, disjoint file sets covering every
  collected item. Each shard has its own basetemp, log and JUnit XML. The earlier
  serial run was deliberately stopped for this execution method and is not
  counted as passing. The private launcher's first collection lacked the repo
  root on sys.path (32 scripts-import collection errors); corrected before the
  authoritative collection/shards, with no product change or test exclusions.
  Initial outcome: 6009 passed, 10 item skips, 2 failures; the collection also
  records the optional missing-av module skip. Shards: 1429/2 skipped (2993.77s),
  1439/2 skipped (2640.66s), 1613/4 skipped/2 failed (2879.69s),
  1528/2 skipped (2913.37s). There were no collection or execution errors.

  The failures were inspected, not ignored. The release dependency equality
  regression caught a real missing update in scripts/release_windows.py; its
  existing assertion failed independently before correction and all 10 release
  tests passed afterward. The Library browser test measured the narrow stacked
  layout at its wide-layout assertion during the concurrent run; the unchanged
  test passed alone in 27.45s. No layout/product change or assertion relaxation
  was made. Final complete affected modules (Library content, release,
  attachments, HTTP authoring and Markdown DOM) passed: 36 tests in 31.88s,
  using C:/Temp/aep-document-final-recheck. Thus both original failed cases pass
  on the final source; the initial full run's nonzero result is retained rather
  than relabeled as a first-pass green run. All 6021 collected cases were covered.

## Owner attachment/model acceptance

The supplied Sales_order.pdf and Sales name and Dept.xlsx were uploaded to an
isolated workspace through AgentWeb.add_attachment, then supplied to the normal
conversation/Gateway authoring path. The approved internal company Gateway was
used; production workspace/configuration and the resident Agent were untouched.
The PDF exposes two pages, five pictures and a C4C hyperlink. The workbook has
one sheet, seven columns and 29 data rows; its original bytes were retained.

The initial real-model run created a private C4C sales-order export/Excel
analysis candidate. It identified fiscal dates, Owner/Sub-Dept mapping and EUR
analysis. Its first invalid input shape was rejected and the model revised it.
This is evidence of attachment-informed draft creation, not a successful SAP
export. No C4C session, browser selectors, actual sales export or real Workflow
execution was exercised in this deliberately draft-only test. An unverified
browser sequence must not be represented as ready for execution. The initial
test hid execution tool schemas; the final isolated run retains their schemas
but refuses execution to make the drafting evidence representative.

The final representative run created candidate `wf-20261109-055356-06d5ac`.
Independent validation found an invalid download save_as and a pandas import
unavailable in the runner. Feedback to the same model/session revised that same
candidate to revision 3, without installing or executing C4C. The revision uses
only the Python standard library and installed openpyxl; all 15 browser actions
validate against BrowserRequest. Empty runtime arguments validate to prefilled
SOP dates, the supplied mapping attachment and an output name.

The exact revision-3 Python step was executed privately against five synthetic
export records and the actual uploaded mapping workbook, not actual sales data.
It produced an Excel workbook with merged mapping/EUR rows, monthly totals and
exception sheets. Independent openpyxl checks observed expected EUR totals
187.00 (USD plus EUR) and 27.12 (1000 TWD), and one each of unknown owner,
unknown currency and invalid date. This proves the Excel step on the fixture,
not live browser execution or a native Excel PivotTable. The private output and
machine-readable evidence are under `.scratch/sales-sop-acceptance-final/`.
Those revision-3 TWD fixture numbers were a temporary interpretation, not a
business-approved rate. The owner explicitly answered on 2026-11-09:
"不是，匯率先保留待確認". The final candidate must therefore remove the guessed
TWD/EUR conversion, preserve original TWD amounts, mark the rate pending and
exclude unconverted TWD from EUR totals. EUR/USD rules remain as in the SOP.
Revision 4's pending-rate behavior was verified before the later correction.

The owner subsequently corrected that answer to yes, explicitly confirming
1 TWD = 0.02712085 EUR. That latest answer supersedes the temporary pending-rate
instruction. Revision 4's pending behavior was verified (TWD EUR blank, separate
pending row, EUR monthly total 187). Final revision 5 (Workflow version 1.0.4)
prefills the explicitly confirmed rate. Its 15 browser actions and empty runtime
arguments pass contract validation; the exact current Python program reran on
the five-record fixture. Workbook checks passed for two EUR monthly rows totaling
187.00 and 27.12, TWD converted at the confirmed rate, zero pending TWD rows and
the same three exception counts. Current output is
`c4c_sales_orders_fy2026_analysis.xlsx` in the private test workspace. No C4C
session or production Workflow execution is implied by this result.

Private model replies, generated candidates/scripts and originals are excluded
from Git. They remain under `.scratch/sales-sop-acceptance*/`. No candidate was
installed into the owner's Agent. The target export screenshot mentioned in
the original example was not independently attached to this development turn;
the provided PDF pictures supply the available visual evidence.

## Review and remaining acceptance

Independent read-only review found silent long-cell truncation and missing Word
hyperlinks; both are addressed by the adapter and regression tests. Its initial
concern about indirect PDF action objects was withdrawn after a synthetic probe.

Still required for the business Workflow: run against an authorized, signed-in
C4C browser, verify actual controls/export scope and expected workbook output.
Changing or restarting the installed Agent requires the normal active-work
check; this implementation performs neither action.
