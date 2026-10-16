# K01 — AS-IS Architecture & Gap Analysis（Knowledge Strategy）

> 2026-10-17，Claude Code。**Documentation only**：沒有改程式、沒有執行 live benchmark、沒有呼叫模型、沒有連線
> 172.25.228.141、沒有讀取 `%LOCALAPPDATA%` 的 live 安裝或 OneDrive vault 內容。
> 基準：`main` HEAD `ddfdb78d`（2026-10-16）。
> 搭配文件：[KNOWLEDGE_STRATEGY_v1.1.md](KNOWLEDGE_STRATEGY_v1.1.md)、[KNOWLEDGE_STRATEGY_v1.1_DIFF.md](KNOWLEDGE_STRATEGY_v1.1_DIFF.md)、
> [v1.0 原文](KNOWLEDGE_STRATEGY_v1.0_original.md)。

**標記：**
- **[V]** 已讀程式或檔案驗證（附 `path:line`）。
- **[D]** 由 repo 中已 commit 的資料計算（benchmark 結果檔）。
- **[I]** 推論，未以程式或執行驗證。
- **[U]** 未驗證。

行號以 `ddfdb78d` 為準。

---

## 1. 摘要：五個最重要的發現

1. **Tool path 的「10/74」已過時，但仍有殘留根因。** [V][D]
   - 10/74 是 2026-10-07 sample-003（commit `041c746`）的結果。當時聊天模型會改寫 Knowledge 結果。
   - 2026-10-09 起（`0b39228a`，HARNESS_UNIFICATION U5），工具路徑執行同一個 Knowledge Harness，validated 答案直接成為回合答案（`src/agent/gateway.py:808-817`）。
   - U5 之後的 core 集（core-009 至 core-015）：工具路徑可接受 147/182（80.8%），直接路徑 56/70（80.0%）。
   - 殘留根因：
     - 未驗證的結果交回聊天模型、record 被移除，而對話回合沒有 grounding 檢查。
     - 呼叫與否、問題措辭由模型決定。
     - 工具路徑只綁一個 Knowledge Skill。
     - 第一個 validated 結果即結束回合。
     - 答案截斷 12,000 字元。
   - 110 題 sample 集在 U5 之後沒有乾淨的量測：U7 未完成。
   - 詳見 §2。
2. **v1.0 假設的基礎設施不存在。** [V]
   - repo 中沒有 PostgreSQL、Alembic、RLS 或 Object Storage，也沒有多人 Knowledge 伺服器。
   - 沒有 Graph / entity / relation / claim 儲存。
   - 也沒有 `bi_schema.py`、`bi_ingest.py` 或任何 BI entity type。
   - 檢索是 in-memory BM25（`src/knowledge/query.py:4-7`）。
   - Vault 是 OneDrive 共享資料夾，Git 被明確否決（`docs/DECISIONS.md:2076, 2164`）。
3. **Agent Web 已涵蓋大部分 Knowledge 管理流程。** [V] 已有 Drop、Processing、Publishing、Asking；Review 與 Editing 只做到一部分。缺 wiki 頁瀏覽與編輯、衝突決策的 UI 與路由、任何 Graph 介面。Obsidian 只是「人另外打開同一個資料夾」（§3）。
4. **Strategy Manifest DAG 與 Workflow engine 重疊，但兩者不等價。** [V]
   - Workflow engine 是線性步驟，沒有 DAG、條件分支、cancel API，也沒有中途人工核准步驟（§5）。
   - v1.1 不擴充引擎，而是把人工審核放在兩段 Workflow 之間，沿用 sandbox / push。
5. **Review、資料分類與流程規則有既有衝突，必須由 owner 裁定。** [V]
   - KNOWLEDGE_COLLAB 寫「no domain-owner approval」。
   - 但 `docs/PRODUCT_ACCEPTANCE_TESTS.md:197, 218`（E2E-05）仍要求 domain-owner review，`docs/ARCHITECTURE.md:757` 的流程圖也畫了這一步（同節 `:771-772` 則說「Domain approval is a later business decision」）。
   - 現行 `DataPolicy` 讓 RESTRICTED 永遠不能送任何模型（`src/agent/data_policy.py:82-83`）。
   - 沒有任何規則規定 PR 或直接在 main commit；實務上自 2026-10-05 起都直接在 main commit。

---

## 2. Knowledge tool path 調查（原則 6）

### 2.1 文件說了什麼

