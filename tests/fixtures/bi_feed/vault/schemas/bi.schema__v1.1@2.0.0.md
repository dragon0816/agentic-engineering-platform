# BI Knowledge Schema 2.0 (schema v8 of the market knowledge bases; owner 2026-10-29)

Schema `bi.schema/v1.1@2.0.0`: 21 card types. Generated from the schema file; edit the schema (a new version), never this document.

Domains: `wireless`, `AIDC`, `robotics`, `mobile`, `aerospace`

## Types

| Type | Label | Fields |
|---|---|---|
| `Opportunity` | 商機 | 15 |
| `TestSolution` | 測試方案 | 22 |
| `Application` | 應用 | 11 |
| `Competitor` | 競品 | 14 |
| `CustomerProduct` | 客戶產品 | 17 |
| `Ecosystem` | 生態系 | 14 |
| `Account` | 客戶 | 10 |
| `Node` | 價值鏈節點 | 7 |
| `Technology` | 技術 | 10 |
| `Concept` | 概念 | 16 |
| `Trend` | 趨勢 | 14 |
| `Signal` | 訊號 | 10 |
| `WinLoss` | 輸贏分析 | 16 |
| `RoadmapRequest` | 產品需求 | 16 |
| `Pitch` | 簡報 | 14 |
| `DemoScript` | 展示腳本 | 11 |
| `Battlecard` | 對戰卡 | 13 |
| `Contact` | 聯絡人 | 11 |
| `VisitLog` | 拜訪紀錄 | 13 |
| `SupplyLink` | 供貨關係 | 18 |
| `RevenueFact` | 收入事實 | 18 |

## Links between types

