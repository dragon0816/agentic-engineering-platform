---
type: technology
name: <% tp.file.title %>
standard_body:
spec_milestones: []
maturity:   # emerging | growth | mature | declining
affects_nodes: []
new_test_requirements: []
confidence: assumed  # verified | assumed
updated: <% tp.date.now("YYYY-MM-DD") %>
---

## 標準時程與重點

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
