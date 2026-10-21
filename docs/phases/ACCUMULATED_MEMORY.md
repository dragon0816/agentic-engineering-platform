# 可累積的記憶管理（設計稿，待 owner 確認）

Owner 討論：2026-10-20。狀態：**design approved 2026-10-20（決定見 §10）；M1 implemented 2026-10-20（見 §11「M1 as built」）；M2 implemented 2026-10-20（見 §12「M2 as built」）；M3 implemented 2026-10-21（見 §14「M3 as built」）；M4 implemented 2026-10-21（見 §15「M4 as built」）；M5 implemented 2026-10-21（見 §16「M5 as built」），M6 起依 §9 進行。** 架構層級的決定，依 `CLAUDE.md`
先討論、owner 確認方向後才開始實作。已決定的部分：採用 **混合式**（集中管理、分開擁有）。

## 1. 為什麼需要

名片與組織圖的 live test 顯示：

- 每次「產生組織圖」都從頭讀信、整理簽名檔，浪費時間與 token，也重複讀同一批信。
- 使用者在對話中說的規則（例如「執行時不需要問是否包含在職人員」）沒有地方保存，
  Agent 只能在當輪口頭答應，甚至說出「規則我已改成」這種沒有工具支持的話。
- Skill／Workflow 產生的結果（聯絡人、匯報關係、同步到哪裡）應該越用越完整。

目標：讓 Skill／Workflow 驅動、可累積的資料與記憶，**集中管理、分開擁有**，每一筆都有來源、可修改、
可復原，而且日常管理成本接近零。

## 2. 紀錄與記憶的界線

| | 紀錄（records） | 記憶（memory） |
|---|---|---|
| 是什麼 | 原始發生的事：對話、Workflow／capability 執行、coding 過程 | 從紀錄整理出、之後會重複用到的東西 |
| 例子 | 「10/20 傳了一張名片」 | 「范仁杰的 email 是 …」、「組織圖不問是否含離職」、「wnc.com.tw 已整理到 10/19」 |
| 保存 | 依保留期限，到期清掉 | 長期保存，直到使用者刪除或過期規則處理 |
| 給誰用 | 使用者查詢、系統分析（經驗回顧、Skill 建議） | Agent 下次直接用 |
| 現有元件 | `conversations`（每段最多 `MAX_STORED_MESSAGES = 100`）、`telemetry.sqlite`、Workflow journal、coding evidence | 名片 `cards.db`（第一個實例） |

各類紀錄的處理：

- **一般對話**：留作紀錄。使用者在對話中說的事實或規則，**經使用者確認後**才成為記憶。
- **Skill／Workflow 執行**：執行紀錄留作紀錄；工具產生的確定性結果（存入的聯絡人、同步進度）
  直接成為記憶，因為是程式產生的，不是模型推測。
- **Coding 對話**：過程留作紀錄。學到的做法不存成零散記憶，而是經由既有的
  經驗回顧（`docs/phases/EXPERIENCE_REVIEW.md`）與 Skill 建議（`docs/phases/SKILL_SUGGESTIONS.md`）
  變成 Skill 的規則，使用者核准才生效。

原則：**紀錄會過期，記憶要有來源。** 記憶項目連回來源（conversation message id、email message id、
run id、圖片 hash）；來源被刪時記憶保留，標「來源已刪除」。

## 3. 混合式架構：集中管理、分開擁有

### 3.1 記憶空間（memory space）

每個 Skill／Workflow 在自己的 manifest 宣告它持有的記憶空間，空間名稱就是它的 identity
（例如 `engineering/business-cards`）。宣告內容：

- **種類**：`entities`（人、公司、關係）、`sync_state`（來源同步進度）、`preferences`（使用者偏好）、
  `facts`（其他事實）。
- **schema**：欄位與驗證（與 Knowledge Strategy 的 `bi.schema` 一樣是資料，不寫死在 Harness）。
- **敏感度**（沿用 `PUBLIC / INTERNAL / CONFIDENTIAL / RESTRICTED`）與**保留期限**。
- **跨空間讀取**：允許哪些其他 Skill 唯讀（例如寫信 Skill 唯讀聯絡人）。

註冊是開發者在 manifest 寫的幾行宣告，使用者感覺不到。沒有註冊，Agent Web 拿到的是看不懂的資料：
無法顯示、無法驗證修改、不知道何時清掉、不知道誰能讀。

### 3.2 共用基礎能力（每個空間自動擁有）

由集中的 Memory Service（Host 內，每個 actor 一份）提供，抽自名片功能已經驗證過的做法：

- **欄位來源**（`field_sources`，依 Knowledge Strategy ADR-K11）：origin（import／tool／user／agent）、
  set_by（Host 填 `<actor> via <channel>`，模型不能自填）、set_at、reason。
- **修改歷史與復原**（`history`、`undone`，以 change id 分組）。
- **待確認提議**（`proposals`）：自動來源與使用者值衝突時不覆蓋，變成提議。
- **每人隔離**：每個 actor 一份；同一台電腦的其他成員看不到。

### 3.3 集中服務直接提供的兩種通用資料

- **同步進度（sync state）**：每個來源上次處理到哪裡，例如
  `{space, source: "mail:Inbox", key: "wnc.com.tw", last_message_date, last_message_ids, extractor_version}`。
- **偏好（preferences）**：使用者說過的規則，按一下才存（見 §5）。

不讓每個 Skill 各自發明一套。

### 3.4 存取規則

- 模型只能透過 Skill 的工具存取記憶，**沒有「讀取全部記憶」的工具**。
- 寫入必須先在 manifest 宣告為該空間的**貢獻者**，而且只能寫「觀察」（§3.8），不能直接改值；
  讀取必須宣告為**讀取者**。兩者安裝時都看得到。
- Bridge 授權與既有 grants 照常適用；憑證與受保護設定不在任何記憶空間內。

### 3.5 儲存

- 每個 actor 一個記憶資料庫（例如 `<workspace>/memory/<actor-key>/memory.sqlite`），各空間分開
  命名的資料表；名片的 `cards.db` 遷移成第一個空間（保留既有資料與歷史）。
- 儲存介面與 Knowledge Strategy 的 `KnowledgeStorageBackend`（ADR-K2）對齊：個人記憶與團隊知識
  是同一件事的不同範圍。這讓個人整理的聯絡人與組織圖，日後可經審核**提升**成團隊 BI 知識
  （BI Schema 的 Account／Ecosystem 與名片的公司、人高度重疊），而不必重建。

### 3.6 生命週期

- Skill 被關閉：資料保留、變唯讀。
- Skill 被移除：資料保留，在記憶頁標「無主」，由使用者決定是否刪除。
- 匯出：每個空間可匯出（JSON），刪除會留下一筆刪除紀錄（不留內容）。

### 3.8 多來源共同填充（owner 討論 2026-10-20）

客戶公司組織圖、chipset 開發 readiness 這類資訊，會由多個 Skill、Workflow 與來源（email 簽名檔、
名片、C4C、口頭）一起填。因此：

1. **空間以領域為單位**，不屬於單一 Skill：例如 `customers/org-chart`、`projects/chipset-readiness`。
   每個空間有一個**管理者 Skill**（定義 schema 與合併規則），另宣告多個**貢獻者**與**讀取者**。
2. **貢獻者只寫觀察**：每筆是帶證據、帶時間的主張（來源、日期、來源 ref），只會累加、不會被改寫。
   名片的 `observations`（每次掃描都保留）就是這個做法的第一個實例。
3. **目前的值由合併規則算出**。合併規則是空間 schema 的一部分，**可依欄位設定來源優先序**，
   不寫死在程式裡。預設（owner 2026-10-20）：

   | 欄位 | 規則 |
   |---|---|
   | 公司正式名稱 | **名片為準**。C4C 是人工填寫、可能有誤；不一致時變成待確認 |
   | 客戶編號（C4C Account ID 等外部 ID） | 只作為對應用的外部 ID（見第 4 點），不決定名稱 |
   | 職稱、部門、處、事業群 | **以最新的證據為準**（名片、簽名檔、C4C 皆可），較舊的不能覆蓋較新的 |
   | 匯報關係 | 只有使用者口頭說、或有明確證據的才畫實線；推論一律虛線 |
   | 使用者親口說的值 | **只有新證據能動它**（owner 決定 2026-10-20，見下方「新證據」）：舊證據一律不理會、不提示；新證據對**組織欄位**（職稱、部門、處、事業群、學位、電話／分機／手機／傳真、地址）**直接改成新值**（「換部門, 或換職位, 就修改那一筆資料」；寫 history、可復原；讀值不確定時只提議）；對 **email**（身分鍵，模型多次讀錯）與其他欄位只變成待確認、不覆蓋 |

   **新證據**（owner 決定 2026-10-20，取代「較新的不同證據變成待確認」）：
   - **名片沒有證據日期**。新不新只看**名片圖片**：對這個人**從沒看過的圖片 hash** 是新名片＝新證據；
     **同一張圖片重掃**是舊證據。名片的掃描日期不拿來比較。沒有圖片的名片（以及匯入的 Hermes 舊名片）
     沒有穩定的身分可判斷，一律當作**不是**新證據。
   - **email 簽名檔**：信的**寄出日期**晚於使用者**最後一次修改該欄位**的那一天，才是新證據（同一天或較早
     都不是）；寄出日期也決定同步視窗（§4）。
   - 之後其他沒有日期的來源，只有具備穩定身分（例如圖片 hash）時才比照名片；否則一律當作不是新證據，
     因為無法分辨是不是使用者已經看過、改正過的內容。
   - **不是**使用者設定的欄位，不同的讀值照原本的規則（最新證據、優先序）處理。
   - 規則是資料：`MergeRules.undated`（`card`、`import`）與每個欄位的 `user_conflict`
     （組織欄位 `take_if_newer`，email、公司名稱與其他欄位 `propose_if_newer`）。