| 文件 | 說法 | 狀態 |
|---|---|---|
| `docs/HARNESS_DESIGN.zh-TW.md` §7.1 表格與 §11.2 | 工具路徑沒有共用狀態機與 Host checks；答案由對話模型重寫；sample-003：直接 25/34、工具 10/74 | **過時**。同文件 §0.1（2026-10-09 更新）已寫「Knowledge 工具路徑改為直接回傳 Harness 驗證過的答案」 |
| `docs/HARNESS_DESIGN.zh-TW.md` §2 | G4 Workflow/Coding 接共用狀態機、G5 跨領域驗收、G6 Agent Web 證明「仍未完成」 | 已被 §0.1 的 U1–U6 部分取代 [V]：`docs/TASKS.md` 的「Harness unification U1-U6」已勾選 |
| `docs/HARNESS_6_LAYER_STATUS.md`（2026-10-04） | 第 4、6 層 Partial；沒有通用的語意驗收閘門，也沒有 insufficient evidence → re-retrieval 路由 | 底部 2026-10-09 更新指向 HARNESS_UNIFICATION。表格數字仍是 10-04 的 |
| `docs/TASKS.md:1454` | `[ ] Knowledge tool route (owner decision): return the harness's validated answer as is, or route more Knowledge questions to the direct harness.` | **未勾選，但已決定並實作**：`docs/DECISIONS.md:1952`（option a）、`docs/TASKS.md` U1-U6 列、commit `0b39228a` |
| `docs/TASKS.md` 「Harness unification U7」 | `[ ]` 變更後的 benchmark 與 Knowledge Skill 1.6.0 的 retry budget | **未完成** |

### 2.2 程式中的資料流（已驗證）

```text
Agent Web 對話（web.py:2607-2678）
  ├─ 指名 vault / 市場矩陣意圖 / Skill 推斷意圖 → 直接路徑 _knowledge_reply → KnowledgeHarness.ask
  ├─ 有附件 → 關閉 Knowledge 與命令路由（web.py:2615-2617）
  └─ 其他 → Gateway.converse（gateway.py）
        ├─ 工具目錄：每個 vault 一個 knowledge__<vault> 工具（gateway.py:400-433）
        │    模型只能填 question（VAULT_QUESTION_SCHEMA，gateway.py:98-118）
        │    Host 綁定 vault 與 Skill procedure（gateway.py:419-424）
        ├─ 模型呼叫工具 → _execute_conversation_tool（gateway.py:908）
        │    knowledge_harness 已接線（host.py:2063-2065）→ KnowledgeHarness.for_tool（knowledge_harness.py:118-121）
        │    → 與直接路徑相同的 ask()（plan_task / run_harness / Host checks）
        │    → validated：data.knowledge_harness="validated"，保留 record（gateway.py:938）
        │    → 未驗證：status failed，failure knowledge_not_validated，**不保留 record**，
        │      instruction 要模型「Tell the person what is above; anything you add is not from the knowledge base」（gateway.py:940-966）
        └─ 迴圈：validated → 立即以 Harness 答案結束回合，模型不改寫（gateway.py:808-817）
                 否則 → observation（≤16,000 字元，gateway.py:85, 818-826）回到模型 → 模型寫最終答案
```

對話回合的 Host checks 只有 `no_unbacked_action_claim` 與 `named_outputs_exist`（`src/agent/conversation_harness.py:6-10, 32-33`）。**沒有 citation 或 grounding 檢查。** [V]

### 2.3 Benchmark 資料（不重跑，只讀 repo 中的結果）[D]

來源：`benchmarks/knowledge_v1/runs/*/Q*/result.json` 與 `metadata.json`。統計時把 PASS 與 INSUFFICIENT_KNOWLEDGE 都算為「可接受」。

| Run | Commit | 日期 | 工具路徑（可接受 / 題數） | 直接路徑 | 未用 Knowledge |
|---|---|---|---|---|---|
| sample-001 | `ab9cb3ea` | 10-07 | 32/58 | 32/34 | 18 FAIL |
| sample-002 | `c64a724c` | 10-07 | 43/76 | 32/34 | — |
| sample-003 | `041c7463` | 10-07 | 40/74（PASS 10） | 28/34（PASS 25） | 2 SYSTEM_ERROR |
| sample-004 | `08961327`（含 U5） | 10-09 | 0/62：41 NEEDS_HUMAN_REVIEW、21 FAIL `knowledge_not_validated` | 26/33 | 15 SYSTEM_ERROR（14 個 `model_http_error`） |
| core-009 | `0be2b141` | 10-11 | 20/26 | 7/10 | — |
| core-010 | `9d0d74c2` | 10-11 | 20/26 | 8/10 | — |
| core-011 | `43dcd768` | 10-11 | 18/26 | 7/10 | — |
| core-012 | `425c5f61` | 10-11 | 23/26 | 7/10 | — |
| core-013 | `677e18af` | 10-12 | 19/26 | 8/10 | — |
| core-014 | `be6ee03f` | 10-12 | 23/26 | 9/10 | — |
| core-015 | `22e649ce` | 10-12 | 24/26 | 10/10 | — |

