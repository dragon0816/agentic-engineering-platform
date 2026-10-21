---
type: technology
name: EtherCAT
domain: [robotics]
standard_body: ETG
spec_milestones: [持續演進]
maturity: mature
affects_nodes: ["[[L2-Servo-Motor-Drive]]", "[[L2-Controller-IPC]]"]
new_test_requirements: [主站/從站一致性, 週期抖動, 同步精度]
confidence: assumed
updated: 2026-10-21
ingested_from: technology_robotics.csv
---

## 標準時程與重點

機器人與伺服最常見的即時工業乙太網路之一。[範例資料,待業務/FAE 驗證]

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
