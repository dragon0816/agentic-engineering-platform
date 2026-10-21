---
type: technology
name: 5G-Private-Network
domain: [wireless, robotics]
standard_body: 3GPP
spec_milestones: [Rel-16/17 工業 IoT 功能]
maturity: growth
affects_nodes: ["[[L2-Comms-Module]]", "[[L3-AMR-AGV]]", "[[L5-Factory-Deployment]]"]
new_test_requirements: [URLLC 時延, 切換與漫遊, 工廠現場覆蓋]
confidence: assumed
updated: 2026-10-21
ingested_from: technology_robotics.csv
---

## 標準時程與重點

沿用 Wireless KB 的 5G 概念,工廠場域另有時延與可靠度需求。[範例資料,待業務/FAE 驗證]

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
