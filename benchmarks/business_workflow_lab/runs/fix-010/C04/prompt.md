請使用報價 CLI 查詢 2026 年 9 月的 Sent 報價並填模板。若 exit code 4，最多重試兩次；exit code 2 或 3 不要重試，請回報 stderr 的原因。stdout 只有成功且可解析時才當成資料。

---
環境說明（操作者提供）
- 今天日期：2026-10-06（Asia/Taipei）
- 本題 workspace：C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\runs\fix-010\C04\workspace
- 附件（在 workspace 的 input 資料夾）：
  - input\quote_template.xlsx
  - input\fx_rates.csv
  - input\quote_cli_manual.md
- 交付物請寫到 workspace 的 output 資料夾；需要可重跑的 workflow 時，請建立成本平台的 workflow。
