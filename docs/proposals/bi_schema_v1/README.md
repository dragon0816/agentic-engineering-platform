# BI Schema v1（`bi.schema/v1`，PoC 契約，不是正式 schema）

> 2026-10-19，Knowledge Strategy v1.3（[KNOWLEDGE_STRATEGY_v1.3.md](../KNOWLEDGE_STRATEGY_v1.3.md) §4.3、§4.4、ADR-K10、ADR-K11）。
> 機器可讀版本：[bi_schema_v1.json](bi_schema_v1.json)（JSON Schema 2020-12 片段）。v0 保留作歷史，不修改：[../bi_schema_v0/](../bi_schema_v0/README.md)。
> 合成實例：[../../contracts/knowledge-api/mock/](../../contracts/knowledge-api/mock/)；benchmark：[../knowledge_benchmark_v0/](../knowledge_benchmark_v0/README.md)。
> 一致性測試：`tests/test_knowledge_strategy_docs.py`（每個 `source-bi-schema-py` 名稱都檢查 `bi_schema.py` 對應行）。
>
> **v1.1（2026-10-19，owner 決定）：** `competing_vendors` 與 Opportunity 成為正式欄位 / 類型（`origin: owner-decision-2026-10-19`，
> `bi_schema.py` 尚未加入，建議的程式行見 §8）；Application `priority` 改為分 market、分期間的 `priorities`（§7）；
> Opportunity `hypothesis_status` 改名為 `opportunity_stage`。`schema_id` 仍是 `bi.schema/v1`（凍結前的 PoC 契約），JSON `version` 1.1.0，`revisions` 記錄變更。

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
  | `owner-decision-2026-10-19` | owner 2026-10-19 決定為正式，但 `bi_schema.py` 還沒有；`decision` / `x-decision` 指出決定，`suggested_code` / `x-suggested-code` 是要加入 `bi_schema.py` 的那一行（§8），測試檢查 §8 逐字包含 |
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
| Opportunity **沒有** schema、資料夾或欄位；只出現在 `README.md:18` 的分析鏈 | — | v1.0 維持 `proposed`；**v1.1 依 owner 2026-10-19 決定成為正式類型**（`owner-decision-2026-10-19`，見 §5、§8） |

## 3. 與 v0 的差異（以程式為準）

### 3.1 類型

| 類型 | v0 | v1（`bi_schema.py`） | 差異 |
|---|---|---|---|
| 全部 11 種卡 | `source-bi-doc` | `source-bi-schema-py`，`:35`（TestSolution）… `:174`（Signal） | 名稱相同（資料夾名）；frontmatter 的 `type:` 值是 snake_case（`test_solution`、`customer_product` …），記在 `frontmatter_type` |
| Opportunity | `source-bi-doc`（簡報有名稱、無欄位） | **程式沒有** | v1.0 `proposed`；**v1.1 正式（owner 2026-10-19）**：`name`、`opportunity_stage`（取代 `hypothesis_status`）、`confidence`、`updated`、`market_segments` 與 3 個連結 |
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
| Application | — | `value_chain`（`:67`）、`lifecycle`（`:69`）、`priority` int 1–5（`:75`） | 新增；**v1.1 把 `priority` 改為 `priorities`**：每個 market × 期間一筆（owner 2026-10-19，§7）；單一值依 §7 升級 |
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
| `account` | CustomerProduct `:93`（one）；Opportunity（owner 2026-10-19，one） | Account | |
| `chipset_modules` | CustomerProduct `:96` | Ecosystem | 新名稱 |
| `inferred_applications` | CustomerProduct `:100` | Application | 新名稱 |
| `influence_on` | Ecosystem `:112` | Account（推論） | 新 |
| `key_suppliers` | Account `:120` | Ecosystem | 新名稱 |
| `key_customers` | Account `:121` | Account（推論） | 新 |
| `upstream`、`downstream` | Node `:130`、`:131` | Node | 新 |
| `affects_nodes` | Technology `:140` | Node | |
| `related_concepts` | Concept `:155` | Concept | 新 |
| `test_solutions` | Concept `:154`；Opportunity（owner 2026-10-19） | TestSolution | |
| `related_tech` | Trend `:164` | Technology | |
| `affected_nodes` | Trend `:165` | Node | 新 |
| `related_applications` | Trend `:166` | Application | 新 |
| `related` | Signal `:182` | 除 Signal、Opportunity 外的 10 種 | 新名稱（v0 `mentions`） |
| `customer_product` | Opportunity（owner 2026-10-19） | CustomerProduct | |
| `competing_vendors` | TestSolution（**owner 2026-10-19，正式**） | Competitor | 新 |