4. **外部 ID 對照**：同一個人或公司在各來源有不同代碼（email、C4C ID、名片圖片 hash、姓名＋公司）。
   空間維護一張對照表；對不上時**不自動合併，先問使用者**（自動合併的條件見 §10 第 7 題）。
5. **來源類型與可信度**：系統紀錄（C4C 等，由人填寫，可信度不預設為最高）、文件（名片、簽名檔）、
   使用者口頭、模型推論。可信度影響合併規則與組織圖的實線／虛線。
6. **隨時間變化的狀態**（例：chipset readiness）：每個項目的觀察帶時間點；目前狀態＝每項最新的有效
   觀察；支援時間點查詢（「上週五的 readiness」）與趨勢。來源互相矛盾（Jira 說已解決、email 說還沒）
   時變成待確認，同時列出兩邊證據。
7. **外部系統預設唯讀**：AEP 不回寫 C4C、Jira 等；回寫另行設計且需使用者核准。

### 3.9 筆記（notes；owner 決定 2026-10-20）

筆記是另一種記憶：自由文字的結論、想法、會議重點、待查事項。與其他種類的差別：

| | 事實／實體 | 偏好 | 筆記 |
|---|---|---|---|
| 內容 | 結構化欄位 | 做事的規則 | 自由文字 |
| 誰寫 | 工具與來源（觀察） | 使用者說的規則，按一下才存 | 使用者一鍵存；或 Agent 提議、使用者確認 |
| Agent 怎麼用 | 合併規則算出目前值 | 使用該 Skill 時自動套用 | **只在需要時查詢**，不自動影響行為 |

- **怎麼記**（owner 決定）：**對話中一鍵存**。每則回答旁有「存成筆記」，也可只選取其中一段存。
- **Agent 主動提議**（owner 同意）：Agent 判斷某個結論值得記，可跳「要存成筆記嗎？」卡片，
  **每段對話最多提議一次**。
- **每則筆記**：連回來源（conversation、message id，點一下回到當時上下文）；標籤；關聯實體
  （例如公司、人、chipset 專案），在組織圖或個人卡片上可看到相關筆記；建立與修改時間、修改歷史、可復原。
- **Agent 怎麼用**（owner 決定）：筆記**不自動注入**每一輪。只在以下情況透過筆記工具查詢，
  回答時標出引用了哪一則：
  1. Skill 或 Workflow 在 manifest 宣告讀取筆記（例如組織圖讀取關聯公司的筆記）；
  2. 使用者提到「之前有記過什麼」這類說法時。
- **管理**：記憶頁多一個「筆記」區塊，可搜尋、依標籤篩選、修改、刪除；可匯出 Markdown。
- **延伸**：有價值的筆記可**提升成團隊知識**（送進 Knowledge 投遞流程，經審核成為 Wiki 內容）。
- **階段**：與偏好一起放在 M3（第一版）。

### 3.10 被捨棄的替代方案

- **全部集中在一個通用記憶庫**（筆記或 key-value）：聯絡人、匯報關係這類結構化資料會失真，
  沒有規則地誰都能讀，一個漏洞就全部外洩。
- **各 Skill 完全自管**：散落各處，使用者找不到也刪不掉；來源、歷史、復原各做一套、品質不一；
  跨 Skill 重用與提升成團隊知識都做不到。

## 4. 增量處理：以組織圖為例

使用者說「WNC 組織圖」時：

1. 查同步進度：`wnc.com.tw` 在 `mail:Inbox` 上次整理到哪一天。
2. 只掃那天之後的新信，並以已處理的 message id 排除重複；第一次沒有紀錄，依讀信設定掃滿範圍
   （目前 Inbox、180 天）。
3. 新人列為候選（使用者確認才存）；與使用者值衝突的變成待確認。這兩條規則沿用名片功能現況。
4. 更新同步進度，再產生組織圖。

細節：

- **讀信設定照樣適用**：同步進度只能讓範圍變小，不能超出設定。
- **擷取規則改版**（`extractor_version` 變更）時把進度歸零，讓舊信用新規則重整一次，並在回覆中說明。
- **手動重來**：「重新整理 WNC 的簽名檔」從頭掃。
- 每人各自一份。

## 5. 偏好（preferences）

- 使用者在對話中說出一條規則時，Agent 跳一張小卡片：「要把這條記成『名片／組織圖』的偏好嗎？」
  按一下才存（符合「AI 提案、人按套用」，沿用 `docs/phases/AI_PROPOSED_CHANGES.md` 的卡片機制）。
- 偏好綁定在記憶空間（Skill）上，之後使用該 Skill 時由 Host 注入給模型，不再詢問。
- 存偏好時檢查與既有偏好是否矛盾；矛盾時先問。
- Agent Web 可查看、修改、刪除所有偏好。
- Agent 不再聲稱「規則我已改成」：沒有工具保存時，就提議存成偏好（`no_unbacked_action_claim`
  已擴充辨識這類說法）。

## 6. 記憶管理頁（Agent Web）

不列出所有對話紀錄讓使用者逐筆管理。依「Agent 知道你什麼」組織：

| 區塊 | 內容 | 使用頻率 |
|---|---|---|
| 待確認 | 跨所有空間待確認的項目（email 不一致、新的簽名檔聯絡人…） | 主要接觸點，但平常在對話中就順手處理 |
| 偏好 | 設定過的規則，一條一行，可改可刪 | 偶爾 |
| 資料 | 每個空間一行（例：聯絡人 3 人，最後更新 10/20），點進去是該 Skill 自己的檢視 | 需要時 |
| 同步進度 | 每個來源讀到哪裡，可「重新整理」 | 幾乎不用 |
| 紀錄 | 對話與執行紀錄的保留期限、刪除 | 設定一次 |

日常管理成本接近零：需要使用者決定的事，在對話當下一句話或按一下就處理；這一頁是偶爾檢查用。

## 7. 管理不好會出現的問題

- **錯的事實擴散**：錯的 email 被用在多封草稿，離職的人仍在組織圖上。
- **偏好矛盾或被遺忘**：Agent 行為奇怪，使用者想不起是哪條規則造成的。
- **推論被當成事實**：「職稱較高」被當成「是他的主管」。
- **資料膨脹**：檢索雜訊、token 成本與延遲上升。
- **隱私**：敏感資料被無限期保留。

## 8. 提升管理品質的工具

1. **來源與可信度**：每筆標證據或推論（名片功能已有）。
2. **新鮮度**：各種類有過期規則，例如聯絡人 12 個月沒再出現，就問「是否仍在職」。
3. **衝突偵測**：偏好矛盾、事實不一致，都變成待確認。
4. **每晚健康檢查**：擴充既有夜間經驗回顧，找出重複、過期、矛盾、沒在用的偏好、無主空間，
   產生建議卡片。
5. **「為什麼這樣做」**：回答標出用了哪條偏好或哪筆記憶，錯了可一鍵修正。
6. **寫入門檻**：工具產生的確定結果自動存；模型推論與使用者規則需要按一下確認。
7. **預設保留期限、可匯出、可刪除。**

## 9. 分階段計畫（待確認）

| 階段 | 內容 | 完成條件 |
|---|---|---|
| M1（**implemented 2026-10-20**，§11） | Memory Service 骨架：空間註冊（manifest 宣告）、共用 provenance／history／undo／proposals、每人隔離；名片 `cards.db` 遷移成第一個空間 | 名片既有測試全過、資料無損遷移 |
| M2（**implemented 2026-10-20**，§12） | 同步進度 + 組織圖增量整理 | 第二次組織圖只讀新信；改版時正確重整 |
| M3（**implemented 2026-10-21**，§14） | 偏好：確認卡、注入、矛盾檢查；筆記：一鍵存、Agent 提議（每段對話最多一次）、依宣告或「之前記過什麼」查詢 | 對話中說的規則按一下後生效、之後不再詢問；回答旁一鍵存筆記，並能被查詢引用 |
| M4（**implemented 2026-10-21**，§15） | Agent Web 記憶頁 | 五個區塊可用；E2E 與瀏覽器測試 |
| M5（**implemented 2026-10-21**，§16） | 品質工具：新鮮度、每晚健康檢查、「為什麼這樣做」 | 健康檢查產生建議卡片 |
| M6（第二版） | 跨空間宣告讀取、提升成團隊知識（Shared Platform 審核發布） | 一筆聯絡人經審核成為 BI Account |

