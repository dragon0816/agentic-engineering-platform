---
type: application
name: AMR 電池包 BMS 與充電驗證
domain: robotics
value_chain: L2
lifecycle: Production
nodes: ["[[L2-Battery-Power-Module]]", "[[L3-AMR-AGV]]"]
technologies: ["[[BMS-Fast-Charging]]"]
trends: ["[[AMR 滲透工廠與倉儲]]", "[[快充與高稼動電池]]"]
measurement_topics: [充放電曲線, 保護時序, 電池模擬]
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
