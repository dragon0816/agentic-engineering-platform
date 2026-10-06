請從 SAP 網頁取得 2026 年 9 月的非 Cancelled 訂單與發票，從 Expense 桌面程式取得同月 Approved 支出，從報價 CLI 取得同月 Accepted 報價。按 ProjectID 整合填 project_template.xlsx，使用附件匯率，分開彙總訂單金額、發票未收金額、核准支出及已接受報價。不要將訂單與報價相加當營收，也不要用客戶名稱當 join key。請交付可重跑的 workflow。

---
環境說明（操作者提供）
- 今天日期：2026-10-06（Asia/Taipei）
- 本題 workspace：C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\runs\fix-002\X01\workspace
- 附件（在 workspace 的 input 資料夾）：
  - input\project_template.xlsx
  - input\fx_rates.csv
  - input\sap_manual.md
  - input\expense_manual.md
  - input\quote_cli_manual.md
- 交付物請寫到 workspace 的 output 資料夾；需要可重跑的 workflow 時，請建立成本平台的 workflow。
