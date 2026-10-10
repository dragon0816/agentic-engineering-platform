# Knowledge 管線發布計畫：Convert → Ingest → Query → Lint/Conflict（草案，待 owner 審）

2026-10-11。依 owner 需求與討論（對話 2026-10-10～11）整理。參考：Karpathy「LLM Wiki」
（https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f）。

## 1. 目標

每個人用自己的 Personal Agent（Agent Web），以 **Karpathy LLM Wiki 基礎 Skill + 自己領域的 Skill**
分析自己的資料：能存取到 vault 資料夾就能分析。權限由 vault 本身控制，不是本計畫的設計重點。

第一個領域：**5 個市場 × 4 條產品線** 的 vault（已設權限），配一個為它客製的 domain matrix Skill。
- 市場：無線通訊、航太／國防、車用／無人機、AI、半導體。
- 產品線：無線通訊綜合測試儀（signaling、non-signaling）、訊號產生器／訊號分析儀、示波器、VNA 網路分析儀。

## 2. 發布形式（建議）

放在 **Agent Web**，新增「Knowledge」頁面；不做獨立 app。理由（對照 `docs/PRODUCT_VISION.md`）：
Personal Agent 是主要介面；領域知識放 Skill（已有安裝、版本、選擇）；寫入核准、Harness 驗證、telemetry
（Atlas 可看進度）與 Knowledge 版本發布都已存在；對話中也能直接觸發（「把這個資料夾 ingest 進 vault」）。

頁面：選 vault → 拖檔案到 drop 並預覽轉換 → 預覽 ingest 的頁面差異並核准 → 衝突報告與判斷。
query 在對話中進行。瀏覽 wiki 沿用 Obsidian（Karpathy 建議），頁面連結可開 Obsidian。

一致性（非權限）：同一 vault 同一時間只允許一個寫入者（vault 鎖），查詢不受影響。

## 3. 現況對照

| 功能 | 已有（`src/knowledge/`） | 缺口 |
|---|---|---|
| Convert | Drop → Raw（內容雜湊身分、寫一次、預覽/套用）；PDF、PPTX、DOCX、TXT、MD；圖片抽出 + 視覺模型說明 | **未接到 Agent**；缺 Excel、HTML、`.ppt`；圖片沒有可點的 `![](…)` 連結；圖中文字僅靠說明；公司端點是否支援看圖未驗證 |
| Ingest | 兩階段規劃（挑頁 → 寫入計畫）、長文件濃縮快取、來源追溯、矛盾標記、預覽與備份 | **未接到 Agent**；規範寫死在程式（非 Skill）；整頁重寫有刪失風險；挑頁時送全部 2007 個標題 |
| Query | 已完成並接上（Skill 1.10.0，benchmark 涵蓋率 0.40，目標 0.50） | 依分層 index 往下找（見 4.1） |
| Lint／Conflict | 靜態 lint、⚠️ 衝突標記、`decisions.md` 與判斷流程 | **未接到 Agent**；沒有「現有文章之間」的語意衝突掃描；沒有過期偵測 |

## 4. 設計

### 4.1 分層 index（Karpathy 的 index，在 2000+ 頁規模下可用）

現有 `index.md` 2910 條、約 36 萬字元，超出 Karpathy 所說「約百個來源、數百頁」的適用規模，
無法每次整份給模型讀。改為：

```
index.md                 總目錄：分類與其子目錄連結
index/market-<市場>.md    每頁一行「雙語」說明（英文 + 繁中）、別名
index/product-<產品線>.md
index/technical.md, index/competitor.md, index/sources-<年>.md ...
```

ingest 與 query 都讓模型「讀總目錄 → 選分類 → 讀子目錄 → 選頁面」，取代挑頁時送全部標題、
以及 query 的關鍵字比對。現有 2910 條由模型分批重新分類，結果預覽後由 owner 核准。

### 4.2 雙語

- 原文頁是唯一正式版；frontmatter 加 `aliases`（英、中、縮寫、型號）與一行雙語 `summary`。
- 若量測後仍不足：自動產生「只供檢索」的翻譯衍生檔（如 `EVM.en.md`），標示為衍生、原文更新即重產、
  不可被引用（答案引用一律回到原文頁）。不採兩份並列正式檔：會不同步、翻譯錯誤會被當證據、成本加倍。

