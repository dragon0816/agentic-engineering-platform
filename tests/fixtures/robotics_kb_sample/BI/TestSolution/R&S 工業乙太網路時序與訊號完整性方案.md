---
type: test_solution
name: "R&S 工業乙太網路時序與訊號完整性方案"
domain: [robotics, AIDC]
applications: ["[[機器人控制器 EtherCAT-TSN 一致性]]"]
technologies: ["[[EtherCAT]]", "[[TSN]]"]
nodes: ["[[L2-Controller-IPC]]", "[[L2-Servo-Motor-Drive]]"]
test_type: signal-integrity
tier: instrument
automation: semi
dut: 控制器;伺服驅動器乙太網路埠
test_items: [實體層波形, 封包時序與抖動]
standards: [IEEE 802.3, IEC 61158]
instruments: [示波器 + 協定解碼選配]
price_band: mid
competing_solutions: ["[[Keysight TSN 一致性方案]]"]
status: available
confidence: assumed
updated: 2026-10-21
ingested_from: test_solutions_robotics.csv
---

## 方案概要

可重用 AIDC 的乙太網路量測配置。[範例資料,待業務/FAE 驗證]

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
