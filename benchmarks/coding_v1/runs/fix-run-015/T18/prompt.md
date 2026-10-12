export.py 原本應讀取 input.csv，依 Model 計算平均 Value 並輸出 summary.xlsx，現在執行會出錯。請找出並修復問題，保持既有 CLI 介面，空白 Value 不納入平均，輸出 Model、Average、ValidCount。請實際執行並驗證結果。

export.py 與 input.csv 在 input 下，依賴記錄在 input/DEPENDENCIES.txt。請把修復後的程式存成 output\export.py（CLI 介面不變），並在工作目錄執行 python output\export.py --input input\input.csv --output output\summary.xlsx 驗證。

---
工作目錄：C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\coding_v1\runs\fix-run-015\T18\workspace
題目中的相對路徑以工作目錄為準，輸入檔在 C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\coding_v1\runs\fix-run-015\T18\workspace\input。
請把所有輸出檔寫到 C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\coding_v1\runs\fix-run-015\T18\workspace\output。不要修改 input 下的任何檔案。
