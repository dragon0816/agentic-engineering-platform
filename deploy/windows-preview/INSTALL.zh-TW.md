# AEP Agent 安裝與更新手冊

這份手冊說明如何在自己的 Windows 電腦安裝、更新、確認版本、解除安裝 AEP Agent，
以及遇到問題時怎麼處理。手冊和安裝包一起發佈，請用同一個版本的手冊。

AEP Agent 安裝在你自己的電腦上，只有這台電腦能開啟它的網頁（Agent Web）。

## 1. 安裝前準備（只需要做一次）

1. **Windows 10 或 11（64 位元）。**
2. **Python 3.12（64 位元）。** 在 PowerShell 輸入：

   ```powershell
   python --version
   ```

   - 顯示 `Python 3.12.x`：可以直接安裝。
   - 沒有 Python 或版本不是 3.12：到 <https://www.python.org/downloads/windows/> 下載
     「Windows installer (64-bit)」的 3.12 版。安裝時勾選 **Add python.exe to PATH**。
     不能安裝軟體時，請洽 IT。
   - 已經有 3.12，但 `python` 指到別的版本：安裝時改用 `-PythonExe`，指定 3.12 的
     `python.exe` 完整路徑（見第 2 節）。
3. **公司語言模型（LLM Gateway）的存取資訊**：網址、模型名稱，以及存放權杖的環境變數
   名稱。這些由發佈者或團隊提供。權杖值只放在 Windows 環境變數，不寫進任何檔案。

## 2. 第一次安裝

1. 把收到的 `aep-windows-preview-0.1.0-<版本>.zip` **解壓縮到短路徑**，例如 `C:\aep`。
   路徑太深時，Windows 會悄悄漏掉檔案，安裝就會失敗。
2. 打開解壓縮後的資料夾（看得到 `install.cmd`）。
3. 雙擊 `install.cmd`，在出現的視窗輸入**你的員工帳號**（例如 `leo.chi`）後按 Enter。

   也可以在這個資料夾開 PowerShell 執行：

   ```powershell
   .\install.cmd -Actor 你的帳號
   # python 不是 3.12 時，指定 3.12 的路徑：
   .\install.cmd -Actor 你的帳號 -PythonExe "C:\Users\你\AppData\Local\Programs\Python\Python312\python.exe"
   ```

4. 安裝程式會依序：
   - 檢查每個檔案的 SHA-256；
   - 建立獨立的 Python 環境；
   - 從安裝包內的檔案離線安裝，不會連外下載；
   - 執行健康檢查（doctor）；
   - 在桌面和開始功能表建立 **AEP Agent** 捷徑。

   最後出現 `Installed the local-only preview at ...` 就是安裝完成。

安裝位置固定在：

```text
%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0
```

## 3. 確認安裝成功

在安裝包資料夾雙擊或執行 `verify.cmd`：

- 會顯示 `bundle source revision: <一串版本碼>`，這就是你安裝的版本；
- 接著執行健康檢查。還沒設定的外部整合會顯示 `pending`，這是正常的。

## 4. 開啟 AEP Agent

- 雙擊桌面上的 **AEP Agent** 捷徑；或在安裝包資料夾雙擊 `start-web.cmd`。
- 第一次開啟需要等約 10～30 秒，之後瀏覽器會自動打開 Agent Web。
- 關掉瀏覽器分頁，Agent 仍在背景執行；下次點捷徑會直接打開。

### 第一次使用：設定語言模型

打開 **Settings → Natural-language model**，填入第 1 節取得的資訊：

- Provider：`OpenAI-compatible Gateway`
- Alias：`company`
- Gateway URL：團隊提供的網址
- Model name：團隊提供的模型名稱
- 需要權杖時：只填「SecretRef 名稱」和「Windows 環境變數名稱」，權杖值另外設在
  Windows 使用者環境變數裡

儲存後依照頁面提示，重新開啟 Agent。其他整合（Jira、週報、Knowledge、Telegram、
Laya 等）都在 Settings 頁設定；細節見同一資料夾的 `README.md`。

## 5. 更新到新版本

收到新版 zip 時：

1. 把新版 zip **解壓縮到新的短路徑資料夾**，例如 `C:\aep-new`。
2. 雙擊新資料夾裡的 `update.cmd`。它會：
   - 讀取你原本的帳號和 Bridge ID，不必再輸入；
   - 先關閉正在執行的 Agent Web；
   - 用新版檔案重新安裝程式；
   - **保留**你的 `host.json` 設定、workspace、對話紀錄和已安裝的能力。
3. 看到 `Updated.` 後，執行 `verify.cmd`，確認版本碼和發佈說明（`RELEASE_NOTES.md`）上的
   一致。
4. 用 **AEP Agent** 捷徑重新開啟。

更新失敗時，畫面會停住並顯示原因（見第 7 節）。原本的設定不會被刪除，可以修正後
再執行一次 `update.cmd`。

## 6. 回報問題時請提供

- 版本碼：`verify.cmd` 顯示的 `bundle source revision`；
- `verify.cmd` 的完整輸出；
- 最新的錯誤紀錄：`%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0\workspace\logs`
  裡最新的 `agent-web-*.err.log`；
- 你做了什麼操作、預期看到什麼、實際看到什麼。

**請不要**提供 Agent Web 網址列裡的 token，也不要提供任何權杖或密碼。

## 7. 常見問題

| 畫面上的訊息 | 原因 | 處理方式 |
|---|---|---|
| `This bundle sits too deep for Windows` | 解壓縮的路徑太長 | 移到 `C:\aep` 這類短路徑後重新執行 |
| `Bundle file is missing` | 解壓縮時漏了檔案 | 刪掉資料夾，重新完整解壓縮 |
| `Bundle integrity check failed` | 檔案損毀或被修改 | 重新下載 zip，比對發佈資料夾裡 `SHA256SUMS.txt` 的值 |
| `This bundle requires 64-bit Python 3.12` | Python 版本不對 | 安裝 Python 3.12（64 位元），或加 `-PythonExe` 指定路徑 |
| `Offline wheel installation failed` | 檔案被占用或防毒軟體攔截 | 關閉 Agent Web 後重試；仍失敗時附上畫面截圖回報 |
| `AEP is not installed ... yet`（update.cmd） | 這台電腦還沒安裝過 | 改用 `install.cmd` |
| 捷徑點了沒反應 | Agent Web 啟動失敗 | 看 `workspace\logs` 最新的 `agent-web-*.err.log` 並回報 |
| 網頁顯示要設定模型 | 還沒設定語言模型 | 依第 4 節設定 |

## 8. 解除安裝

在安裝包資料夾執行：

```powershell
.\uninstall.cmd          # 只列出會刪除的資料夾，不會真的刪除
.\uninstall.cmd -Apply   # 真的刪除整個安裝資料夾（含設定與紀錄）
```

解除安裝會刪除 `host.json`、workspace 和對話紀錄。需要保留時，請先另外備份
安裝資料夾。桌面和開始功能表的 **AEP Agent** 捷徑請手動刪除。

## 9. 檔案位置一覽

| 項目 | 位置 |
|---|---|
| 安裝資料夾 | `%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0` |
| 設定 | 安裝資料夾裡的 `host.json`（更新時保留） |
| 工作資料、對話、能力 | 安裝資料夾裡的 `workspace\` |
| 錯誤紀錄 | `workspace\logs\` |
| 已安裝的版本 | 安裝資料夾裡的 `bundle-manifest.json`（`source_revision`） |