讀法：
- 「10/74」是 sample-003 的 **PASS** 數；把 INSUFFICIENT 算入，可接受為 40/74。sample-003 的 34 個工具路徑 FAIL 全是 `REASONING_GAP`，即模型改寫後評審不認可。[D]
- sample-004 是 U5 之後唯一的 110 題 sample。其中 41 題被判 NEEDS_HUMAN_REVIEW，原因是「the trace predates the host record carrying the cited passages」（grader 1.3；record 欄位在稍後的 a18421a / 875d3e3 才加入）。所以 **U5 後的 sample 集沒有有效的工具路徑量測**。[D]
- core 集（36 題）的路由是固定的：每題 26 題走工具、10 題走直接，所以兩條路徑問的是**不同的題目**，不是同題對照。[D]
- core-009 至 015 的工具路徑非可接受原因合計：`REASONING_GAP` 19、`VALIDATION_GAP / knowledge_not_validated` 13、其他 `VALIDATION_GAP` 2、NEEDS_HUMAN_REVIEW 1。[D]

### 2.4 根因（tool path 的殘留弱點）

| # | 根因 | 證據 | 對 Graph backend 的影響 |
|---|---|---|---|
| T1 | **（已修正）模型改寫 Harness 結果。** 10/74 的主因 | U5 前：`docs/HARNESS_DESIGN.zh-TW.md` §7.1；修正：`gateway.py:808-817`、commit `0b39228a` [V] | 若 Graph 以新的聊天工具提供，且不走 Harness，會重現此問題 [I] |
| T2 | **未驗證結果交回模型，且移除 record。** 模型自行寫最終答案，並可加入一般知識；最終答案沒有 grounding 檢查；grader 也無法驗證引用 | `gateway.py:938`（`kept = {"record": ...} if validated else {}`）、`gateway.py:940-966`、`conversation_harness.py:6-10` [V]。sample-004 有 21 題 `knowledge_not_validated` FAIL [D] | Graph 查不到或部分查到時，同樣會落入模型自由回答 [I] |
| T3 | **部分支持的答案在兩條路徑上待遇不同。** 直接路徑：Harness 自己產生「已查到可引用的部分資料…未能以證據支持：…」並原樣顯示。工具路徑：同一結果因 `ok=false` 走 T2 | `knowledge_harness.py:235-268`（partial 文字）、`:283`（`ok` 只在 validated 時為 true）[V]。sample-004 Q0181：`claim_status: supported`、`facet_status: missing`，被判 `knowledge_not_validated` [D] | Hybrid 的「部分 backend 失敗要明示」在工具路徑上會被模型重寫 [I] |
| T4 | **是否呼叫工具、問題措辭都由模型決定。** schema 只用描述要求原句，沒有強制 | `gateway.py:98-118`；core-005 曾因模型加上「cite Raw evidence / focus on X」而縮小答案（同處註解）[V]。sample-001 有 18 題完全沒用 Knowledge [D] | Graph 查詢對措辭與 entity 名稱更敏感 [I] |
| T5 | **工具路徑只綁「第一個」符合條件的 Knowledge Skill**，不依 vault 或 retrieval mode | `knowledge_harness.py:76-91`（`harness_skill` 回傳第一個）、`:118-121`（`for_tool`）[V] | 無法讓某個 vault 用 graph / hybrid、另一個用 wiki [I] |
| T6 | **第一個 validated 結果就結束回合** | `gateway.py:808-817` [V] | Graph 若是另一個工具，融合不會發生，或由模型在工具結果之間完成；混合 Knowledge 與其他工作的問題，其他工作會被截掉 [I] |
| T7 | **回合答案截斷為 12,000 字元**，synthesis 卻可產出更長的答案 | `gateway.py:948` [V]；core-005 review 提到「超過 10,000 字元的答案」（`docs/DECISIONS.md` 2026-10-10 Skill 1.11.0 段）[V] | Hybrid 答案帶關係鏈與引用時會更長 [I] |
| T8 | **量測缺口**：U7 未完成；sample 集在 U5 後沒有有效量測；core 集兩路徑題目不同 | §2.3 [D]、`docs/TASKS.md` U7 列 [V] | 無法用現有數字判斷 tool path 是否仍是最大弱點 |

### 2.5 修正選項（給 Graph 設計用）

| 選項 | 做法 | 優點 | 缺點 |
|---|---|---|---|
| A | Graph 作為另一個聊天工具（`graph__<vault>`） | 實作快 | 重現 T1 / T2 / T6；Hybrid 由模型融合，不可驗證 |
| **B（建議）** | retrieval_mode 放在同一個 knowledge-query 能力與 Harness 內；工具路徑只回傳 Harness 結果 | 工具數不變；融合、去重、缺口檢查與 Host checks 都在 Host；直接路徑與工具路徑行為一致 | 需修改 Knowledge Harness 與 procedure（屬 Harness 變更，需 owner 同意） |
| C | 所有 Knowledge 問題都走直接路徑 | 最簡單 | 已被否決（`docs/DECISIONS.md` 2026-10-07：無法處理混合工作） |

與 B 搭配的小修正（v1.1 ADR-K6、AEP-K02）：
- T2 / T3：partial 結果原樣回傳並保留 record。
- T4：保留使用者原句。
- T5：依 vault 綁 Skill。
- T7：截斷上限對齊。
- T8：完成 U7 量測。

