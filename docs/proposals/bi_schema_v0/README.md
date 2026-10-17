# BI Schema v0（`bi.schema/v0`，PoC 契約，不是正式 schema）

> 2026-10-17，Knowledge Strategy v1.2（[KNOWLEDGE_STRATEGY_v1.2.md](../KNOWLEDGE_STRATEGY_v1.2.md) §4.3、ADR-K10）。
> 機器可讀版本：[bi_schema_v0.json](bi_schema_v0.json)（JSON Schema 2020-12 片段，pydantic 友善）。
> 合成實例：[../../contracts/knowledge-api/mock/](../../contracts/knowledge-api/mock/)；benchmark：[../knowledge_benchmark_v0/](../knowledge_benchmark_v0/README.md)。
> 一致性測試：`tests/test_knowledge_strategy_docs.py`。

## 1. 來源

**主要來源是 owner 2026-10-17 提供的「BI 知識庫」簡報**（BDM Business Intelligence Knowledge Base，17 頁）。
- 這是內部文件，**沒有放進 repo**；下文只引用頁碼與極短的詞句。
- 它說明：
  - 一條「趨勢到商機」的分析鏈（slide 3）；
  - 各層卡片的意義與關鍵欄位（slide 4–6）；
  - 卡片之間的連結欄位（slide 7）；
  - 我方 / 對手規則（slide 8）；
  - Concept 審閱（slide 9）；
  - 匯入流程（slide 10–11）；
  - 資料品質規則（slide 12）；
  - Dashboard 缺口檢查（slide 13）。
- 目前的 BI 知識庫是 Obsidian + Dataview 的卡片資料夾（slide 1、7），領域是無線通訊市場（slide 1）。

次要來源是 v1.0 提案（[KNOWLEDGE_STRATEGY_v1.0_original.md](../KNOWLEDGE_STRATEGY_v1.0_original.md)「PostgreSQL Knowledge Graph」段）：
- 它列出相同的 12 個類型名稱；
- 它也定義了 claim 與 evidence 的角色。

| origin | 意義 |
|---|---|
| `source-bi-doc` | BI 文件定義的。`name_status: doc` 表示欄位名稱出現在文件中；`provisional` 表示文件描述了這個欄位，但名稱要以 `bi_schema.py` 為準（slide 10：「欄位名稱以 bi_schema.py 為唯一依據」），而該檔案不可得 |
| `source-v1.0` | 只在 v1.0 提案中定義 |
| `proposed-v0` | 本提案新增，盡量少，每項都附理由 |

**仍不可得：** `bi_schema.py`（欄位名稱的唯一依據）、`bi_ingest.py`、`bi_slides_extract.py`，以及 mapping JSON（slide 10–11）。
所有 `provisional` 名稱與列舉值，都要在取得 `bi_schema.py` 後核對，並以 §6 的 upcast 升到 `bi.schema/v1`。

## 2. Entity types（12，全部 `source-bi-doc`）

分析鏈（slide 3）：Trend → Technology → Node → Ecosystem → Product（客戶產品）→ Application → Test Solution → Opportunity。

