# BI 資料集經 Shared Platform 分享（設計提案，待 owner 確認）

2026-10-21，Claude Code。**只是設計，沒有程式改動。** 範圍：讓 Domain Knowledge owner 把自己維護的
BI 卡片資料集分享給其他電腦上的同事，同事在 Knowledge 頁、Dashboard 與對話（`bi__query`）都能讀到。
owner 已選擇**先走既有的 AEP Shared Platform**，不等 #212（中央 PostgreSQL 放哪裡，未決）。

## 0. 摘要（給 owner 的三行）

- **建議 A：快照（snapshot）當成一種新的平台資產 `bi_dataset`。** owner 按「發佈到 Shared Platform」，
  平台存一個不可變的版本；同事選取（訂閱）後由既有的 Bridge sync 裝成**唯讀**副本。沿用平台既有的
  擁有權、群組、選取、TLS 釘選與不可變版本，平台端只加一個資產種類、一個發佈端點與大小上限。
- 第一個 slice 只做**唯讀分享**（約 8–10 個工作天）；同事的修改變成提議送回 owner 是之後的 slice。
- 開始前需要 owner 先決定一件事：**141 是公開測試機**，INTERNAL 的 BI 資料能不能放上去（§8.4 Q1）。

## 1. 現況（讀過的程式與文件）

| 項目 | 現況 | 出處 |
|---|---|---|
| BI 卡片儲存 | 每台電腦各自一個 SQLite：`<workspace>/bi/<dataset>/bi.sqlite`；資料表 `cards`、`fields`（值＋`kind`/`ref`/`by`/`at` 來源）、`history`（append-only）、`proposals`（匯入與人工值衝突時的待確認）、`imports`（可整批復原）。人工值不會被匯入覆蓋；過期編輯回 409 `stale_edit` | `src/capabilities/bi_cards/store.py`、`src/host_runtime/bi_cards_api.py` |
| 資料集名稱 | `^[A-Za-z0-9_-]{1,40}$`；`datasets()` 只列出 `<workspace>/bi/<x>/bi.sqlite` 存在的資料夾 | `store.py` |
| Schema | 目前內建 `bi.schema/v1.1`。另一個 agent 正在加「每個資料集綁一個 schema id@version，使用者 schema 裝在 `<workspace>/bi/schemas/`」 | `schema.py`；進行中 |
| 對話 | `bi-cards/query@1.0.0` 的 `bi__query`，參數 `dataset`；回答引用 `[卡片 <type>:<key>]` | `capability.py`、`manifest.py`、`bi_cards_tools.py` |
| 分類 | #214：BI 資料是 **INTERNAL**；分類只決定模型路由（只走公司內部 gateway），**誰能讀由資料庫分享給誰決定**，不另加權限層 | `docs/DECISIONS.md` 2026-10-21 |
| 平台資產 | `AssetKind = task / workflow / skill / knowledge / agent / bridge_extension`；發佈版本不可變（`PublishedAssetPackage`、`PackageMetadata{artifact_ref, sha256}`）；名稱擁有權 `AssetNameOwnership`（owner、`co_editors`、`may_publish`）；使用權 `entitled()`＋`NameAccess`（visibility、members、groups） | `src/common/distribution.py`、`src/common/assets.py`、`src/common/ownership.py`、`src/common/identity.py` |
| 成員發佈 | Member Portal `assets/submit` → Review queue → 另一位管理員核准才發佈；平台指定版本號。只開放 `skill`、`workflow`；請求本體上限 256 KiB、artifact 上限 192 KiB | `src/control_plane/submissions.py`、`member_http.py`、`src/host_runtime/platform_publish.py` |
| 選取與同步 | 成員在 Marketplace（或 Agent 經 `/v1/member/select`）選定**確切版本**給某個 Bridge；Agent sync 收到 plan＋artifact（base64 內嵌在回覆裡），全部驗證完才寫入；同名同版本但內容不同 → `asset_conflict`；平台連不到絕不當作撤銷 | `src/host_runtime/sync.py`、`src/common/sync.py`、`platform-selections.json` |
| Knowledge 套件 | `PortableKnowledgePackage`：只允許 `raw/`、`wiki/*.md` 與根目錄三個 md；sync 裝到 `knowledge_vaults/<ns>/<name>/<version>`，裝過的內容被改過會被拒絕 | `src/knowledge/package.py`、`sync.py` |
| Knowledge 協作 | 專案 vault 在 OneDrive，sandbox → benchmark → push；**不經平台**，maintainers 名單在 host.json | `docs/phases/KNOWLEDGE_COLLAB.md`、`src/host_runtime/knowledge_push.py` |
| 團隊成員 | `/v1/member/me` 回答本人的 groups，快取在 workspace；連不到時用快取 | `src/host_runtime/team_membership.py` |
| 平台主機 | 141：Bridge API 8775、Member Portal 8776、自簽憑證，Agent 端以 SHA-256 指紋釘選（`check_bridge`、`certificate_pin`）。owner 2026-10-15：141 是**公開測試機**，不是公司電腦 | `src/host_runtime/shared_platform.py`、`deploy/shared-platform-preview/START-HERE.md` |
| 前例 | 累積記憶「集中管理、分開擁有」：一個空間一個 manager，其他是 contributor（只寫觀察／提議）與 reader（只讀）；匯出格式 `aep-memory-space-export/1` | `docs/phases/ACCUMULATED_MEMORY.md` §3 |

