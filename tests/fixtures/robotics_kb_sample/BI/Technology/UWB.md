---
type: technology
name: UWB
domain: [wireless, robotics]
standard_body: IEEE 802.15.4z / FiRa
spec_milestones: [已商用]
maturity: growth
affects_nodes: ["[[L1-Robot-Chipset]]", "[[L2-Sensing-Module]]", "[[L3-AMR-AGV]]"]
new_test_requirements: [測距精度, 脈衝波形與頻譜遮罩]
confidence: assumed
updated: 2026-10-21
ingested_from: technology_robotics.csv
---

## 標準時程與重點

室內精準定位與人員安全區域。[範例資料,待業務/FAE 驗證]

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
