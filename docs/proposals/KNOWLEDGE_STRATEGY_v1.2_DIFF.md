# Knowledge Strategy v1.1 → v1.2 差異摘要

> 2026-10-17，documentation and contract design only。
> v1.1：[KNOWLEDGE_STRATEGY_v1.1.md](KNOWLEDGE_STRATEGY_v1.1.md)（保留不改，作為歷史）；
> v1.2：[KNOWLEDGE_STRATEGY_v1.2.md](KNOWLEDGE_STRATEGY_v1.2.md)。
> 「D1–D6、D2a」指 owner 2026-10-17 第二輪的決定（v1.2 §0.2）。

## 1. 起因

owner 2026-10-17 回覆了 v1.1 §8 的部分問題：
- D1：第一批使用者與 benchmark。
- D2：BI Schema v0。
- D4：優先順序。
- D5：Atlas。
- D6：重申的架構要求。
- D2a：同日補充，提供「BI 知識庫」文件，並要求 Schema v0 完全保留文件定義的類型與關係。

**D3（Harness 通用規則 G1–G4 或先量 U7）未決定，維持 pending。**

## 2. ADR 狀態變更

| ADR | v1.1 | v1.2 |
|---|---|---|
| K1 Strategy = Workflow + Skills + Configuration | 建議 | **decided**（owner 2026-10-17，D6）；Strategy Config 加 `schema` 欄位 |
| K2 Storage / PostgreSQL | 介面建議、中央 DB pending | Phase 1 不用 PostgreSQL / Object Storage：**decided**（D6）；介面改為型別無關；**中央 DB 仍 pending** |
| K3 Agent Web 主要 UI、Obsidian adapter | 建議 | **decided**（D6），新增 Strategy Selection；Obsidian 永遠不是必要依賴；現有 BI 知識庫是 Obsidian + Dataview，import adapter 的第一個用途 |
| K4 Document / Evidence ID | evidence_id 寫入 Raw，舊 Raw 回填 | **evidence_id 放在 Host 衍生索引，不寫回 Raw**：避免 Phase 7 Knowledge parity（immutable Raw）衝突 |
| K5 Review Policy | 機制建議、BI 內容 pending | Phase 1 只用 `general_collab`（D6：不做完整多人審核）；`domain_owner_review` 仍 pending |
| K6 Harness 通用規則 G1–G4 | 建議 G1–G4 並量 U7 | **pending**（D3）：列出甲（G1–G4）與乙（先量 U7）兩案；新增 E2E-01 衝突說明與回歸計畫（§7.5） |
| K7 Atlas API | 建議 | 機制 **decided**（D5）；Q10 重述為 metadata / content 兩個 scope（待確認）；`POST /query` 延到 v0.2 |
| K8 資料分類 | 定義建議、BI 類別 pending | 不變；Phase 1 的客戶類型只在合成 fixture 上 |
| K9 協作流程 | pending | 不變 |
| **K10（新）** | — | Schema 與儲存、Harness 解耦：schema 是 Strategy Config 載入的資料；backend 型別無關；Harness 不 import BI 型別；換 schema 是 config + migration；v0 → v1 upcast 規則 |

## 3. 新增

| 新增 | 位置 | 原因 |
|---|---|---|
| Owner 決定表（D1–D6、D2a） | v1.2 §0.2 | 記錄 2026-10-17 第二輪決定 |
| Agent Web 能力對照（Drop、Strategy Selection、Processing、Review、Editing、Publishing、Asking、Obsidian），附既有程式位置與規劃的 issue | §1.4 | D6 |
| **BI Schema v0**：12 種類型全部 `source-bi-doc`；14 個關係名稱、22 個 domain 組合（18 個 `source-bi-doc`，其中 8 個名稱出自文件、10 個 provisional；4 個 `proposed-v0`）；文件的規則、缺口檢查、90 天過期規則；JSON Schema 片段，每個屬性標 origin / 頁碼 / name_status | `docs/proposals/bi_schema_v0/`、§4.3 | D2、D2a |
| **BD benchmark v0**：25 題（5 類 × 5），`review_status: draft-unreviewed`，gold triples 用 Schema v0 的類型與 BI 文件的連結名稱 | `docs/proposals/knowledge_benchmark_v0/`、§5.2 | D1 |
| 未審閱 Ground Truth 規則與正式判定前提（≥ 20 / 25 題、每類 ≥ 3、OD 全審） | §5.6 | D1 |
| **Knowledge API v0.1 契約**：OpenAPI 3.1（14 個 GET）、11 份 JSON Schema、19 份合成 mock 與 index、給 Atlas Coding Agent 的 README | `docs/contracts/knowledge-api/`、§6 | D5 |
| 整合排程：Knowledge 軌是既有工作外圍的平行軌 | §7.3 | D4 |
| 共用程式熱點與衝突風險表 | §7.4 | D4 |
| G1–G4 對 E2E-01 的回歸計畫 | §7.5 | D4、D3 |
| 一致性測試（stdlib only）：mock 對 JSON Schema、mock graph 對 Schema v0、benchmark 對 mock | `tests/test_knowledge_strategy_docs.py` | 讓 Atlas 依賴的 mock 不會漂移 |

## 4. 修改

