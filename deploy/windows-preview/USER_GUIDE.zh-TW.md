# AEP Agent 使用指南

這份指南說明 AEP Agent 的**每一個設定和功能**：在哪裡、填什麼、為什麼、出錯時怎麼辦。
安裝、更新、解除安裝請看同一資料夾的 `INSTALL.zh-TW.md`。

- 寫給：第一次使用 AEP 的工程師。
- 畫面上的英文標籤照原樣寫，例如 **Settings → LLM gateway → Test**，方便你對照畫面。
- 例子裡的帳號、網址、路徑都是假的（例如 `alex.wang`、`https://platform.example:8776`），
  請換成你自己的。
- **任何權杖、密碼、邀請連結、Personal Agent code 都不要貼進對話、文件、Jira 或聊天軟體。**

## 目錄

0. 快速開始
1. 設定 LLM gateway（最重要）
2. 語言模型設定（Natural-language model）
3. Agent Web 導覽
4. 對話與執行 Workflow
5. Capabilities：管理 Skill 與 Workflow
6. Knowledge：維護知識庫
7. Laya AI 決策加速
8. Telegram
9. Workflow 設定
10. 共享平台（Shared Platform）：給一般成員
11. Agent 模式（Agent mode）
12. AI 提案、人按套用
13. Coding agents 與安裝包附帶的 Skills
14. 排程（Schedules）
15. 管理員：Shared Platform 管理
16. 常見問題與錯誤代碼
17. 名詞解釋

---

## 0. 快速開始

裝好之後，照這張清單由上往下做。打勾的項目做完，就能正常使用。

- [ ] **開啟 Agent Web**：雙擊桌面的 **AEP Agent** 捷徑。還沒啟動時會先出現 **AEP Agent is starting…**
      頁面（轉圈和經過時間），約 10～30 秒後自動切換到 Agent Web。
      在同一個分頁按重新整理（F5）沒關係，頁面會回來。新開的分頁、書籤，或重開 AEP 之後，
      要再用捷徑打開：網址本身不能進入 Agent Web，這是為了不讓電腦上的其他人或網站使用你的 Agent。
- [ ] **確認語言模型能用**：左邊 **Settings** → **LLM gateway** 卡片顯示 `Running`，
      按 **Test** 看到 `✓ gpt-5.5: …`（✓ 開頭）。不是時看第 1 章。
- [ ] **問一句話試試**：左邊 **New session**，在下方輸入框打「你好，你能做什麼？」，按
      **Send**。
- [ ] （選用）**改 Agent 的名字和說話風格**：**Settings → Agent identity and speaking
      style**（第 3.3 節）。
- [ ] （團隊有共享平台時）**連上共享平台**：跟管理員拿邀請連結和兩個網址，照第 10 章做
      一次，之後就能一鍵安裝同事分享的 Skill / Workflow。
- [ ] （要用 Workflow 時）在 **Capabilities** 選那個 Workflow，把 **Settings on this
      computer** 的必填設定填好（第 9 章）。
- [ ] （選用）**Telegram**：想在手機上用時照第 8 章設定。
- [ ] （選用）**排程**：要每週自動跑的工作照第 14 章設定。
- [ ] （用 Claude Code / Codex / Copilot 寫程式的人）確認 **Settings → Coding agents** 卡片
      顯示已安裝（第 13 章）。

> 小提醒：Agent Web 網址列裡有一段 `token=...`，頁面打開後會自動拿掉。不要把含 token 的
> 網址傳給別人。

---

## 1. 設定 LLM gateway（最重要）

AEP Agent 要透過 **LLM gateway** 才能使用公司的語言模型（chatrs 上的 GPT 等）。
沒有它，Agent 無法回答任何一般對話。安裝程式已經替你裝好、設定好，並設成登入
Windows 時自動啟動；這一章說明它是什麼、怎麼確認它正常、出問題時怎麼處理。

### 1.1 它是什麼

- 一個只在這台電腦上聽 `127.0.0.1:4000` 的小程式（LiteLLM），把 Agent 的請求轉給
  公司的模型服務。別台電腦連不到它。Claude Code 也可以透過它使用公司模型。
- 程式裝在安裝資料夾的 `gateway-venv\`；設定、權杖檔和紀錄放在
  `%LOCALAPPDATA%\AgenticEngineeringPlatform\gateway\`，**更新和解除安裝都會保留**。
- **Settings → Natural-language model** 卡片上方會顯示
  「Uses the built-in gateway at 127.0.0.1:4000 (running).」，不需要再填任何網址或權杖。

### 1.2 Settings 上的 LLM gateway 卡片

| 畫面上的項目 | 意思 |
|---|---|
| 狀態 `Running` / `Starting…` / `Stopped` | 正在執行 / 正在啟動（開機後約 1～3 分鐘）/ 沒有執行 |
| `not started by AEP` / `run outside AEP` | 4000 埠上有一個不是 AEP 啟動的 gateway；AEP 只顯示狀態、可以測試，不會去停它 |
| Token `valid until YYYY-MM-DD HH:MM UTC (N days left)` | 公司權杖到期日，**不會顯示權杖本身**；顯示 `missing — press Refresh token` 或 `EXPIRED on …` 時請按 **Refresh token** |
| Models answering / Local key / Configuration / LiteLLM / Folder | 上次測試結果、本機金鑰是否存在、設定是否正確、LiteLLM 版本、gateway 資料夾 |
| **Start** | 啟動 gateway（只在 `Stopped` 時可按） |
| **Restart** | 重新啟動 AEP 自己啟動的 gateway |
| **Refresh token** | 用你的 Windows 網域登入立即換新權杖 |
| **Test** | 問預設模型一句話，成功顯示 `✓ gpt-5.5: …`，失敗顯示 `✗` 和錯誤代碼 |
| **Start the gateway when I sign in to Windows** | 勾選＝登入 Windows 時自動啟動（預設勾選） |

卡片上沒有 Stop 按鈕；要停止時用指令 `gateway stop`（1.5 節）。

### 1.3 自動啟動

- 登入 Windows 時自動啟動（工作排程器的「AEP LLM Gateway」，只對你自己的帳號，
  不需要系統管理員權限；工作排程器拒絕時改用你帳號的登入啟動項目）。
- 重開機後第一次啟動可能要 1～3 分鐘。這段時間 Agent 會回答
  「The LLM gateway is still starting」，稍等再問即可。
- gateway 停掉後**不會**自己一直重啟（權杖錯誤時一直重啟只會掩蓋原因）；請看下面的
  疑難排解。

### 1.4 權杖（token）

- 公司模型服務要一個約 28 天有效的權杖。gateway 用你的 **Windows 網域登入
  （Kerberos）** 自動換新：不需要也不會儲存密碼，不開瀏覽器。
- 權杖只存在 `%LOCALAPPDATA%\AgenticEngineeringPlatform\gateway\gateway.env`。
  **不要把這個檔案或權杖寄給任何人。**
- 換新需要：電腦在公司網域且已登入——在公司網路上，或連上 VPN 並有 Kerberos 票證
  （PowerShell 執行 `klist`，看得到 `krbtgt/` 開頭的票證）。
- 剩 7 天以內時，登入自動啟動會先換新。也可以手動按 **Refresh token**。在家沒有 VPN 時
  換不了，但舊權杖到期前照常可用。

### 1.5 用指令檢查

```powershell
$aep = "$env:LOCALAPPDATA\AgenticEngineeringPlatform\preview-0.1.0\.venv\Scripts\aep-host.exe"
& $aep gateway status    # 狀態、權杖到期日、LiteLLM 版本、自動啟動
& $aep gateway test      # 問預設模型一句話
```

| 指令 | 作用 |
|---|---|
| `& $aep gateway status` | 是否在執行、權杖到期日、LiteLLM 版本、自動啟動 |
| `& $aep gateway start` / `stop` / `restart` | 啟動 / 停止 / 重新啟動（只停 AEP 自己啟動的那一個） |
| `& $aep gateway test --model gpt-5.4` | 測試某個模型 |
| `& $aep gateway refresh-token --force` | 立即用網域登入換新權杖（換新後按 Restart） |
| `& $aep gateway autostart --on` / `--off` | 開啟 / 關閉登入時自動啟動 |
| `& $aep gateway init --force` | 依 `gateway.json` 重新產生 `litellm-config.yaml` |

這些指令都不會印出權杖或金鑰。不想用內建 gateway（例如團隊有別的模型服務）時，安裝和
更新加 `-NoGateway`，再照第 2 章填團隊提供的網址。

### 1.6 疑難排解

| 你看到的 | 原因 | 處理方式 |
|---|---|---|
| Agent 回答「The LLM gateway is not running」 | gateway 沒在執行 | **Settings → LLM gateway → Start**；仍停住時看 `gateway\logs\gateway.log` 最後幾行 |
| 「The LLM gateway is still starting」 | 剛開機，LiteLLM 還在載入 | 等 1～3 分鐘再問 |
| `401`、「the company token has probably expired」 | 權杖過期，或本機金鑰不一致 | **Refresh token** 後 **Restart**；仍是 401 時回報（不要貼出 `gateway.env` 或 `LITELLM_MASTER_KEY` 的值） |
| `405 Method Not Allowed` | 某個模型在 `litellm-config.yaml` 設成 `openai/` | 模型一律用 `hosted_vllm/`；或執行 `& $aep gateway init --force` |
| 回答串流到一半中斷，`gateway.log` 出現 `IndexError` | 公司服務送出 `choices` 為空的片段 | gateway 內建修正；換過 LiteLLM 版本後才出現時，回報 `gateway status` 顯示的版本 |
| `127.0.0.1:4000 is already served` / `not started by AEP` | 另一個程式已在用 4000 | 正常的保護：AEP 不會啟動第二個，也不會停掉別人的。要換埠號：`& $aep gateway init --port 4001 --force`，再把第 2 章的 **Gateway URL** 改成同一個埠號 |
| `No Kerberos ticket` | 沒有網域登入 | 連公司網路或 VPN；必要時登出再登入，用 `klist` 檢查 |
| `rejected the Windows ticket (401)` | 公司登入網站不在「近端內部網路」區域 | 請 IT 確認；`klist purge` 後登出再登入 |
| **Test** 按鈕是灰的 | gateway 不在 `Running` | 先 **Start**，等狀態變 `Running` |
| **Start / Restart / Refresh token** 是灰的 | 這台電腦的 gateway 設成「只顯示、不管理」（自己架的 gateway） | 用你自己的方式管理那個 gateway |
| 「公司的模型服務現在沒有回應（HTTP 503）」 | gateway 在跑，但公司那邊的模型服務沒有回應（例如維護中） | 不是你的設定問題；等一下按回答下方的 **重試**，一直這樣請通知管理員 |
| 「模型 3 分鐘內沒有回應（逾時）」 | 一次模型呼叫超過 `host.json` 的 `models.call_timeout_seconds`（預設 180 秒） | 按 **重試**；常常發生時，看上一列或 **Settings → LLM gateway → Test** |
| 重新整理後 **Send** 是灰的，下方寫「正在檢查可用的對話後端與模型…」 | 正在檢查 Codex、Claude Code、Copilot 的登入狀態與 gateway | 等它好（可能要一分鐘）；不要一直重新整理 |

---

## 2. 語言模型設定（Natural-language model）

位置：**Settings → Natural-language model**。用內建 gateway 的人**不需要改這裡**；
只有團隊要你接別的模型服務，或你想換模型時才改。

| 欄位 | 填什麼 | 為什麼 |
|---|---|---|
| **Provider** | `OpenAI-compatible Gateway`（公司 gateway）或 `Ollama on this computer`（在本機跑模型） | 決定用哪種協定連模型 |
| **Alias** | 預設 `company` | Agent 內部稱呼這個模型的名字；一般不用改 |
| **Gateway URL** | 內建 gateway：`http://127.0.0.1:4000/v1`；其他：團隊提供的網址 | 模型服務的位址。連到別台電腦時必須是 `https://` |
| **Models this Gateway serves** + **Reload available models** | 按按鈕從 gateway 讀模型清單，再從下拉選一個 | 免得打錯模型名稱 |
| **Model name served by the Gateway** | 例如 `gpt-5.5`；可以從上面選，也可以自己打 | 實際使用的模型 |
| **Declared model context capacity (tokens)** | 預設 `128000` | 描述模型能吃多長的內容；**不會**讓對話送出更多內容（那是 3.4 節的設定） |
| **SecretRef name (optional)** | 權杖的「名稱」，例如 `llm_gateway_token`；內建 gateway 是 `litellm_gateway` | 只是名字，不是權杖本身 |
| **Environment variable name (optional)** | 放權杖的 Windows 使用者環境變數名稱，例如 `AEP_LLM_TOKEN`；內建 gateway 是 `LITELLM_MASTER_KEY` | 權杖值放在這個環境變數裡，**這個頁面不收、也不存權杖值** |

按 **Save model settings**，會顯示 `Saved. Restart the Agent to use this model configuration.`：
關掉 Agent Web 再用捷徑打開，新設定才生效。之後下方會顯示
`Configured: company → gpt-5.5 at ...`。兩個權杖欄位要嘛都填、要嘛都空，只填一個會出現
`Settings were not saved: the request was not valid model settings`。

### 2.1 權杖要放在哪裡

1. 開始功能表搜尋「編輯您帳戶的環境變數」。
2. 在「使用者變數」按「新增」，名稱填你在 **Environment variable name** 填的名字，
   值貼上團隊給的權杖。
3. 關掉 Agent Web 後再用捷徑打開（環境變數只有新啟動的程式看得到）。

### 2.2 資料傳送核准（data approval）

卡片下方有一行：

- `Administrator approval: <核准編號> · Classes: UNCLASSIFIED`：這個 gateway 已經被核准
  可以傳送這些等級的資料。內建 gateway 預設已核准 `UNCLASSIFIED`。
- `No administrator data-transfer approval is recorded for this Gateway.`：還沒核准。
  核准是管理員寫在 `host.json` 的 `models.data_approval`，這個頁面不能改。

**注意**：只改 **Model name** 會保留核准；改 **Gateway URL**、**Provider** 或權杖對應，
核准會被清掉，要請管理員重新核准。

### 2.3 常見訊息

| 訊息 | 處理方式 |
|---|---|
| `No routing model is configured.` | 還沒設定模型；照上表填好並儲存 |
| `Settings are read-only in this launch mode.` | 這次啟動沒有帶設定檔；用桌面捷徑重新開啟 |
| `Credential value present: false` | 你填了環境變數名稱，但這個變數沒有值；照 2.1 設定後重開 |

---

## 3. Agent Web 導覽

Agent Web 是 Agent 的網頁介面。左邊是功能按鈕和對話清單，右邊是內容。

### 3.1 左邊的按鈕

| 按鈕 | 打開什麼 | 章節 |
|---|---|---|
| **New session** | 開一個新的對話 | 第 4 章 |
| **Capabilities** | 這台 Agent 已安裝的 Skill / Workflow / Knowledge，以及共享平台的 Library | 第 5 章 |
| **Settings** | 所有設定卡片 | 第 1、2、3.3、7、8、10、11、13 章 |
| **Schedules** | 排程（頁面標題 **Scheduled tasks**） | 第 14 章 |
| **Knowledge** | 知識庫維護的三個步驟 | 第 6 章 |
| **Tasks** | Agent 跑過或正在跑的背景工作，以及等待你按 Apply 的變更 | 3.5 節 |
| **Reviews** | Agent 每晚整理出的改善提案 | 6.6 節 |
| **記憶** | Agent 記得你的哪些事：待確認、偏好、筆記、資料、同步進度、紀錄 | 4.9 節 |

對話畫面沒有獨立按鈕：一打開就是對話畫面，點左邊任何一個 session 也會回到對話。

### 3.2 對話清單（Sessions）

- **Sessions** 旁邊的數字是對話總數；**Search sessions** 可以用標題搜尋。
- 每一列顯示標題、訊息數和使用的模型後端；正在執行時會多一個「執行中」。
- 刪除：滑到那一列按 🗑（會再確認一次，**刪除後無法復原**）。也可以在
  **Settings → Conversation context and saved sessions** 選 **Saved session** 後按
  **Delete selected session**。
- 對話標題由系統自動產生，目前**不能改名**。
- 不同 session 可以同時跑；同一個 session 的訊息會依序排隊（顯示「排隊中…」）。

### 3.3 Settings 頁的一般設定

Settings 頁由上往下的卡片：

| 卡片 | 用途 | 章節 |
|---|---|---|
| **Agent identity and speaking style** | Agent 名字、自我介紹、說話風格 | 本節 |
| **Avatar** | 左上角的頭像 | 本節 |
| **LLM gateway** | 語言模型的連線程式 | 第 1 章 |
| **Natural-language model** | 用哪個模型 | 第 2 章 |
| **Conversation context and saved sessions** | 每次送多少對話歷史給模型、刪除 session | 3.4 節 |
| **Telegram bot** | 用 Telegram 跟 Agent 對話 | 第 8 章 |
| **Shared platform** | 連上團隊共享平台 | 第 10 章 |
| **Laya decision acceleration** | Laya 快速決策 | 第 7 章 |
| **MCP servers** | 給 Agent 加外部工具 | 3.6 節 |
| **Coding agents** | Claude Code / Codex / Copilot 的 AEP 設定 | 第 13 章 |
| **Agent mode** | 讓 Claude Code / Copilot 在對話中動手做事 | 第 11 章 |
| **Agent profile** | 限縮 Agent 可用的 Skill、Knowledge 和模型 | 本節 |
| **Capability management** | 說明文字，沒有可以設定的欄位 | — |

**Agent identity and speaking style**

- **Agent name**：Agent 的名字（最多 80 字），顯示在左上角。
- **Self-introduction**：一句自我介紹（最多 500 字）。
- **soul.md**：說話風格，例如「用繁體中文、先講結論、條列重點」。
- 按 **Save Agent identity**，下一句對話就生效。這裡只影響說話方式，**不能**改變權限、
  工具、核准或事實。

**Avatar**：點一個圖案當你的頭像；Agent 工作時它會動。每個使用者各選各的。

**Agent profile**：列出可用的 profile，啟用後會限縮 Agent 可用的 Skill、Knowledge、
能力和模型要求。啟用後要重新開啟 Agent Web。不確定時不要動。

### 3.4 Conversation context and saved sessions

