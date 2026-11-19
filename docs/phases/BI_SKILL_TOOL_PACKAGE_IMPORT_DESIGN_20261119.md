# BI 判讀規則與資料處理工具「整包匯入／匯出」設計（2026-11-19，唯讀設計，未實作）

Owner 需求：「處理資料的 skill 和 tool，希望可以讓使用者 import 進來使用」；來源選「整包（資料夾/zip）」。
本文件只提設計，沒有改程式。另一個 agent 正在簡化 BI 頁面，所以 UI 只放進步驟 2 的「更多」選單。

## 0. 現況（設計依據）

- **判讀規則（skill）**：`<home>/skills/<name>/rev-<n>-<author>.md`，Markdown 加 frontmatter（`name, revision, schema,
  role(classify|extract), applies_to, card_types, table_recipes`），unit `skill:<home>/<name>` 指向目前版本
  （`src/knowledge/repo/skills.py`、`aep_bi/cards/vault_skills.py`、`docs/phases/KNOWLEDGE_REPO.md` §8）。跨領域的
  classify 在 `library/skills/classify/`，由 schema 產生。`vault.save_skill` 會檢查卡片類型與 `applies_to`，並把規則綁到
  vault 目前的 schema。
- **資料處理工具（tool）**：`<home>/tools/<name>/rev-<n>-<author>.<ext>`，一個版本一個檔，unit `tool:<home>/<name>` 只記
  `revision, author, path, sha256`（`vault_tools.py`、`card_model.py`）。**沒有說明欄位**。執行方式：`tool_runs.execute`，
  獨立 process（`-I`、空環境、300 秒）、audit hook 擋網路／子程序／原生函式庫／寫到 OUTPUT 以外；只能輸出 ≤20 個
  `.csv/.md`、合計 ≤50 MB。靜態檢查用 `tool_session.check_code`（可編譯、用到 `INPUT`/`OUTPUT`、≤200,000 字）。
  依 2026-11-12 決策，**不需要核准**（`requires_approval: False`）。
- **目前唯一的「包」格式**：分析包 `aep.bi.analysis_pack/v1`（`packs.py`，單一 JSON，≤200 個分析，有 import/export）。
  Shared Platform 的 bi_dataset snapshot 是整個資料集層級的，不適合拿來裝規則和工具。
- **版本**：所有內容都是不可變的版本檔加上 unit。staged 之後會成為待提交的改動，在「版本」區 commit 並 push 後才會共享，
  也可以 revert。
- **上傳**：BI JSON body 上限 8 MB（`bi_cards_api.MAX_BI_BODY_BYTES`）；原始串流上傳有前例（`/api/bi/sources/upload`）。
  先預覽、拿 token、再套用，也有前例（`migrate-domains`、`atlas-import`）。
- **owner 的參考工具**（`tests/fixtures/robotics_kb_sample/tools`、`bi_vault_example/tools`）是 CLI 腳本：用 argparse，
  `import bi_schema`、`yaml`，直接寫 vault 卡片。**它們不符合 INPUT/OUTPUT 合約**，匯入時會被判為「無效」並寫出原因（見 §4、§6）。

## 1. 包格式 `aep.bi.package/v1`

一句話：**根目錄放 `aep-bi-package.json` 描述檔，skill 沿用現有 frontmatter `.md`，tool 沿用單一 `.py`；資料夾和 zip 都收。**

```
<任意名稱>/                      zip 可以把這層直接放在根目錄，或多包一層資料夾（只接受一層）
  aep-bi-package.json           必要
  skills/<name>.md              與 vault 的 skill 版本檔格式相同（frontmatter + 內文）
  tools/<name>.py               與 tool 版本檔相同：一個檔，用 INPUT/OUTPUT
  README.md                     選用，只用於預覽顯示
  analyses.json                 選用：現有 aep.bi.analysis_pack/v1（交給 packs.import_pack，第二階段再做）
```

```json
{"format": "aep.bi.package/v1",
 "name": "robotics-ingest", "version": "1.2.0", "description": "機器人領域的判讀規則與表格轉換工具",
 "schema": "bi.schema/v1.1@5.0.0",
 "exported_from": {"vault": "...", "home": "robotics", "commit": "abc123", "at": "2026-11-19T10:00:00+08:00"},
 "contents": [
  {"kind": "skill", "name": "robotics-extract", "file": "skills/robotics-extract.md", "role": "extract",
   "applies_to": ["sources/vendor-tables"], "card_types": ["Account", "Ecosystem"],
   "description": "供應商表格怎麼讀", "sha256": "…", "from_revision": 3},
  {"kind": "tool", "name": "xlsx-to-csv", "file": "tools/xlsx-to-csv.py", "input_types": [".xlsx"],
   "output_types": [".csv"], "description": "把每張工作表轉成一個 CSV", "sha256": "…", "from_revision": 2}]}
```

