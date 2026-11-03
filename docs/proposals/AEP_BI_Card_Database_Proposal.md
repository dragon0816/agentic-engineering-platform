# AEP BI 知識卡片框架與 SQLite 關聯索引修改 Proposal

日期：2026-11-03  
對象：Claude Code／AEP 維護者  
版本：v1.2（簡化資料表；新增證據覆核與 benchmark 校準分工）  
狀態：設計提案，供現有程式盤點、review 與實作  
依據：本次 Leo 討論及所提供 BI 範例；尚未核對 AEP 現有程式與資料庫。

## 1. 修改目標與已對齊原則

將市場原始資料轉為可理解、可溯源、可審查的卡片，透過 SQLite 串成知識網路，支援 Robotics、Aerospace 等不同市場的檢索與分析。

1. 每張卡片是一個節點；每條關聯連接兩張卡片，有類型與方向，可串成鏈或網路。
2. 每種卡型 schema 定義一種卡片。現有較新版的 21 種卡型是起點，不是不可改動的固定集合。
3. 每張卡片的內容框架只有五類：標題、結構化屬性、摘要／用途／範圍、reference、時間。「具體知識內容」就是這些欄位的值，不另設第六類。
4. SQLite 主要保存卡片識別與位置、必要檢索索引，以及卡片間關係與依據。
5. type 表示知識種類；domain 表示市場。Robotics、Aerospace 不直接等同卡型。
6. 卡片不以分類 folder 作為 retrieval 邊界。新卡建議使用 cards/<stable-id>.md；原始資料、模板與系統資源另放。
7. 卡片與 DB 之間不可維護兩份可獨立修改的同一事實。

## 2. Claude Code 開工前先盤點

閱讀專案既有協作規範，盤點卡片格式、schema registry、ingest、SQLite tables、retrieval、權限、review、版本與 UI。列出「現況 → 提案 → 修改點」，優先擴充現有機制，不建立平行系統。

本文件中的 table、API、檔案位置是邏輯名稱；請依既有架構映射。若實作與本文假設不同，先記錄差異與理由，再採取符合既有架構的等效設計。不可為了套用提案而重寫 harness。

交付本次修改的程式、migration、必要驗證與說明，沿用專案 branch／PR 流程；不要自行合併或發布。

## 3. 五類卡片內容框架

| 類別 | 內容 | 必要性 |
|---|---|---|
| 1 標題 | 清楚描述核心對象或事情 | 草稿及正式卡必要 |
| 2 結構化屬性 | ID、type、schema version、domain、tags、卡型欄位、連結、可靠度／缺值狀態、維護審查資訊 | 身分必要；其餘依卡型與發布規則 |
| 3 摘要／用途／範圍 | 核心知識、能支援哪些問題、適用與不適用條件、事實／推論／矛盾說明 | 核心摘要必要；未知不得硬補 |
| 4 reference | 原始資料識別與位置、證據摘錄、支持／反駁哪項敘述 | 草稿可缺但標記；正式核心敘述需可追溯 |
| 5 時間 | 資料指涉時間、來源日期、建立／更新／最後確認時間、時間依據與重查時間 | 系統時間必要；其他保留未知 |

以上是呈現與邏輯分組；全部仍受完整 schema 規範。不要將 schema 限縮為 frontmatter 的 tags。

### 3.1 結構化屬性規則

- card_id 使用穩定、不依賴名稱與 folder 的識別碼，沿用現有 ID 系統。
- type 指向註冊的卡型 schema；schema_version 固定本卡採用的版本。
- domain 為可多選清單，允許跨市場共用。
- type schema 定義欄位型別、必填條件、列舉、關聯目標卡型、萃取規則與證據要求。
- 市場特有欄位使用註冊且版本化的領域擴充，不讓 LLM 每次自行產生新 key。只有新增需獨立管理的知識種類時，才評估新增卡型。
- confidence 不得由「被匯入」「通過格式驗證」自動升為 verified。區分知識採信程度與審查流程狀態。
- priority 不列為全卡共用必要欄位。既有值保留並標示其範圍未知；未定義評分者、情境、標準與有效時間前，不作全域排序依據。資源優先度由情境評估管理，本次不要求新增評分子系統。

### 3.2 缺值規則

以欄位值與 field_states 分開表達：

