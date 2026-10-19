---
type: concept
name: EVM
aliases: [Error Vector Magnitude, 誤差向量幅度]
category: metric
one_liner: "衡量發射訊號「畫得有多準」的分數,越低越好"
analogy: "像描摹文字,EVM 越低字越工整、對方越容易讀懂"
technologies: ["[[WiFi-7]]", "[[5G-NR-FR2]]"]
applications: ["[[WiFi7-MLO互通與吞吐量驗證]]"]
test_solutions: ["[[FR2-AiP-OTA緊縮場方案]]"]
related_concepts: ["[[4096-QAM]]", "[[EIRP]]"]
audience: sales
review_status: draft
confidence: assumed
updated: 2026-10-13
ingested_from: concepts_draft.json
---

## 30 秒版
EVM 是看一個發射器「訊號畫得有多準」的指標。調變階數越高(例如 Wi-Fi 7 的 4096-QAM),對 EVM 的要求越嚴格,所以量測儀器本身也要夠乾淨。

## 客戶會怎麼說
- 「EVM 過不了」→ 訊號品質不夠乾淨,常見原因是功率放大器非線性或雜訊
- 「高階調變下 EVM 壓不下來」→ 通常出現在 Wi-Fi 7 的 4096-QAM

## 我們量什麼、用什麼量
- 量:發射訊號的 EVM(單位為 dB 或 %)
- 用:向量訊號分析儀 / 向量訊號收發儀

## 常見誤解與不要說的話
- 不要承諾具體門檻數字,不同標準與調變階數的要求不同(待查證)
- EVM 好不代表傳得遠,它描述的是訊號品質,不是距離

## 深入版(選填)
(待工程師補充)EVM 會受 PA 線性度、相位雜訊、IQ 不平衡與量測儀器本身底噪影響。
