# AEP Shared Platform Preview：安裝與測試起點

這是 **Shared Platform** 安裝包，不是 Personal Agent + Bridge。一般公司電腦不需安裝
這一包；它應安裝在提供團隊 Registry、Marketplace 與 Bridge API 的共享電腦。

## 安裝

需求：64-bit Windows 10/11 與 64-bit Python 3.12。解壓縮到短路徑，例如
`C:\aep-platform`，然後在可看到 `install.cmd` 的 PowerShell 執行：

```powershell
.\install.cmd -Administrator platform-admin
```

安裝位置：

```text
%LOCALAPPDATA%\AgenticEngineeringPlatform\shared-platform-preview-0.1.0
```

安裝器預設只監聽 `127.0.0.1`，不會立刻暴露到公司網路，也不會建立邀請。

## 驗證與啟動

```powershell
.\verify.cmd
.\start-platform.cmd
```

### Expected result

- `verify.cmd` 顯示 bundle source revision 與 `shared platform configuration: valid`。
- 啟動後終端顯示 Bridge API 與 Member Portal URL。
- 本機可以開啟 Member Portal；停止程序不會刪除 Registry database。

如果顯示 Windows socket `10048` 或 port occupied，代表 `control_port` 或
`member_port` 已有其他程序使用。先確認是否為正在運作的舊 Shared Platform；不要直接
停止不明程序。若不是既有平台，為兩個入口各選一個未使用且不同的 port，更新
`platform.json` 後重啟。

## 讓其他電腦連線前

編輯安裝目錄中的 `platform.json`：

1. 將 `listen_host` 設為這台共享電腦的固定 DNS 名稱或 IP。
2. 設定 `tls_certificate_path` 與 `tls_private_key_path`；非 loopback listener 沒有 TLS
   會被程式拒絕。自簽憑證即可，作法見下方「管理員 SOP」第 6 節。
3. 確認 `control_port` 與 `member_port` 的防火牆規則只允許預期網路。
4. 在 `invitations` 加入具期限的邀請，再啟動並安全交付產生的 invitation link。

詳細格式與目前 reference-process 限制請看 `README.md`。TLS private key、邀請連結、
Bridge token 與其他 secret 不可提交到 GitHub 或附在測試 evidence。

## Evidence

回報測試時請保留 artifact 名稱、workflow run URL、bundle revision、兩個實際 URL、
Member Portal 畫面，以及 sanitized 的錯誤碼。不得附上 invitation proof 或 token。

## 管理員 SOP：讓同事開始使用

同事端的操作寫在 Agent 安裝包的 `USER_GUIDE.zh-TW.md` 第 10 章；管理員的完整說明（分頁、邀請、
角色與群組、密碼重設、審核、Bridges、共同編輯與轉移、TLS）整理在同一份指南的第 15 章。
以下是管理員 SOP 摘要：

Member Portal 分成分頁（網址會記住目前分頁，例如 `#tab=review`，重新整理或上一頁都會留在原
分頁）。管理員登入後預設在 **Overview**，另外有 **Review queue**（分頁上的數字是等待審核的
數量）、**Registrations (Bridges)**、**All published assets**、**Members & invitations**；
一般同事只看到 **Marketplace**、**My published assets**、**My submissions**、
**Applications**。

### 0. 平台總覽（Overview）

**Overview** 一頁列出：已註冊電腦（啟用／停用）、成員（啟用／待接受邀請）、各類資產
（Skills、Workflows、Knowledge、Agent profiles、Extensions）的名稱數與版本數、
Applications，以及送審項目（等待／核准／退回／撤回）。點任一個方塊會開啟對應分頁；
**All published assets** 可依種類篩選，切換卡片或表格（表格可排序），卡片按名稱可看
該版本的完整內容（Workflow 的步驟、參數、權限；Skill 的說明、指令、關鍵字規則）。
這裡列出**所有**已發布的資產，不論你自己能不能使用。回覆中不會有任何 token、邀請碼或登入碼。

### 1. 發邀請（每位同事一次）

