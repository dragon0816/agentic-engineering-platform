# AEP 功能 Plugin 結構評估：LLM Wiki、BI Knowledge 與未來模組

日期：2026-11-13。狀態：**修訂後已通過 Claude Code review：Critical0、Important0。
使用者條件同意已滿足，先推送文件，再依以下明確範圍開始第一階段開發**。
檢查基準：`it-owned-tool-access-20261112@a902df0f`；遠端 main 為 `267c75e4`。
使用者已澄清：對象包含 LLM Wiki、BI Knowledge，以及未來其他新功能。

## 結論與使用者體驗

可行，符合「新增功能不必修改核心 runtime」的既有架構方向；目前還不能只把
BI 或 Wiki 資料夾壓縮就成為完整 Plugin。需要先補一次通用的功能擴充介面，
將頁面、API、工作處理、資料存取與 Agent 能力的寫死掛載改成註冊機制。

使用者第一次仍需更新至支援 Feature Plugin API 的 AEP 版本。之後，相容
該 API 的 Plugin 可單獨安裝／更新，不需重新安裝 AEP。不是承諾任意未來功能
永遠不必更新核心：若需要新的核心契約或不同的執行環境，仍須更新 AEP。

目標操作：在 AEP 安裝 Plugin → 自動完成相容性／依賴／健康檢查 → 顯示新入口
→ 同一 session 可探索其工具並使用。**不新增 IT 核准、工具安裝／執行核准**。
實際軟體缺失、登入錯誤及執行失敗照實回報；相容性檢查不是人為工具准入名單。

## 目前已具備的基礎

| 既有能力 | 已查證的程式 | 可沿用程度與限制 |
| --- | --- | --- |
| Skill／Workflow 安裝、版本及同步 | `src/host_runtime/skill_packs.py`、`assets.py` | 沿用資產格式與安裝紀錄；不是完整 GUI／服務 Plugin 安裝器 |
| 工具探索／即時連接 | `src/host_runtime/tool_access.py`、`mcp_servers.py`、`src/capabilities/runtime.py` | 沿用工具 schema、成功結果、防重複執行；需補 Plugin 所有權與卸載註銷 |
| Bridge Extension 程序、套件、健康及回退 | `src/extensions/contracts.py`、`package.py`、`runtime.py` | 沿用 JSONL session、封裝 digest／health 等低層元件；manager 是單一 active slot，未接入 Host 啟動，不是可直接沿用的多 plugin 管理器。相容契約限 Windows／Python3.12，沒有 UI／API／migration 貢獻契約 |
| Registry 分發與版本 | `src/common/distribution.py`、`src/control_plane/distribution.py` | 沿用身份、版本、封裝、來源紀錄；目前 AssetKind 沒有 Feature Plugin 聚合型別 |
| 知識版本庫 | `src/knowledge/repo/repository.py` | 已有 RepoType/register_type，可保留通用版本機制；現有 type 以 Python import 註冊，不能直接視為外部 Plugin 協定 |

重要區別：既有 Application 是外部 Software 的目錄／整合資訊，不代表 AEP
會下載、啟動並掛載整個功能。既有 MCP 則提供工具，單靠 MCP 不會產生 AEP
側欄、頁面、schema migration 與資料生命週期。

另有實際缺口：`ExtensionManager.activate` 仍要求 `ExtensionActivationApproval`，
及裝置／policy 的 `_approve` 檢查。它是舊 Extension 基礎設施的路徑，不能
直接照搬成新的免核准 Plugin 安裝器。第一階段不呼叫其 `activate()`，也不修改
舊 manager；使用依 plugin id 管理多個 worker 的新 manager，重用低層通訊元件。
套件完整性、格式及可執行環境檢查與人為核准分開，不新增 IT／signer 准入名單。

## 需要修改的位置

