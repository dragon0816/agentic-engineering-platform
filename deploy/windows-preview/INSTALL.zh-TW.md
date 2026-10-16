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
3. **公司網域登入**：安裝包內建 LLM gateway，用你的 Windows 網域登入取得公司模型的
   權杖（見「設定 LLM gateway（最重要）」）。安裝時最好在公司網路上，或連著 VPN。

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
   - 安裝 **LLM gateway**，用你的網域登入取得權杖、設成登入時自動啟動並啟動它
     （見下一節；不想要時加 `-NoGateway`）；
   - 執行健康檢查（doctor）；
   - 在桌面和開始功能表建立 **AEP Agent** 捷徑；
   - 替這台電腦上找得到的 Claude Code、Codex、GitHub Copilot 裝好 AEP 的 skills 和
     MCP 設定（見第 11 節；不想要時加 `-NoAgentSkills`）；
   - 裝好安裝包附帶的 Skills：AEP 正在使用的 Skills **開啟**，Hermes skill pack
     **關閉**當備用（見第 12 節）。

   最後出現 `Installed the local-only preview at ...` 就是安裝完成。

安裝位置固定在：

```text
%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0
```

## 設定 LLM gateway（最重要）

AEP Agent 要透過 **LLM gateway** 才能使用公司的語言模型（chatrs 上的 GPT 等）。
沒有它，Agent 無法回答任何一般對話。安裝程式已經替你裝好、設定好，並設成登入
Windows 時自動啟動；這一節說明它是什麼、怎麼確認它正常、出問題時怎麼處理。

### 它是什麼

- 一個只在這台電腦上聽 `127.0.0.1:4000` 的小程式（LiteLLM），把 Agent 的請求轉給
  公司的模型服務。別台電腦連不到它。Claude Code 也可以透過它使用公司模型。
