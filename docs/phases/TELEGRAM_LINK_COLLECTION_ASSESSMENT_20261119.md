# Telegram 連結收集 → BI 工作領域定時轉換與 Ingest：盤點評估（2026-11-19）

狀態：**唯讀評估，未實作、未取得任何 AGENTS22 consent**。本文件只盤點現況與缺口，供 owner 決策。

## 0. 需求（owner 原話摘要）

MD、PM、sales 平常從網頁、Threads、Instagram 取得新消息。希望他們把網址用 Telegram 傳給 AEP，
指定某個 BI 資料領域（工作領域），AEP 在固定時間自動轉換（convert）並 ingest。

## 1. 結論摘要

| 項目 | 判斷 |
|---|---|
| 一般網頁 | 可行，**大部分可以放在 BI Plugin 內完成**，不需要改 harness |
| Threads / Instagram | 技術上做得到「部分」內容；完整內容多半要登入，還有 Meta ToS 風險，需要 owner 決策 |
| 「自動」的意思 | 建議：自動抓取＋自動轉 Markdown＋自動啟動 AI Ingest → 停在**待審（review）**；不自動接受、不自動 push |
| 必須碰 core / harness 的地方 | (a) 排程完成後主動推播 Telegram 結果；(b) 不打指令、只貼網址也要確定性分流。兩者都是選配，各自要 AGENTS22 consent |

## 2. 使用流程（以最少操作為原則）

| 方案 | 操作 | 優點 | 缺點 |
|---|---|---|---|
| **A（建議 P1）指令式** | `/bi link <工作領域> <網址> [備註]` | 確定性分流（AGENTS 規則 8），不用經過模型，也不改 harness | 每次都要打領域 |
| B 預設領域 | 先 `/bi link 預設 <工作領域>` 一次，之後 `/bi link <網址>` | 打字更少，同樣不改 harness | 要記住每個人的預設領域（存在 plugin） |
| C 只貼網址 | 直接貼網址或從 IG/Threads「分享」到 bot | 最省事 | 目前純文字會進模型對話（`telegram.py` `_converse`），要確定性分流就得改 Telegram 路由＝harness，需要 consent；不改的話只能靠模型選工具，結果不保證 |

建議 P1 先做 A，同時支援 B（`/bi link <網址>` 沒寫領域時用預設）。回覆與管理指令：

- 收到後立刻回：「已收到，排入 <vault>/<工作領域>，第 N 筆，預計 HH:MM 處理」（或「這個網址已經在佇列，略過」）。
- `/bi links`：列出自己今天排入的連結和狀態（待處理/已轉換/待審/失敗＋原因）。
- `/bi unlink <編號>`：處理之前可以撤回。處理之後要撤回，改走既有的「刪除來源」。

## 3. 現況 vs 缺口

