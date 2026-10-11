# Harness 缺口修補計畫

日期：2026-10-09　撰寫：Claude Code　狀態：草案，待 owner 審閱
相關文件：`docs/HARNESS_DESIGN.zh-TW.md`（設計說明）、`docs/phases/HARNESS_UNIFICATION.md`（統一切片 U1–U7）、`docs/DECISIONS.md` 2026-10-09

---

## 1. 目前進度

**已完成（U1–U6，2026-10-09，在 `harness-unification` 分支，全部測試 2409 passed）：**

| 切片 | 內容 |
|---|---|
| U1 | 共用核心：可不需 TaskContract 建立計畫；重試可從 execute 開始（修復不重新規劃）；adapter 可命名用盡時的失敗碼 |
| U2 | Coding 跑在共用狀態機上（collect＝計畫、execute＝變更、validate＝宣告的測試、retry＝修復），對外行為不變 |
| U3 | Workflow 跑在共用 Harness 上；Workflow 可宣告輸出檢查（`checks`），步驟成功但輸出不在時判為失敗 |
| U4 | 對話回合的 Host checks：宣稱完成卻沒有成功工具、提到的輸出檔不存在或為空 → 帶原因重試一次 |
| U5 | Knowledge 工具路徑回傳 Harness 驗證過的答案；重試預算由 Skill 決定，重試時擴大檢索 |
| U6 | 草稿修訂刪除步驟需明確聲明；外部 agent 執行已安裝未修改的 Workflow 免核准；文件更新 |

**進行中（U7 驗證）：** 統一前基準 coding_v1 = 19/20（fix-run-015，T08 失敗）；lab 基準 fix-011 執行中。合併後將跑統一後的 coding_v1、lab、knowledge_v1 樣本，並以遙測 `strategy_id` 比對。

---

## 2. 仍存在的缺口（依優先順序）

優先度：**P0** 影響正確性或使用者信任、應最先處理；**P1** 影響品質與可觀測性；**P2** 長期能力。

### P0-1　Host checks 仍以通用規則為主，缺少「任務語意」驗收（第 6 層）

- **現況**：對話回合只檢查「宣稱 vs 實際工具」與「檔案存在且非空」；Workflow 只有三種輸出檢查（存在、非空、資料非空）。coding_v1 T16（只看頂層 input/）、lab C02（覆寫範本公式、填 `N/A` 而非空白）、X02（漏掉逾期發票）這類**內容錯誤**仍抓不到。
- **做法**：
  1. 在 `SkillHarnessGuidance` 增加 **`host_checks`**：Skill 只能從 Host 已實作的檢查類型中挑選並填參數，不能自帶程式碼。
  2. Host 實作第一批**內容檢查器**（皆為確定性、可重複）：
     - `xlsx_formulas_preserved`：輸出活頁簿中，範本原有公式的儲存格仍是公式；
     - `xlsx_blank_not_placeholder`：範本空白欄位不得被填入 `N/A`、`-` 等佔位字；
     - `rows_cover_input`：輸出的鍵值涵蓋所有輸入檔（含子資料夾）中的鍵值；
     - `csv_schema`：欄位名稱與順序符合宣告；
     - `numbers_reconcile`：彙總值等於明細加總（容許誤差）。
  3. Coding Skill（1.8.0）與 Workflow 草稿可宣告這些檢查；失敗時帶具體差異重試。
- **驗收**：每個檢查器都有「刻意錯誤的輸出必須被拒絕」的負向測試；lab C02/X02、coding_v1 T16 的錯誤輸出重放時被判為失敗。
- **需要 owner 決定**：第一批檢查器清單；Coding Skill 1.8.0 是否一併採用（目前暫停中）。

### P0-2　對話重試可能重複有副作用的工具

- **現況**：U4 的重試會重新執行整個 tool loop；若第一次已執行寫入型工具，第二次可能再做一次（目前受核准與 Bridge 互斥鎖限制，但仍可能重複寫檔）。
- **做法**：重試時把第一次的工具結果（名稱、成功/失敗、產出檔案清單）帶入提示，並在 Host 端記錄「本回合已成功的非 read 能力呼叫」；重試中再次呼叫同一能力且參數相同時，直接回傳先前結果而不重做（冪等快取，以 `(能力, 參數雜湊)` 為鍵，只在同一回合有效）。
- **驗收**：測試中第一次寫檔後 Host check 失敗，重試時同一寫入不會被執行第二次。

### P0-3　Knowledge `knowledge_model_failed` 原因未明

- **現況**：合成呼叫偶發失敗，原因未記錄（HANDOFF 已知問題）。遙測現在會記錄每次模型呼叫的錯誤碼與耗時，但 Knowledge 能力內部的合成失敗只回報代碼。
- **做法**：在 `QueryEngine.ask` 的模型呼叫失敗時，把供應商錯誤碼、截斷與否、輸出 token 數寫入遙測（不含內容）；跑 knowledge_v1 樣本後依分布決定對策（提高上限、改用串流、重試策略）。
- **驗收**：樣本執行後能說出失敗的類型與比例。

### P1-1　Knowledge 重試只是「擴大參數」，不是真正的評估→再檢索迴圈（第 3、4 層）

