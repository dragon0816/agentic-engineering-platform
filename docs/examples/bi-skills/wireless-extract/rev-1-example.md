---
name: wireless-extract
revision: 1
schema: bi.schema/v1.1@5.0.0
role: extract
applies_to: ["applications/wireless/sources"]
card_types: ["Ecosystem", "Account", "CustomerProduct", "Technology", "Concept", "TestSolution", "Competitor", "Signal", "SupplyLink"]
# 同事通常會改：card_types（做競品的人會加 Battlecard）、自己關心的頻段與標準、哪些規格一定要記。
---

# 無線來源的判讀規則

## 要抓什麼
- 晶片、模組、整機、電信商、認證實驗室各有自己的 Ecosystem 卡，role 照原文明寫的角色填。
- 新標準、新世代、新頻段是 Technology；客戶的具體機種是 CustomerProduct，不要混在一起。
- 解釋名詞的文字（「30 秒版」「常見誤解」）是 Concept，one_liner 和 analogy 照原文，不要自己改寫。

## 什麼算證據
- 一句話描述某家公司，才算那家公司的事實。整段列出多家公司時，每句話只算在它明寫的公司身上。
- 機種用了哪顆晶片、誰供應誰，要來源明寫；同屬一個平台或同一條產業鏈不算。

## 什麼要留空
- 來源沒寫的規格（頻段、功率、速率、認證狀態）留空，不要用標準的一般規定補。
- launch_date 只填來源寫的日期；「2026 下半年」放 launch_window。
- 多家合計的市占不是任何一家的數字，不要拆給個別公司，也不要填進單一公司的數字欄位。

## 常見陷阱
- 頁面裡的分類標題（例如「某類 SoC」）是整理者的分類，不代表這家公司賣這項產品；內文有明寫才算。
- 標準世代不要合併：Wi-Fi 6E 和 Wi-Fi 7、5G FR1 和 FR2、3GPP 不同 Release 是不同的東西。
- 「客戶會怎麼說」這類話術範例不是真實客戶的回饋，不要做成 Signal。
- 「主導」「領先」「最大」是原文的評語，要保留原句，不是可比較的數字。
- confidence 不要寫 verified；evidence_grade 已有的值不要改，那是人的判斷。
