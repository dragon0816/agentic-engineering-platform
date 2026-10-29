# 用 AEP 修改大型程式（例如晶片控制 driver）

給要讓 AEP 的 Agent 修改大型 repository 的團隊成員。設計見 `docs/phases/CODING_AT_SCALE.md`。

## 1. 它怎麼改程式

- 模型**不會整份讀入、也不會整份回傳**檔案。它先看檔案大綱（class、function 與行號），再搜尋、分段讀取
  需要的部分，最後用「找到這段原文 → 換成這段」的精確修改。所以 100 KB 以上的檔案也能改。
- 一次可以改**主要檔案加最多 9 個其他檔案**（`more_files`），每個都要符合 `host.json` 的 `writable`，
  測試檔永遠不能改。
- 驗證順序：你指定的測試 → repository 宣告的檢查（例如 pylint、mypy）→ 整個測試資料夾。失敗時模型會看到
  錯誤訊息與目前的 diff，再修正（最多 3 次）。
- 改動留在獨立的 git worktree 裡給你審，**不會 commit**。CRLF 檔案維持 CRLF，BOM 會保留。
- 程式碼只送到公司內部的 Gateway 模型，不會送到 Claude Code、Codex 這類外部 agent。

## 2. 事前準備

1. **把測試需要的檔案都 commit**（本機 commit 即可，不用 push）。worktree 從 HEAD 建立，未 commit 的修改、
   被 `.gitignore` 忽略的檔案（例如本機的 fixtures、比對工具）都不會在裡面。
2. **專用的 runner 直譯器**：一份獨立安裝的 Python（不能是 venv 的 `python.exe`），位元數要和 repository
   的依賴相符（需要 64-bit 函式庫就用 64-bit）。用它安裝 pytest 與 repository 的依賴，以及要宣告的檢查工具
   （pylint、mypy…）。
3. **防火牆規則**：在系統管理員 PowerShell 執行一次（`aep-host doctor` 會印出完整指令）：
   `New-NetFirewallRule -DisplayName "AEP coding runner - block outbound" -Direction Outbound -Program "<runner python.exe>" -Action Block -Profile Any`
4. 檔案必須是 UTF-8，而且不能混用 CRLF 與 LF；否則模型會被告知這個檔不能改。

## 3. `host.json` 設定範例

```json
"coding": {
  "runner_python": "C:\\Users\\<you>\\AppData\\Local\\AgenticEngineeringPlatform\\coding-runner\\python\\python.exe",
  "timeout_seconds": 900,
  "memory_mb": 4096,
  "author_max_turns": 40,
  "author_max_output_tokens": 8000,
  "change_max_processes": 1,
  "repositories": [
    {
      "name": "wmt",
      "path": "C:\\work\\WMT",
      "writable": ["src/**/*.py"],
      "test_folder": "tests",
      "checks": [
        {"name": "pylint", "module": "pylint", "args": ["{files}"]},
        {"name": "mypy", "module": "mypy", "args": ["{files}"]}
      ]
    }
  ]
}
```

- `timeout_seconds` 是**每一次**測試或檢查的上限（最多 1800）；整套測試要在這個時間內跑完。
- `checks` 最多 5 個，以 `python -m <module> <args>` 在 worktree 中執行；`{files}` 會換成這次可以改的檔案。
  非 0 結束就算失敗。
- `change_max_processes` 預設 1（測試不能開子程序）。如果測試一定要啟動其他程式，才調高；子程序不受
  runner 防火牆規則保護，這是你接受的風險。
- 測試程式無法連網（防火牆）、只能寫入 worktree 與 run 資料夾（低完整性）。需要真實 DUT 或網路的測試不適合
  在這裡跑，請用 mock 或另外在 bench 上驗證。

## 4. 怎麼下指令

在 Agent Web 或 Telegram 對 Agent 說要改哪個 repository，並提供：

- **要改什麼**：一兩句描述測試期待的行為。
- **主要檔案**：例如 `src/wmt/qualcomm_wlan_driver.py`。
- **其他檔案**（可省略）：例如新抽出的 `src/wmt/op2_table.py`。
- **哪些測試代表完成**：既有的 pytest 檔案或 node id。

完成後結果會列出 worktree 位置、每一步驗證的結果與 diff；evidence 在 run 資料夾的 `result.json`。

## 5. 目前的限制

- **看起來像密碼的程式碼會被擋**：平台的憑證規則會拒絕含有 `password = ...`、`password: str`、`api_key: ...`
  這類文字的修改（`author_change_has_credential`）。如果 driver 裡有這類行，目前無法用這條路修改，需要
  平台維護者決定處理方式。
- 還沒有在真實 repository 上跑過（C7 練習 repository 的首次真機執行也還沒做）。
- 只改 Python 專案的 pytest 流程；其他語言或建置系統不在範圍內。
