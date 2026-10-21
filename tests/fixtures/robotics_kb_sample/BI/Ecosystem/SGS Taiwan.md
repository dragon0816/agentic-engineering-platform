---
type: ecosystem
name: SGS Taiwan
domain: [wireless, robotics]
node: "[[X-Certification-Lab]]"
nodes: ["[[X-Certification-Lab]]"]
role: cert-lab
relationship_to_us: partner
influence_on: ["[[台達電]]", "[[大銀微系統]]"]
reference_design: false
confidence: assumed
updated: 2026-10-21
ingested_from: ecosystem_robotics.csv
---

## 角色說明

[範例資料,待業務/FAE 驗證]

## 如何影響客戶的量測設備選型

## 使用此成員的客戶產品
```dataview
TABLE account AS 客戶, node AS 節點, launch_date AS 上市日
FROM "BI/CustomerProduct"
WHERE contains(default(ecosystem, []), this.file.link)
SORT launch_date ASC
```
