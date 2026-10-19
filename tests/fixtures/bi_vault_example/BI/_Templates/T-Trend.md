---
type: trend
name: <% tp.file.title %>
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

## 我們的行動
