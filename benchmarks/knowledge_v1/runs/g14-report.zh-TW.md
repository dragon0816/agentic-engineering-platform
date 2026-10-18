# G1–G4 修改後的 U7 重跑報告

日期：2026-10-18。AEP commit `b1264d83`（G1–G4，Agent Web 已重啟），grader 1.4。
跑法與 U7 完全相同（`u7-report.zh-TW.md`）：36 題涵蓋率核心層，`--route chat` × 2、
`--route direct` × 2。四次共 21:29–23:18。

## 結果（可接受 ＝ PASS ＋ INSUFFICIENT_KNOWLEDGE）

| 範圍 | U7 chat-1 / chat-2 | **G1–G4 chat-1 / chat-2** | U7 direct-1 / direct-2 | G1–G4 direct-1 / direct-2 |
|---|---|---|---|---|
| 全部 36 題 | 30 / 30 | **36 / 34** | 34 / 33 | 34 / 36 |
| 路由走工具路徑的 26 題 | 21 / 22 | **26 / 25** | 25 / 24 | 24 / 26 |

- **Tool-path parity：** 同樣 26 題，工具路徑 51/52（98.1%），直接路徑 50/52（96.2%）。
  差距由 U7 的 −11.5 pp 變為 **+1.9 pp（工具路徑略高），達到 ≤ 5 pp 門檻。**
- **Q1041 / Q1061 / Q1091**（U7 在工具路徑穩定失敗）：四次全部通過。
- 延遲中位數：chat 83 s / 75 s（U7 80 / 75），direct 58 s / 65 s（U7 65 / 68）；沒有變慢。

## 仍未通過的（G1–G4 四次中）

| 題號 | chat 路由 | chat-1 | chat-2 | direct-1 | direct-2 | 判斷 |
|---|---|---|---|---|---|---|
| Q1021 | tool | ok | REASONING | REASONING | ok | 兩條路徑都隨機出現，合成 / reviewer 雜訊（U7 也一樣） |
| Q0671 | direct | ok | REASONING | ok | ok | 同上 |
| Q0646 | tool | ok | ok | `knowledge_model_failed` | ok | 直接路徑一次模型呼叫失敗；直接路徑程式未被 G1–G4 改動，屬暫時性錯誤 |

## G2 紀錄

兩次 chat 共 52 次 Knowledge 工具呼叫，`anchor.outcome` 全部是 `same`：英文題目時，對話模型
原句照傳，**意圖偏移率 0%**。中文題目的情況需要另外量（`--set zh`，見語言無關的 G2 修正）。

## 結論

G1（部分有依據的答案不再交模型改寫）消除了 U7 的工具路徑差距；剩下的失分是兩條路徑共有的
隨機推理雜訊與一次暫時性模型錯誤，不是路徑問題。

## 補充：中文題（語言無關的 G2 修正之後，2026-10-19）

AEP commit `369c139d`（Agent Web 已重啟），`--set zh`（8 題繁體中文，見 `questions/zh-core.json`）。

| Run | 結果 | 路由 |
|---|---|---|
| `zh-chat-1` | **8/8 PASS** | 直接 5、工具 3 |
| `zh-direct-1` | **8/8 PASS** | 直接 8 |

- 3 次工具呼叫的 `anchor.outcome` 都是 `same`：模型把中文原句照傳，並填了逐字複製的
  `original_terms`（全部核對通過，`discarded_terms` 為空）。**意圖偏移率 0%。**
- 模型這次沒有填 `term_translations`（`translations_used` 為空），所以雙語擴充檢索仍只來自
  Harness 內的 `query_rewrite`；中文題照樣全數通過。
