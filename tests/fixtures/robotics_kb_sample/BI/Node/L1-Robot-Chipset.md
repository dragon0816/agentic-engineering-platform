---
type: node
name: L1-Robot-Chipset
domain: robotics
layer: L1
downstream: ["[[L2-Servo-Motor-Drive]]", "[[L2-Controller-IPC]]", "[[L2-Sensing-Module]]", "[[L2-Comms-Module]]", "[[L2-Battery-Power-Module]]"]
typical_test_needs: [邊緣AI SoC 電源完整性, 高速介面一致性(MIPI/SerDes/乙太網), Wi-Fi/BT/UWB 晶片射頻特性, 毫米波雷達晶片量測]
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
