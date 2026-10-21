---
type: node
name: X-Certification-Lab
domain: wireless
layer: X
typical_test_needs: [EMC/射頻/安全法規認證, 機器人整機另需功能安全(ISO 10218 / ISO 13849)]
ingested_from: nodes_robotics.csv
---

## 說明

沿用 Wireless KB 既有 X 層節點(跨領域共用);[範例資料,待業務/FAE 驗證]

## 此層典型量測需求

## 此層生態系成員
```dataview
TABLE role AS 角色, relationship_to_us AS 與我關係
FROM "BI/Ecosystem"
WHERE node = this.file.link OR contains(default(nodes, []), this.file.link)
SORT role ASC
```

## 此層客戶產品
```dataview
TABLE account AS 客戶, launch_date AS 上市日, launch_window AS 上市時程
FROM "BI/CustomerProduct"
WHERE node = this.file.link OR contains(default(nodes, []), this.file.link)
SORT launch_date ASC
```

## 影響此層的趨勢
```dataview
TABLE stage AS 階段, time_to_demand AS 需求時間, measurement_impact AS 量測影響
FROM "BI/Trend"
WHERE contains(default(affected_nodes, []), this.file.link)
SORT measurement_impact DESC
```