### 4.3 Ingest 由 Skill 驅動

- **基礎 Skill：Karpathy LLM Wiki 規範**（schema）：sources／entities／concepts／syntheses、index、log、
  lint、每頁 frontmatter、⚠️ 矛盾行、`decisions.md` 為最終。取代程式內寫死的 `DEFAULT_CONVENTIONS`。
- **domain matrix Skill（此 vault 客製）**：5 市場 × 4 產品線的頁面範本與抽取規則，例如產品頁的選件／規格表、
  市場頁的需求與趨勢（附日期）、競品只收官方或第三方說法；ingest 先判斷 raw 屬於哪些市場 × 產品格。
- **綜合頁**：raw 觸及某市場 × 產品格時，同步更新該格的綜合頁（寫明來源）；好的 query 答案可經核准
  存回為綜合頁（Karpathy：answers filed back）。

### 4.4 寫入安全

- 由「整頁重寫」改為段落層級操作（新增段落、取代某標題下內容）。
- Host 拒絕會刪除既有「有來源」內容的計畫，除非明確標示為更正並附來源。
- 套用前檢查：每條事實有來源連結、frontmatter 完整、連結可解析（缺頁建 stub）。

### 4.5 Convert 補齊

- **Excel**：工作表中的表格以 Markdown 表格保存；**圖表 → 數字表格 + 分析總結**（由模型依圖表資料撰寫，
  標示為模型說明）。
- **HTML**：正文抽取（去除導覽、廣告），保留表格與圖片。
- **`.ppt`**：轉成 `.pptx` 後沿用現有抽取（需確認可用的轉換方式）。
- **圖片**：每張圖輸出「說明 + 可點的圖片連結 `![](assets/…)` + 圖中文字（OCR）+ 原頁文字」，
  圖片檔照 Karpathy 建議存在本地 assets。
- 先驗證公司端點是否支援看圖；不支援時需 owner 指定可用的視覺模型。

### 4.6 Lint／Conflict

- 保留靜態 lint。
- 新增**全庫語意衝突掃描**：依實體／主題把互相連結的頁面分群，模型比對同一主題的說法，產出衝突報告並加 ⚠️；
  owner 判斷後寫入 `decisions.md`。
- 每條說法帶來源日期；lint 標出可能過期的內容（新舊規格衝突多半是時間造成）。

### 4.7 批次與觀測

- 560 個 raw 可排隊、可中斷續跑；進度與結果寫入 telemetry，Atlas 可看 ingest 進度。

## 5. 分階段

| 階段 | 內容 | 驗收 |
|---|---|---|
| K1 | 接上 Agent：convert、ingest、lint 成為 Bridge 能力；Agent Web「Knowledge」頁（選 vault、drop 預覽、ingest 差異核准）；vault 鎖 | 在獨立測試 vault 跑完 convert → ingest → lint（TASKS 既有待辦） |
| K2 | 分層 index + 雙語別名／摘要；ingest 挑頁與 query 改為循 index | 36 題 benchmark 涵蓋率不低於 0.40、目標 0.50；耗時不惡化 |
| K3 | Karpathy 基礎 Skill + domain matrix Skill；段落層級寫入與刪除防護 | 測試 vault ingest 後無刪失；頁面符合範本 |
| K4 | Convert 補齊：Excel（表格、圖表 → 數字表 + 總結）、HTML、`.ppt`、圖片連結與 OCR | 各格式樣本轉換結果經 owner 檢視 |
| K5 | 綜合頁與「答案存回」；全庫衝突掃描與過期偵測 | 衝突報告經 owner 抽查 |
| K6 | 批次 ingest、telemetry、發布文件 | Atlas 上可看 ingest 進度 |

每階段完成即 commit、更新 TASKS／HANDOFF；影響 query 的階段以 36 題 benchmark 驗證（參考答案沿用，不再花 Claude Code 額度）。

## 6. 待 owner 決定

1. 發布形式採 Agent Web「Knowledge」頁（建議）是否同意。
2. 分階段順序是否同意；K1 用哪個測試 vault（建議另建小型測試 vault，不直接動市場 × 產品 vault）。
3. 若公司端點不能看圖，圖片說明與 Excel 圖表分析改用哪個模型。
4. `.ppt` 舊格式是否仍需支援（需在 Windows 上有可用的轉換工具，例如已安裝的 PowerPoint）。
