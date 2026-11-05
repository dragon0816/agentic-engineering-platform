---
name: mobile-extract
revision: 1
schema: bi.schema/v1.1@5.0.0
role: extract
applies_to: ["applications/mobile/sources"]
card_types: ["CustomerProduct", "Account", "Ecosystem", "Technology", "Signal", "SupplyLink", "Competitor"]
# 尚未驗證：目前沒有 mobile 的來源資料夾，也沒有資料，這份規則沒有用真實來源試過。
# 同事通常會改：是否收平板與穿戴、哪些拆解或認證來源算可信、Signal 的門檻。
---

# 手機來源的判讀規則（範例，尚未用真實資料試過）

## 要抓什麼
- 具體機種是 CustomerProduct，account 填品牌；chipset_modules 只填來源明寫的晶片或模組。
- 品牌、晶片廠、模組廠、代工廠、電信商分開成 Account 或 Ecosystem，不要混成一張。

## 什麼算證據
- 官方規格頁、認證資料庫、實機拆解可以算事實；傳聞、外洩、分析師預估只能做 Signal，reliability 不高於 medium，並寫明出處。
- 零件出現在拆解報告，只代表那一台機種用了它，不代表整個系列都用。

## 什麼要留空
- launch_date 只填官方發表或開賣日期；傳聞的時間放 body，launch_window 也要原文有寫。
- 出貨量、市占沒有具名出處就留空。

## 常見陷阱
- 同一機種不同地區版本的頻段和晶片可能不同，來源沒講是哪一版就不要當成全部版本。
- 機種名字相近（標準版、Pro、Ultra）是不同的 CustomerProduct，不要合併。
- 認證通過不等於已上市，發表也不等於已開賣。
- confidence 不要寫 verified；evidence_grade 已有的值不要改，那是人的判斷。
