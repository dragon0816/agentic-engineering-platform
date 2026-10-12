# Findings - 2026 年 9 月報價檢查

- 查詢期間：2026-09-01 至 2026-09-30（含起訖日）
- 逾期判定基準日：2026-09-30
- 資料來源：quote_cli_mock；匯率：input/fx_rates.csv
- 取得報價：12 份；明細：29 筆
- 處理原則：保留全部報價，不因到期而刪除。

## 明細合計檢查
未發現 LineAmount = Quantity × UnitPrice 或 Subtotal = 明細 LineAmount 合計的不一致。

## 折扣後 NetAmount 檢查
未發現 NetAmount = Subtotal × (1 − DiscountPercent / 100)（ROUND_HALF_UP 至兩位小數）的不一致。

## ValidUntil 小於 2026-09-30 且尚未 Accepted 的報價
共 3 份：
| QuoteID | CustomerID | ProjectID | QuoteDate | ValidUntil | Status | Currency | NetAmount |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Q0010 | C001 | P001 | 2026-09-01 | 2026-09-20 | Sent | TWD | 207629.63 |
| Q0014 | C001 | P001 | 2026-09-09 | 2026-09-28 | Expired | EUR | 18072.00 |
| Q0017 | C007 | P005 | 2026-09-17 | 2026-09-29 | Sent | TWD | 433800.00 |
