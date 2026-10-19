---
type: application
name: 5G-FR2手機產線RF校正
value_chain: L3
lifecycle: Production
nodes: ["[[L3-Handset]]"]
technologies: ["[[5G-NR-FR2]]"]
measurement_topics: [TX 校正, RX 校正]
priority: 3
confidence: assumed
updated: 2026-10-14
ingested_from: application_sample.csv
---

## 應用說明

(虛構範例)尚未建立對應方案

## 痛點與價值主張

## 對應的 Test Solution(廠商空白 = 我方 R&S)
```dataview
TABLE vendor AS 廠商
FROM "BI/TestSolution"
WHERE contains(applications, this.file.link)
SORT vendor ASC
```