| v1.1 | v1.2 | 原因 |
|---|---|---|
| §5.2 25 題「market × product family」關係題（R01–R25） | 改為 BD / Marketing 五類題目（MT、TE、CP、AT、OD），每題附 Expected Entities、三元組、Evidence Requirements、Expected Answer、Review Domain | D1 |
| §5.5 門檻：Hybrid Answer Accuracy ≥ 0.50；Relationship precision ≥ 0.80 / recall ≥ 0.60 | Answer Accuracy ≥ 0.55 且 ≥ Wiki-only + 0.05；OD 類 ≥ Wiki-only + 0.10；新增 Evidence (c) 模態標示 ≥ 0.90、(d) 獨立文件要求 ≥ 80%；Relationship recall ≥ 0.65、F1 ≥ 0.70；缺口偵測 4 / 4；過期資料提醒 2 / 2；Account ≠ Ecosystem 混淆 0 次 | BD 情境、BI 文件規則 |
| §5.4 baseline 在現行 live Knowledge 上跑 | 主要在合成 fixture 上跑（含客戶類型的題目只在 fixture）；15 題可選擇另在真實 vault 副本上跑 | 措辭必須合成；ADR-K8 |
| §6 API 草案（`/query`、`/graph/entities…`、`/evidence/{id}`、`/documents/{id}`） | 五組最小 API：Entity、Relationship / Graph、Evidence、Quality Metrics、Strategy Run Status；`/graph` 回傳 Atlas graph normalizer 要求的 `{nodes, edges}`，state 使用 Atlas graph_states；gaps 使用 Atlas gap taxonomy；envelope 加 `source`（provenance）；錯誤加 `http_status`、`details`；`/query` 延到 v0.2 | D5、Atlas `applications/rs_knowledge` 的實際格式 |
| §6 entity 類型 market / product_family / application / technology / competitor | 改用 BI Schema v0 的 12 種類型與 14 個連結名稱 | D2、D2a |
| §7 issue AEP-K02 = G1–G4 + U7 | 重新編排（見 §5）；G1–G4 / U7 移到 AEP-K13（pending D3） | D3 未決；D4 要求 E2E-01 不受影響 |
| §4.1 BI Graph PoC 只有 5 種 entity 類型 | 12 種類型；客戶類型只在合成 fixture | D2 |
| §4.1 Phase 1 範圍 | 明示不做 PostgreSQL、Object Storage、完整多人審核；只驗證價值 | D6 |
| §8 open questions 14 題 | Q2、Q3、Q4、Q5、Q13、Q14 記錄答案（§8.1）；其餘重編，並新增 N1（`bi_schema.py` 核對、第 8 個 Node、Opportunity / Signal 連結、Node 擴充、真實卡片匯入）、N2（正式審閱者）、N3（v0.1 凍結） | owner 回覆 |

## 5. Issue 編號對照

| v1.1 | v1.2 |
|---|---|
| AEP-K02 G1–G4 + U7 | **AEP-K13**（pending D3；排在 E2E-01 owner 實機驗證之後） |
| AEP-K03 問題集 + baseline | **AEP-K02** 審閱 BD benchmark + 合成 fixture + Wiki-only baseline |
| — | **AEP-K03** Schema Registry + Strategy Config `schema`（ADR-K10） |
| AEP-K04 Document / Evidence ID + Backend | AEP-K04（evidence_id 改放衍生索引；backend 型別無關） |
| AEP-K05 Strategy Config + General Wiki | AEP-K05 General Wiki Strategy + Strategy Selection 後端 |
| AEP-K06 BI graph PoC | AEP-K06（依 Schema v0） |
| AEP-K07 Graph 審核 UI | AEP-K07 Strategy Selection 與 Graph 審核 UI（放 Knowledge 頁，不碰 Reviews 面板） |
| AEP-K08 GraphRetriever + Hybrid | AEP-K08（G3 未決前不改 `harness_skill`） |
| AEP-K09 API v0.1 + mock | AEP-K09 實作路由（契約與 mock 已在 v1.2 交付；獨立模組比照 `telemetry_api.py`） |
| AEP-K10 三種 benchmark | AEP-K10（加 §5.6 前提） |
| AEP-K11 資料分類 | AEP-K11 |
| AEP-K12 wiki 瀏覽與衝突決策 | AEP-K12 |

閘門不變：**AEP-K02 起全部等 owner 核准 v1.2。**

## 6. 整合排程發現的衝突（摘要；細節見 v1.2 §7.3–7.5）

- **E2E-01：** `tests/test_product_e2e_01.py:11, 331` 直接建構 `agent.gateway.Gateway`，另有 25 個測試檔 import `agent.gateway`。G1–G4 只能在 owner 決定 D3、且 E2E-01 owner 實機驗證完成之後進行，並依回歸計畫。
- **Phase 7：** v1.1 的「evidence_id 寫入 Raw、舊 Raw 回填」會與 Knowledge 平台 parity gate（immutable Raw、content identities）衝突，已改為衍生索引。Phase 7 Knowledge parity 進行時，不在同一份副本上跑 Graph 抽取。
- **Skill suggestions S3（on hold）：**
  - Graph 審核改放 Knowledge 頁，不碰 Reviews 面板與 `experience_proposals.py` / `skill_suggestions.py`。
  - G3 若改 `SkillManifest`，新欄位必須選填。
- **Productization 5（active）：** `web_page.py`（2026-10-01 以來 87 個 commit）與 `web.py`（96 個）是熱點。Knowledge UI（K07、K12）排在 P5 的 slice 之間；K09 只在 `web.py` 加一行掛載。

## 7. 未改變

- P1–P10 修訂原則。
- 「Strategy 不是新引擎」「Graph 不新增聊天工具」「一份文件只解析一次」。
- 六項指標、parity 與不退化規則：保留，只依 BD 情境與未審閱 ground truth 調整。
- ADR-K8、K9 的內容。
- §7.6（原 §7.3）需要修改的 repo 規則清單。

不修改 `docs/DECISIONS.md`、`docs/ARCHITECTURE.md` 或 `src/`。
