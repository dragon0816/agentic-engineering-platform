# BI Schema v1（`bi.schema/v1`，PoC 契約，不是正式 schema）

> 2026-10-19，Knowledge Strategy v1.3（[KNOWLEDGE_STRATEGY_v1.3.md](../KNOWLEDGE_STRATEGY_v1.3.md) §4.3、§4.4、ADR-K10、ADR-K11）。
> 機器可讀版本：[bi_schema_v1.json](bi_schema_v1.json)（JSON Schema 2020-12 片段）。v0 保留作歷史，不修改：[../bi_schema_v0/](../bi_schema_v0/README.md)。
> 合成實例：[../../contracts/knowledge-api/mock/](../../contracts/knowledge-api/mock/)；benchmark：[../knowledge_benchmark_v0/](../knowledge_benchmark_v0/README.md)。
> 一致性測試：`tests/test_knowledge_strategy_docs.py`（每個 `source-bi-schema-py` 名稱都檢查 `bi_schema.py` 對應行）。

## 1. 來源與方法

- **主要來源：`tests/fixtures/bi_vault_example/tools/bi_schema.py`**（owner 2026-10-19 提供，同日核准以測試資料身分 commit，e30cd8bf）。
  它的 docstring 寫明自己是卡片 schema 的唯一依據（`bi_schema.py:1-3`）。BI 文件 slide 10 也說欄位名稱以它為準。
  - v1 的 JSON 是用 Python `ast` **讀取**（不執行）`bi_schema.py` 產生的；每個類型、欄位、列舉別名都帶行號。檔案 sha256 記在 `source.primary_sha256`，測試會比對。
  - 次要來源：`bi_ingest.py`（合併、正規化、缺目標警告）、`tools/README.md`、`README.md`、`BI/Dashboard.md`、`tools/prompts/slide_distill.md`。
- **程式與簡報不一致時，以程式為準**（下文每一處都標出）。
- v1 中每個類型、欄位與關係都有 `origin`：
  | origin | 意義 |
  |---|---|
  | `source-bi-schema-py` | 在 `bi_schema.py` 定義；`code_ref` / `x-code` 是 `bi_schema.py:<行>` |
  | `proposed` | `bi_schema.py` 沒有；從 v0 保留或 v1.3 新增，每一項附 `reason` / `x-reason` |
  | `aep-record` | AEP 儲存紀錄的外殼（id、分類、發佈狀態），不是卡片欄位 |
- 範例 vault（`tests/fixtures/bi_vault_example/BI/`，不含 `_Templates` 與 `Dashboard.md`）共 **103 張卡**：Node 8、Ecosystem 57、Account 4、Application 4、Competitor 6、Concept 8、CustomerProduct 2、Signal 3、Technology 4、TestSolution 3、Trend 4。內容為虛構或未查證（`README.md:12`），只當測試資料。

## 2. `bi_schema.py` 的結構事實（v1 已編碼）