**`competing_solutions` 型別不一致（以程式與資料為準的重要發現）。** `bi_schema.py:52` 只有一個 linklist，別名是「競品方案 / 競品 / competitors」；
`tools/README.md:83` 與 `tools/prompts/slide_distill.md:14` 說我方卡列出對手的 **TestSolution** 卡；但範例 vault 的兩個值都指向 **Competitor**（公司）卡
（`BI/TestSolution/FR2-AiP-OTA緊縮場方案.md:16` → Competitor-X、`BI/TestSolution/WiFi7-MLO互通與吞吐量方案.md:16` → Competitor-Y）。v1 的處理：
`competing_solutions` 維持 range TestSolution；指向 Competitor 的值不默默收下，而是遷移成 `competing_vendors` candidate 並發出型別警告（規則 `competing_solutions_type_check`），審核後才發佈。
**owner 2026-10-19：「要加」** → `competing_vendors`（TestSolution → Competitor，linklist）成為正式欄位，建議的 `bi_schema.py` 程式行見 §8。

## 4. 欄位分類（ADR-K11）

每個屬性與關係來源都有 `x-field-class` / `field_class`：

| 類別 | 意義 | v1 中的欄位 |
|---|---|---|
| `judgement` | 人的評估；保留誰、何時、為何；匯入或 agent 永不覆蓋人設定的值 | 所有類型的 `confidence`；Application `priorities`（每筆自帶 provenance，§7）；Trend `stage`、`time_to_demand`、`market_impact`、`measurement_impact`、`our_fit`；Technology `maturity`；Competitor `strengths`、`weaknesses`、`pricing_position`；CustomerProduct `volume_tier`；Ecosystem `relationship_to_us`；Concept `audience`、`review_status`；Signal `so_what`、`reliability`；Opportunity `opportunity_stage`；關係 `competing_solutions`、`competing_vendors`、`influence_on`、`inferred_applications` 與 Opportunity 的連結 |
| `derived` | 由其他資料算出，不直接編輯 | `updated`、`is_own_solution`、`synthetic`、`legacy_v0` |
| `sourced` | 來自文件或匯入的事實 | 其餘全部（例如 Application `lifecycle`：它描述應用所處的階段類別，不是排序，所以判為 sourced） |

## 5. Opportunity 與 Signal

- **Opportunity：** `bi_schema.py` 沒有這個類型（也沒有資料夾或模板，`BI/_Templates/` 只有 11 個）。它只是 `README.md:18` 分析鏈的終點。v1.0 維持 `proposed`。
  **owner 2026-10-19：「要」** → v1.1 正式類型（`owner-decision-2026-10-19`）：
  | 欄位 | 種類 | 分類 | 說明 |
  |---|---|---|---|
  | `name` | str（必填，命名欄位） | — | → `display_name`；檔名由它產生 |
  | `account` | link → Account | judgement | 商機是推論，客戶歸屬也要人確認 |
  | `customer_product` | linklist → CustomerProduct | judgement | |
  | `test_solutions` | linklist → TestSolution | judgement | 提出的我方方案 |
  | `opportunity_stage` | enum hypothesis / qualified / pursuing / won / lost / rejected，預設 hypothesis | judgement | 取代 v1.0 `hypothesis_status`（前三個值相同）。不叫 `stage`：`ENUM_ALIASES` 依欄位名稱跨類型共用（`bi_schema.py:190`），`bi_ingest.py` 套別名後不再檢查列舉（`:154-160`），Trend `stage` 的別名（觀察 → watch …）會把 Trend 的值寫進 Opportunity |
  | `confidence`、`updated` | tail 欄位（`bi_schema.py:16-20`，`tail=True`） | judgement、derived | 與其他 tail 類型相同 |
  | `market_segments` | AEP 提議欄位（不在工具中） | sourced | 同 v1.0 |

  分類維持 CONFIDENTIAL、`label_is_content: true`（ADR-K8 pending）。建議的 `bi_schema.py` 程式行見 §8。
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

