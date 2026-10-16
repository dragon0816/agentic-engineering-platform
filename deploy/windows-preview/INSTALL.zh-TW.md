# AEP Agent 安裝與更新手冊

這份手冊只說明**安裝、確認、開啟、更新、解除安裝**，以及安裝時遇到問題怎麼辦。
每個設定和功能怎麼用（LLM gateway、語言模型、Agent Web 各頁、Knowledge、Telegram、
共享平台、Agent 模式、排程……）都寫在同一資料夾的
**`USER_GUIDE.zh-TW.md`（AEP Agent 使用指南）**。

手冊和安裝包一起發佈，請用同一個版本的手冊。AEP Agent 安裝在你自己的電腦上，只有這台
電腦能開啟它的網頁（Agent Web）。

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
   - 已經有 3.12，但 `python` 指到別的版本：安裝時加 `-PythonExe`，指定 3.12 的
     `python.exe` 完整路徑（見第 2 節）。
3. **公司網域登入**：安裝包內建 LLM gateway，它用你的 Windows 網域登入取得公司模型的
   權杖。安裝時最好在公司網路上，或連著 VPN（細節見使用指南第 1 章「設定 LLM
   gateway（最重要）」）。
4. **你的員工帳號名稱**（例如 `alex.wang`）：安裝時要輸入。之後連共享平台時，管理員
   會用**同一個名稱**替你開帳號，所以只用英文字母、數字和 `. - _`，**不要用 email**。

## 2. 第一次安裝

1. 把收到的 `aep-windows-preview-0.1.0-<版本碼>.zip` **解壓縮到短路徑**，例如 `C:\aep`。
   路徑太深時，Windows 會悄悄漏掉檔案，安裝就會失敗。
2. 打開解壓縮後的資料夾（看得到 `install.cmd`）。
3. 雙擊 `install.cmd`，在出現的視窗輸入**你的員工帳號**後按 Enter。

   也可以在這個資料夾開 PowerShell 執行：

   ```powershell
   .\install.cmd -Actor alex.wang
   # python 不是 3.12 時，指定 3.12 的路徑：
   .\install.cmd -Actor alex.wang -PythonExe "C:\Python312\python.exe"
   ```

4. 安裝程式會依序：
   - 檢查路徑長度，再檢查每個檔案的 SHA-256；
   - 建立獨立的 Python 環境，並從安裝包內的檔案**離線**安裝（不會連外下載）；
   - 安裝 **LLM gateway**，用你的網域登入取得權杖、設成登入 Windows 時自動啟動，
     並啟動它；
   - 執行健康檢查（doctor）；
   - 在桌面和開始功能表建立 **AEP Agent** 捷徑；
   - 替這台電腦上找得到的 Claude Code、Codex、GitHub Copilot 裝好 AEP 的 skills 和
     MCP 設定；
   - 裝好安裝包附帶的 Skills：AEP 正在使用的 Skills **開啟**，Hermes skill pack
     **關閉**當備用。

   最後出現 `Installed the local-only preview at ...` 就是安裝完成。

安裝位置固定在：

```text
%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0
```

### 安裝選項

一般人不需要加任何選項。需要時加在 `install.cmd` 後面：

| 選項 | 作用 |
|---|---|
| `-Actor <帳號>` | 你的員工帳號（不加會在視窗裡問你） |
| `-PythonExe "<路徑>"` | 指定 Python 3.12 的 `python.exe` |
| `-BridgeId <名稱>` | 這台電腦在平台上的名稱；預設是 `bridge-<電腦名稱>`，兩台電腦同名時才需要 |
| `-InstallRoot "<資料夾>"` | 改安裝位置（例如路徑太深時用 `C:\aep\preview`） |
| `-NoGateway` | 不安裝 LLM gateway（團隊有別的模型服務時）；之後在 Settings 填模型網址 |
| `-NoAgentSkills` | 不動 Claude Code / Codex / Copilot 的設定 |
| `-NoShortcut` | 不建立桌面和開始功能表捷徑 |

