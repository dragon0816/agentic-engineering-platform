# C4C live Workflow validation

Owner request 2026-11-09: C4C signs in automatically; run the SOP and verify the
actual Workflow. The previously confirmed TWD rate is 0.02712085 EUR per TWD.

## Observed contract

The AEP Edge executor signs in automatically and reaches Sales Orders. This
account uses DD.MM.YYYY dates and European decimal notation. All + Document
Date Between 01.07.2026 and 30.06.2027 initially returned 749 rows over 25 pages;
later live runs returned 750. Validate the current UI count, not a fixed fixture.
There is
no Export/Spreadsheet control in this view; the SOP itself specifies copying
the table. No order edits, messages or external writes are required.

SAP controls require trusted pointer press/release; HTMLElement.click silently
does not open their selectors. Hidden duplicate navigation controls make an
unscoped label ambiguous. The table splits its header and body into two DOM
tables. Reading only the first page or the body's blank header cells loses data.

## Architecture / implementation slices

- Keep all site access in the Browser capability and Bridge policy. Do not fetch
  SAP endpoints or access application internals from Python. No LLM at replay.
- Add the Browser's native pointer primitive, keep read-mode checks before any
  pointer dispatch, filter hidden matches and recognize visible option controls.
- Extend read_table additively with header_table and typed optional pagination
  (next/current targets, bounded page count). Start at page 1, observe progress,
  refuse row/page limits, and never return a silently incomplete table.
- Await the visible count's loading marker and numeric completion before reading
  query results. SAP retains old page counts/tables while starting an async query.
  Wait for stable rows and distinct ID keys while paging: frozen ID cells can
  lag the other columns. Never repair this by dropping duplicate rows afterward.
- Reuse the same installed browser/operate capability and side-effect policy;
  no publishing, installation authority or model/provider contract changes.
- Feed complete browser rows to a deterministic local Python/Excel step. Parse
  the observed European currency/date formats, retain raw values, compare UI
  count with row count/unique IDs, and report missing mappings/currencies/dates.

## Verification

Trusted-pointer and hidden/option regressions fail before their fixes. Add
synthetic multi-page/header-split regressions and bounds/unchanged-page failure
cases. Replay the actual saved Workflow through WorkflowEngine/Bridge, verify
the current UI count, raw/enriched rows and EUR aggregates independently, then run relevant and
full verification. Private business data stays out of Git. No production Agent
restart is required to validate the current code in a separate workspace.
