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
   會被程式拒絕。
3. 確認 `control_port` 與 `member_port` 的防火牆規則只允許預期網路。
4. 在 `invitations` 加入具期限的邀請，再啟動並安全交付產生的 invitation link。

詳細格式與目前 reference-process 限制請看 `README.md`。TLS private key、邀請連結、
Bridge token 與其他 secret 不可提交到 GitHub 或附在測試 evidence。

## Evidence

回報測試時請保留 artifact 名稱、workflow run URL、bundle revision、兩個實際 URL、
Member Portal 畫面，以及 sanitized 的錯誤碼。不得附上 invitation proof 或 token。

## 管理員 SOP：讓同事開始使用

同事端的操作寫在 Agent 安裝包的 `INSTALL.zh-TW.md` 第 5 節。管理員要做的是：

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

- 啟動：`start-platform.cmd`（開機後不會自動啟動）。重啟不會遺失帳號、已發布的能力、
  審核紀錄與已註冊的電腦，這些都存在 `workspace\registry.sqlite`。
- 每次重啟會產生新的 `invitation-links-*.json`，裡面是 `platform.json` 裡尚未使用的
  啟動邀請；**檔案內容是登入憑證，不要轉寄或提交到 Git**。
- 更新：用新版安裝包重新執行 `install.cmd`，`platform.json` 會保留。

### 6. 開放給公司網路

預設只監聽本機（127.0.0.1），其他電腦連不到。開放時：

1. `platform.json` 的 `listen_host` 改成這台電腦的固定 IP 或 DNS 名稱；
2. 設定 `tls_certificate_path` 與 `tls_private_key_path`（非本機一律要求 HTTPS）；
3. Windows 防火牆開放 `control_port` 與 `member_port`；
4. 重啟後把新的兩個 `https://` 網址給同事。

使用自簽憑證時，同事的 Agent 需要信任該憑證（Agent 端的信任設定尚在開發中）。