| 事實 | 位置 | v1 的處理 |
|---|---|---|
| 欄位種類：`str`、`int`、`bool`、`date`、`enum`、`list`、`link`、`linklist`、`virtual` | `bi_schema.py:3-6, 10-12` | `source.field_kinds`；`link` = 單一關係（cardinality one），`linklist` = 多個 |
| `virtual` 只用於檔名，不寫進 YAML | `bi_schema.py:6`；Signal `title` `:175`；檔名 = `date-title`（`:174`） | Signal `title` → `display_name`，不是 property |
| 命名欄位是 `name`，只有 CustomerProduct 是 `product_name` | `:36, 66, 79, 92, 104, 118, 128, 136, 146, 163`；`:92` | `naming_field` → `display_name` |
| `confidence`（verified / assumed，預設 assumed）與 `updated`（預設 today）只加在 `tail=True` 的類型 | `:16-20` | Account（`:124`）、Node（`:133`）、Signal（`:185`）是 `tail=False`，**沒有** `confidence` 也沒有 `updated` |
| Signal 的 `reliability: high|medium|low` 評的是來源，不是驗證狀態 | `:184` | 規則 `confidence_is_not_reliability` |
| Application `lifecycle`（RD / Certification / Production / Reliability / Field）與 CustomerProduct `test_stage_now`（RD / cert / production）是**不同的列舉** | `:69-70`、`:99` | 規則 `lifecycle_stage_mapping`：RD→RD、cert→Certification、production→Production；Reliability、Field 無對應 |
| `launch_window` 是自由文字（例：`2027-Q1`），不是日期 | `:97` | `type: string`（v0 的 `launch_schedule` 有日期 pattern，已移除） |
| link 欄位**沒有目標類型**；目標卡不存在只警告 | `bi_schema.py` 全檔；`bi_ingest.py:722-727` | 每個 range 都是推論，`range_basis` 說明依據；規則 `links_need_resolved_targets`：AEP 只在目標解析成正確類型時才存關係，否則成為詞彙缺口候選 |
| 沒有穩定的 entity_id：卡片以檔名識別，檔名由命名欄位經清理產生 | `bi_ingest.py:58-60, 427-434` | AEP 的 `entity_id` / `canonical_key` 規則不變（`id_rules`） |
| 必填只有命名欄位，Signal 另有 `date`、`summary`、`so_what` | `:176, 181, 183` | `required` = 程式必填 + 有預設值的欄位（`bi_ingest.py:410-424` 建卡時一律補預設值） |
| 列舉中文別名、欄名別名 | `:188`、`:190-244` | `global_aliases`、`enum_aliases`、每個欄位的 `x-aliases`（給匯入正規化用） |
| Opportunity **沒有** schema、資料夾或欄位；只出現在 `README.md:18` 的分析鏈 | — | 維持 `proposed`（見 §5） |

## 3. 與 v0 的差異（以程式為準）

### 3.1 類型

| 類型 | v0 | v1（`bi_schema.py`） | 差異 |
|---|---|---|---|
| 全部 11 種卡 | `source-bi-doc` | `source-bi-schema-py`，`:35`（TestSolution）… `:174`（Signal） | 名稱相同（資料夾名）；frontmatter 的 `type:` 值是 snake_case（`test_solution`、`customer_product` …），記在 `frontmatter_type` |
| Opportunity | `source-bi-doc`（簡報有名稱、無欄位） | **程式沒有** | `proposed`，保留 `hypothesis_status`、`market_segments` 與 3 個連結 |
| Node 清單 | 7 個（簡報 slide 4 列出的；owner 2026-10-18「看到幾個就幾個」） | 程式不固定清單；範例 vault 有 **8 張 Node 卡**：L1-Chipset、L2-Antenna-Module、L2-RF-FEM-Module、L3-Handset、L3-WiFi-Router-CPE、L4-Base-Station、L5-Carrier-Network、X-Certification-Lab | v1 依同一規則改用 **8 個**（簡報的「模組」在 vault 拆成天線模組與 RF 前端模組，這也解開了 v1.2 的「slide 4 說 8 個只列 7 個」）。`layer` 列舉 L1–L5、X（`:129`） |

### 3.2 屬性（property）

