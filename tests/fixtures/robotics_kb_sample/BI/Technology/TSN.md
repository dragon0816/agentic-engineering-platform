---
type: technology
name: TSN
domain: [robotics, AIDC]
standard_body: IEEE 802.1 / IEC/IEEE 60802
spec_milestones: [工業 profile 持續制定]
maturity: growth
affects_nodes: ["[[L2-Controller-IPC]]", "[[L3-Cobot-Arm]]", "[[L3-AMR-AGV]]"]
new_test_requirements: [時間同步(802.1AS), 排程流量(802.1Qbv), 乙太網路實體層一致性]
confidence: assumed
updated: 2026-10-21
ingested_from: technology_robotics.csv
---

## 標準時程與重點

與 AIDC 的乙太網路量測共用基礎能力。[範例資料,待業務/FAE 驗證]

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
