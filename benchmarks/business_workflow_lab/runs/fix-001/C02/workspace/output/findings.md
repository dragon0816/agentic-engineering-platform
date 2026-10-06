# 2026 年 9 月報價檢核 findings

- 查詢期間：2026-09-01 至 2026-09-30（含起訖日）
- 基準日：2026-09-30
- 報價筆數：12（已全部保留於 Excel，未因到期刪除）
- 明細列數：29

## 明細合計與 NetAmount 檢查
- 所有報價的明細 LineAmount 加總皆等於 Subtotal。
- 所有報價的 NetAmount 皆等於 Subtotal × (1 − DiscountPercent / 100)，並以 ROUND_HALF_UP 四捨五入至兩位小數。
- 所有明細列 LineAmount 皆等於 Quantity × UnitPrice，並以 ROUND_HALF_UP 四捨五入至兩位小數。

## ValidUntil 小於 2026-09-30 且尚未 Accepted 的報價
| QuoteID | CustomerID | ProjectID | QuoteDate | ValidUntil | Status | Currency | NetAmount | NetAmountTWD |
|---|---|---|---|---|---|---|---:|---:|
| Q0010 | C001 | P001 | 2026-09-01 | 2026-09-20 | Sent | TWD | 207629.63 | 207629.63 |
| Q0014 | C001 | P001 | 2026-09-09 | 2026-09-28 | Expired | EUR | 18072.00 | 632520.00 |
| Q0017 | C007 | P005 | 2026-09-17 | 2026-09-29 | Sent | TWD | 433800.00 | 433800.00 |

## 匯率
| Currency | RateToTWD |
|---|---:|
| EUR | 35 |
| TWD | 1 |
| USD | 32 |
