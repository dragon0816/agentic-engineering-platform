# Quote Findings — September 2026

- Period fetched: `2026-09-01` to `2026-09-30` inclusive
- Baseline date for expiry check: `2026-09-30`
- Source: quote_cli synthetic quote system; FX: `input/fx_rates.csv`
- Quotes retained in workbook: **12** (no quote removed because of expiry)
- Line items retained in workbook: **29**
- Source ProjectID blank/missing values kept blank in workbook: **4**

## Consistency checks

- LineAmount = Quantity × UnitPrice mismatches: **0**
- Subtotal vs. sum(LineAmount) mismatches: **0**
- NetAmount = Subtotal × (1 − DiscountPercent / 100), ROUND_HALF_UP 2 decimals mismatches: **0**
## ValidUntil < 2026-09-30 and not Accepted

Count: **3**

| QuoteID | CustomerID | ProjectID | QuoteDate | ValidUntil | Status | Currency | NetAmount |
|---|---|---|---|---|---|---|---:|
| Q0010 | C001 | P001 | 2026-09-01 | 2026-09-20 | Sent | TWD | 207,629.63 |
| Q0014 | C001 | P001 | 2026-09-09 | 2026-09-28 | Expired | EUR | 18,072.00 |
| Q0017 | C007 | P005 | 2026-09-17 | 2026-09-29 | Sent | TWD | 433,800.00 |

## Totals by Status and Currency

| Status | Currency | NetAmount | NetAmountTWD | Count |
|---|---|---:|---:|---:|
| Accepted | EUR | 7,654.41 | 267,904.35 | 2 |
| Accepted | TWD | 282,150.00 | 282,150.00 | 1 |
| Accepted | USD | 10,350.00 | 331,200.00 | 1 |
| Draft | TWD | 912,342.00 | 912,342.00 | 3 |
| Expired | EUR | 18,072.00 | 632,520.00 | 1 |
| Sent | TWD | 641,429.63 | 641,429.63 | 2 |
| Sent | USD | 500.18 | 16,005.76 | 2 |