| From | Field | To |
|---|---|---|
| `Opportunity` | `account` | `Account` |
| `Opportunity` | `customer_product` | `CustomerProduct` |
| `Opportunity` | `applications` | `Application` |
| `Opportunity` | `our_solutions` | `TestSolution` |
| `Opportunity` | `competitors` | `Competitor` |
| `Opportunity` | `lost_to` | `Competitor` |
| `TestSolution` | `vendor` | `Competitor` |
| `TestSolution` | `applications` | `Application` |
| `TestSolution` | `technologies` | `Technology` |
| `TestSolution` | `nodes` | `Node` |
| `TestSolution` | `competing_solutions` | `TestSolution` |
| `TestSolution` | `reference_customers` | `Account` |
| `Application` | `nodes` | `Node` |
| `Application` | `technologies` | `Technology` |
| `Application` | `trends` | `Trend` |
| `Competitor` | `node` | `Node` |
| `Competitor` | `nodes` | `Node` |
| `Competitor` | `technologies` | `Technology` |
| `CustomerProduct` | `account` | `Account` |
| `CustomerProduct` | `node` | `Node` |
| `CustomerProduct` | `nodes` | `Node` |
| `CustomerProduct` | `technologies` | `Technology` |
| `CustomerProduct` | `chipset_modules` | `Ecosystem` |
| `CustomerProduct` | `chipset_modules` | `Account` |
| `CustomerProduct` | `ecosystem` | `Ecosystem` |
| `CustomerProduct` | `ecosystem` | `Account` |
| `CustomerProduct` | `inferred_applications` | `Application` |
| `Ecosystem` | `node` | `Node` |
| `Ecosystem` | `nodes` | `Node` |
| `Ecosystem` | `technologies` | `Technology` |
| `Ecosystem` | `influence_on` | `Account` |
| `Account` | `node` | `Node` |
| `Account` | `nodes` | `Node` |
| `Account` | `key_suppliers` | `Ecosystem` |
| `Account` | `key_suppliers` | `Account` |
| `Account` | `key_customers` | `Account` |
| `Account` | `key_customers` | `Ecosystem` |
| `Node` | `upstream` | `Node` |
| `Node` | `downstream` | `Node` |
| `Technology` | `affects_nodes` | `Node` |
| `Concept` | `technologies` | `Technology` |
| `Concept` | `applications` | `Application` |
| `Concept` | `test_solutions` | `TestSolution` |
| `Concept` | `related_concepts` | `Concept` |
| `Trend` | `related_tech` | `Technology` |
| `Trend` | `affected_nodes` | `Node` |
| `Trend` | `related_ecosystem` | `Ecosystem` |
| `Trend` | `related_ecosystem` | `Account` |
| `Trend` | `related_applications` | `Application` |
| `WinLoss` | `opportunity` | `Opportunity` |
| `WinLoss` | `account` | `Account` |
| `WinLoss` | `applications` | `Application` |
| `WinLoss` | `our_solutions` | `TestSolution` |
| `WinLoss` | `competitors` | `Competitor` |
| `WinLoss` | `winner` | `Competitor` |
| `WinLoss` | `winner` | `Ecosystem` |
| `WinLoss` | `winner` | `Account` |
| `RoadmapRequest` | `applications` | `Application` |
| `RoadmapRequest` | `our_solutions` | `TestSolution` |
| `RoadmapRequest` | `competitors` | `Competitor` |
| `RoadmapRequest` | `source_win_loss` | `WinLoss` |
| `RoadmapRequest` | `source_opportunities` | `Opportunity` |
| `Pitch` | `applications` | `Application` |
| `Pitch` | `our_solutions` | `TestSolution` |
| `Pitch` | `technologies` | `Technology` |
| `Pitch` | `concepts` | `Concept` |
| `Pitch` | `accounts` | `Account` |
| `DemoScript` | `our_solutions` | `TestSolution` |
| `DemoScript` | `applications` | `Application` |
| `Battlecard` | `competitor` | `Competitor` |
| `Battlecard` | `our_solutions` | `TestSolution` |
| `Battlecard` | `applications` | `Application` |
| `Battlecard` | `competing_solutions` | `TestSolution` |
| `Contact` | `account` | `Account` |
| `Contact` | `reports_to` | `Contact` |
| `Contact` | `applications` | `Application` |
| `VisitLog` | `account` | `Account` |
| `VisitLog` | `contacts` | `Contact` |
| `VisitLog` | `opportunity` | `Opportunity` |
| `VisitLog` | `applications` | `Application` |
| `VisitLog` | `our_solutions` | `TestSolution` |
| `SupplyLink` | `supplier` | `Ecosystem` |
| `SupplyLink` | `supplier` | `Account` |
| `SupplyLink` | `customer` | `Account` |
| `SupplyLink` | `customer` | `Ecosystem` |
| `SupplyLink` | `nodes` | `Node` |
| `SupplyLink` | `technologies` | `Technology` |
| `SupplyLink` | `customer_products` | `CustomerProduct` |
| `RevenueFact` | `company` | `Account` |
| `RevenueFact` | `company` | `Ecosystem` |
| `RevenueFact` | `company` | `Competitor` |
| `RevenueFact` | `customer` | `Account` |
| `RevenueFact` | `customer` | `Ecosystem` |

## Opportunity — 商機

- Named by: `name`
- Domain: one

| Field | Label | Kind | Allowed values | Links to | Required |
|---|---|---|---|---|---|
| `name` | 商機名稱 | str |  |  | yes |
| `domain` | 領域 | enum | `wireless`, `AIDC`, `robotics`, `mobile`, `aerospace` |  |  |
| `account` | 客戶 | link |  | Account |  |
| `customer_product` | 客戶產品 | link |  | CustomerProduct |  |
| `applications` | 對應應用 | linklist |  | Application |  |
| `our_solutions` | 我方方案 | linklist |  | TestSolution |  |
| `competitors` | 競爭對手 | linklist |  | Competitor |  |
| `deal_stage` | 商機階段 | enum | `lead`, `qualified`, `proposal`, `eval`, `negotiation`, `won`, `lost` |  |  |
| `expected_close` | 預計成交 | date |  |  |  |
| `size` | 規模 | enum | `S`, `M`, `L` |  |  |
| `lost_to` | 敗給 | link |  | Competitor |  |
| `owner` | 負責人 | str |  |  |  |
| `confidence` | 信心度 | enum | `verified`, `assumed` |  |  |
| `updated` | 更新日期 | date |  |  |  |
| `body` | 備註 | str |  |  |  |