1. 以管理員帳號登入 Member Portal → **Members & invitations** 分頁 → **Invitations**。
2. **Account** 填同事電腦 `host.json` 裡 `device.registered_by` 的值（例如 `leo.chi`）。
   只能用英文字母、數字和 `. - _`，**不能用 email**；名稱不一致時，同事註冊電腦會被拒絕
   （`device_owner_mismatch`）。
3. **Role**：一般同事選 Member；要能審核的人選 Administrator。**Groups** 填團隊名稱（例如
   `engineering`），同團隊的人才看得到「只有我的團隊」的能力。之後要改角色或群組，在同一分頁
   的成員表按 **Role and groups**；變更會被記錄，最後一位管理員不能被改成 Member
   （`last_administrator`）。
4. 按 **Create invitation** → **Copy link**，用私訊交給同事。連結只能用一次；過期或用掉後
   可以再發一張，不用的可以按 **Revoke**。同事第一次打開邀請連結時會設定自己的密碼，之後用
   「帳號 + 密碼」登入，不需要再發邀請。
5. 一併告訴同事兩個網址：Member Portal URL 與 Bridge API URL。

### 1.1 密碼：重設連結與強制登出

Member Portal 的登入方式是**帳號 + 密碼**；邀請連結只用在第一次（同時設定密碼）。
**Members & invitations** 分頁的成員表有 **Password** 欄（Set / Not set，以及尚未使用的
重設連結期限），每一列有：

- **Password reset link**：同事忘記密碼時按這個，複製出現的連結用私訊交給他。連結只能用
  一次、預設 60 分鐘內有效（API 可設 1～1440 分鐘），再發一次會讓上一個連結失效。
  同事打開後設定新密碼即登入；他其他瀏覽器的登入會被撤銷（Personal Agent code 保留）。
  停用的帳號不能用重設連結。
- **Force sign-out**：電腦遺失、帳號外洩時按這個。該成員所有瀏覽器登入、所有 session，
  **連同 Personal Agent code** 立即失效；他的密碼不變，可以再用密碼登入（若密碼也可能外洩，
  接著發一個 Password reset link）。

規則：密碼至少 12 字元、不可包含帳號名稱或常見密碼；同一帳號錯 5 次鎖 15 分鐘，同一來源
位址錯 20 次鎖 15 分鐘（經由 SSH tunnel 時大家的來源都是 127.0.0.1，所以位址的上限較高）；
重啟平台會清除鎖定計數。所有登入失敗都只回 `authentication_failed`，不透露帳號是否存在。
平台只保存密碼的 scrypt 雜湊（`workspace\registry.sqlite` 的 `identity_passwords`），
任何回覆與紀錄都不含密碼。

唯一的管理員忘記密碼、又沒有其他還登入著的瀏覽器時：在 `platform.json` 的 `invitations`
加一張給**另一個**管理員帳號的啟動邀請，重啟後用它登入，再替原帳號發 Password reset link。

### 2. 審核同事發布的 Skill / Workflow

1. Member Portal → **Review queue** 分頁，預設只列出等待審核的項目（也可切到全部、已核准、已退回、已撤回）。
2. 按 **View** 看完整內容、要求的權限與風險，以及上一個已發布版本。
3. 按 **Approve and publish**（寫下你檢查了什麼）或 **Reject**（一定要寫原因，送出的人看得到）。
4. 核准後才會出現在其他人的 Library。目前設定允許管理員審核自己送出的項目
   （`platform.json` 的 `allow_self_review`，驗證完成後可改成 `false`）。

### 3. 調整誰能使用

Member Portal → **My published assets**，或管理員在 **All published assets** 分頁的任何資產 →
**Who can use it**：可改成「只有團隊」或「全公司」，也可以額外加指定的帳號或群組。
已發布的版本內容不會改變；收回權限不會移除別人已經安裝的版本。

