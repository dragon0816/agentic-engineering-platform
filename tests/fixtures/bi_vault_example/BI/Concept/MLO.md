---
type: concept
name: MLO
aliases: [Multi-Link Operation, 多連結運作]
category: protocol
one_liner: "Wi-Fi 7 的功能,讓一台裝置同時用多個頻段連線"
analogy: "像高速公路同時開多條車道,車流更順暢、塞車時有備援"
technologies: ["[[WiFi-7]]"]
applications: ["[[WiFi7-MLO互通與吞吐量驗證]]"]
test_solutions: ["[[WiFi7-MLO互通與吞吐量方案]]"]
related_concepts: ["[[吞吐量]]", "[[共存]]", "[[4096-QAM]]"]
audience: sales
review_status: draft
confidence: assumed
updated: 2026-10-13
ingested_from: concepts_draft.json
---

## 30 秒版
MLO 讓一台裝置同時使用 2.4、5、6GHz 多條連線。好處是更快、更穩、延遲更低,但也讓互通測試變複雜,這就是新的量測需求。

## 客戶會怎麼說
- 「MLO 在不同廠牌的路由器與手機之間不穩」→ 互通性問題
- 「開 MLO 之後延遲有改善嗎?」→ 需要實測

## 我們量什麼、用什麼量
- 量:連結切換、互通性、吞吐量與延遲、多裝置壓力
- 用:無線連線測試儀 + 屏蔽箱 + 自動化軟體

## 常見誤解與不要說的話
- MLO 不是把兩個頻段的速度簡單相加
- 需要路由器與用戶端兩端都支援才能生效

## 深入版(選填)
(待工程師補充)MLO 有多種運作模式,各模式對延遲與吞吐量的好處不同,待查證標準細節。