| 欄位 | 預設 / 範圍 | 意思 |
|---|---|---|
| **Recent messages, including the new question** | 1～40 | 每次送給模型的最近幾則訊息（含這次的問題） |
| **History text budget (UTF-8 bytes)** | 4000～48000 | 對話歷史最多送多少位元組 |
| **Tool calls per turn (1–150)** | 150 / 1～150 | 一則訊息最多可以呼叫幾次工具 |
| **Time limit per turn (minutes, 1–120)** | 30 / 1～120 | 一則訊息最多可以做多久 |

後兩項是「一則訊息最多做多少工作」。到上限時 Agent 會先停下來，說明原因，已做的步驟會
留在對話中，回覆「繼續」就接著做。Agent 用相同內容重複呼叫同一個工具時也會提早停下：
連續失敗 3 次，或中間沒有新動作卻重複超過 5 次。

按 **Save context limits** 立即生效。問題本身超過預算時，Agent 會退回讓你修改，
**不會偷偷截斷**。每個 session 會保存在這台電腦；不同 session 之間**不共用記憶**。

### 3.5 Tasks（背景工作）

- 列出 Workflow 和背景工作：Knowledge 的轉換（convert）、重新 ingest、測試、push、
  經驗回顧（experience review）、AI 提案。一般對話不列在這裡。
- 欄位：**Status**、**Task**、**Kind**、**Started**、**Took**、**Result**。狀態有
  running / done / failed / needs you / stopped / interrupted。
- 只保留最新 50 筆；執行中的會自己更新，也可以按 **Refresh**。
- 上方的 **Pending changes** 列出還沒按 **Apply** / **Cancel** 的 AI 提案（第 12 章）。

### 3.6 MCP servers（進階）

MCP server 可以給 Agent 加新工具（例如 GitHub、檔案系統）。**加入一個 server 等於核准它
所有的工具**，Agent 在對話、寫程式和 Workflow 裡都能用，請只加你信任的。

1. 展開 **Add or edit a server**。
2. **Name (lowercase, e.g. github)**：小寫英文和 `-`，最多 32 字。
3. **Connection**：
   - **Local command (stdio)**：填 **Command**（例如 `npx`）、**Arguments (one per line)**、
     **Working folder (optional)**、**Environment, not secret (NAME=value per line)**、
     **Secret environment (NAME=value per line; an empty value keeps the stored one)**。
   - **Remote URL (HTTP)**：填 **URL (starting with https or http)**、
     **Headers, not secret (Name: value per line)**、**Bearer token (empty keeps the stored one)**。
4. **Timeout per call (seconds)**（預設 60）、**Enabled**。
5. 按 **Save and connect**。

秘密值（Secret environment、Bearer token）只存在你的 Windows 使用者環境裡，存完不再顯示；
要保留舊值時留空即可。

---

## 4. 對話與執行 Workflow

### 4.1 基本操作

- 輸入框提示 **Ask naturally, or type / to choose a command**：直接用中文或英文問。
- **Enter** 送出，**Shift+Enter** 換行，或按 **Send**。
- **附加檔案**：按 📎，或把檔案拖進輸入框、貼上。支援圖片、PDF、CSV、HTML、TXT、JSON、
  YAML、MD、ZIP；每個檔案最多 25 MB，一則訊息最多 10 個。只附檔不打字時，會送出
  「請看附件。」
- 每段回答下方或按右鍵：
  - **回覆這段對話**：針對這一段追問；
  - **複製回覆**；
  - **評價**：👍 有幫助 / 👎 沒幫助 / ➖ 普通，可以補一句原因。**👎 和原因會進入每晚的
    經驗回顧**（6.6 節），幫 Agent 改進。
- **回答和你附加的檔案**（2026-10-20）：每個檔案都是一個可以點的小標籤（📎 檔名）。點下去
  右側會開啟檢視面板（手機寬度時是全螢幕），上面有檔名、**Preview / Code** 切換、
  「在瀏覽器開啟」、「下載」、關閉（Esc 也可以關）：
  - HTML：Preview 在隔離的框裡執行（不能連網路，也碰不到 Agent Web 的登入資訊）；Code 看原始碼。
  - Markdown（.md）：Preview 顯示排版後的內容；Code 看原文。
  - 圖片只有預覽；JSON、CSV、TXT、PY、PS1、YAML 等文字檔顯示含行號的內容（CSV 另有表格
    預覽），有「複製」按鈕；檔案很大時只顯示前 5000 行並註明。
  - 其他檔案只能下載或在瀏覽器開啟。
  目前會出現在回答上的是工具產生的檔案（例如組織圖）；`coding` 在工作資料夾產生的 HTML
  還不會自動附在回答上。
- 目前**沒有**中途停止回答的按鈕；不想等可以開新的 session。
- 等待回答時，原本的「working…」會換成即時進度：Harness 走到哪個階段（例如
  「① 規劃 ✓ ② 查資料（第 2 輪）… ③ 執行 ④ 驗收」）、最近用了哪些工具，以及
  「工具 12/150 · 3:05 / 30:00」（已用次數／上限 · 經過時間／時間上限）。只顯示名稱和
  數字，不顯示內容。Claude Code、Copilot 後端只顯示它要求使用的工具；Codex 只顯示經過時間。
  Telegram 會在同一則「⏳ Working on it…」訊息裡更新同樣的資訊：狀態一有變化（新階段、工具開始或結束、重試）就更新，同一個對話最多每秒更新一次，不會另外發新訊息。
- 一則訊息做到上限（工具次數、時間，或重複呼叫同一個工具）時會先停下來，回覆「繼續」
  就接著做；上限在 3.4 節設定。

### 4.2 選擇模型後端

對話上方左邊的下拉選單（**Conversation backend**，在「as … · on … · namespace …」那行左邊；
只在對話頁出現）：

| 選項 | 說明 |
|---|---|
| **Configured LLM Gateway** | 預設。走第 1、2 章的公司模型，**可以使用 AEP 的所有工具**（Workflow、Knowledge…） |
| **Claude Code** / **GitHub Copilot** / **Codex** | 用這台電腦上已登入的 CLI 回答 |
| **GitHub Copilot (agent, AEP tools)** | Copilot 加上 AEP 的知識庫與撰寫工具 |

- 選項後面出現 ` · sign in`：要先登入，按跳出視窗的 **Authenticate**，完成後按
  **Check again**。出現 ` · install`：這台電腦沒有裝那個 CLI。
- 選公司 gateway 以外的後端時，會跳出 **Start a PUBLIC conversation**：只能送**可以分享
  給外部服務**的內容；指令和本機工具在這種對話裡不能用。按 **Start PUBLIC session** 開新
  session。
- 想讓 Claude Code / Copilot 在對話裡讀寫檔案、執行指令，請開 Agent 模式（第 11 章）。
- gateway 不可用時會出現 **Open Settings**，帶你到 Settings。

### 4.2.1 選擇語言模型（LLM model）

用 **Configured LLM Gateway** 時，輸入框下方左邊的下拉選單列出 gateway 目前提供的模型
（Agent 用 Settings 裡的權杖對應讀 gateway 的模型清單，權杖不會送到網頁）：

- 選一個模型，**下一則訊息起**就用它回答，不用重新啟動 Agent。旁邊顯示
  `This conversation · from the next message`。
- 選擇記在這個對話，也會變成你的預設：之後還沒選過模型的對話會用它（顯示 `Your default`）。
  沒選過時用 Settings 的模型（後面標 `Settings default`）。
- 回答進行中選單會鎖住（`Locked while the answer runs`），答完再換。
- gateway 只提供一個模型時，只顯示模型名稱，不是選單；讀不到清單時只顯示 Settings 的模型，
  並寫 `Gateway list unavailable · Settings model`。
- 之前選的模型 gateway 不再提供時，選單顯示 `… · not served now`，那則訊息會被拒絕
  （`model_not_approved`），請改選別的模型。
- 換模型不改變資料規則：資料傳送核准（2.2 節）照樣先檢查，只能送到同一個已核准的 gateway。
- 這個對話裡做的所有事都用這個模型：一般回答、問 Knowledge 的回答、在對話中起草 Workflow 或
  Skill、讀名片等，都用同一個模型。
- 每則回答下方會用小字顯示 **模型：…**（例如 `模型：claude-sonnet-5`），可以確認是哪個模型回答的。
  指令（例如 `/help`）或執行表單沒有用到模型，就不會顯示。
- **Telegram**：每個 Telegram 對話各自記一個模型；沒選過就用你的預設，再沒有就用 Settings 的模型。
  傳 `/model` 看目前的模型和清單，傳 `/model 2` 或 `/model <模型名稱>` 換模型（同時變成你的預設）。
- 不屬於任何對話的工作一律用 Settings 的模型：排程（Schedules）、每晚的整理與經驗檢討、Knowledge
  頁上的問答、基準測試、轉換與 Skill 助手。
- Claude Code、Copilot、Codex 後端用它們自己的模型，這裡顯示 `Model: chosen by …`。
- Settings 第 2 章仍然決定 gateway 網址和預設模型。

### 4.3 斜線指令

輸入 `/` 會跳出指令清單：

| 指令 | 作用 |
|---|---|
| `/help` | 列出可用的指令 |
| `/run <名稱>` | 打開某個 Workflow 的執行表單，例如 `/run rs-wmt-package-release`；`/run 11` 用編號直接執行 |
| `/run workflow <ns/name@版本> {JSON}` | 用 JSON 參數執行一個指定版本的 Workflow（進階） |
| `/wiki-query <問題>` | 問某個已安裝的 Knowledge，回答附出處 |
| `/wiki-convert`、`/wiki-ingest`、`/wiki-lint` | 執行對應的 Knowledge Workflow（進階；一般請用 Knowledge 頁） |
| `/problem <說明>` | 把這段對話存成一份本機的問題回報草稿（不會自動開 Issue） |

已安裝的 Skill 也會把自己的指令放進清單；點一下只會**填進輸入框**，按 **Send** 才執行。

### 4.4 在對話中執行 Workflow（執行表單）

說「執行 rs-wmt-package-release」、「run rs-wmt-package-release」，或打 `/run <名稱>`，Agent 會在
回答下方畫出 **Run <Workflow 名稱>** 表單，不需要你一題一題打字。

1. 表單會先帶入你在句子裡已經說的值（例如 `chipsetId=kt326`，或直接說「43W」「2026-10-19」
   「dry run」「正式」、選項的名稱），並在表單上方寫「已從你的訊息帶入：…」，請先看一下對不對。
   只有說得很明確時才會帶入（例如同時說了 43W 和 44W 就不帶）。沒人填的選填欄位收在
   **其他選項（使用預設值）** 裡，需要時再展開。
2. 欄位名稱後面有 `*` 是必填；有 ` (needs confirmation)` 的欄位會再確認一次。
3. 下拉選單旁的 **Refresh list** 會重新讀取選項；「Pick or type」的欄位可以從清單選，
   也可以自己打。
