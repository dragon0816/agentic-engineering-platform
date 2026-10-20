# 可累積的記憶管理（設計稿，待 owner 確認）

Owner 討論：2026-10-20。狀態：**design approved 2026-10-20（決定見 §10）；M1 implemented 2026-10-20（見 §11「M1 as built」），M2 起依 §9 進行。** 架構層級的決定，依 `CLAUDE.md`
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
   | 使用者親口說的值 | **優先**；之後若出現**較新的**不同證據，變成待確認，不自動改 |

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
| M2 | 同步進度 + 組織圖增量整理 | 第二次組織圖只讀新信；改版時正確重整 |
| M3 | 偏好：確認卡、注入、矛盾檢查；筆記：一鍵存、Agent 提議（每段對話最多一次）、依宣告或「之前記過什麼」查詢 | 對話中說的規則按一下後生效、之後不再詢問；回答旁一鍵存筆記，並能被查詢引用 |
| M4 | Agent Web 記憶頁 | 五個區塊可用；E2E 與瀏覽器測試 |
| M5 | 品質工具：新鮮度、每晚健康檢查、「為什麼這樣做」 | 健康檢查產生建議卡片 |
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
- 使用者的值優先：不同的證據一律變成待確認（`user_conflict: propose`；較舊的證據也提議，沿用
  第三次 live test 的「不論確定與否都不覆蓋」；`propose_if_newer` 是可選的另一種寫法）。
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