## 10. Owner 決定（2026-10-20）

1. 問組織圖時**自動先增量整理新信**：要（新人仍需使用者確認才存）。
2. 每晚背景整理：**不要**。
3. 偏好「按一下才存、Agent Web 可管理」：好。
4. 第一版 **M1–M4**，M5 隨後，M6 第二版：好。
5. 與 Knowledge Strategy 的關係：**另立本文件並互相引用**，前提是不把資料弄亂（owner 的疑慮）。
   澄清並採用：「互相引用」只指 (a) 文件交叉引用、概念只定義一次（例如欄位來源規則以 ADR-K11 為準），
   (b) 個人記憶與團隊知識**共用同一套程式契約**（provenance、history、proposals 的格式）。
   **資料完全分開**：個人記憶在 actor 自己的記憶資料庫；團隊知識在 Knowledge vault 與 Shared Platform；
   兩者之間**沒有自動同步**，只有 M6 的「提升」：使用者按下、經審核後**複製**一份，原資料不變、
   也不會反向影響。
6. 公司正式名稱以**名片為準**（C4C 為人工填寫、可能有誤）。
7. 跨來源對不上時：**email 完全相同或外部 ID 已在對照表中時自動合併並留紀錄，其餘先問使用者**。
8. 筆記：對話中一鍵存；Agent 可主動提議（每段對話最多一次）；只在 Skill／Workflow 宣告讀取、或
   使用者提到「之前有記過什麼」時查詢（§3.9）。

## 11. M1 as built（2026-10-20，Claude Code）

決定紀錄：`docs/DECISIONS.md` 2026-10-20「Accumulated memory M1: one memory database per actor,
spaces declared in manifests, merge rules as data」。契約：`docs/CONTRACTS.md`「Memory spaces and
the Memory Service」。

### 11.1 架構

| 位置 | 內容 |
|---|---|
| `src/common/memory.py` | 共用契約（不含資料）：`MemorySpaceDeclaration`、`MergeRules`／`FieldMergeRule`／`RelationRule`／`AutoMergeRule`、`Decision`、`FieldProvenance`（ADR-K11 的 `origin`／`set_by`／`set_at`／`reason`） |
| `src/memory/service.py` | Memory Service：每個 actor 一份 `<workspace>/memory/<actor-key>/memory.sqlite`；`MemoryService`（空間註冊）、`MemorySpace`（為某個 asset 開啟的空間）、`SpaceTx`（一個交易內的共用能力） |
| `src/memory/merge.py` | 合併規則的評估：`decide`、`resolve`、`auto_merge`；不碰儲存 |
| `src/memory/registry.py` | `MemoryRegistry`：哪個 asset 在哪個空間是 manager／contributor／reader，以及 manager 提供的合併規則 |
| `src/host_runtime/memory_spaces.py` | Host 的 registry（AEP 內建 manifest ＋ 本機安裝的 Skill／Workflow，含已關閉的）；安裝時的「一個空間一個 manager」檢查 |
| `src/capabilities/business_cards/space.py` | 第一個空間 `contacts/org`：宣告、合併規則（資料）、空間自己的資料表 |
| `src/capabilities/business_cards/migration.py` | `cards.db` → `contacts/org` 的一次性遷移 |
| `src/capabilities/business_cards/store.py` | 名片專屬邏輯（比對、尊稱與統編、公司別名、匯報線、組織圖資料）建在共用能力之上 |

`memory.sqlite` 的資料表：

- `meta`（schema 版本、遷移標記）、`spaces`（每個空間一列：manager、資料表前綴、宣告與合併規則的 JSON）。
- 共用（每列帶 `space`）：`observations`（只增不改：trigger 拒絕 DELETE，UPDATE 只允許把
  `retracted_by` 從空白設一次）、`field_sources`、`history`、`undone`、`proposals`
  （多了 `decided_at`／`decided_by`）、`external_ids`。
- 空間自己的（以空間命名）：`contacts_org__people`、`contacts_org__reporting_lines`（多了
  `observation_id`）、`contacts_org__candidates`。

### 11.2 Manifest 宣告

Skill 與 Workflow manifest 多一個可省略的 `memory_spaces`（最多 16 項）；空的時候序列化時省略，
manifest 的 bytes 與 digest 不變（與 G3 的 `asset_bindings` 同樣做法）。每項：

```json
{"space": "contacts/org", "role": "manager", "kinds": ["entities"],
 "sensitivity": "CONFIDENTIAL", "retention": "until_deleted",
 "schema_ref": "contacts.org.person.v1", "merge_rules": "contacts.org.merge.v1"}
```

- `space`：`<領域>/<名稱>`（小寫，2–3 段）。`role`：`manager`（定義 schema 與合併規則，可讀寫）、
  `contributor`（加觀察、可讀）、`reader`（只讀）；manager 包含 contributor，contributor 包含 reader。
- manager 必須宣告 `kinds`、`sensitivity`、`retention`（`until_deleted` 或 `P30D`／`P12M`／`P2Y`）、
  `schema_ref`、`merge_rules`；contributor／reader 不得宣告後四項。一個 manifest 每個空間只宣告一次。
- 安裝時驗證：所有安裝路徑都經過 manifest 驗證；另外 Shared Platform 同步（`asset_conflict`）與
  Agent Web 重新開啟 Skill／Workflow（`memory_space_has_a_manager`）會拒絕第二個 manager。
- 名片 Skill（`engineering/business-cards@1.0.0`）宣告自己是 `contacts/org` 的 manager。

### 11.3 存取規則

- 模型只能經由 Skill 的工具（`cards__*`）接觸記憶；沒有任何「讀取全部記憶」的工具。
- `MemoryService.space(space, asset=...)`：沒有宣告 → `memory_space_not_declared`；reader 寫入 →
  `memory_write_not_declared`；只有 manager 能用空間自己的資料表與寫 provenance（`memory_manager_only`）；
  觀察的來源類型必須是合併規則認得的（`memory_source_unknown`）。
- 寫入只有觀察：使用者的修改、確認、離職、匯報線也都是 `user`（或證據類型）來源的觀察，再加上
  history；目前值由 manager 依合併規則算出並保存在自己的檢視（`contacts_org__people`）。
- `set_by`／`recorded_by`／`actor` 一律由 Host 從 request context 填（`<actor> via <channel>`）。
- Bridge 的 grants 與審批照舊：名片 capability 仍經 Bridge 以 actor 的 grants 執行。

### 11.4 合併規則（資料）

`MergeRules` 以 JSON 存在 `spaces.rules_json`。`contacts/org` 的預設（§3.8.3、§10.6–10.7）：

- `trust`：`user` → user_stated；`card`、`email_signature`、`import`、`signature`、`email_content` →
  document；`c4c` → system_record；`title_inference`、`agent` → inferred。
- `company`：`precedence`（user_stated > document > system_record > inferred）：名片勝過 C4C，
  C4C 不一致時變成待確認（`lower_trust`）；名片即使較舊也會取代 C4C 的值；同一等級以最新證據為準。
- `title`、`department`、`division`、`business_group` 與其他欄位：`newest_evidence`，任何來源。
- 使用者的值：M1 時不同的證據一律變成待確認（`user_conflict: propose`）；**2026-10-20 owner 決定後改為
  只有新證據能動它**（§3.8.3「新證據」、§13；規則 `contacts.org.merge.v2`）。
- `external_ids`：`c4c_account`、`c4c_contact`，只用來對應，不成為欄位值（`match_only`）。
- `relations`：`reporting_line` 只有 `user`、`signature`、`email_content` 是實線；其他一律虛線。
- `auto_merge`：其他來源只在 email 完全相同或外部 ID 已在對照表時自動合併，其餘先問。名片與簽名檔
  之間仍用名片自己已決定的比對規則（圖片 hash、email、姓名＋公司；DECISIONS 2026-10-20）。

`SpaceTx.decide` 的順序：沒有值或值相同 → 保留；外部 ID → 保留（只對應）；使用者自己說的 → 採用；
目前值是使用者的 → 提議；沒有目前值 → 採用；優先序較低 → 提議（或依規則保留）；讀值不確定 → 保留；
證據較舊 → 保留；其餘 → 採用。
名片的 `_merge` 先處理名片專屬的情況（同一公司或姓名的另一種寫法、email 不同、備註附加、
只讀到一部分），其餘交給 `decide`。

