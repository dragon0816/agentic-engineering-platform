---
type: trend
name: 工業網路 TSN 化
domain: robotics
related_tech: ["[[TSN]]", "[[EtherCAT]]"]
affected_nodes: ["[[L2-Controller-IPC]]", "[[L2-Servo-Motor-Drive]]"]
related_applications: ["[[機器人控制器 EtherCAT-TSN 一致性]]"]
stage: emerging
time_to_demand: 6-18m
market_impact: 3
measurement_impact: 4
our_fit: 5
confidence: assumed
updated: 2026-10-21
ingested_from: trend_robotics.csv
---

## 趨勢描述

可借用 AIDC 乙太網路量測能力。[範例資料,待業務/FAE 驗證]

## 為什麼對量測需求有影響

## 證據(Signal)
```dataview
TABLE date, summary, reliability
FROM "BI/Signal"
WHERE contains(related, this.file.link)
SORT date DESC
```

## 受影響的客戶產品(經技術或節點推得)
```dataview
TABLE account AS 客戶, node AS 節點, launch_date AS 上市日
FROM "BI/CustomerProduct"
WHERE length(filter(default(this.related_tech, []), (t) => contains(default(technologies, []), t))) > 0
   OR length(filter(default(this.affected_nodes, []), (n) => contains(default(nodes, []), n) OR n = node)) > 0
SORT launch_date ASC
```

## 我們的行動