| 類型 | v0 屬性 | v1 | 種類 |
|---|---|---|---|
| Trend | `measurement_impact`（文字） | `measurement_impact` int 1–5（`:170`） | 型別改變；v0 文字移到 `legacy_v0` |
| Trend | `our_fit` high/medium/low | int 1–5（`:171`） | 型別改變；upcast 對照 high→4、medium→3、low→2（`origin: migration`，待人確認） |
| Trend | `stage` emerging/growth/mature/declining（v0 提議） | watch / emerging / accelerating / peak / fading（`:167`） | 列舉不同 |
| Trend | — | `time_to_demand`、`market_impact`、`confidence`、`updated`（`:168-169`） | 新增 |
| Technology | `maturity` research/pre_standard/standardized/deployed | emerging / growth / mature / declining（`:139`） | 列舉不同 |
| Technology | `standards_body` | `standard_body`（`:137`） | 改名 |
| Technology | — | `spec_milestones`、`new_test_requirements`（`:138, 141`） | 新增 |
| Node | `position_set`（proposed） | 保留 `proposed`，值改為 `vault-reference` / `proposed-extension`；新增 `reference_position`（proposed）與 `layer`（`:129`）、`typical_test_needs`（`:132`） | |
| Ecosystem | `role` 5 個提議值 | 11 個值（`:106-108`：chipset、module、ODM、OEM、carrier、cert-lab、integrator、distributor、standards、component、osat） | 列舉不同 |
| Ecosystem | — | `relationship_to_us`、`reference_design`、`ticker`（`:110, 113, 114`） | 新增 |
| Account | `region` 列舉 | 自由文字（`:122`） | 型別改變 |
| Account | `customers`（文字清單） | `key_customers` linklist（`:121`） | 改為關係；無法解析的名稱進 `legacy_v0` |
| Account | — | `ticker`（`:123`） | 新增 |
| CustomerProduct | `launch_schedule` | `launch_window`（`:97`） | 改名 |
| CustomerProduct | — | `volume_tier`、`test_stage_now`（`:98-99`） | 新增 |
| Application | `measurement_topic`（必填字串） | `measurement_topics` 清單（`:74`），非必填 | 改名、改型別 |
| Application | — | `value_chain`（`:67`）、`lifecycle`（`:69`）、`priority` int 1–5（`:75`） | 新增；`priority` 是 judgement（ADR-K11） |
| TestSolution | `is_own_solution`（source-v1.0）、`product_family`（proposed-v0） | 程式都沒有；保留為 `proposed`（`is_own_solution` 是 `vendor` 空白規則的明確形式，derived） | |
| TestSolution | — | `test_type`、`tier`、`automation`、`dut`、`test_items`、`standards`、`instruments`、`price_band`、`services`、`status`（預設 planning）、`owner`（`:41-55`） | 新增 |
| Competitor | `confirmed` | 程式沒有；併入卡片 `confidence`（true→verified、false→assumed） | 移除 |
| Competitor | — | `pricing_position`、`recent_moves`、`ticker`（`:85-87`） | 新增 |
| Concept | `review_state` | `review_status`（`:157`，draft / reviewed，預設 draft） | 改名；這是卡片的「業務試讀」狀態，不是紀錄層的發佈 `review_status` |
| Concept | `audience`（文字） | 列舉 sales / sales+FAE / engineer（`:156`，預設 sales） | 型別改變 |
| Concept | — | `aliases`、`category`、`reviewer`（`:147-148, 159`） | 新增 |
| Signal | `date` 可為 YYYY-MM | 必須 YYYY-MM-DD（`:176`） | upcast：月份 → 該月 1 日，`legacy_v0.date_precision: month` |
| Signal | `source` 必填 | 非必填（`:180`） | |
| Signal | — | `summary`（必填，無預設，`:181`）、`source_type`（`:177`） | 新增；`summary` 缺值的紀錄回到 candidate |
| 紀錄層 | `sources`（provisional） | 程式沒有；`bi_ingest.py` 只寫 `ingested_from`（輸入**檔名**，`:577-585`） | 移除，改用 `provenance.document_ids` / `evidence_ids` |

### 3.3 關係：v1.2 N1 的 10 個 provisional 名稱已解決