## TestSolution — 測試方案

- Named by: `name`
- Domain: multi

| Field | Label | Kind | Allowed values | Links to | Required |
|---|---|---|---|---|---|
| `name` | 方案名稱 | str |  |  | yes |
| `domain` | 領域 | list |  |  |  |
| `vendor` | 廠商 | link |  | Competitor |  |
| `applications` | 對應應用 | linklist |  | Application |  |
| `technologies` | 技術 | linklist |  | Technology |  |
| `nodes` | 節點 | linklist |  | Node |  |
| `test_type` | 測試類型 | enum | `conducted`, `OTA`, `protocol`, `channel-emu`, `spectrum`, `power`, `ATE`, `signal-integrity`, `optical`, `channel-char`, `wafer-probe`, `EMC`, `environmental` |  |  |
| `tier` | 方案型態 | enum | `instrument`, `integrated`, `automated`, `service` |  |  |
| `automation` | 自動化程度 | enum | `manual`, `semi`, `full` |  |  |
| `dut` | 被測物 | str |  |  |  |
| `test_items` | 測試項目 | list |  |  |  |
| `standards` | 標準 | list |  |  |  |
| `instruments` | 儀器配置 | list |  |  |  |
| `price_band` | 價格帶 | enum | `entry`, `mid`, `high` |  |  |
| `services` | 服務 | list |  |  |  |
| `competing_solutions` | 競品方案 | linklist |  | TestSolution |  |
| `reference_customers` | 參考客戶 | linklist |  | Account |  |
| `status` | 狀態 | enum | `planning`, `available`, `EOL` |  |  |
| `owner` | 負責人 | str |  |  |  |
| `confidence` | 信心度 | enum | `verified`, `assumed` |  |  |
| `updated` | 更新日期 | date |  |  |  |
| `body` | 備註 | str |  |  |  |

## Application — 應用

- Named by: `name`
- Domain: one

| Field | Label | Kind | Allowed values | Links to | Required |
|---|---|---|---|---|---|
| `name` | 應用名稱 | str |  |  | yes |
| `domain` | 領域 | enum | `wireless`, `AIDC`, `robotics`, `mobile`, `aerospace` |  |  |
| `value_chain` | 價值鏈 | enum | `L1`, `L2`, `L3`, `L4`, `L5`, `X` |  |  |
| `lifecycle` | 生命週期 | enum | `RD`, `Certification`, `Production`, `Reliability`, `Field` |  |  |
| `nodes` | 節點 | linklist |  | Node |  |
| `technologies` | 技術 | linklist |  | Technology |  |
| `trends` | 趨勢 | linklist |  | Trend |  |
| `measurement_topics` | 量測主題 | list |  |  |  |
| `confidence` | 信心度 | enum | `verified`, `assumed` |  |  |
| `updated` | 更新日期 | date |  |  |  |
| `body` | 備註 | str |  |  |  |

## Competitor — 競品

- Named by: `name`
- Domain: multi

| Field | Label | Kind | Allowed values | Links to | Required |
|---|---|---|---|---|---|
| `name` | 名稱 | str |  |  | yes |
| `domain` | 領域 | list |  |  |  |
| `node` | 節點 | link |  | Node |  |
| `nodes` | 涉及節點 | linklist |  | Node |  |
| `technologies` | 技術 | linklist |  | Technology |  |
| `product_lines` | 產品線 | list |  |  |  |
| `strengths` | 強項 | list |  |  |  |
| `weaknesses` | 弱項 | list |  |  |  |
| `pricing_position` | 價格定位 | enum | `low`, `par`, `premium` |  |  |
| `recent_moves` | 近期動態 | list |  |  |  |
| `ticker` | 代號 | str |  |  |  |
| `confidence` | 信心度 | enum | `verified`, `assumed` |  |  |
| `updated` | 更新日期 | date |  |  |  |
| `body` | 備註 | str |  |  |  |

## CustomerProduct — 客戶產品

- Named by: `product_name`
- Domain: one

