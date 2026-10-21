---
type: node
name: L4-System-Integrator
domain: robotics
layer: L4
upstream: ["[[L3-Cobot-Arm]]", "[[L3-AMR-AGV]]", "[[L3-Humanoid-Quadruped]]"]
downstream: ["[[L5-Factory-Deployment]]"]
typical_test_needs: [產線整合驗證, 工業網路確定性與延遲, 現場無線覆蓋與干擾, EMC 現場問題排查]
ingested_from: nodes_robotics.csv
---

## 說明

初稿:上下游與典型量測需求為假設,待業務/FAE 驗證

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
