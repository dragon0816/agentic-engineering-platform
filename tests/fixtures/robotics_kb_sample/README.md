# Robotics KB 完整範例(schema v4)

台灣機器人與智慧自動化的 BI 知識庫範例,**含全部 12 種卡片(共 104 張)**,可直接用 Obsidian 開啟 `BI/` 資料夾瀏覽。三個領域(wireless、AIDC、robotics)共用同一套 schema。

> 所有內容是**範例資料**,每張卡 `confidence: assumed`,內文標有「[範例資料,待業務/FAE 驗證]」。廠商、型號、股票代號、客戶產品與商機都不是已驗證的事實,請用實際情報取代。

## 內容

| 資料夾 / 檔案 | 說明 |
|---|---|
| `BI/` | 完整範例 vault:104 張卡 + 12 個 Templater 模板 |
| `Dashboard-Robotics.md` | 機器人版 Dashboard,放在 vault 根目錄(與 `BI/` 同層) |
| `tools/` | `bi_schema.py`、`bi_ingest.py` 與 `samples/robotics/` 內的 12 個來源 CSV |
| `build_sample.py` | 依來源 CSV 從頭重建 `BI/`(`py build_sample.py [輸出資料夾]`) |
| `PATCH-NOTES.md` | schema v4 與 ingest 的變更說明、套用步驟、需確認事項 |

## 卡片數量

| 卡種 | 張數 | 內容 |
|---|---|---|
| Node | 13 | 機器人 L1–L5 共 12 個(晶片在 `L1-Robot-Chipset`)+ 沿用 Wireless KB 的 `X-Certification-Lab` |
| Account | 12 | 附件的核心代表廠商 |
| Ecosystem | 8 | NVIDIA、聯發科、Qualcomm、工研院、TÜV Rheinland、SGS Taiwan、凌華科技、鴻海 |
| Competitor | 5 | Keysight、Anritsu、LitePoint、致茂電子、NI |
| Technology | 10 | EtherCAT、TSN、5G-Private-Network、Wi-Fi-7、UWB、mmWave-Radar、Functional-Safety、Edge-AI-SoC、BMS-Fast-Charging、Servo-Drive-SiC-GaN |
| Trend | 7 | 人形機器人、Cobot AI 化、AMR 滲透、TSN 化、無線化、安全法規、快充 |
| Application | 10 | 伺服 EMC、TSN 一致性、無線共存、雷達/UWB、關節動態、電池 BMS、整機認證、EOL、現場覆蓋、SoC 電源完整性 |
| TestSolution | 14 | 我方 R&S 7 個(`vendor` 空白)+ 對手 7 個 |
| CustomerProduct | 8 | 各 Account 的代表產品,連到 Node、Technology、Ecosystem |
| Opportunity | 7 | lead、qualified、proposal、eval、won、lost 各階段 |
| Signal | 4 | 情報示範 |
| Concept | 6 | 白話名詞卡(名稱避開與 Technology 同名) |

## 鏈路怎麼走

Trend → Technology → Node → Ecosystem → CustomerProduct → Application → 我方 TestSolution → Opportunity。
例如:`達明機器人` → 產品 `達明 新世代 AI 協作手臂` → 應用 `機器人控制器 EtherCAT-TSN 一致性` → 方案 `R&S 工業乙太網路時序與訊號完整性方案` → 商機 `達明 新世代 Cobot 無線與 TSN 驗證`。

## 故意留的缺口(用來示範 Dashboard)

- `AMR 電池包 BMS 與充電驗證`、`機器人產線下線測試`:對手有方案、我方沒有(Dashboard §6 標紅)。
- `AMR 電池包 BMS 與充電驗證`:有客戶產品需求但沒有商機(§19)。
- `快充與高稼動電池` 趨勢:沒有對應方案(§10)。
- `大銀 直驅馬達伺服模組`:刻意不填生態系成員(§16 完整性檢查)。
- `R&S 5G 私有網路機器人連線驗證方案`:沒有進行中商機(§18)。
- 部分 Technology 缺 Concept 解釋(§14)。

## 使用方式

1. 安裝 Obsidian 外掛 **Dataview**(並開啟 JavaScript Queries)與 **Templater**。
2. 把 `BI/` 與 `Dashboard-Robotics.md` 放進同一個 vault 根目錄,開啟 Dashboard。
3. 要改資料:編輯 `tools/samples/robotics/*.csv`,執行 `py build_sample.py`(輸出到新資料夾比較安全,例如 `py build_sample.py ./BI_new`)。重跑不會產生變更(冪等)。
4. 要併入既有的 wireless / AIDC vault,不要直接覆蓋:先看 `PATCH-NOTES.md`,並用 `--fill-only` 匯入共用卡。

## 已驗證與未驗證

- 已驗證:重建、重跑冪等、全部 wikilink 無死連結(104 張)、Dashboard 的 8 個 `dataviewjs` 區塊以模擬 `dv` 執行。
- 未驗證:所有 DQL 區塊沒有在 Obsidian 實際執行過;卡片內文的 Dataview 區塊(節點/生態系/趨勢掛勾)同樣未在 Obsidian 實測。