| 環節 | 已有（檔案） | 缺口 |
|---|---|---|
| Telegram 身分 | `TelegramIngressConfig.actor_for(sender_id)`：一個 Telegram 帳號對應一個 actor；沒對應的人會被拒 | 每位 MD/PM/sales 都要先完成對應（設定工作，不用改程式） |
| 指令確定性分流 | `/x y rest` → `command_to_message` → `x.y rest` → `CommandRouter.match`（`src/agent/routing.py`），把 `{"args": rest}` 交給 Skill 宣告的 `CommandBinding` capability；`RequestContext` 帶 `actor`、`channel` | BI 隨附的 Skill（`aep_bi/cards/manifest.py`，alias `bi`）目前**沒有 commands**。要加 `link`/`links`/`unlink` 三個 command，綁到新的 BI capability（在 plugin 內，屬於 Skill/capability，不是 harness） |
| 連結佇列（inbox） | 沒有 | 新的 plugin 資料表：id、vault、工作領域（home）、原始 URL、正規化 URL、送出者 actor、channel、chat hash、送出時間、備註、狀態、嘗試次數、錯誤碼、抓取時間、source_id、run_id |
| 排程 | Host 排程：`common/scheduling.py`（每日/每週、時區、`target_kind` = workflow \| agent_task）、`schedule_worker.py`（原子 claim、at-most-once、不補跑歷史）、`schedule_loop.py` 跑在 Agent Web resident（`cli.py:855`）；有排程 GUI（`schedule_web.py`）。**沒有 n8n**（owner 規則） | (1) Feature 沒有 `shipped_workflows` hook，plugin 不能直接附一個 Workflow，要另外安裝一個呼叫 `bi-cards/link_process` 的 Workflow 再排程；或 (2) 在 plugin 內自己設一個「每日 HH:MM」計時器。見 §4 |
| 抓網頁 | `integrations/browser.py`：用本機 Edge 走 DevTools，有自己的 profile（登入由人手動完成），可取 `document.body.innerText`；`capabilities/web`（`web/read`，`allowed_origins` 預設 `*`） | 沒有 HTTP 抓取＋HTML→Markdown 的轉換器；`convert.py` 只支援 CSV/TSV/Excel/PDF/Word/PPT/MD/TXT，**沒有 `.html`**。依賴只有 pydantic/tzdata/office；新增 HTML 抽取套件（例如 trafilatura、markdownify）要先查授權與維護狀態，也可以只用標準庫 `html.parser` 自己寫精簡版 |
| 存成來源 | `Staging.add_source(name, text\|content_base64, media_type, classification, folder, actor)`：同一份 sha256 只存一次（已有去重）；在 vault 裡依 `folder` 放進工作領域 | 原始抓取結果（raw HTML 或 JSON）要以**不可變來源**保存（規則 7），轉出的 Markdown 是 revision；provenance 寫在 Markdown 開頭（URL、送出者、送出時間、抓取時間、抓取方式、HTTP 狀態、標題） |
| 轉換 | `convert.convert`，加上 `source_markdown` revisions | 新增 `.html` 轉換分支（plugin 內） |
| Ingest | `ai_runs.start(...)` 背景跑 → `extracting` → `review`/`partial`/`failed`；需要 `AiRuntime`（模型）；沒有模型時回 `model_unavailable` | `AiRuntime` 目前只在 Agent Web 的 HTTP 路徑組出來（`bi_cards_api.py:1540–1571`，要用 `gateway`/`web`）。capability binding 只拿得到 `workspace_root`，**排程處理時怎麼拿到模型是技術缺口**（見 §4） |
| 審核 | 已有 review：接受/確認匯入、「全部套用」、「全部接受並匯入」（2026-11-18） | 不用改。審核人收到「有 N 筆待審」的入口連結即可 |
| 結果回報 | Telegram 只能**回覆**這次的訊息；`telegram.py` 沒有讓排程或 plugin 主動送訊息的介面；Agent Web 的工作清單（`web.tasks().tracked("bi-ingest", …)`）會顯示背景 ingest | 主動推播「今天 8 筆：6 筆待審、2 筆失敗（登入牆）」＝ core channel 變更，要 consent。不改的替代：使用者用 `/bi links` 自己查，審核人在 Agent Web 看 |
| Vault commit/push | `vault.commit` / `vault.push`（push 有 benchmark 關卡） | 建議**不自動 commit/push**：自動產生的來源和候選卡留在本機，由審核人審完再照現有流程 commit/push |
| 公司網路 | 連外走公司 Zscaler proxy（合法），有些網站會被擋 | 抓取失敗時回報真實的 OS/HTTP 錯誤碼，不要繞過 |

## 4. 程式碼該放哪裡

| 部分 | 位置 | 是否屬於 harness / core |
|---|---|---|
| `link`/`links`/`unlink` command、inbox、URL 正規化與去重、抓取器、HTML 轉換、處理流程 | `feature_plugins/bi_knowledge/python/aep_bi/cards/link_inbox.py`（新檔）、`convert.py`、`manifest.py`、`capability.py` | 否。屬於 plugin 的 Skill/capability |
| Inbox 資料 | 建議放在 vault 本機工作區旁邊的獨立 sqlite（例如 `<workspace>/bi/link_inbox.sqlite`），不動 BI store schema；或放進 staging DB 加一張表（要做 migration） | 否 |
| 定時處理 | 選項 1：既有 Host 排程＋一個 Workflow（呼叫 `bi-cards/link_process`，`side_effect: write`）。好處是沿用原子 claim、補跑與 GUI；缺點是要另外裝 Workflow，而且 capability 拿不到模型。選項 2：plugin 內的每日計時器，在 BI「管理」選單設時間。好處是一個畫面設定、拿得到 Agent Web 的模型；缺點是要自己做 at-most-once claim | 選項 1、2 都不改 core；但選項 1 若要讓 capability 取得 Agent Web 模型而去改 core 介面，就是 core 變更 |
| 主動推播 Telegram | `src/channels/telegram.py` 加一個「送通知給 actor」的服務，再透過 `Feature.service` 或新 hook 開給 plugin | **是** core/channel；Feature 目前沒有 Telegram 相關 hook（`host_runtime/features.py`）。要 AGENTS22 consent |
| 只貼網址的確定性分流 | `telegram.py` 在 `_converse` 之前比對 Skill `KeywordRule`（目前有模型時不會比對） | **是** harness（routing），要 AGENTS22 consent |