| Field | Label | Kind | Allowed values | Links to | Required |
|---|---|---|---|---|---|
| `product_name` | 產品名稱 | str |  |  | yes |
| `domain` | 領域 | enum | `wireless`, `AIDC`, `robotics`, `mobile`, `aerospace` |  |  |
| `account` | 客戶 | link |  | Account |  |
| `node` | 節點 | link |  | Node |  |
| `nodes` | 涉及節點 | linklist |  | Node |  |
| `technologies` | 技術 | linklist |  | Technology |  |
| `chipset_modules` | 晶片模組 | linklist |  | Ecosystem, Account |  |
| `ecosystem` | 供應鏈成員 | linklist |  | Ecosystem, Account |  |
| `launch_window` | 上市時程 | str |  |  |  |
| `launch_date` | 預估上市日 | date |  |  |  |
| `volume_tier` | 量級 | enum | `low`, `mid`, `high` |  |  |
| `test_stage_now` | 目前階段 | enum | `RD`, `cert`, `production` |  |  |
| `inferred_applications` | 推論應用 | linklist |  | Application |  |
| `segment` | 區段 | list | `space`, `gateway`, `ut`, `launch`, `mro`, `cell-phone`, `ap-cpe`, `module-iot`, `aidc-computing`, `aidc-power`, `car-ebus-electronics`, `robotics-amr`, `space-satellite`, `uav`, `radar-ew`, `osat` |  |  |
| `confidence` | 信心度 | enum | `verified`, `assumed` |  |  |
| `updated` | 更新日期 | date |  |  |  |
| `body` | 備註 | str |  |  |  |

## Ecosystem — 生態系

- Named by: `name`
- Domain: multi

| Field | Label | Kind | Allowed values | Links to | Required |
|---|---|---|---|---|---|
| `name` | 名稱 | str |  |  | yes |
| `domain` | 領域 | list |  |  |  |
| `node` | 節點 | link |  | Node |  |
| `nodes` | 涉及節點 | linklist |  | Node |  |
| `role` | 角色 | enum | `chipset`, `module`, `ODM`, `OEM`, `carrier`, `cert-lab`, `integrator`, `distributor`, `standards`, `component`, `osat`, `foundry`, `test-equipment`, `institute`, `ipc`, `material`, `operator`, `hyperscaler`, `power-system`, `thermal-system` |  |  |
| `segment` | 區段 | list | `space`, `gateway`, `ut`, `launch`, `mro`, `cell-phone`, `ap-cpe`, `module-iot`, `aidc-computing`, `aidc-power`, `car-ebus-electronics`, `robotics-amr`, `space-satellite`, `uav`, `radar-ew`, `osat` |  |  |
| `technologies` | 技術 | linklist |  | Technology |  |
| `relationship_to_us` | 與我關係 | enum | `customer`, `partner`, `influencer`, `competitor`, `none` |  |  |
| `influence_on` | 影響客戶 | linklist |  | Account |  |
| `reference_design` | 參考設計 | bool |  |  |  |
| `ticker` | 代號 | str |  |  |  |
| `confidence` | 信心度 | enum | `verified`, `assumed` |  |  |
| `updated` | 更新日期 | date |  |  |  |
| `body` | 備註 | str |  |  |  |

## Account — 客戶

- Named by: `name`
- Domain: multi

| Field | Label | Kind | Allowed values | Links to | Required |
|---|---|---|---|---|---|
| `name` | 客戶名稱 | str |  |  | yes |
| `domain` | 領域 | list |  |  |  |
| `node` | 節點 | link |  | Node |  |
| `nodes` | 涉及節點 | linklist |  | Node |  |
| `key_suppliers` | 主要供應商 | linklist |  | Ecosystem, Account |  |
| `key_customers` | 主要客戶 | linklist |  | Account, Ecosystem |  |
| `region` | 地區 | str |  |  |  |
| `segment` | 區段 | list | `space`, `gateway`, `ut`, `launch`, `mro`, `cell-phone`, `ap-cpe`, `module-iot`, `aidc-computing`, `aidc-power`, `car-ebus-electronics`, `robotics-amr`, `space-satellite`, `uav`, `radar-ew`, `osat` |  |  |
| `ticker` | 代號 | str |  |  |  |
| `body` | 備註 | str |  |  |  |

