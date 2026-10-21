---
type: test_solution
name: "R&S 機器人 Wi-Fi/藍牙射頻測試方案"
domain: [wireless, robotics]
applications: ["[[機器人無線連線射頻與共存]]"]
technologies: ["[[Wi-Fi-7]]"]
nodes: ["[[L2-Comms-Module]]", "[[L3-AMR-AGV]]"]
test_type: conducted
tier: integrated
automation: full
dut: 機器人無線模組;整機
test_items: [發射功率/EVM, 接收靈敏度, 吞吐量]
standards: [IEEE 802.11be]
instruments: [無線通訊測試儀 + 自動化軟體]
price_band: high
competing_solutions: ["[[LitePoint IQxel Wi-Fi 7 量產測試]]"]
status: available
confidence: assumed
updated: 2026-10-21
ingested_from: test_solutions_robotics.csv
---

## 方案概要

尚無對應產線 EOL 的快速測試版本(Dashboard §6 缺口)。[範例資料,待業務/FAE 驗證]

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
