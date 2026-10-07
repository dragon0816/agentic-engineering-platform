從三個提供的 catalog URL 合併產品資料，欄位為 Model、Price、Currency、MemoryGB、SourceURL。同型號在不同來源仍分別保留。Price 移除貨幣符號與千分位後轉為數值；保留各自幣別，不換匯。記憶體以 1024 MB = 1 GB 換算。

catalog URL：http://127.0.0.1:64212/t12/a、http://127.0.0.1:64212/t12/b、http://127.0.0.1:64212/t12/c

---
工作目錄：C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\coding_v1\runs\fix-run-012\T12\workspace
題目中的相對路徑以工作目錄為準，輸入檔在 C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\coding_v1\runs\fix-run-012\T12\workspace\input。
請把所有輸出檔寫到 C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\coding_v1\runs\fix-run-012\T12\workspace\output。不要修改 input 下的任何檔案。
