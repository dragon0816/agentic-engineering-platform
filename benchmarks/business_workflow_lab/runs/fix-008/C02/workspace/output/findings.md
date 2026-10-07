# Quote findings

- Query period: 2026-09-01 to 2026-09-30 inclusive
- Baseline date for ValidUntil: 2026-09-30
- Source: quote_cli mock; fx_rates.csv
- Quotes retained in workbook: 12 (no quote removed because of expiration)
- Line rows retained in workbook: 29

## Calculation checks

| QuoteID | Detail sum | Subtotal | DiscountPercent | Expected NetAmount | Reported NetAmount | Result |
|---|---:|---:|---:|---:|---:|---|
| Q0010 | 218557.50 | 218557.50 | 5 | 207629.63 | 207629.63 | OK |
| Q0011 | 11500.00 | 11500.00 | 10 | 10350.00 | 10350.00 | OK |
| Q0012 | 267825.00 | 267825.00 | 0 | 267825.00 | 267825.00 | OK |
| Q0013 | 2930.85 | 2930.85 | 5 | 2784.31 | 2784.31 | OK |
| Q0014 | 18072.00 | 18072.00 | 0 | 18072.00 | 18072.00 | OK |
| Q0015 | 313500.00 | 313500.00 | 10 | 282150.00 | 282150.00 | OK |
| Q0016 | 256.50 | 256.50 | 5 | 243.68 | 243.68 | OK |
| Q0017 | 433800.00 | 433800.00 | 0 | 433800.00 | 433800.00 | OK |
| Q0018 | 572130.00 | 572130.00 | 10 | 514917.00 | 514917.00 | OK |
| Q0019 | 256.50 | 256.50 | 0 | 256.50 | 256.50 | OK |
| Q0020 | 5126.42 | 5126.42 | 5 | 4870.10 | 4870.10 | OK |
| Q0021 | 129600.00 | 129600.00 | 0 | 129600.00 | 129600.00 | OK |

## ValidUntil < 2026-09-30 and Status not Accepted

| QuoteID | CustomerID | ProjectID | QuoteDate | ValidUntil | Status | Currency | NetAmount |
|---|---|---|---|---|---|---|---:|
| Q0010 | C001 | P001 | 2026-09-01 | 2026-09-20 | Sent | TWD | 207629.63 |
| Q0014 | C001 | P001 | 2026-09-09 | 2026-09-28 | Expired | EUR | 18072.00 |
| Q0017 | C007 | P005 | 2026-09-17 | 2026-09-29 | Sent | TWD | 433800.00 |

## FX rates used

| Currency | RateToTWD |
|---|---:|
| EUR | 35 |
| TWD | 1 |
| USD | 32 |
