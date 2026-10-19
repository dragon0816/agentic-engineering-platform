---
type: application
name: WiFi7-MLO互通與吞吐量驗證
value_chain: L3
lifecycle: Certification
nodes: ["[[L3-WiFi-Router-CPE]]"]
technologies: ["[[WiFi-7]]"]
trends: ["[[WiFi7普及與下一代預備]]"]
measurement_topics: [互通, 吞吐量, 共存]
priority: 4
confidence: assumed
updated: 2026-10-14
ingested_from: application_sample.csv
---

## 應用說明

(虛構範例)MLO 多連結運作的互通與效能驗證。

## 痛點與價值主張

## 對應的 Test Solution(廠商空白 = 我方 R&S)
```dataview
TABLE vendor AS 廠商
FROM "BI/TestSolution"
WHERE contains(applications, this.file.link)
SORT vendor ASC
```