---

## 3. Agent Web Knowledge 頁覆蓋（原則 3）

UI 全部在 `src/host_runtime/web_page.py` 的一個 Python 字串中。路由與處理函式在 `src/host_runtime/web.py`。

- Knowledge 頁是 `<section id="panel-knowledge">`（`web_page.py:1362`）。
- 頁面是三步驟 stepper `#kp-stepper`（`:1372`）：Pull data、Ingest data、Testing data。
- 所有寫入都在個人 sandbox 中進行。
- Installed 頁另有 Ask Knowledge 方塊 `#knowledge-action`（`:1257`）。

| 能力 | 狀態 | 證據 [V] | 缺口 |
|---|---|---|---|
| **Knowledge Drop** | 已實作（只到 sandbox） | 檔案上傳經 `pipeline("drop-add")`；後端 `KnowledgePipeline.add_drop`（`src/knowledge/pipeline.py:461`），上限 50 MB（`:62`），不覆蓋；從 project vault pull（`pipeline.py:249`） | `/api/knowledge/pipeline/call` 的請求上限是 36 MB 的 base64 JSON（`web.py:313, 5455-5462`），所以約 26–27 MB 以上的檔案會被 UI 路由拒絕 [I：依 base64 膨脹 4/3 推算]。聊天附件不進 Knowledge drop |
| **Processing** | 已實作 | convert（`web.py:4777` `start_convert`，背景執行、逐檔進度）；ingest plan / apply；批次 re-ingest（`web.py:4865` `start_reingest`）；進度 `/api/knowledge/progress`；Advanced 中有 lint、adopt legacy Raw、bilingual index | 沒有 Strategy 選擇（只有一條 wiki ingest）；XLSX / HTML 不支援（`docs/TASKS.md` K1.5） |
| **Editing** | 部分 | 只能編輯規則檔（`CLAUDE.md`、`skills/*/SKILL.md`）與問題檔：`write_rule`（`pipeline.py:379`）拒絕其他路徑（`not_a_rule_file`）與 sandbox 範圍外（`rule_outside_scope`）。另有 AI assist pane 與問題編輯器 | wiki 頁無法直接編輯；Raw 依設計不可寫；plan 中草擬的頁面無法在套用前修改 |
| **Review** | 部分 | ingest plan 逐頁 new / changed 比對與矛盾提示，「Apply to this sandbox」；merge 衝突並排、可選保留哪一邊；Reviews 頁 `#panel-reviews`（`web_page.py:1640`），可審 rule_edit 與 test_question 提議 | 沒有明確的 Reject；⚠️ 衝突的裁決與決策紀錄沒有 UI 或路由：`src/knowledge/conflicts.py:72` `append_decision`、`:132` `resolve`、`:90/:118` `clear_conflict(s)` 在 src 中沒有其他呼叫者；沒有 domain-owner 核准步驟（依 KNOWLEDGE_COLLAB 設計） |
| **Publishing** | 已實作，無 Git | push 到 project vault：`web.py:4562` `start_push`，只有 maintainer 可 push（`pipeline.py:750` `may_push`），流程為 merge → benchmark gate → sourced-line 檢查 → 寫入並備份；Refresh Agent 的 Knowledge（`web.py:4953` `refresh_knowledge`，需重啟）；本機 candidate publish（`web.py:4475` `publish_knowledge`） | 沒有 Git（刻意，OneDrive）；不能發佈 Knowledge 到 Shared Platform：平台 publish 只支援 skill / workflow [V 依子代理回報 `platform_publish.py:32`，未逐行重讀] |
| **Asking** | 已實作 | Installed 頁 Ask 方塊 → `POST /api/knowledge/ask`（`web.py:5967`）→ `KnowledgeHarness.ask`；引用表列出 kind、raw_ref、wiki_page、page / slide / section 與段落；對話中走直接或工具路徑（§2） | 引用不是可點連結；無 retrieval_mode 選擇；無 Graph |
| 瀏覽 | 部分 | vault 清單（`GET /api/knowledge/pipeline`）、sandbox 內容、Raw 清單與資料夾篩選 | **沒有 wiki 頁樹或瀏覽器** |
| Obsidian | 最小耦合 | 複製 vault 時排除 `.obsidian`；lint 容忍 Obsidian frontmatter 與 `[[wikilink]]`；`schema.py` 註解說規則在 Obsidian 中編輯 | 沒有 `obsidian://` 連結或 wikilink 渲染；adapter 不存在（只有 `src/knowledge/migrate.py` 的 legacy vault adopt） |
| 多使用者 | 單人 Agent | Agent Web 只聽 loopback，需要 bearer token；所有動作以 `self.runtime.actor` 執行；其他人透過 maintainers 清單與 OneDrive 權限協作 | 沒有每個請求的成員身分（`docs/DECISIONS.md` 2026-10-16 S2 也指出） |

