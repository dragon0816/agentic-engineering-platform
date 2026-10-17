# Knowledge Strategy v1.0 → v1.1 差異摘要

> 2026-10-17，K01（docs only）。v1.0 原文：[KNOWLEDGE_STRATEGY_v1.0_original.md](KNOWLEDGE_STRATEGY_v1.0_original.md)；
> v1.1：[KNOWLEDGE_STRATEGY_v1.1.md](KNOWLEDGE_STRATEGY_v1.1.md)；事實依據：[K01_AS_IS_GAP_ANALYSIS.md](K01_AS_IS_GAP_ANALYSIS.md)。
> 「P1–P10」指 owner 2026-10-17 的修訂原則 1–10（列於 v1.1 §0）。

## 1. 保留（Kept）

| v1.0 段落 | 保留內容 | 備註 |
|---|---|---|
| 目標與不可破壞原則 | 保留 Harness 六層與 coding / workflow / knowledge asking 行為；BI/Wiki 邏輯不寫死於 Harness；改 Harness 前先以測試證明缺口 | 與 P1、`AGENTS.md` 規則 4、`docs/phases/HARNESS_UNIFICATION.md` 一致 |
| 先做 Repo Audit | 先產出 AS-IS gap report | 檔名改為 `docs/proposals/K01_AS_IS_GAP_ANALYSIS.md`（owner 指定） |
| 架構 | Ingestion 與 Retrieval 分開；同一文件可走 wiki / graph / both；Atlas 只經版本化 API、不直連資料庫 | P4、P10 |
| Multimodal Extraction 與 Evidence | 一次解析、Wiki/Graph 共用穩定 evidence_id；模型產生的文字（圖片描述）須標記來源 | 現有 `RawSection.described_by`（`src/knowledge/raw.py:61-72`）已做到「模型的字不冒充來源」 |
| Hybrid Retrieval | EvidenceHit 統一形狀；canonical evidence ID 去重；兩邊由同一文件衍生時不可當兩份獨立證據；分數不可直接比較，用 rank fusion；缺關係不可編造；round/hop/token 上限 | P4、P5 |
| 協作與安全 | 預設 internal；模型後端選擇 server-side fail-closed；只用合成測試資料 | 對齊 `docs/DECISIONS.md` 2026-10-02「Initial backend data rule」 |
| Atlas Contract | 統一 response envelope `{schema_version, request_id, generated_at, data, pagination?, warnings?, error?}`；AEP 負責權限與語意，Atlas 負責顯示 | 加入 `contract_version`，並對齊遙測契約慣例（P10） |
| 驗收 | 既有功能不退化；一份文件雙策略只解析一次；重跑不重複；人工修改保留；Wiki/Graph/Hybrid 可追溯同一來源；循環有界；比較準確率、引用、latency、token、loop | 量化為 v1.1 §5 的門檻草案（P5） |

## 2. 修改（Changed）

| v1.0 | v1.1 | 原因 |
|---|---|---|
| **Strategy Manifest**：自有 YAML DSL（`steps` + `needs` DAG、重試、timeout、checkpoint、human_approval、publish），需自建 JSON Schema 驗證與執行 | **Strategy = Workflow + Skills + Configuration**。執行用既有 Workflow engine（`src/workflow/engine.py`，journal / recover / preflight / 安裝即核准）；步驟是 Bridge capability；領域規則在 Skill；Strategy Config 只是宣告式綁定（id、版本、workflow ref、skill refs、review policy ref、output kind），**沒有 steps/needs** | P1。v1.0 的 DAG 會與 Workflow engine 與 Harness 狀態機重複（K01 §5） |
| human_approval 是 Manifest 內的一個暫停步驟 | 人工審核是兩段 Workflow 之間的邊界：處理 Workflow 產出 sandbox 中的 candidate 後結束；審核在 Agent Web；發佈沿用既有 push / publish | P1、P3；Workflow engine 沒有「中途等人」步驟（K01 §5），不為此改引擎 |
| 架構以 PostgreSQL + Alembic + RLS + Object Storage 為前提 | 定義 **KnowledgeStorageBackend** 介面；Phase 1 PoC 用 Host 本機（vault 檔案 + Host SQLite 衍生索引）；是否採用中央 PostgreSQL 為 **ADR pending** | P2；現況無任何 PostgreSQL（K01 §6），`docs/ROADMAP.md:312` 已把「storage/index technology for knowledge retrieval」列為 open decision |
| Submission API `/api/v1/knowledge/submissions…`（多使用者伺服器） | Phase 1 不新建 Submission server。Knowledge Drop / Processing / Review / Publish 走既有 Agent Web Knowledge 頁與 `/api/knowledge/*`（K01 §3）；對外只新增唯讀的 Knowledge Query / Graph / Evidence API 給 Atlas | P2（multi-user 留在長期設計）、P3、P10 |
| Obsidian Vault 是 Wiki 的發佈目標 | **Agent Web 是主要 Knowledge Management UI**；Obsidian 降為可選的 Legacy Import/Export Adapter | P3 |
| 審核：依 Claim Domain 分派 BD / PM / AE / Account Owner | **Review Policy 可設定**。General Wiki 維持 `docs/phases/KNOWLEDGE_COLLAB.md`（無 vault lock、無 domain-owner approval、benchmark gate）；BI Knowledge 可**提議** Domain Owner Review Policy，但先列出與既有決策的衝突，不改既有決策 | P7 |
| 對照 `bi_schema.py` / `bi_ingest.py` 與 11 個 BI entity type | 這些檔案在 repo 中不存在（K01 §4.6）。v1.1 的 Graph schema 以現有 `src/knowledge/market_matrix.py` 的 market × product family 為種子，BI entity types 改為 owner 待提供的輸入（Open question） | 事實修正 |
| 驗收以敘述列出 | 三種 benchmark（Wiki-only / Graph-only / Hybrid）、25 題關係型問題草案、六項指標定義與量測方式、量化門檻（**待 owner 確認**） | P5 |
| Issues：K01–K10，每項獨立 PR，不得自行 merge | Issue 草案 AEP-K02 起依序、皆以 owner 核准 K01 為閘門；PR 流程與「main 直接 commit」之選擇列為 **ADR pending（協作流程）**，不預設 | P9；repo 近況是在 main 直接 commit 並記錄在 `docs/TASKS.md`（K01 §10） |
| 「外部模型」未定義 | 明確定義 internal Gateway / external CLI agents（Claude Code、Codex、Copilot）/ 其他雲端模型三類，並對齊既有 PUBLIC 規則與 per-vault `privacy` | 審閱意見；`docs/DECISIONS.md` 2026-10-02、2026-10-03、2026-10-12 |
| Atlas Contract 名稱 `KNOWLEDGE_ATLAS_API_CONTRACT_v1` | `schema_version: "aep.knowledge.v1"`（envelope）＋文件版本 `contract v0.1`，沿用 `docs/telemetry/AEP_ATLAS_TELEMETRY_CONTRACT.md` 的版本慣例（加欄位不升版、破壞性變更升 `v2`） | P10 |