| 狀態 | 意義 | 值 |
|---|---|---|
| unknown | 適用但尚無資料 | scalar=null，list=[] |
| not_applicable | 不適用 | null 或 []，必要時說明原因 |
| pending_confirmation | 有候選內容待確認 | 保留候選值與依據 |
| confirmed_none | 確認不存在 | null 或 []，保留確認依據 |

有正常值且無缺值狀態時，依證據與 review 判讀。空清單本身不能推定 confirmed_none。JSON／YAML 的 null 不能寫成字串「N/A」或「不適用」。缺核心欄位可存 draft，但不可無提示地發布。

### 3.3 Reference 與時間規則

Reference 需支援：reference_id、來源 URI／raw asset ID、文件標題、頁碼／段落／音檔時間位置、必要短摘錄，以及 supports/refutes 的敘述位置。ingested_from 只表示中間匯入檔，不能替代原始證據。

可用穩定 claim ID，或版本內欄位路徑／段落 anchor 指向敘述；若使用後者，修改內容後必須檢查引用是否失效。原始來源保留，不因彙整而覆蓋。

有明確事件／期間就記錄原意；沒有日期時，用提供／匯入時間作為 reference_at，並標記 reference_time_basis=submission_fallback。不可將預設時間寫成事件實際發生日期。文字編輯只更新 updated_at，不自動更新 last_confirmed_at。

## 4. 示意卡片

以下為虛構資料及格式示意；實作可沿用現有 Markdown 格式，但必須等效涵蓋五類資訊。

```yaml
---
card_id: CARD-SL-001
type: supply_link
schema_version: "1"
domains: [robotics, wireless]
tags: [module]
attributes:
  supplier: CARD-ORG-A
  customer: CARD-ORG-B
  product: 模組 M
  supply_stage: sample
field_states:
  mass_production_date:
    state: unknown
    reason: 原始資料未提供
confidence: assumed
owner: domain-owner
review_status: draft
revision: 1
ingested_from: source_batch.csv
time:
  event_date: null
  source_date: null
  reference_at: "2026-11-03T10:00:00Z"
  reference_time_basis: submission_fallback
  created_at: "2026-11-03T10:00:00Z"
  updated_at: "2026-11-03T10:00:00Z"
  last_confirmed_at: null
  review_due_at: null
---
# A 公司提供模組 M 給 B 公司評估

## 摘要、用途與範圍
A 公司提供模組 M 給 B 公司評估；資料未確認量產採用。
用途：支援供應鏈辨識與後續需求查證。
範圍：只涵蓋模組 M 的送樣關係，不代表 B 全部產品均採用。

## References
- reference_id: REF-001
  source: raw://visit-note-001
  locator: 第 2 段
  supports: attributes.supplier, attributes.customer, attributes.product, attributes.supply_stage
  note: 訪談明確提到送樣，未提及量產。
```

審查意見與歷史可以引用既有 audit 系統，無須全寫進 frontmatter。related cards 顯示區由 SQLite 自動產生，不要求使用者再輸入一份。

## 5. SQLite：兩張核心表＋一張證據對照表

此處先定義業務上必須表達的資訊，不要求照抄為全新物理 tables。Claude Code 應映射現有 AEP tables，僅補不足部分。多租戶隔離、版本、審計與同步機制仍需保留，但優先沿用既有實作，不將全部工程欄位列為新增需求，也不要求維護者手填。

### 5.1 cards：卡片目錄

| 核心欄位 | 意義 | 填寫方式 |
|---|---|---|
| card_id | 唯一、穩定的卡片識別 | 系統產生／沿用 |
| type | 採用的卡型 schema | AI 建議，按 registry 驗證 |
| file_path | 卡片所在位置 | 系統記錄；若 DB 儲存內容則映射既有定位方式 |
| title | 方便顯示與搜尋的標題 | 從卡片同步 |

只有 card_id、type、位置是卡片目錄的基本責任；title 是便利索引。完整五類知識保存在卡片，schema version、domain、review 等資訊若需要查詢，可索引既有 metadata，不要求另建同名欄位或 table。

卡片改名／移檔維持 ID；ID 不重用。同名卡不等於同一對象。

### 5.2 relations：卡片關係

| 核心欄位 | 意義 | 填寫方式 |
|---|---|---|
| relation_id | 識別這一條關係，供證據引用 | 系統產生 |
| from_card_id | 起點卡片 | 由連結欄位或候選關係產生 |
| relation_type | 關係意義與方向 | 從註冊關係字典選取 |
| to_card_id | 終點卡片 | 由連結欄位或候選關係產生 |
| status | pending／inferred／confirmed／disputed／rejected | AI 提出，專家覆核；不等於審查流程狀態 |

