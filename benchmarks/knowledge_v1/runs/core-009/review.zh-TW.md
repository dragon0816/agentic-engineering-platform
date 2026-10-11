# knowledge_v1 core-009：目前 HEAD 與 Skill 1.10.0 的新基準

2026-10-12。程式 `0be2b14`，Knowledge Skill `company-agent/knowledge-query@1.10.0`，
rs-knowledge 1.0.2，36 題（與 core-005 相同的題組）。目的：模型可能已漂移，先重量一次基準，
後面的候選版本都跟這一次比。

## 結果

| | core-005（2026-10-10） | core-009（今天） |
|---|---|---|
| 可回答 22 題涵蓋率 | 0.395 | **0.372** |
| 可回答 22 題 PASS / 不足 / FAIL / 系統錯誤 | 17 / 1 / 4 / 0 | 15 / 2 / 4 / 1 |
| 證據不足 14 題涵蓋率 | 0.289 | 0.281 |
| 全部 36 題 PASS / 不足 / FAIL | 25 / 4 / 7 | 21 / 6 / 8（另 1 題 SYSTEM_ERROR） |
| contradicted / invented 合計 | 22 / 51 | 27 / 47 |
| 中位數 / p90 回應時間 | 156 / 233 s | 185 / 329 s |

說明：

- 同一設定下涵蓋率低了 0.02，在同題重評的浮動（約 0.06）之內；可視為模型大致沒漂移，
  但回應時間明顯變慢。量測期間我同時在跑離線的檢索重播（少量模型呼叫與 CPU），可能讓時間偏高一點。
- Q0871 是 `knowledge_model_failed`（模型端失敗），記為 SYSTEM_ERROR。

## 離線分析（core-005 與 core-009 的 trace）

1. **對話模型改寫了問題。** 36 題中有 26 題走 tool 路徑（對話模型呼叫 `knowledge__rs-knowledge`）。
   core-005 的 26 次呼叫只有 1 次原文照傳：常見的是在問題後面加上「Please cite Raw evidence」、
   「Focus on …」、指定產品（例如把 AI 資料中心題導向 CMX500 / CMP180）或「rank opportunities by strength」。
   原因是 tool 的說明來自舊的 `engineering/knowledge-query@1.0.0` Skill：「This capability can answer only
   with citations to Raw evidence」。合成模型照字面只引用證據最後 4 段 Raw 備援段落（多半無關），
   於是回答「沒有 Raw 段落支持」：Q0296、Q0546、Q0911、Q0051 都是這樣，涵蓋率接近 0，還被判 contradicted。
2. **檢索仍是主要缺口。** 可回答題的參考重點中，約 55–60% 所在的頁面根本沒進到合成的證據；
   有進到證據卻被漏掉的只有約 10%。
3. **時間花在詞彙檢索。** 每題都重建整個 corpus（約 20 秒），每個查詢又重算一次全庫的 BM25
   文件頻率（約 0.7 秒 × 約 30 次查詢）。這和答案品質無關，純粹是浪費。
4. **第一稿常因粗體小標沒有引用而被要求重寫。** 例如 Q0296 的重播：第一稿只因 4 行粗體列表標題
   沒有 `[n]` 就沒通過預檢，重寫多花 20–40 秒，有時重寫版更短。這屬於驗證規則，未修改，列為提案。

## 後續

- core-010：修正 tool 問題改寫 + 檢索加速（C1）。
- core-011：在 C1 上再放寬證據選擇（C2）。
