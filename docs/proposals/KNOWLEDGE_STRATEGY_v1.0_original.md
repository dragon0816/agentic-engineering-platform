# AEP Knowledge Strategy — Claude Code 開發交接 v1.0

> 2026-10-17；此文件是目標設計，不代表現有程式已實作。Repo: `dragon0816/agentic-engineering-platform`。

## 目標與不可破壞原則

保留現有 Harness 六層（Routing/Planning/Retrieval/Reasoning/Loop/Validation）及 coding、workflow、knowledge asking 行為。**優先只新增 Strategy、Skills、Adapters、設定**；如需修改 Harness，先以測試證明通用能力缺口，提出最小變更與回歸測試，經負責人同意才改。不得把 BI/Wiki 邏輯寫死於 Harness。遵守 Repo 的 AGENTS.md、CLAUDE.md、PR Review、CI/CD 規範；不得自行 merge/deploy。

## 先做 Repo Audit

Claude Code 必須先讀取最新 `src/`、knowledge preprocessing/finding、Skill Registry、Agent Loop、retrieval、vault storage、auth、telemetry、tests。產出 `docs/knowledge/AS_IS_GAP_ANALYSIS.md`，列出真實程式路徑、可重用元件、缺口與相容性方案。下列 API/名稱為**建議**，不得假設現有。

## 架構

```text
BD / PM / AE -> Submission API -> Auth + Classification + Object Storage
  -> Shared Multimodal Extraction (一次解析、版本化、保留 evidence)
  -> Strategy Registry (auto / wiki / graph / both)
     -> general_wiki: normalize -> classify -> chunk -> knowledge finding
        -> link/conflict check -> human review -> Obsidian Vault + Index
     -> bi_knowledge_graph: classify -> entity/claim extraction -> resolution
        -> relation finding -> evidence verification -> human review -> PostgreSQL KG
  -> Shared Source/Evidence Registry

Question -> Existing AEP Harness -> Retrieval Strategy
  -> wiki_only / graph_only / hybrid
  -> ACL-filtered retrieval -> evidence fusion -> gap check
  -> bounded cross-source retrieval -> grounded answer + citations
Atlas -> versioned Knowledge API (no direct DB access)
```

Strategy 定義流程、條件、版本、Skill 依賴；Skill 執行步驟；Harness 提供通用迴圈與工具調度。不得另建一套專用 Agent Harness。

## Strategy Manifest

```yaml
api_version: knowledge.aep/v1
id: bi_knowledge_graph
version: 1.0.0
kind: ingestion
input_contract: document.extraction.v1
output_contract: knowledge.candidates.v1
steps:
  - {id: classify, skill: knowledge.domain_classifier}
  - {id: extract, skill: knowledge.entity_claim_extractor, needs: [classify]}
  - {id: resolve, skill: knowledge.entity_resolver, needs: [extract]}
  - {id: find, skill: knowledge.relationship_finder, needs: [resolve]}
  - {id: validate, skill: knowledge.evidence_validator, needs: [find]}
  - {id: review, kind: human_approval, needs: [validate]}
  - {id: publish, skill: knowledge.graph_publisher, needs: [review]}
limits: {max_step_retries: 2, max_total_steps: 30, timeout_seconds: 600}
publication: {require_review: true, drafts_searchable: false}
```

使用 JSON Schema 驗證 Manifest；支援 DAG、條件分支、有限重試、timeout、checkpoint、人工審核暫停/恢復、取消、版本釘選、telemetry。拒絕循環依賴、未知 Skill、型別不符與不安全模型。不得執行 Manifest 中的任意程式碼。`auto` 可建議一條或兩條策略，但不代表免審核。

## Submission API（建議）

| Method | Route | 用途 |
|---|---|---|
| POST | `/api/v1/knowledge/submissions` | 建立投遞 |
| POST | `/api/v1/knowledge/submissions/{id}/files` | 上傳/預簽名傳輸 |
| POST | `/api/v1/knowledge/submissions/{id}/complete` | 啟動背景處理 |
| GET | `/api/v1/knowledge/submissions/{id}` | 狀態與執行軌跡 |
| GET | `/api/v1/knowledge/submissions/{id}/candidates` | 草稿與證據 |
| POST | `/api/v1/knowledge/candidates/{id}/review` | 審核/修改/拒絕 |
| POST | `/api/v1/knowledge/submissions/{id}/publish` | 發布核准內容 |
| GET | `/api/v1/knowledge/strategies` | 策略清單 |
| POST | `/api/v1/knowledge/ask` | 混合檢索問答 |

```json
{"domain":"auto","content_type":"auto","classification":"internal","context":null,"strategies":["general_wiki","bi_knowledge_graph"],"source":{"kind":"file_upload"},"idempotency_key":"demo-001"}
```

Metadata 用 JSON Schema 2020-12、型別與 enum 驗證；使用者身分從 token 取得，禁止客戶端冒名。檔案 MIME sniff、大小限制、SHA256、病毒/ZIP 安全掃描、URL SSRF 防護、rate limit、審計。狀態：created→uploading→queued→extracting→routing→processing→awaiting_review→publishing→published；另有 failed/cancelled/quarantined/partially_published。跨 Vault/DB/Index 發布使用 outbox/reconciliation，重跑不得重複發布。