## Node — 價值鏈節點

- Named by: `name`
- Domain: multi

| Field | Label | Kind | Allowed values | Links to | Required |
|---|---|---|---|---|---|
| `name` | 節點 | str |  |  | yes |
| `domain` | 領域 | list |  |  |  |
| `layer` | 層級 | enum | `L1`, `L2`, `L3`, `L4`, `L5`, `X` |  |  |
| `upstream` | 上游 | linklist |  | Node |  |
| `downstream` | 下游 | linklist |  | Node |  |
| `typical_test_needs` | 典型量測需求 | list |  |  |  |
| `body` | 備註 | str |  |  |  |

## Technology — 技術

- Named by: `name`
- Domain: multi

| Field | Label | Kind | Allowed values | Links to | Required |
|---|---|---|---|---|---|
| `name` | 技術 | str |  |  | yes |
| `domain` | 領域 | list |  |  |  |
| `standard_body` | 標準組織 | str |  |  |  |
| `spec_milestones` | 標準時程 | list |  |  |  |
| `maturity` | 成熟度 | enum | `emerging`, `growth`, `mature`, `declining` |  |  |
| `affects_nodes` | 影響節點 | linklist |  | Node |  |
| `new_test_requirements` | 新增測試需求 | list |  |  |  |
| `confidence` | 信心度 | enum | `verified`, `assumed` |  |  |
| `updated` | 更新日期 | date |  |  |  |
| `body` | 備註 | str |  |  |  |

## Concept — 概念

- Named by: `name`
- Domain: multi

| Field | Label | Kind | Allowed values | Links to | Required |
|---|---|---|---|---|---|
| `name` | 名詞 | str |  |  | yes |
| `domain` | 領域 | list |  |  |  |
| `aliases` | 別名 | list |  |  |  |
| `category` | 類別 | enum | `radio`, `protocol`, `metric`, `measurement`, `standard`, `device` |  |  |
| `one_liner` | 一句話 | str |  |  |  |
| `analogy` | 比喻 | str |  |  |  |
| `technologies` | 相關技術 | linklist |  | Technology |  |
| `applications` | 相關應用 | linklist |  | Application |  |
| `test_solutions` | 相關方案 | linklist |  | TestSolution |  |
| `related_concepts` | 相關概念 | linklist |  | Concept |  |
| `audience` | 對象 | enum | `sales`, `sales+FAE`, `engineer` |  |  |
| `review_status` | 審閱狀態 | enum | `draft`, `reviewed` |  |  |
| `reviewer` | 審閱者 | str |  |  |  |
| `confidence` | 信心度 | enum | `verified`, `assumed` |  |  |
| `updated` | 更新日期 | date |  |  |  |
| `body` | 備註 | str |  |  |  |

## Trend — 趨勢

- Named by: `name`
- Domain: one

| Field | Label | Kind | Allowed values | Links to | Required |
|---|---|---|---|---|---|
| `name` | 趨勢 | str |  |  | yes |
| `domain` | 領域 | enum | `wireless`, `AIDC`, `robotics`, `mobile`, `aerospace` |  |  |
| `related_tech` | 相關技術 | linklist |  | Technology |  |
| `affected_nodes` | 影響節點 | linklist |  | Node |  |
| `related_ecosystem` | 相關生態系 | linklist |  | Ecosystem, Account |  |
| `related_applications` | 相關應用 | linklist |  | Application |  |
| `stage` | 階段 | enum | `watch`, `emerging`, `accelerating`, `peak`, `fading` |  |  |
| `time_to_demand` | 需求時間 | enum | `0-6m`, `6-18m`, `18-36m`, `36m+` |  |  |
| `market_impact` | 市場影響 | int | 1 – 5 |  |  |
| `measurement_impact` | 量測影響 | int | 1 – 5 |  |  |
| `our_fit` | 我方契合度 | int | 1 – 5 |  |  |
| `confidence` | 信心度 | enum | `verified`, `assumed` |  |  |
| `updated` | 更新日期 | date |  |  |  |
| `body` | 備註 | str |  |  |  |

