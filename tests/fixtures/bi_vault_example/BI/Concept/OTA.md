---
type: concept
name: OTA
aliases: [Over-the-Air, 空中量測]
category: measurement
one_liner: "不接線,在空中直接量裝置真實的發射與接收表現"
analogy: "像在音場裡聽歌手唱歌,而不是把麥克風線接進他的喉嚨"
technologies: ["[[5G-NR-FR2]]"]
applications: ["[[5G-FR2-AiP-OTA驗證]]"]
test_solutions: ["[[FR2-AiP-OTA緊縮場方案]]"]
related_concepts: ["[[EIRP]]", "[[TRP]]", "[[緊縮場 CATR]]", "[[波束成型]]"]
audience: sales
review_status: draft
confidence: assumed
updated: 2026-10-13
ingested_from: concepts_draft.json
---

## 30 秒版
OTA 就是「不接線,在暗室裡把整台裝置連同天線一起量」。毫米波的天線通常整合在晶片模組裡,沒有地方接線,所以一定得用空中量測。

## 客戶會怎麼說
- 「我們的天線模組沒有 RF 接頭,沒辦法接線量」→ 只能做 OTA
- 「傳導量測合格,為什麼天線整合後掉很多?」→ 天線與外殼的影響要靠 OTA 才看得到

## 我們量什麼、用什麼量
- 量:EIRP、TRP/TIS、場型、波束掃描
- 用:暗室(毫米波常用緊縮場)+ 向量訊號收發儀 + 波束控制軟體
- 對應方案見相關方案欄位

## 常見誤解與不要說的話
- OTA 不是現場路測,是在受控暗室內的實驗室量測
- 有 OTA 不代表不需要傳導量測,兩者互補
- 不要說「OTA 比較準」,要說「OTA 才量得到整機含天線的真實表現」

## 深入版(選填)
(待工程師補充)OTA 暗室的靜區大小、量測不確定度與量測時間是方案報價與比較的關鍵。