- `name` 是包的代號（小寫英數字與 `-`）；`version` 用 semver，只用來顯示和記錄，不影響 vault 的版本號。
- `applies_to` **以 home 為相對路徑**（`sources/...`）。匯入時改寫成 `<目標 home>/sources/...`；匯出時把 home 前綴去掉。
- `schema` 是匯出當時的 schema。skill 檔自己的 `schema` 以 manifest 為準。相容性的判斷方式：`card_types` 全部存在於目標
  vault 目前的 registry，才可以匯入；匯入後由 `save_skill` 綁到目前的 schema。缺類型就列為無效，並寫出缺哪幾個。
- `sha256` 用來辨識「內容和現有版本相同」；`from_revision` 只是追溯資訊。
- 對應到現有儲存：skill 走 `vault.save_skill`（`home` 填目標工作領域），tool 走 `vault_tools.stage_text`。**不新增 unit 種類**。
  tool 的說明有兩個做法，請 owner 選（Q3）：(a) 寫進程式開頭的 docstring，unit 不變；(b) 在 `tool:` unit 加一個選用的
  `description` 鍵（`card_model` 只檢查必要鍵，舊資料不受影響）。

## 2. 匯入流程（最少 GUI）

1. 步驟 2「判讀規則」區的 `biRowMenu`（「更多」）新增「匯入」。點下後，在同一位置展開兩個按鈕：「選資料夾」
   （`<input webkitdirectory>`）和「選 zip」（`accept=.zip`）。瀏覽器無法用同一個對話框同時選資料夾和檔案，
   所以分成兩顆按鈕；也接受把檔案拖進來。
2. 上傳並預覽：
   - zip：以原始 body 串流上傳到 `package-upload`，用 XHR `upload.onprogress` 顯示「上傳 3.2 / 8.0 MB・00:04」。
   - 資料夾：瀏覽器只讀 `.json/.md/.py/.txt`，用 JSON 送出（≤8 MB），顯示「讀檔 12 / 30：tools/x.py」。
   - 伺服器解壓到 `<workspace>/bi/<dataset>/package_imports/<token>/`（放在 vault 資料夾外，1 小時後清掉），並且**不執行任何程式**。
3. 預覽表，一列一項，欄位是「種類・名稱・狀態・原因・動作」。狀態有：
   - **新增**：此工作領域沒有同名項目。
   - **更新既有**：同名項目存在、內容不同。匯入後成為第 n+1 版，舊版保留，可以 revert。
   - **相同（略過）**：sha256 與目前版本相同。
   - **衝突**：同名項目在本機有尚未 commit 的改動；同名 skill 的 role 不同；或目標是 classify（由 schema 產生、跨領域）。
     預設不勾選，並附「存成新版本」或「改名匯入（`<name>-<包名>`）」兩個選項。
   - **無效**：每一條原因都寫出來，例如沒用 INPUT/OUTPUT、無法編譯、缺卡片類型、檔名不合法、超過大小上限。不可勾選。
   - **警告**（可以匯入）：import 了沙箱沒有的模組（例如 `yaml`、`requests`、同包內的 `bi_schema`）會寫「執行會失敗」；
     `applies_to` 的資料夾在目標領域還不存在；schema 版本不同但類型都對得上。
4. 「匯入到 <工作領域名稱>」：預設勾選新增和更新既有。分批呼叫 apply，每批 10 項，按鈕旁顯示「寫入 4 / 9：xlsx-to-csv・00:02」。
   結束時在原處顯示「已加入 9 項待提交改動，到『版本』commit 並 push 後大家才會用到」，失敗的項目寫出實際原因。
   全部都是 staged 改動，「放棄改動」可以整批撤回。**任何情況都不會無聲覆寫**。
5. 匯入後，tool 可以照常用「試跑」驗證；寫不出合約的參考工具，用現有「和 AI 一起修改」改寫（tool_session）。

## 3. 匯出

「更多」裡再加「匯出」。點下後在原處列出此工作領域目前的判讀規則和工具，預設全選，可勾選。按「下載 zip」，由伺服器用
`zipfile` 產生上面的版面和 manifest：`applies_to` 去掉 home 前綴，填入 sha256、from_revision、目前 commit。
尚未 commit 的項目會標「含未提交版本」，但仍可匯出。classify 預設不勾選，因為它是由 schema 產生的。
進度顯示「打包 5 / 12：robotics-extract」，最後提示下載。

## 4. 驗證與安全（無核准關卡，依 2026-11-12 決策）

- **zip 結構**：拒絕絕對路徑、`..`、磁碟代號、反斜線、NUL、symlink（external_attr）、大小寫不同但其實重名的檔案、
  Windows 保留名稱。解壓前就逐項檢查 header。
