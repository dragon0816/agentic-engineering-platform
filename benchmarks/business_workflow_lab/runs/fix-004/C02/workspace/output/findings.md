# Quote findings — September 2026

- Query period: 2026-09-01 through 2026-09-30 inclusive
- Expiry review baseline: 2026-09-30
- Source: quote_cli mock; fx_rates.csv
- Generated at: 2026-10-07T05:16:04+08:00
- Quotes retained in workbook: 12 (no quote removed because of expiry)
- Line items retained in workbook: 29

## Amount consistency checks

- All quotes passed: each quote Subtotal equals the sum of LineAmount values, each LineAmount equals Quantity × UnitPrice, and each NetAmount equals Subtotal × (1 − DiscountPercent / 100) rounded ROUND_HALF_UP to 2 decimals.

## ValidUntil before 2026-09-30 and Status not Accepted

| QuoteID | CustomerID | ProjectID | QuoteDate | ValidUntil | Status | Currency | NetAmount |
|---|---|---|---|---|---|---:|---:|
| Q0010 | C001 | P001 | 2026-09-01 | 2026-09-20 | Sent | TWD | 207629.63 |
| Q0014 | C001 | P001 | 2026-09-09 | 2026-09-28 | Expired | EUR | 18072.00 |
| Q0017 | C007 | P005 | 2026-09-17 | 2026-09-29 | Sent | TWD | 433800.00 |

## Summary by Status and Currency

| Status | Currency | NetAmount | NetAmountTWD | Count |
|---|---|---:|---:|---:|
| Accepted | EUR | 7654.41 | 267904.35 | 2 |
| Accepted | TWD | 282150.00 | 282150.00 | 1 |
| Accepted | USD | 10350.00 | 331200.00 | 1 |
| Draft | TWD | 912342.00 | 912342.00 | 3 |
| Expired | EUR | 18072.00 | 632520.00 | 1 |
| Sent | TWD | 641429.63 | 641429.63 | 2 |
| Sent | USD | 500.18 | 16005.76 | 2 |