- 程式裝在安裝資料夾的 `gateway-venv\`；設定、權杖檔和紀錄放在
  `%LOCALAPPDATA%\AgenticEngineeringPlatform\gateway\`，**更新和解除安裝都會保留**。
- Agent Web 的 **Settings → Natural-language model** 會顯示
  「Uses the built-in gateway at 127.0.0.1:4000」，不需要再填任何網址或權杖。

### 自動啟動

- 登入 Windows 時自動啟動（工作排程器的「AEP LLM Gateway」，只對你自己的帳號，
  不需要系統管理員權限；工作排程器拒絕時改用你帳號的登入啟動項目）。
- 重開機後第一次啟動可能要 1～3 分鐘。這段時間 Agent 會回答
  「The LLM gateway is still starting」，稍等再問即可；Settings 的卡片會顯示
  `Starting…`，準備好後變成 `Running`。
- gateway 停掉後**不會**自己一直重啟（權杖錯誤時一直重啟只會掩蓋原因）；請看下面的
  疑難排解。

### 權杖（token）

- 公司模型服務要一個約 28 天有效的權杖。gateway 用你的 **Windows 網域登入
  （Kerberos）** 自動換新：不需要也不會儲存密碼，不開瀏覽器。
- 權杖只存在 `%LOCALAPPDATA%\AgenticEngineeringPlatform\gateway\gateway.env`；
  Agent Web 只顯示到期日，不顯示權杖本身。**不要把這個檔案或權杖寄給任何人。**
- 換新需要：電腦在公司網域且已登入——在公司網路上，或連上 VPN 並有 Kerberos 票證
  （PowerShell 執行 `klist`，看得到 `krbtgt/` 開頭的票證）。
- 剩 7 天以內時，登入自動啟動會先換新。也可以手動：Settings → **LLM gateway** →
  **Refresh token**。在家沒有 VPN 時換不了，但舊權杖到期前照常可用。
- 安裝時若顯示「The LLM gateway's token could not be renewed now」，表示當下沒有網域
  登入：連上公司網路或 VPN 後，到 Settings → LLM gateway 按 **Refresh token**。

### 確認 gateway 正常

1. 打開 Agent Web → **Settings → LLM gateway**：
   - 狀態是 `Running · 127.0.0.1:4000`；
   - Token 顯示 `valid until …（N days left）`；
   - 按 **Test**，看到 `✓ gpt-5.5: OK`。
2. 或在 PowerShell 執行：

   ```powershell
   $aep = "$env:LOCALAPPDATA\AgenticEngineeringPlatform\preview-0.1.0\.venv\Scripts\aep-host.exe"
   & $aep gateway status    # 狀態、權杖到期日、設定是否正確
   & $aep gateway test      # 問預設模型一句話
   ```

常用指令（都用上面的 `$aep`）：

| 指令 | 作用 |
|---|---|
| `& $aep gateway status` | 是否在執行、權杖到期日、LiteLLM 版本、自動啟動 |
| `& $aep gateway start` / `stop` / `restart` | 啟動 / 停止 / 重新啟動（只停 AEP 自己啟動的那一個） |
| `& $aep gateway test --model gpt-5.4` | 測試某個模型 |
| `& $aep gateway refresh-token --force` | 立即用網域登入換新權杖（換新後按 Restart） |
| `& $aep gateway autostart --on` / `--off` | 開啟 / 關閉登入時自動啟動 |

不想安裝 gateway（例如團隊有別的模型服務）時，安裝和更新加 `-NoGateway`，再到
Settings → Natural-language model 填團隊提供的網址。

### 疑難排解

| 你看到的 | 原因 | 處理方式 |
|---|---|---|
| Agent 回答「The LLM gateway is not running」 | gateway 沒在執行 | Settings → LLM gateway → **Start**；仍停住時看 `gateway\logs\gateway.log` 最後幾行 |
| 「The LLM gateway is still starting」 | 剛開機，LiteLLM 還在載入 | 等 1～3 分鐘再問 |
| `401`、「the company token has probably expired」 | 權杖過期，或本機金鑰不一致 | **Refresh token** 後 **Restart**；仍是 401 時回報（不要貼出 `gateway.env` 或 `LITELLM_MASTER_KEY` 的值） |
| `405 Method Not Allowed` | 某個模型在 `litellm-config.yaml` 設成 `openai/`，LiteLLM 改走公司服務沒有的 Responses API | 模型一律用 `hosted_vllm/`；或執行 `& $aep gateway init --force` 依 `gateway.json` 重新產生設定 |
| 回答串流到一半中斷，`gateway.log` 出現 `IndexError` | 公司服務送出 `choices` 為空的片段 | gateway 內建修正；若在換過 LiteLLM 版本後出現，回報 `gateway status` 顯示的版本（LiteLLM 內部改變時 gateway 會拒絕啟動並說明原因） |
| `127.0.0.1:4000 is already served` / 卡片顯示 `not started by AEP` | 另一個程式（例如你自己架的 gateway）已在用 4000 | 正常的保護：AEP 不會啟動第二個，也不會停掉別人的。要換埠號：`& $aep gateway init --port 4001 --force`，再把 Natural-language model 的網址改成同一個埠號 |
| `No Kerberos ticket` | 沒有網域登入 | 連公司網路或 VPN；必要時登出再登入，用 `klist` 檢查 |
| `rejected the Windows ticket (401)` | 公司登入網站不在「近端內部網路」區域 | 請 IT 確認；`klist purge` 後登出再登入 |
| 安裝時 `would need …-character paths` | 安裝路徑太深 | 用較短的 `-InstallRoot`（例如 `C:\aep\preview`），或加 `-NoGateway` |

## 3. 確認安裝成功

在安裝包資料夾雙擊或執行 `verify.cmd`：

- 會顯示 `bundle source revision: <一串版本碼>`，這就是你安裝的版本；
- 接著執行健康檢查。還沒設定的外部整合會顯示 `pending`，這是正常的。

## 4. 開啟 AEP Agent

- 雙擊桌面上的 **AEP Agent** 捷徑；或在安裝包資料夾雙擊 `start-web.cmd`。
- 第一次開啟需要等約 10～30 秒，之後瀏覽器會自動打開 Agent Web。
- 關掉瀏覽器分頁，Agent 仍在背景執行；下次點捷徑會直接打開。

### 第一次使用：語言模型

安裝程式已經把語言模型設成內建的 LLM gateway（見「設定 LLM gateway（最重要）」），
Settings → Natural-language model 會顯示「Uses the built-in gateway at 127.0.0.1:4000」，
不需要再設定。只有不用內建 gateway（安裝時加了 `-NoGateway`）時，才打開
**Settings → Natural-language model** 填入團隊提供的資訊：

- Provider：`OpenAI-compatible Gateway`
- Alias：`company`
- Gateway URL：團隊提供的網址
- Model name：團隊提供的模型名稱
- 需要權杖時：只填「SecretRef 名稱」和「Windows 環境變數名稱」，權杖值另外設在
  Windows 使用者環境變數裡

儲存後依照頁面提示，重新開啟 Agent。其他整合（Jira、週報、Knowledge、Telegram、
Laya 等）都在 Settings 頁設定；細節見同一資料夾的 `README.md`。

## 5. 連上共享平台（Shared Platform）

共享平台是團隊共用的 Skill 與 Workflow 市集：你可以**安裝**同事分享的能力，也可以
把自己的能力**發布**給大家用。平台由管理員架設，你只需要做一次下面的設定。

你會用到三種代碼，用途不同，**都不要貼到對話、文件或聊天軟體裡**：

| 名稱 | 從哪裡來 | 用途 | 效期 |
|---|---|---|---|
| 邀請連結（Invitation） | 管理員寄給你 | 第一次登入 Member Portal（網頁），建立你的帳號並設定密碼 | 只能用一次 |
| 密碼 | 你自己在第一次登入時設定 | 之後用「帳號 + 密碼」登入 Member Portal | 直到你更改 |
| Personal Agent code | Member Portal 的「Connect a Personal Agent」 | 讓你的 Agent 以你的身分發布、註冊這台電腦 | 30 天 |
| Bridge token | Agent Web 按「Enroll this PC」時自動取得 | 讓這台電腦從平台讀取清單、安裝 | 90 天 |

### 5.1 跟管理員要三樣東西

1. **你的帳號名稱**：必須和這台電腦 `host.json` 裡 `device.registered_by` 的值**完全一樣**
   （例如 `leo.chi`）。只能用英文字母、數字和 `. - _`，**不要用 email**。
   不確定時，在 Agent Web 的 **Settings → Shared platform** 卡片上看「registered by」。
2. **Member Portal URL**（例如 `https://<平台位址>:8776`）
3. **Bridge API URL**（例如 `https://<平台位址>:8775`）

