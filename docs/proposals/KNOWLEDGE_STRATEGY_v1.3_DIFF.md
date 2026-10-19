# Knowledge Strategy v1.2 → v1.3 差異摘要

> 2026-10-19，documentation, contract and benchmark-data only（`src/` 沒有變更，未開始 AEP-K02）。
> v1.2：[KNOWLEDGE_STRATEGY_v1.2.md](KNOWLEDGE_STRATEGY_v1.2.md)（保留不改，作為歷史）；
> v1.3：[KNOWLEDGE_STRATEGY_v1.3.md](KNOWLEDGE_STRATEGY_v1.3.md)。

## 1. 起因

- **owner 提供真正的 BI 工具與範例 vault**（`bi_schema.py`、`bi_ingest.py`、`bi_slides_extract.py`、`bi_concept_candidates.py`、prompts、samples、`BI/` 卡片）。
  同日 owner 核准以測試資料 commit：`tests/fixtures/bi_vault_example/`（e30cd8bf）。
- **owner 的問題：** Application 的 `priority` 合理嗎？大家一直調會不會亂掉？
- **owner 分享的 Codex「BI Knowledge Source Brief v6」**：對同一份範例資料的稽核。v1.3 的以下內容**來自這份 Brief**，並經 Claude Code 逐項對照 fixture 檔案核實（附 `檔案:行`）：
  - Node 是 8 個不是 7 個；
  - `bi_schema.py` 的結構事實（欄位種類、virtual `title`、`product_name`、tail 欄位、`reliability` ≠ verified、`lifecycle` 與 `test_stage_now` 不同列舉、`launch_window` 是文字、缺連結目標只警告、Opportunity 只在 README）；
  - 資料品質問題 DQ-1–DQ-9；
  - Dashboard 注意事項；
  - Case A 為第一條垂直流程及其最低驗收清單，以及 Case B–E 的順序；
  - 第二組 8 題範例 vault 題。
  - Brief 把幾件已決定的事列為待決（第一批使用者、25 題與 0.70、U7 / G1–G4、Atlas 由另一個 agent 以 mock 建置），也重複了「vault 用 Git」的舊錯誤（DECISIONS 2026-10-11 已否決：OneDrive 同步會損壞 `.git`）。v1.3 不重開這些。

## 2. N1 解決：Schema v0 → v1

| 項目 | v1.2 | v1.3 |
|---|---|---|
| 欄位名稱來源 | BI 簡報；10 個連結名稱 provisional | `bi_schema.py`（以 `ast` 讀取產生 `bi_schema_v1.json`；每個名稱附 `bi_schema.py:<行>`，測試逐行比對、sha256 釘住） |
| provisional 連結 | 10 個 | 5 個確認、5 個改名（Application `nodes`、CustomerProduct `inferred_applications` / `chipset_modules`、Ecosystem `technologies`、Account `key_suppliers`）；v0 `mentions` = 程式的 `related` |
| 關係 | 14 名稱 / 22 組合 | 25 名稱 / 37 組合（33 出自程式，4 個 proposed） |
| 類型 | 12 個 `source-bi-doc` | 11 個 `source-bi-schema-py`；Opportunity `proposed`（程式沒有） |
| Node | 7 個 | **8 個**（範例 vault；模組拆成天線模組與 RF 前端模組） |
| 屬性 | 多數 provisional 名稱與提議列舉 | 程式的名稱、種類、列舉、預設與必填；差異逐條見 `bi_schema_v1/README.md` §3 |
| `competing_solutions` | range TestSolution | 同；範例 vault 指向 Competitor（公司）卡 → 新增 proposed `competing_vendors` 與型別檢查規則 |
| v0 | — | `bi_schema_v0/` 保留不改（測試釘住 sha256） |
| upcast | `bi_schema_v0.json` 的 `upcast` 原則 | `bi_schema_v1.json` 的 `upcast_from_v0`：type / record / property / relationship 對照與 value map；mock 與 benchmark 已依此升級。修訂一處：改名的關係重算 `relationship_id`，claim 內容不變、指向依 `relationship_id_map` |

## 3. 新增章節

