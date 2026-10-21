---
type: customer_product
product_name: 新漢 AMR 控制主機
domain: robotics
account: "[[新漢]]"
node: "[[L3-AMR-AGV]]"
nodes: ["[[L3-AMR-AGV]]", "[[L2-Controller-IPC]]", "[[L2-Sensing-Module]]"]
technologies: ["[[Wi-Fi-7]]", "[[5G-Private-Network]]", "[[mmWave-Radar]]", "[[UWB]]"]
chipset_modules: ["[[Qualcomm]]", "[[聯發科]]"]
ecosystem: ["[[Qualcomm]]", "[[聯發科]]", "[[鴻海]]"]
launch_window: 2027 H1
launch_date: 2027-04-30
volume_tier: mid
test_stage_now: RD
inferred_applications: ["[[機器人無線連線射頻與共存]]", "[[AMR 毫米波雷達與 UWB 定位量測]]"]
confidence: assumed
updated: 2026-10-21
ingested_from: customer_products_robotics.csv
---

## 產品概述

[範例資料,待業務/FAE 驗證]

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