管理員會用你的帳號名稱發一張邀請，寄給你一個邀請連結。

### 5.2 登入 Member Portal（瀏覽器）

**第一次（用邀請連結，同時設定密碼）**

1. 打開管理員給你的**邀請連結**，畫面會顯示 **Set your password** 和你的帳號名稱；
   或打開 Member Portal URL，展開 **Have an invitation or a password reset link?**，
   把連結貼上後按 **Continue**。
2. 輸入兩次新密碼，按 **Set password and sign in**。密碼至少 12 個字元（可以用幾個英文字
   組成的句子），不能包含帳號名稱，也不能是常見密碼。
3. 右上角顯示你的帳號名稱，就是登入成功。這個瀏覽器之後會記得你。

**之後（帳號 + 密碼）**

- 打開 Member Portal URL，在 **Sign in** 輸入 **Account**（例如 `leo.chi`）與
  **Password**，按 **Sign in**。瀏覽器的密碼管理員可以記住它。
- 輸入錯誤 5 次，這個帳號會被鎖 15 分鐘；畫面只會說「帳號或密碼錯誤」，不會說是哪一個。
- **改密碼**：登入後按右上角 **Password**，輸入目前密碼與新密碼。其他瀏覽器會被登出，
  這個瀏覽器保持登入；Agent 的 Personal Agent code 不受影響。