## 5. Threads / Instagram 可行性

| 項目 | 現況判斷（實作前要再實測） |
|---|---|
| 未登入抓取 | IG 貼文/Reels 頁面多半有登入牆，只拿得到 `og:title`/`og:description`（常含部分貼文文字、帳號、日期）；Threads 公開貼文有時能拿到 og 文字；兩者頁面都靠 JS 渲染 |
| 官方 API | Meta oEmbed（IG/Threads）需要 Meta App 與 token，回傳的是嵌入用 HTML，內容有限；Threads API 主要讀自己帳號的貼文。要申請 App 並受 Meta 平台政策約束 |
| 已登入的瀏覽器 profile | `browser.py` 已支援「人手動登入一次的獨立 profile」，技術上能讀完整貼文；但 Meta 服務條款禁止未經許可的自動化收集，帳號有被鎖的風險，也會綁住某個人的帳號 |
| 速率 | 每天少量（幾十筆）、逐筆間隔、失敗不立即重試，風險較低；大量抓會觸發封鎖 |
| 圖片 / 影片 | AEP 既有決策是**不做 OCR**（`convert.py` `NO_TEXT_MESSAGE`）。Reels 語音可以考慮用既有的 voice STT（faster-whisper，voice extras），但下載影片同樣有 ToS 問題 |
| 務實做法 | P2 先做「og 摘要＋使用者備註」：抓不到內文時回「只取得摘要，請把貼文文字一起貼上」，備註文字視為來源內容的一部分（標明是送出者提供的） |

## 6. 「自動」的定義（建議）

1. 送出時：只登記，不抓取（回覆要快，也不會在白天占用網路或模型）。
2. 排程時間到：逐筆抓取 → 存 raw → 轉 Markdown → 在該工作領域啟動 AI Ingest，停在 `review`。
3. 通知：審核人在 Agent Web 看到待審 run；（選配、需 consent）Telegram 推播摘要給送出者與審核人。
4. 不自動接受候選卡，不自動 commit/push（規則 7：來源可追溯，卡片經人審）。owner 若要「自動接受」，必須另外明確決策。

## 7. 風險與需要 owner 決定的事

| # | 決策 | 建議預設 |
|---|---|---|
| D1 | 第一階段支援哪些來源 | P1 只做一般網頁；Threads/IG 放 P2 |
| D2 | Threads/IG：只取公開摘要、申請 Meta App，或用已登入的 profile | 先只取公開摘要＋備註；登入 profile 要 owner 書面接受 ToS 與帳號風險 |
| D3 | 指令格式：A 或 A+B；要不要做 C（harness，要 consent） | A+B，不做 C |
| D4 | 排程方式：Host 排程＋Workflow，或 BI 管理選單的每日時間 | BI 管理選單（每個 vault 一個時間，每日或每週幾），最簡單 |
| D5 | 排程粒度 | 每日一次（例如 07:30），可加「立即處理」按鈕 |
| D6 | 誰審 ingest 結果 | 該工作領域的負責人（呼應「每個領域有自己的人」）；未指定時由 vault 擁有者審 |
| D7 | 自動化做到哪一步 | 到 `review` 為止；不自動接受、不自動 push |
| D8 | 資料分類預設 | 公開網頁內容預設 PUBLIC；附上的備註預設 INTERNAL（分類只影響可送哪個模型，不再擋存取，見 2026-11-17 決策） |
| D9 | 容量限制 | 單頁 raw ≤ 5 MB、轉換後 ≤ 1 MB 文字、每人每日 ≤ 50 筆、逾時 30 秒、失敗最多重試 2 次（隔天） |
| D10 | 主動推播 Telegram 結果（core 變更） | 建議做（體驗差很多），但要先取得 AGENTS22 scoped consent |
| D11 | 送出者沒有 vault 寫入權或領域不存在 | 立即拒絕並列出可用的工作領域 |