| 層次 | 現況／耦合點 | 建議改動 | 影響 |
| --- | --- | --- | --- |
| Web GUI | `src/host_runtime/web_page.py` 直接包含 Wiki／BI 的 HTML、CSS、JS；`knPane` 寫死 pipeline／bi | AEP 留 shell、登入、導覽、主題；Plugin 宣告頁面／tab 與自己的靜態資源。保留穩定頁面 ID 與舊入口轉接 | 大；是主要拆分工作 |
| Web API | `web.py` 直接 import／呼叫 `bi_cards_api.handle`、`knowledge_repos_api.handle` 等 | 加入 namespace route registry／proxy；先經共同身份檢查再轉送，保留舊 API facade | 中至大；禁止用任意遠端 URL 取代已安裝 worker 目的地 |
| 領域後端 | `host_runtime/bi_*` 同時存放 HTTP adapter、AI agent、工作與輸出邏輯；Wiki 維護在 `knowledge/pipeline.py`、`wiki_repos.py`、`wiki_work.py` 等 | 先建立 facade，再把功能服務移入 Plugin worker／套件；透過穩定服務契約存取共用能力 | 大；不能只移動檔案而保留對整個 HostRuntime 的依賴 |
| 啟動與工具註冊 | `host.py` 直接註冊 `bi_cards_bindings`、`bi_cards_tools`；`assets.py` 直接附帶 BI Skill | 改由 Plugin 宣告其資產與能力，PluginManager 安裝／啟動後註冊，停用時只移除該 Plugin 的項目 | 中；屬 harness／dispatch 變更 |
| Agent／Knowledge | `host.py` 的 live wiki source、`web.py` 的 BI 分流、`assistant_tools.py` 的 BI native tool 都有領域特例 | 新增 provider／tool contribution 契約，以 adapter 保留既有問答與證據行為，不重新設計推理流程 | 高；Knowledge asking 最敏感的邊界 |
| 資料與 migration | BI 的 `bi.sqlite`、`search.sqlite`、vault registry、repository units／published view；Wiki 的原始檔／Raw／Wiki／版本 | Plugin 擁有 domain schema/migrations，資料放 workspace，與 Plugin 程式版本分離；保留通用 repository/provenance 能力 | 中至大；需能備份、升級及恢復 |
| 分發與生命週期 | Skill packs 與 Bridge Extensions 各自有部分能力，沒有全功能聚合安裝 | PluginManifest + 安裝帳本 + 相容性／依賴解析 + worker／UI／資產整體啟用與回退；重用既有元件 | 中至大；不要再造一套重複 Bridge executor |
| 打包與測試 | `pyproject.toml`、Windows preview build 目前把功能程式一起打包 | 核心版與 Plugin 產物分開建置；各自測試，建立核心／Plugin 相容矩陣 | 中；先維持 bundled plugin 相容安裝再分離 |

## 建議的核心／Plugin 邊界

```text
AEP Core
  Web shell + installed-plugin navigation + authenticated API proxy
  Plugin catalog/manager + package/compatibility + lifecycle
  Agent/Bridge contracts + model gateway + execution receipts
  Identity/session + artifacts/jobs + Knowledge evidence/provenance contracts
  Shared repository/version services
        |
        +-- LLM Wiki Plugin: UI + intake/convert/curation + wiki maintenance + assets
        +-- BI Knowledge Plugin: UI + schema/ingest/cards/dashboard + assets
        +-- Future Plugin: its pages/API/data/processing/assets
```

核心知道「如何掛載功能」，不應再知道某個功能有哪個表單欄位、哪種卡片或
哪個商業資料處理步驟。共用的來源／引用／模型資料規則維持在核心邊界。
Wiki 與 BI 業務 schema、匯入規則、dashboard 則歸各 Plugin。

建議組合「聚合 manifest + 獨立 worker + Web module」，沿用現有 Extension
低層程序通訊與 Skill pack 安裝能力。不是把外部 Python 模組直接 import 進
核心程序，也不是把整個功能全塞成一個沒有生命週期資訊的 MCP server。
獨立 worker 降低依賴與故障耦合，不宣稱它本身是 OS sandbox。

未來可執行 Plugin JS 的前端需要獨立 origin 容器與具版本的訊息/API 契約。
**第一階段只接受宣告式頁面，不提供 Plugin HTML／JS／iframe**。後續必須明定 origin、session
與事件來源，不把 AEP 管理 token 放進 Plugin JS，也不允許 Plugin 任意改動
shell DOM。同來源 iframe 並不自動隔離 DOM；需評估獨立 origin／sandbox
及容器 broker。不能直接套用現有唯讀報表 iframe，因其 CSP／表單／網路限制
與可互動功能頁面不同。這是掛載契約，不是工具使用核准。

