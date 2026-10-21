---
type: technology
name: BMS-Fast-Charging
domain: [robotics]
maturity: growth
affects_nodes: ["[[L2-Battery-Power-Module]]", "[[L3-AMR-AGV]]"]
new_test_requirements: [充放電曲線, 電池模擬, 保護電路時序]
confidence: assumed
updated: 2026-10-21
ingested_from: technology_robotics.csv
---

## 標準時程與重點

AMR 稼動率與快充需求拉動。[範例資料,待業務/FAE 驗證]

## 新增或加嚴的量測需求

## 相關概念(給業務的白話解釋)
```dataview
TABLE one_liner AS 一句話
FROM "BI/Concept"
WHERE contains(technologies, this.file.link)
```

## 相關趨勢
```dataview
LIST
FROM "BI/Trend"
WHERE contains(related_tech, this.file.link)
```
