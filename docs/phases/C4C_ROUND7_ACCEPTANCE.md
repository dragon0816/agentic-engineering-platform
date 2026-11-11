# C4C round7 acceptance (2026-11-12)

Result: AEP-authored Workflow passed full trials and independent output
reconciliation. Not installed; installation awaits the owner's normal approval.
Metadata only; enterprise rows and amounts stay in local artifacts.

## Workflow and runs

- Conversation `conversation-77223c69b5b24dc3aa6868789f440014` (original novice
  prompt, SOP PDF and mapping workbook; no technical selectors or business code
  from the coding agent).
- Candidate `wf-20261111-142125-2cc6c2`, `engineering/sap-sales-orders-report@1.0.9`,
  digest `9b0cbe2744de9d157dc18b68c443c6ab853c311070de789319b589dc534caf8d`;
  steps `browser/operate@1.0.0` (23 actions) and `coding/run-python@1.0.0`.
- Accepted run `run-7adcb257cd5a48069e1989748da44a8d`: succeeded, `verified=true`,
  `coverage_complete=true`.
- Output `C:/Users/Chi_L/Documents/aep-workflows/sap-sales-orders-report/output/sap_sales_orders_report_20261112-040011.xlsx`
  (source rows: `.aep-run/run-014/params.json` in the same workspace). The
  2026-11-09 `test_c4c_sales_orders.xlsx` is old and not part of this result.
- Earlier attempts are preserved: trials 1-3 failed (runs
  `run-5487d372125544c79eba680065d592e1`, `run-21905a52f2ee48a79a8f57a92098af9f`,
  `run-2e3e02f444f04b0484190971e8224b38`); trial 4
  `run-27759de762d64b3f8116055aa725245c` succeeded but unverified (plan assertions
  indexed to the old step); trial 5 `run-728331372d264cd5b659b29727899999`
  verified the same browser step (1.0.8); trial 6 is the accepted 1.0.9 run.

## Browser replay evidence

The compiled browser step waits for the freshly loaded navigation after reload
and handles the Sales panel by its `aria-expanded` state. Before any further
trial, AEP replayed the exact compiled sequence in one call twice: once with the
Sales panel expanded beforehand (scoped inspection `expanded=true`) and once
collapsed; both succeeded and were identical to the compiled step. Trials 4, 5
and 6 then succeeded with that same unchanged browser step. The earlier reload
race remains the most likely cause of trials 2 and 3; it is consistent with the
fix but not independently proven.

## Independent reconciliation

`.scratch/c4c_excel_validator.py` recomputes everything from the run's source rows
and the supplied mapping workbook (`.scratch/c4c-drive-20261111/validation-run014.json`):

- Source: 775 rows, 775 unique IDs, 0 blank IDs, all 11 required columns.
- C4C UI (AEP read-only report): 775 records, 26 pages; equals the source count.
- Dates: 0 outside 2026-07-01..2027-06-30; months 2026-07..2026-11 present.
- Copy sheet: 775 rows, ID multiset equal to source, 0 cell mismatches.
- Owner/Sub-Dept: 775/775 agree with independent mapping; 10 owners without a
  Sub-Dept (9 named not in the mapping workbook + blank owner), all listed as
  待確認; 179 rows without Sub-Dept; no department guessed.
- Blank Owner: 2 orders, flagged 待確認 in detail and in their own sheet.
- FX (EUR 1, USD 0.87, TWD 0.02712085): currencies EUR 340, USD 141, TWD 294;
  775/775 EUR values agree within 0.01. No unsupported currency this period, so
  the 待確認 currency list is correctly empty and the EUR aggregate is complete.
- Monthly owner summary: 160/160 cells and all row totals agree; Grand Total
  differs from the detail sum by 0.11 EUR (row rounding). The blank owner (EUR 0)
  is not a summary row.

## Remaining risks

- The date inputs are located by a placeholder containing the year (`e.g.
  31.12.2026`); C4C may change that example next year and break replay.
- The UI total was read by AEP, not by an independent reader.
- Not installed; installing needs the owner's approval in Agent Web.
- Unapproved harness observations, unchanged: `preflight_invalid` returns no
  detail; failed-capability text says "not executed" after partial runs;
  approval results are clipped at 2,000 characters; a 30-minute turn limit
  required one plain 「繼續」.
- During review, one AEP reply that quoted a trial preview exposed a few source
  names to the coding agent's local context; nothing was sent elsewhere.