要讓另一個帳號發布新版本：同一列按 **Owner and co-editors** → 加入 **co-editor**（帳號名稱）；
或用 **Transfer owner** 把擁有者轉給某人或某團隊（會先確認新擁有者）。每一列都會顯示
「May publish new versions」：擁有者、擁有團隊的成員與 co-editors，其他人發布會被拒絕
（`publisher_not_authorized`）。擁有者、擁有團隊成員與管理員都能調整這些設定。

### 4. 管理已註冊的電腦（Bridges）

Member Portal → **Registrations (Bridges)** 分頁列出所有已註冊的電腦、所屬帳號、token 到期日、
**Last seen**（該電腦最後一次呼叫 Bridge API 的時間與動作）與選取的能力數。電腦遺失或
同事離開時按 **Disable**，該電腦的 token 立即失效，也不能再自行註冊。

### 5. 啟動、更新與資料

- 啟動：`start-platform.cmd`。要開機自動啟動，見第 6 節的排程工作。重啟不會遺失帳號、
  已發布的能力、審核紀錄與已註冊的電腦，這些都存在 `workspace\registry.sqlite`。
- 每次重啟會產生新的 `invitation-links-*.json`，裡面是 `platform.json` 裡尚未使用的
  啟動邀請；**檔案內容是登入憑證，不要轉寄或提交到 Git**。
- 更新：用新版安裝包重新執行 `install.cmd`，`platform.json` 會保留。

### 6. 開放給公司網路（自簽憑證、防火牆、開機自動啟動）

預設只監聽本機（127.0.0.1），其他電腦連不到。以下以 `172.25.228.141`（電腦名稱
`OPENLAB01`）為例，換成你的 IP 與名稱。全部在**這台平台電腦**上、以執行平台的 Windows
帳號、在系統管理員 PowerShell 中操作。

**6.1 在這台電腦上產生自簽憑證**（私鑰不離開這台電腦）

用 Git for Windows 附帶的 `openssl`（`C:\Program Files\Git\usr\bin\openssl.exe`）：

```powershell
$Dir = "$env:LOCALAPPDATA\AgenticEngineeringPlatform\shared-platform-tls"
New-Item -ItemType Directory -Force $Dir | Out-Null
$Me = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
icacls $Dir /inheritance:r /grant:r "${Me}:(OI)(CI)F"      # 只有這個帳號能讀
@"
[req]
distinguished_name = dn
prompt = no
[dn]
CN = 172.25.228.141
O = AEP Shared Platform
[ext]
subjectAltName = IP:172.25.228.141,DNS:OPENLAB01,DNS:openlab01
basicConstraints = critical,CA:FALSE
keyUsage = critical,digitalSignature
extendedKeyUsage = serverAuth
subjectKeyIdentifier = hash
"@ | Set-Content -Encoding ascii "$Dir\ext.cnf"
& "C:\Program Files\Git\usr\bin\openssl.exe" req -x509 -newkey ec `
  -pkeyopt ec_paramgen_curve:prime256v1 -nodes -days 825 `
  -keyout "$Dir\platform-key.pem" -out "$Dir\platform-cert.pem" -config "$Dir\ext.cnf" -extensions ext
Remove-Item "$Dir\ext.cnf"
icacls "$Dir\platform-key.pem" /inheritance:r /grant:r "${Me}:F"
```

憑證放在安裝目錄**外面**，重新安裝或解除安裝都不會刪掉它。私鑰（`platform-key.pem`）
不要複製、寄送或提交到 Git；遺失或外洩時重新產生，並把新的指紋給所有同事。

**6.2 設定 `platform.json` 並取得指紋**

```json
"listen_host": "172.25.228.141",
"tls_certificate_path": "C:\\Users\\<帳號>\\AppData\\Local\\AgenticEngineeringPlatform\\shared-platform-tls\\platform-cert.pem",
"tls_private_key_path": "C:\\Users\\<帳號>\\AppData\\Local\\AgenticEngineeringPlatform\\shared-platform-tls\\platform-key.pem"
```

