# LLM Wiki（知識庫維護）Plugin 化範圍提案（草稿 r1）

日期：2026-11-18。狀態：**草稿，未經 owner 同意開工，未實作，未 commit**。
基準：`main@9b019e76`（BI 已是 bundled in-process Plugin `bi-knowledge.bi` 1.0.0，
Plugin API 1.2）。依據：`FEATURE_PLUGIN_ASSESSMENT_20261113.md` 第 3 步（LLM Wiki
第二個，先保留共用 asking 邊界）、`FEATURE_PLUGIN_BI_STAGE2_PROPOSAL_DRAFT_20261115.md`
r3 與 `docs/DECISIONS.md` 2026-11-16..18、AGENTS.md rule 22／23。

## 0. 結論先講

- 照 BI r3 同一套做：Wiki **維護**（intake／convert／curation pipeline、wiki
  repositories 與版本、知識庫維護 pane）打包成 `feature_plugins/llm_wiki`
  （Python 套件 `aep_wiki`），AEP 啟動時載入，安裝／更新後重啟生效；不做 iframe、
  token 隔離或 worker。
- Knowledge **問答**（harness、retrieval、引用、`knowledge_binding`、assistant
  knowledge 工具）以及問答要讀的 Wiki 資料格式**留在 core**，BI 與一般對話也靠它。
- 既有掛載點幾乎夠用；新增只限通用的：頁面片段排序、缺功能時的 stand-in 表。
- 與 BI 不同處：Wiki 的 CSS／JS 在 `web_page.py` 裡和 core 共用 helper 交錯，
  頁面「逐位元組相同」做不到便宜的版本，需 owner 決定驗收標準（§8 D2）。

## 1. 盤點（file:line，行數為 `wc -l`／區段；測試數為 `def test_` 粗算）

### 1a. 頁面（`src/host_runtime/web_page.py`，11,089 行）

| # | 位置 | 規模 | 歸屬 |
| --- | --- | --- | --- |
| P1 | CSS `248-410`、`426-452`（`.kp-*`、`#kn-*`） | 約 190 行 | 多數 Wiki；但 `.kp-actions`、`.kp-markdown` 被 Reviews（`2133-2155`、`8247-8360`）與記憶筆記（`10529`）用，`.kp-stage*`、`.kp-stepper`、`.kp-step-n` 被 BI 片段用 33 次 → 這幾條留 core |
| P2 | `1754-1767` Knowledge 標頭（`kn-note`、`kp-refresh`）與 `kn-tabs` 兩顆 tab | 14 行 | core shell（BI 已如此） |
| P3 | `1768-2098` `kn-pane-pipeline`（Pull／Ingest／Test 三步、`kp-repos`、`kp-ver` 版本、`kp-push-card`、Advanced） | 331 行，緊接 `<!-- KNOWLEDGE_PANE -->`（`2099`） | Wiki；但內含 `kp-status`（`1785`，被 core `kpRun` 用）與 `kp-askable`（`1814`，問答清單） |
| P4 | JS `8068-8077` `kpSandbox`、`pipeline()` | 10 行 | Wiki；但 Reviews `rvOpenSandbox`（`8195-8200`）直接呼叫 `pipeline`、`kpOpen`、`kpRun` |
| P5 | JS `8078-8134` `kpStatus`／`kpRun`／`kpKey`／`kpWithProgress`／`kpButton` | 57 行 | **core 共用**：Reviews（`8199-8382` 十餘處）、送審清單（`7693`）用 |
| P6 | JS `8419-8462` `loadKnowledge`、`8509-10034` 其餘 `kp*`（約 80 個函式：版本 `kpVer*`、repo、stepper、convert／reingest／push／bench timer、lint、rule diff、skill assist、merge） | 約 1,570 行 | Wiki；`kpVer*`（`8568-8773`）用 BI 的 `bh`／`biTime`／`biBadge`（無 BI 時由 `NO_BI_JS` 頂替，`11046-11064`） |
| P7 | JS `8460-8508` `askableRow`／`askableLoad`（寫 `kp-askable` 與 `bi-b-askable`） | 約 45 行 | **core（問答邊界）**：BI 片段 `bi_page.py:2955` 也呼叫 |
| P8 | JS `10939-10985` `loadKnowledgeTab`／`knShow`／tab 點擊 | 47 行 | core shell；寫死 `pipeline`／`bi` 兩名，讀 `/api/knowledge/pipeline` 與 `/api/bi/datasets` |