### 11.5 遷移（名片 `cards.db` → `contacts/org`）

第一次開啟名片庫時（每個 actor 各自）：

1. 在 `memory.sqlite` 取得寫入鎖，確認尚未遷移、目標是空的。
2. 備份：在 `cards.db` 旁寫 `cards.db.bak-<UTC 時間>`，在 SQLite 的共享讀鎖下逐 byte 複製，
   檢查 SHA-256 相同、`PRAGMA integrity_check` 為 ok、每張表的列數相同；不符就刪掉暫存檔並停止
   （`memory_backup_failed`）。已有相同內容的備份就沿用。
3. 在同一個交易內複製八張表的每一列，保留所有 id（observation、proposal、line、history、change id），
   所以彼此的參照不變；provenance 補上 ADR-K11 的 `origin`（由來源推得）、`set_by`／`set_at`
   （由設定該值的 history 列推得）與 `reason`「migrated from cards.db」。
4. 逐列讀回並與原表比對；任何差異（`memory_migration_mismatch`）或錯誤（`memory_migration_failed`）
   都會整個 rollback，`memory.sqlite` 不留任何部分資料；`cards.db` 只以唯讀開啟，從不寫入。
5. 寫入標記（來源、備份、各表列數、時間、`cards.db` 的大小、修改時間與 SHA-256），之後開啟就略過。

之後 `cards.db` 不再被寫入。若它在遷移後又被改過（例如退回舊版 AEP 並存了名片），名片庫會拒絕
（`memory_legacy_changed`），不會默默忽略那些變更。

**正式環境第一次啟動會做什麼**：Agent Web 以新程式啟動後，第一次有名片工具被呼叫時（或
`aep-host cards import`），對該 actor 的 `%LOCALAPPDATA%` 工作區
`business-cards/<actor-key>/cards.db` 做上述 1–5；新增 `memory/<actor-key>/memory.sqlite`。

**如何退回**：停掉 Agent Web，checkout 之前的 commit；舊程式照舊使用 `cards.db`（遷移不會改它；
備份也在旁邊）。遷移之後在新版做的修改只在 `memory.sqlite`。要再升級：若退回期間 `cards.db`
有變更，先把 `memory/<actor-key>/memory.sqlite` 移到別處，新版就會從 `cards.db` 重新遷移；
若沒變更，直接升級即可。

### 11.6 與設計稿的差異與補充

- 觀察只增不改；以前「復原新增」會刪掉該人的觀察，現在改為 retract（內容保留、不再參與）。
  使用者陳述在其變更被復原時也會 retract；名片或簽名檔的讀值（sighting）在復原後仍保留。
- `cards__history` 的 `observations` 只列讀值（名片、簽名檔、匯入），使用者自己的陳述在 history。
- 失敗時採「清楚的錯誤」而不是唯讀 fallback（中文說明見 `business_cards_tools.FAILURE_TEXT`）。
- `<workspace>/business-cards/<actor-key>/` 仍保留組織圖檔案、舊的 `cards.db` 與備份。

### 11.7 留給後續階段的擴充點

- **M2 同步進度**：`kinds` 已有 `sync_state`；在 `memory.sqlite` 加共用表（`space, source, key,
  last_message_date, last_message_ids, extractor_version`）與 `SpaceTx` 方法即可，不需要改宣告格式。
- **M3 偏好與筆記**：`kinds` 已有 `preferences`、`notes`；同樣是共用表加 API，觀察與 history 可直接沿用。
- **M4 記憶頁**：`MemoryService.spaces()`、跨空間的 `proposals`（每列帶 `space`）可直接列出「待確認」；
  `retention` 已在宣告中，可接上到期處理。
- 非內建 manager 的合併規則目前只能由程式提供（`MemoryRegistry.provide_rules`）；從 Skill 套件載入規則資料
  留待之後。

## 12. M2 as built（2026-10-20，Claude Code）

決定紀錄：`docs/DECISIONS.md` 2026-10-20「Accumulated memory M2: generic sync state, incremental
harvest, the org chart harvests in the same call」。契約：`docs/CONTRACTS.md`「Memory spaces and the
Memory Service」的 Sync state 一項，以及名片的 `org-chart`／`harvest-signatures`。名片端的說明：
`docs/phases/BUSINESS_CARDS.md` §5、§6。

### 12.1 通用同步進度（Memory Service）

- `memory.sqlite` 新增共用表 `sync_state`（主鍵 `space, source, key`；`last_message_date`（UTC ISO）、
  `last_message_ids`（最多 500 個，最新的在前）、`extractor_version`、`updated_at`、`updated_by`）與
  `sync_history`（每次 `advance`／`reset`／`restore` 一列，存變更前後的完整狀態、actor、原因）。
  `CREATE TABLE IF NOT EXISTS`，M1 的資料庫開啟時自動加上，不需要遷移。
- 只有 manager 宣告了 `sync_state` 種類的空間能用（否則 `memory_kind_not_declared`）；讀需要 reader、
  寫需要 contributor，與其他共用能力相同。每個 actor 一個資料庫，所以每人各自一份。
- `SpaceTx`／`MemorySpace`：`sync_state`、`sync_states`、`advance_sync`（只能往前：較早的日期
  `sync_state_backwards`；`extractor_version` 不同時必須先 reset，`sync_extractor_changed`；同一天或之後
  的 id 與舊的合併）、`reset_sync`（刪掉該列，舊值留在 history）、`restore_sync(history_id)`（把某一列
  history 之前的狀態放回去，可用來復原 reset）、`sync_history`。
- 「只在成功之後前進」是呼叫端的責任：名片的整理在讀信或模型失敗時完全不動進度。
- 名片 Skill 的宣告加上 `sync_state`（`kinds: ["entities", "sync_state"]`）；只有名片 Skill 的 manifest
  digest 改變，其他 shipped manifest 不變（`memory_spaces` 仍然只有它有）。

### 12.2 增量整理簽名檔（`capabilities/business_cards/harvest.py`）

- 進度鍵：`(contacts/org, "mail:<資料夾>", <網域>)`；沒指定資料夾時是設定裡所有資料夾（`mail:Inbox`、
  `mail:Inbox+Sent Items`）。資料夾組合不同就是另一個來源，第一次會讀滿範圍。
- 視窗（`harvest.plan`）：
  - **首次**（沒有進度）：讀信設定的全部範圍（`days` 與 `max_days` 取小）。
  - **增量**：從 `last_message_date` 往前一天（`OVERLAP`，接住晚到資料夾、日期較早的信）開始，
    上次處理過的 message id 直接略過；**讀信設定一定封頂**：視窗開始不會早於設定範圍（回覆會加
    「（讀信設定只到 N 天內）」）。
  - **重新整理**（`full: true`，「重新整理 WNC 的簽名檔」）與**擷取規則改版**（`signatures.EXTRACTOR_VERSION`
    與進度裡的不同）：讀滿範圍；成功後先 reset（history 記原因）再前進。
- 已經被觀察過的信（`observations.source_ref` 是該 message id）略過並計數（`already_seen`），不再提議。
  例外是擷取規則改版：已存的人的信也重讀，但只有新讀法**真的改變**某些欄位時才列為候選（其餘算
  `already_seen`），所以改版後只看到有差別的人。手動重新整理仍略過已存的信，上次沒存（拒絕或過期）
  的人會再列出來。
- 進度前進到哪裡（`harvest.target`）：
  - 全部處理完：最新一封處理過的信的時間（範圍內沒有信時是這次掃描的時間）。
  - 有信沒處理（讀不到，或超過這次的人數上限 `limit`）：停在**最早一封沒處理的信之前**，下次會再讀，
    處理過的靠 id 略過；回覆說「整理進度只更新到 M/D，沒有處理的信下次會再讀」。
  - 增量時只有上次已處理的信：進度不動（不寫 history）。永遠不往回。
  - 模型或讀信失敗：整個整理失敗，進度不動。
- 搜尋一次最多 50 封（`outlook_mail.MAX_RESULTS`，既有上限）。範圍內超過 50 封時只處理最新的 50 封，
  `truncated` 為 true，回覆明說「範圍內的信超過 50 封，只處理了最新的 50 封」；更早的信增量整理讀不到
  （這和 M1 前的行為相同），需要時縮小範圍或之後擴充分頁。
- 這次沒找到新的人時不覆蓋這段對話先前的候選名單（之前列的還能用 `cards__store_candidates` 存）。
- `scan_note` 以視窗開頭：「首次整理（收件匣 180 天內）：…」、「從 10/19 之後的新信：…」、
  「重新整理（收件匣 180 天內）：…」、「簽名檔擷取規則已更新，這次重新整理全部範圍內的信（收件匣 180 天內）：…」；
  多個網域時每個網域一句、前面加網域。`domains` 列出每個網域的 mode、起點與前進後的日期。
