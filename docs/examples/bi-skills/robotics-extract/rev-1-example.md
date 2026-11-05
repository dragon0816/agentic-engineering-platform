---
name: robotics-extract
revision: 1
schema: bi.schema/v1.1@5.0.0
role: extract
applies_to: ["applications/robotics/sources"]
card_types: ["CustomerProduct", "TestSolution", "Competitor", "Application", "Node", "Trend", "Account", "Ecosystem", "Technology", "Signal"]
# 同事通常會改：哪種機器人類別算進來（AMR、協作手臂、人形）、自己常遇到的測試項目、誰算競品。
---

# 機器人來源的判讀規則

## 要抓什麼
- 機器人整機和關鍵模組（關節、伺服驅動、電池、控制器、視覺）是 CustomerProduct，account 填做這個產品的公司。
- 測試方案是 TestSolution：vendor 填原文寫的方案提供者；是不是競品，要來源明寫才算，並記在 body。
- 有具體量測項目的使用情境是 Application，measurement_topics 照原文列。

## 什麼算證據
- 來源明寫的量測項目、測試階段、認證名稱才算。安規、EMC、功能安全要哪些項目，不能從一般規定推。
- 「預計」「規劃」「有望」只能算規劃，不是已量產或已導入。

## 什麼要留空
- test_stage_now 只在來源寫明目前階段時才填（RD、cert、production）。
- market_impact、measurement_impact、our_fit 這類評分是人的判斷，來源沒寫就留空，不要自己打分。
- 空白標題底下沒有內容就是沒有資料，不要替它寫內容。

## 常見陷阱
- 標著「範例資料」「待驗證」的內容：只把這個標記和內容一起留在 body，不要當成已證實；confidence 不要提高。
- 表格或查詢語法（例如 dataview 區塊）是頁面的版面，不是資料，不要從裡面抓值。
- 模組廠和整機廠常常都叫「機器人公司」，要照原文分清楚誰做哪一層。
- 工業通訊（EtherCAT、TSN）、無線（5G、Wi-Fi、UWB）和電源是不同的測試領域，不要混成一張方案卡。
- confidence 不要寫 verified；evidence_grade 已有的值不要改，那是人的判斷。
