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

- [ ] **開啟 Agent Web**：雙擊桌面的 **AEP Agent** 捷徑（第一次約 10～30 秒）。
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
- 目前**沒有**中途停止回答的按鈕；不想等可以開新的 session。

### 4.2 選擇模型後端

輸入框下方的下拉選單（**Conversation backend**）：

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

1. 表單會先帶入你在句子裡已經說的值（例如 `chipsetId=kt326`）。
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

### 4.6 在 Telegram 執行

設定好 Telegram（第 8 章）後，傳 `/run <名稱>` 或「執行 <名稱>」，bot 會一題一題問：
選項是按鈕，多選按完選項後按 **Done**；上傳欄位請把檔案當「文件」傳送，傳完打 `/done`
（選填可以 `/skip`）；有身分欄位時會先問「Same as last time? …」按 **Yes** 或 **Change**。
最後會列出所有值，**會改變東西的 Workflow 一定要按確認才會執行**。缺少的 Workflow
設定只能在 Agent Web 填。

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

### 6.7 寫到哪裡

| 動作 | 寫入 |
|---|---|
| Pull、Add files、Convert、Ingest、改規則、改題目 | 只寫你的沙盒（`sandbox_root` 底下） |
| Push | 正式 vault（`root`），先備份被替換的檔案，並記錄誰從哪個沙盒推的 |
| Refresh the Agent's Knowledge | 這台 Agent 的本機 Knowledge 新版本（`host.json` 會先備份） |
| Reviews 的 Accept | 開 review 沙盒、缺口清單或 issue 紀錄；不會直接改 vault |

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
- 執行 Workflow：`/run <編號或名稱>` 或「執行 <名稱>」，見 4.6 節。過程中 `/skip` 用預設值、
  `/cancel` 取消；表單 15 分鐘沒完成會失效。
- `/help`（或 `/start`）：說明用法。
- `/new`：開一個新的對話（忘掉之前的檔案）。
- `/status`：這台電腦的狀態。
- `/<skill> <指令>`：直接執行某個 Skill 的指令。
- 傳檔案或照片並加上說明文字，Agent 會處理那個檔案。
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
| 「The answer could not be delivered here …」 | Telegram 拒絕了那則訊息（太長或太頻繁）；到 Agent Web 看同一個結果 |
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

### 9.3 個人 Workflow 不在安裝包裡

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

### 10.1 跟管理員要三樣東西

1. **你的帳號名稱**：必須和安裝時輸入的帳號**完全一樣**（例如 `alex.wang`）。只能用英文
   字母、數字和 `. - _`，**不要用 email**。不確定時看 **Settings → Shared platform** 卡片
   上「registered by」的值。
2. **Member Portal URL**（例如 `https://platform.example:8776`）。
3. **Bridge API URL**（例如 `https://platform.example:8775`）。

管理員會用你的帳號名稱發一張邀請，私訊給你一個邀請連結。

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
2. 打開 Agent Web → **Settings → Shared platform**：
   - **Member Portal URL**、**Bridge API URL**：填 10.1 拿到的兩個網址；
   - **Personal Agent code**：貼上剛剛的代碼；
   - 按 **Save**。代碼只存在你的 Windows 使用者環境裡，不會寫進任何檔案，也不會再顯示。

### 10.4 註冊這台電腦（Enroll this PC，只做一次）

在同一張卡片按 **Enroll this PC**：

- 成功時顯示 `Enrolled as <bridge-id>` 和 token 的到期日。
- 這一步只是讓這台電腦**可以從平台拿東西**，不會安裝任何能力，也不會改變這台電腦能執行
  什麼。
- 再按一次只會換一個新 token（舊的失效），不會重複註冊。token 快到期時再按一次即可。
- 顯示 **The Bridge API URL did not answer** 時，什麼都沒有存，請檢查 Bridge API URL。

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

- 啟動：`start-platform.cmd`（開機後不會自動啟動）。帳號、已發布的能力、審核紀錄與已註冊的
  電腦都存在 `workspace\registry.sqlite`，重啟不會遺失。
- 每次重啟會產生 `invitation-links-*.json`（`platform.json` 裡尚未使用的啟動邀請）；**內容是
  登入憑證，不要轉寄或提交到 Git**。
- 更新：用新版安裝包重新執行 `install.cmd`，`platform.json` 會保留。

### 15.8 開放給公司網路（TLS）

預設只監聽本機（127.0.0.1），其他電腦連不到。開放時編輯安裝目錄的 `platform.json`：

1. `listen_host` 改成這台電腦的固定 IP 或 DNS 名稱；
2. 設定 `tls_certificate_path` 與 `tls_private_key_path`（**非本機一律要求 HTTPS**，沒有 TLS
   會被拒絕）；
3. Windows 防火牆只對預期的網路開放 `control_port`（Bridge API，預設 8765）與 `member_port`
   （Member Portal，預設 8766；兩個不能相同）；
4. 重啟後把兩個 `https://` 網址給同事。

出現 Windows socket `10048` 或 port occupied：那個埠已被使用。先確認是不是正在運作的舊平台，
不要直接停掉不明程序；否則替兩個入口各選一個未使用的埠，更新 `platform.json` 後重啟。
使用自簽憑證時，同事的 Agent 需要信任該憑證（Agent 端的信任設定尚在開發中）。

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
關掉背景的 Agent Web 視窗（或在工作管理員結束 `aep-host`），再雙擊 **AEP Agent** 捷徑。

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