## Signal — 訊號

- Named by: `date`, `title`
- Domain: one

| Field | Label | Kind | Allowed values | Links to | Required |
|---|---|---|---|---|---|
| `title` | 標題 | virtual |  |  | yes |
| `domain` | 領域 | enum | `wireless`, `AIDC`, `robotics`, `mobile`, `aerospace` |  |  |
| `date` | 日期 | date |  |  | yes |
| `source_type` | 來源類型 | enum | `standard`, `regulator`, `report`, `filing`, `news`, `conference`, `customer`, `competitor`, `internal` |  |  |
| `source` | 來源 | str |  |  |  |
| `summary` | 摘要 | str |  |  | yes |
| `related` | 相關 | linklist |  |  |  |
| `so_what` | 所以呢 | str |  |  | yes |
| `reliability` | 可靠度 | enum | `high`, `medium`, `low` |  |  |
| `body` | 備註 | str |  |  |  |

## WinLoss — 輸贏分析

- Named by: `name`
- Domain: one

| Field | Label | Kind | Allowed values | Links to | Required |
|---|---|---|---|---|---|
| `name` | 案例名稱 | str |  |  | yes |
| `domain` | 領域 | enum | `wireless`, `AIDC`, `robotics`, `mobile`, `aerospace` |  |  |
| `opportunity` | 商機 | link |  | Opportunity |  |
| `account` | 客戶 | link |  | Account |  |
| `outcome` | 結果 | enum | `won`, `lost`, `no-decision` |  |  |
| `decided_date` | 決定日 | date |  |  |  |
| `applications` | 對應應用 | linklist |  | Application |  |
| `our_solutions` | 我方方案 | linklist |  | TestSolution |  |
| `competitors` | 競爭對手 | linklist |  | Competitor |  |
| `winner` | 勝出者 | link |  | Competitor, Ecosystem, Account |  |
| `primary_reason` | 主要原因 | enum | `price`, `performance`, `features`, `relationship`, `timing`, `incumbent`, `budget`, `other` |  |  |
| `gaps` | 缺口 | list |  |  |  |
| `lessons` | 心得 | list |  |  |  |
| `confidence` | 信心度 | enum | `verified`, `assumed` |  |  |
| `updated` | 更新日期 | date |  |  |  |
| `body` | 備註 | str |  |  |  |

## RoadmapRequest — 產品需求

- Named by: `name`
- Domain: one

| Field | Label | Kind | Allowed values | Links to | Required |
|---|---|---|---|---|---|
| `name` | 需求名稱 | str |  |  | yes |
| `domain` | 領域 | enum | `wireless`, `AIDC`, `robotics`, `mobile`, `aerospace` |  |  |
| `applications` | 對應應用 | linklist |  | Application |  |
| `our_solutions` | 我方方案 | linklist |  | TestSolution |  |
| `competitors` | 相關競品 | linklist |  | Competitor |  |
| `source_win_loss` | 來源案例 | linklist |  | WinLoss |  |
| `source_opportunities` | 來源商機 | linklist |  | Opportunity |  |
| `gap_type` | 缺口類型 | enum | `feature`, `performance`, `price`, `integration`, `certification`, `service` |  |  |
| `impact` | 影響程度 | int | 1 – 5 |  |  |
| `customer_count` | 受影響客戶數 | int |  |  |  |
| `request_status` | 需求狀態 | enum | `idea`, `submitted`, `accepted`, `planned`, `shipped`, `declined` |  |  |
| `target_release` | 目標版本 | str |  |  |  |
| `owner` | 負責人 | str |  |  |  |
| `confidence` | 信心度 | enum | `verified`, `assumed` |  |  |
| `updated` | 更新日期 | date |  |  |  |
| `body` | 備註 | str |  |  |  |

## Pitch — 簡報

- Named by: `name`
- Domain: multi

