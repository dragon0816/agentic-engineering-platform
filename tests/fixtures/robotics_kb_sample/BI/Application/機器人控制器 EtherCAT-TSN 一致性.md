---
type: application
name: 機器人控制器 EtherCAT/TSN 一致性
domain: robotics
value_chain: L2
lifecycle: RD
nodes: ["[[L2-Controller-IPC]]"]
technologies: ["[[EtherCAT]]", "[[TSN]]"]
trends: ["[[工業網路 TSN 化]]", "[[協作機器人 AI 化與普及]]"]
measurement_topics: [週期抖動, 時間同步, 乙太網路實體層]
priority: 4
confidence: assumed
updated: 2026-10-21
ingested_from: application_robotics.csv
---

## 應用說明

[範例資料,待業務/FAE 驗證]

## 痛點與價值主張

## 對應的 Test Solution(廠商空白 = 我方 R&S)
```dataview
TABLE vendor AS 廠商
FROM "BI/TestSolution"
WHERE contains(applications, this.file.link)
SORT vendor ASC
```

## 相關商機
```dataview
TABLE account AS 客戶, deal_stage AS 階段, our_solutions AS 我方方案
FROM "BI/Opportunity"
WHERE contains(default(applications, []), this.file.link)
SORT deal_stage ASC
```
