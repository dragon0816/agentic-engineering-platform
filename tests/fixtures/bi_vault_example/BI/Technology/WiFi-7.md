---
type: technology
name: WiFi-7
standard_body: IEEE 802.11be / Wi-Fi Alliance
spec_milestones: ["IEEE 標準核准與出版時程(待查證)", "Wi-Fi Alliance 認證啟動(待查證)"]
maturity: growth
affects_nodes: ["[[L1-Chipset]]", "[[L2-RF-FEM-Module]]", "[[L3-WiFi-Router-CPE]]", "[[L3-Handset]]"]
new_test_requirements: ["320MHz 頻寬 EVM", "4096-QAM 線性度", "MLO 互通與吞吐量", "6GHz 共存"]
confidence: assumed
updated: 2026-10-13
---

## 標準時程與重點
(範例)請查證實際時程。

## 新增或加嚴的量測需求
更寬頻寬與高階調變使 EVM 與線性度要求提高;多連結運作(MLO)增加互通測試複雜度。

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
