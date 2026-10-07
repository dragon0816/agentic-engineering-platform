請遞迴處理 testplan.json 的物件與陣列，只把名為 frequency 且值為 GHz/MHz 單位字串的欄位轉成 MHz 數值，並在同一物件加入 frequency_unit: MHz。例如 2.4GHz 變成 2400。frequency 已是數值時保留原狀，未知單位的字串保留並記 warning。其他欄位、數值、陣列順序全部不可改動。

---
工作目錄：C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\coding_v1\runs\fix-run-009\T17\workspace
題目中的相對路徑以工作目錄為準，輸入檔在 C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\coding_v1\runs\fix-run-009\T17\workspace\input。
請把所有輸出檔寫到 C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\coding_v1\runs\fix-run-009\T17\workspace\output。不要修改 input 下的任何檔案。