前四欄表達連線；status 是避免推論被當成事實的最低語義要求。審查者、理由、時間與歷史沿用既有 audit／review 機制，不在此強制再加一組 review_status、confidence、owner 等欄位。

「關係範圍」必須能表達，但不強制加 scope_key：優先讓起點為已限定產品／專案的 SupplyLink 等卡片；若同一對節點確有不同情境的關係，才增加 scope metadata 並納入去重。不同範圍或時期不能盲目合併。

#### 必要實作行為

- 驗證目標 ID 與允許卡型，保留現有權限／知識庫隔離。
- 支援起點查詢與終點反查；不人工維護正反兩份關係。
- 能識別關係由 schema 欄位、AI 推論或人工建立，並追溯來源欄位；儲存方式可沿用 metadata／audit，不強制新欄位。
- 去重與同步不得誤刪人工／推論關係。刪卡、移檔、來源更新時處理失效連結。
- 關係時間與範圍優先引用依據卡片；若關係自身有不同有效期間，再保存必要 metadata。

### 5.3 relation_evidence：關係與證據的對照

這張表回答「哪條關係由卡片中的哪項 reference 支持或反駁」，不取代卡片的 reference，也不複製原始文章。

| 核心欄位 | 意義 |
|---|---|
| evidence_link_id | 這次證據對應的唯一識別，可供覆核引用 |
| relation_id | 對應哪條關係 |
| basis_card_id | 證據保存在哪張卡 |
| reference_id | 卡片內哪個 reference |
| stance | supports／refutes／context_only |

relation_id、basis_card_id 對應既有有效資料；reference_id 需在卡片引用範圍內解析。來源版本與敘述定位沿用 reference／既有版本系統，不強制另加 basis_card_revision、claim_locator 欄位。若尚無版本機制，保存足夠快照或在內容變更後標記待重審，不能靜默指向不同證據。

同一來源可以支持多條關係，一條關係可以有多個來源。多篇同源轉載不能被當成多份獨立佐證。context_only 不作支持票數，refutes 不能被無聲忽略。

卡片中的摘要、數字與欄位敘述也需有證據映射，但由卡片 reference 負責；relation_evidence 只處理卡片間關係，不要求把全部敘述都搬進 DB。

### 5.4 工程欄位與額外 tables：按需沿用

| 項目 | 處理原則 |
|---|---|
| workspace／ACL | 必須保留既有隔離，必要時使用複合鍵；不是可省略的安全要求 |
| schema_version、revision、hash、indexed_at | 依現有格式與同步機制選用，由系統處理 |
| deleted_at、歷史、review audit | 沿用現有刪除與審計機制 |
| card_domains、card_tags | 有既有 metadata 索引就沿用；只有查詢需要時再建 |
| schema registry／relation 字典 | 優先沿用版本化設定或 registry，不強制新增 SQL table |
| evidence 評估、人工覆核、規則設定 | 依第 6.1 節保存到既有 metadata／review／設定機制，不先擴增一套新 tables |

不能因本節表格較簡單而刪除 AEP 已有必要欄位；也不能為了「完整」把所有候選欄位全部新增。PR 說明每項新增的實際用途。

## 6. 關係如何產生：具體例子

假設卡片 CARD-SL-001 有 supplier=CARD-ORG-A、customer=CARD-ORG-B，schema 已宣告兩者為連結欄位。

| 起點 | 關係 | 終點 | 來源 |
|---|---|---|---|
| CARD-SL-001 | has_supplier | CARD-ORG-A | attributes.supplier |
| CARD-SL-001 | has_customer | CARD-ORG-B | attributes.customer |

關係字典將 supplier 映射 has_supplier；不是 LLM 任意創造名稱。系統依欄位建立索引，關係確認程度仍取決於證據及 review，不因成功解析而設成 confirmed。

若要查「誰供貨給 B」，先反查 has_customer → 找到 SupplyLink 卡 → 沿 has_supplier 找公司，再讀 SupplyLink 的產品、範圍、時間、證據。毋須再人工維護 A→supplies_to→B 的重複連線。若為效能生成該連線，必須標明衍生來源並可重建。

