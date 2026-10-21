---
type: test_solution
name: "R&S UWB 定位射頻量測方案"
domain: [wireless, robotics]
applications: ["[[AMR 毫米波雷達與 UWB 定位量測]]"]
technologies: ["[[UWB]]"]
nodes: ["[[L1-Robot-Chipset]]", "[[L2-Sensing-Module]]"]
test_type: spectrum
tier: instrument
automation: semi
dut: UWB 晶片/模組
test_items: [脈衝波形, 頻譜遮罩, 測距]
standards: [IEEE 802.15.4z]
instruments: [向量訊號產生器 + 訊號分析儀]
price_band: high
status: planning
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
