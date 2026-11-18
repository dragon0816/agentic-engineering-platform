# 模擬 SAP OI → Excel：交付與過程紀錄

日期：2026-11-19（Asia/Taipei）。分支 harness/reliability-141。
Runtime 基線為本分支 reliability commit 57b2da51；本次新增 benchmark 與測試，
未修改 src、BI Knowledge、正式 Host，未 push、PR、merge 或部署。

## 驗收結果

第 6 次完整試跑成功：使用 59 的 gpt-5.6 gateway 與 AEP 原生 Gateway.converse、
BrowserSession、Bridge、既有受限 Python 與 operation ownership。
10 個模型回合、9 次工具呼叫，約 46.90 秒（不含最後瀏覽器關閉與打包）。
網頁篩選匯出 16 列；移除 1 列完全重複與 3 列 Cancelled/Pending，留下 12 列 Booked。
負數及零金額保留；USD 固定測試匯率 32。總額 TWD 13,580。

| Sales | 2026-09 | 2026-10 | Total TWD |
|---|---:|---:|---:|
| Alice Chen | 2500 | 2800 | 5300 |
| Bob Lin | 4700 | 680 | 5380 |
| Carol Wu | 500 | 2400 | 2900 |
| Grand Total | 7700 | 5880 | 13580 |

獨立 oracle 驗證明細身分/時間/客戶/狀態/幣別/金額、公式與儲存值、彙總、
原生 PivotTable source/axis/sum 及全部 cache records。新版 acceptance 另外要求
最後 exporter 驗收通過、conversation answered 及完整匯出 16 列。
answered 單獨只代表完成對話，不能推論業務成功。

## 實際產出順序（不是推測的模型內部思考）

1. 提供 SOP.md 與 task-request.md；模型可見業務規則，不提供 sealed expected.json。
2. 模型透過 browser__operate 開啟 loopback 模擬頁，填日期及 Sales，檢查分頁。
3. 透過瀏覽器下載全部篩選 CSV，原始檔保留在 output/downloads。
4. 模型撰寫 Python normalization script，交由現有 coding__run 執行。
5. 第一次程式把有效筆數誤設為 13，實際得到 12，因此 exit 1。
   工具回饋保留失敗，模型把斷言修為 12 後重跑；未將第一次失敗報成最終成功。
   兩份程式與實際 stdout/失敗內容都在成功 run 的 dialogue/evidence/output/scripts。
6. oi__export 是本案例新增的具契約 benchmark adapter，先驗證 normalized JSON，
   再用 workbook.py 製作兩張表、金額公式及計算快照；pivot_package.py 補上原生
   PivotTable/PivotCache 結構。它不是模型臨時自行實作通用 Excel 引擎。
7. 工具對實際儲存檔做獨立驗收，回傳具型別結果；mandatory failure 會使 Bridge failed。
8. 保存原始模型請求/回應、每次工具參數/結果、程式、CSV、JSON、截圖、驗收與 Excel。
   dialogue.md 是可觀察的模型回應及工具對話，不包含未公開的內部推理。
9. 對成功檔再次執行加強 oracle、負向回歸，產出 SHA-256 清單與此交付包。

## 全部試跑與修正（原始紀錄不覆寫）

| Run | 結果與判定 |
|---|---|
| 1 | fixture 工具接線錯誤，缺少 browser/export 明確 schema；12 回合仍 needs_input，無成品。修為現有 host bridge_tools 介面。這是 benchmark 接線錯誤，不主張為 production 缺陷。 |
| 2 | 網頁匯出與正規化成功，Artifact XLSX export 原生程序 exit 3221226505 (0xC0000409)，缺 native pivot；任務未完成。 |
| 3 | 嘗試 explicit process.exit(0) 無法解決相同 native crash；仍失敗，未認定成功。 |
| 4 | fallback Python 已產出正確 Excel，但 mandatory Artifact render 仍 crash；exporter false、needs_input。舊 validation.json 的 passed=true 是本 benchmark 報表聚合缺陷，已更正邏輯並加測試；此 run 整體判為失敗。 |
| 5 | 移除不可用 native renderer，改從實際 saved cells 建 HTML 檢視；11 回合/10 工具，內容與 exporter 通過。之後另修報表聚合條件。 |
| 6 | 修正後完整重跑，含一次真實 normalization exit 1 → 模型修復 → 重跑，10 回合/9 工具，artifact/exporter/task 均通過。唯一正式交付 Excel 取此 run。 |