4. **上傳欄位**：按選檔案後會立刻上傳，清單會列出已上傳的檔案；上傳中不能按 Run
   （訊息 `Wait for the upload to finish.`）。上傳的檔案存在
   `workspace\workflow-uploads\`，30 天後自動清掉；每個檔案最多 25 MB，一個欄位最多 20 個。
5. **Use last values: …**：Workflow 有「身分」類欄位（例如公司名稱、晶片代號）時，會出現
   這個按鈕，一按就填入你上次成功送出的值。這些值只存在這台電腦的
   `workspace\identity-presets.json`，**不會存任何像密碼的值**。
6. 按 **Run**。畫面顯示 `Running <名稱>… N s`，跑完結果會接在對話裡，Agent 看得到結果，
   你可以接著問。

其他情況：

- `This Workflow asks for nothing; press Run to start it.`：沒有參數，直接按 **Run**。
- `Not set yet: <設定名稱>…`，**Run** 是灰的：這個 Workflow 有「這台電腦的設定」還沒填
  （例如資料夾位置）。按 **Open <名稱> settings** 去填（第 9 章），填完回來就能執行。
- `Cannot run: …`：某個欄位的值不合格，照訊息修改。
- `The Workflow did not run: …`：被拒絕或失敗，訊息會說原因（常見代碼見第 16 章）。
- 只有最新一則回答的表單是展開的，舊的會收起來。
- 也可以從 **Capabilities → Workflows** 選 Workflow，在 **Run this Workflow** 填表後按
  **Run Workflow**。

### 4.5 會改變東西的動作要你確認

Agent **不會自己**安裝、核准或發布任何東西。需要你決定時，對話裡會出現卡片：

| 卡片 | 按鈕 | 章節 |
|---|---|---|
| 安裝請求 / 執行請求（Agent 在對話中做的 Workflow 草稿） | **核准** / **拒絕** | 第 5 章 |
| 變更提案（例如改 Laya 設定） | **Apply** / **Cancel**（30 分鐘後過期） | 第 12 章 |
| Agent 模式的權限請求 | **Allow** / **Allow for this conversation** / **Deny**（10 分鐘沒回答視為 Deny） | 第 11 章 |
| 寄信 | **Send** / **Keep as draft** / **Cancel** | 第 11 章 |

**想以後重複用：說「做成可以重複用的」**（2026-10-20）。說「做成可以重複用的」「做成
workflow」「以後都用這個」「建立一個工具」時，Agent 會起草一個 Workflow（程式是固定的一步，
每次會變的值變成表單欄位），對話裡出現安裝卡；你按 **Install** 才會安裝，之後在
Capabilities 和對話裡都能直接執行。只說「現在做一次」時，Agent 只跑一次、不起草。
Agent 沒有記憶規則的地方：你說「以後都不要問…」，它只在這次對話照做，要長期有效請讓它做成
Workflow 或提出設定變更，由你按下套用。

### 4.6 在 Telegram 執行

設定好 Telegram（第 8 章）後，傳 `/run <名稱>` 或「執行 <名稱>」（例如「幫我執行 43W SDE weekly
report」）。

- **你訊息裡已經講的值會直接用，不會再問**（例如 43W 會變成 `2026_43W`，用範例的格式；日期、
  選項名稱、「dry run／只看計畫」與「正式／寫入」也會帶入，只在說得很明確時）。上次填過的身分欄位
  也會沿用。
- **選填欄位不會一題一題問**，直接用預設值；只有**必填而且還沒有值**的欄位會一題一題問，每題都會
  等你回答（選項是按鈕，多選按完後按 **Done**；上傳欄位把檔案當「文件」傳送，傳完打 `/done`）。
- 最後出現**一張確認卡**，列出每個值和它的來源：「（從你的訊息）」、「（預設）」、「（上次的值）」，
  沒填的列在「未填（不使用）」。按 **確認執行** 才會執行；按 **修改** 選要改的欄位，或直接打字，
  例如「Dry run 改成否」、「From date 2026-10-19」、「week=2026_44W」；只打開關欄位的名稱（例如
  「執行方式」）會切換成另一個選擇。改完會再顯示卡片。`/cancel` 取消。
- **是非題用「每個選擇會做什麼」來顯示，不再是 Yes／No。** 例如 SDE weekly report 的「執行方式」兩個按鈕
  是「只看計畫（不寫入、不寄信）」和「正式執行（寫入週報、起草郵件）」，確認卡上寫「執行方式：正式執行
  （寫入週報、起草郵件）（預設）」。打字也可以用這些字：「只看計畫」、「改成正式執行」，是／否／yes／no
  也照樣可以。Agent Web 的執行表單同樣顯示成兩個選項（不是一個勾選框）。
- 只有按**目前這一題**的按鈕才算數；按到之前訊息上的按鈕，bot 會說「這個按鈕屬於較早的問題，沒有採用」
  並重問目前這一題。
- 對 bot 之前的問題按 **回覆（Reply）** 打值：流程還在，就改那一題；流程已經結束（例如 Agent Web
  重新啟動過、或超過 15 分鐘），bot 會說「那個流程已經結束，已用你的值重新開始」，並把那個值帶入。

缺少的 Workflow 設定只能在 Agent Web 填。

#### 再看一次執行的結果（圖、報表、郵件草稿）

- Workflow 執行完，**做出來的圖會直接傳到對話裡**（Telegram 是照片，Agent Web 顯示在結果下面）。
- 同一個對話裡，Agent **記得這次對話做過什麼**：哪個 Workflow、run id、成功與否、一行摘要，以及做出來的
  檔案（圖、試算表、文件）和郵件草稿，每個都有一個短編號（例如 `f1`）。這份清單不會因為聊了很多句就被
  擠掉。
- 之後直接說「把統計圖貼給我」、「剛剛那張圖再傳一次」、「把報表給我」，Agent 會把那個檔案附在回答裡
  （Telegram：圖片用照片、其他用文件；Agent Web：用對話裡的檔案檢視器打開）。**它不會再問你檔案路徑。**
- 只能附**這個對話、你自己**做出來的檔案；別的對話、別人的檔案、或任意路徑都會被拒絕。郵件草稿在
  Outlook 裡，不能當附件傳，但 Agent 會告訴你主旨。
- Telegram 傳 `/new` 開始新對話時，這份清單也會清空。

#### 結果摘要

- 每次 Workflow 跑完（或 Agent 用了好幾個工具完成一件事），回答最後會多一段 **「結果摘要」**：任務、
  成功與否、重點數字、產出（編號與檔名）、後續要做的事（例如「郵件草稿已存在 Outlook，尚未寄出」）。
- 之後在同一個對話問「剛剛算了幾項？」、「剛剛的圖」，Agent 會用這些摘要回答；Agent Web 重新啟動後也還在。
- 摘要存在這台電腦，**預設保留 30 天**，每晚自動刪除過期的。天數在「記憶」頁的 **紀錄** 分頁 →
  「任務摘要」改，這裡也能看最近的摘要、刪除或存成筆記。
- 想長期留下來：按摘要下面的 **存成筆記**（Agent Web 是「結果摘要存成筆記」；Telegram 按按鈕或回覆
  「存成筆記」）。不按就不會存成筆記。

### 4.7 名片與組織圖

安裝後預設就開著（Capabilities 裡的 **engineering/business-cards**）。名片資料只存在這台電腦、
只屬於你自己（`<workspace>\business-cards\`），不會分享給其他成員，也不會送到外部模型；
讀照片和簽名檔都只經過公司內部的 LLM gateway。

- **存名片（最常用：Telegram）**：在 Telegram 直接把名片照片傳給 bot，不用打字也可以；一次選
  多張照片（相簿）會一張一張存。以「檔案」方式傳的 JPG／PNG 也可以（iPhone 的 HEIC 檔請改用一般
  照片傳送）。在 Agent Web 則在 Gateway 對話按迴紋針附上照片，說「幫我存這張名片」。Agent 會列出讀到的公司、姓名、事業群／處／部門、職稱、電話、
  分機、手機、傳真、Email，**只問它不確定的欄位**。回覆第一句會說是新增還是對到既有的人，例如
  「已對到既有聯絡人 王小明（範例科技），依名片圖片比對。」，接著才講變化，例如
  「上次是研發部經理，現在是協理」；每次掃描都留紀錄。電話、傳真、手機只差在空格、橫線、括號或
  +886 的寫法時不算變更，也不會說有更新。名片上沒印英文名就不會存英文名；「博士」
  「Dr.」這類學位另外存，不會混進職稱；統一編號存在自己的欄位（名片上有印就會存，即使印在地址
  旁邊）。同一張照片再傳一次，或同名同公司但 Email 讀得不一樣，都算同一個人：不會多出一筆，
  會保留原本的 Email、把它標成「需確認」，並告訴你兩個 Email 不同，請你說哪個對。只有同名、
  同公司，但 Email 和部門（或處）都不同，才會當成另一個人。再掃一次讀得比較短（例如少了
  「事業群」或「I」）不會蓋掉原本比較完整的值。回覆裡的欄位都用中文名稱（英文名、統一編號…），
  問你某個欄位時會先講目前存的值。
- **確認欄位**：只要有一次掃描對某個欄位沒把握，它就一直標成「需確認」（組織圖上也會標
  「需確認：Email」），直到你確認或改正。確認就直接說「email 正確」；改正就說正確的值；存錯
  而應該留空的欄位（例如名片上沒有的英文名）就說「把范○○的英文名刪掉」。都會記在歷史裡，說
  「復原」可以撤回。
- **兩個值不同時**（2026-10-20 起）：你自己改過或確認過的值，只有**新證據**會動它：
  **新的名片**（這個人從沒掃過的名片照片），或**寄出日期比你那次修改晚**的信件簽名檔。同一張名片
  再掃一次、沒有照片的名片、比較舊的信，都**不會**改、也不會再問你（你已經看過並改正過）。
  新證據裡的**職稱、部門、處、事業群、學位、電話／分機／手機／傳真、地址**會**直接更新**
  （「換部門或換職位，就修改那一筆資料」），回覆照樣說「上次是…，現在是…」，說「復原」可以撤回。
  **Email** 是例外：新名片或新信讀到不一樣的 Email 不會覆蓋，會保留原本的、標成「需確認」，並告訴你
  兩個值，例如「這次讀到的 Email（b@…）和名片夾裡的（a@…）不同」（其他欄位如姓名也一樣）。說「王小明的 email 正確」就保留名片夾裡的值；說另一個值或
  「用新的」就改成這次讀到的值。兩種都會記在歷史裡（保留是「確認」、改用是「欄位變更」），
  說「復原」可以撤回。想看還有哪些沒決定，就說「有哪些待確認？」。
- **改資料**：直接說「王小明的手機是 0912-…」。你自己改的值，只有新的名片或較新的信才會更新
  （見上一點）；舊名片重掃、舊信不會蓋掉。更新前那些還在「待確認」、其實來自舊名片重掃或舊信的項目，
  升級後第一次使用時會自動關掉一次（記在歷史裡，說「復原」可以重新打開）。
- **歷史**：說「王小明的歷史」。狀態寫「在職／已離職」，來源寫「名片／郵件簽名檔／使用者」，
  時間是台灣時間（例如 2026-10-20 14:03）。變更編號只在你要復原某一筆時才會出現，平常只會說
  「可以說『復原』撤回」。
- **組織圖**：說「範例公司的組織圖」，公司可以用簡稱或網域說（例如「WNC」「啟碁」都找得到
  啟碁科技）。每個人的框寫姓名和學位（例如「王則閔 博士」）、職稱、電話＃分機、手機；說明裡
  也會列出還有哪些欄位「需確認」。對話裡會出現 PNG 圖和說明表格：框代表事業群 → 處 →
  部門，框內依職稱高低排序；**只有畫出來的線才是回報關係**，實線有證據（簽名檔、郵件、你告訴
  它的），虛線是依職稱推測的。沒有實線時，這張圖只是分組，不是回報關係圖。Telegram 會在
  簡短的文字回覆後傳組織圖照片（附一句說明），再附上完整說明檔（.md）。
- **組織圖會先整理新信**（2026-10-20）：問「WNC 組織圖」時，Agent 會先讀這家公司**上次整理之後
  的新信**（網域取自名片夾裡這家公司的人的 Email 和網站，例如 wnc.com.tw），再畫圖。新找到的人
  **不會自動存**：會先列成候選（s1、s2…），你說「都存進去」或「存 s1」它才存，存好會重畫一次組織圖；
  在你確認之前，組織圖只畫已經存的人。回覆會說這次讀了哪段範圍，例如「從 10/19 之後的新信：
  掃描 3 封，…」或第一次的「首次整理（收件匣 180 天內）：…」，所以第二次問同一家公司的組織圖
  只會讀新信，很快。名片夾裡這家公司的人都沒有公司 Email 或網站、或 Outlook 沒開時，會照樣用已存
  的資料畫圖，並告訴你這次沒有先整理新信、原因是什麼。
- **互動式（HTML）組織圖**（2026-10-20）：說「用 HTML 互動式呈現範例公司的組織圖」，或提到
  「互動式」「可搜尋」「樹狀」，Agent 會產生一個 HTML 檔（要圖片也要 HTML 就說「兩種都要」）。
  檔案完全獨立、不連網路，任何瀏覽器都能開。裡面有：**樹狀**（公司 → 事業群 → 處 → 部門 →
  人，可收合；有回報關係時另列回報樹，實線有證據、虛線是推論）、**分組**（和 PNG 一樣的框）、
  **搜尋**（姓名、英文名、職稱、部門、Email），點搜尋結果或任何一個人會打開**名片卡**：姓名
  和學位、公司、事業群／處／部門、職稱、電話＃分機、手機、傳真、Email、在職／已離職、需確認的
  欄位、來源（名片／郵件簽名檔／使用者）和日期、回報關係與依據，以及你連到這個人的**相關筆記**
  （見 4.8）。「顯示已離職」可以切換（預設
  不顯示，以灰色呈現）。在 Agent Web 會**直接顯示在回答裡**（可拉高、「放大」、「在面板開啟」、
  「在瀏覽器開啟」）；在 Telegram 會收到 .html 檔，下載後用瀏覽器開啟。
- **回報關係**：說「李大華向王小明報告」，Agent 會記成「使用者告知」的實線。
- **離職**：只有你說了才會記（記錄的是你的帳號和管道，例如 Telegram），例如「陳美已經離職了」。之後的組織圖不畫她（要看可說
  「包含離職的人」，會以灰色顯示）。說錯了就說「復原」，或說「陳美還在」。
- **從簽名檔整理**：說「從 example.com 的信件簽名檔整理聯絡人」。只會讀 Settings → Agent
  mode 設定的信件範圍（資料夾、天數），只讀那個網域寄來的信，只把簽名檔那幾行送給內部模型；
  它先列出候選名單（每位有編號，例如 s1、s2），你說「都存進去」或「存 s1 和 s3」它就直接存，
  不會再讀一次信；候選名單一小時內有效，過期了請再整理一次。信件內文不會被保存。它會說掃了
  幾封、幾封有簽名檔、幾封沒有，例如「掃描 5 封，1 封有簽名檔，4 封沒有簽名檔。」（同一位寄件人
  較舊的信不會再讀，也會算出來）。有幾封信讀不到時只會略過那幾封，並告訴
  你原因，例如「讀信失敗：1 封信無法讀取（message_unknown），已略過；其餘 3 封已處理」；
  讀不到的信下次整理時會再試。
- **只讀新信、重新整理**：每家公司（網域）各自記得整理到哪一天，下次只讀之後的新信；已經存過
  或上次已經列過的信不會再列一次（回覆會說「N 封先前已整理過，略過」）。讀信範圍仍以 Settings 的
  設定為準，只會更小、不會超過。想從頭整理一次，就說「**重新整理 WNC 的簽名檔**」（公司或網域都
  可以），會重讀設定範圍內的全部信；上次沒存的人會再列出來。系統的簽名檔擷取規則更新後，第一次
  整理會自動重讀全部範圍並說明「簽名檔擷取規則已更新，這次重新整理全部範圍內的信」，只會列出
  讀到新內容的人。整理進度每個人各自一份，其他成員看不到。
- **舊的 Hermes 名片**：如果以前用過 Hermes 的 business-cards（`~/.business-cards/cards.db`），
  說「匯入舊名片」或執行 `aep-host cards import --config <host.json>`，可以重複執行，不會重複匯入。

### 4.8 偏好與筆記（Agent 記得你說過的事）

Agent 不會自己記住規則或筆記；**一定要你按一下**才會保存，存在這台電腦上你自己的記憶庫裡，其他成員看不到。

- **偏好**：你在對話中說一條以後都適用的規則，例如「執行時不需要問是否包含在職人員」，Agent 會照做，
  並在回答下面跳一張卡片「要把這條記成『名片／組織圖』的偏好嗎？」。按「**存成偏好**」才會保存；
  按「不用」就只用在這次。存好之後，每次用到那個 Skill（例如名片與組織圖）Agent 都會照這條做，不再問你。
  如果新的這條和以前存的相反（例如以前存了「不需要問」，現在說「要問」），按下存的時候會先列出兩條請你選：
  「取代舊的」、「兩條都留」或「不用」。Telegram 也會出現同樣的卡片和按鈕。
- **筆記**：每則回答右上角的工具列有 📝「**存成筆記**」（滑鼠移過去或在回答上按右鍵就看得到），按一下就把整則回答存成筆記；
  只想存一段，就用滑鼠**選取那段文字**，旁邊會出現「**存選取內容**」。存好後會顯示「已存成筆記（n-…）」，
  旁邊的「復原」可以撤回。Agent 覺得某個結論值得記，也可能跳一張「要存成筆記嗎？」卡片（每段對話最多一次），
  一樣要你按「存成筆記」才會存。
- **查筆記**：筆記不會自動影響回答。你問「**我之前有記過什麼關於 WNC 的？**」、「查一下我的筆記」這類話時，
  Agent 才會去查，回答會標出用了哪一則，例如「[筆記 n-1a2b3c4d5e]」。名片與組織圖功能開著時，它也可以查連到聯絡人的筆記；
  HTML 組織圖的名片卡會列出連到這個人的「相關筆記」。
- **管理**：左邊的「**記憶**」頁可以檢視、修改、刪除所有偏好和筆記（見 4.9 節）；剛存錯也可以在存好的訊息旁按「復原」。

### 4.9 「記憶」頁：Agent 記得你的哪些事

左邊按「**記憶**」。這一頁只有你自己看得到（每位成員各自一份），Agent 沒有任何工具能讀或改這一頁；你在這裡做的每個變更都記成「<你> via web」，大多可以按上方訊息旁的「**復原**」撤回。會刪掉東西的動作都會先問你。平常在對話中就能處理這些事，這一頁是偶爾檢查用。

上方有六個分頁，旁邊的數字是筆數：

| 分頁 | 內容 | 可以做什麼 |
|---|---|---|
| **待確認** | 自動讀到的值和存著的不一樣（例如新名片上的 Email 和你確認過的不同），列出存著的、新讀到的、證據（名片或簽名檔、日期） | 「**保留原值**」（確認存著的是對的）、「**改用新值**」、「開啟該聯絡人」 |
| **偏好** | 存過的規則，依 Skill 分組；誰在何時存的、「來源對話」、「用過 N 次」 | 「修改」（會先檢查是否和同一個 Skill 的其他偏好矛盾，矛盾時讓你選「取代舊的」或「兩條都留」）、「刪除」 |
| **筆記** | 所有筆記，可搜尋、依標籤或關聯的聯絡人篩選 | 「修改」（Markdown）、「加標籤」、標籤旁的 × 移除、「連結聯絡人」、聯絡人旁的 × 取消連結、「刪除」、勾選後「匯出選取（Markdown）」、「開啟原本的對話」 |
| **資料** | 每個記憶空間一列：由哪個 Skill 管理（已開啟／已關閉／內建）、種類、敏感度、保留期限、筆數、最後更新。管理的 Skill 已不在這台電腦時標「**無主**」 | 聯絡人與組織：「開啟聯絡人」可搜尋、依在職／已離職篩選、看每個人的「歷史」。組織圖仍在對話中說「<公司> 組織圖」 |
| **同步進度** | 每個來源整理到哪裡（例如 `mail:Inbox` 的 `wnc.com.tw` 讀到 10/19）、擷取版本、誰在何時更新 | 「**重新整理**」（先問你；下次整理從頭讀範圍內的信）、「**復原上次重設**」 |
| **紀錄** | 對話（保留到你刪除，每段最多 100 則訊息）、執行紀錄（30 天或 500 MB，固定）、經驗回顧案例的保留天數（可改，和 Reviews 頁同一個設定）、各記憶空間的保留期限（目前只能看） | 每個空間「**匯出 JSON**」；「**刪除資料…**」要輸入空間名稱（例如 `contacts/org`）才會刪，**不能復原**，只留一筆刪除紀錄（時間、筆數，沒有內容） |

- 刪除「聯絡人與組織」只清記憶資料庫裡的資料；舊版的 `cards.db` 和它的備份（在 `business-cards\<你>\`）不會被刪，需要的話自己刪掉。
- 「改用新值」「保留原值」和在對話中說「用新的」「Email 正確」是同一件事，名片的歷史會記下來，可以復原。

### 4.10 「為什麼？」與記憶健康檢查

**「為什麼？」**：回答用到你的偏好或記憶時，回答下方會有一個小小的「**為什麼？**」。按一下列出這則回答用到的：

- **偏好**：這一輪套用了哪幾條你存的偏好（例如「組織圖不用問是否含離職」）；
- **聯絡人**：名片／組織圖的工具讀到或改到的人；
- **筆記**：回答引用的筆記（`[筆記 n-…]`）；
- **整理進度**：這次整理簽名檔前進的網域（例如 `wnc.com.tw`）。

每一項旁邊有「**到記憶頁修改或刪除**」（整理進度是「到同步進度」），會開啟「記憶」頁並標出那一項；覺得哪條偏好造成奇怪的行為，就在那裡修改或刪除。已經刪掉的項目會標「（已刪除）」。只記「用了哪一項」（編號），不另存內容。

在 **Telegram** 傳 **`/why`**，會回覆上一則回答用到的偏好與記憶；要修改請到 Agent Web 的「記憶」頁。

**記憶健康檢查**：每天凌晨（和經驗回顧一起，02:00 之後）自動檢查一次，也可以在「記憶」→「待確認」上方按「**立即檢查**」。它**只找問題、不會自己改任何資料**；找到的項目以「健康檢查：…」標籤放在「待確認」，每一項都要你按了才會處理：

| 類型 | 什麼時候出現 | 可以按 |
|---|---|---|
| 可能重複 | 兩位聯絡人 Email 相同，或同公司同名但 Email 或部門不同（所以沒有自動合併） | 「**合併（保留第 1 筆）**」（空白的欄位用第 2 筆補上、匯報線一起移過來，**可以復原**）、「不是同一人」（之後不再問）、開啟第 1／2 筆 |
| 很久沒出現 | 在職的聯絡人 12 個月（可改）沒有任何新的名片、簽名檔或你的確認：「<姓名> 是否仍在職？」 | 「**仍在職**」（記下你的確認，之後 12 個月不再問）、「**已離職**」（可以復原） |
| 偏好可能矛盾 | 同一個 Skill 有兩條以上的偏好時，用內部模型問一次是否有互相衝突的（存的時候的檢查沒抓到的那種） | 「停用第 1 條」「停用第 2 條」（都可以復原）、「兩條都留」 |
| 很久沒用的偏好 | 一條偏好 90 天（可改）沒有被任何回答用到 | 「刪除」（可以復原）、「保留」 |
| 無主的資料 | 記憶空間的管理 Skill 已不在這台電腦 | 「保留」，或「到紀錄匯出或刪除」 |
| 整理進度停住 | 某個來源 30 天沒有前進 | 「知道了」、「到同步進度」 |

- 設定在「記憶」→「**紀錄**」→「健康檢查」：每晚檢查開／關（預設開）、聯絡人幾個月沒出現就問（0 = 依空間的規則，目前 12 個月）、偏好幾天沒用就提醒（預設 90 天）。關閉後「立即檢查」也不能按，也不會呼叫模型。
- 沒有可用的內部模型時，矛盾檢查會略過（其他項目照樣檢查）。每位成員各自檢查、各自的結果；夜間報告（Reviews 頁的 review 報告）只寫各類的筆數，不寫內容。

### 4.11 交給專家子代理（多代理委派，預設關閉）

開啟後，Agent 在一個回合裡可以把**一件範圍明確的小工作**交給另一個「專家」Agent profile
（子代理），拿回結構化的結果再繼續回答你。Agent 自己仍然對答案負責；子代理只是它的工具
（`agent__delegate`）。

**怎麼開**（預設關閉，關閉時和以前完全一樣）：

1. 在 `host.json` 加上 `"multi_agent": {"enabled": true}`，然後重新啟動 Agent Web
   （重新啟動前先確認沒有進行中的工作，見 Tasks 與 `/api/activity`）。
2. 把專家 profile 放到 `<workspace>\assets\agents\<namespace>__<name>__<version>.json`。
   安裝包附了一個**關閉中**的範例：`agents/examples/knowledge-researcher.json`（只讀的知識研究員）。
   它的 `knowledge` 是空的：請填入你要讓它讀的知識庫（Knowledge vault）的確切名稱與版本，
   否則它拿不到任何知識庫工具（缺資訊時一律不給，不會自己放寬）。
3. 有 Shared Platform 授權的電腦：專家 profile、它用到的 Skill 與 Capability 都要先選取；
   作用中的 profile 可以在 `may_delegate_to` 列出專家（新版範例 `agents/engineering-0.2.0.json`）。
   沒有平台授權的個人電腦（owner mode）：已安裝、`published` 的 profile 就能當專家。

**怎麼用**：

- 作用中的 profile 在 `may_delegate_to` 列出的專家，Agent 會自己判斷要不要交給它（看 profile 的
  說明與 `selector_hint`）。
- 其他已安裝的專家，**要你在訊息裡說出它的名字**才會用，例如：「請用 knowledge-researcher
  查一下 Wi-Fi 7 的 MLO 規格重點」。
- 結果出現在 Agent 的回答裡；子代理的檔案與 Workflow 執行會記在**這個對話**的「產出」清單，
  之後可以用編號請 Agent 附上（`session__attach_file`）。

**它不會做的事**（規則）：

- 子代理**看不到這段對話**：只拿到 Agent 寫給它的任務說明，和 Agent 指定的這個對話的產出。
- 子代理**不會直接問你問題**：缺資訊時它回報「需要什麼」，由 Agent 問你一個問題。
- 子代理只能用**你本來就能用、而且 profile 允許**的工具，兩者的交集；不會因為 profile 而多出權限。
  畫面操作（瀏覽器、桌面）、MCP、表單、記憶、提案卡片等工具不會交給子代理。
- 會改變東西的動作**一樣要你按核准**（同 4.5），核准按鈕出現在這個對話。
- 同一回合裡，同一個寫入動作**最多執行一次**（子代理重做也一樣）。
- 一回合最多 **3 個**子代理、子代理不能再交給別的子代理；每個子代理有自己的工具次數、輪數與
  時間上限（profile 的 `max_tool_calls`、`max_turns`、`time_limit_s`），時間到就停，回報
  `delegation_time_limit`。目前**沒有「取消」按鈕**。
- 只讀的子代理（全部工具都只讀）在同一個回覆裡可以**同時跑**（最多 3 個）；有寫入能力的子代理
  一次只跑一個。
- 子代理的回答也經過 Host 檢查：沒有工具紀錄卻說「已完成」會被標註，Agent 的回答下方會出現
  「Host 註記：…未通過 Host 檢查」，不會被改寫成通過。
- 子代理用的是這個對話選的語言模型（同一個資料傳送核准）。**Claude Code / Codex / Copilot 後端
  的對話不能委派**。

**看得到什麼**：Agent Web 的進行中工作會標出正在跑的子代理數（`/api/activity` 的 `delegations`）；
遙測（Telemetry）每個子代理是一個 `agent_delegation` run，連到這一回合，只記次數與 token 數，
不記內容。

### 4.12 多 Agent 委派：開關、畫面與上限

這一節說明怎麼開「多 Agent 委派」，以及開了之後在 Agent Web 和 Telegram 會看到什麼。委派本身的規則
（誰能當專家、子代理看得到什麼）見上一節 4.11。

**怎麼開**

1. Agent Web → **Settings** → 「**多 Agent 委派**」卡片，勾「允許委派給子代理」。預設關閉。
2. 卡片會寫「已儲存為開啟；重新啟動 Agent Web 後生效」：設定存在 `host.json` 的
   `multi_agent.enabled`，**要重新啟動才生效**。重新啟動前先確認沒有進行中的工作（Tasks 頁或
   `/api/activity`），重新啟動會中斷正在跑的工作。
3. 想關掉：取消勾選，同樣重新啟動後生效。關閉時和沒有這個功能時完全一樣。
4. 這次啟動沒有 `host.json` 可寫時（例如唯讀的啟動方式），開關是灰的，卡片會說明。

**在 Agent Web 看到什麼**

- 回合進行中，原本的進度框（「工具 n/150 · 時間」）下方，**每個子代理一行**：profile 名稱、
  任務說明的前 60 個字、狀態（執行中／完成／需要資訊／等待確認／失敗）、它自己用了幾次工具、
  花了多久，只讀的子代理標「只讀」。同時跑的只讀子代理**並排**顯示；手機寬度時上下排列。
  最上面一行會寫「子代理執行中（n 個）…」。
- 回答下方多一個收合的「**委派紀錄（n 個子代理）**」：點開後每個子代理一段，寫 profile、狀態、
  花的時間、token 數與模型呼叫次數、一句摘要（需要資訊時寫它要問的問題；沒通過 Host 檢查時寫
  「Host 註記」）。子代理產生的**檔案**是按鈕，按了用原本的檔案檢視器打開；Workflow 執行列出
  編號和狀態。之後也可以用編號（例如 f3）請 Agent 附上檔案。
- 紀錄只放摘要，不放子代理的完整回答；拒絕的委派（例如超過上限）沒有子代理執行，不會列出。

**在 Telegram 看到什麼**

- 那一則會被更新的「⏳ Working on it…」狀態訊息，多出「子代理（n 個執行中）：」和每個子代理一行
  （狀態、工具次數、時間）與任務說明。狀態有變就更新，但同一個聊天**最多每秒更新一次**。
- 最後的回覆在結果摘要之前加上「委派紀錄」：每個子代理的狀態、時間、token、摘要或問題、產出編號。
  回覆太長時，照原本的方式改成傳檔案。

**上限與規則（摘要）**

- 深度 1：子代理不能再交給別的子代理。
- 一回合最多 **3 個**子代理；第 4 個會被拒絕。
- 只有全部工具都只讀的子代理可以**同時跑**（最多 3 個）；有寫入能力的子代理一次一個。
- 會改變東西的動作**一樣要你按確認**；同一回合同一個寫入動作最多執行一次。
- 只有 AEP 自己的 Gateway 對話可以委派；**Claude Code、Codex、Copilot 後端的對話不會委派**。
- 時間到的子代理會停下來並標「失敗」（`delegation_time_limit`）；目前沒有取消按鈕。

---

## 5. Capabilities：管理 Skill 與 Workflow

左邊 **Capabilities** 打開，頁面標題是 **Installed on this Agent**。

### 5.1 名詞

- **Skill**：教 Agent 某件事怎麼做的說明書（何時用、用哪些指令）。
- **Workflow**：一串固定步驟的自動化程序（例如準備 release 套件），有參數表單。
- **Knowledge**：Agent 可以查詢並附出處的知識庫版本。
- **Extensions** / **Apps**：Bridge 擴充功能與獨立應用程式（由平台管理，一般人不用動）。

### 5.2 頁面上方

- **Refresh status**：重新讀取。
- **外部 Agent 提交，等待你核准**：Claude Code、Codex、Copilot 送來的 Skill / Workflow。
  按 **完整內容** 看完再按 **核准** 或 **拒絕**。Skill 要在重新開啟 Agent Web 後才生效。

### 5.3 分頁與篩選

- 分頁：**Skills**、**Workflows**、**Knowledge**、**Extensions**、**Apps**（數字是數量）。
- 搜尋框 **Search this Agent's capabilities**：用名稱、命名空間或說明搜尋。
- 篩選（只在 Skills / Workflows 分頁）：

| 篩選 | 列出什麼 |
|---|---|
| **All** | 全部 |
| **Installed** | 已安裝且開啟中的 |
| **Drafts** | 在對話中做出來、或外部 agent 送來、**還沒安裝**的草稿 |
| **Switched off** | 已安裝但關閉中的（Agent 不會使用） |

- 清單每一列右邊的開關：亮＝開啟，按一下關閉；暗＝關閉，按一下開啟。

### 5.4 選一個項目後的按鈕

| 狀態 | 按鈕 | 作用 |
|---|---|---|
| 草稿（`Draft — not installed`） | **Install** | 你的核准：安裝它。Workflow 立即可用，Skill 要重新開啟 Agent Web 後才用 |
| | **Discard draft** | 刪除草稿（不影響已安裝的版本） |
| 已安裝 | **Switch off** | 關閉：Agent 不再使用，但保留在這台電腦（`assets\skills\disabled` 或 `assets\workflows\disabled`） |
| 關閉中 | **Switch on** | 重新開啟 |
| 已安裝 / 關閉中 | **Remove from this Agent** | 移除：檔案移到 `workspace\removed\<日期>\`，**不會刪除** |

- 跟著 AEP 一起出貨的項目不能移除（按鈕是灰的，說明 `Ships with AEP…`），請改用
  **Switch off**。
- **找回移除的項目**：到 `workspace\removed\<日期>\` 把檔案移回原本的資料夾
  （`workspace\assets\skills\` 或 `workspace\assets\workflows\`），再按 **Refresh status**。
- Skill 的詳細頁有 **Ask /<指令>** 按鈕，會把指令放進對話輸入框。
- Workflow 的詳細頁有 **Settings on this computer**（第 9 章）和 **Run this Workflow**。
- Workflow 的詳細頁還有 **Revise in chat**：開一個新對話，輸入框裡先填好「Revise the
  installed Workflow <名稱@版本>: 」，你把要改的地方寫完再按 **Send**（不會自動送出）。
  Agent 會讀出這個 Workflow 原本的步驟（包含內嵌的 Python 腳本）、複製成版本加一的草稿
  （例如 1.0.0 → 1.0.1，同一個名稱）再改，對話裡出現安裝卡「Revision of X 1.0.0 →
  1.0.1」並列出改了哪些步驟、參數和腳本行數。按 **Install** 才會安裝；舊版本保留、
  執行紀錄不變。不是你自己的 Workflow（例如跟 AEP 一起出貨的）會改成你自己名下的新名稱
  （fork），卡片會寫明。
- 團隊擁有的 Workflow（例如 `team:engineering`）：如果你是該團隊成員，會在原名稱下改成
  1.0.1，不會 fork。成員資格先問共享平台（離線時用上次的結果）；沒有連平台時，用 Settings →
  Shared platform 的 **Teams I belong to on this PC**，這時卡片會寫「(declared on this PC)」。
  這只影響這台電腦上的草稿名稱；發布回平台時，平台仍會用它自己的紀錄檢查。
- Knowledge 的詳細頁有 **Ask this Knowledge source**：選 **Knowledge Asking Skill**、
  輸入 **Question**，按 **Ask Knowledge**，下方列出引用來源。
- 最下面的 **Recent runs** 列出最近的執行紀錄。

### 5.5 Share Platform Library（共享平台的能力）

要先完成第 10 章的設定。頁面下半部 **Share Platform Library**：

1. 分頁 **Skills / Workflows / Extensions / Apps**；可以用 **Search shared capabilities**、
   **All categories**、狀態篩選（**Installed** / **Selected** / **Available**）找。
2. 點一張卡片看細節（說明、版本、擁有者、誰能用、內容）。
3. 按 **+ Add to this Agent**：替你在平台登記並**立即安裝**到這台電腦，左邊清單會出現新
   項目。卡片上若出現 `Restart needed before the Agent can use it.`，請重新開啟 Agent Web。
4. 已選取但還沒裝好時，按 **Install now**；不要了按 **Remove selection**。
5. **Sync again**：只有在 Member Portal（網頁）上選了東西時才需要按，把那邊的選擇裝到
   這台電腦。
6. **Open Marketplace**：在新分頁打開 Member Portal 的 Marketplace；已存 Personal Agent
   code 時會**自動用你的身分登入**（一次性、一分鐘有效的登入票）。
7. **Selections authorized on this Bridge**：這台電腦已被授權的選擇清單。

如果這台電腦有手寫的 `grants.json`，安裝只會放進檔案，**能執行什麼仍由 `grants.json`
決定**，卡片上會註明。

### 5.6 Publish to the shared platform（分享自己的能力）

1. 在 **Publish to the shared platform** 卡片：
   - **Skill or Workflow**：選要分享的項目；
   - **Change**：`patch: a fix`（修正）/ `minor: something added`（新增功能，預設）/
     `major: changes how it is used`（用法改變）；
   - **Who can use it**：`As the Skill or Workflow says` / `Only my team` /
     `Everyone in the organization`；
   - **Note for the reviewer**：一句話說明改了什麼、為什麼。
2. 按 **Publish for review**，看到 `<名稱> is waiting for an administrator's review.`。
3. 要等平台管理員（不能是你自己，除非平台另外設定）核准後，其他人才看得到。**版本號由
   平台決定。**