- `harvest-signatures` 可用 `company` 代替 `domain`：網域取自該公司已存的人的 Email 與網站
  （`CardStore.company_domains`，M1 的別名邏輯；公用信箱不算）；沒有就 `company_has_no_domain`。

### 12.3 組織圖先整理新信（owner 決定 §10.1）

**選擇：工具選項 `cards__org_chart(harvest_first=true)` ＋ Skill procedure 指示**，不是另一個編排步驟：

- 一次 capability 呼叫裡完成「找網域 → 增量整理 → 留候選 → 用已存的資料畫圖」，回傳 `harvest`
  （候選名單，**不在圖上、不會存**）或 `harvest_note`（略過的原因）。對話模型不必先呼叫整理、
  再呼叫畫圖，比「只畫圖」不多任何一輪模型呼叫；讀簽名檔的模型呼叫只在有新信時發生（每 10 個簽名檔一次）。
- 「候選需要確認」不變：圖只畫已存的人；使用者說「都存進去」→ `cards__store_candidates` →
  `cards__org_chart(harvest_first=false)` 重畫。
- capability 契約的預設是 `false`，Host 不會偷偷替模型打開：CLI、Workflow 或其他呼叫者畫圖時不會
  意外去讀信（測試環境也不會碰到真的 Outlook）；對話裡由 procedure 指示「問組織圖時用 true」。
- 沒有已知網域：不整理，`harvest_note` 說明，照樣畫圖。Outlook 不能用（沒開、COM 錯誤）或沒有內部模型：
  照樣畫圖，`harvest_note` 說「這次沒有先整理新信：<原因>（<code>）；組織圖依已存的資料畫。」，進度不動。
- 公司還沒有任何已存的人、但網域的信裡有候選：回傳候選、不畫圖，等使用者存了再畫。

被捨棄：單獨的「整理後畫圖」編排步驟或 Workflow（多一層、而且畫圖前就要決定候選，容易變成自動存）；
Host 端把 `harvest_first` 預設為 true（所有既有呼叫者都會開始讀信）。

### 12.4 M1 留下的待決事項（已決定）

使用者設定的值遇到不同證據時怎麼辦：owner 2026-10-20 已決定（§3.8.3「新證據」、§13）。

### 12.5 留給 M3 之後

- 記憶頁（M4）的「同步進度」區塊：`sync_states`、`sync_history`、`reset_sync`／`restore_sync` 已備好，
  只差 UI；「重新整理」按鈕就是 `reset_sync`（或 `harvest-signatures` 的 `full`）。
- 搜尋上限 50 封：若真實信件量常超過，可在 `MailReader` 加上「直到某時間」的分頁，讓增量整理由舊到新讀完。
- `extractor_version` 目前是程式常數；之後若擷取規則變成 Skill 資料，版本應跟著資料走。

## 13. 新證據直接更新組織欄位、email 仍是待確認（owner 決定 2026-10-20，Claude Code 實作）

決定紀錄：`docs/DECISIONS.md` 2026-10-20「New evidence updates organisational fields directly; email
stays a proposal」。規則見 §3.8.3「新證據」。

- **合併規則**（`contacts.org.merge.v2`）：`FieldMergeRule.user_conflict` 多了 `take_if_newer`；
  `MergeRules.undated`（沒有證據日期的來源：`card`、`import`）。`merge.decide` 對使用者設定的值：
  `undated` 來源只有 `novel`（圖片沒看過）才算新證據，否則 `keep`／`seen_evidence`；有日期的來源只有
  日期（以天計）**晚於**使用者那次修改的日期才算，否則 `keep`／`older_evidence`；新證據在
  `take_if_newer` 欄位直接 `take`（`new_evidence`，讀值不確定時仍 `propose`），其他欄位 `propose`。
- **名片**：`CardStore._novel`——這個人的觀察裡從沒出現過這個 `sha256:` 圖片 ref。沒有圖片＝不是新證據。
  名片觀察的 `source_date` 仍是掃描日，只用於非使用者值的最新證據排序與顯示，**不**用於使用者值的判斷。
- **比較的「使用者修改時間」**：該欄位 provenance 的 `source_date`，也就是使用者說的那一天（與 `set_at`
  同一天，本地日期）；簽名檔的寄出日期以天比較。
- **舊證據**：不改、不提議、不列在 `kept`、不設 `email_differs`（完全不提）。
- **新證據更新使用者的值**：一般的 `field` history，reason 為 `new card <圖片 ref>` 或
  `newer email <message id>`，可用 `cards__undo` 復原（provenance 回到使用者）；回覆照常以
  「上次是…，現在是…」開頭。
- **Email**：永遠不被讀值覆蓋。使用者設定的 email 只有新證據才提議；不是使用者設定的照舊（不同就提議、
  需確認）。
- **一次性清理**（`CardStore._apply_newer_evidence_rule`，meta 標記
  `contacts_org:rule:new_evidence_only:2026-10-20`）：開啟名片庫時（在 `cards.db` 遷移之後）把
  針對使用者值、來自舊證據的待確認關閉（重掃已看過的圖片，或寄出日期不晚於使用者修改的簽名檔），
  同一個 change id、每筆一列 history（kind `proposal_rule`，reason
  「older than the person's change, rule 2026-10-20」），`cards__undo` 該 change id 就重新打開
  （kind `proposal_reopen`）。只做一次；復原後不會再被關。來自新證據、仍開著的待確認保留給使用者決定。
- 測試：`tests/test_business_cards_new_evidence.py`；調整既有測試中以舊規則為前提的斷言
  （`test_business_cards_store.py`、`test_memory_service.py`、`test_business_cards_capabilities.py`）。

## 14. M3 as built（2026-10-21，Claude Code）

決定紀錄：`docs/DECISIONS.md` 2026-10-21「Accumulated memory M3: preferences and notes are Host-managed
spaces; only the person's press saves」。契約：`docs/CONTRACTS.md`「Memory spaces and the Memory
Service」的 Preferences and notes 一項。

### 14.1 兩個由 Host 管理的空間

| 空間 | 種類 | manager | 誰讀 |
|---|---|---|---|
| `personal/preferences` | `preferences` | Host（`host/memory`） | 只有 Host：在一輪對話開始時注入 |
| `personal/notes` | `notes` | Host（`host/memory`） | 宣告 `{"space": "personal/notes", "role": "reader"}` 的 Skill／Workflow（經 manager 的 API `memory.notes.for_reader`），以及 `notes__search` |

- 宣告與規則在 `src/memory/personal.py`；Host 的 registry（`host_runtime.memory_spaces.registry`、
  `business_cards.space.default_registry`）在任何 manifest 之前先宣告它們（`from_manifests(first=)`），
  所以沒有已安裝的 Skill 能當它們的 manager（`conflicts()` 也把它們算進去）。
- 仍在同一個 `memory/<actor-key>/memory.sqlite`（每人一份）；各自的資料表
  `personal_preferences__items`、`personal_notes__items`；歷史、復原用 M1 的 `history`／`undone`／
  `SpaceTx.undo`（各自的 undo handler）。新增 `SpaceTx.changed_after`：之後還有沒被復原的變更動到同一筆時，
  復原被拒（`undo_conflict`）。
- 名片 Skill 多宣告一項 `personal/notes` reader（組織圖的「相關筆記」）；只有名片 Skill 的 manifest digest 改變。

### 14.2 偏好（§5）

- **每一條**：`preference_id`（`p-…`）、`text`（使用者的原話，NFKC、單行、最多 300 字）、`scope`
  （`skill:<namespace>/<name>`，或 `space:<space>`）、`scope_label`（名片 Skill 是「名片／組織圖」）、
  `subject`、`polarity`、`status`（`active`／`removed`／`replaced`）、`created_by`（`<actor> via <channel>`，
  Agent Web 是 `web`）、`created_at`、`source_session`、`source_message`（使用者那句話的 message id）、
  `proposed_by`（`agent`）、`replaced_by`。
- **提議**：模型只有 `memory__propose_preference(rule, skill, subject?)`，它只建一張卡片
  「要把這條記成『<Skill 名稱>』的偏好嗎？」（存成偏好／不用，24 小時有效，card id `mm-…`）。**沒有任何
  模型工具會直接存偏好。** `skill` 可以是工具前綴（`cards`）、名稱或 `namespace/name`；找不到時拒絕並列出
  已開啟的 Skill。已經存過一樣的（同 scope、同主題、同方向）：拒絕提議（`preference_already_saved`）。
  同一段對話裡同一條還在等的卡片不會重複建立。
- **卡片不結束這一輪**（`ActionCard.ends_turn = false`，新欄位，預設 true）：模型的回答照常寫完，卡片顯示在
  回答下面；Telegram 也是先回答再卡片（`telegram.py` 只改這一個分支）。
