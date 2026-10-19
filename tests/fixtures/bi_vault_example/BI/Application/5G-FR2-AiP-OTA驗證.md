---
type: application
name: 5G-FR2-AiP-OTA驗證
value_chain: L2
lifecycle: RD
nodes: ["[[L2-Antenna-Module]]"]
technologies: ["[[5G-NR-FR2]]"]
trends: ["[[多無線電共存與邊緣AI終端]]"]
measurement_topics: [OTA, 波束成型, EIRP]
priority: 4
confidence: assumed
updated: 2026-10-14
ingested_from: application_sample.csv
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
