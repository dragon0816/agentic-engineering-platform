# U7 量測報告（G1–G4 修改前的基準）

日期：2026-10-18。owner 決定先跑 U7、再改 G1–G4，題集用 36 題涵蓋率核心層
（`questions/coverage.json`），不用 110 題 sample。AEP commit `3a97c8a0`，grader 1.4。

## 跑法

| Run | 路徑 | 說明 |
|---|---|---|
| `u7-chat-1`、`u7-chat-2` | `--route chat` | 使用者實際會走的路：Agent Web 自己路由（Skill intent 命中 → 直接路徑，否則 → 對話工具路徑） |
| `u7-direct-1`、`u7-direct-2` | `--route direct` | 同一題、同一個 Knowledge Harness，經 `/api/knowledge/ask`（與對話直接路徑相同） |

每個路徑跑 2 次，取兩次看雜訊。四次共約 1 小時 48 分（16:58–18:47）。

## 結果

「可接受」＝ PASS ＋ INSUFFICIENT_KNOWLEDGE。

| 範圍 | chat-1 | chat-2 | direct-1 | direct-2 | core-015（10/12 對照） |
|---|---|---|---|---|---|
| 全部 36 題 | 30 | 30 | 34 | 33 | 34 |
| 路由走工具路徑的 26 題 | 21 | 22 | 25 | 24 | 24 |
| 路由走直接路徑的 10 題 | 9 | 8 | 9 | 9 | 10 |

- **Tool-path parity（v1.2 門檻 ≤ 5 pp）：** 在同樣 26 題上，工具路徑平均 21.5/26（82.7%），
  直接路徑平均 24.5/26（94.2%），**差 11.5 pp，未達門檻**。
- 延遲中位數：chat 80 s / 75 s，direct 65 s / 68 s；p90 chat 131 s / 105 s，direct 99 s / 112 s。

## 逐題（只列至少一次未通過的題目）

| 題號 | chat 路由 | chat-1 | chat-2 | direct-1 | direct-2 | core-015 |
|---|---|---|---|---|---|---|
| Q1041 | tool | VALIDATION | VALIDATION | ok | ok | VALIDATION |
| Q1061 | tool | VALIDATION | VALIDATION | VALIDATION | ok | ok |
| Q1091 | tool | VALIDATION | VALIDATION | ok | ok | REASONING |
| Q0351 | tool | REASONING | REASONING | ok | REASONING | ok |
| Q1021 | tool | REASONING | ok | ok | REASONING | ok |
| Q0489 | direct | ok | REASONING | ok | ok | ok |
| Q0571 | direct | ok | REASONING | ok | REASONING | ok |
| Q0671 | direct | REASONING | ok | REASONING | ok | ok |

## 發現

1. **工具路徑穩定失分的是 Q1041、Q1061、Q1091（兩次 chat 都 `knowledge_not_validated`），
   同題直接路徑大多通過。** 三題的 Harness 紀錄都是 `claim_status: supported`、有 Raw 引用
   （4–12 筆），只是 facet 或關係不完整（`facet_status: missing`）。直接路徑把這種「部分有依據」
   的答案原樣顯示（評分算可接受），工具路徑則標成未驗證、交回模型 —— **正是 G1 要修的情況。**
   這 3 題 × 2 次＝ 6 次失分，幾乎就是兩條路徑的全部差距。
2. **REASONING_GAP 在兩條路徑上都會隨機出現**（Q0351、Q1021、Q0489、Q0571、Q0671），同題兩次結果
   不一致，屬於模型合成與 reviewer 的雜訊，不是路徑問題。這也是每個路徑要跑 2 次的原因。
3. **G2 目前量不到：** trace 沒有記錄對話模型傳給 `knowledge__<vault>` 的 question 參數
   （工具紀錄的 arguments 為空），無法比對原句與改寫。G2 實作時要先把「原句 / 改寫」寫進紀錄，
   才能算「意圖偏移率」。
4. 與 10/12 的 core-015 相比，chat 從 34 降到 30；差異集中在上述三題與隨機的 REASONING_GAP，
   沒有新的失敗類型。

## 之後怎麼比較

G1–G4 修改後，用完全相同的命令再跑一次（chat × 2、direct × 2，同一個 36 題、同一個 grader），
與本報告逐題比較。預期 G1 會讓 Q1041 / Q1061 / Q1091 在工具路徑上與直接路徑一致。

```text
python benchmarks/knowledge_v1/run.py --run-id <id> --set core --route chat
python benchmarks/knowledge_v1/run.py --run-id <id> --set core --route direct
```