LLM 額外推論出的「某產品需要某測試」不屬 schema 欄位的機械映射。須使用註冊關係，保留依據、範圍與 inferred 狀態，待 review；不能把技術／節點共同出現就視為已確認關係。

### 6.1 證據評估、人工覆核與權重

#### A. 三種概念分開

| 層次 | 記錄什麼 | 調整方式 |
|---|---|---|
| 原始證據 | 來源、內容、日期、原文位置 | 保留原始版本；錯誤以修訂紀錄更正 |
| 個別採信判斷 | 直接確認／轉述、支持範圍、時間明確度、獨立性、矛盾與未知 | AI 建議，維護者按證據覆核 |
| 共用評估規則 | 綜合來源特徵、時效與佐證的方式 | 版本化設定，以 benchmark 校準 |

reference 保存可觀察的證據特徵；特定關係的支持程度保存於該 evidence-link 的評估 metadata 或既有 review 記錄。同一訪談可能直接支持「有需求」，卻不支持「已承諾採購」，不可只對整份來源給一個通用分數。

#### B. 維護者必須能調整什麼

透過現有卡片／關係 review 畫面，提供：

1. 查看目標敘述、原始 reference、定位、AI 判定及理由。
2. 更正支持／反駁／僅背景、證據直接性、適用範圍、日期與同源資訊。
3. 對個別敘述或關係作採信／待確認／不採信的覆核，附理由。
4. 保存 reviewer、時間、前後值與理由，支援追溯及重新評估。

初期使用有文字定義的等級即可，不強制設數字權重滑桿。例如「直接支持／間接支持／不足以支持」，須有定義與理由；資訊不足另標未知。採信程度不同於商機價值或資源 priority。

若既有系統已有數字評分，維護者可以提出或執行個案 override，但需保存 system_assessment、human_override、override_reason、reviewer、reviewed_at、policy_version（可用 metadata，不要求一項一個 SQL 欄位）。人工值不覆蓋系統原值；有權覆核且目標／版本仍有效時才優先使用。來源或目標範圍改變後標記需重審，保留歷史，不盲目沿用。

#### C. 共用權重怎麼改

先訂可解釋規則，不預設任意百分比、LLM 自評分數或全域門檻。證據日期不明只影響相關時間判斷，不把整張卡一律降權；BD 直接客戶確認也不能僅因來源為 BD 就降權。

個案覆核不自動修改全域規則。調整共用規則時記錄適用 domain／任務、版本、變更理由與驗證結果；影響的系統評估可重算，但人工覆核需檢查是否仍有效。不得用回答分數反向改寫原始證據。

#### D. Benchmark／刷題的角色

每個 domain 維護少量有代表性的問題，由領域負責人定義預期答案、必要證據路徑、不可推論的邊界與時間條件。先定位錯誤，再決定修改對象：

| 錯誤 | 優先修改 |
|---|---|
| 正確卡片未取回 | retrieval／metadata／索引 |
| 卡片找到了，但必要關係未延伸 | 關係資料或 traversal 策略 |
| 原文被錯誤萃取、數字口徑錯 | ingest／schema／卡片內容 |
| 轉載被當獨立證據、背景當支持 | 證據評估規則 |
| 讀到反駁仍答得過度肯定 | 推理與答案生成規則 |

刷題調整的是系統行為與共用規則，不是將個別證據「調成真實」。保留未參與調整的驗證題，題目不足時揭露此限制；比較證據覆蓋、錯誤確定性、關聯正確性與答案品質，不只看總答對率。資料修正與規則調整分開記錄，避免無法辨識改善原因。

#### E. 初期交付邊界

本次交付證據檢視、語義覆核、理由與歷史，以及可重現的代表題評估。若有既有評分規則，完成版本化與人工 override 支援；若沒有，不為此新建複雜數字權重引擎、自動調參或大量題庫。後續累積案例後再決定數值化。

## 7. 權威來源與同步

採單一欄位只有一個寫入責任來源：

| 資料 | 權威來源 | 另一端角色 |
|---|---|---|
| 五類卡片內容、專屬連結欄位 | 卡片文件，透過現有 card service 寫入 | SQLite 為可重建索引 |
| schema_field 連線 | 卡片連結欄位 | relations 自動生成，不直接手改 |
| 無對應卡片欄位的推論／人工關係 | SQLite 關係紀錄，含證據與 review | 卡片 UI 動態顯示；匯出時附關係清單 |
| schema、relation 定義 | 版本化 registry | 驗證／UI／ingest 共用 |