| v0（provisional） | v1 真實欄位 | 位置 | 結果 |
|---|---|---|---|
| Account `node` | `node`（link） | `:119` | 確認 |
| Application `node`（由「價值鏈層級」推讀） | **`nodes`**（linklist）；另有 `value_chain` 列舉 L1–L5、X（`:67`），不是連結 | `:71` | 改名；簡報的「價值鏈層級」其實是 `value_chain` 屬性 |
| CustomerProduct `technologies` | `technologies` | `:95` | 確認 |
| CustomerProduct `applications` | **`inferred_applications`** | `:100` | 改名 |
| Concept `applications` | `applications` | `:153` | 確認 |
| Ecosystem `supplied_technologies` | **`technologies`** | `:109` | 改名 |
| Account `suppliers` | **`key_suppliers`** | `:120` | 改名 |
| CustomerProduct `account` | `account`（link） | `:93` | 確認 |
| CustomerProduct `chip_modules` | **`chipset_modules`** | `:96` | 改名 |
| Concept `test_solutions` | `test_solutions` | `:154` | 確認 |
| （proposed-v0）Signal `mentions` | **`related`** | `:182` | 程式本來就有，改名並轉為 `source-bi-schema-py` |

v0 的 8 個 `doc` 名稱（`related_tech`、`affects_nodes`、Ecosystem `node`、Application / Concept `technologies`、TestSolution `applications`、`competing_solutions`、`vendor`）在程式中全部存在，名稱相同。

### 3.4 v1 全部關係（25 個名稱、37 個 domain 組合）

| 名稱 | domain（`bi_schema.py` 行） | range（推論依據見 JSON `range_basis`） | 新於 v0 |
|---|---|---|---|
| `vendor` | TestSolution `:37`（one） | Competitor | |
| `applications` | TestSolution `:38`、Concept `:153` | Application | |
| `technologies` | TestSolution `:39`、Application `:72`、Competitor `:81`、CustomerProduct `:95`、Ecosystem `:109`、Concept `:152` | Technology | TestSolution、Competitor 為新 |
| `nodes` | TestSolution `:40`、Application `:71` | Node | 新名稱 |
| `competing_solutions` | TestSolution `:52` | TestSolution | |
| `reference_customers` | TestSolution `:53` | Account | 新 |
| `trends` | Application `:73` | Trend | 新 |
| `node` | Competitor `:80`、CustomerProduct `:94`、Ecosystem `:105`、Account `:119`（皆 one） | Node | Competitor、CustomerProduct 為新 |
| `account` | CustomerProduct `:93`（one）；Opportunity（proposed） | Account | |
| `chipset_modules` | CustomerProduct `:96` | Ecosystem | 新名稱 |
| `inferred_applications` | CustomerProduct `:100` | Application | 新名稱 |
| `influence_on` | Ecosystem `:112` | Account（推論） | 新 |
| `key_suppliers` | Account `:120` | Ecosystem | 新名稱 |
| `key_customers` | Account `:121` | Account（推論） | 新 |
| `upstream`、`downstream` | Node `:130`、`:131` | Node | 新 |
| `affects_nodes` | Technology `:140` | Node | |
| `related_concepts` | Concept `:155` | Concept | 新 |
| `test_solutions` | Concept `:154`；Opportunity（proposed） | TestSolution | |
| `related_tech` | Trend `:164` | Technology | |
| `affected_nodes` | Trend `:165` | Node | 新 |
| `related_applications` | Trend `:166` | Application | 新 |
| `related` | Signal `:182` | 除 Signal、Opportunity 外的 10 種 | 新名稱（v0 `mentions`） |
| `customer_product` | Opportunity（proposed） | CustomerProduct | |
| `competing_vendors` | TestSolution（**proposed，v1.3**） | Competitor | 新 |

**`competing_solutions` 型別不一致（以程式與資料為準的重要發現）。** `bi_schema.py:52` 只有一個 linklist，別名是「競品方案 / 競品 / competitors」；
`tools/README.md:83` 與 `tools/prompts/slide_distill.md:14` 說我方卡列出對手的 **TestSolution** 卡；但範例 vault 的兩個值都指向 **Competitor**（公司）卡
（`BI/TestSolution/FR2-AiP-OTA緊縮場方案.md:16` → Competitor-X、`BI/TestSolution/WiFi7-MLO互通與吞吐量方案.md:16` → Competitor-Y）。v1 的處理：
`competing_solutions` 維持 range TestSolution；指向 Competitor 的值不默默收下，而是成為 `competing_vendors` candidate 並發出型別警告（規則 `competing_solutions_type_check`）。
是否把 `competing_vendors` 寫回 `bi_schema.py`，是給 owner 的問題（v1.3 §8）。