| 章節 | 內容 |
|---|---|
| §0.3 | 2026-10-19 的輸入與決定；「已決定、不重開」清單 |
| §4.3（改寫） | Schema v1 摘要 |
| §4.4（新） | 實際 BI 管線（14 步，附行號）；對應到兩條 Strategy（`bi_card_import`、`bi_knowledge_graph`）= Workflow + Skills + Config；重用 / 新建 / 不得重複；Obsidian 專屬部分只在 Legacy Adapter；「不覆蓋人工內容」對 storage 介面的意義 |
| §4.5（新） | 資料品質問題 DQ-1–DQ-9，各有規則與驗收檢查 |
| §4.6（新） | Dashboard 注意事項：過期用 `file.mtime`、confidence 分布跳過無欄位的卡、無方案查詢把 planning 算成覆蓋；定義「已建立 / 可銷售 / 我方」方案 |
| §4.7（新） | Case A 垂直流程與 9 項最低驗收；Case B–E |
| ADR-K11（新） | Judgement 欄位與欄位層級 provenance：欄位分類、`field_provenance`、匯入不覆蓋 human 值（成為待審提議）、歷史與復原、base_version 編輯流程、priority 評分準則草案、單一 vs 分團隊 / 期間（建議 Phase 1 單一，pending） |
| ADR-K2 介面 | 新增 `fields`：`set_field`（base_version）、`propose_field`、`field_history`、`revert` |
| ADR-K10 | 演練結果：只改資料與 config 就完成 v0 → v1 |

## 4. MVP 範圍與 issue 草案

| Issue | v1.2 | v1.3 |
|---|---|---|
| AEP-K03 | 假 `bi.schema/v1` | 真正的 `bi.schema/v1` + `upcast_from_v0`，結果須與 repo 中升級後的 mock 一致 |
| AEP-K04 | evidence id + storage backend | 加 ADR-K11 `fields` 介面與驗收（過期編輯被拒、匯入不覆蓋 human 值、可復原） |
| AEP-K06 | Schema v0 抽取 | Schema v1；重用 `office.py`；多類型分派與核准步驟明確建模；依賴 K14 |
| AEP-K07 | 審核表 | 加 mapping 預覽、逐卡 diff、欄位編輯與待審欄位提議 |
| AEP-K13 | pending D3 | **done**（2026-10-18） |
| **AEP-K14（新）** | — | BI 卡片匯入能力（Case A）：**以 AEP 能力重寫 `bi_ingest.py` 的行為，不 import 該檔**；以 fixture samples 做對照測試 |
| **AEP-K15（新）** | — | Legacy Obsidian Import / Export Adapter（frontmatter、`[[連結]]`、模板、Dataview 只在這裡） |
| **AEP-K16（新）** | — | 第二組 8 題的 runner |
| 範圍表 | — | 新增 Case A；投影片 OCR 仍屬後期 |

**為什麼重寫而不是包裝 `bi_ingest.py`：** 它是 CLI（`sys.exit`、`print`）、有模組層級全域狀態（`ALIASES`）、直接寫 Obsidian 檔案（繞過 sandbox / gate / push）、沒有測試，而且 merge 會覆蓋人工欄位值。它的**規則**（別名、正規化、mapping 語法、冪等）是有價值的規格：別名與列舉別名已成為 Schema v1 的資料，行為由 AEP-K14 以對照測試重現。

## 5. 契約、mock 與 benchmark

- **Knowledge API v0.1（凍結前修訂）：** `relationship_type` 改為 v1 的 25 個名稱；`Relationship.origin` 改為 `source-bi-schema-py` / `proposed`；`Entity` 加選填 `record_version`、`field_provenance`；新增 `GET /entities/{entity_id}/history`（`EntityHistory`、`FieldChange`）；`contract_version` 仍是 0.1。對照表在契約 README「Pre-freeze revision」。
- **mock：** 所有 entity 的 properties 依 upcast 改寫（v0 值保留在 `legacy_v0`），`schema_id: bi.schema/v1`；6 種改名的關係重算 id 並同步到 graph、graph_seed、entity_detail、quality_summary；新增兩個 Node（天線模組、RF 前端模組）、兩條 Node `upstream`、一個 `competing_vendors` candidate；每個 judgement 值有 `field_provenance`；新增 `entity_history.json`；strategies 的 schema digest 改為 v1 檔案的 sha256。仍全部合成。
- **benchmark：** 25 題的 33 個三元組改用 v1 名稱，題意與答案不變；新增補充題 SUP-01（priority 的歷史）；新增第二組 `vault_example_questions.json`（8 題，範例 vault 的真實名稱，`draft-unreviewed`，不計入 25 題門檻）。
- **測試** `tests/test_knowledge_strategy_docs.py`：mock 改對 v1 驗證（含 cardinality、型別檢查、Node 參考集、預設欄位、graph 與 relationships 一致）；v0 改為「保留不變」（sha256）與「upcast 涵蓋所有 v0 名稱」；新增 v1 逐行追溯 `bi_schema.py`、judgement provenance、history 一致性、strategy digest、SUP-01、範例 vault 題組對照 fixture。沒有刪除或放寬任何斷言；原本「mock 符合 v0」的斷言因 mock 依設計升級而改為「mock 符合 v1」。