其他風險：模型成本（每篇 ingest 都要呼叫模型）、重複內容（同一則新聞轉載，sha256 不同；先用正規化 URL 去重，內容近似去重留到之後）、
付費牆網站、跟 Agent Web 搶模型（排在下班或清晨）、重啟時要確認沒有處理中的工作（規則 19）。

## 8. 分階段計畫

| 階段 | 內容 | 粗估規模 | Harness / core 面 | 測試 |
|---|---|---|---|---|
| **P1 一般網頁** | `/bi link`/`links`/`unlink`（含預設領域）；inbox；URL 正規化（去掉 utm/fbclid/igsh）與去重；HTTP 抓取（系統 proxy、逾時、大小上限）；`.html` 轉換；存 raw＋provenance；定時處理 → `add_source` → convert → `ai_runs.start` → `review`；BI 管理選單設時間，處理時顯示進度（規則 23）；`/bi links` 查結果 | M：約 900–1300 行（含測試） | 無（Skill command＋plugin capability＋plugin 計時器）。若選 Host 排程而要改 core 讓 capability 拿到模型 → 那部分要 consent | URL 解析/正規化/去重單元測試；inbox 狀態轉移；HTML 轉換 fixtures（中英文、亂碼、超大檔）；假 transport 抓取（不連網）；處理流程 at-most-once（重跑不會重複新增來源或 run）；Telegram 整合測試：`/bi link` 不經模型就到 capability（參照 `tests/test_telegram_ingress.py`）；錯誤碼回報；ruff format --check、mypy src+tests、只裝 dev,office extras（跟 CI 一致） |
| P1.5 主動推播 | 排程完成後用 Telegram 傳摘要給送出者與審核人；附 Agent Web 待審連結 | S：約 200–300 行 | **core channel**，要 AGENTS22 consent | 推播只送一次；未對應的 actor 不送；遇到 rate limit 退避；token 不進 log |
| P1.6 只貼網址（選配） | 純網址訊息確定性分流到 `bi.link`（用預設領域） | S | **harness routing**，要 consent | 只有網址才分流，混合文字仍走對話；回歸測試現有對話 |
| P2 Threads/IG 公開摘要 | 平台辨識；og/meta 抽取；需要 JS 時用既有 Edge headless 取 innerText；抓不到就請送出者補文字；備註併入來源 | M：約 500–800 行 | 無 | 對應各平台 HTML fixtures；登入牆判定；同一主機速率限制；Edge 程序有關閉（不殘留 headless Edge） |
| P3 進階（每項分別決策） | 已登入 profile 讀完整貼文；Reels 語音轉文字（voice STT）；近似內容去重；Meta 官方 API | L | 視方案而定 | 視方案而定 |

建議順序：owner 先決定 D1–D9 → P1 → 實測一週 → 決定 D10（P1.5）→ P2。
每個階段完工都要寫入 `docs/TASKS.md`；有技術決策就追加到 `docs/DECISIONS.md`。

## 8. Owner 修訂（2026-11-19）

- **範圍只做靜態內容**：網頁、Threads／Instagram 分享連結的文字與圖片資訊，以及傳到 bot 的檔案。
  不做語音、影片（含 Reels 轉文字）；**P3 不做**。
- Threads／IG：先用分享連結下載 HTML，取 `og:` 與頁面可見文字；拿不到全文時標「只取得摘要」，
  並讓傳送者在 Telegram 補一句文字。是否需要無頭瀏覽器渲染，以 owner 提供的實際連結實測後決定。
- 架構：owner 提的「多 Agent＋BI data agent 綁 bot」改為**同一個 bot＋BI 收集箱與排程**：
  多 Agent V1 只是對話內委派、不是常駐排程 agent；一台 Host 只綁一個 Telegram bot
  （`TelegramIngressConfig`，多 bot 屬 core 變更）。
  - 每個工作領域在 BI「管理」設：收集處理時間（convert＋ingest）、審核提醒時間。
  - 到時自動抓取→轉檔→ingest→候選卡停在待審；審核時間提醒；「全部接受並匯入」後自動跑該領域
    測試並更新 Dashboard，再通知結果。
  - 需 AGENTS22 同意的兩處（core）：Telegram 主動通知；不打指令直接分享連結的確定性分流。
- 待 owner 確認：P1 範圍、上述兩處是否做、§7 其餘建議預設。