## 4. 欄位分類（ADR-K11）

每個屬性與關係來源都有 `x-field-class` / `field_class`：

| 類別 | 意義 | v1 中的欄位 |
|---|---|---|
| `judgement` | 人的評估；保留誰、何時、為何；匯入或 agent 永不覆蓋人設定的值 | 所有類型的 `confidence`；Application `priority`；Trend `stage`、`time_to_demand`、`market_impact`、`measurement_impact`、`our_fit`；Technology `maturity`；Competitor `strengths`、`weaknesses`、`pricing_position`；CustomerProduct `volume_tier`；Ecosystem `relationship_to_us`；Concept `audience`、`review_status`；Signal `so_what`、`reliability`；Opportunity `hypothesis_status`；關係 `competing_solutions`、`competing_vendors`、`influence_on`、`inferred_applications` 與 Opportunity 的連結 |
| `derived` | 由其他資料算出，不直接編輯 | `updated`、`is_own_solution`、`synthetic`、`legacy_v0` |
| `sourced` | 來自文件或匯入的事實 | 其餘全部（例如 Application `lifecycle`：它描述應用所處的階段類別，不是排序，所以判為 sourced） |

## 5. Opportunity 與 Signal

- **Opportunity：** `bi_schema.py` 沒有這個類型（也沒有資料夾或模板，`BI/_Templates/` 只有 11 個）。它只是 `README.md:18` 分析鏈的終點。v1 維持 `proposed`，
  保留 `hypothesis_status` 與連結 `account`、`test_solutions`、`customer_product`，理由同 v0：鏈的終點需要一個可審閱的推論型商機。
- **Signal：** 程式有完整定義（`:174-185`）。v0 提議的 `mentions` 其實就是程式的 `related`；`summary` 與 `so_what` 必填；
  沒有 `confidence` / `updated`；`reliability` 不等於驗證。

## 6. v0 → v1 upcast（ADR-K10）

完整規則在 JSON 的 `upcast_from_v0`：
- `type_map`：全部同名（Opportunity 仍 proposed）。
- `record_map`：`updated` 保留；`sources` 移除（理由見 §3.2）。
- `property_map`：逐類型逐欄位；動作是 `keep`、`rename`、`rename_to_list`、`value_map`、`type_change`、`normalize`、`to_relationship_or_legacy`。
  沒有對應的值移到 `properties.legacy_v0`，不默默丟掉。經 value map 得到的 judgement 值帶 `field_provenance.origin: migration`，待人確認。
- v1 必填但沒有值：有程式預設就用預設（`bi_ingest.py:410-424`），否則紀錄回到 `draft` / `candidate`（例：Signal `summary`）。
- `relationship_map`：v0 的 22 個 (domain, 名稱) 組合全部列出；6 個改名，其餘保留。改名的關係以 v1 名稱重算 `relationship_id`，並寫 `relationship_id_map`；claim 的 id、敘述、模態與證據不改，只有它指向的 relationship id 跟著 map 走。
- 先 dry-run 報告，再以 `(entity_type, canonical_key)` 與 `relationship_id` 冪等套用；document id 與 evidence id 永不改寫。

mock（`docs/contracts/knowledge-api/mock/`）與 benchmark 已依這些規則升級，可當作 upcast 的實例。

## 7. 仍待 owner 決定（摘要，完整見 v1.3 §8）

- `competing_vendors` 是否寫回 `bi_schema.py`，或只做型別警告。
- link range 的推論是否正確，特別是 `influence_on` 與 `key_customers`（程式沒有目標類型）。
- Node 擴充（AI 資料中心、車用雷達、交換器 ASIC、光模組、通訊模組）是否接受；範例 vault 的 module 廠（role `module`）沒有 node。
- Application `priority` 的評分準則與是否依團隊、期間分開（ADR-K11）。
