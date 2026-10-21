---
type: application
name: AMR 毫米波雷達與 UWB 定位量測
domain: robotics
value_chain: L3
lifecycle: RD
nodes: ["[[L3-AMR-AGV]]", "[[L2-Sensing-Module]]"]
technologies: ["[[mmWave-Radar]]", "[[UWB]]"]
trends: ["[[AMR 滲透工廠與倉儲]]"]
measurement_topics: [FMCW 調變品質, 測距精度, 頻譜遮罩]
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