## 7. Application priority：分 market、分期間（owner 2026-10-19）

owner 對 v1.3 §8.2 第 4 點的回答：「分 market，分期間」。priority 不是單一全域值。完整定義在 JSON `priority_scoping` 與 `priority_entry`。

- **形狀：** Application `priorities` 是清單，每筆 `{market, period, value 1–5, origin, set_by, set_at, reason, source_ref, version}`；每個 (market, period) 至多一筆。
  provenance 在每一筆裡（`x-provenance: per-entry`），所以 `field_provenance` 沒有 `priorities` 這個 key。人設定的那一筆必須有 `reason`；匯入或 agent 永不覆蓋 origin 是 human 的那一筆，只會成為待審提議（ADR-K11）。
- **market 指什麼：** `src/knowledge/market_matrix.py` 的 `TargetMarket` 五個值（`wireless_communications`、`aerospace_defense`、`automotive`、`ai_server`、`semiconductor`），加上 `unspecified`。
  - 依據：這就是 v1 既有的 `market_segments` 屬性的值，也是 Knowledge API `market_segment` 篩選（Atlas 的 market binding）的值。
  - `bi_schema.py` 與範例 vault **沒有** market 欄位：`value_chain`（`:67`）與 Node `layer`（`:129`）是供應鏈位置；Account `region`（`:122`）是自由文字；Trend `market_impact`（`:169`）是評分，不是市場。
  - **待 owner 確認（子問題）：** market 是指這五個市場區隔，還是業務區域 / 客戶群？可以加值；若是區域，要另一個列舉。
- **期間格式：** 日曆季 `YYYY-Qn`（例 `2026-Q4`，pattern `^[0-9]{4}-Q[1-4]$`）。ADR-K11 建議每季檢視；`launch_window` 也用同樣寫法（例 `2027-Q1`）。若公司用會計季度，改的是對照，不是格式。
- **單一 priority 的升級**（`bi_schema.py:75`、範例 vault、既有工具）：一筆 `{market: unspecified, period, value}`。
  - period：已知值的 `set_at`（欄位 provenance）就用它的季；否則用卡片 `updated` 的季（`bi_ingest.py` 每次匯入會寫 `updated`）；再否則用匯入日的季。
  - origin `import`，`set_by` 是 `import:<ingested_from>` 或 `legacy-snapshot:<vault digest>`；沒有 `ingested_from` 的卡，值視同人工設定而受保護（v1.3 DQ-2）。
  - 例：`BI/Application/5G-FR2-AiP-OTA驗證.md` 的 `priority: 4`、`updated: 2026-10-14` → `{market: unspecified, period: 2026-Q4, value: 4, origin: import, set_by: import:application_sample.csv}`（測試對照 fixture 檢查）。
  - 之後的匯入：表格有 market 欄（別名 市場、market）與期間欄（別名 期間、季度、period），或 mapping 的 `defaults` 指定，就寫入那個範圍；否則 unspecified + 匯入日的季。`bi_schema.py` 不必為此修改（`F` 的種類放不下物件清單）。
- **Dashboard 排序：** 使用者選一個 market 和一個期間（預設上次的選擇，否則 unspecified + 本季）。
  1. 先列該 (market, period) 有值的 Application，依 value 由高到低；
  2. 再列同期間 `unspecified` 的，標「未分 market」；
  3. 其餘列在最後，標「未評」，並顯示最近一筆較早的值**僅供參考**，不作為排序值。
  同分依名稱。過去期間的值留作歷史，不自動延用到新期間。
- **評分準則：** ADR-K11 的 1–5 準則不變，在所選 market 內判斷；6 / 18 / 36 個月的窗口從期間第一天起算。
- **Trend 不分範圍：** `bi_schema.py` 的 Trend 沒有 priority；Dashboard 的趨勢優先度是 `measurement_impact × our_fit`（`BI/Dashboard.md:5, 8`），是算出來、不儲存的值。Trend 的 `market_impact`、`measurement_impact`、`our_fit` 維持單一 judgement 值；若 owner 要它們也分 market，套用同樣的 entry 形狀。

## 8. Changes to apply to the BI tooling（給 owner 套用到自己的 `bi_schema.py`）

