# Quotation Findings

- Query period: 2026-09-01 through 2026-09-30 (inclusive)
- Source: quote_cli mock
- Generated at: 2026-10-06T00:00:00+08:00
- Expiry basis: flag quotes where ValidUntil < 2026-09-30 and Status is not Accepted
- Quotes retained in workbook: 12
- Line items retained in workbook: 29
- Missing ID placeholder: N/A

## Calculation checks
No line subtotal or NetAmount inconsistencies found.

## Expired and not Accepted as of 2026-09-30
| QuoteID | Detail |
|---|---|
| Q0010 | ValidUntil 2026-09-20 < 2026-09-30; Status Sent |
| Q0014 | ValidUntil 2026-09-28 < 2026-09-30; Status Expired |
| Q0017 | ValidUntil 2026-09-29 < 2026-09-30; Status Sent |

## Missing ID placeholders
| QuoteID | Field | Placeholder |
|---|---|---|
| Q0016 | ProjectID | N/A |
| Q0019 | ProjectID | N/A |
| Q0020 | ProjectID | N/A |
| Q0021 | ProjectID | N/A |

## Summary by status and currency
| Status | Currency | Count | NetAmount | NetAmountTWD |
|---|---|---:|---:|---:|
| Accepted | EUR | 2 | 7654.41 | 267904.35 |
| Accepted | TWD | 1 | 282150.00 | 282150.00 |
| Accepted | USD | 1 | 10350.00 | 331200.00 |
| Draft | TWD | 3 | 912342.00 | 912342.00 |
| Expired | EUR | 1 | 18072.00 | 632520.00 |
| Sent | TWD | 2 | 641429.63 | 641429.63 |
| Sent | USD | 2 | 500.18 | 16005.76 |