- 以前只用邀請連結登入、還沒有密碼的人：登入後頁面上方會提示 **Set password**，
  按下去設定即可（不需要目前密碼）。
- **忘記密碼**：請管理員從 **Members & invitations** 發一個 **Password reset link**
  給你（只能用一次、預設 60 分鐘內有效）。打開後設定新密碼就會登入，其他瀏覽器會被登出。

### 5.3 讓你的 Agent 代表你（Personal Agent code）

1. 在 Member Portal 的 **Publish from your Personal Agent** 區塊按
   **Connect a Personal Agent**，複製出現的代碼（只會顯示這一次）。
2. 用桌面捷徑打開 Agent Web → **Settings → Shared platform**：
   - **Member Portal URL**、**Bridge API URL**：填 5.1 拿到的兩個網址；
   - **Personal Agent code**：貼上剛剛的代碼；
   - 按 **Save**。代碼只存在你的 Windows 使用者設定裡，不會寫進任何檔案。

### 5.4 註冊這台電腦（Enroll this PC，只做一次）

在同一張 **Shared platform** 卡片按 **Enroll this PC**：

- 成功時顯示 `Enrolled as <bridge-id>`，並顯示 token 的到期日。
- 這一步只是讓這台電腦**可以從平台拿東西**，不會安裝任何能力，也不會改變這台電腦
  能執行什麼。
- 再按一次只會換一個新 token（舊的失效），不會重複註冊。
- 顯示 **The Bridge API URL did not answer** 時，什麼都沒有存，請檢查 Bridge API URL。

### 5.5 安裝同事分享的 Skill / Workflow

1. Agent Web → **Capabilities**，往下到 **Share Platform Library**。
2. 點一張卡片展開細節（說明、版本、擁有者、誰能用、依賴的 Workflow）。
3. 按 **+ Add to this Agent**。Agent 會自動在平台登記並安裝到這台電腦，畫面會自己
   更新，左邊清單會出現新的項目，不需要再按其他按鈕。
