---
type: trend
name: <% tp.file.title %>
domain: wireless  # wireless | AIDC | robotics
related_tech: []
affected_nodes: []
related_applications: []
stage:   # watch | emerging | accelerating | peak | fading
time_to_demand:   # 0-6m | 6-18m | 18-36m | 36m+
market_impact:   # 1-5
measurement_impact:   # 1-5
our_fit:   # 1-5
confidence: assumed  # verified | assumed
updated: <% tp.date.now("YYYY-MM-DD") %>
---

## 趨勢描述

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
