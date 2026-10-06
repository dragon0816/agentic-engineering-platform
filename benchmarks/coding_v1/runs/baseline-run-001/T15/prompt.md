解析 test.log 的每個非空行，格式為 [TIME][DEVICE][TEST][RESULT]，結果是 PASS 或 FAIL。輸出 parsed.json，欄位 timestamp、device_id、test_name、status；status 使用 Pass/Fail。無法解析的行輸出 warnings.json，包含原始行號、原文及原因，不能讓整個程式中止。

---
工作目錄：C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\coding_v1\runs\baseline-run-001\T15\workspace
題目中的相對路徑以工作目錄為準，輸入檔在 C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\coding_v1\runs\baseline-run-001\T15\workspace\input。
請把所有輸出檔寫到 C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\coding_v1\runs\baseline-run-001\T15\workspace\output。不要修改 input 下的任何檔案。