4. 不想要了：在卡片上按 **Remove selection**；或在左邊清單選取後，按右上角的
   **Remove from this Agent**（檔案會移到 `workspace\removed\<日期>\`，可以找回）。
5. 用不到但想保留：在清單上把開關切到 **off**，Agent 就不會再選用它。

如果這台電腦有手寫的 `grants.json`，安裝只會放進檔案，**能執行什麼仍由
`grants.json` 決定**，卡片上會註明。

### 5.6 把自己的 Skill / Workflow 分享給大家

1. Agent Web → **Capabilities** → **Publish to the shared platform** 卡片。
2. 選擇要分享的 Skill 或 Workflow、變更等級（patch / minor / major）、
   **Who can use it**（只有我的團隊 / 全公司），寫一句給審核者的說明，按
   **Publish for review**。
3. 送出後狀態是 **pending**，要等平台管理員審核通過，其他人才看得到。版本號由平台決定。
4. Skill 若會執行某個 Workflow，那個 Workflow 也要一起發布（或已經在平台上）。
5. 發布後，擁有者或管理員可以在 Member Portal 的 **My published assets** 修改
   **Who can use it**。

### 5.7 常見問題

| 畫面上的訊息 | 原因 | 處理方式 |
|---|---|---|
| `device_owner_mismatch` | Portal 帳號和這台電腦的 `registered_by` 不同 | 請管理員用 `registered_by` 的名稱發邀請，重做 5.2～5.4 |
| `Could not create invitation: invalid_request`（管理員） | 帳號名稱有 `@` 或其他符號 | 只用英文字母、數字和 `. - _` |
| `session_expired` | Portal 網頁閒置太久 | 重新整理頁面（新版會自動續期） |
| 「Account or password is wrong, or there were too many attempts」 | 帳號或密碼錯誤，或錯太多次被鎖 15 分鐘 | 等 15 分鐘再試；忘記密碼請管理員發 Password reset link |
| 「This reset link was already used / has expired」 | 重設連結只能用一次且有期限 | 請管理員再發一個 |
| `publisher_not_authorized` | 這個名稱屬於別人 | 請擁有者把你加為 co-editor，或改用新的名稱 |
| Library 是空的 | 還沒註冊、或沒有你能用的項目 | 先做 5.4；或請擁有者把 **Who can use it** 改成全公司 |
| `platform_unreachable` | 平台位址錯誤或網路不通 | 檢查兩個網址；確認平台有在執行 |

## 6. 更新到新版本

收到新版 zip 時：

1. 把新版 zip **解壓縮到新的短路徑資料夾**，例如 `C:\aep-new`。
2. 雙擊新資料夾裡的 `update.cmd`。它會：
   - 讀取你原本的帳號和 Bridge ID，不必再輸入；
   - 先關閉正在執行的 Agent Web；
   - 用新版檔案重新安裝程式；
   - **保留**你的 `host.json` 設定、workspace、對話紀錄和已安裝的能力；
   - 先停下 AEP 啟動的 LLM gateway，更新後再啟動它；gateway 的設定和權杖保留
     （加 `-NoGateway` 則不動 gateway）；
   - 把 Claude Code / Codex / Copilot 裡 AEP 的 skills 和 MCP 設定更新到新版
     （加 `-NoAgentSkills` 則不動）；
   - 加入新版附帶的 Skills；已經在這台電腦上的**維持你設定的狀態**：你關掉的不會被
     重新打開，你移除的不會被裝回來，你改過的不會被覆寫（見第 12 節）。
3. 看到 `Updated.` 後，執行 `verify.cmd`，確認版本碼和發佈說明（`RELEASE_NOTES.md`）上的
   一致。
4. 用 **AEP Agent** 捷徑重新開啟。

更新失敗時，畫面會停住並顯示原因（見第 8 節）。原本的設定不會被刪除，可以修正後
再執行一次 `update.cmd`。

## 7. 回報問題時請提供

- 版本碼：`verify.cmd` 顯示的 `bundle source revision`；
- `verify.cmd` 的完整輸出；
- 最新的錯誤紀錄：`%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0\workspace\logs`
  裡最新的 `agent-web-*.err.log`；
- 你做了什麼操作、預期看到什麼、實際看到什麼。

**請不要**提供 Agent Web 網址列裡的 token，也不要提供任何權杖或密碼。

## 8. 常見問題

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
| Agent 說 LLM gateway 沒在執行、還在啟動或 401 | gateway 的狀態 | 見「設定 LLM gateway（最重要）」的疑難排解 |

## 9. 解除安裝

在安裝包資料夾執行：

```powershell
.\uninstall.cmd          # 只列出會刪除的資料夾，不會真的刪除
.\uninstall.cmd -Apply   # 真的刪除整個安裝資料夾（含設定與紀錄）
```

`-Apply` 會先把 AEP 放進 Claude Code / Codex / Copilot 的 skills 和 MCP 設定拿掉
（只拿 AEP 自己的，其他設定不動），關閉 LLM gateway 的登入自動啟動並停下 AEP 啟動的
gateway，再刪除安裝資料夾。gateway 的設定和權杖檔
（`%LOCALAPPDATA%\AgenticEngineeringPlatform\gateway\`）會保留，不需要時請自行刪除。

解除安裝會刪除 `host.json`、workspace 和對話紀錄。需要保留時，請先另外備份
安裝資料夾。桌面和開始功能表的 **AEP Agent** 捷徑請手動刪除。

## 10. 檔案位置一覽

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
| Hermes skills 給 coding agent 用的原始資料夾 | `workspace\agent-skills\hermes-*`（開啟時才複製到 Claude Code / Copilot 的 `skills\`） |

## 11. 用 Claude Code / Codex / Copilot 產生 AEP 可用的 Skill 與 Workflow

AEP 和一般 Claude Code 最大的差別：在 AEP 做出來的 Skill 和 Workflow **在 AEP 上就能用**
（Agent Web 會自動產生執行表單，Telegram 會一題一題問），而且你的 coding agent 可以直接
查 AEP 的公司知識庫（Knowledge）。

### 11.1 預設裝了什麼

安裝和更新時，AEP 會替這台電腦上**找得到的** Claude Code、Codex、GitHub Copilot CLI
（指令在 PATH 上，或已有它們的設定資料夾）放入：

| 項目 | 用途 |
|---|---|
| skill `aep-workflow-creator` | 教 agent 寫出 AEP 可用的 Workflow：先釐清需求、用有型別的參數（日期、下拉選單、上傳檔案…）、檢查、送出、測試、請你核准 |
| skill `aep-skill-creator` | 教 agent 寫 AEP Agent 用的 Skill |
| skill `aep-knowledge` | 教 agent 查 AEP 知識庫：搜尋 → 讀頁面 → 註明出處，不亂編產品資訊 |
| MCP server `aep` | 撰寫工具：目錄、格式、檢查、送出、測試、申請安裝（只回狀態碼，看不到公司資料） |
| MCP server `aep-assistant` | 知識庫搜尋／閱讀／問答，以及已安裝的 Workflow；透過**正在執行的 Agent Web** 回答 |

- 只會改 AEP 自己的項目；你原有的 MCP server、skills 都不會被刪改。設定檔修改前會先備份成
  `<檔名>.aep-backup-<時間>`。
- 你自己已有同名的 skill 或 MCP server 時，AEP 會保留你的，並在畫面上註明。
- 權杖（token）不會寫進 agent 的設定檔；`aep-assistant` 每次呼叫時才從 AEP 讀取。
- 沒有安裝的 agent 會顯示 `not found on this computer; skipped`，之後裝了再到 Settings 按
  Install 即可。

### 11.2 在 Settings 查看、更新或移除

打開 AEP Agent → **Settings** → **Coding agents**。每個 agent 一張卡片，顯示：
是否找到、三個 skills 是否已安裝（installed / out of date / your own）、兩個 MCP server
是否已註冊。按 **Install / Update** 安裝或更新，按 **Remove** 移除 AEP 的項目。
改完請**重新開啟**該 agent（Claude Code 重開視窗、VS Code 重新載入）。

也可以用指令（在安裝資料夾）：

```powershell
.\.venv\Scripts\aep-host.exe assets --config host.json connect --for all --user           # 安裝／更新
.\.venv\Scripts\aep-host.exe assets --config host.json connect --for all --user --status  # 查看
.\.venv\Scripts\aep-host.exe assets --config host.json connect --for all --user --remove  # 移除
```

### 11.3 怎麼問

在任何資料夾開 Claude Code / Codex / Copilot，直接說：

- 「幫我做一個 AEP Workflow：每月把上傳的費用 CSV 合併成一份 Excel」
- 「幫我做一個 AEP Skill，讓 AEP Agent 會用 monthly-expense 這個 Workflow」
- 「用 AEP 知識庫查 CMX500 支援哪些 5G NR 頻段，附上出處」

agent 會先重述需求，**不清楚的地方會先問你**（例如 CSV 編碼、日期格式、結果要放哪、
會不會寄信）。回答後它會檢查、送出、測試；任何會改變東西的執行和**所有安裝**都要你在
Agent Web 按核准才會生效（Installed 頁面上方會列出等待核准的項目）。

注意：
- 查知識庫和執行 Workflow 需要 **Agent Web 正在執行**；沒開時 agent 會請你先開
  AEP Agent 捷徑。
- 新的 Skill 在 AEP Agent 重新啟動後才會被使用。

## 12. 安裝包附帶的 Skills

安裝和更新時，AEP 會一併裝好兩組 Skills。

### 12.1 開啟的：AEP 正在使用的 Skills

| Skill | 用途 |
|---|---|
| `company-agent/workflow-author` | 在對話中幫你寫 Workflow |
| `company-agent/knowledge-query`（1.12.0）、`engineering/knowledge-query`（1.0.1） | 查公司知識庫（RS_Knowledge），回答附出處 |
| `company-agent/market-alignment`、`company-agent/personal-proof` | 市場對照表、個人證明 |
| `engineering/coding` | 程式修改與執行 Python（`coding-change`、`run-python`） |
| `engineering/weekly-report`、`engineering/team-tickets` | 週報、Jira team tickets 預覽 |
| `engineering/rs-ncc-improvement-plan-skill` | NCC 改善計畫 |
| `engineering/sales-to-chipset`、`engineering/release-package-guide` | Sales-to-chipset 報表、release package |

它們會用到的 Workflows 也會一起裝好。需要外部設定（Jira、Excel、Outlook…）的，要等你在
`host.json` 設定好才會執行成功。

### 12.2 關閉的：Hermes skill pack（備用）

51 個從 Hermes agent 移植來的 skills（50 個 MIT 授權，加上僅供公司內部使用的
`business-cards`；作者與來源列在安裝包的 `hermes\NOTICE.md`），預設**全部關閉**，不會干擾 Agent 的選擇。例如：

- 文件：`docx`、`xlsx`、`powerpoint`、`pdf`、`document-to-action-items`、`meeting-action-items`
- 開發：`github`、`systematic-debugging`、`test-driven-development`、`requesting-code-review`、
  `simplify-code`、`spike`、`codebase-inspection`、`node-inspect-debugger`、`dogfood`
- 研究：`arxiv`、`grounded-citations`、`llm-wiki`、`competitor-news-monitor`、`blocked-page-recovery`
- 設計與創作：`ui-ux-pro-max`、`claude-design`、`design-md`、`popular-web-designs`、
  `architecture-diagram`、`humanizer`、`p5js`、`manim-video`…
- 其他：`business-cards`（名片辨識與公司分組圖）、`google-workspace`、`notion`、`airtable`、
  `box`、`obsidian`、`maps`、`email-inbox-triage`、`himalaya`、`claude-code`、`codex`…

完整清單在 Agent Web → **Capabilities** → **Skills**，篩選 **Switched off**，名稱以
`hermes/` 開頭。部分 skill 需要額外的指令或環境變數（例如 `NOTION_API_KEY`），說明寫在
skill 內容開頭的「AEP note」裡；`teams-meeting-pipeline` 和 `sdlc-review` 需要 Hermes 本身才能用。

### 12.3 打開或關閉

1. Agent Web → **Capabilities** → **Skills**，篩選 **Switched off**，點選要用的 skill。
2. 按 **Switch on**。Agent 在 Agent Web **重新啟動後**才會用它。
3. 這台電腦的 Claude Code / Copilot 已裝好 AEP 設定（第 11 節）時，同一個 skill 的原始資料夾
   會同時複製到 `%USERPROFILE%\.claude\skills\hermes-<名稱>` 和
   `%USERPROFILE%\.copilot\skills\hermes-<名稱>`，在 agent mode 裡也能用；重新開啟該 agent
   後生效。你自己已有同名資料夾時，AEP 不會動它。
4. 不用時按 **Switch off**：Agent 不再使用，coding agent 裡的複本也會被拿掉。

更新時，你打開、關掉或移除的 Skills 都會維持原狀；新版本多出來的 Hermes skills 一樣以
關閉狀態加入。

