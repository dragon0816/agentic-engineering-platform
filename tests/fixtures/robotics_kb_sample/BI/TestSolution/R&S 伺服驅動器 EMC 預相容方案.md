---
type: test_solution
name: "R&S 伺服驅動器 EMC 預相容方案"
domain: [robotics, wireless]
applications: ["[[伺服驅動器電源與 EMC 驗證]]", "[[機器人整機 EMC 與功能安全認證]]"]
technologies: ["[[Servo-Drive-SiC-GaN]]", "[[Functional-Safety]]"]
nodes: ["[[L2-Servo-Motor-Drive]]", "[[X-Certification-Lab]]"]
test_type: EMC
tier: integrated
automation: semi
dut: 伺服驅動器;機器人控制櫃
test_items: [傳導/輻射 EMI 預掃描]
standards: [CISPR 11, IEC 61800-3]
instruments: [EMI 測試接收機, LISN, 近場探棒]
price_band: mid
competing_solutions: ["[[Keysight PXE EMI 預相容方案]]"]
status: available
confidence: assumed
updated: 2026-10-21
ingested_from: test_solutions_robotics.csv
---

## 方案概要

型號與配置待 FAE 核對。[範例資料,待業務/FAE 驗證]

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
