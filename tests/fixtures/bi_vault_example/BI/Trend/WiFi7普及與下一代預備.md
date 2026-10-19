---
type: trend
name: WiFi7普及與下一代預備
related_tech: ["[[WiFi-7]]"]
affected_nodes: ["[[L1-Chipset]]", "[[L3-WiFi-Router-CPE]]", "[[L3-Handset]]"]
related_applications: []
stage: accelerating
time_to_demand: 0-6m
market_impact: 4
measurement_impact: 4
our_fit: 4
confidence: assumed
updated: 2026-10-13
---

## 趨勢描述
Wi-Fi 7 裝置滲透率上升,廠商開始評估下一代。

## 為什麼影響量測
寬頻寬與高階調變拉高 EVM 與線性度要求,MLO 增加互通測試。

## 證據(Signal)
```dataview
TABLE date, summary, reliability
FROM "BI/Signal"
WHERE contains(related, this.file.link)
SORT date DESC
```