```powershell
& "$env:LOCALAPPDATA\AgenticEngineeringPlatform\shared-platform-preview-0.1.0\.venv\Scripts\aep-platform.exe" `
  certificate-fingerprint --config "$env:LOCALAPPDATA\AgenticEngineeringPlatform\shared-platform-preview-0.1.0\platform.json"
```

印出的 `SHA-256 fingerprint: 83:95:...` 就是要交給同事的指紋（`start-platform.cmd` 啟動時
也會印 `Certificate SHA-256: ...`）。指紋是公開資訊，但要用**可信的管道**給（私訊、團隊公告），
同事會拿它和 Agent Web 顯示的值比對。

**6.3 Windows 防火牆**

```powershell
New-NetFirewallRule -DisplayName "AEP Shared Platform" -Direction Inbound -Protocol TCP `
  -LocalPort 8775,8776 -Action Allow -Profile Domain,Private
```

把 `8775,8776` 換成 `platform.json` 的 `control_port`、`member_port`。只開放 Domain／Private
設定檔。若公司網路在這台電腦上是「無法辨識的網路」（設定檔為 Public，`Get-NetConnectionProfile`
可查），改成只對那張網卡開放，不要對所有 Public 網路開放：

```powershell
$Nic = (Get-NetIPAddress -AddressFamily IPv4 -IPAddress 172.25.228.141).InterfaceAlias
Set-NetFirewallRule -DisplayName "AEP Shared Platform" -Profile Domain,Private,Public -InterfaceAlias $Nic
```

平台只監聽 `listen_host` 這個位址，所以 Wi-Fi、VPN 等其他網卡本來就連不到。

**6.4 開機自動啟動（排程工作，失敗自動重啟）**

```powershell
$Bundle = "C:\aep-platform"   # 解壓縮安裝包的資料夾（有 start-platform.cmd）
$Action = New-ScheduledTaskAction -Execute "cmd.exe" `
  -Argument "/c `"`"$Bundle\start-platform.cmd`" >> `"$Bundle\platform.log`" 2>&1`""
$Trigger = New-ScheduledTaskTrigger -AtStartup
# 每 5 分鐘檢查一次：平台還在執行就不動（IgnoreNew），結束了就重新啟動。
$Trigger.Repetition = (New-ScheduledTaskTrigger -Once -At (Get-Date) `
  -RepetitionInterval (New-TimeSpan -Minutes 5)).Repetition
# 開機觸發的重複檢查要等下次開機才開始；這個觸發讓檢查從現在就開始。
$Watch = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
  -RepetitionInterval (New-TimeSpan -Minutes 5)
$Settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable `
  -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
  -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$Principal = New-ScheduledTaskPrincipal -UserId $Me -LogonType S4U -RunLevel Limited
Register-ScheduledTask -TaskName "AEP Shared Platform" -Action $Action -Trigger @($Trigger, $Watch) `
  -Settings $Settings -Principal $Principal
Start-ScheduledTask -TaskName "AEP Shared Platform"
```

`S4U` 讓工作在沒有人登入時也以這個帳號執行，不需要存密碼。紀錄寫在
`C:\aep-platform\platform.log`。**更新平台前**先 `Disable-ScheduledTask -TaskName "AEP Shared
Platform"`，停掉平台、重新安裝後再 `Enable-ScheduledTask` 和 `Start-ScheduledTask`，否則
5 分鐘檢查會在安裝途中把舊版啟動。

**6.5 交給同事**

- Member Portal：`https://172.25.228.141:8776`
- Bridge API：`https://172.25.228.141:8775`
- 憑證指紋（SHA-256）：6.2 印出的值

同事在 Agent Web **Settings → Shared platform** 填兩個網址，按 **Fetch & show fingerprint**，
比對指紋相同後按 **Trust this certificate**，再按 **Enroll this PC**（使用指南第 10 章）。
瀏覽器打開 Member Portal 時會警告「不安全／憑證無效」：比對憑證檢視器裡的 SHA-256 與你給的
指紋相同後再繼續，或匯入 Agent Web 下載的 `.cer`（指南 10.1.1 說明風險）。
