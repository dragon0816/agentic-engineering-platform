# C4C round7 acceptance (2026-11-12, Asia/Taipei)

Result: AEP-authored Workflow passed full trials and independent output
reconciliation. Installation request is pending the owner's approval.
Metadata only; enterprise rows and amounts stay in local artifacts.

## Final version

- Conversation `conversation-77223c69b5b24dc3aa6868789f440014` (original novice
  prompt, SOP PDF and mapping workbook; no technical selectors or business code
  from the coding agent; reviewer feedback was given in plain language only).
- Candidate `wf-20261111-142125-2cc6c2`, `engineering/sap-sales-orders-report@1.0.9`,
  digest `dae0b636346fb8bc5ce22fff6d6d1ec560500b880c46989b4d0a139c4e6f3d4d`;
  steps `browser/operate@1.0.0` (23 actions) and `coding/run-python@1.0.0`.
- Accepted run `run-8782ad04c94e47de87b71015479b220a`: succeeded, `verified=true`,
  `coverage_complete=true`.
- Output `C:/Users/Chi_L/Documents/aep-workflows/sap-sales-orders-report/output/sap_sales_orders_report_20261112-042323.xlsx`
  (source rows `.aep-run/run-015/params.json` in the same workspace).
- Install request card `ap-20261111-202432-5d212d` (kind install, pending, same
  digest). Created through the normal platform request; not self-approved.

## History (all preserved)

| Trial | Run | Outcome |
|---|---|---|
| 1 | run-5487d372125544c79eba680065d592e1 | failed: label ensure_visible, compiled without replay |
| 2 | run-21905a52f2ee48a79a8f57a92098af9f | failed: click Sales Orders after presence check |
| 3 | run-2e3e02f444f04b0484190971e8224b38 | failed: same as 2; first budget exhausted |
| 4 | run-27759de762d64b3f8116055aa725245c | succeeded, unverified (assertions indexed to old step) |
| 5 | run-728331372d264cd5b659b29727899999 | succeeded, verified (1.0.8, same browser step) |
| 6 | run-7adcb257cd5a48069e1989748da44a8d | succeeded, verified (1.0.9, blank Owner flagged) |
| 7 | run-8782ad04c94e47de87b71015479b220a | succeeded, verified, ACCEPTED (rounding policy, year-free date locator) |

Outputs of trials 4-6 and the 2026-11-09 `test_c4c_sales_orders.xlsx` are not the
final result.

## Browser replay evidence

The browser step waits for the freshly loaded navigation after reload, handles
the Sales panel by its `aria-expanded` state, and locates the two date inputs
inside the condition dialog by a stable `-datePicker-inner` suffix and grid
position (no example-year placeholder). Before trial 7, AEP replayed the exact
compiled 23-action sequence in single calls twice: after a reload that left the
Sales panel collapsed (`expanded=false`) and after explicitly expanding it
(`aria-expanded='true'`); both succeeded and equalled the compiled step. The
earlier reload race remains the most likely cause of trials 2/3, consistent with
the fix but not independently proven.

## Independent reconciliation

`.scratch/c4c_excel_validator.py` recomputes from the run's source rows and the
supplied mapping workbook; result `.scratch/c4c-drive-20261111/validation-run015.json`.

- Source: 775 rows, 775 unique IDs, 0 blank IDs, all 11 required columns.
- C4C UI (AEP read-only report): 775 records, 26 pages; equals the source count.
- Dates: 0 outside 2026-07-01..2027-06-30; months 2026-07..2026-11.
- Copy sheet: 775 rows, ID multiset equal to source, 0 cell mismatches.
- Owner/Sub-Dept: 775/775 agree with the independent mapping; 10 owners without
  a Sub-Dept (9 named not in the mapping workbook + blank owner) listed 待確認;
  179 rows without Sub-Dept; no department guessed.
- Blank Owner exception: 2 source orders have an empty Owner in C4C; their EUR is
  exactly 0. They are flagged 待確認 in the detail, listed on `Blank Owner 待確認`,
  counted in `Unmatched Owners`, and shown as a zero row in the summary. This is
  a tracked exception, not a claim that every order has a named owner.
- FX (EUR 1, USD 0.87, TWD 0.02712085): EUR 340, USD 141, TWD 294 orders;
  775/775 EUR values agree. No other currency this period, so the 待確認 currency
  list is correctly empty and the EUR aggregate is complete.
- Rounding policy (declared in Checks): each line's EUR rounded to the cent
  (ROUND_HALF_UP), then summed. Under that policy, recomputed from source:
  165/165 owner-month cells and all owner totals agree within half a cent.
- Internal consistency on the written values: owner-month cells vs detail,
  owner totals vs cells, month totals vs owner rows, Grand Total vs detail sum —
  0 differences above half a cent (all max differences 0.00).

The earlier 1.0.9 output (trial 6) failed these consistency checks (17 cells,
3 owner totals, 1 month total, Grand Total off by 0.09), which led to the policy fix.

## Remaining risks

- The UI total was read by AEP, not by an independent reader.
- Date-input locators rely on the dialog grid order (Value, Value To) and the
  `-datePicker-inner` suffix observed now; a C4C UI release could change them.
- Unapproved harness observations, unchanged: `preflight_invalid` returns no
  detail; failed-capability text says "not executed" after partial runs;
  approval results are clipped at 2,000 characters; a 30-minute turn limit
  required one plain 「繼續」.
- During review, one AEP reply quoting a trial preview exposed a few source
  names to the coding agent's local context; nothing was sent elsewhere.