| Field | Label | Kind | Allowed values | Links to | Required |
|---|---|---|---|---|---|
| `name` | 簡報名稱 | str |  |  | yes |
| `domain` | 領域 | list |  |  |  |
| `pitch_audience` | 對象 | enum | `sales`, `customer-engineer`, `customer-manager`, `executive` |  |  |
| `applications` | 對應應用 | linklist |  | Application |  |
| `our_solutions` | 我方方案 | linklist |  | TestSolution |  |
| `technologies` | 技術 | linklist |  | Technology |  |
| `concepts` | 白話概念 | linklist |  | Concept |  |
| `accounts` | 適用客戶 | linklist |  | Account |  |
| `duration_min` | 時間(分鐘) | int | 1 – 180 |  |  |
| `content_status` | 內容狀態 | enum | `draft`, `reviewed`, `in-use` |  |  |
| `owner` | 負責人 | str |  |  |  |
| `confidence` | 信心度 | enum | `verified`, `assumed` |  |  |
| `updated` | 更新日期 | date |  |  |  |
| `body` | 備註 | str |  |  |  |

## DemoScript — 展示腳本

- Named by: `name`
- Domain: multi

| Field | Label | Kind | Allowed values | Links to | Required |
|---|---|---|---|---|---|
| `name` | 腳本名稱 | str |  |  | yes |
| `domain` | 領域 | list |  |  |  |
| `our_solutions` | 我方方案 | linklist |  | TestSolution |  |
| `applications` | 對應應用 | linklist |  | Application |  |
| `duration_min` | 時間(分鐘) | int | 1 – 480 |  |  |
| `demo_env` | 展示環境 | list |  |  |  |
| `content_status` | 內容狀態 | enum | `draft`, `reviewed`, `in-use` |  |  |
| `owner` | 負責人 | str |  |  |  |
| `confidence` | 信心度 | enum | `verified`, `assumed` |  |  |
| `updated` | 更新日期 | date |  |  |  |
| `body` | 備註 | str |  |  |  |

## Battlecard — 對戰卡

- Named by: `name`
- Domain: multi

| Field | Label | Kind | Allowed values | Links to | Required |
|---|---|---|---|---|---|
| `name` | 名稱 | str |  |  | yes |
| `domain` | 領域 | list |  |  |  |
| `competitor` | 競爭對手 | link |  | Competitor | yes |
| `our_solutions` | 我方方案 | linklist |  | TestSolution |  |
| `applications` | 對應應用 | linklist |  | Application |  |
| `competing_solutions` | 對手方案 | linklist |  | TestSolution |  |
| `our_advantages` | 我方優勢 | list |  |  |  |
| `our_weaknesses` | 我方弱點 | list |  |  |  |
| `content_status` | 內容狀態 | enum | `draft`, `reviewed`, `in-use` |  |  |
| `owner` | 負責人 | str |  |  |  |
| `confidence` | 信心度 | enum | `verified`, `assumed` |  |  |
| `updated` | 更新日期 | date |  |  |  |
| `body` | 備註 | str |  |  |  |

## Contact — 聯絡人

- Named by: `name`
- Domain: multi

| Field | Label | Kind | Allowed values | Links to | Required |
|---|---|---|---|---|---|
| `name` | 姓名 | str |  |  | yes |
| `domain` | 領域 | list |  |  |  |
| `account` | 客戶 | link |  | Account |  |
| `job_title` | 職稱 | str |  |  |  |
| `contact_function` | 職能 | enum | `procurement`, `rd`, `test`, `quality`, `management`, `sales`, `other` |  |  |
| `decision_role` | 決策角色 | enum | `decision`, `influencer`, `user`, `gatekeeper` |  |  |
| `relationship_status` | 關係 | enum | `champion`, `supporter`, `neutral`, `blocker`, `unknown` |  |  |
| `reports_to` | 主管 | link |  | Contact |  |
| `applications` | 關注應用 | linklist |  | Application |  |
| `last_contact` | 最近聯絡 | date |  |  |  |
| `body` | 備註 | str |  |  |  |

## VisitLog — 拜訪紀錄

