---
type: trend
name: 多無線電共存與邊緣AI終端
related_tech: ["[[5G-NR-FR2]]", "[[WiFi-7]]"]
affected_nodes: ["[[L3-Handset]]"]
related_applications: []
stage: accelerating
time_to_demand: 6-18m
market_impact: 5
measurement_impact: 3
our_fit: 3
confidence: assumed
updated: 2026-10-13
---

## 趨勢描述
終端整合更多無線電與運算,功耗、散熱與共存成為挑戰。

## 為什麼影響量測
共存、功耗與熱管理測試比重提高。

## 證據(Signal)
```dataview
TABLE date, summary, reliability
FROM "BI/Signal"
WHERE contains(related, this.file.link)
SORT date DESC
```