## Plugin 應包含什麼

以下是建議格式，不是目前已支援的安裝檔：

```text
bi-knowledge.aep-plugin
  plugin.json          # id/version/core API range/dependencies/contributions
  web/                 # UI assets，依固定入口及 SDK 掛載
  backend/             # wheel／worker entrypoint／依賴 lock
  schemas/             # domain schema，與程式版本分開標示
  migrations/          # 帶版本、備份、恢復條件
  assets/skills/       # 既有 Skill manifests
  assets/workflows/    # 既有 Workflow manifests
  tools/               # typed declarations；實際 handler 在 worker
  samples/             # 可選的非公司測試資料
  checks/              # 安裝健康檢查／功能 smoke cases
```

manifest 至少要有：穩定 id、版本、所需核心 Plugin API 版本範圍、執行環境、
Plugin 依賴、頁面入口、API namespace、工具／資產清單、資料 schema 版本、
生命週期與健康檢查。套件不包含使用者的實際資料庫、文件、token 或密碼。

建議新增的結構（名稱為提案）：`common/plugins.py`、`plugins/manager.py`、
`plugins/context.py`、`host_runtime/plugin_web.py` 及對應 UI SDK。
其中 context 只暴露穩定的模型請求、檔案／artifact、工作、事件、來源證據及
repository 服務，不把整個 HostRuntime／Web handler 物件當成公開 SDK。

## 資料與更新：避免功能可拆、資料卻損壞

- 程式放 versioned plugin directory；使用者資料保留 workspace，可先沿用
  現有 `bi/`、`knowledge-repos/` 路徑。第一版不需搬資料路徑或換資料庫。
- BI vault 的 repository units／變更紀錄與證據必須保留；SQLite 是工作投影，
  search.sqlite 是索引快取。不能只複製 bi.sqlite 就宣稱完整遷移。
- Wiki 保留原始文件、Raw、Wiki、引用／衝突決策與版本，不在 plugin 化時重寫
  ingestion 或只保存最終整理文字。
- 安裝與啟用採 staging → 相容／依賴檢查 → migration／health → 一次切換
  contributions；中途失敗不留下半套 UI、工具或資產。跨 registry 採帳本／
  補償流程，不宣稱跨檔案與多資料庫具有一個天然 ACID transaction。
- 更新等 Plugin 自己的工作到安全點；既有 turn／run 固定所用版本，完成
  後再切換。第一階段只沿用目前每 turn、記憶體內的 TurnEffects 防重複執行，
  不宣稱跨 AEP 程序重啟的 durable receipts。不得重啟後自動重跑不確定的寫入；
  持久化 effect ledger 是後續需另列範圍的 harness 變更。
- 程式回退不等於資料回退。migration 要宣告舊程式能否讀新 schema；不能時
  需有備份恢復或前向修復策略，不能只把舊 wheel 啟動就當 rollback 成功。
- 停用／卸載預設保留資料；移除資料是獨立、明確的使用者操作。Plugin B
  使用中的共用依賴不能因卸載 Plugin A 而被移除。

## Knowledge asking 品質如何維持

第一輪保留目前 Knowledge Harness、retrieval／query、證據與引用驗證的
行為，以 adapter 接 Plugin；不趁拆分改選模型、重排來源或重寫答案流程。
資料提供者輸出至少保留 source identity、版本、頁面／段落／Raw 關係與資料
分類；前端換模組不應換掉回答使用的版本或來源。

以目前同445個 Knowledge 案例為固定比較集，並新增：未裝／停用 BI 不影響
Wiki 問答；未裝 Wiki 不讓普通對話或其他 Plugin 壞掉；同時安裝兩者時仍依
來源回答；升級前後 source IDs、引用、資料版本與模型 request 相符。
不能只確認 Web 頁面能打開，也不以 deterministic 測試保證所有真實模型品質。

## 建議開發順序與驗收

