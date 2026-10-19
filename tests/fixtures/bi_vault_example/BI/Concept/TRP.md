---
type: concept
name: TRP
aliases: [Total Radiated Power, TIS, Total Isotropic Sensitivity, 總輻射功率]
category: metric
one_liner: "把各方向的發射功率加總,看裝置「整體」送出多少"
analogy: "像燈泡朝四面八方一共送出多少光,而不只看最亮的那一個方向"
technologies: ["[[5G-NR-FR2]]"]
applications: ["[[5G-FR2-AiP-OTA驗證]]"]
test_solutions: ["[[FR2-AiP-OTA緊縮場方案]]"]
related_concepts: ["[[EIRP]]", "[[OTA]]"]
audience: sales
review_status: draft
confidence: assumed
updated: 2026-10-13
ingested_from: concepts_draft.json
---

## 30 秒版
TRP 看發射的「總量」,TIS 看接收的「靈敏度總量」。電信商認證常用這兩個指標評估整台手機的天線效能。

## 客戶會怎麼說
- 「電信商要 TRP/TIS 報告」→ 電信商認證常要求整機輻射表現

## 我們量什麼、用什麼量
- 量:TRP(發射)與 TIS(接收靈敏度的空間總和)
- 用:OTA 暗室 + 轉台或多探頭系統

## 常見誤解與不要說的話
- TRP 與 EIRP 是兩個不同角度:EIRP 看最強方向,TRP 看整體
- TIS 是接收端的對應指標,常和 TRP 成對出現

## 深入版(選填)
(待工程師補充)TRP 需要在球面上取樣多點,取樣密度與量測時間是設備選型的重點。