頁面打 `/api/knowledge/*` 23 處，其中 `ask`、`askable`、`askable/propose` 屬問答。

### 1b. Web 路由與方法（`src/host_runtime/web.py`，8,129 行）

| # | 位置 | 內容 |
| --- | --- | --- |
| W1 | import `68-90`（21 個 pipeline spec）、`225-227`、`234-244`、`304`、`351`、`353`、`355`、`358-359` | 靜態 import Wiki 維護模組 |
| W2 | `7194`、`7365` `knowledge_repos_api.handle`（GET／POST，R4a） | `knowledge_repos_api.py` 162 行 |
| W3 | GET `7203`、`7208`、`7213`、`7218`、`7265`、`7268`、`7281`、`7284`；POST 名單 `7383-7393`、上傳上限 `7450`、處理 `7467-7618` | pipeline／call、publish、push、convert、reingest、benchmark、skill-assist、refresh、review-proposal、progress |
| W4 | 方法 `6198-6432`（`knowledge_pipeline`…`push_status`，約 235 行）、`6609-6902`（convert／reingest／refresh／skill_assist／benchmark，約 295 行） | 移入 Plugin 的 `handle()` |
| W5 | Reviews／經驗：`experience_harvest` `2332`、`_outcome` `2458`、`review_proposal` `2621`、`2565-2580` 用 `_sandboxes()`／`_pipeline()` 把提案送進 Wiki sandbox | core Reviews → Wiki；無 pipeline 時已有 "manual" 退路 |
| W6 | 問答：`knowledge_binding.handle`（GET 首行）、`8008` `/api/knowledge/ask`、`4277-4390` `_named_knowledge`／`_skill_intended_knowledge`／`_knowledge_reply`、`6903-6917` | **留 core** |

### 1c. Host 組裝（`src/host_runtime/host.py`，2,655 行）

| # | 位置 | 內容 | 歸屬 |
| --- | --- | --- | --- |
| H1 | `93-138` pipeline contracts／specs import；`365` `ImageDescriber`；`372`、`375-393` | 靜態 import | 移 |
| H2 | `1402-1403`、`2581-2655` `_register_knowledge_pipeline`：由 host.json `knowledge_pipeline` 建 `KnowledgePipeline(Sandboxes…)`，註冊 21 個 `knowledge-pipeline/*@1.0.0` capability（permission `knowledge-pipeline.use`） | 約 75 行 | 移，經 `capability_bindings` |
| H3 | `2355` `wiki.set_benchmark(partial(wiki_bench.gate, …))` | push 前檢查測試紀錄 | 移，經 `startup` |
| H4 | `1618-1623` `catalog.register_live(manifest, wiki_repos.agent_source…)` | 問答讀 repo 的發佈版本 | **留 core** |
| H5 | `contracts.py:22,657` `knowledge_pipeline: KnowledgePipelineHostBinding` | host.json 設定型別 | 留 core（設定格式不變） |

### 1d. Python 模組與資產

| 群 | 檔案（行數） | 建議 |
| --- | --- | --- |
| 維護（只被維護端用） | `knowledge/pipeline.py`(1067)、`planning`(624)、`merge`(286)、`sandbox`(279)、`stage`(175)、`migrate`(350)、`conflicts`(161)、`wiki_work`(402)、`progress`(60)、`describe`(162)、`skill_guide/`（3 份 md，`pipeline.py:376-378` 讀）；`host_runtime/knowledge_repos_api`(162)、`wiki_bench`(99)、`knowledge_convert`(80)、`knowledge_reingest`(162)、`knowledge_push`(224)、`knowledge_publish`(214)、`knowledge_bench`(228)、`skill_assist`(136)；`capabilities/knowledge_pipeline/handlers.py`(388) | **移入 `aep_wiki`**，約 5,900 行 |
| 跨界（維護寫、問答讀） | `knowledge/wiki_repos.py`(375)：`agent_source`／`reading_folder`／`listing`／`VIEW_DIR` 被 `host.py:1622`、`knowledge_binding.py:33,290` 用；`create`／`commit`／`push`／`revert`／`tag`… 只維護用 | **拆**：讀取面留 core，寫入面移 Plugin |
| Wiki 資料格式（問答也讀） | `raw`(754)、`lint`(373)、`layered_index`(564)（`query.py:30-34` import）、`sections`(188)、`repo/wiki.py`(597，`:403` 匯入即 `register_type`)、`repo/*` 引擎、`questions`(122，BI 用) | **留 core**；Plugin 依賴它們 |
| 問答 | `query`、`query_rewrite`、`search_rounds`、`evidence`、`evolution`、`procedure`、`schema`、`market_matrix`、`vault`；`host_runtime/knowledge_harness`、`knowledge_binding`、`knowledge_observation`；`capabilities/knowledge_query` | **留 core，不碰** |
| 其他 core | `office.py`（`attachment_documents.py` 用）、`package.py`（`sync.py` 用）、`capabilities/knowledge_pipeline/contracts.py`（設定型別） | 留 core |

