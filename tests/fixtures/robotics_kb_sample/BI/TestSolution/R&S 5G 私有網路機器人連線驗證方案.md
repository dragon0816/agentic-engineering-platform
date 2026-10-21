---
type: test_solution
name: "R&S 5G 私有網路機器人連線驗證方案"
domain: [wireless, robotics]
applications: ["[[機器人無線連線射頻與共存]]", "[[工廠現場無線覆蓋與干擾排查]]"]
technologies: ["[[5G-Private-Network]]"]
nodes: ["[[L2-Comms-Module]]", "[[L5-Factory-Deployment]]"]
test_type: protocol
tier: integrated
automation: semi
dut: 5G 模組;AMR
test_items: [協定一致性, 時延, 切換]
standards: [3GPP Rel-16/17]
instruments: [5G 無線通訊測試儀]
price_band: high
competing_solutions: ["[[Keysight UXM 5G 無線測試]]", "[[Anritsu MT8000A 5G 測試]]"]
status: available
confidence: assumed
updated: 2026-10-21
ingested_from: test_solutions_robotics.csv
---

## 方案概要

[範例資料,待業務/FAE 驗證]

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