## 6. Open questions 的變化

- **關閉：** N1 欄位名稱；第 8 個 Node；範例 vault 是否可 commit（owner 2026-10-19：可以）。
- **新增：** `competing_vendors` 是否寫回 `bi_schema.py`；link range 推論；priority 準則與範圍；judgement 欄位清單；Opportunity 是否加入程式；講者備註是否擴充 `office.py`；Knowledge API 就地修訂或升 0.2。

## 7. Owner 決定（2026-10-19）：v1.3 就地更新

owner 同日回答 v1.3 §8.2 的七題。本版不另開 v1.4，直接更新 v1.3 與相關契約、mock、benchmark；`src/` 只改了講者備註一項。

| # | owner 回答 | v1.3 變更 |
|---|---|---|
| 1 | `competing_vendors`：「要加」 | Schema v1.1：TestSolution → Competitor、linklist，`origin` 由 `proposed` 改為 `owner-decision-2026-10-19`（新的 origin：owner 決定為正式、`bi_schema.py` 尚未加入）。`competing_solutions` 的 range 仍是 TestSolution，指向 Competitor 的值遷移成 `competing_vendors` candidate 並警告。建議的 `bi_schema.py` 程式行在 `bi_schema_v1/README.md` §8「Changes to apply to the BI tooling」，測試檢查它與 JSON 逐字一致 |
| 2 | priority：「分 market，分期間」 | Application `priority` → `priorities`（每個 market × 期間一筆，provenance 在每一筆裡）；新 JSON `priority_entry`、`priority_scoping`、規則 `priorities_scoped_by_market_and_period`、`upcast_from_tooling`。market = `TargetMarket` 五值 + `unspecified`（定義的子問題留給 owner）；期間 `YYYY-Qn`；單一值升級為 unspecified + 日期所在季；Dashboard 排序規則；評分準則不變。Trend 不分範圍（程式沒有 Trend priority，Dashboard 的是算出值）。mock 的 11 個 Application、`entity_history.json`（`field: priorities` + `scope`）、SUP-01 已改 |
| 3 | judgement 欄位清單、Node 擴充：「接受」 | ADR-K11 第 1 點、§4.3 標 decided；JSON `field_classes_decision`、`node_reference_set` |
| 4 | Opportunity：「要」 | 正式類型（`owner-decision-2026-10-19`）：`name`、`account`、`customer_product`、`test_solutions`、`opportunity_stage`（取代 `hypothesis_status`）、`confidence`、`updated`；建議程式行（類型與列舉別名）在 README §8.2、§8.3；mock 的 5 個 Opportunity 已改 |
| 5 | 講者備註：「我覺得可以」 | `office.py` `PptxExtractor` 升為 `pptx.v2`：講者備註成為該投影片的最後一個 text section，首行 `Speaker notes:`；空白備註不產生；既有 Raw 不重寫；`docs/CONTRACTS.md` 同步；`tests/test_office.py` 新增 3 個測試 |
| 6 | API 版本：「好」 | 二選一的問題，回答有歧義；解讀為接受現行做法（就地修訂、仍是 0.1），**待確認**。契約 README 新增「Second pre-freeze revision」表：`Relationship.origin` 加 `owner-decision-2026-10-19`、`priorities`、`opportunity_stage`、`FieldChange.scope` |
| 7 | ADR-K9：「如果寫好了，可以進main」 | ADR-K9 decided（選項 A）；`docs/DECISIONS.md` 2026-10-19 條目；`AGENTS.md` 補一句 |

測試 `tests/test_knowledge_strategy_docs.py`：沒有刪除或放寬斷言。改寫的斷言（Opportunity 不再是 `proposed` 而是 `owner-decision-2026-10-19`；priority 歷史改依 market × 期間比對）都更嚴格或等價，並新增 `test_owner_decisions_of_2026_10_19_are_in_schema_v1`（README 建議程式行與 JSON 逐字一致、`TargetMarket` 對照、fixture 升級範例、API origin）。Schema v1 檔案變更後，strategies 的 schema digest 已重新釘選。

仍待：N2 正式審閱者、ADR-K8 資料分類、link range 推論、priority 評分準則、market 定義子問題、第 6 題解讀確認、v1.3 整體核准。