1. **通用契約與薄外殼**：明定 PluginManifest／API／資料與相容契約，以小型
   fixture Plugin 證明安裝後有新頁面、新 API、新工具、新 Workflow；卸載只
   移除自己的 contributions，核心 wheel／程序不需更換。
2. **BI 先行**：保留現有程式作來源，先接 facade／搬 UI，再抽服務；以 bundled
   Plugin 保留原有入口與資料，驗證後才改為獨立安裝。不要一次重寫卡片流程。
3. **LLM Wiki 第二個**：移出維護 GUI／pipeline 與資產；先保留共用 asking
   邊界，再逐步接 provider 契約。用第二個真實功能驗證沒有 BI 專用 Plugin API。
4. **獨立發佈**：核心與兩個 Plugin 分開產包；安裝、離線依賴、重啟後還原、
   schema 升級、失敗恢復、停用／卸載、共存與防重複執行全部驗收。

完成定義：在固定支援版 AEP 上，僅安裝／更新 Plugin 就新增完整功能；不改
核心原始碼、不重新 pip install AEP、不覆寫 AEP 虛擬環境、不要求 IT／工具
核准；Core＋Plugin 各自 lint/type/test/build 通過，Knowledge 同集比較無退化。
未安裝功能的環境也必須能啟動，不殘留引用該 Plugin 的硬編碼 import。

此變更範圍屬中大型結構拆分，最大工作是 GUI／Host 耦合與資料遷移生命週期，
不是 ZIP 工具。首次通用插件機制會涉及 routing、tool/provider dispatch、
session／run state 等 harness；Skill 無法新增 HTTP route 或改靜態掛載。
上述程式路徑是因果證據。使用者後續明確要求 review 通過後開始開發；條件同意
先限於下面的 Slice 1。BI／Wiki 抽離及未列出的 harness 擴充另待具體範圍同意。

## Claude Code review 修訂：Slice 1 明確範圍

使用者原話：「你先把這個計劃丟給 Claude code review，沒問題後，請 push
評估文件，並開始開發，有些可以平行處理的部分請開多個 subagent 來處理」。
補充偏好：「開 sub Agent，優先開 Claude code」。

review 第一輪 Critical0、Important5；I3 中的 owner-only／禁止 Agent 安裝建議
已由 reviewer 撤回，因與現行 direct install 契約及使用者要求不符。以下回應
I1–I5，需 reviewer 確認無未解 Important／Critical 才 push 並開始實作。
最終 reviewer `63582bfb-e29f-4ebb-88c2-2b0c062e2eaf` 已確認 READY；回覆
`b988e3e8-8a6a-4acd-8772-a906d4234bb6`。I1–I5 全部關閉，Minor 納入驗收。

### 第一階段功能與邊界

只做通用機制及非公司資料 hello fixture，**不搬移 BI／Wiki，不新增 Knowledge
provider/routing，不改既有 asking、資料分類或模型規則**。

- `src/common/plugins.py`：closed typed PluginManifest，穩定 id/version、Plugin
  API 相容範圍、runtime、精確依賴、namespace、宣告式 page、capabilities、
  Skill／Workflow assets、data schema 標記與 health。namespace／capability／
  page／asset identity 必須能判定唯一，不允許覆蓋核心或其他 plugin。
- `src/plugins/package.py`：有版本的封裝、精確檔案 digest、限量的 inert staging。
  第一版可採 closed JSON/base64 envelope，**不提供 ZIP 解壓**，因此不宣稱支援
  任意壓縮包。拒絕 traversal、絕對／drive／ADS 路徑、Windows reserved names、
  大小寫碰撞、symlink／junction 與超量內容。啟用時重驗 staged bytes，避免
  驗證後檔案被更改。hash 只證明內容一致，不宣稱來源可信或已通過業務驗收。
- `src/plugins/manager.py`：依 plugin id 的多 active 管理、安裝帳本、worker
  health、精確 ownership 註冊／註銷、失敗補償、啟用狀態重開後恢復。底層重用
  JSONL transport，不呼叫舊 ExtensionManager.activate 或建立假 ActivationApproval。
  不做資料 migration；若 schema 不相容則回實際 setup／compatibility failure。
  本階段 worker 使用 AEP interpreter 與 stdlib／既有 AEP dependencies，
  不往 AEP venv 安裝任何東西；Plugin 獨立 venv／第三方依賴解析留待後續。
