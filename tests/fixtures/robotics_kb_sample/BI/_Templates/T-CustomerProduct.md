---
type: customer_product
product_name: <% tp.file.title %>
domain: wireless  # wireless | AIDC | robotics
account:
node:
nodes: []
technologies: []
chipset_modules: []
ecosystem: []
launch_window:
launch_date:
volume_tier:   # low | mid | high
test_stage_now:   # RD | cert | production
inferred_applications: []
confidence: assumed  # verified | assumed
updated: <% tp.date.now("YYYY-MM-DD") %>
---

## 產品概述

## 時程(研發、認證、量產)

## 推論的量測需求

## 供應鏈成員(Ecosystem 或 Account 卡)
```dataview
TABLE role AS 角色, relationship_to_us AS 與我關係, node AS 節點
FROM "BI/Ecosystem" OR "BI/Account"
WHERE contains(default(this.ecosystem, []), file.link)
```

## 影響此產品的趨勢(經技術或節點推得)
```dataview
TABLE stage AS 階段, time_to_demand AS 需求時間, measurement_impact AS 量測影響
FROM "BI/Trend"
WHERE length(filter(default(this.technologies, []), (t) => contains(default(related_tech, []), t))) > 0
   OR length(filter(default(this.nodes, []), (n) => contains(default(affected_nodes, []), n))) > 0
   OR (this.node AND contains(default(affected_nodes, []), this.node))
SORT measurement_impact DESC
```

## 相關商機
```dataview
TABLE deal_stage AS 階段, our_solutions AS 我方方案, expected_close AS 預計成交
FROM "BI/Opportunity"
WHERE customer_product = this.file.link
SORT expected_close ASC
```
