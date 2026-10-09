# knowledge_v1 core-001：Harness + 公司 gpt-5.5 對照 Claude Code 參考答案

2026-10-09。36 題核心題（`questions/coverage.json` 的 core，涵蓋 93 個面向）。
AEP 為統一 Harness 之後、工具路徑保留引用段落的版本（a18421a 之後重啟的 Agent Web）。
參考答案：`benchmarks/knowledge_v1/references/`，Claude Code 只用唯讀工具在 Vault 內作答，
283 條重點的原文引用全部核對通過；其中 14 題參考答案判定 Vault 證據不足。

## 1. 原本的評分（run.py，grader 1.3）

**30 / 36 可接受**（PASS 20、INSUFFICIENT_KNOWLEDGE 10），FAIL 6，SYSTEM_ERROR 0。
Q1001、Q1021 第一次遇到公司 LLM 503（服務暫時不可用），重問後計入。

## 2. 對照參考答案（reference_grade.py，grader 1.2，評審為公司 gpt-5.5）

涵蓋率 =（涵蓋 + 部分 × 0.5）÷ 參考重點數。

| 參考答案判定 | 題數 | 平均涵蓋率 | 有矛盾的題 | 有「捏造」標記的題 |
|---|---|---|---|---|
| Vault 足以回答 | 22 | 0.27 | 2 | 4 |
| Vault 不足以回答 | 14 | 0.14 | 4 | 5 |

各題結果：`reference-report.md`；每題逐條標記：`Q*/reference-grade.json`。

## 3. 發現

1. **檢索漏抓（最重要）。** 參考答案判定 Vault 足以回答的 22 題中，AEP 有 7 題說證據不足：
   Q0846、Q0871、Q1001、Q1021、Q1061、Q1071 回 INSUFFICIENT_KNOWLEDGE，
   Q0296 判 PASS 但內容是「沒有證據」（與參考答案 4 條矛盾）。原本的評分把這些都算「可接受」，
   只有對照參考答案才看得出來。
2. **基礎題（定義類）在工具路徑全部未通過驗證。** 6 題基礎題（Q1001–Q1091）都走工具路徑、
   都被 Harness 拒絕；拒絕訊息是「requested product/option/spec evidence was missing」。
   定義題不需要產品/選件/規格面向，看起來是面向評估把定義題當成產品題處理。這是 Harness 行為，
   修改前需 owner 決定。已逐題核對：6 題都是 `phase=needs_input`、`missing_facets` 含
   `product_option_spec`、Raw 引用 0 條。
   **更正（同日調查後）：** `retrieval_attempts` 是空的，只是因為查詢失敗時沒有 record 可讀，不代表重試沒跑；
   telemetry 顯示重試有排程。真正原因是檢索：例如問 EVM 時，`wiki/concepts/EVM.md` 只排在第 20 名，前面被
   題目句型字詞和與題目無關的面向檢索詞占滿。以參考答案引用的檔案量測，檢索召回率只有 0.12。
   修正見 DECISIONS 2026-10-09「Bilingual retrieval」與 `runs/core-002`。
3. **開放題涵蓋率天生偏低。** solution_mapping、strategic 類題目（例如 Q0121「市場需求 → 參數 → 儀器能力」）
   有多條正確路徑；參考答案走 5G FWA，AEP 走 Wi-Fi 7，兩者都有根據。這類題的涵蓋率只能當參考。
4. **答得好的題確實高分。** 例如 Q0011（Wi-Fi 7/8 信令與非信令）0.81。
5. **「捏造」標記要人工判讀。** Q0401 的標記內容多數在 AEP 已核對的引用段落裡（參考答案沒寫到，不是捏造）；
   Q0801 則是把一般 SAR 信令能力套到「半導體」應用，屬延伸過頭。

## 4. 評審方法的限制

- 參考答案是「一個好答案」，不是唯一正解；開放題尤其如此。
- 同一題重評，涵蓋率會差約一條「部分」（Q0011：0.625 / 0.688）。
- 評審規則調整過兩次（1.1：附上參考答案全文；1.2：明確標示「非知識庫」的補充不算捏造），都是修正誤判，
  沒有放寬對 AEP 答案本身的要求。

## 5. 建議下一步

1. 查第 2 點：基礎題為什麼要求產品/選件/規格面向（需 owner 同意才改 Harness）。
2. 查第 1 點：7 題檢索漏抓，比對參考答案引用的檔案和 AEP 實際檢索到的段落，分辨是檢索還是驗證的問題。
3. 修完後只重跑這 36 題核心題 + reference_grade，參考答案不用重產生（不再花 Claude Code 額度）。