結論：原則 3 要求的 Drop / Processing / Publishing / Asking 都已存在，可直接重用。Editing 與 Review 需補 wiki 編輯、衝突裁決與 Graph 審核。Obsidian 降為 adapter 幾乎不需要拆除任何東西。

Knowledge HTTP 路由（`web.py` 的 POST allow-list 在 `:5401-5411`）[V 依子代理回報；`/api/knowledge/ask` `:5401, 5967` 與 `/api/knowledge/refresh` `:5410, 5579` 已重讀]：
- **GET：** `/api/knowledge/pipeline`、`skill-assist`、`push`、`review-proposal`、`convert`、`progress`、`reingest`、`benchmark`。
- **POST：** `/api/knowledge/ask`、`pipeline/call`（`{step, arguments}`，21 個 step）、`pipeline/publish`、`benchmark/start`、`push/start`、`reingest/start|stop`、`convert/start|stop`、`refresh`、`skill-assist`。

---

## 4. Knowledge 子系統盤點

### 4.1 文件擷取 [V]

`src/knowledge/office.py`：
- `PdfExtractor`（`:84`，`pdf.v1`）：每頁文字與每頁內嵌圖片。**沒有表格模型**，表格以文字順序出現（`:85-86`）。
- `PptxExtractor`（`:121`，`pptx.v1`）：逐張投影片處理文字框、表格（Markdown）與圖片。**不擷取 speaker notes**。
- `DocxExtractor`（`:167`，`docx.v1`）：段落、表格與圖片。sections 沒有頁碼。
- **沒有 OCR。** 圖片以 image section 保存；其文字由 vision 模型描述（`src/knowledge/describe.py`），並以 `described_by` 標記（`src/knowledge/raw.py:61-72`）。
- openpyxl 在 `office` extra 中，但沒有 XLSX extractor [依子代理回報 `pyproject.toml:33`]。

審閱意見說「已擷取 PDF/PPTX/DOCX 含頁、表格、圖片」：PPTX 與 DOCX 正確；**PDF 沒有表格**。

### 4.2 Raw、ID 與 provenance [V]

- `source_id = "src-" + sha256(bytes)[:16]`（`src/knowledge/raw.py:126-131`）：同樣的位元組在任何檔名下都是同一 source。
- `KnowledgeSource`（`src/knowledge/contracts.py:9-16`）。
- Raw frontmatter：`source_id`、`source_sha256`、`original_ref`、`raw_ref`、`extractor`、`created`（`raw.py:37`）。
- 引用：`Citation{kind, source, raw_ref, section, page, slide, wiki_page}`（`src/knowledge/query.py:254-265`）。`section` 是 Raw 文件中的序號。
- **沒有持久化的 passage / evidence ID**：答案的 `[n]` 只在單次合成內編號（`query.py:1449-1456`）。
- 可直接重用作 `document_id` 的是 `source_id`。`evidence_id` 需要新增（v1.1 ADR-K4）。

### 4.3 檢索與合成 [V]

- `src/knowledge/query.py:4-7`：「Retrieval is deterministic and lexical (BM25 over passages, with characters and character bigrams for CJK text…)」。
- 沒有資料庫、FTS 或 embedding；以 vault 檔案樹指紋快取（子代理回報 `query.py:681-727`）。
- 多輪搜尋：`search_rounds.py`。雙語改寫：`query_rewrite.py`。facet 評估：`evidence.py`。Skill procedure：`procedure.py`。

### 4.4 市場矩陣（Graph 的最近似物）[V]

`src/knowledge/market_matrix.py`：
- **ProductFamily** 有 5 個值（`:18-24`）：nonsignaling_wireless、signaling_wireless、signal_generation_analysis、vector_network_analysis、oscilloscope。
- **TargetMarket** 有 5 個值（`:25-27`）。
- `MatrixCell.evidence_level` 有三級：nearby_mention / separate_passages / no_raw_match（`:118-137`）。
- 每格固定 `market_fit_verified: Literal[False]`。
- 計算方式是對 Raw 做一次 regex 詞彙共現。模組自述這是 lead discovery，不是 fit claim（`:1-4`）。
- 注意：knowledge_v1 問題集是 5 市場 × **4** 產品族（signaling 與 non-signaling 合併為一族），矩陣則是 5 × 5 [V `benchmarks/knowledge_v1/README.md`、`market_matrix.py:18-24`]。

### 4.5 Graph / entity / claim [V]

- 沒有 Graph 儲存。
- `wiki/entities/` 只是 Markdown 頁面資料夾。
- `FacetRelation`（`src/knowledge/evidence.py:44`）是單次查詢內的暫時結構。
- 沒有 claim 表。

### 4.6 `bi_schema.py` / `bi_ingest.py` [V，範圍有限]

- 整個 repo 與 `C:\Users\Chi_L\Documents`（深度 6）都找不到這兩個檔名。
- `src/` 中搜尋 `TestSolution|CustomerProduct|\bEcosystem\b` 得到 0 筆。
- [U] 部分 `.scratch/*` 目錄與 Documents 中無權限讀取的目錄未檢查。

