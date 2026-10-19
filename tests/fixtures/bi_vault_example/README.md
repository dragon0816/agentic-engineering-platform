# BI Vault Starter(無線通訊量測範例)

## 使用方式
1. 將整個 `BI` 資料夾放進你的 Obsidian vault 根目錄。
2. 安裝並啟用外掛:**Dataview**(必要)、**Templater**(建議)。
   - Dataview 設定:開啟 Enable JavaScript Queries、Automatic View Refreshing。
   - Templater 設定:Template folder location 指定為 `BI/_Templates`。
3. 開啟 `BI/Dashboard.md` 查看範例報表。
4. 新增資料:在對應資料夾建立新檔案,用 Templater 插入對應模板。

## 重要提醒
- **所有範例資料均為虛構或待查證**(`confidence: assumed`),僅用於示範結構,請替換為真實資料。
- 標準時程、市場數字請向官方來源查證後再改為 `verified`。
- YAML 的連結一定要加引號,例如 `"[[5G-NR-FR2]]"`;連結名稱需與檔名一致。
- 數字欄位不要加引號;日期格式 `YYYY-MM-DD`。

## 分析鏈
Trend → Technology → Value Chain Node → Ecosystem → Customer Product → Application → Test Solution → Opportunity

## 資料夾
- Node:價值鏈節點(骨架,很少變動)
- Technology:技術與標準時程
- Trend:市場趨勢(由 Signal 彙整)
- Signal:市場訊號(每則情報一筆,必寫 so_what)
- Ecosystem:生態系成員(晶片商、認證實驗室…)
- CustomerProduct:客戶產品與上市時程
- Account / Application:示範用最小版本

## v2 更新:方案層與 ingest 工具
- 新增 `BI/TestSolution`(方案層)、`BI/Competitor`,Application 擴充為 4 筆(其中「5G-FR2手機產線RF校正」刻意沒有方案,用來示範缺口查詢)。
- `tools/` 內有 Python ingest 工具,可把 CSV、Excel、Markdown 表格轉成各張卡,說明見 `tools/README.md`。
- `_Templates` 已由 `bi_schema.py` 重新產生,欄位與 ingest 工具保持一致。