| Type | 頁碼 | 文件中的意義（摘要） | v0 屬性（origin / name_status） | 預設分類 | label 為內容 |
|---|---|---|---|---|---|
| Trend | 3, 4 | 市場趨勢；鏈的第 1 步 | `measurement_impact`、`our_fit`、`stage`（bi-doc / provisional）；`market_segments`（proposed-v0） | UNCLASSIFIED | 否 |
| Technology | 3, 4 | 驅動趨勢的技術 | `maturity`、`standards_body`（bi-doc / provisional）；影響節點 → 連結 `affects_nodes` | UNCLASSIFIED | 否 |
| Node | 3, 4 | 價值鏈的**固定位置**：文件說共 8 個，列出晶片、模組、手機、CPE、基地台、電信網路、認證實驗室（可辨識 7 個） | `position_set`（proposed-v0：`bi-doc` 或 `proposed-v0-extension`） | UNCLASSIFIED | 否 |
| Ecosystem | 3, 4, 5 | **節點上的供應商與夥伴**（晶片、模組、認證夥伴） | `role`（bi-doc / provisional）；所在節點 → `node`；供應的技術 → `supplied_technologies` | UNCLASSIFIED | 否 |
| Account | 5 | **買我們儀器的客戶**（不在 slide 3 的鏈圖上） | `region`、`customers`（bi-doc / provisional）；所在節點 → `node`；主要供應商 → `suppliers`；`synthetic`（proposed-v0，標記 mock） | CONFIDENTIAL | 是 |
| CustomerProduct | 3, 5 | 客戶推出的產品（slide 3 稱 Product） | `launch_schedule`（bi-doc / provisional）；所屬客戶 → `account`；使用技術 → `technologies`；晶片模組 → `chip_modules` | CONFIDENTIAL | 是 |
| Application | 3, 5 | 該產品需要的量測應用 | `measurement_topic`（bi-doc / provisional）；價值鏈層級 → `node`；相關技術 → `technologies`；`market_segments`（proposed-v0） | UNCLASSIFIED | 否 |
| TestSolution | 3, 6, 8 | 一套測試方案（我方或對手） | `is_own_solution`（source-v1.0，owner 要求）；`product_family`（proposed-v0）；廠商 → `vendor`；對應應用 → `applications`；競品方案 → `competing_solutions` | UNCLASSIFIED | 否 |
| Competitor | 6, 8 | 競爭對手 | `strengths`、`weaknesses`、`product_lines`、`confirmed`（bi-doc / provisional） | INTERNAL | 否 |
| Concept | 6, 9 | 給業務的白話技術解釋 | `one_liner`、`analogy`、`audience`、`review_state`（draft / reviewed）（bi-doc / provisional）；相關技術 → `technologies`；相關應用、方案 → `applications`、`test_solutions` | UNCLASSIFIED | 否 |
| Signal | 6, 11, 15 | 一則外部情報（例如研討會簡報） | `date`、`source`、`reliability`（bi-doc / provisional）；`so_what`（bi-doc / **doc**） | UNCLASSIFIED | 否 |
| Opportunity | 3, 13 | 商機；文件只列名稱（以及 Dashboard 輸出「客戶商機線索」），**沒有定義欄位或連結** | `hypothesis_status`、`market_segments`（proposed-v0） | CONFIDENTIAL | 是 |

所有卡片的共通欄位：`updated`（bi-doc / doc，slide 12、15）、`sources`（bi-doc / provisional，slide 12）。

列舉值（如 `our_fit` 的 high / medium / low、`stage`、`maturity`、`role`、`reliability`）都是提議：文件只給出欄位，沒有給值。

**與 v1.0 類型清單的差異：**
- **名稱：** 12 個名稱相同，沒有增減。
- **語意：** 有以下差異，v0 依 BI 文件：
  - Ecosystem 是供應商 / 夥伴**公司**卡，不是「價值鏈 / 聯盟」。
  - Node 是固定的價值鏈位置清單。
  - CustomerProduct 在鏈圖上叫 Product。
  - Account 不在鏈圖上。
  - Opportunity 沒有欄位。
- **v0 先前草稿的修正：** v0 先前的草稿（在取得 BI 文件前）曾把 Ecosystem 解讀為價值鏈，並自訂了 24 個關係；這些都已依文件改正。

## 3. Relationships

方向與文件的卡片欄位相同：欄位所在的卡片是 subject。文件說明連結寫成 `[[卡片名]]`，Dataview 會自動反向彙整（slide 7）。在 graph 中，反向查詢由 `neighbors` 提供，不另存反向關係。