### 4.7 衝突與決策 [V]

- `decisions.md` 為 append-only（`src/knowledge/conflicts.py`）。
- planner 會讀取決策（`decisions_text`）。
- `rejected_claims` 回饋給 planner（子代理回報 `evolution.py:379`）。
- 寫入決策與解除衝突的函式沒有任何呼叫者（§3）。

---

## 5. Workflow engine vs v1.0 Strategy Manifest [V]

| v1.0 Manifest 需求 | Workflow engine 現況 | 證據 |
|---|---|---|
| DAG（`needs`） | **線性**：`steps: tuple[...]`，依序執行；步驟輸入可取自先前步驟（`StepInput`） | `src/common/assets.py:268-273, 514-527`；`engine.py` docstring |
| 條件分支 | 無 | 同上 |
| 有限重試 | 有，只限 read 步驟、`transient_failure`、最多 3 次（`RetryPolicy` `le=3`） | `assets.py:261-265`；`docs/HARNESS_DESIGN.zh-TW.md` §9 |
| timeout | Bridge 逾時；呼叫端等待上限 | `docs/HARNESS_DESIGN.zh-TW.md` §9–10 |
| checkpoint / 復原 | 有：write-ahead journal、`SqliteCheckpointStore`、`recover` 要求同一版本已安裝且未改變 | `src/workflow/checkpoints_sqlite.py`、`engine.py` `recover`（子代理回報 `:1238-1250`） |
| 人工審核暫停 / 恢復 | **無引擎內步驟**；suspend 是人工確認；排程有 per-run approval（`host_runtime/schedules.py`） | 子代理回報 `journal.py`、`schedules.py:511-574` |
| 取消 | **無** engine cancel API | 子代理回報 |
| 版本釘選 | 有，`namespace/name@version` | `engine.py` `InstalledWorkflows` |
| telemetry | 有，`workflow_run` | 遙測契約 §3 |
| 拒絕未知 Skill / 不安全模型 | Bridge 授權與 preflight（能力已安裝、非 read 步驟不得重試） | `docs/HARNESS_DESIGN.zh-TW.md` §9–10 |

推論 [I]：v1.0 的 Manifest 若實作，會成為第二個執行器，與 `AGENTS.md` 規則 2、4、11 以及 HARNESS_UNIFICATION（「the separate loops were history, not need」，`docs/DECISIONS.md:1952-1955`）衝突。缺少的「人工暫停」可以用既有的 sandbox candidate → 審核 → push 表達，不需要改引擎。

---

## 6. 儲存、多人與 Shared Platform [V]

- **Host 的 SQLite：** `host_runtime/state.py`（`SqliteLocalState`）、`schedules.py`、`experience*.py`、`skill_suggestions.py`、`workflow/checkpoints_sqlite.py`、`telemetry/store.py` [依子代理回報]。
- **Shared Platform 的 SQLite：** `control_plane/registry_sqlite.py`（packages、artifacts、name_owners、name_access）、`identity_store.py`、`feedback.py`、`submissions.py` [依子代理回報]。
- 平台在 172.25.228.141，使用固定憑證指紋（`docs/DECISIONS.md` 2026-10-16）。
- **PostgreSQL / Alembic / RLS / Object Storage：** src、deploy、docs、pyproject 都沒有。唯一提到 object storage 的是一份「out of scope」說明 [V 子代理；`docs/ROADMAP.md:312` 已重讀]。
- **沒有任何「選 SQLite 不選 PostgreSQL」的決策。** 每個 SQLite 都是依功能各自決定的。
- **身分：** Shared Platform 有成員帳號、密碼（scrypt）、device binding、token 指紋（`control_plane/identity.py`、`member.py`）。Agent Web 只有單一 `runtime.actor`。
- [I] 在 OneDrive 共享資料夾中放 SQLite 檔案，有與 `.git` 類似的同步損壞風險。這是 v1.1 ADR-K2 選項 A 把 Graph 真實來源放在檔案、只把 SQLite 當 Host 本機衍生索引的原因。

---

## 7. 資料分類與「外部模型」[V]

- `src/agent/data_policy.py:11`：`DataClass = PUBLIC | INTERNAL | CONFIDENTIAL | RESTRICTED | UNCLASSIFIED`。
- 未知永不當 PUBLIC（`:16-23`）。
- 原生 agent backend 只收 PUBLIC（`:128-137`，`native_requires_public`）。
- Gateway 需要 host-admin 核准，且**不得核准 RESTRICTED**（`:82-83`）。
- `src/models/approved.py:36-41`：每個 Gateway 模型請求目前視為 UNCLASSIFIED。Knowledge 合成走 `ApprovedModelClient` [依子代理回報 `host.py:1116-1120, 1196`]。
- 每個 vault 一個 `privacy: private|public` 設定（`docs/DECISIONS.md` 2026-10-03）。
- [U] local CLI agent mode 經 MCP `aep_knowledge_*` 取得的 Knowledge 結果，是否再經分類檢查。

