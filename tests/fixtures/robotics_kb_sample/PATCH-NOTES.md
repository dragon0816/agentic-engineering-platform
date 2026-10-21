# Robotics KB patch(schema v4)

把機器人與智慧自動化(robotics)加入既有的 wireless、AIDC BI KB,三個領域共用同一套 schema。

## 內容

| 檔案 | 說明 |
|---|---|
| `tools/bi_schema.py` | 取代舊版。`DOMAINS` 加入 robotics、新增 Opportunity 卡、多項欄位調整(見下) |
| `tools/bi_ingest.py` | 取代舊版。新增 `--fill-only`、領域驗證、領域衝突防護、`node` 自動併入 `nodes` |
| `tools/samples/robotics/nodes_robotics.csv` | 12 個機器人 Node(L1 晶片已放入 `L1-Robot-Chipset`) |
| `tools/samples/robotics/competitors_robotics.csv` | Keysight、Anritsu、LitePoint |
| `tools/samples/robotics/accounts_core_robotics.csv` | 附件「核心代表廠商」12 家的 Account 精簡卡 |
| `BI/_Templates/` | 由新 schema 重新產生的 Templater 模板(含 `T-Opportunity.md`) |
| `Dashboard-Robotics.md` | 機器人版 Dashboard,放 vault 根目錄 |

## 套用步驟(在 `tools` 資料夾執行)

```powershell
# 0. 備份舊的 bi_schema.py、bi_ingest.py,再用本包的兩個檔案取代

# 1. 重新產生模板(會覆蓋 BI/_Templates 內的 T-*.md)
py bi_ingest.py --emit-templates ../BI/_Templates

# 2. 先預覽再匯入:Node → 競品 → Account
py bi_ingest.py samples/robotics/nodes_robotics.csv --type node --vault ../BI --dry-run
py bi_ingest.py samples/robotics/nodes_robotics.csv --type node --vault ../BI
py bi_ingest.py samples/robotics/competitors_robotics.csv --type competitor --vault ../BI --fill-only
py bi_ingest.py samples/robotics/accounts_core_robotics.csv --type account --vault ../BI

# 3. 把 Dashboard-Robotics.md 放到 vault 根目錄
```

## schema 變更重點

- **共用卡改多領域**:Technology、TestSolution、Concept 的 `domain` 由單值改為清單,例如 `[wireless, robotics]`。
- **新欄位**:CustomerProduct 加 `nodes`、`ecosystem`、`launch_date`;Account、Ecosystem、Competitor 加 `nodes`(`node` 仍是主要節點)。
- **新卡 Opportunity**:Application → 我方 TestSolution(`vendor` 空白)→ Opportunity,階段欄位為 `deal_stage`。
- **列舉值**:`test_type` 加 `EMC`;Ecosystem `role` 加 `institute`(法人)、`ipc`(工業電腦廠)。
- **掛勾視圖**:Node、Ecosystem、Trend、CustomerProduct、Application、TestSolution 內文加入 Dataview 區塊,顯示彼此的關聯(趨勢由技術或節點交集推得,不另存)。

## ingest 行為變更

- `--fill-only`:只填空欄位,不覆蓋既有單值,清單取聯集。把 robotics 加到既有卡時使用。
- 領域驗證:`domain` 清單只接受 wireless、AIDC、robotics(大小寫不拘),打錯的值會被丟棄並警告。既有卡裡的未知值保留,不會因合併而遺失。
- 領域衝突防護:單一領域的卡(Node、Application、Trend、CustomerProduct、Signal、Opportunity)若同名卡屬於別的領域,該列會被略過並警告,不會覆蓋。沒有 `domain` 的舊卡視為 wireless。
- 隱含領域:多領域卡若沒有 `domain`,補上 robotics 時會先寫成 `[wireless, robotics]`,不會從無線視圖消失。
- `node` 會自動併入 `nodes`。已存在的卡第一次重新匯入時會因此顯示 `~ updated`。
- 領域要寫在 CSV 的「領域」欄,或用 `--default domain=robotics`。`defaults` 只對新建立的卡生效,既有卡不會被補。

## 實測範圍

在測試 vault 上跑過:匯入、重跑冪等、`--fill-only`、領域衝突、領域驗證、舊卡隱含 wireless、Opportunity、模板輸出。Dashboard 的 8 個 `dataviewjs` 區塊以模擬的 `dv` 執行過(robotics 與 wireless 兩種領域);所有 DQL 區塊沒有在 Obsidian 實際執行過,請先在小資料上確認。
`bi_slides_extract.py`、`bi_concept_candidates.py` 與 `prompts/` 未納入檢查。

## 需要你確認

1. 現有 wireless、AIDC Dashboard 若用 `domain = "AIDC"` 這類等號比對,被本工具重寫成清單的卡會比對失敗,請改用 `contains(domain, "AIDC")`。
2. `T-Opportunity` 與 Opportunity 匯入的預設領域是 wireless,機器人商機請在 CSV 填「領域」或加 `--default domain=robotics`。
3. 12 家 Account 的主要節點與涉及節點是依附件說明做的假設;股票代號取自附件的表格,未回查,東佑達的代號留白。
4. `X-Certification-Lab` 沿用現有節點,Dashboard §4 會把 X 層節點顯示在所有領域。
5. 同一家公司請只建一種卡(Account 或 Ecosystem),兩個資料夾同名會讓 Obsidian 連結混淆。客戶產品的 `ecosystem` 欄位可以連到 Account 卡。
6. Node 的「典型量測需求」是 T&M 切入點初稿,尚未經業務或 FAE 驗證。