| 關係（欄位） | domain → range | origin | name_status | 頁碼 |
|---|---|---|---|---|
| `related_tech` | Trend → Technology | source-bi-doc | doc | 7 |
| `affects_nodes` | Technology → Node | source-bi-doc | doc | 4, 7 |
| `node` | Ecosystem → Node | source-bi-doc | doc | 4, 7 |
| `node` | Account → Node | source-bi-doc | provisional（「所在節點」） | 5 |
| `node` | Application → Node | source-bi-doc | provisional（「價值鏈層級」，解讀為連到 Node） | 5 |
| `technologies` | Application → Technology | source-bi-doc | doc | 5, 7 |
| `technologies` | Concept → Technology | source-bi-doc | doc | 7, 9 |
| `technologies` | CustomerProduct → Technology | source-bi-doc | provisional（「使用技術」） | 5 |
| `applications` | TestSolution → Application | source-bi-doc | doc | 6, 7 |
| `applications` | CustomerProduct → Application | source-bi-doc | provisional（鏈的「產品需要量測」） | 3, 5 |
| `applications` | Concept → Application | source-bi-doc | provisional（「相關…應用」） | 9 |
| `competing_solutions` | TestSolution（我方）→ TestSolution（對手） | source-bi-doc | doc | 7, 8 |
| `vendor` | TestSolution（對手）→ Competitor | source-bi-doc | doc | 6, 8 |
| `supplied_technologies` | Ecosystem → Technology | source-bi-doc | provisional（「供應的技術」） | 4 |
| `suppliers` | Account → Ecosystem | source-bi-doc | provisional（「主要供應商」） | 5 |
| `account` | CustomerProduct → Account | source-bi-doc | provisional（「所屬客戶」） | 5 |
| `chip_modules` | CustomerProduct → Ecosystem | source-bi-doc | provisional（「晶片模組」） | 5 |
| `test_solutions` | Concept → TestSolution | source-bi-doc | provisional（「相關…方案」） | 9 |
| `account` | Opportunity → Account | **proposed-v0** | — | 理由：文件沒有定義 Opportunity 的連結（slide 3、13），但商機必須指向客戶 |
| `customer_product` | Opportunity → CustomerProduct | **proposed-v0** | — | 理由：鏈的第 5 步到第 8 步 |
| `test_solutions` | Opportunity → TestSolution | **proposed-v0** | — | 理由：鏈的第 7 步到第 8 步（我方方案） |
| `mentions` | Signal → Trend / Technology / Account / CustomerProduct / Ecosystem / Competitor / Application | **proposed-v0** | — | 理由：文件定義 Signal 的日期、來源、可靠度與 `so_what`，並說匯入時「留下 Signal 記錄來源」（slide 11、15），但沒有連結欄位，否則無法追溯 Signal 支持哪張卡 |

**合計：**
- 14 個關係名稱，22 個 (名稱, domain) 組合：
  - `source-bi-doc` 18 個（其中 8 個欄位名稱出自文件，10 個為 provisional）；
  - `proposed-v0` 4 個。
- 另有 4 個 `source-v1.0` 的 claim 連結：`claim_about` 與 claim ↔ evidence 的 supports / contradicts / context。

文件中**以文字保存、不建連結**的欄位：
- Account 的「客戶」：沒有對應的卡片類型。
- Competitor 的「產品線」：對手方案另以 TestSolution + `vendor` 表示。

## 4. 規則（`rules`、`gap_checks`、`review_roles`）

| id | origin | 頁碼 | 內容 |
|---|---|---|---|
| account_not_ecosystem | source-bi-doc | 5 | Account 是買我方儀器的客戶；Ecosystem 是供應鏈上的晶片、模組、認證夥伴；兩者不混用。同一 canonical_key 不得兩者皆是；Account 只經 `suppliers` 連到 Ecosystem（產品經 `chip_modules`） |
| own_solution_vendor | source-bi-doc | 8 | 我方方案 vendor 留空（沒有 `vendor` 連結），也不建我方的 Competitor 卡；對手方案恰有一個 `vendor` 連到 Competitor 卡；`competing_solutions` 從我方方案指向對手方案 |
| own_solution_explicit | source-v1.0 | — | `is_own_solution` 必填，且等於「沒有 vendor 連結」 |
| coverage_counts_own_only | source-bi-doc | 8, 13 | Application 的方案覆蓋只計我方方案；對手方案只出現在對照表 |
| claim_modality | source-bi-doc | 11, 12 | 區分「宣稱」與「推論」；推測內容標 assumed，查證後改 verified；不確定的事實列入待查證（assumed），不當成事實；簡報中的每個論點標頁碼 |
| claim_record_fields | source-v1.0 | — | `claim_kind`、`verification_status`、`review_status` 與 evidence 角色沿用 v1.0 的 kg.claim / kg.claim_evidence |
| concept_review | source-bi-doc | 9, 12 | Concept 先標 draft，業務試讀後改為 reviewed |
| stale_after_90_days | source-bi-doc | 12 | 每張卡記錄來源與更新日期，超過 90 天會被提醒 → Atlas `graph_state: stale`、gap `STALE_DATA` |
| node_fixed_set | source-bi-doc | 4 | Node 是固定清單（文件的無線通訊節點）。**proposed-v0 擴充**：為 owner 的非無線 BD 情境（AI 資料中心、車用雷達）新增節點，標 `position_set: proposed-v0-extension` |
| import_idempotent_merge | source-bi-doc | 10, 11 | 先 dry-run；可重複執行不產生重複卡片；預設合併、不覆蓋人工內文；擷取結果在審閱前不進正式集合；不貼原文全文，只留摘要與來源 |
| assertion_needs_support / inference_needs_basis / disputed_needs_both_sides / domain_range / classification_inherits_max / label_is_content | proposed-v0 | — | 見 JSON |

