# BI Knowledge Plugin 化 Stage 2 範圍提案（修訂草稿 r3）

日期：2026-11-16。狀態：**草稿，未經 owner 同意開工，未實作，未 commit**。
基準：`phase-plugins/bi-facade-20261114@b5547fcb`（Plugin API 1.1、bi-overview 已驗收）。
依據：`FEATURE_PLUGIN_ASSESSMENT_20261113.md` Stage 2；AGENTS.md rule 22。

修訂紀錄：
- r1（11-15）：先 in-process seam，最後才處理 UI。
- r2（11-16）：sandboxed iframe + broker 先行。**已由 owner 否決**。
- r3（11-16，本版）owner 原話：「為什麼一定要用iframe,來掛載目前的頁面，我不想要
  改變目前現有的頁面，希望這些頁面和運作程式可以透過安裝後，重啟aep,即可被引用」；
  「拿到token 到底有什麼關係，電腦是公司電腦，也只有使用者本人會用，不要做這種
  卡東卡西的設計好嗎」。因此 r3：**Plugin 的頁面片段與 Python 程式在 AEP 同一
  程序、同一頁面中載入；安裝或更新後重啟 AEP 生效；不做 iframe、不做 token
  隔離、不另開 worker 程序**。

## 0. 結論先講

- 做法：AEP core 留一組「功能掛載點」（頁面片段、HTTP 路由、工具、回答後處理、
  Knowledge 分流、啟動工作、Skill 資產）。BI 的頁面（現有 HTML／CSS／JS 原樣）
  與 Python 程式（`host_runtime/bi_*`、`capabilities/bi_cards`）打包成
  `aep.bi-knowledge` Plugin。AEP 啟動時讀已安裝且啟用的 Plugin，把程式加進
  import 路徑、呼叫它的 `register()`，把頁面片段放回現在的位置。
- 使用者看到的頁面和操作**完全不變**（裝了 BI Plugin 時，頁面輸出與現在逐位元組
  相同）。之後 BI 改版：在 Plugins 頁安裝新版 BI Plugin → 重啟 AEP。
- 什麼時候仍要更新 AEP：BI 需要 core 新增的功能、新的第三方 Python 套件，或
  core 改了 BI 用到的內部介面。Plugin 宣告相容的 AEP 版本範圍，不相容時 AEP
  照常啟動、略過該 Plugin 並在 Plugins 頁說明原因。
- 取捨（照實記錄，owner 已接受）：Plugin 程式以 AEP 同等權限執行，可以讀到 AEP
  的一切；只安裝自己團隊做的 Plugin。這是公司電腦、單一使用者下的選擇，不是
  安全隔離。
- Slice 1 的 worker 型 Plugin（例如 bi-overview）照常支援；r3 新增的是另一種
  「同程序、重啟載入」的 Plugin。

## 1. BI 寫死在 core 的盤點（file:line 證據）

行數為本 commit 的 `wc -l`；測試數為 `def test_` 粗略計數。