兩個重要的現有限制：
1. 成員發佈路徑（192 KiB、只收 skill／workflow、每版都要管理員審核）**不適合**資料快照，需要另開。
2. `knowledge` 套件的路徑規則只收 Markdown，**裝不下** SQLite 或結構化卡片；硬塞會把 Knowledge 的檢查放寬，所以不建議重用 `knowledge` 種類（§2 A 的變體 A′）。

## 2. 選項比較

### A. 不可變快照，新的平台資產種類 `bi_dataset`（建議）

owner 的 Agent 從本機 `bi.sqlite` 打包一個快照（gzip 的 JSON，格式 `aep-bi-dataset-snapshot/1`），
發佈到平台成為 `<namespace>/<name>@<version>`。同事選取後，既有 sync 把它裝成本機唯讀資料集。

### A′. 同 A，但重用 `knowledge` 種類

只省下「新增一個 kind 字串」，卻要放寬 `PortableKnowledgePackage` 的路徑規則、讓 Knowledge 安裝器
認得 SQLite／卡片，還會讓 Marketplace 把 BI 資料和 vault 混在一起。**不建議**，以下不再展開。

### B. 平台上的即時讀寫 API

資料集只存在中央（141 上一個 SQLite），平台提供 `/v1/bi/<dataset>/cards`、`/dashboard`、`/query`
與寫入（帶 `base_version`）；每台 Agent 的 BI 頁與 `bi__query` 都改成呼叫平台。

### C. 不經平台：匯出檔／匯入檔（備案）

