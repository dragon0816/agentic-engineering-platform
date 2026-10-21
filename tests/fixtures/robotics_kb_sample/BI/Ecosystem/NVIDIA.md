---
type: ecosystem
name: NVIDIA
domain: [robotics]
node: "[[L1-Robot-Chipset]]"
nodes: ["[[L1-Robot-Chipset]]"]
role: chipset
technologies: ["[[Edge-AI-SoC]]"]
relationship_to_us: influencer
influence_on: ["[[達明機器人]]", "[[上銀科技]]", "[[新漢]]"]
reference_design: true
ticker: NVDA
confidence: assumed
updated: 2026-10-21
ingested_from: ecosystem_robotics.csv
---

## 角色說明

機器人邊緣 AI 運算平台供應商;其平台選型影響客戶電源完整性與介面量測需求。[範例資料,待業務/FAE 驗證]

## 如何影響客戶的量測設備選型

## 使用此成員的客戶產品
```dataview
TABLE account AS 客戶, node AS 節點, launch_date AS 上市日
FROM "BI/CustomerProduct"
WHERE contains(default(ecosystem, []), this.file.link)
SORT launch_date ASC
```
