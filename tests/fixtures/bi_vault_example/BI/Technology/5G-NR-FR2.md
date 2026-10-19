---
type: technology
name: 5G-NR-FR2
standard_body: 3GPP
spec_milestones: ["3GPP 相關 Release 時程(待查證)", "電信商認證啟動時程(待查證)"]
maturity: growth
affects_nodes: ["[[L2-Antenna-Module]]", "[[L3-Handset]]", "[[L4-Base-Station]]"]
new_test_requirements: ["毫米波 OTA 緊縮場量測", "波束成型驗證", "高頻 EVM"]
confidence: assumed
updated: 2026-10-13
---

## 標準時程與重點
(範例)請以 3GPP 與電信商公開文件查證後填入。

## 新增或加嚴的量測需求
毫米波頻段難以做傳導量測,OTA 成為主要方法,暗室與緊縮場投資高。

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
