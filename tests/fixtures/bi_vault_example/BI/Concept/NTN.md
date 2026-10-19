---
type: concept
name: NTN
aliases: [Non-Terrestrial Network, 非地面網路, 衛星直連]
category: radio
one_liner: "用衛星提供手機直接連線的網路,山區與海上也有訊號"
analogy: 像把基地台掛到天上
technologies: ["[[NTN-Satellite]]"]
applications: ["[[衛星直連-通道模擬驗證]]"]
test_solutions: ["[[NTN衛星通道模擬方案]]"]
related_concepts: ["[[通道模擬]]"]
audience: sales
review_status: draft
confidence: assumed
updated: 2026-10-13
ingested_from: concepts_draft.json
---

## 30 秒版
NTN 讓手機不靠地面基地台,直接連到天上的衛星。對量測的影響是:延遲大、都卜勒大、連線容易中斷,需要新的測試方法。

## 客戶會怎麼說
- 「手機要支援衛星直連」→ 需要衛星通道模擬與認證測試
- 「NTN 認證還在討論」→ 規範與認證仍在演進(待查證)

## 我們量什麼、用什麼量
- 量:衛星通道下的連線、鏈路中斷復原、GNSS 協同
- 用:通道模擬器 + 網路模擬器

## 常見誤解與不要說的話
- NTN 不是只有衛星,也包括高空平台等非地面基地台
- 不要說「衛星直連會取代地面網路」,它是補足覆蓋

## 深入版(選填)
(待工程師補充)3GPP NTN 的 Release 時程與測試規範待查證。
