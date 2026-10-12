# core-015 檢討：知識庫自己的回答規則（重寫的 ask-knowledge）

日期：2026-10-12。程式 b25e1f1d：vault 中 `mode: answer` 的 skill 會加進答案合成的提示詞，
排在已安裝 Knowledge Skill 的回答規則之後。

候選 Knowledge：`rs-knowledge@1.0.3-askrules.1`，內容是 rs-k 1.0.2 加上
`skills/ask-knowledge/SKILL.md`（內容來自 `src/knowledge/skill_guide/answer.SKILL.md`）。
只在量測期間綁定，結束後已還原。對照組：core-012（同程式、沒有 vault 回答規則），用評分 1.4。

| | core-012 | core-015 |
|---|---|---|
| 可回答 22 題涵蓋率 | 0.477 | **0.503** |
| contradicted / invented | 15 / 67 | **9 / 31** |
| PASS / FAIL（評分 1.4） | 33 / 1 | 32 / 2 |
| 中位數 / p90 | 74 / 114 s | 71 / 114 s |

- 涵蓋率提高、延伸發揮減少一半以上、矛盾減少，速度沒有變慢。依驗收規則保留。
- 主要差別來自回答規則：
  - 分清技術／產品／市場層。
  - 沒有排名就不要下結論，改列各選項的條件。
  - 型號只用證據裡的寫法，證據不足時說明缺什麼。
- 單次量測。延伸發揮的下降幅度遠大於量測雜訊。
- 正式 Agent 目前（rs-knowledge 1.0.2）沒有 `skills/` 資料夾，所以使用者還沒受惠。要發佈成
  新的 Knowledge 版本，或從專案 vault Refresh 後才會生效。
