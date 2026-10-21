---
type: trend
name: AMR 滲透工廠與倉儲
domain: robotics
related_tech: ["[[Wi-Fi-7]]", "[[5G-Private-Network]]", "[[mmWave-Radar]]", "[[UWB]]", "[[BMS-Fast-Charging]]"]
affected_nodes: ["[[L3-AMR-AGV]]", "[[L2-Battery-Power-Module]]", "[[L5-Factory-Deployment]]"]
related_applications: ["[[機器人無線連線射頻與共存]]", "[[AMR 毫米波雷達與 UWB 定位量測]]", "[[AMR 電池包 BMS 與充電驗證]]", "[[工廠現場無線覆蓋與干擾排查]]"]
stage: accelerating
time_to_demand: 0-6m
market_impact: 4
measurement_impact: 4
our_fit: 4
confidence: assumed
updated: 2026-10-21
ingested_from: trend_robotics.csv
---

## 趨勢描述

無線與電池雙線都有量測機會。[範例資料,待業務/FAE 驗證]

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