- **現況**：U5 的重試把每個 facet 的查詢全部用上、加大段落數與 Wiki 命中數；但不會依「缺哪個 facet、為什麼缺」改寫查詢。
- **做法**：重試時依 `facet_report` 的缺口產生**針對性查詢**（缺的 facet × 問題主體 × Skill 的 discovery_queries），只對缺的 facet 再檢索；保持 procedure 規則不變。
- **驗收**：knowledge_v1 樣本中「INSUFFICIENT_KNOWLEDGE 且 Vault 實際有資料」的比例下降；G3 第 5 步（線上覆蓋率量測）完成並記錄。

### P1-2　路由層沒有跨領域分類器；JEV 只在 shadow（第 1 層）

- **現況**：路由靠規則與固定順序；JEV 的建議只記錄在 `jev-shadow.jsonl`，未評估是否可啟用。
- **做法**：用 shadow 紀錄與遙測（`skill.selected`、`routing.completed`、run 結果）產生 JEV 對照報告：JEV 的選擇與實際成功工具一致的比例、退回基準的原因分布。達標（由 owner 定門檻）後，先在 `skill_selection` 啟用 active 模式，coding 排除規則保留。
- **驗收**：報告指令可重複產出；啟用前後以 `strategy_id` 比較成功率與延遲。

### P1-3　策略比對報告尚未產品化

- **現況**：遙測已記錄 `strategy_id`，但比較要靠 Atlas（尚未實作）。
- **做法**：新增 `aep-host telemetry compare --since ... --by strategy_id,run_kind,skill_id`：輸出每組的成功率、p50/p95 延遲、平均模型呼叫數、token 覆蓋率、重試率、各 state 停留時間。
- **驗收**：U7 的統一前後比較直接用此指令產出。

### P1-4　Workflow 輸出檢查需要人工宣告

- **現況**：U3 的 `checks` 要由作者（Agent 或外部 agent）主動宣告；多數既有 Workflow 沒有宣告。
- **做法**：草稿試跑成功後，Host 依實際產出**建議** checks（例如 run-python 產出的 `*.xlsx` → `files_nonempty`），在安裝核准卡上顯示，owner 按安裝時一併寫入；既有 Workflow 在草稿清單提供「加上輸出檢查」。
- **驗收**：新安裝的 Workflow 預設都有至少一個輸出檢查。

### P1-5　草稿修訂保護只看「刪除步驟」

- **現況**：U6 只偵測刪除步驟；刪除輸出檢查、把寫入改成只讀、移除參數同樣會讓功能變弱。
- **做法**：比對前後版本的步驟、checks、參數、side effect 等級；功能變弱時一律要求聲明，並在核准卡標示差異。
- **驗收**：每種弱化都有測試。

### P2-1　跨領域驗收（G5）尚無正式測試組

- **做法**：建立 `tests/test_harness_cross_domain.py`：對 Knowledge、Coding、Workflow、對話各給一個**刻意錯誤的輸出**，全部必須被 Host checks 拒絕，且停止原因、遙測 phase 一致。
- **驗收**：此測試組納入 CI；任何領域新增 adapter 必須通過。

### P2-2　上下文管理沒有通用政策（第 3 層）

- **現況**：歷史訊息固定最近 12 則、48,000 bytes；長任務容易遺失早期約束。
- **做法**：把「任務約束」（使用者給的規則、範本、輸出位置）抽成結構化的 task notes，隨每輪附上，不受歷史截斷影響；遙測記錄截斷次數。
- **驗收**：長對話 benchmark（新增 2–3 題多輪任務）不再遺失早期規則。

### P2-3　Codex / Copilot 尚未實測（外部 authoring）

- **做法**：安裝並登入兩個 CLI 後跑 `benchmarks/authoring_v1` r002。
- **需要 owner**：安裝與公司帳號登入。

### P2-4　Atlas 端尚未實作

- 依 `docs/telemetry/AEP_ATLAS_TELEMETRY_CONTRACT.md` §8，由 Atlas 端負責；AEP 端已提供 API 與串流。

---

## 3. 建議執行順序

| 階段 | 項目 | 前置條件 | 驗證 |
|---|---|---|---|
| A（本週） | U7 驗證完成；P1-3 比較指令；P0-3 合成失敗遙測 | 基準 benchmark 完成 | 統一前後比較報告 |
| B | P0-1 第一批內容檢查器＋Skill `host_checks`；P0-2 重試冪等 | owner 確認檢查器清單、Coding Skill 1.8.0 | lab、coding_v1 全跑（GUI 於 owner 不在時） |
| C | P1-1 針對性再檢索；P1-4 建議輸出檢查；P1-5 修訂保護擴充 | B 完成 | knowledge_v1 樣本、authoring 測試 |
| D | P1-2 JEV 評估與啟用；P2-1 跨領域驗收；P2-2 task notes | C 完成、JEV 門檻由 owner 定 | 全套 benchmark＋遙測比較 |
| E | P2-3、P2-4 | 外部條件（CLI 安裝、Atlas） | authoring_v1 r002、Atlas 驗收 |

每一階段：單元測試全綠 → 非 GUI benchmark → GUI benchmark（owner 不在時）→ 以遙測 `strategy_id` 比較 → 寫 findings → 更新 DECISIONS/TASKS/HANDOFF。

## 4. 請 owner 決定

1. P0-1 第一批內容檢查器是否採用上列五種，或增減。
2. Coding Skill 1.8.0（暫停中）是否與 P0-1 一起推出。
3. P1-2 啟用 JEV 的門檻（例如：與實際成功工具一致率 ≥ 90%、退回率 ≤ 10%）。
4. 階段 B 之後是否需要每階段都跑完整 knowledge_v1 樣本（每次數小時）或只在 C、D 跑。