Skill：`assets.py` 目前**沒有** Wiki 專屬 shipped Skill（`:83` `knowledge_skill()` 是問答
Skill，留 core）；`skill_guide/*.SKILL.md` 是 pipeline 的引導檔，隨 Plugin 走，不經
`shipped_skills`。

### 1e. 測試

- 維護（import 需改名，斷言不改）約 29 檔、約 130 個：`test_knowledge_pipeline`(9)、
  `_pipeline_web`(9)、`_pipeline_host`(2)、`_repos_api`(6)、`_repo_pipeline`(5)、
  `_repo_agent`(3)、`_repo_ui`(1)、`_repo_long_paths`(1)、`_wiki_work`(5)、`_sandbox`(6)、
  `_scope`(5)、`_merge`(7)、`_stage`(4)、`_pull`(4)、`_push`(5)、`_publish`(3)、`_reingest`(5)、
  `_convert_job`(2)、`_progress`(5)、`_bench`(6)、`_files`(5)、`_wizard`(5)、
  `test_skill_assist`(4)、`test_wiki_bench`(2)、`test_planning`(9)、`test_conflicts`(5)、
  `test_migrate`(4)、`test_describe`(10)、`test_review_proposals`(5)。
- 問答／資料格式（留 core 不動）約 13 檔、約 165 個：`test_query`(26)、
  `test_knowledge_evidence`(37)、`test_knowledge_wiki_primary`(18)、`test_raw`(15)、
  `test_vault_asking_binding`(19)、`_e2e`(6)、`test_lint`(7)、`test_layered_index`(8)、
  `test_knowledge_sections`(7)、`test_knowledge_schema`(5)、`test_market_matrix`(3)、
  `test_knowledge_market_evaluation`(3)、`test_office`(11)。
- 混合：`test_agent_web`(83)、`test_product_e2e_05`(6)、`test_tasks`(6)、`test_agent_mail`、
  `test_assistant_tools`；BI UI 測試約 20 檔用到 `kp-` 類別或 `bi_page_driver`。
- 固定比較集：445 個 Knowledge 案例與 46 個 source hash（TASKS `5032-5036`）。

## 2. 該留 core 的理由

1. 問答邊界是 BI、一般對話、Telegram、外部 Agent（`aep_knowledge_*`）共用；評估
   文件要求先保留。搬動它等於改 Knowledge 路由／context 組裝，屬另一個 harness 範圍。
2. `query.py` 直接讀 `raw`／`lint`／`layered_index` 的格式；`repo/wiki.py` 在 import
   時登記 repository 型別。把它們移出 core，沒裝 Wiki 的 AEP 就讀不了已發佈的 wiki
   repo，也會讓問答品質依賴 Plugin 版本。
3. 共用 UI helper（P5、P7、`.kp-actions` 等）被 Reviews、記憶、BI 使用。
代價：Wiki 的**資料格式**改版仍需更新 AEP；Wiki 的**流程、頁面、API、工作**改版只需
更新 Plugin。實作時以 `requires_core`（`core_api`）管理。

## 3. 需要的掛載點（全部通用）

