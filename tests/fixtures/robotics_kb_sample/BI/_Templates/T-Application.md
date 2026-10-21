---
type: application
name: <% tp.file.title %>
domain: wireless  # wireless | AIDC | robotics
value_chain:   # L1 | L2 | L3 | L4 | L5 | X
lifecycle:   # RD | Certification | Production | Reliability | Field
nodes: []
technologies: []
trends: []
measurement_topics: []
priority:   # 1-5
confidence: assumed  # verified | assumed
updated: <% tp.date.now("YYYY-MM-DD") %>
---

## 應用說明

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
