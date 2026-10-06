從提供的列表收集五個產品資料，輸出 robust_products.xlsx，欄位為 Name、Price、Currency、CPU、URL、FetchStatus。缺價格或規格填 N/A；detail page HTTP 500 最多嘗試 3 次，仍失敗時保留列表名稱與 URL，其他未知欄位填 N/A，FetchStatus 設為 error。另輸出 warnings.json，成功頁設為 ok。

產品列表 URL：http://127.0.0.1:49758/t13/list

---
工作目錄：C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\coding_v1\runs\fix-run-005\T13\workspace
題目中的相對路徑以工作目錄為準，輸入檔在 C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\coding_v1\runs\fix-run-005\T13\workspace\input。
請把所有輸出檔寫到 C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\coding_v1\runs\fix-run-005\T13\workspace\output。不要修改 input 下的任何檔案。
