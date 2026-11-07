# BI 查詢跨類型與備註片段：真實模型檢查

2026-11-07，`bi-query-other-types`，修改前基準 `b1dd4cf8`。使用先前 SOP 的全虛構
`vault-fictional-marine` 工作區副本，與真實 gateway 模型 `gpt-5.5`，透過
`bi_bench.ask_on` → Agent harness → `bi__query`，每回合獨立、無先前對話。
未啟動 owner Agent Web，未讀真實 vault，未把金鑰放入輸入、輸出或本文。

固定題目：「BW-200 的校準週期是多少？」答案只在
`CustomerProduct:BW-200 射頻感測模組` 的 body：「BW-200 的校準週期為 6 個月」。
使用相同副本、相同題目、相同模型與既有主機分類核准。這是工作副本的 benchmark
讀取路徑；發佈版本隔離另由自動化測試驗證。

直接查詢重現：`text=BW-200` 時，SupplyLink 有 2 張，CustomerProduct 有 3 張，
不設類型有 10 張。修改前，三種查法的結果都沒有「6 個月」，雖然儲存的 body 有該值。
修改後，後兩種結果有最多 300 字元、含來源的命中片段；SupplyLink 的結果仍不包含
其他類型的卡片列，只提供可重查的計數提示。

Gateway 探測分別 2.0 秒、2.4 秒，皆成功，未掛住。每個階段只計下面 5 回合，
沒有丟棄失敗回合或重試挑選結果。命中定義為實際回覆給出 6 個月；逐回合讀取確認
修改後五個答案都肯定陳述該週期、引用 CustomerProduct 卡片，並保留待驗證／虛構提醒。

| 回合 | 修改前命中 | 工具呼叫數 | 修改後命中 | 工具呼叫數 |
|---|---|---:|---|---:|
| 1 | 否 | 2 | 是 | 1 |
| 2 | 否 | 1 | 是 | 1 |
| 3 | 否 | 1 | 是 | 1 |
| 4 | 否 | 1 | 是 | 1 |
| 5 | 否 | 1 | 是 | 1 |
| 合計 | 0／5 | 6（平均 1.2） | 5／5 | 5（平均 1.0） |

本次自然模型的修改前五回合已經不限制類型：第一回合先查 `BW-200`，再查
`BW-200 校準 週期 calibration`；其餘只查 `BW-200`。修改後五回合都以
`BW-200 校準週期` 查所有類型。因此這個小樣本證明 body 可見性的重要性，不能把
提升全歸因於跨類型提示，也不能視為一般準確率估計。

跨類型提示的行為由獨立 stub 回歸測試驗證：先限制 SupplyLink，實際收到其他類型
計數後去除限制，讀到 CustomerProduct 的 body_snippet，才回覆並引用該卡片。
沒有從計數猜答案，也沒有放寬原本的必須命中詞。未裁切的長篇 body、未核准來源和未發佈版本
仍不會藉此進入一般查詢結果。

## 驗證與既有 UI 失敗對照

查詢修改為 `e9105373`。指定與相關測試共 116 passed；Ruff format/check、mypy 通過，
feed goldens 未變。額外全套 pytest 為 5994 passed、9 skipped、2 failed（6761 秒），
不能報為全綠。兩個失敗是 review 提案確認與 sessions 新版次等待；sessions 整檔
單獨重跑 1 passed。review 失敗案例單獨 1 passed，但整檔先前兩次均 10 passed／1 failed；
未修改基準先前一次整檔 11 passed。

依 orchestrator 要求，提交後以相同暫存 DevTools 診斷外掛交替跑整檔，各 3 次，
一次一檔、各自 basetemp。外掛只旁錄原本 Runtime.evaluate 回傳的 exceptionDetails，
不重送點擊、不改回傳、不改產品程式或測試斷言，且遮蔽敏感值。

| 順序 | 版本 | 結果 | 秒 |
|---|---|---|---:|
| 1 | 本分支 | 11 passed | 281.18 |
| 2 | b1dd4cf8 | 11 passed | 279.81 |
| 3 | 本分支 | 11 passed | 321.04 |
| 4 | b1dd4cf8 | 11 passed | 397.85 |
| 5 | 本分支 | 11 passed | 586.50 |
| 6 | b1dd4cf8 | 10 passed、1 failed | 500.60 |

新增對照失敗計數：本分支 0／3、基準 1／3；加計先前的獨立整檔執行則為本分支
2／5、基準 1／4，全套的失敗另列。基準失敗精確同一案例、同一行 703，JS 訊息為：

```text
TypeError: Cannot read properties of undefined (reading 'click')
    at <anonymous>:1:180
```

運算式找到 FAKE-040 提案列後，找含「確定取代」的按鈕再呼叫 click；失敗當下按鈕為
undefined。這證明問題已存在於未修改基準，尚不能判定兩版本失敗率相等，也未證明
是哪個重繪／競態機制使按鈕消失。已在 TASKS 留獨立追蹤項目，本次沒有改 UI 或放寬斷言。