| 需求 | 用既有 hook | 新增（通用） |
| --- | --- | --- |
| 路由 W2-W4 | `handle`（token 後）；`refuses_post` | — |
| 21 個 capability | `capability_bindings` | — |
| `set_benchmark`、pipeline 建置 | `startup` | — |
| Reviews → sandbox（W5） | `service("knowledge_pipeline")`、`service("knowledge_sandboxes")` | — |
| 頁面 P1／P3／P4／P6 | `page_fragments`（`feature_css`、`knowledge_pane`、`feature_js`） | **片段排序**：目前依 plugin id 排序（`in_process.py:176,198`），`bi-knowledge` 會排在 `llm-wiki` 前，Wiki 頁片要在 BI 前。提議 manifest `in_process.page_order`（整數，預設 100） |
| 沒裝 Wiki 時 shell 仍呼叫的名字（`pipeline`、`kpOpen`、`loadKnowledge`、`kp-status`、`kp-askable`、`kp-refresh` 行為） | — | **stand-in 表**：把 `web_page.page()` `11070-11073` 的 BI 專用判斷改成 core 內一張「標記 id → 替身 CSS/HTML/JS」表，BI 與 Wiki 各一列（`NO_BI_*` 原樣保留） |
| `knShow`／`loadKnowledgeTab`（P8） | — | 不新增 slot；沒裝 Wiki 時以 stand-in CSS 隱藏 `pipeline` tab，邏輯不改 |

不新增：問答相關 hook（`bypasses_knowledge`、`askable_vaults`、`finish_answer` 不給
Wiki 用）、權限、approval、TurnEffects。

## 4. 階段

**階段 A：core seam，Wiki 仍內建（`features.BUILTIN` 或 bundled 原地）**

| 動作 | 內容 |
| --- | --- |
| 新增 `host_runtime/features_wiki.py`、`wiki_page.py` | 只轉呼叫既有函式；P1／P3／P4／P6 原樣搬成片段 |
| 修改 `web.py`、`host.py`、`web_page.py`、`features.py`、`plugins/in_process.py` | 改經 FeatureSet；路由順序、token 前後位置、上傳上限不變；加 `page_order` 與 stand-in 表 |
| 拆 `knowledge/wiki_repos.py` | 讀取面留原檔，寫入面搬 `wiki_repos_write.py`（仍在 core，B 階段才移） |
| 先寫 characterization（對現行程式為綠） | pipeline／repos API 代表回應、21 capability identity 與順序、Reviews 送 sandbox、Knowledge tab 選擇、頁面快照（見 §6）；`test_feature_set_without_wiki.py`（無 Wiki 能啟動、Knowledge 問答與 BI 正常、`sys.modules` 無維護模組） |

**階段 B：搬進 `feature_plugins/llm_wiki`（bundled，重啟生效）**

| 動作 | 內容 |
| --- | --- |
| 新增 | `plugin.json`（`llm-wiki.wiki` 1.0.0，`core_api` ≥1.3.0 <2.0.0，`in_process.package` `aep_wiki`）、`python/aep_wiki/{feature.py,host/,pipeline/,web/}`、`skill_guide/`；builder `scripts/build_llm_wiki_plugin.py --check` |
| 修改 | core wheel 不含維護模組；Windows bundle 附帶 Wiki Plugin，預設啟用，現有使用者無差異 |
| 修改 | 約 29 個維護測試檔機械式改 import；斷言零差異 |

## 5. 觸及的 harness 面與 rule 22 因果證據

| Harness 面 | 改動 | 為何 Skill 無法解決 |
| --- | --- | --- |
| Web routing | W2-W4 經 `FeatureSet.handle` | Skill 是 `SkillManifest` 資料（`agent/skills.py:91-114`），不能新增或移除 HTTP route |
| Capability registration | 21 個 `knowledge-pipeline/*` 經 `capability_bindings` | 註冊在 `host.py:2581-2655` 的 Python 啟動流程，Skill 選用發生在其後 |
| 啟動 state | `set_benchmark`、pipeline 建置經 `startup` | 同上，是啟動程式碼 |
| Reviews 提案路由 | W5 經 `service()` | 夜間提案送 sandbox 是 `web.py` 程式判斷，非模型行為 |
| 頁面組裝 | 片段排序、stand-in 表 | 頁面由 `web_page.page()` 產生，Skill 不能決定載入哪段 HTML/JS |
| Knowledge 問答／permissions | **不改** | — |

要解決的是「Wiki 維護程式靜態 import 在 core（W1、H1），改 Wiki 就得更新 AEP」；任何
Skill／Workflow 都不能改變 AEP 載入哪些程式，所以 Skill 方案在因果上不成立。

## 6. 必須不變的行為與驗證

不變：
- 問答答案、引用、`knowledge_binding` 清單；445 案例 ID／結果與 46 source hash 相同。
- `/api/knowledge/*` 所有回應、狀態碼、上傳上限；21 個 capability identity、permission
  `knowledge-pipeline.use`、policy；host.json `knowledge_pipeline` 格式。
