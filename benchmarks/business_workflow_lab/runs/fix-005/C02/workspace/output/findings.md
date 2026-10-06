# Findings - 2026-09 Quotes

- 查詢期間：2026-09-01 至 2026-09-30（含起訖日）
- 到期判斷基準日：2026-09-30
- 資料來源：quote_cli_mock；匯率：input/fx_rates.csv
- 取得報價數：12
- 取得明細列數：29
- 保留原則：全部報價皆保留於 Excel，不因到期或狀態刪除。

## 金額一致性檢查
- 全部報價的明細 LineAmount 合計均等於表頭 Subtotal。
- 全部報價的折扣後 NetAmount 均符合 `Subtotal × (1 − DiscountPercent / 100)` 並 ROUND_HALF_UP 至兩位小數。
- 全部明細列的 LineAmount 均符合 `Quantity × UnitPrice`。

## ValidUntil < 2026-09-30 且尚未 Accepted 的報價
| QuoteID | CustomerID | ProjectID | ValidUntil | Status | Currency | NetAmount |
|---|---|---|---|---|---|---:|
| Q0010 | C001 | P001 | 2026-09-20 | Sent | TWD | 207629.63 |
| Q0014 | C001 | P001 | 2026-09-28 | Expired | EUR | 18072.00 |
| Q0017 | C007 | P005 | 2026-09-29 | Sent | TWD | 433800.00 |

## 每份報價檢查明細
| QuoteID | Lines | Line Sum | Subtotal OK | Expected NetAmount | NetAmount OK |
|---|---:|---:|---|---:|---|
| Q0010 | 3 | 218557.50 | OK | 207629.63 | OK |
| Q0011 | 1 | 11500.00 | OK | 10350.00 | OK |
| Q0012 | 3 | 267825.00 | OK | 267825.00 | OK |
| Q0013 | 2 | 2930.85 | OK | 2784.31 | OK |
| Q0014 | 3 | 18072.00 | OK | 18072.00 | OK |
| Q0015 | 2 | 313500.00 | OK | 282150.00 | OK |
| Q0016 | 1 | 256.50 | OK | 243.68 | OK |
| Q0017 | 3 | 433800.00 | OK | 433800.00 | OK |
| Q0018 | 4 | 572130.00 | OK | 514917.00 | OK |
| Q0019 | 1 | 256.50 | OK | 256.50 | OK |
| Q0020 | 4 | 5126.42 | OK | 4870.10 | OK |
| Q0021 | 2 | 129600.00 | OK | 129600.00 | OK |