AEP 不修改 owner 的 `bi_schema.py`（repo 中的 `tests/fixtures/bi_vault_example/tools/bi_schema.py` 是逐字快照，測試以 sha256 釘住；
owner 的工作副本在 repo 之外）。以下三處變更讓工具與 Schema v1.1 一致。下列每一行都與 `bi_schema_v1.json` 的 `suggested_code` / `x-suggested-code` 逐字相同，測試會檢查。
行號是快照（sha256 `395ff4e7…`）的行號。

**8.1 `competing_vendors`（owner 第 1 點「要加」）：** 在 TestSolution 的 `competing_solutions`（`bi_schema.py:52`）之後、`reference_customers`（`:53`）之前插入一行：

```text
        ("competing_solutions", F("linklist", ["競品方案", "競品", "competitors", "competing solutions"])),
        ("competing_vendors", F("linklist", ["競爭廠商", "對手廠商", "competing vendors"])),
        ("reference_customers", F("linklist", ["參考客戶", "客戶", "reference customers"])),
```

只有中間那一行是新的。別名不用「競品廠商」，因為它已經是 `vendor` 的別名（`:37`）。`competing_solutions` 的別名不改；它的值若指向 Competitor 卡，AEP 匯入時依規則
`competing_solutions_type_check` 遷移成 `competing_vendors` candidate 並警告。範例 vault 的兩個值（`BI/TestSolution/FR2-AiP-OTA緊縮場方案.md:16`、`WiFi7-MLO互通與吞吐量方案.md:16`）可由 owner 手動改到 `competing_vendors`。

**8.2 Opportunity 類型（owner 第 4 點「要」）：** 在 `SCHEMAS` 的 `"signal"` 項目之後（`bi_schema.py:185` 之後、結尾 `}`（`:186`）之前）加入：

```text
    # ------------------------------------------------------------ opportunity layer (owner decision 2026-10-19)
    "opportunity": schema("Opportunity", ["name"], [
        ("name", F("str", ["商機名稱", "商機", "名稱", "opportunity", "name"], required=True)),
        ("account", F("link", ["客戶", "account"])),
        ("customer_product", F("linklist", ["客戶產品", "產品", "customer product"])),
        ("test_solutions", F("linklist", ["對應方案", "相關方案", "test solutions"])),
        ("opportunity_stage", F("enum", ["商機階段", "opportunity stage"],
                                enum=["hypothesis", "qualified", "pursuing", "won", "lost", "rejected"],
                                default="hypothesis")),
    ], ["## 商機假設", "## 依據(Signal / CustomerProduct)", "## 下一步"]),
```

`tail` 用預設 `True`，所以 `confidence` 與 `updated` 自動加上。加入後 `bi_ingest.py --type opportunity` 可用，`--emit-templates` 會產生 Opportunity 模板；vault 需要 `BI/Opportunity/` 資料夾。

**8.3 `opportunity_stage` 的列舉別名：** 在 `ENUM_ALIASES` 最後一項 `"pricing_position"`（`bi_schema.py:243`）之後、結尾 `}`（`:244`）之前加入：

```text
    "opportunity_stage": {"假設": "hypothesis", "推論": "hypothesis", "確認": "qualified", "已確認": "qualified",
                          "跟進中": "pursuing", "進行中": "pursuing", "贏得": "won", "成交": "won",
                          "失去": "lost", "未成交": "lost", "否決": "rejected", "不成立": "rejected"},
```

**priority 不需要改工具：** 工具維持單一 `priority`（`:75`），AEP 依 §7 升級成 `{market: unspecified, period, value}`。

套用後請告訴 AEP：重新以 `ast` 產生對照、更新 `source.primary_sha256` 與測試的釘選，並把這三處的 origin 改回 `source-bi-schema-py`、附上新的行號。

## 9. 仍待 owner 決定（摘要，完整見 v1.3 §8.2）

- **已決定（2026-10-19）：** `competing_vendors` 要加（§3.4、§8.1）；priority 分 market、分期間（§7）；judgement 欄位清單與 Node 擴充（`proposed-extension`）接受；Opportunity 要（§5、§8.2）。
- **仍待：** link range 的推論（`influence_on`、`key_customers`，程式沒有目標類型）；§7 的 market 定義子問題（市場區隔還是業務區域）。
