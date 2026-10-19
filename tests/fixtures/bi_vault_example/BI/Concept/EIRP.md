---
type: concept
name: EIRP
aliases: [Effective Isotropic Radiated Power, 等效全向輻射功率]
category: metric
one_liner: 天線朝最強方向「實際對外發出的等效功率」
analogy: "像手電筒加聚光罩,看的是光束正中央的亮度,不是燈泡本身的瓦數"
technologies: ["[[5G-NR-FR2]]"]
applications: ["[[5G-FR2-AiP-OTA驗證]]"]
test_solutions: ["[[FR2-AiP-OTA緊縮場方案]]"]
related_concepts: ["[[OTA]]", "[[TRP]]", "[[波束成型]]"]
audience: sales
review_status: draft
confidence: assumed
updated: 2026-10-13
ingested_from: concepts_draft.json
---

## 30 秒版
EIRP 描述的是「朝最強方向送出去多少功率」。毫米波靠天線陣列把能量集中,所以 EIRP 是 5G 毫米波裝置規格與法規裡最常被問的數字之一。

## 客戶會怎麼說
- 「EIRP 要符合法規上限」→ 認證時會被限制
- 「PA 輸出夠大,為什麼 EIRP 沒到?」→ 天線增益與損耗也要算進去

## 我們量什麼、用什麼量
- 量:EIRP(通常在波束最強方向,並隨波束掃描量測)
- 用:OTA 暗室 + 向量訊號收發儀

## 常見誤解與不要說的話
- EIRP 不等於 PA 輸出功率
- EIRP 只看最強方向,整體能力要看 TRP

## 深入版(選填)
(待工程師補充)簡化關係:EIRP ≈ 傳導功率 + 天線增益 − 線路損耗。