缺口檢查（slide 13）：
- 沒有我方方案的 Application → `RELATION_GAP`；
- 缺 Concept 的 Technology → `METADATA_GAP`；
- 推測內容比例 → `REASONING_GAP`；
- 過期資料 → `STALE_DATA`；
- 另提議 disputed → `CONFLICT`（proposed-v0）。

審閱角色：
- 文件規定 Concept 由業務試讀（slide 9）；負責人與審閱頻率「待指定」（slide 15）。
- Benchmark 的 Domain Reviewer（BD / PM / AE，建議）見 v1.2 §5。

## 5. 與儲存、Harness 解耦

細節見 v1.2 ADR-K10。
1. **Schema 是資料。** `bi_schema_v0.json` 由 Strategy Config 的 `schema` 欄位引用（`schema_id` 加 sha256 digest），不是 Python 型別。
2. **Storage 不認得 BI 類型。** backend 只存 `entity_type` 字串加一份 `properties` 文件，依紀錄所標 `schema_id` 驗證；關係依 `sources` 的 domain 與 `range` 驗證。
3. **Harness 不 import 任何 BI 型別。**
4. **換成真正的 `bi_schema.py` 是 config 與 migration 的變更**，不是 Harness 的變更。
5. 文件的匯入規則與 v0 的對應：
   - dry-run、可重複執行、合併不覆蓋人工內文（slide 10），對應 v0 的 `import_idempotent_merge` 與 ADR-K1 的 sandbox candidate → 審閱 → push。
   - `_Inbox`（slide 11）對應 sandbox candidate。

## 6. v0 → v1 upcast（JSON 的 `upcast`）

- **type_map / property_map / relationship_map：**
  - 依 `bi_schema.py` 的實際欄位名稱，把所有 `provisional` 名稱改成正式名稱。
  - v1 必填卻沒有值的紀錄，回到 draft / candidate。
  - 無對應的屬性移到 `properties.legacy_v0`。
  - 無對應的 `proposed-v0` 關係不發佈並送審。
- claim、evidence id、document id 與 review_status 永不改寫；`edited_by_human` 的紀錄保留，並回報衝突。
- 先 dry-run 產生報告，再以 `(entity_type, canonical_key)` 與 `relationship_id` 冪等套用。

## 7. ID 規則

| ID | 規則 |
|---|---|
| entity_id | `ent-<小寫 entity_type>-<canonical_key>` |
| relationship_id | `rel-` + sha256(subject_entity_id \| relationship_type \| object_entity_id)[:16] |
| claim_id | `clm-` + sha256(relationship_id \| statement)[:16] |
| document_id | 既有 `source_id`：`src-` + sha256(原始位元組)[:16]（`src/knowledge/raw.py` `source_for`） |
| evidence_id | `ev-` + sha256(document_id \| locator \| normalized_text)[:20]（ADR-K4） |

所有 ID 都符合 AEP `Symbol`（`src/common/base.py:8`）的字元集。

## 8. 剩餘缺口（給 owner）

1. `bi_schema.py`、`bi_ingest.py`、`bi_slides_extract.py` 與 mapping JSON 仍不可得。10 個 provisional 欄位名稱與所有列舉值待核對。
2. slide 4 說 Node 共 8 個，但只列出 7 個；第 8 個是什麼？
3. Application 的「價值鏈層級」是連到 Node，還是另一個層級列舉？
4. Opportunity 在文件中沒有欄位；v0 的 3 個 proposed-v0 連結與 `hypothesis_status` 是否可以？
5. Signal 是否應有連結欄位（v0 提議 `mentions`）？
6. 是否接受 v0 為 AI 資料中心與車用雷達情境擴充 Node（`proposed-v0-extension`）？還是 Phase 1 的 benchmark 應只用無線通訊節點？
