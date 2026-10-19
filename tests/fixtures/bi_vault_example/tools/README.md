# BI Ingest 工具

把 CSV、Excel、Markdown 表格或 JSON 轉成 vault 內各張卡(YAML frontmatter 格式正確、連結帶引號、日期與列舉值正規化)。

## 需求
```
pip install pyyaml openpyxl
```
Python 3.9 以上。pyyaml 用於合併既有卡片,openpyxl 用於讀 Excel。

## 常用指令
```bash
cd tools

# 看有哪些卡片類型與欄位
python bi_ingest.py --list-types

# 依 schema 重新產生所有 Templater 模板(欄位以 bi_schema.py 為準)
python bi_ingest.py --emit-templates ../BI/_Templates

# 先預覽,不寫檔
python bi_ingest.py samples/test_solution_sample.csv --type test_solution --vault ../BI --dry-run

# 正式匯入
python bi_ingest.py samples/test_solution_sample.csv --type test_solution --vault ../BI

# Excel(指定工作表)、Markdown 表格(指定第幾個表格,從 0 起算)
python bi_ingest.py data.xlsx --type customer_product --vault ../BI --sheet 客戶產品
python bi_ingest.py report.md --type ecosystem --vault ../BI --table 0 --mapping samples/mapping_ecosystem.json
```

## 它會做什麼
| 項目 | 規則 |
|---|---|
| 欄名對應 | 欄名或別名(中英文)自動對應 schema 欄位;對不上的會列出,可用 mapping 指定 |
| 日期 | 轉成 `YYYY-MM-DD`,支援 `2026/10/13`、`2026年10月13日`、民國 `115/10/13`、Excel 日期 |
| 清單 | 以 `;` `,` `、` `\|` 或換行分隔 |
| 連結 | 轉成 `"[[名稱]]"`,自動清除不合法的檔名字元;目標卡不存在時會警告 |
| 列舉值 | 中文自動對應(如 `整合方案` → `integrated`),不合法的值會警告並略過 |
| 數字 | 檢查範圍(如優先度 1 到 5) |
| 檔名 | 由 name 欄位產生(Signal 為 `日期-標題`),與連結名稱一致 |
| 來源標記 | 新卡會加上 `ingested_from: 檔名`,方便追溯,可用 `--no-source-tag` 關閉 |

## 合併規則(預設 `--mode merge`)
- 已存在的卡:新的非空單值覆蓋舊值,清單取聯集(`--replace-lists` 可改為取代)。
- 內文與未知的 frontmatter 欄位會保留。
- 內容沒有變化就不寫檔,所以同一份資料重跑是安全的。
- `--mode skip` 遇到已存在的卡就略過;`--mode overwrite` 整張重建(會丟失手寫內文,請小心)。
- 合併會以標準格式重寫 frontmatter,YAML 內的註解不會保留。

## mapping JSON(欄名對不上時使用)
```json
{
  "columns":  {"廠商": "name", "類別": "role"},
  "defaults": {"confidence": "assumed", "owner": "Milton"},
  "enum_aliases": {"role": {"模組廠": "module"}}
}
```
`defaults` 只套用在新建立的卡。

## 新增欄位或卡片類型
編輯 `bi_schema.py`,在對應類型加一行 `F(...)`,再執行 `--emit-templates` 同步模板。Dataview 查詢用到的欄位名稱要與 schema 一致。

## 建議的匯入流程
1. 取得原始資料(CRM 匯出、產品規格表、研究報告表格),先存成 CSV 或直接用 Excel。
2. `--dry-run` 看欄位對應與警告,必要時寫 mapping。
3. 正式匯入後打開 Obsidian,檢查 Dashboard 的缺口與過期查詢。
4. 匯入的資料預設 `confidence: assumed`,經客戶或實測驗證後再手動改為 `verified`。
5. 客戶機密資料(如詢價、客戶原話)不要放在同步到雲端的 vault 或匯入檔中,先確認公司資料政策。

## 進階 mapping(v3)
除 `columns / defaults / enum_aliases` 外,mapping JSON 支援 `skip_rows`、`text_replace`、`explode`、`derive`、`compose`、`exclude_names`、`name_aliases`;`--table` 可用 `0-6`、`1,3`、`all`、`has:欄名|欄名`。範例見 `samples/real/README.md`。

## Concept 卡(給業務的白話名詞解釋)
- `--type concept`:欄位見 `python bi_ingest.py --list-types`。內文可含多段 `## 標題`,會自動放進對應段落(見 `samples/concepts_draft.json`)。
- `python bi_concept_candidates.py ../BI --out samples/concept_candidates.md`:掃描現有卡的清單欄位與縮寫,列出尚無 Concept 卡的候選名詞。
- 草稿卡 `review_status: draft`,請業務試讀確認看得懂後改為 `reviewed`;Dashboard 第 14、15 節追蹤缺口與審閱佇列。

## 簡報(研討會投影片)匯入流程
1. `python bi_slides_extract.py talk.pptx --vault ../BI --out ../_Inbox`:擷取成暫存檔(放在 BI 之外,不被 Dataview 索引),並標出疑似測試方案頁與提到的既有卡片。
2. 把暫存檔貼給 Claude,搭配 `prompts/slide_distill.md` 蒸餾成 Signal / TestSolution / 補充備註的 JSON。
3. 人工確認後用 `bi_ingest.py --dry-run` 預覽,再匯入。
- 我方是 Rohde & Schwarz:TestSolution 的 `vendor` 欄位空白 = 我方方案;填 Competitor 卡名(Keysight、Anritsu…)= 對手方案,由我方卡的 `competing_solutions` 連到它。
- R&S 不建 Competitor 卡。

## 簡報 OCR(PaddleOCR,選用)
```powershell
py -m pip install paddlepaddle paddleocr pillow numpy pdfplumber python-pptx
py bi_slides_extract.py talk.pptx --vault ../BI --out ../_Inbox --ocr auto --ocr-lang ch
```
- `--ocr auto`(預設):有安裝且能載入模型才做 OCR,否則略過並提示;`on` 必須做;`off` 不做。
- `--ocr-lang`:`ch`(中英混合,預設)、`chinese_cht`(繁體)、`en`。`--min-conf`(預設 0.6)以下的文字會被捨棄。
- pptx:讀每張內嵌圖片(小於 120px 的圖示略過);PDF:文字太少的頁(掃描頁)整頁辨識,有圖的頁只保留文字層沒有的行。
- 圖多但讀不到文字、或疑似測試方案頁的圖片,會標「需要讀圖」並存到 `_Inbox/<檔名>_images/`,請把這些圖貼給 Claude 看。
- 第一次執行會下載辨識模型(需連網);公司網路若擋下載,請改用離線模型或在可連網的電腦先跑一次。
