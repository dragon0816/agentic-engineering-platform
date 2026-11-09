# Chat document attachments and reply numbering — 2026-11-09

## Scope and integration

Branch main, starting at b9d96ac7. Owner approved direct PDF/XLSX/DOCX chat
attachments for SOP-to-Workflow authoring, reply numbering fixes, and testing
with Sales_order.pdf / Sales name and Dept.xlsx. Numbering is committed in
59320b68; the companion attachment/packaging/docs change is the commit carrying
this handoff. No push, release, production installation or Agent restart.

## Delivered

- host_runtime/attachment_documents.py: local, bounded PDF page text/pictures/
  HTTP(S) links; existing DOCX paragraph/table/picture extractor plus document
  links; XLSX sheet/row/formula previews. Originals stay intact. Parser failures,
  missing dependencies and truncation are explicit.
- attachments.py / web_page.py: .xlsx/.docx upload and drop support, locally
  extracted model evidence and supplied-value guidance. Existing session
  ownership, Gateway egress policy and native-backend attachment refusal remain.
- Ordered-list starts preserve source numbers across paragraphs/bullets.
- Windows builder/install/CI AND release_windows.py carry existing approved
  python-docx/lxml/PDF-image dependencies. No new third-party library.
- Regression, HTTP/model-wire/real authoring/preview/test-actor-install tests,
  operator guide, phase spec, appended decisions and evaluation report updated.

Architecture remains local read-only preprocessing, not Knowledge ingestion or
another authoring runtime. No publication/execution authority or provider change.
Details: docs/phases/CHAT_DOCUMENT_ATTACHMENTS.md and
 docs/evaluations/CHAT_DOCUMENT_ATTACHMENTS_2026-11-09.md.

## Verification evidence

Python: .venv/Scripts/python; repository pytest configuration supplies src.

- Original regressions failed before implementation: 9 failed / 5 passed.
- Initial related set: 138 passed in 114.19s.
- Attachment/authoring/bundle set: 35 passed in 96.10s before final Word-link test.
- Final focused attachment/authoring/Markdown set: 20 passed in 47.19s.
- Full coverage: 6021 items in 524 modules from normal --collect-only. Four
  disjoint file sets with independent basetemp/log/JUnit files. Initial result:
  6009 passed, 10 item skips, 2 failed; collection also skipped missing optional
  av. Shards passed/skipped: 1429/2 (2993.77s), 1439/2 (2640.66s),
  1613/4 with 2 failures (2879.69s), 1528/2 (2913.37s).
- Both failures inspected/resolved by rechecks: release dependency equality
  found a real missing release_windows.py update; unchanged assertion failed
  independently, then all 10 release tests passed after the fix. Library browser
  measured a stacked layout at its wide-layout assertion during concurrent
  execution; unchanged standalone rerun passed in 27.45s. No speculative product
  layout fix and no relaxed assertions.
- Final whole affected modules (Library content, release, attachments, HTTP
  authoring, Markdown DOM): 36 passed in 31.88s; C:/Temp/aep-document-final-recheck.
  Both initially failed cases pass on final source. Do not describe the initial
  full command as first-pass green. Its original failure evidence is retained.
- Ruff check . and format --check . passed (1397 files); Mypy passed (1052 files).
  pip check and isolated plus --no-isolation sdist/wheel builds passed. The final
  post-documentation build also passed (document-build-release-final.log).
- Independent read-only review found silent cell truncation and missing Word
  hyperlinks; both fixed/tested. Indirect PDF action concern was withdrawn.

Private launcher: .scratch/run_document_suite.py. Evidence: document-shards.json,
 document-shard-N.log/.xml/-result.json, document-suite-result.json. All processes
finished. AEP_GUI_TESTS=0 matches previous full-suite practice; optional skips
are listed in those reports. The initial serial attempt was deliberately stopped
around 7%, not counted as passing. The launcher's first collection lacked repo
root on sys.path (32 import errors); corrected before the authoritative collection.

## Owner attachment / real-model test

An isolated Agent Web workspace used the already-approved internal company
Gateway at localhost:4000; execution tools retained their schemas but refused
execution, except draft creation/read-back. Production config/workspace and
resident Agent were untouched. PDF: 2 pages, 5 embedded pictures and C4C URL;
XLSX: 7 columns and 29 data rows, originals byte-preserved.

Candidate wf-20261109-055356-06d5ac, final revision 5, version 1.0.4. Independent
feedback corrected download save_as and an unavailable pandas dependency. Current
15 browser actions validate against BrowserRequest; empty runtime arguments
validate to supplied dates, actual mapping path, output name and confirmed rate.
The exact current Python step uses standard library/openpyxl only. Five synthetic
export records plus the actual mapping produced independently verified EUR
monthly totals 187.00 and 27.12 and one unknown owner/currency/invalid date each.
This is fixture code execution, not authenticated SAP or the full C4C Workflow.

The owner temporarily said leave TWD pending, then explicitly changed the answer
to yes: 1 TWD = 0.02712085 EUR. Latest confirmation governs. Revision 4's pending
behavior was tested, then final revision 5's confirmed conversion reran and passed.
No guessed platform-wide FX default was introduced. See appended DECISIONS.

Private records: .scratch/sales-sop-acceptance-final/result.json,
fixture-evidence.json and c4c-sales-order-export-analysis/output/
c4c_sales_orders_fy2026_analysis.xlsx. Original files, model replies, generated
scripts/manifests and example workbook are not committed or included in builds.
No candidate was installed into the owner's Agent.

## Remaining acceptance / next action

Implementation is complete within the approved scope. The installed Agent still
needs the normal owner-authorized update with an active-work check. Then verify
actual selectors, SSO/permissions, date filter, export completeness and workbook
output in a signed-in C4C session. None is claimed proven here. The generated
monthly summary is a table, not a native Excel PivotTable. The target export
screenshot mentioned in the example was not separately provided in this coding
turn; the supplied PDF pictures were the available visual evidence.

Known verification limitation: the Library wide-layout browser assertion was
intermittent in the concurrent full run; original geometry and passing rechecks
are preserved. A later Windows CI run may still expose that existing test's
geometry sensitivity. No remote CI was launched for these unpushed commits.