## 3. 確認安裝成功

在安裝包資料夾雙擊或執行 `verify.cmd`：

- 會顯示 `bundle source revision: <一串版本碼>`，這就是你安裝的版本；
- 接著執行健康檢查。還沒設定的外部整合會顯示 `pending`，這是正常的。

再確認語言模型能用：開啟 AEP Agent（第 4 節）→ 左邊 **Settings** → **LLM gateway**
卡片，狀態是 `Running`，按 **Test** 看到 `✓` 開頭的結果。不是時，請看使用指南第 1 章的疑難排解。

## 4. 開啟 AEP Agent

- 雙擊桌面上的 **AEP Agent** 捷徑；或在安裝包資料夾雙擊 `start-web.cmd`。
- 第一次開啟需要等約 10～30 秒，之後瀏覽器會自動打開 Agent Web。
- 關掉瀏覽器分頁，Agent 仍在背景執行；下次點捷徑會直接打開。
- 接下來請照使用指南第 0 章「快速開始」逐項完成設定。

## 5. 更新到新版本

收到新版 zip 時：

1. 把新版 zip **解壓縮到新的短路徑資料夾**，例如 `C:\aep-new`。
2. 雙擊新資料夾裡的 `update.cmd`。它會：
   - 讀取你原本的帳號和 Bridge ID，不必再輸入；
   - 先關閉正在執行的 Agent Web（**正在跑的工作會被中斷**，請先等它們跑完）；
   - 用新版檔案重新安裝程式；
   - **保留**你的 `host.json` 設定、workspace、對話紀錄和已安裝的能力；
   - 先停下 AEP 啟動的 LLM gateway，更新後再啟動；gateway 的設定和權杖保留
     （加 `-NoGateway` 則不動 gateway）；
   - 把 Claude Code / Codex / Copilot 裡 AEP 的 skills 和 MCP 設定更新到新版
     （加 `-NoAgentSkills` 則不動）；
   - 加入新版附帶的 Skills；已經在這台電腦上的**維持你設定的狀態**：你關掉的不會被
     重新打開，你移除的不會被裝回來，你改過的不會被覆寫。
3. 看到 `Updated.` 後，執行 `verify.cmd`，確認版本碼和發佈說明（`RELEASE_NOTES.md`）上的
   一致。
4. 用 **AEP Agent** 捷徑重新開啟。

更新失敗時，畫面會停住並顯示原因（見第 9 節）。原本的設定不會被刪除，修正後再執行一次
`update.cmd` 即可。要退回舊版：解壓縮舊版 zip，執行裡面的 `update.cmd`，設定一樣保留。

## 6. 解除安裝

在安裝包資料夾執行：

```powershell
.\uninstall.cmd          # 只列出會刪除的資料夾，不會真的刪除
.\uninstall.cmd -Apply   # 真的刪除整個安裝資料夾（含設定與紀錄）
```

`-Apply` 會依序：

1. 把 AEP 放進 Claude Code / Codex / Copilot 的 skills 和 MCP 設定拿掉（只拿 AEP 自己的，
   其他設定不動）；
2. 關閉 LLM gateway 的登入自動啟動，並停下 AEP 啟動的 gateway；
3. 刪除安裝資料夾。

會保留、需要時請自行刪除的：