- `src/host_runtime/plugin_web.py`：位於現有 Web 身份檢查之後的管理入口及
  `/api/plugins/<id>/*` namespace proxy，只能呼叫該已安裝 worker 的宣告 API；
  無任意 URL／port proxy。worker 僅接收到必要 request context，不接 AEP Web
  管理 token。Plugin 的回傳值不作為核心管理命令執行。
  不轉送 Authorization 或其他 HTTP headers，request／response 大小有上限，
  RPC 有 timeout；同一 JSONL worker 的請求序列化，crash 不自動重跑寫入。
- 宣告式 page 僅含結構化文字／資料及核心定義的顯示元件。由核心以 DOM
  `textContent` 等安全方式渲染，無 arbitrary HTML／JS／expression／iframe，
  因此不產生能讀 `TOKEN`／sessionStorage 的 publisher script。未來可執行
  GUI 與獨立 origin／scoped token 不包含在本階段。
- `host.py` 只加一次 generic PluginManager 啟動／註冊 hook；`web.py` 只加
  authenticated generic routing；`web_page.py` 只加 generic Plugin 入口與
  宣告式 renderer。這三個共用檔案由主 agent 單獨整合，避免平行互相覆蓋。
- Plugin capabilities 經 InstalledCapabilities／現有 TurnEffects，不改 Gateway
  或重做防重複執行。活躍 turn／run 不換版本、不移除正在使用的 bindings；
  更新回 busy 或延後至工作結束。每個 plugin 的資料與安裝程式版本分開。
- Bundled assets 使用 `skill_packs` ledger 語義：保留 user-modified、removed、
  switched-off 選擇。卸載只移除仍由此 plugin 擁有且未被修改的資產；保留資料。
  不建立 fake approved／verified，安裝成功不代表功能／業務驗收。

### 安裝來源與身份，不是新的工具核准

authenticated Web／CLI 明確動作即可要求 install/update/disable/uninstall。
後續 authenticated Agent tool 可在使用者工作需要該套件時直接安裝；第一階段
可暫不提供該工具介面，但不得把尚未實作寫成「Agent 不得安裝」的政策。
安裝帳本記 actor、channel、source、digest、result／failure；由對話觸發時記
turn／message reference，沿用當 turn 防重複語義。不要求逐次人工核准或 signer
名單；簽章只有真正驗證後才記有效，第一版不支援時不能假記 valid／trusted。
worker/API 回傳文字不會自動呼叫安裝入口；它沒有核心管理 bearer token。

### 必要測試與平行邊界

先完成並凍結 common typed contract，再平行 package／manager、Web module／
renderer helpers 與獨立 negative／integration fixtures；分配互斥檔案所有權。
主 agent 擁有 host.py／web.py／web_page.py 及最終整合／文件。

新測試：`test_plugin_manifest.py`、`test_plugin_package.py`、`test_plugin_manager.py`、
`test_plugin_web.py`、`test_plugin_assets.py`、`tests/fixtures/plugins/hello/`。
至少驗證安裝／健康／API／工具／page、兩 plugin 共存、失敗無半套註冊、重開
恢復、active work busy、不同 digest 同版本拒絕、downgrade 不靜默進行、依賴／
identity 衝突、tampered staging、路徑與大小限制、auth／namespace 隔離、XSS／
管理 token 不外洩、user asset 選擇及卸載保留資料。

回歸包含未裝 Plugin 的原有啟動、tool_access／capability／local_asset_install、
同445 Knowledge cases IDs/outcomes、Ruff／format／mypy／full suite／build。
fixture 只用本機合成資料，不執行真實公司模型、信箱、C4C 或公司儀器。

## 本次檢查界線

根據現有程式與契約做靜態追蹤，未安裝套件、未執行真實公司資料流程、未修改
runtime／Skill 實作、未合併 main、未更新 resident，也未宣稱 Plugin 已可用。
沒有程式改動，因此沒有重跑完整測試／建置；它們是後續實作的必要驗收。
先前 main 合併評估所發現的 legacy form「解說被當執行成功」問題另案處理，
不應混入 Plugin 拆分一起大改。