## 3. 移除或延後（Removed / Deferred）

| 項目 | 處置 | 原因 |
|---|---|---|
| 自有 Strategy Manifest DSL 與執行器 | 移除 | P1 |
| PostgreSQL `kg.*` schema、Alembic migration、RLS | 延後；成為 KnowledgeStorageBackend 的一個候選實作 | P2、P8 |
| Object Storage（原始檔） | 延後；Phase 1 原始檔仍在 vault `drop/` | P8 |
| OCR、進階圖表理解（embedded series、vision_estimation） | 延後 | P8；`src/knowledge/office.py` 無 OCR（K01 §4.1） |
| Submission 狀態機（created→…→partially_published）、outbox/reconciliation | 延後；Phase 1 沿用 sandbox / plan / apply / push 的既有狀態 | P2、P3 |
| 病毒 / ZIP 掃描、URL SSRF 防護、rate limit | 延後到「多使用者 Shared Knowledge Service」階段；Phase 1 沒有對外上傳入口 | Phase 1 範圍 |
| Atlas 端 `/quality/*`、`/conflicts`、`/feedback`、`/reviews/queue`、`/strategies/runs` | 延後到 contract v0.2+；v0.1 只有 Query / Graph / Evidence | P10「minimal」 |
| `auto` 策略建議 | 延後 | 先證明兩條固定策略 |

## 4. 新增（Added）

| 新增 | 位置 | 原因 |
|---|---|---|
| AS-IS vs TO-BE 架構圖 | v1.1 §1 | 任務要求 |
| Existing Component Reuse Matrix | v1.1 §2 | P1、P8、P9 |
| 9 份 ADR 草案（含 pending） | v1.1 §3 | 任務要求 |
| **Knowledge tool-path 調查與修正方案** | K01 §2、v1.1 ADR-K6 | P6：v1.0 未提及；現況 tool path 已於 2026-10-09 改為直接回傳驗證過的答案，但仍有殘留根因（未驗證結果交回聊天模型改寫、模型決定是否呼叫及問題措辭、單一 Skill 綁定、第一個 validated 結果即結束回合等）。Graph backend 若作為另一個工具會重現這些問題 |
| Agent Web Knowledge 頁覆蓋盤點（Drop / Processing / Editing / Review / Publishing / Asking） | K01 §3 | P3 |
| 關係型問題集草案（25 題）與 baseline 程序 | v1.1 §5 | P5 |
| 量化 MVP 門檻（待 owner 確認） | v1.1 §5.5 | P5 |
| Atlas Knowledge API v0.1 草案（OpenAPI 風格＋pydantic 友善 JSON） | v1.1 §6 | P10 |
| 需要修改的 repo 規則 / 文件清單 | v1.1 §7.3 | P9 |
| 編號衝突提醒：`docs/TASKS.md` 已有 Knowledge pipeline release「K1–K6」 | v1.1 §7、§8 | 避免 AEP-K02 與既有 K2 混淆 |
| 過時文件清單（10/74 數字、`docs/TASKS.md:1454` 未勾選、HARNESS_6_LAYER_STATUS 等） | K01 §12 | 事實修正 |

## 2026-10-17 修訂：ADR-K6 改為通用規則

owner 問「為什麼有專為 Knowledge 客製的 Harness」後決定：ADR-K6 的四項修正改寫為**所有領域適用的
通用接合規則 G1–G4**（未通過驗收的結果不交模型改寫、使用者原句優先、Skill 依綁定資產選擇、輸出長度
一致），寫進對話 Harness 而非 Knowledge 特例；並說明 `knowledge_harness.py` 是領域 adapter（只提供
execute 與 validate），不是另一套迴圈。AEP-K02 改名為 "Apply the generic Harness hand-off rules G1–G4
and measure U7"，驗收要求以 Knowledge 與至少一個非 Knowledge 領域各驗一次。