- Named by: `date`, `title`
- Domain: one

| Field | Label | Kind | Allowed values | Links to | Required |
|---|---|---|---|---|---|
| `title` | 標題 | virtual |  |  | yes |
| `domain` | 領域 | enum | `wireless`, `AIDC`, `robotics`, `mobile`, `aerospace` |  |  |
| `date` | 日期 | date |  |  | yes |
| `account` | 客戶 | link |  | Account |  |
| `contacts` | 對象 | linklist |  | Contact |  |
| `opportunity` | 商機 | link |  | Opportunity |  |
| `applications` | 討論應用 | linklist |  | Application |  |
| `our_solutions` | 討論方案 | linklist |  | TestSolution |  |
| `visit_type` | 類型 | enum | `visit`, `call`, `demo`, `workshop`, `conference`, `email` |  |  |
| `summary` | 摘要 | str |  |  | yes |
| `next_steps` | 下一步 | list |  |  |  |
| `follow_up_date` | 跟進日 | date |  |  |  |
| `body` | 備註 | str |  |  |  |

## SupplyLink — 供貨關係

- Named by: `name`
- Domain: multi

| Field | Label | Kind | Allowed values | Links to | Required |
|---|---|---|---|---|---|
| `name` | 供貨關係 | str |  |  | yes |
| `domain` | 領域 | list |  |  |  |
| `supplier` | 供應商 | link |  | Ecosystem, Account | yes |
| `customer` | 客戶 | link |  | Account, Ecosystem |  |
| `product` | 交付品 | str |  |  |  |
| `platform` | 平台 | str |  |  |  |
| `segment` | 區段 | list | `space`, `gateway`, `ut`, `launch`, `mro`, `cell-phone`, `ap-cpe`, `module-iot`, `aidc-computing`, `aidc-power`, `car-ebus-electronics`, `robotics-amr`, `space-satellite`, `uav`, `radar-ew`, `osat` |  |  |
| `nodes` | 涉及節點 | linklist |  | Node |  |
| `technologies` | 技術 | linklist |  | Technology |  |
| `customer_products` | 客戶產品 | linklist |  | CustomerProduct |  |
| `evidence_grade` | 證據等級 | enum | `A`, `B`, `C`, `D` |  |  |
| `supply_stage` | 供貨階段 | enum | `demo`, `sample`, `cert`, `pilot`, `mass` |  |  |
| `source` | 來源 | str |  |  |  |
| `source_date` | 來源日期 | date |  |  |  |
| `not_confirmed` | 尚待確認 | list |  |  |  |
| `confidence` | 信心度 | enum | `verified`, `assumed` |  |  |
| `updated` | 更新日期 | date |  |  |  |
| `body` | 備註 | str |  |  |  |

## RevenueFact — 收入事實

- Named by: `name`
- Domain: multi

| Field | Label | Kind | Allowed values | Links to | Required |
|---|---|---|---|---|---|
| `name` | 名稱 | str |  |  | yes |
| `domain` | 領域 | list |  |  |  |
| `company` | 公司 | link |  | Account, Ecosystem, Competitor | yes |
| `period` | 期間 | str |  |  | yes |
| `rev_layer` | 收入層級 | enum | `company`, `segment`, `customer` |  | yes |
| `customer` | 客戶 | link |  | Account, Ecosystem |  |
| `segment_name` | 區段名稱 | str |  |  |  |
| `amount` | 金額 | float |  |  |  |
| `share_pct` | 占比 | float | 0 – 100 |  |  |
| `yoy_pct` | 年增 | float |  |  |  |
| `unit` | 單位 | str |  |  |  |
| `basis` | 口徑 | enum | `reported`, `media`, `estimated`, `target` |  |  |
| `source` | 來源 | str |  |  |  |
| `source_date` | 來源日期 | date |  |  |  |
| `not_confirmed` | 不可比較 | list |  |  |  |
| `confidence` | 信心度 | enum | `verified`, `assumed` |  |  |
| `updated` | 更新日期 | date |  |  |  |
| `body` | 備註 | str |  |  |  |