若 AEP 已採 DB 為卡片權威來源，保留既有模式並將 Markdown 定義為匯出視圖，達成同樣的單一來源原則；在 PR 清楚說明映射。不得同時允許檔案與 DB 無衝突控制地修改相同資料。

同步需能偵測變更、失敗重試與狀態檢查；沿用現有 revision、hash 或等效機制，不強制全部新增。檔案與 SQLite 不能假設共用原子交易：使用既有 outbox／job／reconcile 機制或可重試的同步流程，索引未完成時標示 stale，不能回報全部成功。重建 schema_field 關係不得刪除 manual／inferred 關係。

## 8. Ingest 與 Review 流程

1. 保存 raw source 與來源 ID。
2. AI Session／Skill 先執行第 8.1 節的 schema 適配判定，選擇既有卡型與適用擴充，載入指定版本 schema；不適配內容建立候選提案。
3. 萃取 key/value，生成摘要、用途、範圍及 references，標記時間依據與不確定性。
4. Entity resolution 與既有卡片比對：以 ID、對象、事件、產品／專案、時間與範圍判斷更新既有卡或建立新卡。名稱同名或別名有歧義時保留待處理，不自動接錯；同對象的矛盾證據保留，不直接覆蓋。
5. 驗證結構與引用，建立 draft。未知目標連結不寫無效外鍵，保留候選與待解析紀錄。
6. 同步 cards 與分類索引，從 link 欄位建立 schema_field relations。
7. 額外分析關係作為 inferred 候選，保存證據。
8. 專家分別 review 卡片內容與需要確認的關係；發布規則不得僅看欄位填滿。

純格式轉換不等於知識確認。LLM 不得自改正式 schema；不適配的資料輸出 schema 調整建議並保留原始內容。

### 8.1 Schema 適配與演進判定

本檢查是 ingest pipeline 的第一階段，需要初步閱讀文章，不是另一套獨立 ingest。判斷單位為文章中的知識項目；一篇文章可以同時沿用多種卡型、更新舊卡、新增卡片，並對少數內容提出 schema 建議。不得整篇只選一種處理方式。

#### A. 判斷順序

優先沿用，必要時擴充，最後才新增卡型。分清「卡片實例」與「卡片類別」。

| 順序 | 問題 | 處理結果 |
|---|---|---|
| 1 | 是同一對象／事件／關係、相同適用範圍的新資料或證據嗎？ | update_card：更新既有卡、追加證據、保留矛盾 |
| 2 | 是既有知識種類下的新對象或新事情嗎？ | create_card：沿用既有 schema 新增卡 |
| 3 | 差異只是分類、名稱、同義詞或列舉值嗎？ | dictionary_change：沿用既有值或提出字典調整，不新增卡型 |
| 4 | 知識種類不變，但缺少必要欄位嗎？ | extend_schema：提出既有 schema／領域擴充變更 |
| 5 | 現有卡型無法合理表達，且需要獨立管理嗎？ | propose_type：提出新卡型提案 |

這是優先檢查順序，不代表命中前兩項後就跳過 schema 驗證。更新舊卡也可能同時需要欄位擴充。新市場、新公司、新詞彙、缺少資料或大量空值，本身都不是新增卡型的理由。

#### B. 新增卡型的四項必要說明

| 必要項目 | 必須具體說明 |
|---|---|
| 知識單位與邊界 | 一張卡代表一個什麼？何時算同一張、何時拆卡？ |
| 既有卡型不適配的理由 | 比較最接近的既有 schema，指出語義扭曲或核心資訊只能塞自由文字的問題；說明為何擴充仍不合理 |
| 獨立管理的必要性 | 是否有自身身分、獨立關聯、更新、時程或審查需求；為何不能只作另一張卡的欄位 |
| 明確業務用途 | 支援哪個查詢、分析或決策，預期產出是什麼 |

四項皆須有具體回答，不以 LLM 的總分或 confidence threshold 取代判斷。資訊不足時輸出 needs_clarification，不自動認可新增。跨文章出現頻率與預期重用程度作為參考，不能當唯一門檻：多篇提及不必然需要新類別，單篇但有明確業務必要也可提案。

#### C. AI 判定紀錄與候選提案