4. 下方表格列出你送出的項目（**Asset, Kind, Submitted, Status, Reviewer note**）；
   還在等待的可以按 **Withdraw** 撤回。
5. Skill 若會執行某個 Workflow，那個 Workflow 也要一起發布（或已經在平台上）。
6. 出現 `Publishing is not set up on this PC…`：先到 **Settings → Shared platform** 填
   Member Portal URL 和 Personal Agent code（第 10 章）。

---

## 6. Knowledge：維護知識庫

左邊 **Knowledge**。這一頁讓你在**自己的沙盒（sandbox）**裡改善共享知識庫（vault）的
**一個資料夾**，分三步：**Pull data → Ingest data → Testing data**。在你按 **Push**
之前，**正式的 vault 完全不會被改到**。

只想**查**知識庫的人不需要這一頁：直接在對話裡問，或用 `/wiki-query`。

### 6.1 先設定 vault（管理員或你自己，在 host.json）

沒有設定時，頁面會顯示 `The Knowledge pipeline is not configured on this machine
(host.json knowledge_pipeline).`。在安裝資料夾的 `host.json` 加入（路徑換成你們的共享
資料夾，例如 OneDrive 上的知識庫）：

```json
"knowledge_pipeline": {
  "vaults": [
    {
      "name": "team-knowledge",
      "root": "C:/Users/you/OneDrive - Company/Team_Knowledge",
      "maintainers": ["alex.wang", "chris.lin"],
      "knowledge_asset": "team-knowledge"
    }
  ],
  "sandbox_root": "C:/kb-sandboxes"
}
```

| 欄位 | 意思 |
|---|---|
| `name` | vault 的代號（英文、數字、`-`），畫面上的 **Project vault** |
| `root` | 共享 vault 資料夾 |
| `drop_root` | 原始檔（PDF、PPTX…）放哪裡；預設 `<root>/drop` |
| `questions_root` | 測試題放哪裡；預設 `<root>/checks/questions` |
| `maintainers` | 誰可以 **Push**（用 Agent 的帳號名稱）；留空＝任何使用這台 Agent 的人都能 Push。誰能寫入資料夾仍由 OneDrive 共用權限決定 |
| `knowledge_asset` | Agent 查詢用的 Knowledge 名稱；Push 後按 **Refresh the Agent's Knowledge** 會更新它（`host.json` 的 `knowledge` 清單裡也要有同名的 Knowledge）。沒填時這個 vault 顯示為 `test vault` |
| `sandbox_root` | 沙盒放哪裡；預設 `workspace\knowledge-sandboxes`。路徑太深時改短一點 |

改完重新開啟 Agent Web。**不要**在 OneDrive 共享資料夾上用 git（同步會弄壞 `.git`）。

### 6.2 vault 長什麼樣子

