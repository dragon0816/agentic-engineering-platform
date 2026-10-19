# 真實資料匯入範例(來自專案「BDM BI KB」的供應鏈/廠商比較文件)

節錄檔(已去連結、精簡)與對應 mapping。執行目錄:`tools/samples/real`。

```bash
R="python3 ../../bi_ingest.py --vault ../../../BI --name-aliases name_aliases.json --quiet"   # 先加 --dry-run 預覽
$R supply_chain_extract.md --type ecosystem --mapping mapping_ecosystem_suppliers.json --table "has:全球代表廠|台系代表廠"
$R module_chain_extract.md --type ecosystem --mapping mapping_ecosystem_modules.json   --table "has:代表廠商"
$R supply_chain_extract.md --type ecosystem --mapping mapping_ecosystem_certlabs.json  --table "has:認證類別"
$R supply_chain_extract.md --type competitor --mapping mapping_competitor_instruments.json --table "has:儀器類別"
$R supply_chain_extract.md --type account --mapping mapping_account_midstream.json --table "has:公司"
$R vendor_comparison_extract.md --type account --mapping mapping_account_strengths.json
```

## 角色劃分原則
- 廠商比較表中的 啟碁/中磊/明泰… 是**客戶(Account)**,不是競爭對手。
- Competitor = 量測儀器廠(Keysight、R&S、Anritsu、LitePoint、EMC-ESD、倚強科技);卡片只有骨架,強弱項/定價/Battlecard 需由你補。
- Ecosystem = 晶片/RF/天線/光/模組/封測/認證單位;已被當成 Account 或 Competitor 的名稱用 `exclude_names` 排除。
- 結果可重複執行(冪等)。尚未建立的連結目標(NXP、NewPhotonics)為提示,可手動補卡。

## mapping 新增語法
`skip_rows` 略過列、`text_replace` 文字替換(可寫入另一欄)、`explode` 把一格內多家廠商拆成多列(括號內容 → `__note`,四碼數字 → `__ticker`)、`derive` 依關鍵字推導欄位、`compose` 組合內文、`exclude_names`、`name_aliases`。