- **數量與大小**：zip ≤20 MB、解壓後合計 ≤50 MB、≤200 個檔、≤100 個項目、單一項目的壓縮比 ≤100（防 zip bomb）。
  `.py` ≤200,000 字（沿用 `vault_tools.MAX_TEXT`）。skill 沿用 `save_skill` 的限制。全部檔案必須是 UTF-8。
  其他副檔名列為「略過（不支援）」。
- **manifest**：`format` 必須正確；`contents[].file` 必須存在，而且只能在 `skills/`、`tools/` 底下。名稱用 `homes.id_problem`
  檢查，長度 ≤60。包裡有檔案但 manifest 沒列，會列出並略過。
- **tool 靜態檢查**：`tool_session.check_code`，再加 AST 掃 import，與 `tool_runs.RUNNER` 預載清單比對，不在清單的寫成警告。
  不在匯入時試跑；執行一律走現有沙箱（`tool_runs.execute`），沒有另開的路徑。沙箱本身是「防失誤，不是防惡意」
  （`listing.guard`），預覽頁要照實寫出這一點。
- **skill 檢查**：`vault.checked_skill`（parse frontmatter、卡片類型、applies_to）。fenced 內文只當資料，不會送給模型執行。

## 5. API、檔案、測試

- 路由（`host/bi_vaults_api.py`）：
  - `POST /api/bi/vaults/<id>/package-upload?home=&name=`：原始 zip 串流，回傳 `{token, preview}`。仿 `_upload_source`，
    用 `_refuse_unread` 處理超量。
  - `POST /api/bi/vaults/<id>/package`，三種 body：`{"preview": {"home", "files": [{"path", "text"}]}}`（資料夾）、
    `{"apply": {"token", "items": [{"id", "as": "new_revision"|"rename"}]}}`（分批）、`{"discard": token}`。
  - `GET /api/bi/vaults/<id>/package-export?home=&items=a,b`：回傳 `application/zip` 附件。需要在 handler 補二進位回應，
    目前 BI 路由只回 JSON。
- 新檔 `aep_bi/cards/packages.py`：FORMAT、`read_zip`/`read_files` → 正規化後的檔案清單、`preview`、`apply_batch`、
  `export_zip`、token 存取與過期處理。
- 改動：`host/bi_vaults_api.py`、`host/bi_cards_api.py`（串流上傳進入點）、`host/bi_page.py`（「更多」兩項、預覽表、進度）；
  依 Q3 決定是否改 `vault_tools.py` 與 `card_model.py`。
- 文件：`docs/CONTRACTS.md` 新增 `aep.bi.package/v1`；`docs/phases/BI_CARD_MODEL.md` P2-a 註記；`docs/DECISIONS.md`；`docs/TASKS.md`。
- 測試 `tests/test_bi_packages.py`：匯出後再匯入結果相同；zip 與資料夾得到相同的預覽；zip slip、symlink、zip bomb、
  檔數超量、非 UTF-8；manifest 缺檔或檔案沒列；新增／更新／相同／衝突／無效五種分類；更新變成 rev n+1 且舊版仍在；
  衝突預設不匯入；改名匯入；缺卡片類型的 skill 判為無效；`applies_to` 改寫成目標 home；tool 缺 INPUT 判為無效、
  沙箱外 import 給警告；token 過期與重複 apply（at-most-once）；分批進度的 n/N。
  頁面測試（現有 bi_page 字串測試）檢查「更多」裡有匯入和匯出、進度元素就在按鈕旁邊。
  fixture：`tests/fixtures/bi_package_example/`，包含合格、不合格各一個 tool 和兩個 skill。

## 6. 需要 owner 決定的問題

1. **Q1 沒有描述檔的資料夾**（例如直接選 owner 的 `tools/` 資料夾）要拒收，還是自動推斷（`skills/*.md` 有 frontmatter 就是 skill，
   `tools/*.py` 就是 tool）再標警告？建議推斷。
2. **Q2 CLI 腳本**（argparse、import 同包模組、pyyaml，例如參考的 `bi_ingest.py`）照合約判為無效，還是以「需改寫」狀態匯入，
   再由 AI 改寫成 INPUT/OUTPUT？建議判為無效，並附「用 AI 改寫」連結。工具也只支援單檔，不支援多檔。
3. **Q3 工具說明**存在 docstring（不改格式），還是在 `tool:` unit 加 `description`？
4. **Q4 衝突的預設**是「存成新版本」還是「改名匯入」？建議同 role 存成新版本，不同 role 改名匯入。
5. **Q5 analysis pack** 要不要在同一個包裡一起匯入（第二階段）？包要不要能放到 Shared Platform 供他人下載？目前不做。
6. **Q6 匯入範圍**：只能匯入到目前的工作領域，還是可以選 `library/<entry>`？建議只用目前的工作領域，最簡單。
