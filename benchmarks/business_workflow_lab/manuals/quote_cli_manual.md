# quote_cli（模擬報價系統 CLI）使用說明

> 合成測試資料。

- Windows 執行：`"{LAB}\quote_cli_mock\quote_cli.cmd" <command>`
- 跨平台執行：`python "{LAB}\quote_cli_mock\run_quote_cli.py" <command>`
- `quote_cli --help` 的內容如下：

```text
{CLI_HELP}
```

補充：
- `quotes list` 回傳 `{"schema_version": 1, "items": [...], "count": N}`；`items` 只有表頭欄位。
- `quotes get Q0001 --format json` 回傳 `{"schema_version": 1, "header": {...}, "line_items": [...]}`，line items 欄位：ProductID、ProductName、Quantity、UnitPrice、LineAmount。
- 表頭欄位：QuoteID、CustomerID、ProjectID、QuoteDate、ValidUntil、Status、Currency、Subtotal、DiscountPercent、NetAmount。
- NetAmount = Subtotal × (1 − DiscountPercent / 100)，四捨五入（ROUND_HALF_UP）至兩位小數；LineAmount = Quantity × UnitPrice。
- 只有 exit code 0 時 stdout 才是正式資料；錯誤訊息在 stderr。
