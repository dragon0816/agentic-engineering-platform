請自動辨識兩份 log：V1 為 [TIME][DEVICE][TEST][RESULT]；V2 為每行 JSON，欄位 ts、dut、case、result。將它們合併為 unified.json，欄位 timestamp、device_id、test_name、status、source_file、format_version，status 統一 Pass/Fail。未知格式的行另外記錄 warning。

---
工作目錄：C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\coding_v1\runs\fix-run-013\T16\workspace
題目中的相對路徑以工作目錄為準，輸入檔在 C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\coding_v1\runs\fix-run-013\T16\workspace\input。
請把所有輸出檔寫到 C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\coding_v1\runs\fix-run-013\T16\workspace\output。不要修改 input 下的任何檔案。
