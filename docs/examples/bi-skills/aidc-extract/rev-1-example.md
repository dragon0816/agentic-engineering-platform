---
name: aidc-extract
revision: 1
schema: bi.schema/v1.1@5.0.0
role: extract
applies_to: ["applications/aidc/sources"]
card_types: ["SupplyLink", "RevenueFact", "Ecosystem", "Account", "CustomerProduct", "Application", "Technology", "Trend", "Signal", "Node"]
# 同事通常會改：card_types（要不要收 Signal）、哪些階段用語對應哪個 supply_stage、自己常讀的報告格式。
---

# AIDC 來源的判讀規則

## 要抓什麼
- 每一組明確寫出的供應商與客戶，都要有自己的 SupplyLink 卡，不要只列最大的一組，也不要只寫進 body。
- 市佔或排名表裡每一家明確列名的公司，都要有自己的卡（Ecosystem 或 Account），不要只抓前幾名；同一家公司已有卡就更新，不要另建同名卡。
- 公司的營收或占比做成 RevenueFact：period 和 unit 照原文，basis 分清 reported、media、estimated、target。

## 什麼算證據
- 供貨關係要來源明寫誰供給誰。兩家公司出現在同一段、同一張表或同一條產業鏈，都不算供貨，不建 SupplyLink。
- 併購、合作開發、公開展示都不等於供貨。

## 什麼要留空
- supply_stage 只在來源寫明階段時才填：展示 demo、送樣 sample、認證 cert、試產 pilot、量產 mass。「導入」「布局」「切入」這類字眼看不出階段，留空，把原文放進 not_confirmed 或 body。
- 來源沒講清楚的料號、金額、占比、客戶，寫進 not_confirmed，不要猜。

## 常見陷阱
- 市場分母：滲透率和市佔要連分母一起保留（AI 晶片、全部資料中心、全球或台灣），分母不同的數字不能放同一張卡比較。
- 預測和實績要分開：全年未結束的數字是預測，basis 不是 reported。
- 報告作者自己的判斷（「本文認為」「策略判斷」）不是事實，basis 用 inference。
- `[web:12]`、`[P§4.2]` 這類標記只是文內索引，不是來源名稱，不要填進 source。
- 名字相近的公司不一定是同一家，來源說是不同公司就分開。
- confidence 不要寫 verified；evidence_grade 已有的值不要改，那是人的判斷。