- gateway 的設定和權杖檔（`%LOCALAPPDATA%\AgenticEngineeringPlatform\gateway\`）；
- 桌面和開始功能表的 **AEP Agent** 捷徑；
- 你的 Windows 使用者環境變數裡的權杖（例如 Telegram bot、Personal Agent code）。

解除安裝會刪除 `host.json`、workspace 和對話紀錄。需要保留時，請先另外備份安裝資料夾。

## 7. 檔案位置一覽

| 項目 | 位置 |
|---|---|
| 安裝資料夾 | `%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0` |
| 設定 | 安裝資料夾裡的 `host.json`（更新時保留） |
| 工作資料、對話、能力 | 安裝資料夾裡的 `workspace\` |
| 錯誤紀錄 | `workspace\logs\` |
| 已安裝的版本 | 安裝資料夾裡的 `bundle-manifest.json`（`source_revision`） |
| LLM gateway 程式 | 安裝資料夾裡的 `gateway-venv\` |
| LLM gateway 設定、權杖、紀錄 | `%LOCALAPPDATA%\AgenticEngineeringPlatform\gateway\`（`gateway.json`、`litellm-config.yaml`、`gateway.env`、`logs\gateway.log`；更新與解除安裝都保留） |
| Claude Code 的 AEP skills / MCP | `%USERPROFILE%\.claude\skills\aep-*`、`%USERPROFILE%\.claude.json` |
| Codex 的 AEP skills / MCP | `%USERPROFILE%\.agents\skills\aep-*`、`%USERPROFILE%\.codex\config.toml` |
| Copilot 的 AEP skills / MCP | `%USERPROFILE%\.copilot\skills\aep-*`、`%USERPROFILE%\.copilot\mcp-config.json` |
| 關閉中的 Skills（含 Hermes skill pack） | `workspace\assets\skills\disabled\` |
| 移除的能力（可找回） | `workspace\removed\<日期>\` |

其他資料夾（Knowledge 沙盒、上傳檔、排程……）見使用指南各章。

## 8. 回報問題時請提供

- 版本碼：`verify.cmd` 顯示的 `bundle source revision`；
- `verify.cmd` 的完整輸出；
- 最新的錯誤紀錄：`workspace\logs` 裡最新的 `agent-web-*.err.log`；
  與語言模型有關時，另附 `%LOCALAPPDATA%\AgenticEngineeringPlatform\gateway\logs\gateway.log`
  的最後幾十行；
- 你做了什麼操作、預期看到什麼、實際看到什麼。

**請不要**提供 Agent Web 網址列裡的 token、`gateway.env` 的內容，也不要提供任何權杖、
密碼或邀請連結。

## 9. 安裝與更新的常見錯誤

| 畫面上的訊息 | 原因 | 處理方式 |
|---|---|---|
| `This bundle sits too deep for Windows` | 解壓縮的路徑太長 | 移到 `C:\aep` 這類短路徑後重新執行 |
| `would need …-character paths`（gateway） | 安裝路徑太深 | 用較短的 `-InstallRoot`（例如 `C:\aep\preview`），或加 `-NoGateway` |
| `Bundle file is missing` | 解壓縮時漏了檔案 | 刪掉資料夾，重新完整解壓縮 |
| `Bundle integrity check failed` | 檔案損毀或被修改 | 重新下載 zip，比對發佈資料夾裡 `SHA256SUMS.txt` 的值 |
| `This bundle requires 64-bit Python 3.12` | Python 版本不對 | 安裝 Python 3.12（64 位元），或加 `-PythonExe` 指定路徑 |
| `Offline wheel installation failed` | 檔案被占用或防毒軟體攔截 | 關閉 Agent Web 後重試；仍失敗時附上畫面截圖回報 |
| `The LLM gateway's token could not be renewed now` | 安裝時沒有網域登入 | 不影響安裝。連上公司網路或 VPN 後，到 Settings → LLM gateway 按 **Refresh token** |
| `AEP is not installed ... yet`（update.cmd） | 這台電腦還沒安裝過 | 改用 `install.cmd` |
| 捷徑點了沒反應 | Agent Web 啟動失敗 | 看 `workspace\logs` 最新的 `agent-web-*.err.log` 並回報 |
| Agent 說 LLM gateway 沒在執行、還在啟動或 401 | gateway 的狀態 | 見使用指南第 1 章的疑難排解 |

其他使用上的問題，請看使用指南第 16 章「常見問題與錯誤代碼」。
