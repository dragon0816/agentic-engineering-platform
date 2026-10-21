---
type: application
name: 機器人整機 EMC 與功能安全認證
domain: robotics
value_chain: X
lifecycle: Certification
nodes: ["[[X-Certification-Lab]]", "[[L3-Cobot-Arm]]", "[[L3-Humanoid-Quadruped]]"]
technologies: ["[[Functional-Safety]]"]
trends: ["[[機器人安全法規趨嚴]]"]
measurement_topics: [EMC 抗擾度, 安全迴路回應時間]
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
