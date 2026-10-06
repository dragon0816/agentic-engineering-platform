將三份報告 CSV、JSON、Markdown 轉為 reports.json，統一欄位 device_id、test_name、status、value、unit。status 將 OK/PASS 轉為 Pass、NG/FAIL 轉為 Fail；未出現 value 或 unit 時使用 null。每筆結果均須保留，ID 視為文字。

---
工作目錄：C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\coding_v1\runs\fix-run-001\T08\workspace
題目中的相對路徑以工作目錄為準，輸入檔在 C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\coding_v1\runs\fix-run-001\T08\workspace\input。
請把所有輸出檔寫到 C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\coding_v1\runs\fix-run-001\T08\workspace\output。不要修改 input 下的任何檔案。
