---
type: application
name: 邊緣 AI SoC 電源完整性
domain: robotics
value_chain: L1
lifecycle: RD
nodes: ["[[L1-Robot-Chipset]]"]
technologies: ["[[Edge-AI-SoC]]"]
trends: ["[[人形機器人走向量產]]"]
measurement_topics: [電源軌雜訊與瞬態, 高速介面]
priority: 3
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