| # | 位置（file:line） | 規模 | 內容／依賴者 | 測試覆蓋 |
| --- | --- | --- | --- | --- |
| C1 | `web_page.py:1075-1473` CSS、`2497-3356` BI pane HTML（380 個 `bi-` id）、`12196-12229` `knPane` 切換、`12271-18999` BI JS（305 個 `bi*` 函式，區間內無非 BI 函式） | 約 400+860+6,730 ≈ **8,000 / 19,101 行** | 直接打 158 處 `/api/bi/*`；`knPane` 寫死 pipeline/bi 兩 tab | 33 個 `test_bi_*_ui.py`；39 檔用 `kn-pane-bi`／`bi_page_driver` |
| C2 | `web.py:113-114,143-149` import `bi_cards_api`、`bi_feed_api`、`bi_cards_tools.*` | 8,136 行檔 | — | 見下 |
| C3 | `web.py:7169` `bi_feed_api.handle`（**在 token 檢查之前**，Atlas 免 token 讀）、`7351` POST 405 | `bi_feed_api.py` 103 行 | Atlas feed | `test_bi_feed_api.py`、`test_bi_feed_server.py` 等 5 檔 |
| C4 | `web.py:7199`（GET）、`7370`（POST）`bi_cards_api.handle`；`bi_cards_api.py:1599-1635` 處理所有 `/api/bi/*`（61 個路徑，含 upload 8 MB、publish、subscriptions、atlas-embed） | `bi_cards_api.py` 1,635 行 | `route()`（`:153`）已是注入式純函式；`web_ai_runtime`（`:1483`）取 Gateway 的 knowledge model／drafting model、`web.tasks()`；`web_bench_runtime`（`:1525`）取 Gateway 給 4 個 harness asker | 59 檔引用 `bi_cards_api` |
| C5 | `web.py:4020` `bi_chart_files`、`4049` `atlas_embeds`、`4072` `with_bi_sources` 改寫回答 | 工具檔 753 行 | 回答完成（completion）後處理 | `with_bi_sources` 只 1 檔（`test_bi_subscriptions.py`）— **覆蓋缺口** |
| C6 | `web.py:4307` `_skill_intended_knowledge`：`bi_question()` 且 `bi_skill_on()` 時不走 Knowledge harness | 2 行分流；`manifest.py:97` | Knowledge asking 路由 | 3 檔引用 `bi_question/bi_skill_on`；445 Knowledge 集 |
| C7 | `web.py:4840` `observe_catalog`（平台 catalog 時更新訂閱 badge）；`2211-2240`、`7685` `aep_bi_query` 開關；`4998` `_publisher` | 約 40 行 | 共享平台／設定 | `test_bi_subscriptions.py`、`test_assistant_bi_query.py`(10) |
| C8 | `host.py:36-37,311,314` import；`1335-1341` `bi_cards_bindings` 註冊 `bi-cards/query@1.0.0` 進 `InstalledCapabilities`（帶 data approval classes）；`2360` `bi_vault.set_benchmark`；`2428` `bi_cards_tools(gateway)` 進 `gateway.host_tools` | 約 10 行 | tool registration／dispatch、啟動 state | 7 檔引用 `bi_cards_tools`；`test_vault_asking_e2e.py`(6) |
| C9 | `bi_cards_tools.py:172-191` Skill 開關 + 已安裝 capability 才提供 `bi__query`／`bi__atlas_show`；`:739` `with_bi_sources` | 753 行 | Web、Telegram、assistant MCP | 同上 |
| C10 | `assets.py:28,94` 附帶 `engineering/bi-knowledge@1.0.0` Skill（`manifest.py` 118 行，switched on） | 2 行 | Skill ledger；`bi_skill_on` 以 namespace `engineering` 判斷 | 2 檔 |
| C11 | `assistant_tools.py:31,56-62,208-219,296` `aep_bi_query` → `bi_assistant_query.py`(101) | 約 25 行 | 外部 Agent MCP 工具 | `test_assistant_bi_query.py`(10) |
| C12 | `channels/telegram.py:74,1963` `with_bi_sources` | 2 行 | Telegram 回答 | **無專屬測試**（缺口） |
| C13 | `knowledge_binding.py:375-382` `bi_vaults_api.askable_vaults` | 8 行 | 「問 vault」清單 | `test_vault_asking_e2e.py` |
| C14 | `sync.py:74,221,456-466,502` 訂閱資料集隨 sync 安裝 | 約 30 行 | 共享平台 sync 交易 | `test_bi_subscriptions.py` 等 |
| C15 | `capabilities/bi_cards/vault.py:413` 模組 import 時 `repo_engine.register_type(BI_TYPE)` | 1 行（副作用） | repository engine | vault 測試群 |
| C16 | `host_runtime/bi_*.py` 16 檔 | **6,458 行** | HTTP adapter、AI agents、bench、subscriptions、chart | 142 個 `test_bi*.py`，約 1,100 個測試 |
| C17 | `capabilities/bi_cards/*.py` 61 檔 + 5 份 schema JSON | **27,987 行** | store/vault/search/runs… | 同上 |
| C18 | `control_plane/bi_datasets.py`(817) 及 `app.py`、`member*.py`、`service.py`、`submissions.py` | 共享平台伺服器側 | 不同部署（平台），非 Host | 平台測試群 |
| D1 | 資料：`<ws>/bi/<dataset>/bi.sqlite`、`search.sqlite`（快取）、`bi/vaults/registry.json`、`bi/vaults/<id>/`、`bi/subscribed/<ns>__<name>/<version>/`、`bi-chat-charts/`（`store.py:64-77,271-348`、`bi_cards_tools.py:83`） | — | vault repository units 為權威，SQLite 為投影 | 既有 store/vault 測試 |


另：近一個月 270 個碰到 BI 的 commit 中，146 個改到 `capabilities/bi_cards`、
其餘多為 UI 與 `host_runtime/bi_*`，所以 UI 和後端程式都必須能隨 Plugin 更新，
只搬 UI 不夠。共享平台 `control_plane/bi_datasets.py` 只用到
`capabilities/bi_cards/snapshot.py` 的格式定義，這一檔留在 core。

