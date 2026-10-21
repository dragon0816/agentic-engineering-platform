---
type: test_solution
name: Keysight 電池與電驅動測試
domain: [robotics]
vendor: "[[Keysight]]"
applications: ["[[AMR 電池包 BMS 與充電驗證]]"]
technologies: ["[[BMS-Fast-Charging]]"]
test_type: power
tier: integrated
automation: full
price_band: high
status: available
confidence: assumed
updated: 2026-10-21
ingested_from: test_solutions_robotics.csv
---

## 方案概要

競品方案;我方沒有對應方案。[範例資料,待業務/FAE 驗證]

## 技術架構與測試流程
- 連接架構(Block Diagram):
- 測試流程:

## 驗證與證據
- Demo 環境與腳本:
- 實測資料與 App Note:
- 成功案例(注意保密):

## 競爭定位(Battlecard)
- 我方差異化賣點:
- 弱點與常見異議:
- 回應話術:

## Discovery Questions
- 

## 回饋與演進
- 客戶回報的缺口 → Roadmap Request:

## 相關商機
```dataview
TABLE account AS 客戶, deal_stage AS 階段, expected_close AS 預計成交
FROM "BI/Opportunity"
WHERE contains(default(our_solutions, []), this.file.link)
SORT expected_close ASC
```
