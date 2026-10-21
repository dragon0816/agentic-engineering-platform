---
type: technology
name: Edge-AI-SoC
domain: [robotics, AIDC]
maturity: growth
affects_nodes: ["[[L1-Robot-Chipset]]", "[[L2-Controller-IPC]]"]
new_test_requirements: [電源完整性, 高速介面(MIPI/PCIe/乙太網路), 熱與瞬態負載]
confidence: assumed
updated: 2026-10-21
ingested_from: technology_robotics.csv
---

## 標準時程與重點

與 AIDC 的電源與高速介面量測共用。[範例資料,待業務/FAE 驗證]

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