- **按下才存**：`AgentWeb.decide_card` 的 `mm-` 分支 → `PersonalMemory.decide`。存的時候先做**矛盾檢查**：
  - 決定：**只用確定性的檢查**，不呼叫模型。`polarity`：句子裡有否定詞（不需要、不用、不要、不必、不再、
    不會、無需、勿、別（「特別、分別、區別、個別、類別…」裡的「別」不算）、never、don't、no need、skip、
    without、stop…）就是 `negative`。`subject`：去掉否定詞與「以後、每次、一律、都、要、請、always、
    please…」之類的字，只留字母與數字。兩條 **同 scope、主題相同**（完全相同或 `difflib` 相似度 ≥ 0.8，
    或提議時給的 `subject` 正規化後相同）：方向相同 = 重複，方向相反 = 矛盾。
  - 重複：不再存，卡片寫「已經有相同的偏好（p-…），沒有重複存」。
  - 矛盾：**先問**，卡片變成「這條偏好和『名片／組織圖』既有的偏好矛盾，要怎麼辦？」，表格列出
    既有那條（之前）與新的（之後），按鈕「取代舊的」（舊的變 `replaced`，同一個 change id，一次復原兩條都回來）、
    「兩條都留」、「不用」。
  - 模型檢查（經內部 gateway、structured output）沒有做：確定性的規則已涵蓋「同主題、相反方向」，
    不送資料出去、沒有延遲；語意上的矛盾留給 M5 的每晚健康檢查。
- **套用**：Gateway 每一個 pass 在決定好工具後問 Host（`Gateway.turn_memory`，Host 的
  `PersonalMemory.turn`），給它「這一輪提供了工具的 Skill」（Skill 指令 `<alias>__…` 或以 alias 開頭的
  Host 工具，例如名片的 `cards__…`）。Host 把這些 Skill 的 scope（`skill:` 本身，加上它宣告的非 personal
  空間 `space:`）中 `active` 的偏好放進 system prompt，標明是使用者自己存的偏好、照做不必再問、不改變權限或工具；
  最新的在前，最多 12 條、1,600 字。名片 Skill 開著時它的工具每一輪都提供，所以它的偏好每一輪都會帶上。
- **記錄用了哪些**：`GatewayConversationResult.preferences_used`、`ConversationMessage.preferences_used`
  （只有回答有），Agent Web 的回覆 JSON 也有 `preferences_used`。M5 的「為什麼這樣做」用它。
- **說了「規則我已改成」**：`MEMORY_GUIDANCE` 與 `no_unbacked_action_claim` 的重試說明都改成指向
  `memory__propose_preference`；`memory__propose_preference`／`memory__propose_note` 不算「會改變東西的工具」，
  所以只有提議、卻說「已記住／已改成」仍會被擋下重試。

### 14.3 筆記（§3.9）

- **每一則**：`note_id`（`n-…`）、`text`（Markdown，最多 20,000 字）、`tags`（最多 8 個，去 `#`、不分大小寫去重）、
  `entities`（`<space>:<kind>:<id>`，例如 `contacts/org:person:p-…`，最多 12 個）、`source_kind`
  （`answer`／`selection`／`agent_proposal`）、`source_session`、`source_message`、`excerpt`
  （`{start, end}`：選取內容在原始回答文字中的位置）、`status`（`active`／`deleted`）、`created_by`、
  `created_at`、`updated_by`、`updated_at`。`update`（文字、標籤、連結）、`delete` 都寫 history、可復原。
- **一鍵存（Agent Web）**：每則回答的工具列多一個 📝「存成筆記」（右鍵選單也有）；在回答裡選取文字會
  出現「存選取內容」按鈕。都打 `POST /api/memory/notes/save {session_id, message_id, selection?}`：
  文字一律由伺服器從存著的回答取；選取內容必須真的在那則回答裡（只比對字母與數字，所以 Markdown 的
  `**`、清單符號不影響；不在裡面就 `selection_not_in_answer`）。同一則回答同樣的內容存第二次會回
  「已經存過了」。存好後顯示「已存成筆記（n-…）。 復原」。不需要模型工具。
- **Agent 提議**：`memory__propose_note(text, tags?, entities?)` → 卡片「要存成筆記嗎？」（存成筆記／不用）。
  **每段對話最多一次**：Host 檢查卡片紀錄；已經提議過就不再提供這個工具，直接呼叫也拒絕
  （`note_already_proposed`）；同一輪 Host 檢查的重試拿到的是同一張卡片。Telegram 的 session 不會結束，
  所以 Telegram 以「同一個聊天、同一天（Asia/Taipei）」算一段對話。按下後存，來源是顯示卡片的那則回答。
- **查詢**：`notes__search(query, tag, entity, since, until, limit≤20)`，只在
  1. 這一輪提供了工具的 Skill 宣告了 `personal/notes` 讀取（目前是名片 Skill，所以它開著時每輪都有），或
  2. 使用者這句話提到以前的筆記（`memory.notes.NOTES_ASKED`，確定性比對）：「之前／以前／上次…有記過／存過／
     寫過」、「記過什麼／哪些／嗎」、「有沒有記過」、「我的筆記／之前的筆記／記過的筆記」、「查／找／翻／搜尋
     （一下）（我的）筆記」、「筆記裡有／寫」、"what did I note"、"did I write down"、"my notes"、
     "earlier/previous notes"、"I noted"。「存成筆記」、「記得幫我…」不算。
  結果每則帶 `note_id` 與 `cite`（`[筆記 n-…]`），說明要求回答時標出引用；筆記**從不自動注入**。日期以
  Asia/Taipei 的日子算。
- **組織圖**：HTML 組織圖的名片卡多一段「相關筆記」：連到 `contacts/org:person:<person_id>` 的筆記，
  最新 5 則，每則日期、前 140 字與 id；資料照樣只用 `textContent` 顯示。沒有宣告讀取或讀不到時就沒有這段。

### 14.4 每人隔離、歷史、復原

- 兩種都在 actor 自己的 `memory.sqlite`；卡片紀錄（`<workspace>/memory/memory-cards.json`）記著提議的 actor，
  按下時寫進那個 actor 的資料庫。其他成員看不到、也搜不到。
- Agent Web 的最小路由（記憶頁是 M4）：`GET /api/memory/notes`、`GET /api/memory/preferences`、
  `POST /api/memory/delete {kind: note|preference, id}`、`POST /api/memory/undo {kind, change_id}`。

### 14.5 留給 M4 之後

- 記憶頁的「偏好」與「筆記」區塊：列表、修改、刪除、復原的 API 都已備好（`Preferences.listed/remove/undo`、
  `Notes.listed/search/update/delete/undo`），只差 UI；筆記的 Markdown 匯出、標籤篩選也在這裡。
- Agent Web 以外（Telegram）沒有一鍵存筆記，只有 Agent 的提議卡片。
- 名片 Skill 宣告了筆記讀取，所以它開著時 `notes__search` 每輪都提供；若 owner 希望更少，可改成只在
  使用者提到筆記時提供（宣告只給組織圖用）。
- 偏好的語意矛盾（不同說法、同一件事）與「沒在用的偏好」留給 M5 的健康檢查。

## 15. M4 as built（2026-10-21，Claude Code）

決定紀錄：`docs/DECISIONS.md` 2026-10-21「Accumulated memory M4: the memory page acts as the owner of the
actor's database」。契約：`docs/CONTRACTS.md`「Memory spaces and the Memory Service」的 Memory page 一項。
使用說明：`USER_GUIDE.zh-TW.md` §4.9。

### 15.1 頁面

Agent Web 左邊多一個「**記憶**」（`#panel-memory`），六個分頁（§6 的五個區塊加上 §3.9 的筆記），
一次 `GET /api/memory/overview` 取得全部，動作後重畫，結果與「復原」顯示在分頁上方：