---

## 8. Atlas 契約慣例 [V]

遙測契約檔案是 `docs/telemetry/AEP_ATLAS_TELEMETRY_CONTRACT.md`，**v0.3**。

- envelope 的 `schema_version: "aep.telemetry.v1"`，文件版本 v0.x。
- 加選填欄位不升 schema；破壞性變更升 `v2`（§9）。
- 讀取路由：GET、loopback、免 token、只允許本機 Origin（§1 #2）。
- 分頁用 cursor（`next_cursor`、`ingest_seq`）。
- Atlas 必須容忍未知欄位，並保留不完整的 run（§8.4）。
- 屬性不得含內容（§4）。

Atlas 端目前只有遙測消費者，**沒有任何 Knowledge API 契約**。Atlas 端的工作記錄在 Atlas repo（`docs/TASKS.md`）。

v1.1 §6 沿用以上慣例。唯一的差異：Knowledge API 會回傳段落原文，所以「免 token」是否適用需要 owner 決定。

---

## 9. Review Policy 衝突 [V]

| 來源 | 內容 |
|---|---|
| `docs/phases/KNOWLEDGE_COLLAB.md:170-171` | 「Any maintainer listed for the project may push; no second approval is needed (owner, 2026-10-11).」 |
| `docs/phases/KNOWLEDGE_COLLAB.md:281-283` | 「There is no vault lock and no domain-owner approval」 |
| `docs/DECISIONS.md:2133-2145`（2026-10-11 K3） | 「Publishing a merged Knowledge version needs one person's confirm click; per-domain approval was not required.」 |
| `docs/DECISIONS.md:2147-2164`（2026-10-11 branches / PR） | 「Co-developers may push without a second approval」 |
| `docs/DECISIONS.md:2166-2173`（2026-10-11 no lock） | 不加鎖；benchmark gate 決定 |
| `AGENTS.md:25`（規則 15） | 「Department/domain owners validate business correctness」，未特指 Knowledge |
| `docs/ARCHITECTURE.md:160-179, 757, 771-772` | 160-179：contribution 的 business review（department owner）；757：E2E-05 流程圖中發佈前有「domain-owner review」；771-772：「Domain approval is a later business decision and does not replace technical validation」 |
| `docs/PRODUCT_ACCEPTANCE_TESTS.md:197, 218`（E2E-05） | 「publishes a new version after domain-owner review」；criterion 8「A domain owner approval is separate from technical validation and publication」 |
| 部分調和 | sandbox 只能維護一個資料夾（`docs/DECISIONS.md:2322-2333`）；shared page 以 proposal 呈現（KNOWLEDGE_COLLAB:89-91）；domain owner 審 vault-rule proposals（`docs/DECISIONS.md:2280-2286`） |

repo 內**已經存在**的矛盾（E2E-05 / ARCHITECTURE vs KNOWLEDGE_COLLAB）與本提案無關。但任何 BI review policy 都必須先由 owner 裁定以哪份為準。

---

## 10. 協作流程與 CI（實況）[V]

- `.github/workflows/verify.yml`：在 `pull_request` 與 push 到 `main` / `phase-*/**` 時執行。步驟依序為：
  1. `pip install -e ".[dev,office]"`
  2. `pytest`
  3. `ruff check`
  4. `ruff format --check`
  5. `mypy`（`files = ["src", "tests"]`）
  6. `build`
  7. `pip check`
  8. Windows preview 安裝 / 解除安裝
  9. Shared Platform smoke
- 其他 workflow 是 Codex / Hermes 遠端測試與部署驗證的 label 生命週期。只有 `hermes-retest-ready-for-merge.yml` 會為**特定 bot PR** 請求人工 merge reviewer。
- repo 中沒有 branch protection 設定。
- **沒有 DECISIONS 條目規定 PR 或直接 commit。** 最後兩個 merge commit 在 2026-10-05 與 2026-10-01；之後都直接在 main commit。HANDOFF 多處寫「Committed on main, not pushed」。
- `docs/TASKS.md:74`（較早的 E2E 表格）：「A row says `done` only after its pull request merges.」
- `AGENTS.md:35-36`：「Each migration PR should be narrow…」。
- `.agents/skills/*`：六份程序。都要求 commit 與 handoff，**沒有任何 PR 規則**。
- 文件測試：**沒有任何測試解析** `docs/TASKS.md`、`HANDOFF.md`、`docs/README.md` 或 `DECISIONS.md`。有讀 docs 的測試只檢查特定文件（`docs/remote-testing-codex-loop.md`、`docs/deployment-validation-loop.md`、`docs/phases/LLM_GATEWAY.md` 等）[依子代理回報，並以 §11 的測試執行佐證]。
- Active product gate：E2E-01（`docs/PRODUCT_ACCEPTANCE_TESTS.md:282-330`；`docs/TASKS.md:132` owner validation pending）。依 CLAUDE.md，本提案不得取代 active gate。