## 2. 階段 A：core 功能掛載點（BI 仍內建，行為不變）

目的：core 不再直接 import BI，改經掛載點呼叫；為階段 B 鋪路；第一次可以測
「沒有 BI 的 AEP 能啟動」。

| 動作 | 檔案 | 內容 |
| --- | --- | --- |
| 新增 | `src/host_runtime/features.py` | `FeatureContribution`／`FeatureSet`：`startup`、`capability_bindings`、`host_tools`、`shipped_assets`、`public_get`（token 前）、`refuse_post`、`routes`（token 後）、`answer_files`、`answer_embeds`、`finish_answer`、`knowledge_bypass`、`assistant_tools`、`askable_vaults`、`observe_catalog`、`page_fragments`。全部選用；空 `FeatureSet` = 無 BI 的 core |
| 新增 | `src/host_runtime/features_bi.py` | BI 的 contribution：**只轉呼叫既有函式**，不改其內部邏輯 |
| 新增 | `src/host_runtime/bi_page.py` | 從 `web_page.py` 原樣搬出 BI CSS／HTML／JS，以 placeholder 放回原位置 |
| 修改 | `host.py`、`web.py`、`web_page.py`、`channels/telegram.py`、`assistant_tools.py`、`assets.py`、`knowledge_binding.py` | 改經 `FeatureSet`；路由順序與 token 前後位置不變 |
| 新增測試 | characterization（工具清單、`/api/bi/*` 代表回應、`with_bi_sources` 經 Web 與 Telegram、Knowledge 分流、assets 清單、頁面 hash）；`test_feature_set_without_bi.py` | 先對現行程式為綠，再改 |

`web_page.py` 與 shell 共用的 BI helper（`biVaultOf`／`biTime`／`biBadge` 給
Knowledge 版本面板、`biAtlasUrl` 給 chat、19000 行後的 schema 安裝 handler）
在實作前逐一列出：屬 BI 的進 BI 片段，被別處使用的改成通用 helper 留在 core。

## 3. 階段 B：從已安裝 Plugin 載入（重啟生效）

| 動作 | 檔案 | 內容 |
| --- | --- | --- |
| 修改 | `src/common/plugins.py` | Plugin API 1.2（additive）：新 runtime `in_process`，宣告 `python_root`（套件內程式目錄）、`entry`（`module:register`）、`web_fragments`（css／html／js 對應 placeholder）、`requires_core`（AEP 版本範圍）。1.1 套件照常 |
| 修改 | `src/plugins/manager.py`、`package.py` | 安裝到有版本號的目錄；`in_process` 安裝／更新／停用標示「重啟後生效」；ledger 記錄待生效版本 |
| 新增 | `src/plugins/loader.py` | Host 啟動時：讀 ledger → 檢查 `requires_core` → 把 `python_root` 加進 `sys.path` → import entry → `register(FeatureRegistry)` 回填 `FeatureSet`。任一 Plugin 失敗：略過、記錄原因、AEP 照常啟動 |
| 新增 | `feature_plugins/bi_knowledge/` | `plugin.json`、`python/aep_bi/…`（由 `host_runtime/bi_*`、`capabilities/bi_cards/*` 搬來，頂層改名為 `aep_bi` 避免和 core 套件名衝突）、`web/`（`bi_page.py` 的片段）、`assets/skills/bi-knowledge`、builder `scripts/build_bi_knowledge_plugin.py --check` |
| 修改 | `features_bi.py` → 移入 Plugin 的 `register()` | core 不再含 BI 程式 |
| 修改 | `pyproject.toml`、Windows bundle | core wheel 不含 BI；安裝包附帶 BI Plugin，**首次啟動自動安裝**，現有使用者看不到差異 |
| 修改 | `tests/test_bi*.py` 等約 142 檔 | import 由 `capabilities.bi_cards`／`host_runtime.bi_*` 改成 `aep_bi.*`（機械式改名，斷言不改） |

資料：`<workspace>/bi/...` 等路徑全部不動，不做 migration。Plugin 停用或卸載
不刪資料。

## 4. 必須不變的行為（A、B 兩階段都適用）

- 裝了 BI Plugin 時，`page()` 輸出與現在逐位元組相同；33 個 BI UI 測試原樣通過。
- 所有 `/api/bi/*`、`/feeds` 行為；工具清單（名稱、schema、順序）；
  `bi-cards/query@1.0.0` identity；`engineering/bi-knowledge` Skill identity 與預設開啟；
  回答的 BI 來源附註、圖表、Atlas embed（Web 與 Telegram）；`aep_bi_query` 開關。