| 分頁 | 內容 | 動作 |
|---|---|---|
| 待確認 | 所有空間開著的 proposals：空間、對象（`contacts/org` 是「姓名（公司）」）、欄位、存著的值、新讀到的值、證據（觀察的來源、日期、ref）、提出時間 | 保留原值、改用新值（`contacts/org` 的欄位）、開啟該聯絡人；`contacts/org` 的決定可復原 |
| 偏好 | `active` 的偏好依 scope（Skill）分組：原話、誰、何時、「來源對話」、「用過 N 次」（最近 100 段對話的 `preferences_used`，最多列 5 則） | 修改（M3 的矛盾檢查）、刪除、復原 |
| 筆記 | 全部 `active` 筆記，Markdown 顯示；搜尋（每個字都要出現）、依標籤、依關聯對象篩選（在瀏覽器裡篩） | 修改（Markdown）、加標籤／×移除、連結聯絡人（搜尋 `contacts/org`）／×取消連結、刪除、復原、勾選後匯出 Markdown、開啟原本的對話 |
| 資料 | 每個空間一列：名稱、管理者與狀態（已開啟／已關閉／內建／**無主**）、種類、敏感度、保留期限、各資料表筆數與待確認數、最後更新 | `contacts/org`：開啟聯絡人（搜尋、全部／在職／已離職、每人的「歷史」：變更、讀到的來源、待確認數）；組織圖仍在對話中 |
| 同步進度 | 每個 (空間, 來源, 鍵)：整理到的日期、擷取版本、誰與何時、上一次的動作 | 重新整理（`reset_sync`，先 `confirm()`）、復原上次重設（`restore_sync`，只在最後一筆是 reset 時） |
| 紀錄 | 保留期限：對話（保留到刪除，每段 100 則，現有規則）、執行紀錄（telemetry 30 天或 500 MB，固定）、經驗回顧案例（可改，沿用 Reviews 的 `/api/experience/settings`）、各記憶空間的 `retention`（唯讀）；每個空間的匯出與刪除；刪除紀錄 | 匯出 JSON；刪除資料（要輸入空間名稱，`confirm` 欄位也在伺服器端檢查） |

- 每個動作記成 `<actor> via web`（`set_by`、`decided_by`、history 的 `actor`、sync 的 `updated_by`）。
- 會刪東西的動作都先問：偏好、筆記刪除與同步重設用 `confirm()`；刪除空間資料是頁內的確認框，要輸入空間名稱。
- 44 px 的點擊目標、淺色與深色、390 px 寬沒有橫向捲動（瀏覽器測試量過）。分頁是 `div`（`section` 會被
  `section{display:none}` 藏起來）。

### 15.2 後端

- `src/host_runtime/memory_page.py`：`MemoryPage`（`AgentWeb.memory_page`），路由見 CONTRACTS。只用
  `web.runtime.actor` 的資料庫；別人的 id 在這裡什麼都找不到。**沒有任何模型工具**：沿用 M3 的三個工具
  （兩個只提議、一個只搜尋筆記），測試確認沒有工具名稱或路由對應到這些動作。
- `MemoryService`（`src/memory/service.py`）新增「擁有者的管理」：`owned(space)`（以 manager 的權限開啟，
  只給 Host 路由用）、`overview()`、`open_proposals()`、`proposal()`、`sync_overview()`、`export_space()`、
  `delete_space()`、`deletions()`；新表 `space_deletions`（`CREATE TABLE IF NOT EXISTS`，舊資料庫開啟時自動加上）。
- 待確認的決定：`contacts/org` 用名片庫既有的 `CardStore.edit`：保留原值＝`confirm=[欄位]`（存著的變成使用者
  確認的值，開著的提議 rejected），改用新值＝把那一筆提議的值設為使用者的值（該提議 accepted），和對話中說
  「Email 正確」「用新的」完全相同，可用 `CardStore.undo` 復原（`/api/memory/proposals/undo`）。其他空間沒有
  管理者的轉接，只能保留原值（提議 rejected，寫一列 `proposal_rejected` history），不提供改用新值。
- 偏好修改：`Preferences.edit`（同一個 id，history `preference_edit`，undo 放回原話）；和其他偏好重複 →
  `preference_duplicate`；矛盾 → `preference_conflict` 並列出，頁面問「取代舊的」（同一個 change 把那條變
  `replaced`）或「兩條都留」。修改後 `subject` 清空（舊的主題可能已不適用）。
- 筆記：`Notes.update` 的 text／tags／entities（只改送來的欄位），`/api/memory/delete`、`/api/memory/undo`
  沿用 M3。
- 無主：空間的 manager 不是 Host，且不在這台電腦已安裝（開或關）的 Skill／Workflow 中
  （`memory_spaces.manager_states`）。
- 匯出：`{format: "aep-memory-space-export/1", space, manager, exported_at, declaration, rules,
  tables（空間自己的表）, shared（該空間在共用表的列）}`，瀏覽器下載 `memory-<space>-<時間>.json`。
- 刪除（§3.6）：一個交易內清空空間自己的表與該空間在所有共用表的列（含 observations：只有這裡在交易內暫時拿掉
  append-only trigger，結束前放回）；空間仍註冊、表仍在；`space_deletions` 一列記時間、誰、原因、各表筆數，**沒有內容**；
  不能復原。`meta`（例如 `cards.db` 已遷移的標記）保留，所以不會重新遷移舊資料。

### 15.3 沒做的與留給之後

- 舊的 `business-cards/<actor>/cards.db` 與備份不在記憶資料庫裡，刪除 `contacts/org` 不會刪它們（確認框與使用
  說明都寫了）。要不要一起刪留給 owner 決定。
- 記憶空間的 `retention` 目前只顯示，沒有到期處理；對話沒有依日期的保留設定（只有每段 100 則），執行紀錄的
  30 天／500 MB 是程式常數。若要可設定，另外決定。
- 沒有管理者轉接的空間不能「改用新值」；之後的空間可以提供自己的轉接（像 `contacts/org` 的 `CardStore.edit`）。
- Telegram 沒有記憶頁（範圍外）。
- 測試：`tests/test_memory_page.py`（每個動作的路由、每人隔離、沒有模型工具）、`tests/test_memory_page_ui.py`
  （真的瀏覽器：每個分頁、動作端到端、淺色／深色／390 px、權杖；截圖 `.scratch/memory-page/`）。

## 16. M5 as built（2026-10-21，Claude Code）

決定紀錄：`docs/DECISIONS.md` 2026-10-21「Accumulated memory M5」。契約：`docs/CONTRACTS.md`「Memory spaces and the
Memory Service」的 Memory quality 一項。使用說明：`USER_GUIDE.zh-TW.md` §4.10。

### 16.1 新鮮度（§8.2）：規則是資料

- `MergeRules.freshness`（`common.memory.FreshnessRule`，可省略，預設沒有）：
  - `kind: entities`：`entity`（`person`）、`after`（`P12M`／`P30D`）、`status`（只問這些狀態的，`active`）、
    `question`（含 `{name}`）。最新一筆觀察（任何來源，包含使用者自己的話）早於期限就成為一個待確認問題。
  - `kind: sync_state`：`after` 內沒有前進的同步進度，列在健康報告與待確認（「整理進度停住」，只有「知道了」）。
- `contacts/org` 的規則（`contacts.org.merge.v2` 仍是同一個 id；`spaces.rules_json` 開啟時自動更新）：
  `{kind: entities, after: P12M, entity: person, question: "{name} 是否仍在職？", status: [active]}`、
  `{kind: sync_state, after: P30D}`。
- 「仍在職」：`CardStore.confirm_active`，一筆 `user` 觀察（claim `status`，`still_active`）加 history `still_active`，
  新鮮度從那天重新算；「已離職」：既有的 `set_status`（可復原）。
- 人的設定 `freshness_months`（0 = 用規則的期限）覆蓋 entities 規則的期限；`sync_state` 的期限只看規則。
- 「沒前進」以 `sync_state.updated_at` 判斷。增量整理沒有新信時進度不寫（§12.2），所以一個常被整理、但一直沒有新信的
  網域也可能被列出；這只是提醒，「知道了」即可。

### 16.2 每晚健康檢查（§8.4）

- `src/memory/health.py`：`run_check(service, preferences, last_used, entities, manager_state, ask, now, settings)`
  只讀記憶，唯一的輸出是 actor 自己資料庫的新表 `health_findings`（`finding_id`、`space`、`kind`、`key`、`subject_json`、
  `state` open／dismissed／resolved／gone、`check_id`、建立／更新／決定時間與人、`action`；`(space, kind, key)` 唯一）。
  同一個問題再跑一次是更新，不重複：已「不用／保留」的維持關閉（很久沒用的偏好例外：再過 `unused_days` 會再問），
  修好又被復原的會重新打開，沒再出現的 open 項目變 `gone`。`health_findings` 也是 `SHARED_TABLES` 之一（匯出、刪除空間時一起）。
- 找什麼（每個 actor 各自）：
  | kind | 條件 | key |
  |---|---|---|
  | `duplicate` | `contacts/org` 兩人 email 相同，或同公司同名但 matcher 沒合併（`CardStore.duplicates`） | 兩個 person id |
  | `stale` | entities 新鮮度規則（`CardStore.last_seen`） | person id ＠ 最後出現日 |
  | `contradiction` | 同一個 scope 有 ≥ 2 條 active 偏好時，問一次內部模型；M3 確定性檢查會抓到的（同主題、相反方向）不再列 | 兩個 preference id |
  | `unused` | 最後一次被回答帶上（`preferences_used`）早於 `unused_days` | preference id |
  | `orphan` | 管理者不是 Host、也不在這台電腦（開或關） | space |
  | `stale_sync` | sync_state 新鮮度規則 | 來源｜鍵 ＠ 最後前進日 |