每個知識項目至少記錄 source_id／原文位置、知識項目摘要、檢查過的 schema 及版本、建議 action、理由、目標 card_id（若有）、待確認問題。action 可複合，例如 update_card + extend_schema。

propose_type 額外產生以下提案內容：

- proposal_id、候選 type 名稱、定義、適用範圍與一張卡的單位。
- 支援的業務問題、原文例子及證據位置。
- 與既有卡型的逐項比較，為何無法沿用或擴充。
- 建議欄位：意義、型別、必填、列舉、缺值規則、證據要求。
- 關係定義：允許連到哪些卡型、方向與語義。
- 至少一張來源可追溯的候選卡，未知內容不得補造。
- 重複使用預期、對既有卡片／retrieval／migration 的影響。
- 提案人／生成時間、領域負責人、未解問題與審查結果。

extend_schema／dictionary_change 也要記錄變更前後、必要性、相容性及負責人；不能因為不是新卡型就繞過 registry 管理。

#### D. 人工確認與版本發布

沿用既有 approval／registry 機制；建議狀態為 proposed → under_review → approved／rejected／needs_clarification。領域負責人確認業務必要與邊界，schema 維護者確認重複性、結構與相容性；同一人可依現有權責兼任，不強制新增審批層級。

approved 代表設計獲准，正式使用前仍須完成 schema 驗證並發布版本。卡片記錄採用的 schema_version；不得直接改寫舊卡的版本標記而不遷移。

未核准／未發布前：

- 不將候選 type 註冊成正式卡型，也不讓其內容冒充正式可檢索知識。
- 原始資料與候選萃取結果保存於既有 staging／draft submission 機制；如需預覽搜尋，必須明確標示候選狀態並沿用權限。
- 同篇文章可用既有 schema 處理的內容照常進行，不阻塞整批。
- 核准並發布後，僅重處理受影響的知識項目；以 source／item／proposal 識別及既有卡 ID 保證冪等。
- 退回時保存原因，修訂或映射至既有卡型，不丟失原始資料。

#### E. 判定示例（示意，非正式市場事實）

| 新文章內容 | 判定 |
|---|---|
| 介紹新的機器人 C 公司 | 沿用 Account schema，新增卡 |
| 補充 A→B 同一模組、同一專案的送樣證據 | 更新對應 SupplyLink，追加 reference |
| 機器人產品新增負載資訊，但現有欄位無法表達 | 評估 CustomerProduct 的 Robotics 欄位擴充 |
| 出現新的供貨階段用語 | 先檢查同義詞映射；必要時提案擴充列舉 |
| 太空任務需獨立追蹤參與公司、產品與里程碑 | 通過四項必要說明後，提案 Mission 卡型 |
| 文章順帶出現任務名稱，尚無獨立管理用途 | 不因此新增 Mission，保留來源與待釐清事項 |

#### F. 實作範圍

接入既有 AI Session／Skill、schema registry 與 review UI；判定結果可先沿用 submission metadata／audit 紀錄保存。不為本節強制增加新的 SQLite tables，不為候選提案重寫 harness。提供使用者檢視理由、修正建議與確認結果的入口，不能只回傳一個不可解釋的分類分數。

## 9. Retrieval 行為

- 先依既有授權範圍搜尋全文／向量／metadata，再沿 SQLite 關係補充相關卡片。
- 支援雙向查詢、多跳、分支與循環；設定最大跳數／節點量，去重與防循環。
- 不以 folder 作唯一搜尋邊界；type/domain 可作篩選，但應符合問題，不能將整個任務永久鎖在單一卡型。
- 返回卡片內容、關係路徑、證據定位、狀態、適用時間；推論不可呈現為事實。
- 每個節點與證據讀取都套用原有 ACL，不能沿關係越權，也不能因回傳關係洩漏受限卡片。
- 查到「方案對應應用」不等於已滿足全部需求；需讀取適用條件與驗證證據。

## 10. 遷移與相容性

1. 備份現有卡片與 DB，先 dry-run 產生差異與無法映射清單。
2. 沿用既有穩定 ID；沒有 ID 的卡片補發 ID，保存舊路徑／名稱至新 ID 的映射。
3. 先轉換五類內容與 metadata，不憑空補摘要事實、日期、可靠度與審查結果。
4. 將 [[名稱]] 解析為 ID；歧義、失效連結輸出報告，不默默猜測。
5. 產生索引與關係，驗證後再切換讀取。
6. 分類 folder 攤平時使用 ID 檔名，更新路徑查詢、模板與 ingest；若仍支援 Obsidian，處理 wikilinks 相容性。可分階段，先解除 retrieval 對 folder 的依賴。
7. 保留 SAMPLE 標記，預設不把虛構範例當正式資料；既有不明來源卡保持待確認。
8. 提供回滾方式、schema migration 版本及可重建索引指令。重跑不得新增重複卡片／關係。

