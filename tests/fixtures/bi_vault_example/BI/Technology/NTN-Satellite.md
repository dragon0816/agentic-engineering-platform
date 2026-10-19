---
type: technology
name: NTN-Satellite
standard_body: 3GPP
spec_milestones: ["NTN 相關 Release 時程(待查證)"]
maturity: emerging
affects_nodes: ["[[L1-Chipset]]", "[[L3-Handset]]", "[[L5-Carrier-Network]]"]
new_test_requirements: ["衛星通道模擬(延遲、都卜勒)", "低軌衛星鏈路 OTA", "GNSS 協同測試"]
confidence: assumed
updated: 2026-10-13
---

## 標準時程與重點
(範例)請查證。

## 新增或加嚴的量測需求
通道模擬與長延遲、大都卜勒位移為關鍵新增測項。

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