- 資料路徑：`Repository(workspace, repo_id)` 下的 wiki repo、`published/`、`vault/`
  （`wiki_repos.py:37-39`）、sandbox root（host.json `sandbox_root` 或預設）、progress、
  bench 紀錄；不搬資料、不做 migration；停用／卸載不刪資料。
- rule 23：convert／reingest／push／bench／kpRun 的進度顯示（步驟、n/N、經過時間）不變。
- BI 頁面與 BI UI 測試；Plugin API 1.1／1.2 套件照常。

驗證：
1. 階段 A：characterization 先綠→改完仍綠；無 Wiki（只 BI）、無 BI（只 Wiki）、兩者皆無
   三種組合都能啟動、Knowledge 頁不出 script error、問答正常。
2. 頁面：依 D2 選項——(a) sha256 不變；或 (b) HTML 結構逐位元組相同、搬移的 CSS/JS 行
   多重集合相同、headless 瀏覽器對 Knowledge／Reviews／BI 所有元素 computed style 快照
   相同、全部 UI 測試通過，之後重新釘住新 hash。
3. 階段 B：從 bundled Plugin 載入後上述快照相同；更新驗收：AEP 不動，裝 Wiki 1.0.1（改
   一段可見文字與一個 API 欄位）→ 重啟 → 生效；停用→重啟→維護 tab 不出現、問答與 BI
   正常；import 錯誤的 Plugin 被略過並顯示原因。
4. 全套 pytest（自己的 `--basetemp`、`-p no:cacheprovider`），與最近基準比對；445 集。
5. ruff check／format --check、mypy（src+tests+feature_plugins）、wheel／sdist、pip check、
   bundle digest 與 builder `--check` 一致、core wheel 無維護模組。
6. 合成資料 headless 跑一次 pull→convert→ingest→test→push 與版本 commit／tag；live GUI
   排在 owner 不在電腦前的時段。獨立 review Critical 0／Important 0。

## 7. 風險與非目標

風險：
- Wiki JS 與 core helper 交錯（P4-P7），搬錯會在 Reviews 或 BI 才爆 → 三種組合的
  headless 測試與 stand-in 測試釘住。
- CSS 搬位置改變層疊順序（P1 原在 `248`，slot 在 `1077`）→ computed style 快照。
- `wiki_repos` 拆分若漏掉讀取面函式，問答讀不到 repo → H4 與 `test_vault_asking_*`。
- Plugin 依賴 core 的 `raw`／`lint`／`layered_index`／`repo` 內部介面，core 改它們時 Plugin
  須同步發版。
- `review_proposal`／夜間 harvest 經 `service()` 後，無 Wiki 時的 "manual" 路徑目前少測。

非目標：改問答 harness、retrieval、引用或模型選擇；把 `raw`／`lint`／`layered_index`／
`repo/wiki` 移出 core；iframe／token 隔離／worker；熱載入；Plugin 自帶第三方依賴；資料
搬移；新 UI 或 rule 23 新功能；共享平台側；push 到 main。

## 8. 需要 owner 決定的事

- **D1（rule 22 scoped consent）**：是否同意照本提案開工，觸及 §5 列出的 harness 面，
  先階段 A、驗收後直接階段 B。
- **D2（頁面驗收標準）**：(a) 堅持 sha256 不變——需在 CSS 與 JS 中再開 3-4 個位置型
  slot，並把 `askableLoad` 留在 Wiki 片段、core 另放替身，較複雜；(b) **建議**：畫面與
  操作完全相同、Wiki 的 CSS/JS 原樣移到既有 slot，以 §6-2(b) 證明後重新釘 hash。
- **D3（core／Plugin 界線）**：同意 Wiki 資料格式模組（`raw`、`lint`、`layered_index`、
  `sections`、`repo/wiki`、`wiki_repos` 讀取面）留 core；代價是格式改版仍要更新 AEP。
- **D4（通用掛載點）**：同意新增 manifest `in_process.page_order` 與 core stand-in 表
  （BI 的 `NO_BI_*` 一併改用此表，輸出不變）。
- **D5（預設）**：Wiki Plugin 隨安裝包 bundled、預設啟用；identity `llm-wiki.wiki`、
  套件 `aep_wiki`。

## 9. 本草稿的檢查界線

僅 `graphify query`、靜態閱讀與 `grep`／`wc` 計數；未修改 src／tests、未執行測試或
建置、未 commit。行號以 `9b019e76` 為準，實作前需重新核對；測試數為粗算。