- Knowledge 分流；445 個 Knowledge 案例 ID／結果與 46 個 source hash 相同。
- Plugin API 1.1 套件、bi-overview、golden v1 fixture 照常。
- 權限、approval、TurnEffects 不動。

## 5. 觸及的 harness 面與 rule 22 因果證據

| Harness 面 | 改動 | 為何 Skill 無法解決 |
| --- | --- | --- |
| Web routing | `/api/bi/*`、feed 經 `FeatureSet` 分派 | Skill 是 `SkillManifest` 資料，不能新增 HTTP route 或改 `web.py` 分派順序（`agent/skills.py:91-114`） |
| Tool registration／dispatch | `installed.register`、`gateway.host_tools` 經 `FeatureSet` | Skill 開關只能決定 `bi_cards_tools` 是否回傳工具（`bi_cards_tools.py:172-191`），不能改 `host.py` 的靜態 import |
| Knowledge 路由 | `web.py:4307` BI 分流經 `knowledge_bypass` | 分流在 Skill 選用之前的 Python 判斷 |
| 回答後處理 | `with_bi_sources`、圖表、embed 經 `FeatureSet` | 模型回覆之後的程式改寫 |
| 啟動 state | Plugin loader；`set_benchmark` 經 `startup` | 啟動流程是程式碼 |
| Permissions | **不改** | — |

要解決的是「BI 程式碼編在 core 裡、core 靜態 import BI」，任何 Skill／Workflow
都改變不了 AEP 載入哪些程式，所以 Skill 方案在因果上不成立。

## 6. 驗證

1. 階段 A：characterization 先綠 → 改完仍綠；無 BI 的 core 能啟動、Knowledge
   問答與 Plugins 頁正常、`sys.modules` 沒有 BI 模組。
2. 階段 B：從已安裝 Plugin 載入後，上面所有快照相同；**更新驗收**：AEP 不動，
   安裝 BI 0.x+1（改一段可見文字與一個 API 回應欄位）→ 重啟 → 看到新版；
   停用 → 重啟 → BI tab 不出現、AEP 其他功能正常；壞掉的 Plugin（import 錯誤）
   不阻擋 AEP 啟動且 Plugins 頁顯示原因；`requires_core` 不符時被略過並說明。
3. 全套 pytest（自己的 `--basetemp`），與 7029 passed／16 skipped 基準比對；
   445 Knowledge 集與 46 source hash。
4. 無快取 Ruff／format、mypy（src+tests+plugin）、wheel／sdist build、pip check、
   Windows bundle 含 BI Plugin 且 digest 與 builder `--check` 一致；core wheel
   不含 BI 模組。
5. 合成資料 headless 實測 BI 建立／匯入／dashboard／chat 引用；live GUI 實測排在
   owner 不在電腦前的時段。
6. 獨立 Claude Code review，Critical0／Important0。

## 7. 風險與非目標

風險：
- `web.py` 路由順序（feed 在 token 前、plugin_web 在 BI 前）搬錯 → 以順序與
  未授權請求測試釘住。
- 142 個測試檔的 import 改名量大 → 用腳本機械式改名，逐檔確認斷言零差異。
- BI 用到不少 core 內部模組（`knowledge.repo`、`common.execution`、
  `agent.gateway` 等約 15 個），core 改這些介面時 BI Plugin 也要跟著發新版；
  以 `requires_core` 與相容測試管理，之後再逐步收斂成正式 API。
- Telegram BI 回答目前無測試 → 階段 A 先補。
- CI 上 BI 瀏覽器測試偶發失敗（例如 `test_bi_many_sources_ui`）屬既有問題，
  不以重跑掩蓋，另行處理。

非目標：iframe、token 隔離、worker 化 BI、熱載入（不重啟就生效）、Plugin 自帶
第三方依賴、共享平台側 BI、資料搬移、LLM Wiki（BI 完成後照同一套做）、resident
更新、merge main。

## 8. 需要 owner 決定的事

已決定：同程序、重啟載入、頁面不變、不做 iframe／token 隔離（11-16）。

待決定：是否同意照本提案開工（先階段 A，驗收後接著做階段 B）。BI 的 AI 助手
（schema／skill／analysis／questions）在 r3 下隨 BI Plugin 一起搬，不需另外決定。

## 9. 本草稿的檢查界線

僅靜態閱讀與 `grep`／`wc`／`git log` 計數；未修改 src/tests、未執行測試或建置、
未 commit。行號以 `b5547fcb` 為準，實作前需重新核對。