- **矛盾的模型問題**：`host_runtime.memory_health.ask_with` 經 `experience_review.structured_call`，用經驗回顧同一個
  內部模型（`review_model`，Knowledge capability 的 company model，經內部 gateway）；structured output、
  `output_contract: memory_health_contradictions`、`max_output_tokens: 500`；每個 scope 一次、最多 `MAX_SCOPES = 5`
  個 scope、每次最多 `MAX_RULES_PER_SCOPE = 12` 條（最新的），只送偏好原文的編號清單；回覆 `{"pairs": [{a, b, why}]}`
  最多 5 對、編號必須在範圍內。少於兩條、檢查關閉時不呼叫；沒有內部模型時略過（`model: unavailable`），
  呼叫失敗時 `failed`，兩種都不動既有的矛盾項目。
- **「沒在用」的資料**：`Preferences.mark_used`／`last_used`（`personal_preferences__uses`：id、最後時間、次數，沒有內容），
  Agent Web 每個回答存檔後與 Telegram 每個回答都記；再加上該 actor 最近 200 段對話的 `preferences_used`（M5 之前的紀錄）。
- **每晚**：`AgentWeb.nightly_tick`（原本夜間迴圈每 30 分鐘看一次）02:00 後每晚一次：先跑健康檢查
  （Tasks 頁「Memory health check (nightly)」，`MemoryHealth.run_all`：`<workspace>/memory/*/memory.sqlite` 的每個 actor，
  每個資料庫的 `meta.actor` 記著是誰的——`MemoryService.for_actor` 開啟時寫入；各自的開關），再照舊做經驗回顧。
  經驗回顧的 `review-*.json`／`.md` 多一個 `memory_health`（`HealthSummary`：actor 數、檢查／關閉／失敗數、各 kind 筆數、
  新開／open／gone、模型呼叫數與各狀態），只有筆數；那晚不需要經驗回顧時，另寫一份只有這一段的 `review-*` 報告。
- **立即檢查**：記憶頁「待確認」上方的按鈕，`POST /api/memory/health/run`，只檢查登入的 actor；檢查關閉時拒絕（`health_off`）。
- **遙測**：每個 actor 一個 `memory_health` run 與一個 `memory.health_checked` 事件，屬性只有布林、數字與模型狀態
  （`found_<kind>`、`opened`、`open`、`gone`、`model`、`model_calls`），沒有任何內容或名字。
- **使用者按了才改**：`MemoryHealth.decide`（`POST /api/memory/health/decide {finding_id, action}`），每個動作都經過
  既有、可復原的寫入：
  | kind | action | 做什麼 | 復原 |
  |---|---|---|---|
  | duplicate | `merge` | `CardStore.merge_people(第 1 筆, 第 2 筆)`：第 1 筆空白的欄位用第 2 筆補（`user` 來源）、匯報線移過來（第 1 筆已有主管時不覆蓋）、第 2 筆的待確認 dismissed、第 2 筆的列刪除（觀察照舊保留）；一個 change | `cards.undo`（`/api/memory/proposals/undo`）：先把第 2 筆整列放回（history `merged_away` 存整列）、待確認重開，再退欄位與線 |
  | duplicate | `dismiss` | 不是同一人 | — |
  | stale | `still_active`／`left` | `confirm_active`／`set_status(left)` | `left` 可復原 |
  | contradiction | `remove_a`／`remove_b`／`keep_both` | `Preferences.remove`（停用）／保留 | `/api/memory/undo kind=preference` |
  | unused | `remove`／`keep` | 同上 | 同上 |
  | orphan | `keep` | 保留（匯出或刪除在「紀錄」） | — |
  | stale_sync | `dismiss` | 知道了 | — |
  每個動作都記成 `<actor> via web`；別的 actor 的 finding id 在這裡找不到（`finding_unknown`）。
  記憶頁在修正下方按「復原」走 `POST /api/memory/health/undo`（2026-10-21，#233）：先用上表的復原撤回那次變更，
  再把這個 `resolved` 的項目改回 `open`（「修好又被復原的會重新打開」立即生效，不必等下一次檢查），卡片馬上回來。

### 16.3 「為什麼這樣做」（§8.5）

- **每一輪記什麼**：`ConversationMessage.memory_used`（只有回答，最多 40 個參照 `<space>:<kind>:<id>`，沒有內容），
  由 `host_runtime.memory_why.memory_used_in(工具紀錄, 回答文字)` 從這一輪的工具結果取：名片工具（`cards__*`）結果裡的
  `person_id`（`contacts/org:person:p-…`）、整理簽名檔（含組織圖的 `harvest`）前進的網域（`contacts/org:sync:<網域>`）、
  `notes__search` 找到且回答有引用（`[筆記 n-…]`）的筆記（`personal/notes:note:n-…`）。偏好仍是 M3 的 `preferences_used`。
  Agent Web 的回覆 JSON 也有 `memory_used`。
- **Agent Web**：有用到偏好或記憶的回答下方有小的「為什麼？」按鈕；按下 `GET /api/memory/why?session_id&message_id`
  （只讀登入 actor 自己的對話與記憶），列出每一項（偏好原文與 Skill、聯絡人姓名與公司、筆記前 60 字、整理進度的網域），
  已刪除的標「（已刪除）」，其餘有「到記憶頁修改或刪除」（整理進度是「到同步進度」）：開啟記憶頁對應分頁並標出那一項
  （`memGoto`；聯絡人開啟歷史）。
- **Telegram**：`/why` 回覆這個聊天上一則回答用到的偏好與記憶（`TelegramIngress._why`，記在記憶體：actor、偏好 id、參照），
  最後一句「要修改或刪除，請到 Agent Web 的「記憶」頁。」；沒有時「上一則回答沒有用到你的偏好或記憶。」HELP 也寫了 `/why`。

### 16.4 設定（§8，紀錄分頁）

- 「記憶」→「紀錄」→「健康檢查」：每晚檢查開／關（預設開）、`freshness_months`（0–120，0 = 依規則）、
  `unused_days`（1–3650，預設 90）。存在 actor 自己資料庫的 `meta.health_settings`（JSON），只改送來的鍵、
  其他（之後版本的）鍵保留；`POST /api/memory/health/settings`，值不對時 `health_settings_invalid`。
- 記憶頁一次 `GET /api/memory/overview` 多一個 `health`：`settings`、`rule_periods`、`last_run`（筆數）、`findings`
  （每項：標題、`pairs`、`actions`、`links`、`kind_label`）。待確認分頁的數字＝提議數＋健康檢查項目數。

### 16.5 沒做的與留給之後

- `orphan` 只提供「保留」與連到「紀錄」；刪除仍走 M4 要輸入空間名稱的流程。
- 「合併」固定保留第 1 筆（建立較早的；同一秒建立時依 id）；要保留另一筆可先「不是同一人」再在對話中處理。
- 一個人被合併後，他舊名片圖片的觀察仍掛在舊 id；之後重掃同一張圖片會改由 email／姓名＋公司找到合併後的人。
- Telegram 的 `/why` 只記最後一則、只在記憶體（Bridge 重啟後就沒有）。
- 測試：`tests/test_memory_health.py`（新鮮度與假時鐘、重複與合併／復原、矛盾與假模型、範圍上限、沒在用、無主、
  同步停住、檢查不改資料、設定、每人隔離）、`tests/test_memory_quality_web.py`（記憶頁路由與按下後的修正與復原、
  設定往返、關閉時不呼叫模型、每人隔離、夜間報告與遙測只有筆數、每一輪的「為什麼」資料、Telegram `/why`）、
  `tests/test_memory_why_ui.py`（真的瀏覽器：「為什麼？」與連結、健康檢查卡片、設定、深色 390 px；截圖
  `.scratch/memory-why/`）。

## 17. B3：記憶頁的速度與載入狀態（2026-10-21，Claude Code）

決定紀錄：`docs/DECISIONS.md` 2026-10-21「The memory page reads the installed manifests and sets up a
memory database once (B3)」。

- 原因：每次 overview 重建記憶 registry 五次（每次解析約 70 個已安裝的 manifest），每個 `MemoryService`
  都重跑資料庫設定（一次 overview 開 `memory.sqlite` 46 次）。
- 現在：已解析的 manifest 與 registry 依檔案（路徑、大小、修改時間）保留，檔案一變就重讀；資料庫檔案沒變時
  不重跑設定；一個請求共用一個連線（`MemoryService.session()`）。
- `GET /api/memory/overview?only=<區塊>,…` 只回那些區塊；頁面動作後只重載受影響的區塊，每個分頁有
  「載入中…」／「更新中…」、第一次載入前數字是「…」、失敗在分頁內顯示並可「重試」。
- 測試：`tests/test_memory_page_performance.py`（數開啟次數、設定次數、掃描次數）、
  `tests/test_memory_page_loading_ui.py`（真的瀏覽器；截圖 `.scratch/memory-perf/`）。

