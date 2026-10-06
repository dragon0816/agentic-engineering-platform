# Expense Viewer（模擬原生桌面費用程式）使用說明

> 合成測試資料。這是 Windows 桌面視窗程式（Tkinter），不是網頁。

- 啟動：`python "C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\expense_desktop_mock\expense_app.py"`（需要已登入的互動式 Windows 桌面）
- 視窗標題：`Expense Viewer (synthetic lab)`

## 主視窗

| 控制項 | 說明 |
|---|---|
| Employee 員工 | 下拉選單 E001～E006，空白代表全部 |
| Project 專案 | 下拉選單 P001～P005，空白代表全部 |
| Date from 起 / Date to 迄 | YYYY-MM-DD，含起訖兩日（ExpenseDate） |
| Status 狀態 | Draft、Submitted、Approved、Rejected，空白代表全部 |
| Query 查詢 | 執行查詢，完成後跳出「查詢完成，共 N 筆」或「查無資料（0 筆）」 |

- 結果表格每頁 8 筆，下方顯示 `Total N rows · Page x / y`，用 **Previous 上一頁** / **Next 下一頁** 換頁。
- 表格欄位：ExpenseID、EmployeeID、EmployeeName、ProjectID、ExpenseDate、Category、Currency、Amount、Status。
- 選一列後按 **Details 明細**（或雙擊該列）開啟明細視窗，內含 ReceiptID、Category、Description（可能含中文與換行）、MissingReceipt；按 **Close 返回** 關閉。
- **Export CSV 匯出 CSV**、**Export Excel 匯出 Excel**：開啟 Windows「另存新檔」對話框，匯出目前篩選條件的全部結果（不只目前這一頁），欄位包含 ReceiptID、Description、MissingReceipt。
- 匯出若顯示「暫時無法寫入，請重試」，表示這次沒有產生檔案，可以再按一次匯出。
- 程式沒有其他資料介面；請透過視窗操作與匯出取得資料。
