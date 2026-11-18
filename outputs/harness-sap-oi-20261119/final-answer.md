已完成受控 SAP OI 匯出任務，結果如下：

- 已開啟模擬 SAP：`http://127.0.0.1:8766`
- 已核對日期：
  - 起日：`2026-09-01`
  - 迄日：`2026-10-31`
- 已套用 Sales 篩選：
  - Alice Chen
  - Bob Lin
  - Carol Wu
- 網頁結果共 16 筆、4 頁，已逐頁確認。
- 已使用瀏覽器 `do=download` 下載全部篩選資料：
  - `output/downloads/filtered_oi.csv`
- 正規化結果：
  - 來源列：16
  - 去除完全重複列：1
  - 唯一來源列：15
  - 排除 `Cancelled` / `Pending`：3
  - 有效 `Booked` 明細：12
  - 負數與零金額均保留
  - USD 依固定匯率 32 換算，TWD 匯率為 1
- 已產生：
  - `output/normalized.json`
  - `output/sales-oi-pivot.xlsx`

獨立驗收結果：

- 驗收通過：`true`
- 明細筆數：12
- OI TWD 總計：`13,580`
- 原生 PivotTable 已解析：`true`
- Pivot cache 與來源資料一致：`true`
- Excel Desktop 刷新驗證：未執行，因環境未安裝 Microsoft Excel
- 公式快取為計算快照，非 Excel Desktop 即時重算結果

中途曾發現並修正一項程式驗證條件錯誤：有效列數實際為 12 而非原先誤設的 13；修正後重新執行並通過驗收。