owner 匯出快照檔（與 A 同一格式，副檔名 `.aepbi`），放在 OneDrive／`S:\` 共用資料夾或私訊給同事，
同事在 Agent Web 匯入。

### 比較

| | A 快照資產 | B 即時 API | C 匯出／匯入 |
|---|---|---|---|
| **工作量** | 中：約 8–10 天（§8.3） | 大：約 15–20 天；BI store 要抽出儲存介面、平台要做讀寫、授權、並發與備份 | 小：約 3–4 天（只做打包、安裝、兩個按鈕） |
| **平台要加什麼** | `bi_dataset` kind、發佈端點（較大的本體上限、不經每版審核）、快照驗證、Marketplace／Overview 顯示、稽核紀錄 | 一整個資料服務：每個資料集的資料庫、讀寫 API、`stale_edit`、逐請求授權、備份、Dashboard 計算 | 不用加 |
| **一致性** | 版本快照：同事看到的是「某一版」，明確標示版本與發佈時間；owner 新改的要等下次發佈 | 強一致：大家看到同一份即時資料 | 同 A，但沒人知道誰拿的是哪一版 |
| **離線** | 完全可用（本機副本）；平台連不到時照常讀，只是看不到新版通知 | 平台或 tunnel 斷線就**讀不到**；對話與 Dashboard 都失效 | 完全可用 |
| **權限** | 沿用平台的名稱擁有權、`co_editors`、`NameAccess` 群組；選取時檢查 `entitled` | 同樣的群組，但每次讀寫都要檢查；寫入權限要新設計 | 誰拿到檔案誰就能讀；無法撤回、沒有群組 |
| **稽核** | 誰發佈哪一版（平台紀錄）；誰選取、哪台 Bridge 裝了哪一版（選取＋Bridge 狀態回報） | 每次讀寫都可記 | 沒有 |
| **與 #212 的關係** | 快照格式與儲存後端無關；#212 決定中央 DB 後，owner 的主資料可以搬過去，快照改由中央產生，或被 B 取代，同事端的唯讀副本仍可當離線快取。**不預先決定 #212** | 在 141 的 SQLite 上做中央服務，**等於提前替 #212 做了放置決定**；若 #212 選 PostgreSQL／別台主機，大半要重做 | 無關 |
| **主要風險** | 快照大小；INTERNAL 資料放在 141 | 141 的可用性（無自動重啟、公開測試機）；提前定案 #212 | 資料外流無法控管、版本混亂 |

**建議 A 作為第一個 slice。** 理由：
1. 平台已經有「不可變版本＋擁有權＋群組＋選取＋sync＋TLS 釘選」整套機制，A 只是新增一種內容；B 要在平台上新建一個資料服務。
2. #214 說「誰能讀由資料庫分享給誰決定」：A 的分享對象就是平台上的群組，正好對應。
3. 符合 local-first：同事離線、141 重開機或 tunnel 斷線時，對話與 Dashboard 仍可用。
4. 不替 #212 做決定。
5. C 是 A 的副產品：同一個快照格式，之後只要加「匯出檔／匯入檔」兩個按鈕就是備案（§9 slice 2）。

## 3. 角色

借用累積記憶的「一個 manager、多個 contributor／reader」模型（`ACCUMULATED_MEMORY.md` §3.8），對應到平台既有的擁有權：

| 角色 | 能做什麼 | 平台上的對應 |
|---|---|---|
| **Owner／maintainer** | 在自己電腦上維護主資料（匯入、編輯）；發佈新版本；決定誰能讀；加減共同維護者；deprecate 某一版 | `AssetNameOwnership.owner`（user 或 team）＋`manages()` |
| **共同維護者（co-maintainer）** | 發佈新版本（從**他自己的**本機主資料，見下方注意） | `AssetNameOwnership.co_editors`＋`may_publish()` |
| **Reader** | 訂閱、讀取（Knowledge 頁、Dashboard、對話） | `entitled()`：owner 群組的成員，加上 `NameAccess.groups` / `members` |
| **Contributor**（之後的 slice） | 對訂閱的資料集提出修改，由 owner 接受或拒絕 | 新增 `NameAccess.proposers`（或沿用一個群組）；slice 3 再定 |

**群組對應資料集存取：**
- 新資料集名稱預設由 owner 所屬的團隊擁有（`Owner{type: "team", id: <group>}`），`visibility: "team"`：該群組的成員都能讀，這就是 #214 的「分享給誰」。
- owner 可在 Member Portal「My published assets」加讀者群組或個人（既有 `NameAccess`），不必重新發佈。
- `bi_dataset` 不允許 `public`；`organization`（平台所有成員）要 owner 明確勾選並看到「INTERNAL 資料會給平台所有成員」的提示（§8.4 Q4）。
- 群組來源是平台的成員紀錄（`/v1/member/me`）。Agent 端的「本機宣告團隊」**不**給讀取權，只有平台判斷。

**誰能發佈新版本：** owner 與 `co_editors`（`may_publish`）。第一個 slice 不支援多位維護者在不同電腦各自改同一份主資料再合併：同一時間只有**一份主資料**（在 owner 的電腦上）。若共同維護者也要發佈，他必須先訂閱最新版、在本機「接手成主資料」（slice 2，§5），否則他發佈的會是另一條線。發佈時平台檢查 `base_version`：快照必須宣告它是從哪一版改來的，不是最新版就拒絕（`version_superseded`，與 Knowledge push 的「先推先贏」同精神）。

## 4. 版本與更新

### 4.1 快照 id 與版本號

- 身分：`<namespace>/<name>@<version>`，例如 `engineering/robotics-bi@1.3.0`；平台指定版本號（與成員發佈相同，作者寫的版本不被信任）。
- 規則：每次發佈 minor +1；綁定的 schema **major** 改變時 major +1；patch 保留給「只改版本說明／deprecate」以外不需要的情況（第一個 slice 不用）。
- 內容 digest：快照 artifact 的 SHA-256（`PackageMetadata.sha256`），sync 時先驗 digest 再讀內容。
- 快照 manifest 內含：`dataset`（owner 本機名稱，只作顯示）、`identity`、`base_version`（從哪一版改來，第一版為空）、`schema`（id@version 與 schema 檔的 SHA-256）、`classification: "INTERNAL"`、`published_by`、`published_at`、`note`（版本說明）、統計（各類型卡片數、欄位數、history 筆數）、`source_last_updated`（主資料最後修改時間）。

### 4.2 同事看到什麼

- Knowledge → BI 卡片的資料集選單分兩組：「我的資料集」與「已訂閱的資料集」。訂閱的顯示為 `robotics-bi 1.3.0 · leo.chi 發佈於 2026-10-21`，並有「唯讀」標記。
- 本機位置：`<workspace>/bi/subscribed/<namespace>__<name>/<version>/bi.sqlite`＋`snapshot.json`。以 SQLite 唯讀模式（`mode=ro`）開啟。`subscribed`、`schemas` 成為保留名稱，不能當本機資料集名。
- 保留目前版本與前一版（可一鍵退回），更舊的在更新成功後刪除。

### 4.3 新版本通知與 pinning

- Agent 已有 catalog 呼叫（Settings 的 sync／doctor）。訂閱的名稱若有比已裝版本新、且自己有權使用的版本，資料集旁顯示「有新版本 1.4.0」徽章，展開可看版本說明、發佈者、時間與卡片數差異。
- 更新是**本人按一下**（與既有「安裝一律是本人的按鍵」一致）：Agent 經 `/v1/member/select` 選新版本並 sync；成功後切換，舊版留作退回。
- **Pinning 就是不更新**：平台的選取本來就是確切版本。「固定在此版本」只是關掉徽章提醒；owner deprecate 某一版時，徽章改成「此版本已停用」，但仍可讀（不自動拿走）。
- 平台連不到時顯示「無法連線平台，目前顯示 1.3.0」，資料照常可讀。

### 4.4 Schema 跟著快照走

- 快照宣告 `schema: {id, version, sha256}`。
- 若為**使用者 schema**（`<workspace>/bi/schemas/` 下的），schema 檔本身放進快照 artifact；內建 schema（如 `bi.schema/v1.1`）只帶 id@version 與 digest。
- 同事 sync 時：
  1. 本機沒有該 schema id@version → 從快照安裝到 `<workspace>/bi/schemas/`，紀錄來源為「隨 `engineering/robotics-bi@1.3.0` 安裝」。
  2. 已有同一 id@version 且 digest 相同 → 直接用。
  3. 已有同一 id@version 但 digest **不同** → 整次 sync 拒絕（`schema_conflict`，與 `asset_conflict` 同樣不寫任何東西），提示「同一個 schema 版本有兩種內容，請 owner 換版本號」。
  4. 內建 schema 但本機 AEP 版本太舊沒有 → 拒絕（`schema_unavailable`），提示升級 AEP。
- 這依賴另一個 agent 正在做的「資料集綁 schema id@version」。本提案假設：綁定記錄在資料集內可讀到、schema 安裝目錄為 `<workspace>/bi/schemas/`、schema 由 id@version＋檔案內容唯一決定。若介面不同，只影響 §4.4 的實作細節。

### 4.5 Provenance 與 history 怎麼帶、什麼要拿掉

| 內容 | 快照中 | 理由 |
|---|---|---|
| `cards`（含 `version`、`synthetic`） | 帶 | 主體；`synthetic` 讓同事看到「範例資料／待驗證」 |
| `fields` 的值與來源（`kind`、`ref`、`by`、`at`） | 帶 | 同事要能看到「誰、何時、從哪個檔第幾列」 |
| `history` | 帶（預設，§8.4 Q3） | 「誰改的、為什麼」是 BI 卡片的價值之一 |
| `ref` 與 `imports.filename` 中的本機路徑 | **只留檔名**（去掉資料夾） | 不洩漏 owner 電腦的路徑與帳號 |
| `proposals`（匯入與人工值衝突的待確認） | **拿掉** | owner 尚未決定的內部工作，不是已發佈的事實 |
| `imports` | 只留 `id`、檔名、時間、`by`、`undone` | 讓 history 的 `import_id` 能對上 |
| 人名（`by`） | 帶平台帳號 | 都是內部同事、INTERNAL；需要時可在 Q3 改成匿名 |
| 任何像密碼／token 的內容 | **拒絕發佈** | 用既有 `reject_embedded_secrets` 檢查每個值，只回報是哪張卡哪個欄位，不回顯內容 |

同事端的 `card version` 與 owner 端相同，所以之後的提議（§5）可以帶 `base_version`，沿用 409 `stale_edit` 規則。

## 5. 同事的修改

**第一個 slice：唯讀。** 在訂閱的資料集上編輯、匯入、載入示範資料、復原都被拒絕（`dataset_read_only`，HTTP 409，頁面上的按鈕不顯示），對話的 `bi__query` 本來就唯讀。

**之後（slice 3）：本機修改變成提議送回 owner。**
1. 同事在訂閱資料集上按「建議修改」（不是「編輯」），填新值與理由；存成本機 outbox 的一筆提議：`{dataset identity, snapshot version, card key, field, base_version, base_value, new_value, reason, by}`。提議**不改變**同事看到的值，只在欄位旁標「你已建議：…（待 owner 處理）」。
2. 提議經 Member Portal 新端點送到平台，只有該名稱的 owner／co-editors 收得到（平台再檢查送出者是 reader 且在 `proposers` 中）。
3. owner 在 Agent Web 的 BI 卡片看到「同事提議」，逐筆接受或拒絕。接受 = owner 本機的人工編輯（`kind: human`、`by: owner`，理由註明「採納 X 的提議」），寫入 history；下一次發佈才會到同事那裡。
4. **與 owner 較新快照的衝突：** 平台或 owner 端比對 `base_version`：該欄位在提議之後被改過 → 提議標成「已過期」，同時顯示提議的值與目前值（與 409 `stale_edit` 的畫面相同），owner 仍可選擇採納。同事更新到新版本時，若某筆提議的欄位已變成提議的值，自動標「已採納」；被拒的顯示 owner 的理由。
5. 同事**不能**在訂閱副本上保留私下改過的值：避免同一張卡在不同電腦有不同答案、對話引用時說不清版本。

**「接手成主資料」（slice 2）：** 共同維護者或 owner 換電腦時，可以把訂閱的最新版轉成本機可寫的資料集（複製一份，記錄 `base_version`），之後從這份發佈。這讓「主資料在哪台電腦」可以移動，但一次只有一份能發佈（平台的 `base_version` 檢查）。

## 6. 安全與隱私

- **分類：** 快照 manifest 固定帶 `classification: "INTERNAL"`；同事端讀取與對話時，資料只送往公司內部 gateway（#214 的模型路由），與本機資料集相同。
- **只有預期的群組拿到資料：**
  - 平台只把快照放進有權使用者的 sync plan（既有 `entitled_in`）；選取時就檢查，不是下載後才擋。
  - `public` 不允許；`organization` 要明確勾選並提示（§8.4 Q4）。
  - **被移出群組／名稱權限被收回：** 下次 sync 平台**有回答**且資料集不在授權內時，Agent 刪除本機副本（不只是隱藏），並記一行「已移除（權限收回）」；平台連不到時**不**刪（與既有「連不到不等於撤銷」一致）。見 §8.4 Q2。
- **快照中沒有秘密：** 打包時 `reject_embedded_secrets` 掃每個值；路徑只留檔名；Agent 的 host.json、憑證、token 從不進快照。平台收到時再驗一次（不信任發佈端）。
- **稽核：**
  - 發佈：平台紀錄誰、何時、哪個名稱與版本、digest、大小、版本說明、`base_version`。
  - 同步：誰選取了哪一版（既有選取紀錄，含時間）；哪台 Bridge 已裝哪一版（Bridge 的狀態回報 `BridgeStateSnapshot` 已有 installed 清單）。
  - owner 在 Member Portal「My published assets」的資料集卡片上可看到「誰已訂閱、裝到哪一版」；管理員在 Overview 看到全部。slice 1 先做平台端紀錄與 API，畫面在 slice 1 只做最小的表格。
- **TLS 與指紋：** 不新增連接埠或憑證。發佈走 Member Portal（8776，成員的 Personal Agent 登入），sync 走 Bridge API（8775，Bridge token），兩者都用現有的 SHA-256 指紋釘選。
- **大小上限（slice 1）：**
  - 每個快照 artifact（gzip 後）≤ **8 MiB**，解壓後 ≤ **64 MiB**，卡片 ≤ **20,000**；超過回 `artifact_too_large`，在 owner 端打包時就先檢查。估計：一張卡含來源與 history 約 3–8 KB，1,000 張卡壓縮後約 1 MB，demo 的 104 張遠低於上限。
  - 發佈端點使用自己的本體上限（約 12 MiB，base64 後），不放寬其他 Member Portal 端點的 256 KiB。
  - sync 回覆目前把 artifact 以 base64 內嵌在 JSON；8 MiB 上限讓單次回覆仍在可接受範圍。若之後資料集變大，改成分開下載 artifact（slice 2 之後），不在 slice 1 做。
  - 平台上每個名稱保留所有版本（不可變）；管理員可 deprecate。
- **141 本身：** 141 是公開測試機（owner 2026-10-15），沒有開機自動啟動。INTERNAL 客戶資料放在上面需要 owner 先同意，或在換到公司主機前只用 demo／合成資料測試（§8.4 Q1）。

## 7. UI 變更

1. **Owner：「發佈到 Shared Platform」**（Knowledge → BI 卡片，資料集列旁）：
   - 對話框：資料集名稱（平台名稱，第一次發佈時決定，預設 `<團隊>/<本機資料集名>`）、讀者（預設「我的團隊 <group>」，可加群組／人；`organization` 需勾選確認）、**版本說明**（必填，一行）、預覽：卡片數、與上一版的差異（新增／修改／刪除卡數）、將拿掉的內容（待確認提議 N 筆、路徑只留檔名）、大小。
   - 發佈中與結果：「已發佈 `engineering/robotics-bi@1.3.0`」；第一次發佈若需審核（§8.4 Q5）顯示「等待管理員核准名稱」。
   - 錯誤以代碼說明：`version_superseded`（「平台上已有比你這份更新的版本，請先更新」）、`artifact_too_large`、`publisher_not_authorized`、`secret_found`（指出卡片與欄位）、`schema_conflict`、平台連不到。
2. **同事：「已訂閱的資料集」**（同一頁，資料集選單第二組，加一個「瀏覽平台上的資料集」）：
   - 列出自己有權讀的 `bi_dataset` 名稱（來自 catalog）：名稱、owner、最新版本、說明；按「訂閱」＝選取最新版＋sync。
   - 已訂閱：版本、發佈者與時間、「唯讀」；**更新徽章**「有新版本 1.4.0」→ 展開版本說明 → 「更新」；「固定在此版本」；「退回 1.3.0」；「取消訂閱」（取消選取並刪除本機副本）。
   - 平台連不到：灰色提示，不影響讀取。
3. **Dashboard 與卡片頁：** 訂閱資料集頂端顯示「資料來源：robotics-bi 1.3.0（leo.chi，2026-10-21）· 唯讀」；編輯、匯入按鈕不顯示。
4. **對話：**
   - `bi__query` 的 `dataset` 可以是本機名稱或訂閱的 `<namespace>/<name>`；只有一個可用資料集時自動選它。結果多帶 `source: {dataset, version, published_by, published_at}`。
   - Skill 指示：每個陳述照舊引用 `[卡片 <type>:<key>]`，回答最後一行寫「資料來源：robotics-bi 1.3.0（2026-10-21 發佈）」。
   - 若本機已有新版本徽章，回答後附一句「平台上有 1.4.0，尚未更新」。

## 8. 第一個 slice

### 8.1 範圍

**包含：**
1. 快照格式 `aep-bi-dataset-snapshot/1`（gzip JSON）：打包（§4.5 的帶與拿掉）、驗證、digest；與 BI store 的唯讀讀取介面（不改主資料的寫入路徑）。
2. 平台：`bi_dataset` 加入 `AssetKind`；Member Portal 發佈端點（owner／co-editors 直接發佈，第一個名稱依 Q5）；`base_version` 檢查；平台指定版本號；大小上限；秘密再檢查；`public` 拒絕；發佈與選取的稽核紀錄；Marketplace／Overview 顯示新種類。
3. Agent sync：`bi_dataset` 安裝器（全部驗證後才寫，裝到 `bi/subscribed/...`，同名同版本不同內容 → `asset_conflict`），schema 隨快照安裝與 `schema_conflict`；保留目前與前一版；權限收回時刪除（依 Q2）。
4. Agent Web：發佈對話框、已訂閱清單、更新徽章、更新／固定／退回／取消訂閱、唯讀標示（`web_page.py`、`bi_cards_api.py`：要在另一個 agent 完成 schema 工作後再改）。
5. 對話：`bi__query` 支援訂閱資料集與版本引用。
6. 文件：`docs/CONTRACTS.md` 新增 `bi_dataset` 與快照格式；`docs/DECISIONS.md` 一條；使用說明一節。

**不包含：** 同事提議（slice 3）；接手成主資料與匯出檔／匯入檔（slice 2，C 的備案）；B 的即時 API；分開下載大型 artifact；多位維護者合併；#212 的中央 DB；自動更新。

### 8.2 驗收測試

自動（pytest，平台用既有的 in-process 參考實作）：
1. 由固定的資料集打包兩次，digest 相同；proposals 不在快照中；`ref`／檔名不含資料夾；含 `password=` 的欄位使打包失敗並指出卡片與欄位、錯誤訊息不含該值。
2. 團隊成員發佈 → `1.0.0`；再發佈（`base_version: 1.0.0`）→ `1.1.0`；用舊的 `base_version` 再發 → `version_superseded`；非成員發佈 → `publisher_not_authorized`；超過上限 → `artifact_too_large`；`public` → 拒絕。
3. 群組成員在 catalog 看到並可選取；非成員看不到，選取 → `asset_not_entitled`。
4. sync 安裝：digest 不符 → 拒絕且工作區不變；重複 sync 冪等；本機缺 schema → 從快照裝上；同 id@version 不同內容 → `schema_conflict` 且什麼都不寫。
5. 訂閱資料集：`/api/bi/cards`、`/api/bi/dashboard` 回傳與 owner 端相同的卡片與 Dashboard；任何寫入路徑回 409 `dataset_read_only`；本機 `datasets()` 不把 `subscribed`／`schemas` 當資料集。
6. 新版本發佈後，Agent 顯示徽章；按更新後切到新版、前一版仍在、可退回；固定後不再提醒。
7. 平台連不到：訂閱資料集照常可讀，徽章顯示「無法連線」；平台回答權限已收回：本機副本被刪除並有紀錄。
8. 稽核：平台紀錄含發佈者、版本、digest、選取者、已裝的 Bridge。
9. `bi__query` 對訂閱資料集的結果帶 `source.version`；Skill 的回答最後一行有版本（用既有的對話測試替身）。
10. UI 瀏覽器測試（深色、390 px）：發佈對話框、已訂閱清單與徽章、唯讀狀態。

現場（owner 在場，依 GUI 測試時段規則）：owner 電腦發佈 demo 資料集 → 第二台電腦（同群組成員）訂閱 → Dashboard 與對話引用版本 → owner 修改一個欄位再發佈 → 第二台出現徽章並更新 → 把第二台的帳號移出群組 → sync 後副本消失。若 Q1 未同意，現場只用 demo／合成資料。

### 8.3 估計

| 工作 | 天數 |
|---|---|
| 快照格式、打包、驗證、唯讀讀取 | 1.5 |
| 平台：kind、發佈端點、版本與 `base_version`、上限、稽核、Marketplace／Overview | 2 |
| Agent sync 安裝器、schema 隨行、保留／退回／收回 | 1.5 |
| Agent Web：發佈對話框、已訂閱清單、徽章、唯讀 | 1.5 |
| 對話：`bi__query` 與 Skill 引用版本 | 0.5 |
| 測試、文件、141 部署與現場測試 | 1.5–3 |
| **合計** | **約 8–10 個工作天** |

前置條件：另一個 agent 的「資料集綁 schema id@version」先合併；141 平台需更新到含 `bi_dataset` 的版本（重啟前先確認 `/api/tasks` 與平台上無人在用）。

### 8.4 給 owner 的問題（每題附建議預設）

| # | 問題 | 建議預設 |
|---|---|---|
| Q1 | 141 是公開測試機。INTERNAL 的真實 BI 資料可以放上去嗎？ | **先不放真實客戶資料**：slice 1 在 141 只用 demo／合成資料驗收；真實資料等平台搬到公司主機，或 owner 明確同意 141 可以。 |
| Q2 | 同事被移出群組（或 owner 收回權限）後，他電腦上的副本要刪掉嗎？ | **要刪**：平台有回答且已無權限時刪除並記錄；平台連不到時不刪。 |
| Q3 | 快照要帶完整修改歷史（含修改者與理由）嗎？ | **帶**，但拿掉待確認提議，路徑只留檔名，人名保留平台帳號。 |
| Q4 | 讀者範圍允許「平台所有成員」（`organization`）嗎？ | **預設只給 owner 的團隊**；`organization` 可用但需勾選確認；`public` 一律不允許。 |
| Q5 | 發佈要經過 Review queue 的管理員核准嗎？ | **只有新名稱的第一版**要管理員核准（確認名稱、擁有團隊與讀者）；之後的版本由 owner／co-editors 直接發佈（資料不是可執行內容，由 owner 負責）。 |

更新是否自動？本提案預設**手動按「更新」並顯示徽章**，與既有「安裝一律是本人的按鍵」一致；除非 owner 想改，否則不列為問題。

## 9. 之後的 slice（概略）

- **Slice 2：** 匯出檔／匯入檔（選項 C，同一格式，給不能連平台的同事）；接手成主資料；Member Portal 的訂閱者表格完整版；大型 artifact 分開下載。
- **Slice 3：** 同事提議（§5）：outbox、平台轉送、owner 接受／拒絕、過期判斷。
- **#212 決定後：** 若採中央 DB，owner 的主資料搬到中央，快照由中央產生（格式不變），或在 B 的即時讀取上保留快照當離線快取。

## 10. 被捨棄的替代方案

- **重用 `knowledge` 種類（A′）**：要放寬 Knowledge 套件的路徑與內容規則，混淆兩種資產，省下的工作很少。
- **先做即時 API（B）**：工作量約兩倍、離線不可用，而且在 141 的 SQLite 上做中央服務等於替 #212 預先決定。
- **只做匯出／匯入（C）**：沒有權限控管、稽核與更新通知，違反 #214「由分享對象決定誰能讀」的精神；保留為 A 之後的備案。
- **把 `bi.sqlite` 原檔當 artifact**：會把 proposals、本機路徑與 SQLite 內部狀態一起帶出去，也無法逐值掃描秘密；改用明確欄位的快照格式。
- **同事可在副本上私改**：同一張卡在不同電腦答案不同，對話引用說不清版本；改成提議（slice 3）。