## 11. 驗收條件

- [ ] 同一張卡可完整呈現五類資訊，UI 不要求重複輸入 SQLite 已有的關係。
- [ ] Application／SupplyLink 等至少兩種卡型，加 Robotics／Aerospace 至少兩領域，驗證共用欄位與擴充規則。
- [ ] 不適用、未知、待確認、確認沒有可區分；數字與日期欄位不混入狀態字串。
- [ ] 同一公司跨領域共用 ID；同名不同公司不誤合併。
- [ ] schema link 欄位可正確產生、更新與移除衍生關係；證據、review 與版本變更正確處理。
- [ ] 同步重跑冪等；模擬檔案更新後 DB 失敗，可偵測並恢復；不誤刪人工／推論關係。
- [ ] 關係反查、多跳、循環、無效目標、跨 workspace／ACL、刪除或移檔都有必要驗證。
- [ ] reference 指到正確來源與版本，支持與反駁資料可同時保留。
- [ ] 日期預設不冒充事件日期；修改文字不更新最後確認時間。
- [ ] 移動 folder 不影響以 ID 為基礎的關係與檢索。
- [ ] 遷移 dry-run、備份、回滾與原有相關測試通過，記錄未涵蓋限制。

- [ ] schema 適配涵蓋更新舊卡、新增實例、字典變更、欄位擴充、新卡型提案及資訊不足；能說明選擇理由。
- [ ] 同一篇文章可同時命中多種處理方式，不強迫單一卡型或阻塞所有內容。
- [ ] 未核准新 type 不進正式 registry；列舉／欄位變更也經版本流程。
- [ ] 模擬候選提案核准、退回與補件；發布後只重處理受影響內容，重跑無重複卡片／關係。
- [ ] 不因新 domain、新名詞、文章數量或欄位空白而直接新增卡型；Mission 正反例均有驗證。

- [ ] DB 變更以兩張核心表與證據對照責任為主；逐項說明必要新增，工程欄位沿用既有機制。
- [ ] 維護者可檢視來源並修正支持關係、直接性、時間、範圍與同源資訊，留下理由與歷史。
- [ ] 卡片內容證據與關係證據均可追溯；context_only 不算支持，同源轉載不當獨立佐證。
- [ ] 個案人工覆核不改全域規則；若有數字 override，保留系統值、人工值、理由、版本與來源變更後重審行為。
- [ ] benchmark 可分辨檢索、關係、萃取、採信與生成錯誤，不為提高答對率而改寫原始證據。
- [ ] 沒有既有評分引擎時，完成語義等級覆核即可，不因驗收而擴建數字權重系統。

## 12. Claude Code 最終交付

1. 現況盤點與設計映射，說明哪些既有機制直接沿用。
2. 五類卡片格式、卡型 schema 與領域擴充規則文件。
3. SQLite migration、索引、同步與重建流程。
4. ingest／review／retrieval／卡片 UI 的必要修改，包含 schema 適配、候選提案與發布後重處理流程。
5. 非真實商業情報的示意資料、必要整合測試與實際驗證結果。
6. 證據覆核 UI／紀錄、評估規則版本（若有），以及 domain 代表題驗證與錯誤分類報告。
7. PR 描述：問題、修改後行為、相容性、驗證及風險；未完成事項明列。

範圍限制：本提案不要求重設全部 21 種卡型、不重寫 harness、不加入新圖資料庫或新向量資料庫、不建立完整市場策略評分系統。先把卡片內容、連結、證據與索引責任建立清楚。

## 13. 實作順序

1. 盤點並映射現有機制，確認單一權威來源。
2. 完成五類卡片與 schema 適配流程。
3. 完成簡化卡片目錄、關係與證據對照，接入 retrieval。
4. 完成維護者證據覆核及必要遷移。
5. 用 domain 代表題檢查完整流程；確定錯誤原因後再調規則。

本版取代 v1.1 的完整欄位清單要求；保留五類框架與 schema 演進規則，將工程擴充改成按現況選用。