---

## 11. v1.0 主張逐項核對

| v1.0 主張 / 假設 | 現況 | 標記 |
|---|---|---|
| PostgreSQL、Alembic、RLS、Object Storage | 不存在 | [V] |
| `/api/v1/knowledge/*` 多人伺服器 | 不存在；有 Agent Web 的 `/api/knowledge/*`（單人、loopback） | [V] |
| Obsidian Vault + Index 是 Wiki 發佈目標 | vault 是 OneDrive 資料夾；索引在記憶體中；Obsidian 只是另一個開啟方式 | [V] |
| `bi_schema.py`、`bi_ingest.py`、11 個 BI entity type | 不存在 | [V]（範圍限制見 §4.6） |
| Strategy Manifest DAG 需要新執行器 | 與 Workflow engine 重疊；引擎無 DAG / 人工步驟 / cancel | [V] |
| Atlas 已有共同契約 | 只有遙測契約 | [V] |
| 依 Claim Domain 分派 BD / PM / AE 審核 | 與 KNOWLEDGE_COLLAB 衝突；與 E2E-05 一致 | [V] |
| 「每 Issue 一 PR、不得自行 merge」 | 與近期實務不同；沒有規則規定任一方式 | [V] |
| 「外部模型」 | v1.0 未定義；repo 有 `DataPolicy` 與 BackendKind 可直接沿用 | [V] |
| Multimodal：表格保留合併儲存格、圖表 embedded series、OCR | 無 OCR；PDF 無表格；圖表只有 vision 描述 | [V] |
| 目標情境、問題集、baseline | v1.0 未提供；repo 有 knowledge_v1（1,100 題、36 題 core、參考答案與 0.50 涵蓋率目標） | [V] |

---

## 12. 過時或不一致的文件（本次不修改，列為後續）

1. `docs/HARNESS_DESIGN.zh-TW.md` §7.1 表格與 §11.2：工具路徑「自己重寫」、10/74。已被 §0.1 與 U5 取代。
2. `docs/TASKS.md:1454`：「Knowledge tool route (owner decision)」仍是 `[ ]`，但已決定並實作。
3. `docs/HARNESS_6_LAYER_STATUS.md`：表格仍是 2026-10-04 狀態。
4. `docs/TASKS.md:20-22`：說決策記錄在 `docs/PHASE_N_MIGRATION.md`、「rather than in one `docs/DECISIONS.md`」，已過時。
5. `AGENTS.md` 規則 3 仍描述 n8n 為可選整合；`docs/DECISIONS.md:808-817`（2026-10-04）決定不用 n8n。
6. `HANDOFF.md` 多個段落累積且都標「— latest」，與 CLAUDE.md「每次重寫」不一致。
7. `src/knowledge/__init__.py` docstring 寫「no ingestion or retrieval runtime yet」[依子代理回報]。
8. ARCHITECTURE 沒有 Knowledge 協作（sandbox / push）、Atlas 遙測或 Harness 統一的段落。
9. Task ID 衝突：`docs/TASKS.md` 已有 Knowledge pipeline release 的「K1–K6」。本提案的 AEP-K02… 容易與之混淆（v1.1 §8 Q12）。
10. `docs/TASKS.md:2408` 與 `HANDOFF.md:32` 有一個反斜線遺失的路徑（`C:epci-wkenv`）[依子代理回報]。

---

## 13. 缺口清單 → v1.1 對應

| ID | 缺口 | v1.1 |
|---|---|---|
| G-01 | Tool path 殘留根因 T2–T8 | ADR-K6、AEP-K02 |
| G-02 | 沒有關係型問題集與 Relationship Accuracy 指標 | §5、AEP-K03 |
| G-03 | 沒有穩定的 evidence_id | ADR-K4、AEP-K04 |
| G-04 | 沒有 storage 抽象 | ADR-K2、AEP-K04 |
| G-05 | 沒有 Strategy 概念（只有一條 wiki ingest） | ADR-K1、AEP-K05 |
| G-06 | 沒有 Graph 儲存、抽取、檢索 | AEP-K06、K08 |
| G-07 | 沒有 Graph 審核 UI；wiki 無法瀏覽 / 編輯；衝突決策無 UI | ADR-K3、AEP-K07、K12 |
| G-08 | 沒有 Atlas Knowledge 契約 | ADR-K7、§6、AEP-K09 |
| G-09 | Knowledge 材料一律視為 UNCLASSIFIED；沒有 document 層級分類 | ADR-K8、AEP-K11 |
| G-10 | Review policy 不可設定；文件間已有矛盾 | ADR-K5 |
| G-11 | 協作流程未明文 | ADR-K9 |
| G-12 | 無 OCR、PDF 無表格、無 XLSX / HTML | Phase 2+（原則 8） |

---

## 14. 本次驗證

見 `docs/TASKS.md` 的 K01 列與 `HANDOFF.md` 頂端段落。只改了文件，沒有改程式。
