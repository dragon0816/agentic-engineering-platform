# 簡報蒸餾提示(給 Claude 用,貼上擷取檔後使用)

我方是 **Rohde & Schwarz(R&S)**;Keysight、Anritsu 是 Competitor。以下是研討會簡報的擷取檔(含頁碼)。
請依下列規則整理成卡片草稿,輸出為 JSON(每種卡一個陣列),不要貼原文,用自己的話寫:

1. **Signal(整場 1 張)**:title、date、source_type=conference、source(檔名/主辦)、summary(3 到 5 句)、
   so_what(對 R&S 的意涵)、related(連到庫內既有 Technology / Trend / Competitor / Account)、reliability。
2. **TestSolution(每個被介紹的方案 1 張)**:
   - 先判斷屬於誰:`vendor` 填該廠商的 Competitor 卡名(Keysight、Anritsu…);我方 R&S 方案 vendor 留空;
     客戶或第三方的現行測法不要建方案卡,寫進 Signal 或 Application 痛點。
   - 欄位:name、applications、technologies、nodes、test_type、tier、automation、dut、test_items、standards、
     instruments、reference_customers。簡報沒提的欄位留空,不要推測。
   - 內文「方案概要」寫簡報宣稱的重點並標頁碼(如「p12」);規格數字標註「簡報宣稱」。
   - 若與我方方案可比,在我方卡的 competing_solutions 列出此卡(只列建議,不要自行改我方卡)。
3. **Competitor / Account / Ecosystem 補充**:只寫新資訊(產品線、時程、客戶進度),每條附頁碼與「宣稱/推論」。
4. **Technology / Trend 補充**:新增的量測需求或時程變化,連回此 Signal。
5. **Concept 候選**:簡報出現、庫內尚無解釋的名詞(列名稱與一句話白話草稿)。
6. 全部標 confidence: assumed。不確定處標「待查證」。最後列出「不確定、需要人工確認的項目」。
