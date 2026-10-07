# Quote findings

- Query period: 2026-09-01 to 2026-09-30 inclusive
- Baseline date for expiry check: 2026-09-30
- Source: quote_cli mock; FX: fx_rates.csv
- Generated at: 2026-10-07T07:36:12+08:00
- Quotes retained in workbook: 12
- Line items retained in workbook: 29

## Consistency checks

Rules: `Subtotal` must equal the sum of line `LineAmount`; each line `LineAmount` should equal `Quantity × UnitPrice`; `NetAmount` must equal `Subtotal × (1 - DiscountPercent / 100)`, rounded ROUND_HALF_UP to 2 decimals.

No consistency differences found.

### Per-quote check table

| QuoteID | Status | Currency | LineCount | LineSum | Subtotal | SubtotalOK | DiscountPercent | ExpectedNetAmount | NetAmount | NetAmountOK |
|---|---|---|---:|---:|---:|:---:|---:|---:|---:|:---:|
| Q0010 | Sent | TWD | 3 | 218557.50 | 218557.50 | True | 5 | 207629.63 | 207629.63 | True |
| Q0011 | Accepted | USD | 1 | 11500.00 | 11500.00 | True | 10 | 10350.00 | 10350.00 | True |
| Q0012 | Draft | TWD | 3 | 267825.00 | 267825.00 | True | 0 | 267825.00 | 267825.00 | True |
| Q0013 | Accepted | EUR | 2 | 2930.85 | 2930.85 | True | 5 | 2784.31 | 2784.31 | True |
| Q0014 | Expired | EUR | 3 | 18072.00 | 18072.00 | True | 0 | 18072.00 | 18072.00 | True |
| Q0015 | Accepted | TWD | 2 | 313500.00 | 313500.00 | True | 10 | 282150.00 | 282150.00 | True |
| Q0016 | Sent | USD | 1 | 256.50 | 256.50 | True | 5 | 243.68 | 243.68 | True |
| Q0017 | Sent | TWD | 3 | 433800.00 | 433800.00 | True | 0 | 433800.00 | 433800.00 | True |
| Q0018 | Draft | TWD | 4 | 572130.00 | 572130.00 | True | 10 | 514917.00 | 514917.00 | True |
| Q0019 | Sent | USD | 1 | 256.50 | 256.50 | True | 0 | 256.50 | 256.50 | True |
| Q0020 | Accepted | EUR | 4 | 5126.42 | 5126.42 | True | 5 | 4870.10 | 4870.10 | True |
| Q0021 | Draft | TWD | 2 | 129600.00 | 129600.00 | True | 0 | 129600.00 | 129600.00 | True |

## ValidUntil < 2026-09-30 and not Accepted

| QuoteID | CustomerID | ProjectID | QuoteDate | ValidUntil | Status | Currency | NetAmount |
|---|---|---|---|---|---|---|---:|
| Q0010 | C001 | P001 | 2026-09-01 | 2026-09-20 | Sent | TWD | 207629.63 |
| Q0014 | C001 | P001 | 2026-09-09 | 2026-09-28 | Expired | EUR | 18072.00 |
| Q0017 | C007 | P005 | 2026-09-17 | 2026-09-29 | Sent | TWD | 433800.00 |

## Workbook notes

- All September quote headers and line items returned by the CLI were written; expired quotes were flagged in this findings file only and were not removed from the workbook.
- Missing source values are left blank.
- NetAmountTWD uses fixed test rates from fx_rates.csv and ROUND_HALF_UP to 2 decimals.
