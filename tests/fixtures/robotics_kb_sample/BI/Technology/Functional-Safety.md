---
type: technology
name: Functional-Safety
domain: [robotics]
standard_body: ISO / IEC
spec_milestones: [ISO 10218 修訂版已發布(請查證施行日期)]
maturity: growth
affects_nodes: ["[[L2-Controller-IPC]]", "[[L3-Cobot-Arm]]", "[[L3-Humanoid-Quadruped]]", "[[X-Certification-Lab]]"]
new_test_requirements: [安全迴路回應時間, 安全 I/O 與通訊, EMC 抗擾度]
confidence: assumed
updated: 2026-10-21
ingested_from: technology_robotics.csv
---

## 標準時程與重點

多為認證與法規驅動需求。[範例資料,待業務/FAE 驗證]

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
