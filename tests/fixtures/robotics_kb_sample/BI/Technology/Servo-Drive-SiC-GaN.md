---
type: technology
name: Servo-Drive-SiC-GaN
domain: [robotics]
maturity: emerging
affects_nodes: ["[[L2-Servo-Motor-Drive]]"]
new_test_requirements: [開關波形, 共模雜訊與 EMI, 死區時間]
confidence: assumed
updated: 2026-10-21
ingested_from: technology_robotics.csv
---

## 標準時程與重點

寬能隙功率元件使 EMC 與波形量測更關鍵。[範例資料,待業務/FAE 驗證]

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
