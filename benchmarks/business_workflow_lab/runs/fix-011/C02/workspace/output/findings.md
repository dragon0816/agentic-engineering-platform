# Quote validation findings

- Query period: 2026-09-01 to 2026-09-30 inclusive
- Base date for expiration flag: 2026-09-30
- Source: quote_cli synthetic quote system; fx_rates.csv
- Quotes retained in workbook: 12
- Line items retained in workbook: 29

## Validation rules
- Detail subtotal check: sum(LineAmount) per quote must equal header Subtotal.
- NetAmount check: Subtotal × (1 − DiscountPercent / 100), rounded ROUND_HALF_UP to 2 decimals, must equal header NetAmount.
- LineAmount check: Quantity × UnitPrice, rounded to 2 decimals, must equal LineAmount.
- Expired/unaccepted flag: ValidUntil < 2026-09-30 and Status != Accepted.

## Summary
- Total findings: 3
- Expired and not Accepted quotes: 3
- ExpiredNotAccepted: 3

## Expired and not Accepted as of 2026-09-30
| QuoteID | CustomerID | ProjectID | QuoteDate | ValidUntil | Status | Currency | NetAmount |
|---|---|---|---|---|---|---|---:|
| Q0010 | C001 | P001 | 2026-09-01 | 2026-09-20 | Sent | TWD | 207629.63 |
| Q0014 | C001 | P001 | 2026-09-09 | 2026-09-28 | Expired | EUR | 18072.00 |
| Q0017 | C007 | P005 | 2026-09-17 | 2026-09-29 | Sent | TWD | 433800.00 |

## Detail findings
| QuoteID | Type | Finding |
|---|---|---|
| Q0010 | ExpiredNotAccepted | ValidUntil 2026-09-20 < 2026-09-30 and Status Sent is not Accepted |
| Q0014 | ExpiredNotAccepted | ValidUntil 2026-09-28 < 2026-09-30 and Status Expired is not Accepted |
| Q0017 | ExpiredNotAccepted | ValidUntil 2026-09-29 < 2026-09-30 and Status Sent is not Accepted |

## Completeness
- No quotes were removed because of expiration status.
- Workbook Quotes sheet contains every QuoteID returned by the September 2026 list query.
