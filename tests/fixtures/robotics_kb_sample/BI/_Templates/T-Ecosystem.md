---
type: ecosystem
name: <% tp.file.title %>
domain: []  # wireless | AIDC | robotics
node:
nodes: []
role:   # chipset | module | ODM | OEM | carrier | cert-lab | integrator | distributor | standards | component | osat | foundry | test-equipment | institute | ipc
technologies: []
relationship_to_us:   # customer | partner | influencer | competitor | none
influence_on: []
reference_design: false
ticker:
confidence: assumed  # verified | assumed
updated: <% tp.date.now("YYYY-MM-DD") %>
---

## 角色說明

## 如何影響客戶的量測設備選型

## 使用此成員的客戶產品
```dataview
TABLE account AS 客戶, node AS 節點, launch_date AS 上市日
FROM "BI/CustomerProduct"
WHERE contains(default(ecosystem, []), this.file.link)
SORT launch_date ASC
```