## Multimodal Extraction 與 Evidence

原始 PDF/PPTX/HTML/XLSX/圖像存內網 Object Storage。PostgreSQL `document` 保存 document_id、document_version_id、sha256、classification、ACL、來源、parser 版本。每個 block 保存 block_id、type(text/table/image/chart/diagram)、page/slide、bbox、reading order、上下文、text/JSON、asset URI、擷取方法及品質。表格保留標題、合併儲存格、單位；原生圖表優先抽取 embedded series，截圖推估值標記 vision_estimation，不可當成正式數據。OCR 失敗應標記待審。Wiki/Graph 共用穩定 evidence_id，重新解析保留版本與映射。

## PostgreSQL Knowledge Graph

建議 `kg.entity(id UUID, entity_type, canonical_key, display_name, properties JSONB, schema_version, classification, status, timestamps)`，unique(entity_type, canonical_key)，JSONB GIN index；`kg.relation(id, source_id FK, target_id FK, relation_type, properties JSONB, classification, status)`，雙向索引；`kg.claim(id, subject_entity_id, statement, claim_kind[source_assertion/inference], verification_status[assumed/verified/disputed], review_status, valid_from/to, classification)`；`kg.claim_evidence(claim_id FK,evidence_id FK,role[supports/contradicts/context])`；`document.evidence` 保存 document/version/block/page/excerpt/asset/ACL；再加 relation_evidence、版本/審計、schema_registry。由 Alembic migration 建表、外鍵、索引、RLS/等價權限。

JSONB 可新增領域屬性而不 ALTER TABLE，但每個 Entity Type 需版本化 JSON Schema、欄位字典與驗證。對照既有 `bi_schema.py`、`bi_ingest.py`，維持 dry-run、idempotent upsert、不覆蓋人工內容。BI 類型含 Trend、Technology、Node、Ecosystem、Account、CustomerProduct、Application、TestSolution、Competitor、Concept、Signal；Opportunity 在分析鏈中，需先查現有 schema。Account 與 Ecosystem 不可混淆；來源 `TestSolution.vendor` 空值代表我方方案，分析時另加明確 is_own_solution。所有主張區分宣稱/推論、assumed/verified、draft/reviewed。

## Hybrid Retrieval

`POST /api/v1/knowledge/ask`：

```json
{"question":"Which customers may need Wi-Fi 8 testing and why?","retrieval_mode":"hybrid","domain":"auto","max_rounds":3,"max_hops":3}
```

建立 WikiRetriever、GraphRetriever adapters，統一 EvidenceHit：hit_id、backend、source_document_id、document_version_id、evidence_id、entity_id/claim_id、page/block、text、score、score_kind、classification、review_status、timestamp。Hybrid：兩邊檢索→先套權限→正規化→以 canonical evidence ID 去重→找缺口/矛盾→有限次交叉檢索→整合答案及逐項引用。兩個資料庫由同一文件衍生，不可當兩份獨立證據；不同 backend 分數不可直接比較，需校準或 rank fusion。部分來源失敗要明示，缺關係不可編造。查詢須受 ACL、timeout、round/hop/token 上限約束。

## 協作與安全

BD 審市場/Signal、PM 審產品/方案、AE 審技術、Account Owner 審客戶/商機；依 Claim Domain 分派而非上傳者身分。跨 Domain 關聯由雙方或授權代表審核。審核 UI 提供原始頁面、圖表、既有知識、差異與接受/修改/拒絕/要求證據。預設 internal；未獲核准不得傳至外部模型或 Codex/Claude CLI，衍生摘要與 Log 同樣受控。模型後端選擇必須 server-side fail-closed。只用合成測試資料開發。

## 與 Atlas 共用 API Contract

共同凍結 `KNOWLEDGE_ATLAS_API_CONTRACT_v1`（OpenAPI + JSON Schema）：`GET /api/v1/knowledge/graph`、`/quality/summary`、`/quality/gaps`、`/conflicts`、`/feedback`、`/reviews/queue`、`/strategies/runs`、`/evidence/{id}`。統一 response envelope `{schema_version,request_id,generated_at,data,pagination?,warnings?,error?}`；AEP 負責權限及資料語意，Atlas 負責顯示。

## Issues 與驗收

AEP-K01 Repo Audit；K02 Strategy Registry；K03 Shared Extraction；K04 Submission API；K05 Wiki Adapter；K06 KG Schema/Adapter；K07 Review/Publish；K08 Hybrid Retrieval；K09 Security；K10 Tests/Telemetry。每項 Issue 有獨立 PR 與測試。驗收：既有 coding/workflow/wiki 不退化；一份混合 PPTX/PDF 可走雙策略且只解析一次；重跑不重複；人工修改保留；Wiki/Graph/Hybrid 都能回答並追溯同一來源；跨來源循環有界；權限與外部模型隔離；斷線/失敗可恢復；新增第三個 mock strategy 不需修改 Harness；比較準確率、引用、latency、token、loop 次數。

## 給 Claude Code 的直接指令

先依本文件盤點 Repo 與規範，輸出 as-is gap report 和計畫；確認與 Atlas 的 OpenAPI 契約後建立 Issues，從 P0 小型 PR 實作並跑 CI；不得在未證明必要時重構 Harness、不得自動 merge/deploy，最後回報測試證據與未完成項目。
