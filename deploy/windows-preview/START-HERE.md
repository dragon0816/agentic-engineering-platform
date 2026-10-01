# AEP Personal Agent + Bridge Windows Preview：安裝與測試起點

這是 **Personal Agent（含 Web GUI）+ Bridge** 安裝包，不是 Shared Platform。
公司電腦與測試電腦安裝這一包；提供 Registry／Marketplace 的共享電腦另用
`aep-shared-platform-windows-<完整 main commit SHA>` artifact。

本手冊與同一個安裝包一起產生。請勿使用其他版本的手冊測試這個安裝包。
更完整的整合、排程、DUT、Telegram 與進階設定請參考同一目錄的
`README.md`。

## 1. 下載正確的安裝包

在 GitHub **Actions → Platform verification** 的成功執行頁面，下載名稱為
`aep-windows-preview-<完整 main commit SHA>` 的 artifact。自動建立的
Deployment Validation Issue 也會列出正確的 workflow run 與 artifact 名稱。

GitHub 下載的是一層 artifact 壓縮檔，裡面可能還有
`aep-windows-preview-0.1.0-<短 SHA>.zip`。兩層都要解壓縮。為避免 Windows
路徑長度問題，最後請放在短路徑，例如 `C:\aep`。

## 2. 安裝

需求：64-bit Windows 10/11 與 64-bit Python 3.12。

在解壓縮後、可看到 `install.cmd` 的目錄開啟 PowerShell：

```powershell
.\install.cmd -Actor employee.id
```

請把 `employee.id` 換成你的平台使用者。Bridge ID 預設由電腦名稱產生，
一般不需要輸入。安裝位置固定為：

```text
%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0
```

## 3. 先驗證安裝

```powershell
.\verify.cmd

$InstallRoot = Join-Path $env:LOCALAPPDATA "AgenticEngineeringPlatform\preview-0.1.0"
& "$InstallRoot\.venv\Scripts\aep-host.exe" version
& "$InstallRoot\.venv\Scripts\aep-host.exe" doctor --config "$InstallRoot\host.json"
```

### Expected result

- `version` 顯示 `0.1.0`。
- `verify.cmd` 確認 bundle source revision 與安裝的 revision 一致。
- `doctor` 至少能讀取 host、workspace 與已安裝資產；未配置的外部整合應顯示
  `pending` 或具體 prerequisite，不應以設定解析錯誤中止。

## 4. 開啟 Personal Agent Web

```powershell
$InstallRoot = Join-Path $env:LOCALAPPDATA "AgenticEngineeringPlatform\preview-0.1.0"
& "$InstallRoot\.venv\Scripts\aep-host.exe" web --config "$InstallRoot\host.json" --open
```

終端會印出帶有暫時存取 token 的 loopback URL。請使用該 URL；不要把 URL 或
token 貼到 Issue、聊天或測試證據中。

第一次使用請開啟 **Settings**：

- Provider：`OpenAI-compatible Gateway`
- Alias：`company`
- Gateway URL：`http://127.0.0.1:4000/v1`
- Model name：Gateway 實際提供的 model id，必須明確填寫

如果 Gateway 需要憑證，只在頁面填 `SecretRef` 名稱與 Windows 環境變數名稱。
憑證值只放在環境變數，不能放進 `host.json`。儲存後依頁面提示重新啟動 Web。

## 5. 依序測試

### A. Ask：自然語言與指令提示

1. 打開 **Ask**。
2. 確認頁面顯示模型 readiness 與已安裝 Skill 提供的指令提示。
3. 輸入一段自然語言工作要求並送出。
4. 再點選一個指令提示，確認它只填入輸入框；按 **Send** 後才執行。

### Expected result

- 已配置 Gateway 時，Agent 以自然語言回覆，並保留 trace evidence。
- 命中固定指令時走 deterministic route，不需要模型重新猜測。
- 缺少模型、grant 或 prerequisite 時，頁面顯示具體的 needs-input/setup-required，
  不應假裝成功。

### B. Workflows：執行已安裝 Workflow

1. 打開 **Workflows**，選擇一個已安裝且 prerequisites/grants 都 ready 的項目。
2. 先查看輸入與 side-effect/approval 分類。
3. 執行安全的 preview 或 read-only 路徑。

### Expected result

- 執行目標包含完整 namespace、name 與 version。
- 成功結果含 run/trace evidence；缺少授權或 dependency 時明確拒絕。
- Publication 本身不會變成 execution permission。

### C. Knowledge：以已安裝 Wiki/Knowledge 回答

1. 確認 **Knowledge** 頁面列出已安裝並綁定 local Vault 的 Knowledge asset。
2. 問一個該 Knowledge 範圍內、可以由測試資料回答的問題。

### Expected result

- 回答引用可追溯的 Raw evidence/reference。
- 沒有 Knowledge manifest、Vault 或 grant 時顯示缺少的 prerequisite，不使用模型
  自行補造企業知識。

### D. Improve：建立改善或新能力草稿

1. 完成一段 Ask 對話後開啟 **Improve**。
2. 對一個已安裝的 Skill、Workflow 或 Knowledge exact version 建立改善草稿；或建立
   新 Skill/Workflow 提案。
3. 重新啟動 Web 後確認草稿仍可查看。

### Expected result

- 草稿保存對話摘要、預期/實際行為與 acceptance criteria。
- 草稿維持 local、draft、不可 publish，business approval 與 technical policy 分開。
- 儲存草稿不會自動執行、安裝、建立 GitHub Issue 或發佈到 shared platform。

### E. Shared platform 與擴充能力

1. 打開 **Shared platform**，確認頁面清楚顯示 connected 或 not configured。
2. 已配置平台連線時，先查看 catalog，再執行 synchronize；不要以 catalog 顯示取代
   本機 installed 狀態。
3. 回到 **Installed here**，分別查看 Skills、Workflows、Knowledge、Agent profiles 與
   Bridge Extensions。Applications 由 Marketplace 提供連結，但保有自己的程序與安裝
   生命週期。

### Expected result

- catalog 能顯示可取得的 exact version，synchronize 後才更新本機 installed inventory。
- selected/published、installed 與 authorized 是不同狀態；任一狀態不會暗示 execution
  permission。
- Bridge Extension 只有在套件驗證、技術核准與本機 activation gate 都成立時才啟用。
- Shared platform 無法連線時，已安裝且 `central_required=false` 的能力仍可依本機授權運作。

## 6. Evidence：回報時保留什麼

請記錄以下資訊，敏感值必須遮蔽：

- artifact 名稱、Platform verification run URL、bundle source revision
- Windows 版本、Python 3.12 版本、Bridge ID 與 actor
- `verify.cmd` 與 `doctor` 的結果
- 測試案例名稱、Expected result、Actual result
- request/run/trace ID 與頁面顯示的錯誤碼
- 必要的畫面截圖與本機 evidence 檔案路徑

請勿附上 API key、access token、Telegram token、完整 tokenized Web URL 或其他 secret
value。若問題是實作缺陷，使用上述 evidence 建立 Issue；環境 prerequisite 不完整時，
應標示為 blocked/setup-required，而不是功能 FAIL。