- `drop\<分類>\...`：原始檔（PDF、PPTX、DOCX、XLSX、HTML、圖片…）。
- `raw\...`：轉換後的 Markdown（Raw 文件）。
- `wiki\...`：整理好的知識頁面（Agent 查詢的內容）。
- `CLAUDE.md`：整個 vault 的寫作規範；`skills\<名稱>\SKILL.md`：各資料夾的 ingest 規則。
- `checks\questions\`：測試題；`index.md`、`log.md`、`decisions.md`。

### 6.3 Step 1 of 3 · Pull data

1. **Continue a sandbox**：繼續之前的沙盒；或在 **Start a new sandbox**：
   - **Project vault**：選 vault；
   - **Folder you maintain**：你負責的資料夾（例如 `Productions/VNA`）；
   - **Sandbox name**：例如 `VNA trial`；
   - 按 **Create sandbox and pull**：整個 vault 複製到你的沙盒，並拉進這個資料夾還沒 ingest
     的原始檔。
2. **From the project vault** → **Pull**：再次拉進新的原始檔（已經 ingest 過的不會重複拉）。
3. **From this computer**：選 **Folder**，選檔案，按 **Add files**，把電腦上的檔案加進沙盒。
4. **Convert**：先按 **Preview convert** 看會轉哪些，再按 **Convert** 把原始檔轉成 Raw。
   圖片會請模型描述，一份簡報可能要幾分鐘；它在背景跑，可以先做別的事，或按 **Stop** 停止。
5. 按 **Next: Ingest data →**。

沙盒上方：**Switch sandbox** 換沙盒；**Discard sandbox** 丟掉整個沙盒（移到
`knowledge-sandboxes\.discarded\`，不會真的刪除；正式 vault 不受影響）。


### 6.4 Step 2 of 3 · Ingest data

**Skills for this folder**：這個資料夾的 ingest 規則。

- 點一個規則檔打開編輯器：**Preview** / **Markdown** 分頁；**Previous file** 顯示和上次存檔的
  差異，**Current file** 可以直接改。
- 右邊的 **AI session**：用一句話告訴它要改什麼（例如「每個市場說法都要附日期」），按
  **Send**；它的建議會放進 **Current file**，你看過再按 **Save**。**New conversation**
  重新開始。
- **Save** 存檔、**Revert to saved** 放棄修改、**Close** 關閉。
- 規則由一般到特定一層層套用：`CLAUDE.md` → 類別規則 → 這個資料夾的規則。在這裡只能改
  這個資料夾的規則，上層的只能看。修改留在沙盒裡，Push 時才會進 vault。

**Ingest**：把 Raw 文件寫成 wiki 頁面。

1. 右邊列出 Raw 文件（剛轉好的會打勾並顯示綠色）。鍵盤：↑↓ 移動、Shift+↑↓ 選一段、
   空白鍵勾選；**All** 全選；下拉選單換資料夾。
2. 點一份文件可以先閱讀；按 **Plan ingest** 看這份會改哪些頁面（**Compare** 看差異，⚠ 是矛盾），
   滿意再按 **Apply to this sandbox**。
3. 按 **Ingest ticked** 處理所有勾選的文件（會先確認、估計時間；背景執行，可按 **Stop**）。
   結果會標示 applied、needs your review（按 **Review** 檢查）或 failed。被替換的頁面備份在
   沙盒的 `.ingest-backup\`。
4. 按 **Next: Testing data →**。

### 6.5 Step 3 of 3 · Testing data

**Questions**：測試題。上方顯示這個資料夾的題目涵蓋率。

- **New question** 新增題目。格式：標題就是問題；`必須提到:` 下面列好答案一定要提到的
  詞，`不可以說:` 下面列不能說的內容，每行以 `- ` 開頭。沒有列詞的題目不計分。
- 按 **Save question** 儲存。

```markdown
# CMX500 支援哪些 5G NR 頻段？
必須提到:
- FR1
- FR2
不可以說:
- 不支援 FR2
```

**Test**：勾選題組，按 **Run test**（結果存在沙盒的 `.benchmarks\`）。每題會分別問「你的沙盒」和「正式 vault」，依詞彙計分，
讓你看到改善或退步。

**Push to the vault**：

1. **Check conflicts**：列出和別人改過的同一段落；每一個衝突選 `keep sandbox`（用你的）或
   `keep published`（用 vault 現在的）。
2. **Push**：合併進**現在的**正式 vault，用勾選的題組再測一次，**只有沒有任何一題退步、
   總分沒有降低、也沒有遺失任何有來源的內容時才寫入**。Push 是直接把檔案複製進 vault 資料夾
   （不是 git）：被替換的檔案先備份到 `<vault>\.ingest-backup\<push id>\`，紀錄寫在
   `<vault>\pushes\` 和 `log.md`。vault 在這段時間被別人改了會自動重試，最多 3 次。
3. **Refresh the Agent's Knowledge**：把 vault 複製成 Agent 的下一個 Knowledge 版本；
   **重新開啟 Agent Web 後**查詢才會用新版。

**Advanced**（一般不需要）：**Run lint**（檢查格式與連結）、**Adopt legacy Raw**、
**Merge into a candidate** / **Publish candidate**（只更新這台 Agent 的版本，不推到正式
vault）、**Write bilingual summaries** / **Build layered index**（大型 wiki 的雙語摘要與
分層索引）。

### 6.6 Reviews：經驗回顧與改善提案

左邊 **Reviews**。Agent 每晚把失敗的、被評 👎 的、或證據不足的回答整理成案例，並提出改善
建議。**你決定之前什麼都不會改。**

- 分頁：**To decide**（待決定）、**Accepted**、**Snoozed**、**Rejected or done**。
- 每個提案的按鈕：
  - **Accept: …**：依提案類型，會「開一個 review 沙盒」（規則修改或新測試題，在 Knowledge
    頁比較、測試、Push）、「加入缺口清單」（缺知識），或「當成 issue 追蹤」（平台問題）；
  - **Reject**：要寫原因，同樣的案例之後不會再提；
  - **Snooze 7 days**：先隱藏 7 天。
- 已接受的：**Open in Knowledge**、**Mark done**；已關閉的可以 **Reopen**。
- **Knowledge gaps**：被接受的「缺知識」提案。把資料放進指定的 drop 資料夾，再按
  **Mark done**。
- **Review settings and the latest report**：**Review now**（立即回顧）、
  **Keep cases [n] days**（案例保留天數）、**Review nightly**（每晚自動）、**Save settings**。

#### 建議的 Skill（Suggested Skill）

Agent 每晚也會比對**你自己的**提問；同一件工作你重複做了好幾次，就會在 **To decide**
出現一張 **Suggested Skill** 卡片。只有你看得到自己的建議，同一台電腦的其他成員看不到。

- 卡片內容：這件工作的一句話說明；**Why**（相同的關鍵字、用了相同的工具順序）；
  次數（幾次提問、幾個對話、幾天）；以及你的提問清單（日期與摘要）。點一筆就會打開那個
  對話並捲到那則提問；對話已刪除的會標示 "This conversation was deleted."。
- 之後又重複同樣的工作，會更新同一張卡（"seen N more times since"），不會多出新卡。
- 按鈕：**Ignore**（忽略；可選 "Not useful"、"One-off"、"Wrong grouping"，也可再補一句，
  **都不是必填**）、**Snooze 7 days**（先藏 7 天）。被忽略的建議，要等你**之後**又重複到
  門檻的次數，才會再出現。已忽略的卡可以 **Reopen**。
- 目前**還不會產生草稿**，也沒有 **Create draft** 按鈕；不會自動安裝任何東西。
- 設定在 **Review settings and the latest report → Suggested Skills**，按 **Save settings**
  儲存，下一次每晚回顧就生效，不用重開 Agent：
  - **Suggest Skills from my repeated work**：開／關（預設開）；
  - **Sensitivity**（敏感度，要重複幾次才建議）：
    - **Low**：3 個對話中共 4 次、至少 3 天，每晚最多 1 張；
    - **Normal**（預設）：3 個對話中共 3 次、至少 2 天，每晚最多 3 張；
    - **High**：2 個對話中共 2 次，每晚最多 5 張；
  - **Compare at most [n] requests a night**：每晚最多送幾則提問給模型比對（10～1000，預設 120）。
- 這些設定存在這台 Host 的工作區，對在這台 Agent Web 上的你生效。

### 6.7 寫到哪裡

| 動作 | 寫入 |
|---|---|
| Pull、Add files、Convert、Ingest、改規則、改題目 | 只寫你的沙盒（`sandbox_root` 底下） |
| Push | 正式 vault（`root`），先備份被替換的檔案，並記錄誰從哪個沙盒推的 |
| Refresh the Agent's Knowledge | 這台 Agent 的本機 Knowledge 新版本（`host.json` 會先備份） |
| Reviews 的 Accept | 開 review 沙盒、缺口清單或 issue 紀錄；不會直接改 vault |

### 6.8 BI 卡片：知識庫、查詢與 Dashboard

BI 卡片是市場與業務情報的結構化卡片。建立和維護的步驟（知識庫與工作領域、轉檔、Ingest、審核、測試、
commit、push、發佈）寫在這個資料夾的 **`BI_SOP\BI_BUILD.zh-TW.md`**；一步一張截圖的操作手冊是
**`BI_SOP\BI_SOP.zh-TW.md`**，寫判讀規則的範例是 **`BI_SOP\BI_SKILL_EXAMPLES.zh-TW.md`**。

**開啟時的知識庫**：BI 卡片區會打開你上次在這個瀏覽器選的知識庫（還在的話）。這台電腦還沒有知識庫時，
按最上面的「新增知識庫」，或「加入」同事已經建好的知識庫。

**AI 的結果是有出處的候選，不是完整答案**：每個值都要人審核才寫入；同樣的輸入每次跑的結果可能不同。

**更正與定案**：卡片詳細頁的欄位可以「提更正單」（新值和理由，存成一份來源），共用知識庫還可以「定案」
（開會決定的值；舊值、誰改的和理由留在歷史）。commit 並 push 後大家才看得到。

**在對話裡查詢**：直接問，例如「哪些應用對手有方案、我方沒有？」「BMS 的應用有沒有商機？」。
Agent 只用卡片回答，每一句會標出處，例如 `[卡片 Application:AMR 電池包 BMS 與充電驗證]`，
並分開「事實」與「推論」。找不到時會說「在這份資料集中沒有…」，不會說成全世界都沒有。問哪個比較優先時，
Agent 會依卡片上的事實自己判斷，並說明這是它的判斷。這個功能由內建 Skill **engineering/bi-knowledge**
提供，預設開啟；在 Capabilities 可以關閉。

**對話裡用訂閱的資料集**（§6.8.2）：在問題裡說出資料集名稱，例如「用 engineering/robotics-bi
看 BMS 有哪些缺口」。回答最後一行會寫出資料來自哪一版，例如「資料來源：robotics-bi v1.2.0（發佈者
leo.chi）」；平台上已有更新的版本時會加一句「平台上有 v1.3.0，尚未更新」；你已沒有讀取權限時會說
「已停止更新」，內容停在那一版。要換成新版，到 BI 卡片的「已訂閱的資料集」按「更新」（不會自動更新）。
Agent 偶爾漏寫這一行時，主機會依查詢結果自動補上（Agent Web 與 Telegram 都一樣），一個資料集只補一次。

**Dashboard**：最上面的「工作領域」決定 Dashboard 和卡片看哪個領域；「全部領域」看全部。新的分析在
「建立與匯入」的步驟 3「Dashboard」區用「和 AI 做新分析」。

#### 6.8.1 新增資料集、安裝 schema

每個資料集在建立時選定**一個 schema**（卡片類型與欄位的定義），之後**不能更換**。內建的 BI schema
是 `bi.schema/v1.1`（上面那 12 種卡片）；也可以安裝自己的 schema，例如產品規格、供應商清單。

- **新增資料集**：在資料集列按「新增資料集」，填名稱（英文字母、數字、`-`、`_`，最多 40 字，
  不能和現有的重複，不分大小寫），選 schema，按「建立」。資料集選單會顯示每個資料集用的 schema。
- **安裝 schema**：按「安裝 schema」，選一個 `.json` 檔，按「驗證並安裝」。檔案有問題時不會安裝，
  下方會逐條列出**哪個位置**錯了，例如 `types[1]（Component）.fields[3]（supplier）.link_to：
  目標類型「Vendor」不在這份 schema 的 types`。安裝好的檔案放在
  `workspace\bi\schemas\<schema_id>@<version>.json`。
- **同一個 id@version 裝好後不能修改。** 內容完全相同再裝一次沒關係；內容不同會被拒絕，
  請把 `version` 改成新版本（例如 `1.0.1`）再安裝，然後用新版本建立新的資料集。
- **非 BI schema 的資料集**：可以匯入 CSV（預覽、寫入、復原）、瀏覽卡片、看來源與歷史、手動修改，
  類型篩選、匯入類型與欄位都依該資料集的 schema。但**沒有 Dashboard**（會顯示「這個 schema 沒有
  Dashboard」），**對話也不會查它**（Agent 會說這個資料集不是 BI schema），也不能「載入示範資料」。
  只有 `bi.schema/*` 的資料集有 Dashboard 與對話查詢。
- 以前就有的資料集（例如 `demo`）自動視為 `bi.schema/v1.1`，用法不變。

**schema 檔的格式**（JSON，UTF-8，最大 1 MB）。最少要有：

```json
{
  "schema_id": "team/product-spec",
  "version": "1.0.0",
  "title": "產品規格",
  "types": [
    {
      "name": "Product",
      "label": "產品",
      "fields": [
        {"name": "name", "label": "產品名稱", "kind": "str", "class": "sourced",
         "aliases": ["產品名稱", "產品"]},
        {"name": "status", "label": "狀態", "kind": "enum", "class": "sourced",
         "enum": ["development", "mass_production"]}
      ]
    }
  ]
}
```

- `schema_id`：小寫英數字與 `.` `_` `-`，可用 `/` 分段；`bi.schema/` 開頭保留給內建 schema。
  `version`：`主.次.修訂`。`title`：顯示名稱。
- 每個類型：`name`（英文，例如 `Product`）、`label`（中文名稱）、`fields`。卡片名稱預設取
  `name` 欄位；要用多個欄位組成，設 `"naming": ["product", "name"]`。
- 每個欄位：`name`（小寫英文與 `_`）、`label`、`kind`（`str` 文字、`int` 整數、`bool` 是否、
  `date` 日期、`enum` 選項、`list` 清單、`link` 連到另一張卡、`linklist` 連到多張卡）、
  `class`（`sourced` 事實、`judgement` 判斷，手改要寫理由、`derived` 衍生，不能手改）。
- 選填：`aliases`（CSV 欄名的別名，匯入時自動對應）、`enum`（`enum` 必填）、`link_to`
  （`link`/`linklist` 必填，目標類型）、`range`（整數範圍 `[0, 100]`）、`default`、`required`；
  最上層的 `enum_aliases` 讓 CSV 的中文值對到選項，例如 `{"status": {"量產": "mass_production"}}`。
- 拼錯的欄位名稱也會被當成錯誤列出，避免設定悄悄沒生效。

**範例 schema「產品規格」**：在「安裝 schema」按「安裝範例 schema（產品規格）」，會安裝
`example/product-spec@1.0.0`（供應商、零組件、產品、規格項目四種類型，零組件連到供應商、產品連到零組件、
規格項目連到產品），並提供四個範例 CSV 下載。接著「用這個 schema 新增資料集」，依序匯入
供應商 → 零組件 → 產品 → 規格項目，連結才找得到對象（「主控 MCU」的供應商「恩智浦」故意不在
供應商清單裡，預覽會出現「找不到對應卡片」的警告）。

#### 6.8.2 分享資料集：發佈到 Shared Platform、已訂閱的資料集

需要先在 Settings → Shared platform 設定 Member Portal 網址與 Personal Agent code（和發佈 Skill
相同）。分享的是**某一版的快照**：同事看到的是你發佈的那一版，之後你再改的內容要等下次發佈。

**發佈（負責人）**：選你自己的資料集，按「發佈到 Shared Platform」。

- **平台名稱**：只有第一次發佈要填，預設是 `<namespace>/<資料集名稱>`（小寫英文、數字與 `-`），
  之後每次發佈都用同一個名稱。
- **版本說明**（必填）：一行，說明這一版改了什麼。
- **讀者**：預設是**我的團隊**。要給平台上所有成員，勾「開放給全公司」，再勾下面的確認
  （INTERNAL 資料會給所有成員）；沒有公開選項。
- **將分享**：所有卡片與欄位來源、修改歷史（誰、何時、為什麼）；**不含**待審提議；
  匯入檔只留檔名，不含你電腦上的資料夾路徑。
- **第一次發佈需要管理員審核**：新名稱的第一版送出後是「待審核」，管理員核准後同事才看得到；
  之後的版本按「發佈」就直接發佈，版本號由平台指定（1.0.0、1.1.0…）。
- 發佈後資料集列會顯示「已發佈 v1.1.0（時間）」或「待審核」。
- 沒有發佈時的說明：
  - 「看起來含有密碼或 token」：指出是哪張卡片的哪個欄位（不會顯示內容），改掉再發佈。
  - 「平台上已有比你這份更新的版本」：別人（共同維護者）先發佈了。
  - 「沒有發佈這個名稱的權限」：請名稱的負責人把你加為共同維護者。
  - 「太大」：超過平台的大小上限。「沒有回應」：平台連不到，資料沒有送出。

**已訂閱的資料集（同事）**：展開 BI 卡片上方的「已訂閱的資料集」。

- 按「瀏覽平台上的資料集」列出你有權讀、還沒訂閱的資料集，按「訂閱」裝到這台電腦（也可以在
  Shared Platform 選取資料集，再到 Settings 同步）。
- 每個訂閱顯示發佈者、版本與狀態：**有新版本**（按「更新」才會換成新版，不會自動更新）、
  **已是最新**、**已停止更新（無權限）**（你已不在讀者名單；這一版仍可讀，但不會再更新）、
  **無法連線**（平台連不到，照常可讀）。
- 「取消訂閱」會先確認，再把這台電腦上的副本移除。
- 資料集選單分成「我的資料集」與「已訂閱」。開啟訂閱的資料集時，上方顯示
  「唯讀：<發佈者> 發佈的 v<版本>」；Dashboard、卡片與對話照常可用，**匯入、編輯、載入示範資料與
  發佈都不提供**。要修改請找發佈者。

#### 6.8.3 核准資料處理程式與分析腳本代表什麼

知識庫的**資料處理程式**（步驟 2 的「資料處理程式」）和 **Python 分析**是在你電腦上執行的程式碼。
資料處理程式的每個新版本，第一次在這台電腦執行前，要由你按「看過了，核准」；Python 分析的腳本
和結果會一起顯示，由你決定要不要存下。

- **核准就是你讀過這段程式，並信任它。** 這是唯一真正的把關：核准綁定這份程式碼的雜湊值，
  程式改了一個字就要重新核准。存下一個分析也一樣，代表你看過它的腳本。
- 執行時的防護會擋下常見的失誤：連網路、開子程序、載入原生程式庫（ctypes）、寫到輸出資料夾
  以外的地方。它也擋下「先把防護關掉」這類簡單的手法。
- **它不是沙箱。** 刻意寫成要做壞事的程式，仍可能找到 Python 本身的漏洞繞過它；程式也可以讀取你
  電腦上讀得到的檔案。看不懂、或來源不明的程式，不要核准。

---

## 7. Laya AI 決策加速

位置：**Settings → Laya decision acceleration**。Laya 是一個能快速回答「小型路由決策」
（例如這句話該用哪個 Skill）的模型。**一般同事不需要設定**；預設是 **Off**。

### 7.1 欄位

| 欄位 | 預設 | 意思 |
|---|---|---|
| **Remote host** | （空） | Laya 主機的位址，由負責人提供 |
| **SSH port** | 22 | Laya 主機的 SSH 埠 |
| **Account** | （空） | 登入 Laya 主機的帳號 |
| **Remote port (Laya)** | 8000 | Laya 服務在遠端主機上的埠 |
| **Local port** | 18000 | 這台電腦上轉接用的埠（1024 以上） |
| **Mode** | Off | `Off`（不用）/ `Shadow (record only)`（只記錄）/ `Active`（真的使用） |
| **Confidence threshold (%)** | 90 | Laya 的信心高於這個值才採用 |
| **Timeout (ms)** | 1500 | 等 Laya 最多多久（100～5000），超過就當作沒有答案 |
| **Owner approval reference** | （空） | Shadow 和 Active 會把你最新的一句話送給 Laya，**必須填核准編號** |
| **Agent Web opens the SSH tunnel and reopens it when it drops** | 不勾 | 勾選＝Agent Web 自己開 SSH 通道並在斷線時重開 |

按 **Save Laya settings**；按 **Check connection** 看狀態，例如
`Connected: Laya answered in 230 ms · tunnel running · last decision …`。

### 7.2 Shadow 是什麼

- **Shadow (record only)**：每次對話時在背景問 Laya，**只記錄**它的選擇和花的時間，
  不影響回答。用來收集資料、評估準不準。
- **Active**：Laya 有信心時，會縮小大模型能看到的 Skill 清單。選錯時可能把對的工具藏起來，
  所以要先用 Shadow 證明夠準。
- **改 Mode 要重新開啟 Agent Web 才生效**（卡片會顯示 `running in shadow until Agent Web
  restarts`）；通道設定則立即生效。

### 7.3 SSH 金鑰或轉接（relay）

Agent 只透過**這台電腦的 `127.0.0.1:<Local port>`** 找 Laya，不會用明文連到別台電腦。
有兩種方式讓那個埠通到 Laya：

1. **SSH 通道（建議）**：Laya 主機要接受你這台電腦的 SSH 金鑰。確認可以不輸密碼登入
   （`ssh -p <SSH port> <Account>@<Remote host>`）後，勾選 **Agent Web opens the SSH tunnel…**。
   Agent Web 用批次模式執行 ssh，金鑰不被接受時會在卡片上顯示 ssh 的錯誤，不會跳出密碼提示。
2. **自己開通道或轉接**：金鑰還沒被接受時，不要勾選；由負責人用其他方式把
   `127.0.0.1:<Local port>` 轉到 Laya 主機。卡片會顯示 `tunnel not opened by Agent Web`，
   只要 **Check connection** 顯示 `Connected` 就能用。

### 7.4 常見訊息

| 訊息 | 處理方式 |
|---|---|
| `Not saved: shadow and active send the latest user message to Laya; enter the owner's approval reference first` | 填 **Owner approval reference** |
| `Not saved: the Laya key is not mapped in host.json credentials` | 請管理員在 `host.json` 的 `credentials` 對應 Laya 的金鑰名稱（`jev_api_key`）到一個環境變數 |
| `Not saved: check the host, account and numbers` | 主機、帳號或數字格式不對 |
| `Not connected through 127.0.0.1:18000` | 通道沒開；檢查 SSH 金鑰，或確認轉接在執行 |

---

## 8. Telegram

位置：**Settings → Telegram bot**。讓你（和你允許的人）用 Telegram 跟這台 Agent 對話。
Agent Web 要在執行中，Telegram 才會有回應。

### 8.1 建立 bot 並設定

1. 在 Telegram 找 **@BotFather**，傳 `/newbot`，照指示取名，拿到 bot 的存取權杖
   （格式像 `123456789:AA…`）。
2. 在 **Telegram bot** 卡片：
   - 勾選 **Answer Telegram messages**；
   - **Bot access token (from @BotFather)**：貼上權杖。它只存在你的 Windows 使用者環境變數，
     存完不再顯示；之後留空就是保留原本的。
3. 按 **Save Telegram settings**（立即生效，不必重開）。權杖存在使用者環境變數
   `AEP_TELEGRAM_BOT_TOKEN`，卡片會顯示 `Token saved in AEP_TELEGRAM_BOT_TOKEN.`。
4. **找出你的 Telegram 數字 ID**：用手機傳任何一句話給你的 bot，再回到卡片按
   **Check who messaged the bot**，在你的那一列按 **Allow**。
5. 或直接在 **Allowed senders** 一行填一個人：`數字ID 帳號`，例如 `123456789 alex.wang`
   （帳號可以省略）。不知道自己的數字 ID，也可以在 Telegram 問 **@userinfobot**。
6. 再按一次 **Save Telegram settings**。

**不在 Allowed senders 裡的人傳的訊息會被忽略。** 公司電腦上，只有這台電腦的擁有者可以
用 Telegram 下指令；有人離職或換手機時，記得把他從清單刪掉。

### 8.2 在 Telegram 能做什麼

- 一般問題：直接打字。回答前會先顯示進度，完成後顯示答案和用到的 Skill。
- 執行 Workflow：`/run <編號或名稱>` 或「執行 <名稱>」，見 4.6 節。訊息裡說了的值（例如 43W）會直接
  用，只問還缺的必填欄位，最後一張確認卡可以按 **修改** 或直接打字改值；`/cancel` 取消；15 分鐘沒完成
  會失效。
- `/help`（或 `/start`）：說明用法。
- `/new`：開一個新的對話（忘掉之前的檔案）。
- `/status`：這台電腦的狀態。
- `/<skill> <指令>`：直接執行某個 Skill 的指令。
- 傳檔案或照片並加上說明文字，Agent 會處理那個檔案。
- 對某則訊息按 **回覆（Reply）** 再打字（例如「再跑一次」），Agent 會一起看到被回覆的那則內容
  （你自己的訊息或 bot 的回答都可以）。同一個對話也會記得之前的要求，包括沒有完成的那一輪和
  Workflow 的執行；這份記憶只在 Agent Web 執行期間保留，重新啟動後會清空，`/new` 也會清空。
- 回答沒有文字時（例如只有圖表），會顯示「<Workflow> 已完成」。
- 很長的回答（例如週報）會分成好幾則訊息；如果 Telegram 仍然拒收（太長或格式無法顯示），
  整份回答會改成一個 `answer-<時間>.md` 檔案傳來，並附上「回答太長或格式無法顯示，已改用檔案傳送」。
- Agent 在對話中要求安裝或執行時，會出現 **核准執行 …** / **核准安裝 …** / **拒絕** 按鈕；
  只有這台電腦的擁有者能按。
- AI 提案（第 12 章）：只有低風險的種類可以在 Telegram 直接按 **Apply**（Laya 設定、
  Workflow 設定、開啟或關閉一個 Skill / Workflow）；其他種類會顯示「Open in Agent Web to
  apply」，請到 Agent Web 的 **Tasks → Pending changes** 按。
- Agent 模式（第 11 章）的 Claude Code / Copilot 在 Telegram 只能回答文字，權限卡片只能在
  Agent Web 按。

### 8.3 常見問題

| 狀況 | 處理方式 |
|---|---|
| bot 不回應 | 卡片顯示 `The bot is running but allows nobody yet` 時，照 8.1 第 4 步 Allow 自己；也檢查 Agent Web 有在執行嗎？**Answer Telegram messages** 有勾嗎？你的 ID 在 **Allowed senders** 裡嗎？ |
| 「The answer could not be delivered here …」 | Telegram 連文字和檔案都拒收了，或連線一直失敗（Telegram 要求等待時，Agent 最多等 1 分鐘再送；連線中斷會再試一次）；到 Agent Web 看同一個結果。原因（不含回答內容）記在 `workspace\logs` 最新的 `agent-web-*.err.log`，以 `Telegram sendMessage refused: HTTP …` 或 `Telegram sendMessage failed …` 開頭 |
| 回答後面出現「（系統檢查：…）」 | 這一輪 Agent 說已經做完某件事，但系統沒看到對應的工具成功執行，或提到的檔案不存在；請到 Agent Web 確認結果，或請它實際執行一次 |
| 「The Agent gave no answer after using …」 | 模型沒有產生文字；換個說法再問一次 |
| 上傳檔案被拒 | Telegram bot 只能下載 20 MB 以下的檔案；大檔請用 Agent Web |
| 「… Open Agent Web to set them, then send /run again.」 | Workflow 的設定只能在 Agent Web 填（第 9 章） |
| `Not saved: The token does not look like a bot token` | 從 @BotFather 重新複製完整權杖 |

---

## 9. Workflow 設定

有些 Workflow 需要「這台電腦上的固定設定」，例如資料夾位置、網址。這些**設一次就好**，
更新時保留，**執行時不會再問**。

### 9.1 在哪裡設

1. **Capabilities → Workflows**，選那個 Workflow。
2. 展開 **Settings on this computer**（缺必填設定時會自動展開）。
3. 上方顯示 `Missing required settings: … The Workflow will not start.` 或
   `All required settings are set.`。
4. 填好後按 **Save settings**，看到 `Saved. The next run uses these settings.`。

**權杖和密碼永遠不在這裡填**；需要的話放在 Windows 使用者環境變數（Workflow 說明會寫
變數名稱）。

### 9.2 範例：rs-wmt-package-release（產生並推送 release 套件）

`engineering/rs-wmt-package-release` 依序：準備（prepare）→ commit → push。

**這台電腦的設定（Settings on this computer）**

| 設定 | 意思 |
|---|---|
| **Release repository** | release repo：隔離資料夾裡的本機 repo；或開啟下一項時，GitLab 的 clone 網址（https 或 ssh，**網址裡不能有權杖**） |
| **Use the real release repository (GitLab)** | 關（預設）＝只接受隔離資料夾裡的本機 repo，適合先練習 |
| **Template branch** | 預設 `template` |
| **Working copy folder** | 工作副本放哪裡（要在隔離資料夾裡） |
| **Input inbox** | 放測試計畫、設定檔、overlay 的收件資料夾（要在隔離資料夾裡） |
| **Isolated root** | 隔離資料夾；裡面必須有 AEP 的標記檔 |
| **Published package index** | 套件索引網址（查晶片版本用） |
| **Readiness table** | 備用的版本查詢表網址 |

**準備隔離資料夾（只做一次）**

1. 建一個資料夾，例如 `C:\release-root`，把 **Working copy folder**（例如
   `C:\release-root\work`）和 **Input inbox**（例如 `C:\release-root\inbox`）都放在裡面。
2. 在隔離資料夾放標記檔 `.aep-isolated-release-root`，內容必須剛好是一行
   `AEP_ISOLATED_RELEASE_ROOT_V1`。在 PowerShell 執行：

   ```powershell
   [IO.File]::WriteAllText("C:\release-root\.aep-isolated-release-root", "AEP_ISOLATED_RELEASE_ROOT_V1`n")
   ```

   沒有標記檔或內容不對時，會被拒絕（`isolated_root_unmarked`）。
3. 需要讀取私有套件索引時，把權杖放在 Windows 使用者環境變數 `ARTIFACTORY_TOKEN`
   （readiness 表用 `OPS_TOKEN`），重新開啟 Agent Web。

**執行時的欄位**：公司名稱、晶片代號與版本（可從清單選或自己打）、額外標籤、
`CMP_KT_OPTION`（KT160 / KT161）、general testcase 版本、說明、從 inbox 選的
測試計畫 / 設定檔 / overlay，或直接上傳、`SUFFIX`、`VERSION override`，以及：

- **Dry run: prepare only, no commit or push**（預設**開**）：只準備工作副本並顯示會
  commit 什麼，不 commit、不 push。**第一次請一定先跑 dry run**。
- **Push to the release repository**（預設**關**，會再確認）：只推這次 run 做出的 commit，
  永遠不會 force push。dry run 時忽略。

### 9.3 借用單回信（rs-loan-customer-block-scan / rs-loan-queue-reply）

兩個 Workflow，接替舊的 06 / 06b（不需要 n8n）：

| Workflow | 做什麼 |
|---|---|
| `engineering/rs-loan-customer-block-scan`（`/run 6`） | 讀 Outlook 收件匣，找「簽核通知」裡的借用單連結（DR…），每個借用單號排入一筆佇列。否決通知、排除的類別、已處理過的單號都會略過。 |
| `engineering/rs-loan-queue-reply` | 一筆一筆處理佇列：在出借系統讀客戶，到 C4C 查 Delivery Block，把回信存成 **Outlook 草稿**（附 C4C 截圖）。查不到客戶或失敗時，改建一封內部通知草稿。 |

**第一次使用**

1. 這兩個 Workflow 安裝時是**關閉**的：**Capabilities → Workflows**，選它們，按 **Switch on**。
2. 在 **Settings on this computer** 填：掃描的資料夾（預設 `Inbox`）、「只處理這個時間之後
   收到的信」（留空＝第一次正式執行的時間）、**內部通知寄給誰**、需要時的回信範本資料夾。
   **不需要也不要填任何密碼**：出借系統和 C4C 的登入由瀏覽器設定檔帶著（出借系統會自動選
   公司帳號；第一次請保持「顯示瀏覽器視窗」打開，看得到登入過程）。
3. 先跑一次 **dry run**（兩個 Workflow 的第一個問題都是「只試跑？」）：掃描只列出會排入
   哪些借用單；回信會讀出借系統和 C4C，但不建草稿、不動佇列。

**平常的流程**

1. 執行 `rs-loan-customer-block-scan`。結果會列出排入的借用單。佇列有待處理時，答案下方
   會出現 `rs-loan-queue-reply` 的執行表單（Telegram 是一個按鈕）；**它不會自己開始**，
   要你按 **Run**。
2. `rs-loan-queue-reply` 會問「這次處理幾筆？」和「草稿建好後，每封各給一張「寄出」確認卡？」。
   回信一律先存在 Outlook 草稿匣。
3. **寄出**（選用）：勾了確認卡時，每封草稿各有一張卡片，顯示收件者、主旨、附件和內文，
   按鈕是 **寄出** 和 **留在草稿匣**。
   - 每一封都要**各按一次**；沒有「全部寄出」。
   - 只在 **Agent Web** 按（Telegram 只顯示卡片，並提示到 Agent Web 的
     **Tasks > Pending changes** 按）。
   - 卡片顯示後若你在 Outlook 改過那封草稿（收件者、主旨或附件），按寄出會**不寄**，請在
     Outlook 自己寄。
   - 一天內沒按，卡片過期，草稿留在草稿匣。
   - 回信是回覆簽核通知那封信，收件者由 Outlook 依原信決定；**按寄出前請看卡片上的收件者**。

**排程（之後自己決定）**：目前沒有建立任何排程。要定時掃描時，到 **Schedules** 新增
`rs-loan-customer-block-scan`（例如每天 09:00 / 14:00），**Highest effect to allow** 選
`write`。回信 Workflow 建議仍由你手動執行；就算排程，它也只建草稿，寄出永遠要你按卡片。

### 9.4 個人 Workflow 不在安裝包裡

安裝包只帶給大家共用的 Skill 和 Workflow。個人自己的 Workflow 不會放進安裝包，也不會被
安裝或排程；需要的話請從共享平台安裝別人分享的能力（第 10 章）。更新時不會刪掉你電腦上已經
安裝的 Skill / Workflow；用不到的可以在 **Capabilities** 關掉或移除。

---

## 10. 共享平台（Shared Platform）：給一般成員

共享平台是團隊共用的 Skill 與 Workflow 市集：你可以**安裝**同事分享的能力，也可以把自己的
能力**發布**給大家用。平台由管理員架設，你只需要做一次下面的設定。

你會用到這幾種代碼，用途不同，**都不要貼到對話、文件或聊天軟體裡**：

| 名稱 | 從哪裡來 | 用途 | 效期 |
|---|---|---|---|
| 邀請連結（Invitation） | 管理員私訊給你 | 第一次登入 Member Portal（網頁），同時設定密碼 | 只能用一次 |
| 密碼 | 你自己在第一次登入時設定 | 之後用「帳號 + 密碼」登入 Member Portal | 直到你更改 |
| Personal Agent code | Member Portal 的 **Connect a Personal Agent** | 讓你的 Agent 以你的身分發布、註冊這台電腦、一鍵開 Marketplace | 30 天 |
| Bridge token | Agent Web 按 **Enroll this PC** 時自動取得 | 讓這台電腦從平台讀取清單、安裝 | 90 天 |

### 10.1 跟管理員要四樣東西

1. **你的帳號名稱**：必須和安裝時輸入的帳號**完全一樣**（例如 `alex.wang`）。只能用英文
   字母、數字和 `. - _`，**不要用 email**。不確定時看 **Settings → Shared platform** 卡片
   上「registered by」的值。
2. **Member Portal URL**（例如 `https://172.25.228.141:8776`）。
3. **Bridge API URL**（例如 `https://172.25.228.141:8775`）。Bridge 是跑在你這台電腦上的
   執行端；「Bridge API」是平台那一端讓各台電腦的 Bridge 連過去的網址（註冊、同步、token），
   在 Agent Web 裡的欄位叫 **Platform sync URL (Bridge API)**，工作仍然都在你這台電腦上執行。
4. **憑證指紋（SHA-256）**：一串 64 個英數字，例如 `83:95:B0:90:…:BA:8B`。平台用的是
   管理員自己簽的憑證（自簽憑證），Windows 不認得它，你要用這串指紋確認連到的是真的平台。

管理員會用你的帳號名稱發一張邀請，私訊給你一個邀請連結。

### 10.1.1 信任平台的憑證（第一次，在 Agent Web）

1. 打開 Agent Web → **Settings → Shared platform**，在 **Member Portal URL** 和
   **Platform sync URL (Bridge API)** 填上兩個 `https://` 網址。
2. 在 **Platform certificate** 區塊按 **Fetch & show fingerprint**。畫面顯示
   `SHA-256 83:95:B0:…`（兩個網址是同一張憑證）和 `not trusted yet`。
3. **逐段比對**這串指紋和管理員給你的是否**完全相同**：
   - 相同：按 **Trust this certificate**。卡片顯示 `Trusted certificate (SHA-256): …`，
     之後這台電腦只接受這一張憑證，其他一律拒絕；
   - 不同：**不要按 Trust**，告訴管理員。可能是網址打錯，或有人冒充平台。
4. 管理員換了憑證時（會通知你新的指紋），重做這三步；按 **Forget** 可以取消信任。

這只影響 Agent（同步、發布、註冊、一鍵開 Marketplace 取得登入票），不會關掉其他網站的
憑證檢查。

**瀏覽器的警告**：用瀏覽器打開 Member Portal（或按 **Open Marketplace**）時，Edge／Chrome
會顯示「你的連線不是私人連線」。兩種處理方式擇一：

- **每個瀏覽器第一次接受一次**：按網址列的「不安全」→ 憑證 → 詳細資料，看
  **SHA-256 指紋**和管理員給的相同，再回到警告頁按 **進階 → 繼續前往**。之後每次重開瀏覽器
  可能還會再問。
- **匯入憑證，不再警告**：在 **Platform certificate** 按 **Download .cer**（只有公開憑證，
  沒有私鑰），雙擊下載的 `shared-platform.cer` → **安裝憑證** → **目前使用者** →
  **將所有憑證放入以下的存放區** → **受信任的根憑證授權單位**；或在 PowerShell 執行
  `certutil -user -addstore Root "$env:USERPROFILE\Downloads\shared-platform.cer"`。
  重開瀏覽器後就不再警告。
  **風險**：受信任的根憑證可以替**任何**網站背書。持有這張憑證私鑰的人，理論上可以對你這個
  Windows 帳號假冒任何 https 網站。私鑰只存在平台電腦上、只有平台的服務帳號能讀，但仍請只
  在比對過指紋後匯入；平台改用公司正式憑證後，從 `certmgr.msc` →「受信任的根憑證授權單位」
  刪除它。不確定時，用第一種方式即可。

### 10.2 登入 Member Portal（瀏覽器）

**第一次（用邀請連結，同時設定密碼）**

1. 打開管理員給你的**邀請連結**，畫面會顯示 **Set your password** 和你的帳號名稱；
   或打開 Member Portal URL，展開 **Have an invitation or a password reset link?**，
   把連結貼上後按 **Continue**。
2. 輸入兩次新密碼，按 **Set password and sign in**。密碼至少 12 個字元（可以用幾個英文字
   組成的句子），不能包含帳號名稱，也不能是常見密碼。
3. 右上角顯示你的帳號名稱，就是登入成功。

**之後（帳號 + 密碼）**

- 打開 Member Portal URL，在 **Sign in** 輸入 **Account**（例如 `alex.wang`）和
  **Password**，按 **Sign in**。
- 輸入錯誤 5 次，這個帳號會被鎖 15 分鐘；畫面只會說「帳號或密碼錯誤」，不會說是哪一個。
- **改密碼**：登入後按右上角 **Password**，輸入目前密碼與新密碼。其他瀏覽器會被登出，
  這個瀏覽器保持登入；Personal Agent code 不受影響。
- 以前只用邀請連結登入、還沒有密碼的人：登入後頁面上方會提示 **Set password**。
- **忘記密碼**：請管理員發一個 **Password reset link**（只能用一次、預設 60 分鐘內有效）。

**Member Portal 的分頁（一般成員）**：**Marketplace**（瀏覽與選擇能力）、
**My published assets**（你發布的能力、調整誰能用）、**My submissions**（你送審的項目與
狀態）、**Applications**（獨立應用程式）。

### 10.3 讓你的 Agent 代表你（Personal Agent code）

1. 在 Member Portal 的 **Publish from your Personal Agent** 區塊按
   **Connect a Personal Agent**，複製出現的代碼（只會顯示這一次）。
2. 打開 Agent Web → **Settings → Shared platform**（`https://` 平台先做完 10.1.1）：
   - **Member Portal URL**、**Platform sync URL (Bridge API)**：填 10.1 拿到的兩個網址；
   - **Personal Agent code**：貼上剛剛的代碼；
   - 按 **Save**。代碼只存在你的 Windows 使用者環境裡，不會寫進任何檔案，也不會再顯示。

**更簡單的做法（不用複製代碼）**：在同一張卡片的 **Personal Agent code** 區塊輸入平台帳號
和密碼，按 **Sign in to get a code**。Agent Web 會用這組帳密登入一次、取得代碼並存好；
密碼只用這一次，不會被保存、記錄或顯示，按下後欄位就清空。之後代碼剩不到 7 天時會自動
換新（舊代碼同時作廢），卡片顯示「Personal Agent code valid until …」。代碼過期時會顯示
**Sign in to get a new code**，再登入一次即可。卡片也會顯示 Bridge token 的到期日，
剩不到 14 天時提醒你再按一次 **Enroll this PC**。

### 10.4 註冊這台電腦（Enroll this PC，只做一次）

在同一張卡片按 **Enroll this PC**：

- 成功時顯示 `Enrolled as <bridge-id>` 和 token 的到期日。
- 這一步只是讓這台電腦**可以從平台拿東西**，不會安裝任何能力，也不會改變這台電腦能執行
  什麼。
- 再按一次只會換一個新 token（舊的失效），不會重複註冊。token 快到期時再按一次即可。
- 顯示 **The Bridge API URL did not answer** 時，什麼都沒有存，請檢查 Bridge API URL。
- 顯示 **The Bridge API's certificate is not trusted by this PC** 時，什麼都沒有存，先做
  10.1.1 信任憑證再按一次。

### 10.5 安裝、發布、誰能用

- **安裝**：**Capabilities → Share Platform Library** → 卡片 → **+ Add to this Agent**
  （5.5 節）；或按 **Open Marketplace** 在網頁上選，再回 Agent Web 按 **Sync again**。
- **發布**：**Capabilities → Publish to the shared platform**（5.6 節），等管理員審核。
- **誰能用（Who can use it）**：發布時在 Agent Web 選 **Only my team**（和擁有者同一個群組的人）
  或 **Everyone in the organization**（平台上所有成員）。之後擁有者或管理員可以在 Member Portal
  的 **My published assets** → **Who can use it** 改成 `As each version declares`、
  `Only the owner`、`Only the owning team`、`Everyone in the organization` 或 `Public`，
  也可以在 **Also these members** / **Also these groups** 加指定的帳號或群組。收回權限不會
  移除別人已經安裝的版本。
- **誰能發布新版本**：擁有者、擁有團隊的成員，以及被加為 **co-editor** 的人。其他人發布
  同名的項目會被拒絕（`publisher_not_authorized`）。

### 10.6 常見問題

| 畫面上的訊息 | 原因 | 處理方式 |
|---|---|---|
| `device_owner_mismatch` | Portal 帳號和這台電腦的 registered by 不同 | 請管理員用 registered by 的名稱發邀請，重做 10.2～10.4 |
| `session_expired` | Portal 網頁閒置太久 | 重新整理頁面 |
| 「Account or password is wrong, or there were too many attempts」 | 帳號或密碼錯誤，或錯太多次被鎖 15 分鐘 | 等 15 分鐘再試；忘記密碼請管理員發 Password reset link |
| 「This reset link was already used / has expired」 | 重設連結只能用一次且有期限 | 請管理員再發一個 |
| `publisher_not_authorized` | 這個名稱屬於別人 | 請擁有者把你加為 co-editor，或改用新的名稱 |
| Library 是空的 | 還沒註冊、或沒有你能用的項目 | 先做 10.4；或請擁有者把 **Who can use it** 改成全公司 |
| `platform_unreachable` | 平台位址錯誤或網路不通 | 檢查兩個網址；確認平台有在執行 |
| `certificate_untrusted` | 還沒信任平台的憑證，或管理員換了憑證（訊息會列出兩個指紋） | 做 10.1.1；指紋和管理員給的不同時不要信任，通知管理員 |
| `certificate_mismatch` | Member Portal 和 Bridge API 出示不同的憑證 | 不要信任，問管理員哪一個才對 |
| 瀏覽器顯示「你的連線不是私人連線」 | 平台用自簽憑證 | 見 10.1.1「瀏覽器的警告」 |
| `Publishing is not set up on this PC` | 沒有 Member Portal URL 或 Personal Agent code | 做 10.3 |
| **Open Marketplace** 開的是登入頁 | 沒有存 Personal Agent code，或代碼過期（30 天） | 重新做 10.3 |
| 「This sign-in from Agent Web expired (it lasts one minute)」 | 一鍵登入票只有 1 分鐘 | 回 Agent Web 再按一次 **Open Marketplace** |
| 「This PC is registered to … which is not the platform account of this Personal Agent code」 | 代碼是別的帳號的 | 用這台電腦擁有者的帳號登入 Portal，重新取得代碼 |

---

## 11. Agent 模式（Agent mode）

一般情況下，選 Claude Code 或 GitHub Copilot 當對話後端時，它們**只能回答文字**。打開
Agent 模式後，它們可以在這個對話**自己的資料夾**裡讀寫檔案、使用 AEP 的 skills 和工具；
所有超出範圍的動作都會先在對話裡跳出卡片問你。

### 11.1 開啟

1. **Settings → Agent mode**。
2. 勾選 **Claude Code: agent mode** 或 **GitHub Copilot: agent mode**（預設全部關閉）。
   **Codex 不支援**（選項是灰的），只能回答文字。注意：對話下拉選單裡的
   **GitHub Copilot (agent, AEP tools)** 不是 Agent 模式，要選 **GitHub Copilot**。
3. **Default folder for conversations**：每個對話會在這裡面有自己的資料夾（預設
   `workspace\agent-sessions\<session>`）。它必須在畫面說明列出的允許位置底下；磁碟根目錄、
   使用者主資料夾都不行。
4. 按 **Save agent mode**。
5. 回到對話，在 **Conversation backend** 選那個後端。輸入框下方會顯示
   `Agent mode · works in <資料夾>`。按 **Folders…** 可以設定這個對話的：
   - **Working folder (empty: the default for this conversation)**；
   - **Read-only folders (one full path per line)**：可以自由讀、不能寫的資料夾。

### 11.2 什麼要問你

| 動作 | 規則 |
|---|---|
| 讀寫**工作資料夾裡**的檔案 | 直接做，不問 |
| 讀 **Read-only folders** 裡的檔案 | 直接讀，不問 |
| 讀寫**工作資料夾以外**的檔案 | 卡片：**Allow** / **Allow this folder for this conversation** / **Deny** |
| **執行任何指令** | 一律卡片，顯示完整指令和資料夾；可以選 **Allow <程式> for this conversation** |
| 使用網路工具 | 卡片；可以選 **Allow for this conversation** |
| 改 coding agent 自己在資料夾裡的設定（`.claude`、`.github\hooks`…） | 卡片，只有 **Allow** / **Deny** |
| **讀信** | 這個對話第一次讀信時一張卡片（**Allow for this conversation** / **Deny**）；附件存到工作資料夾的 `mail-attachments\` |
| **寄信** | 卡片顯示完整的收件人、副本、主旨、內文、附件；**Send** / **Keep as draft** / **Cancel**；**每一封都要按一次**，沒有「整個對話都允許」 |

**權限卡片 10 分鐘沒有回答＝Deny；寄信卡片 10 分鐘沒有回答＝保留為草稿，不會寄出。**
草稿在 Outlook 被改過時不會寄出；含有像密碼內容的信會被拒絕。

### 11.3 讀信的範圍（Email the agent may read）

| 欄位 | 範例 | 意思 |
|---|---|---|
| **Folders (one per line, for example Inbox or Inbox/Projects)** | `Inbox` | 可以讀的 Outlook 資料夾 |
| **Days back, at most** | `30` | 最多往回讀幾天（1～365） |
| **Never read mail from (an address or @domain per line)** | `@hr.example.com` | 永遠不讀這些寄件者 |
| **Never read these folders (one per line)** | `Inbox/Personal` | 永遠不讀這些資料夾 |

### 11.4 Knowledge 工具

Agent 模式可以替你建立 Knowledge 沙盒、Pull、Convert、Ingest、跑測試題（寫入動作會跳卡片）。
**Push 到正式 vault 只能在 Knowledge 頁由你按。**

### 11.5 永遠拒絕的事（就算你按了 Allow）

- 修改或讀出權杖、SSH 金鑰、密碼、瀏覽器存的密碼、Windows 使用者環境變數裡的秘密、
  `host.json`、Windows 防火牆等受保護的設定；
- 碰防火牆、登錄檔、`setx`、`cmdkey`、SSH 金鑰、`gh auth`、各 CLI 的 login、`net user` 的指令；
- 寫入 AEP workspace（`agent-sessions` 以外）、Windows 系統資料夾、Program Files；
- 安裝、核准或發布 AEP 的 Skill / Workflow（它只能**送出草稿**，由你在 Capabilities 按
  **Install** 或 **核准**）。

被拒絕時會看到「AEP never changes credentials or protected system settings through the agent …」。

### 11.6 紀錄

所有請求都寫在 `workspace\agent-mode\audit.jsonl`（秘密會遮掉）。每張卡片和每次拒絕都是一筆
Task；每個回合也是一筆 Task（「<後端> agent turn in <資料夾>」，列出問了幾次、拒絕幾次、
自動通過幾次）。卡片也會留在對話紀錄裡。Telegram 不會執行 Agent 模式。

---

## 12. AI 提案、人按套用

你可以直接在對話裡說想改什麼，例如「把 Laya 改成 shadow、門檻 0.9」、「把舊的 coding
Skill 關掉」、「幫我把 sync-test Workflow 加到這台電腦」。Agent 會回一張**變更提案卡片**：

- 標題說明要改什麼；表格 **Setting / Now / After** 只列出會變的欄位；
- **Why: …** 是 Agent 的理由，下面列出要注意的影響；
- 按鈕 **Apply**（套用）和 **Cancel**（取消）。**你按 Apply 之前什麼都不會改。**

| 可以提案的種類 | 內容 |
|---|---|
| Laya | 主機、埠、帳號、模式、門檻、逾時、自動通道 |
| Shared platform | Member Portal URL、Bridge API URL、註冊這台電腦 |
| Natural-language model | Provider、Alias、Gateway URL、模型名稱、秘密的**名稱**與環境變數**名稱** |
| Telegram | 開啟 / 關閉、允許的傳訊者 |
| Workflow 設定 | 某個 Workflow 的固定設定 |
| Capability | 安裝草稿、開啟 / 關閉、移除（可找回）一個 Skill / Workflow |
| 加入共享能力 | 把平台上的某個版本加到這台電腦 |
| 發布 | 把一個已安裝的 Skill / Workflow 送審 |

規則：

- 提案 **30 分鐘後過期**（`Expired: ask the Agent again`）；設定在這段時間被別人改過時，
  **Apply** 會被拒絕，請 Agent 重新提案。
- **永遠不會出現在提案裡**：權杖、密碼、Personal Agent code、API key 等秘密的**值**
  （Agent 只會說「請到 Settings → … 貼上」）；權限（`grants.json`）；共享平台的審核、邀請、
  改別人的權限；會改變東西的 Workflow 執行（走它自己的表單與確認）；重新啟動 Agent Web。
- **Telegram**：只有 Laya、Workflow 設定、開啟 / 關閉一個 Skill / Workflow 可以直接按
  **Apply**；其他種類請到 Agent Web 的 **Tasks → Pending changes** 套用。
- 每個提案和結果都會記成一筆 Task。

---

## 13. Coding agents 與安裝包附帶的 Skills

AEP 和一般 Claude Code 最大的差別：在 AEP 做出來的 Skill 和 Workflow **在 AEP 上就能用**
（Agent Web 會自動產生執行表單，Telegram 會一題一題問），而且你的 coding agent 可以直接
查 AEP 的公司知識庫（Knowledge）。

### 13.1 預設裝了什麼

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
- 權杖不會寫進 agent 的設定檔；`aep-assistant` 每次呼叫時才從 AEP 讀取。
- 沒有安裝的 agent 會顯示 `not found on this computer; skipped`，之後裝了再到 Settings 按
  **Install** 即可。

### 13.2 Settings → Coding agents

每個 agent（**Claude Code**、**Codex**、**GitHub Copilot CLI**）一張卡片，顯示：是否找到
（`found on this computer` / `not found on this computer`）、三個 skills 是否已安裝（installed / out of date /
not installed / your own, kept）、兩個 MCP server 是否 registered。按鈕依狀態顯示 **Install**、**Update** 或
**Reinstall**，以及 **Remove**（移除 AEP 的項目）。改完請**重新開啟**該 agent（Claude Code
重開視窗、VS Code 重新載入）。

也可以用指令（在安裝資料夾）：

```powershell
.\.venv\Scripts\aep-host.exe assets --config host.json connect --for all --user           # 安裝／更新
.\.venv\Scripts\aep-host.exe assets --config host.json connect --for all --user --status  # 查看
.\.venv\Scripts\aep-host.exe assets --config host.json connect --for all --user --remove  # 移除
```

### 13.3 怎麼問

在任何資料夾開 Claude Code / Codex / Copilot，直接說：

- 「幫我做一個 AEP Workflow：每月把上傳的費用 CSV 合併成一份 Excel」
- 「幫我做一個 AEP Skill，讓 AEP Agent 會用 monthly-expense 這個 Workflow」
- 「用 AEP 知識庫查 CMX500 支援哪些 5G NR 頻段，附上出處」

agent 會先重述需求，**不清楚的地方會先問你**（例如 CSV 編碼、日期格式、結果要放哪、
會不會寄信）。回答後它會檢查、送出、測試；任何會改變東西的執行和**所有安裝**都要你在
Agent Web 按核准才會生效（**Capabilities** 頁上方的 **外部 Agent 提交，等待你核准**）。

注意：

- 查知識庫和執行 Workflow 需要 **Agent Web 正在執行**；沒開時 agent 會請你先開 AEP Agent
  捷徑。
- 新的 Skill 在 AEP Agent 重新啟動後才會被使用。

### 13.4 安裝包附帶的 Skills

安裝和更新時，AEP 會一併裝好兩組 Skills。

**開啟的：AEP 正在使用的 Skills**

| Skill | 用途 |
|---|---|
| `company-agent/workflow-author` | 在對話中幫你寫 Workflow |
| `company-agent/knowledge-query`、`engineering/knowledge-query` | 查公司知識庫，回答附出處 |
| `company-agent/market-alignment`、`company-agent/personal-proof` | 市場對照表、個人證明 |
| `engineering/coding` | 程式修改與執行 Python（`coding-change`、`run-python`） |
| `engineering/team-tickets` | Jira team tickets 預覽 |
| `engineering/rs-ncc-improvement-plan-skill` | NCC 改善計畫 |
| `engineering/sales-to-chipset`、`engineering/release-package-guide` | Sales-to-chipset 報表、release package |

它們會用到的 Workflows 也會一起裝好。需要外部設定（Jira、Excel、Outlook…）的，要等設定好
才會執行成功（第 9 章）。

**關閉的：Hermes skill pack（備用）**

51 個從 Hermes agent 移植來的 skills（50 個 MIT 授權，加上僅供公司內部使用的
`business-cards`；作者與來源列在安裝包的 `hermes\NOTICE.md`），預設**全部關閉**，不會干擾
Agent 的選擇。例如：

- 文件：`docx`、`xlsx`、`powerpoint`、`pdf`、`document-to-action-items`、`meeting-action-items`
- 開發：`github`、`systematic-debugging`、`test-driven-development`、`requesting-code-review`、
  `simplify-code`、`spike`、`codebase-inspection`、`node-inspect-debugger`、`dogfood`
- 研究：`arxiv`、`grounded-citations`、`llm-wiki`、`competitor-news-monitor`、`blocked-page-recovery`
- 設計與創作：`ui-ux-pro-max`、`claude-design`、`design-md`、`popular-web-designs`、
  `architecture-diagram`、`humanizer`、`p5js`、`manim-video`…
- 其他：`business-cards`、`google-workspace`、`notion`、`airtable`、`box`、`obsidian`、`maps`、
  `email-inbox-triage`、`himalaya`、`claude-code`、`codex`…

名片請用預設開著的 `engineering/business-cards`（第 4.7 節），不必打開 Hermes 的 `business-cards`。

部分 skill 需要額外的指令或環境變數（例如 `NOTION_API_KEY`），說明寫在 skill 內容開頭的
「AEP note」裡；`teams-meeting-pipeline` 和 `sdlc-review` 需要 Hermes 本身才能用。

**打開或關閉**

1. **Capabilities → Skills**，篩選 **Switched off**，點選要用的 skill（名稱以 `hermes/` 開頭）。
2. 按 **Switch on**。Agent 在 Agent Web **重新啟動後**才會用它。
3. 這台電腦的 Claude Code / Copilot 已裝好 AEP 設定時，同一個 skill 的原始資料夾會同時複製到
   `%USERPROFILE%\.claude\skills\hermes-<名稱>` 和
   `%USERPROFILE%\.copilot\skills\hermes-<名稱>`，在 agent 裡也能用；重新開啟該 agent 後
   生效。你自己已有同名資料夾時，AEP 不會動它。
4. 不用時按 **Switch off**：Agent 不再使用，coding agent 裡的複本也會被拿掉。

更新時，你打開、關掉或移除的 Skills 都會維持原狀；新版本多出來的 Hermes skills 一樣以關閉
狀態加入。

---

## 14. 排程（Schedules）

左邊 **Schedules**，頁面標題 **Scheduled tasks**。排程**只是記下你的意圖**；要你「授權」
（Grant）後才會在無人看管時執行。

### 14.1 新增排程（New schedule）

| 欄位 | 填什麼 |
|---|---|
| **Installed Workflow or Agent Task** | 要排程的 Workflow 或 Agent 工作 |
| **Schedule name** | 英文名稱，例如 `team-tickets-friday` |
| **Repeats** | `Weekly`（勾選星期幾）或 `Daily` |
| **Local time** | 幾點，預設 09:00 |
| **Time zone (IANA)** | 例如 `Asia/Taipei`（預設取瀏覽器的時區） |
| Workflow 的欄位，或 **Runtime inputs (one JSON object)** | 每次執行要用的值（排程表單不能上傳檔案，請填路徑） |
| **Save paused** | 勾選＝先存成暫停 |

按 **Save schedule**，看到 `Saved <名稱>. Grant it below before it can run unattended.`。

### 14.2 授權（Grant）

在 **Schedules** 區的排程卡片：

1. **Highest effect to allow** 選允許的最高影響：
   - `read`：只讀，可以無人執行；
   - `write` / `execute`（例如寫 Excel、存 Outlook 草稿）：還需要這台電腦的授權允許這些能力；
   - `external_side_effect`（寄信、發訊息、發布 release）：**永遠不會自動執行**，每次都會在
     **Waiting for your approval** 等你按。
2. **days (optional)**：授權幾天後自動失效。
3. 按 **Grant**。之後可以 **Revoke grant** 收回。

沒有授權時卡片顯示 `Not granted: due runs stop as needs input.`。其他按鈕：**Pause** /
**Resume**（暫停 / 恢復）、**History**（執行紀錄）。目前**沒有編輯或刪除排程的按鈕**；要改
時請新增一個新的，把舊的 **Pause**。

### 14.3 等你核准（Waiting for your approval）

會對外送出東西的排程，每次到時間都會出現在這裡：按 **Approve and run** 或 **Deny**，可以寫
**note (optional)**。

### 14.4 要有東西去「看時間」

排程要有程式定期檢查才會執行，二擇一：

- 頁面上方會說明目前是否有在檢查（沒有時顯示「This Agent is not checking schedules by itself…」）；
- 讓 Windows 每 15 分鐘檢查一次（在安裝包資料夾的 PowerShell 執行；會替你的帳號建立工作排程
  「Agentic scheduled tasks」）：

  ```powershell
  .\schedule-tick.ps1                    # 登入期間每 15 分鐘
  .\schedule-tick.ps1 -EveryMinutes 5
  .\schedule-tick.ps1 -Remove            # 取消
  ```

- 或請管理員在 `host.json` 設定 `"schedules": {"resident_loop": true}`，讓 Agent Web 執行時
  自己檢查。

排程以**你的帳號**執行（不是 SYSTEM），所以要在你登入時才會跑。電腦關機錯過的，只補跑
24 小時內（`schedules.catch_up_hours`）最近的一次。

### 14.5 中斷的執行

被中斷的執行不會自己重試，排程會顯示為卡住。到 **History** 那一筆選 **Resolve**：
`It did not run` / `It succeeded` / `It failed`，排程才會繼續。排程資料存在
`workspace\schedules.sqlite`。

---

## 15. 管理員：Shared Platform 管理

這一章給**架設和管理共享平台**的人。平台安裝包是另一包
（`aep-shared-platform-preview`），安裝步驟見那一包的 `START-HERE.md`。

### 15.1 Member Portal 的分頁

網址會記住目前分頁（例如 `#tab=review`），重新整理或上一頁都會留在原分頁。管理員登入後
預設在 **Overview**，另外有 **Review queue**（分頁上的數字是等待審核的數量）、
**Registrations (Bridges)**、**All published assets**、**Members & invitations**；一般成員
只看到 **Marketplace**、**My published assets**、**My submissions**、**Applications**。

**Overview** 一頁列出：已註冊電腦（啟用／停用）、成員（啟用／待接受邀請）、各類資產
（Skills、Workflows、Knowledge、Agent profiles、Extensions）的名稱數與版本數、Applications，
以及送審項目（等待／核准／退回／撤回）。點任一個方塊會開啟對應分頁。

**All published assets** 可依種類篩選、切換卡片或表格（表格可排序）；卡片按名稱可看該版本的
完整內容（Workflow 的步驟、參數、權限；Skill 的說明、指令、關鍵字規則）。這裡列出**所有**
已發布的資產，不論你自己能不能使用。

### 15.2 發邀請（每位同事一次）

1. **Members & invitations** → **Invitations**。
2. **Account**：同事安裝時輸入的帳號（`host.json` 的 `device.registered_by`，例如
   `alex.wang`）。只能用英文字母、數字和 `. - _`，**不能用 email**；名稱不一致時同事註冊電腦
   會被拒絕（`device_owner_mismatch`）。
3. **Role**：一般同事選 Member；要能審核的人選 Administrator。**Groups**：團隊名稱（例如
   `engineering`），同團隊的人才看得到「只有我的團隊」的能力。**Minutes**：邀請有效分鐘數
   （預設 1440，也就是一天）。
4. 按 **Create invitation** → **Copy link**，用私訊交給同事，並告訴他 Member Portal URL 和
   Bridge API URL。連結只能用一次；過期或用掉可以再發，不用的按 **Revoke**。

之後要改角色或群組：成員表按 **Role and groups**（會留下紀錄；最後一位管理員不能被改成
Member，`last_administrator`）。

### 15.3 密碼：重設連結與強制登出

成員表的 **Password** 欄顯示 Set / Not set 以及尚未使用的重設連結期限。每一列有：

- **Password reset link**：同事忘記密碼時按，複製連結私訊給他。只能用一次、預設 60 分鐘內
  有效，再發一次會讓上一個失效。同事設好新密碼即登入，他其他瀏覽器的登入會被撤銷（Personal
  Agent code 保留）。停用的帳號不能用。
- **Force sign-out**：電腦遺失、帳號外洩時按。該成員所有瀏覽器登入、所有 session，**連同
  Personal Agent code** 立即失效；密碼不變（若密碼也可能外洩，接著發 Password reset link）。

規則：密碼至少 12 字元、不可包含帳號名稱或常見密碼；同一帳號錯 5 次鎖 15 分鐘，同一來源位址
錯 20 次鎖 15 分鐘；重啟平台會清除鎖定計數。登入失敗一律只回 `authentication_failed`。平台
只保存密碼的雜湊值。

唯一的管理員忘記密碼時：在 `platform.json` 的 `invitations` 加一張給**另一個**管理員帳號的
啟動邀請，重啟後用它登入，再替原帳號發 Password reset link。

### 15.4 審核（Review queue）

1. **Review queue** 預設只列出等待審核的項目（也可切到全部、已核准、已退回、已撤回）。
2. 按 **View** 看完整內容、要求的權限與風險，以及上一個已發布版本。
3. 按 **Approve and publish**（會問「What did you check?」，和核准一起保存）或 **Reject**
   （會問「Why is it rejected?」，送出的人看得到）。
4. 核准後才會出現在其他人的 Library。`platform.json` 的 `allow_self_review`（**預設 `true`**）
   允許管理員審核自己送出的項目；驗證完成後建議改成 `false`。

### 15.5 誰能用、共同編輯、轉移

在 **My published assets**，或管理員在 **All published assets** 的任何資產：

- **Who can use it**：改成「只有團隊」或「全公司」，也可以加指定的帳號或群組。已發布的版本
  內容不會改變；收回權限不會移除別人已安裝的版本。
- **Owner and co-editors**：加入 **co-editor**（帳號名稱），讓他能發布新版本。
- **Transfer owner**：把擁有者轉給某人或某團隊（會先確認）。
- 每一列顯示「May publish new versions」：擁有者、擁有團隊的成員與 co-editors。
- 管理員在 **All published assets** 另外有 **Details**（看完整內容）和 **Deprecate**
  （標示為不再建議使用）。

### 15.6 已註冊的電腦（Registrations (Bridges)）

列出所有已註冊的電腦、所屬帳號、token 到期日、**Last seen**（最後一次呼叫 Bridge API 的時間
與動作）與選取的能力數。電腦遺失或同事離開時按 **Disable**，該電腦的 token 立即失效，也不能
再自行註冊。

### 15.7 啟動、更新與資料

- 啟動：`start-platform.cmd`；要開機自動啟動，建立排程工作「AEP Shared Platform」（15.8）。
  帳號、已發布的能力、審核紀錄與已註冊的電腦都存在 `workspace\registry.sqlite`，重啟不會遺失。
- 每次重啟會產生 `invitation-links-*.json`（`platform.json` 裡尚未使用的啟動邀請）；**內容是
  登入憑證，不要轉寄或提交到 Git**。
- 更新：用新版安裝包重新執行 `install.cmd`，`platform.json` 會保留。

### 15.8 開放給公司網路（TLS、自簽憑證、防火牆、自動啟動）

預設只監聽本機（127.0.0.1），其他電腦連不到。完整指令在 Shared Platform 安裝包的
`START-HERE.md` 第 6 節，步驟如下（都在平台電腦上、以執行平台的帳號操作）：

1. **產生自簽憑證**：用 Git for Windows 的 `openssl` 在平台電腦上產生憑證與私鑰，SAN 寫這台
   電腦的 IP 和名稱（例如 `IP:172.25.228.141,DNS:OPENLAB01`），放在安裝目錄外的
   `%LOCALAPPDATA%\AgenticEngineeringPlatform\shared-platform-tls\`，私鑰只給這個帳號讀取。
   **私鑰不可複製到別台電腦、寄出或提交到 Git**。
2. **`platform.json`**：`listen_host` 改成這台電腦的 IP；`tls_certificate_path`、
   `tls_private_key_path` 指向兩個檔案（**非本機一律要求 HTTPS**）。`control_port`
   （Bridge API）和 `member_port`（Member Portal）不能相同，被其他程式占用時（Windows socket
   `10048`）換一個未使用的埠；不要直接停掉不明程序。
3. **取得指紋**：`aep-platform certificate-fingerprint --config <platform.json>` 印出
   `SHA-256 fingerprint: …`；平台啟動時也會印 `Certificate SHA-256: …`。
4. **防火牆**：新增輸入規則「AEP Shared Platform」，TCP，兩個埠，只開 **Domain／Private**
   設定檔；公司網路在這台電腦上被判定為「無法辨識的網路」（Public）時，改成只對那張網卡開放
   （所有設定檔 + `-InterfaceAlias`），不要對所有 Public 網路開放。
5. **開機自動啟動**：排程工作「AEP Shared Platform」，開機時以平台帳號執行
   `start-platform.cmd`（S4U，沒人登入也會跑），每 5 分鐘檢查一次、平台結束了就重新啟動；
   紀錄在安裝包資料夾的 `platform.log`。**更新前**先 `Disable-ScheduledTask`，裝完再
   `Enable-ScheduledTask` 與 `Start-ScheduledTask`。
6. **交給同事**：兩個 `https://` 網址和憑證指紋，用私訊或團隊公告這種可信的管道。同事照第 10 章
   10.1.1 在 Agent Web 比對指紋並按 **Trust this certificate**；瀏覽器的警告也在那裡說明。

更換憑證（到期、私鑰外洩、改用公司正式憑證）：重新產生、重啟平台、公告新指紋；每位同事在
Agent Web 重做 10.1.1（舊的指紋會被拒絕，訊息會列出新舊兩個指紋）。改用公司 CA 簽發的憑證後，
Windows 已信任它，同事按 **Forget** 即可。

---

## 16. 常見問題與錯誤代碼

### 16.1 常見問題

**Agent 回答「需要更多資訊」或說不會做？**
沒有安裝相關的 Skill / Workflow 時，Agent 不會亂猜。到 **Capabilities** 看有沒有、是不是被
關掉了（**Switched off**），或從 **Share Platform Library** 安裝。

**新裝的 Skill 沒有被用到？**
Skill 在 Agent Web 重新啟動後才生效。關掉 Agent Web 再用捷徑打開。（重新啟動前先到
**Tasks** 確認沒有正在跑的工作，重啟會中斷它們。）

**怎麼重新啟動 Agent Web？**
先到 **Tasks** 確認沒有正在跑的工作，再停止 Agent Web，然後雙擊 **AEP Agent** 捷徑。捷徑只會
打開已經在執行的 Agent Web，不會重新啟動它；停止的一行 PowerShell 指令見安裝手冊第 4 節
「停止／重新啟動 Agent Web」（或在工作管理員結束 `aep-host`）。安裝或更新後畫面顯示
「Agent Web 正在執行：請重新啟動才會用到新的設定」時，也是這樣做。

**安裝時說 `This bundle requires 64-bit Python 3.12`？**
你的 `python` 是別的版本（例如 3.14）。照訊息裡列出的 3.12 路徑加 `-PythonExe "<路徑>"` 重新執行
`install.cmd`，或安裝 64 位元 Python 3.12；見安裝手冊第 9 節。

**對話紀錄存在哪？會被別人看到嗎？**
存在這台電腦的 `workspace\`，只有這台電腦能開 Agent Web。用 PUBLIC 後端的對話內容會送到那個
外部服務。

**按任何按鈕都出現「This page is from an earlier start of Agent Web…」？**
Agent Web 重新啟動過，舊分頁的頁面金鑰失效了。關掉舊分頁，用 **AEP Agent** 捷徑重新打開。

**可以兩台電腦用同一個帳號嗎？**
可以，各自安裝、各自 **Enroll this PC**；兩台電腦名稱相同時，安裝時用 `-BridgeId` 改名。

### 16.2 錯誤代碼

| 代碼 / 訊息 | 意思 | 處理方式 |
|---|---|---|
| `needs_input` | 缺參數，或沒有對應的 Skill / Workflow | 補上資訊；或安裝相關能力 |
| `unknown_skill` | 指令對不到任何已安裝的 Skill | 檢查名稱；到 Capabilities 確認已安裝並開啟 |
| `permission_denied` | 這台電腦沒有被授權執行這個能力 | 請管理員確認授權（`grants.json` 或平台上的選擇） |
| `workflow_upload_outside_store` | 上傳欄位的值不是透過上傳得到的檔案 | 用表單的上傳按鈕重新上傳 |
| `isolated_root_unmarked` | release 隔離資料夾沒有正確的標記檔 | 見 9.2 |
| `workbook_open` | 要寫入的 Excel 檔正開著 | 關掉 Excel 檔再執行 |
| `stale`（AI 提案） | 提案後設定被改過 | 請 Agent 重新提案 |
| `not_a_maintainer` | 你不在這個 vault 的 `maintainers` 裡 | 請 vault 負責人把你加進去 |
| `path_too_long` | Knowledge 沙盒路徑超過 Windows 限制 | 把 `sandbox_root` 改成較短的資料夾 |
| `unresolved_conflicts` | Push 前還有衝突沒選邊 | 按 **Check conflicts** 逐一選擇 |
| `remote_not_isolated` | release 設定填了 GitLab 網址，但沒開 **Use the real release repository (GitLab)** | 開啟該設定，或改用本機 repo |
| `path_outside_isolated_root` | 工作副本、inbox 或本機 repo 不在隔離資料夾裡 | 見 9.2 |
| `egress_approval_missing` | Laya 沒填核准編號 | 填 **Owner approval reference** |
| `device_owner_mismatch` | Portal 帳號和這台電腦的擁有者不同 | 見 10.6 |
| `publisher_not_authorized` | 名稱屬於別人 | 請擁有者加你為 co-editor |
| `platform_unreachable` | 連不到共享平台 | 檢查網址與網路 |
| `session_expired` | Portal 閒置太久 | 重新整理 |
| `authentication_failed` | 帳號或密碼錯誤（或被鎖） | 等 15 分鐘或請管理員重設 |
| `last_administrator` | 不能把最後一位管理員改成 Member | 先指派另一位管理員 |
| `invalid_request`（建立邀請） | 帳號名稱有 `@` 等符號 | 只用英文字母、數字和 `. - _` |
| `401`（模型） | 公司權杖過期或金鑰不一致 | 見 1.6 |
| `405 Method Not Allowed`（模型） | gateway 模型設定錯誤 | 見 1.6 |

安裝與更新的錯誤見 `INSTALL.zh-TW.md` 第 9 節。

---

## 17. 名詞解釋

| 名詞 | 說明 |
|---|---|
| **AEP Agent / Personal Agent** | 裝在你電腦上的 Agent，只聽你（和你允許的人）的話 |
| **Agent Web** | Agent 的網頁介面，只有這台電腦能開 |
| **LLM gateway** | 這台電腦上的小程式，把 Agent 的請求轉給公司的語言模型 |
| **Skill** | 教 Agent 某件事怎麼做的說明書：何時用、用哪些指令或 Workflow |
| **Workflow** | 固定步驟的自動化程序，有參數表單，可以手動、在對話中或排程執行 |
| **Capability（能力）** | Agent 可以使用的東西的統稱（Skill、Workflow、Knowledge、底層工具） |
| **Draft（草稿）** | 做好但還沒安裝的 Skill / Workflow，要你按 **Install** 才生效 |
| **Knowledge** | Agent 查詢並附出處的知識庫版本 |
| **Vault** | 共享的知識庫資料夾（drop、raw、wiki、規則、測試題） |
| **Sandbox（沙盒）** | 你自己的 vault 工作副本；Push 前不影響正式 vault |
| **Raw** | 原始檔轉成的 Markdown 文件 |
| **Ingest** | 依規則把 Raw 文件寫成 wiki 頁面 |
| **Push** | 把沙盒合併回正式 vault（測試不退步才寫入） |
| **Shared Platform（共享平台）** | 團隊共用的 Skill / Workflow 市集與審核中心 |
| **Member Portal** | 共享平台的網頁（Marketplace、送審、管理） |
| **Bridge** | 一台已在共享平台註冊的電腦（你的 Agent 那一端） |
| **Bridge ID** | 這台電腦在平台上的名稱，預設 `bridge-<電腦名稱>` |
| **Bridge API** | Bridge 和平台溝通的網址 |
| **Bridge token** | **Enroll this PC** 時取得、讓這台電腦從平台讀取與安裝的憑證（90 天） |
| **Personal Agent code** | 從 Member Portal 取得、讓 Agent 以你的身分操作平台的代碼（30 天） |
| **Invitation（邀請連結）** | 管理員發的一次性連結，用來建立帳號並設定密碼 |
| **Co-editor** | 被擁有者允許發布同名新版本的人 |
| **registered by** | 這台電腦的擁有者帳號（`host.json` 的 `device.registered_by`） |
| **host.json** | 這台 Agent 的設定檔（在安裝資料夾）；**不放任何權杖** |
| **SecretRef** | 秘密的「名稱」，實際的值放在 Windows 環境變數裡 |
| **MCP server** | 提供工具給 AI agent 的標準介面 |
| **Agent mode** | 讓 Claude Code / Copilot 在對話的工作資料夾裡動手做事，超出範圍要你按卡片 |
| **Change proposal（變更提案）** | Agent 提出、要你按 **Apply** 才生效的設定變更 |
| **Shadow mode** | Laya 只在背景記錄選擇、不影響回答的模式 |
| **Hermes skill pack** | 安裝包附帶、預設關閉的 51 個備用 skills |
| **Grant（授權）** | 允許某個能力或排程執行的紀錄 |