另有 authoring preflight 發現 JS Date 路徑將一筆時間改變，獨立 oracle 擋下；
先改顯式 Excel serial 的 prototype，最終 Python 路徑使用 datetime。
尚未確認 Artifact native crash 根因，不能據此宣稱 AEP 引擎缺陷。
run2 曾普通點擊 Export 而在 Downloads 留下同一份虛構 CSV；以 SHA-256 與建立時間
確認後已移入 run2 evidence，後續指定瀏覽器 download 操作。

原始 run4 validation 保留作稽核；attempt-assessments.json 才是修正後整體裁定。
原始 run manifest 也可能列出未納入 bundle 的 SQLite/private browser profile；
交付內容以 SHA256SUMS.json 為準，不假裝原始 manifest 是整包清單。

## 測試與限制

- 最終 focused pytest：38 passed（12 個 benchmark cases 加既有 reliability/ownership/browser）。
- Ruff 全 repo lint/format 通過（1329 files formatted check）；mypy 981 source files 通過。
- 負向控制會拒絕錯總額、錯 FX、錯 cache、錯 pivot 定義、漏分頁資料，
  以及「內容正確但必要 exporter 失敗」或 conversation 未完成。
- 既有 ownership 測試 helper 預設 30ms 容易先 timeout，掩蓋 unknown/ack failure；
  改為 2s，專門 timeout 測試仍顯式使用短期限。未修改 production timeout。
- 未再跑全套。前階段完整 raw suite 是 5315 passed/35 skipped/4 failed，
  其中三個為已證實 baseline BI failure、一個 stale schema assertion 已修；不宣稱全套綠燈。
- 141 未安裝 Microsoft Excel。公式快取為可核對的計算快照，非 Excel 重算證據。
  原生 pivot 可被 openpyxl 與 XML reader 解析，不等同 desktop Excel 已成功刷新。
- 全部 SAP 記錄、客戶與匯率均虛構；不涵蓋真實 SAP SSO、權限、DOM、網路或下載行為。
- 測試 fixture 的 network-rule presence 為 stub，未驗證 production firewall containment。
- 本例為指定 SOP + 既有工具 + 新增 benchmark exporter 的受控驗收，
  不代表任意 SOP/PDF、任意 Excel 都已能正確處理，也不證實歷史 SAP 事件根因。
- 六次開發試跑不能當成成功率或 Codex/Claude 的公平比較 benchmark。

## 公司電腦人工驗收

1. 開啟 sales-oi-pivot.xlsx，確認沒有修復/毀損提示。
2. 點 OI Pivot 的樞紐，確認來源 OI Data!A1:K13、Sales 列、Month 欄、OI TWD 加總。
3. Refresh All，確認 12 筆明細及上述矩陣仍一致，重算 K2:K13。
4. 僅在另存的測試複本改一筆金額並重算/刷新，確認 pivot 隨來源更新。
5. 留下 Excel 版本與結果；通過前保留 desktop_refresh=unverified。
6. 真實 SAP 上線前，再用核准的真實 SOP/欄位/期間建立獨立 expected 結果。

## 交付檔案

- sales-oi-pivot.xlsx：唯一最終產物。
- SOP.md / task-request.md：實際規範及輸入任務。
- dialogue.md：run6 完整可觀察過程。
- generated-scripts/：模型產生的兩版原始程式（保留失敗版，以 .py.txt 保存原文；ZIP attempt 內保留 .py）。
- validation.json / post-validation.json：當次及交付前驗收。
- mock-sap.html：完整虛構資料的可互動離線頁面。
- workbook-review.html：從 Excel 已存儲存格產生，非 Excel 應用程式截圖。
- full-review.zip：六次試跑、模型 JSON、工具結果、原始 CSV、程式、
  當次 source snapshots、最終 source、fixtures、測試、失敗 prototype logs 與此報告。
  attempt 裡的失敗 xlsx 僅是原始證據，不是可交付報表替代版本。
- SHA256SUMS.json：交付檔與 ZIP 的雜湊（清單本身不自我雜湊）。

所有 bundle 檔與 ZIP 內容皆排除瀏覽器 profile、SQLite、環境設定、金鑰及 HTTP headers。
封裝前掃描實際私密值與交付識別字，結果為零命中。
