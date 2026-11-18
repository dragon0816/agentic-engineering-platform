# Synthetic SAP OI reliability benchmark

Owner requested a mock SAP web → SOP-driven extraction → Excel/PivotTable case,
including SOP, process dialogue and complete generation evidence (2026-11-19).

This is an isolated benchmark fixture, not a Shared Harness redesign or installed
production Workflow. Reuse Gateway.converse, BrowserSessionHandler, coding.run_python,
Bridge results, local state and model adapters. Fixture grants permit loopback
browser access and writes only in this run's synthetic workspace. Keep BI work separate.

The model must operate the web page and download its filtered CSV. It writes a
normalization script via the existing restricted Python tool. A benchmark-only
write capability consumes its normalized JSON, creates Excel and runs a sealed,
independent oracle before reporting success. The oracle's expected values are
frozen independently of the generated program. No arbitrary JSON success-key scan.

The Artifact Tool public surface did not provide usable PivotTable authoring.
Initial sheet authoring/export and subsequent saved-file import/render prototypes
failed on Windows with native exit 3221226505 (0xC0000409); an explicit process.exit
workaround did not fix it. These are environment observations, not a diagnosed
native-library root cause. Preserve build.mjs/render.mjs as failed prototypes only.

The final benchmark uses the already available openpyxl author and a narrow
stdlib OOXML packaging adapter for the missing native PivotTable parts. The
independent oracle reads the saved workbook, formula snapshots, native pivot
source/axes/measure and every cache record. It also checks normalized records
against independently frozen fictional fixtures. HTML previews read actual saved
cells; they are not desktop Excel screenshots or proof of recalculation.
No desktop Excel is installed on 141; native Excel open/refresh is unverified.
Reference: https://learn.microsoft.com/en-us/office/open-xml/spreadsheet/working-with-pivottables

Task acceptance requires answered conversation, a successful final typed exporter
verification, independently accepted saved artifact and all 16 exported rows.
Artifact correctness alone cannot override a failed mandatory exporter step.
Run 4 exposed a benchmark-report aggregation defect; its original report is frozen,
explicitly superseded by a separate assessment, and covered by negative tests.

Persist every model request/response, tool arguments/results, generated script,
browser screenshot, downloaded CSV, normalized data, builder, validation report,
and final workbook. Credentials/HTTP headers are excluded; fictional task data is
included for owner review. Fault controls must reject missing pivot parts, missing
rows, wrong totals, and stale/tampered cache records. Never describe a failed
mandatory check as verified success. Do not export additional workbook variants.
