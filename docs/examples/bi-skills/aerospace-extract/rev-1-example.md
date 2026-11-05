---
name: aerospace-extract
revision: 1
schema: bi.schema/v1.1@5.0.0
role: extract
applies_to: ["applications/aerospace/sources"]
card_types: ["SupplyLink", "CustomerProduct", "Ecosystem", "Technology", "Trend", "Application", "Signal", "Node"]
# 同事通常會改：segment 的切法（衛星本體、地面站、使用者終端）、哪些政府來源算官方、要不要收 Signal。
---

# 航太與衛星來源的判讀規則

## 要抓什麼
- 明寫的供應商與客戶，各做一張 SupplyLink；product 照原文，交付品沒寫清楚就照原文說「未明」。
- 終端、衛星、酬載是 CustomerProduct；segment 分清使用者終端（ut）和星載（space），來源沒講就留空。
- 製造地轉移、法規開放是 Trend；要把影響的節點和公司照原文列出。

## 什麼算證據
- 公司自己確認或具名媒體採訪，才算供貨證據。保密、不評論、匿名消息要連同這句話寫進 body，不能算已確認。
- 公司列為某星系的供應商，不代表每一項產品或每一代衛星都是；不明的部分寫進 not_confirmed。

## 什麼要留空
- 上市日、料號、頻段、軌道、各代衛星配置：來源沒寫就留空。來源明說未揭露，也還是留空，並把原句放進 body。
- 客戶占比和當期金額：沒寫就留空，不要從總營收推。

## 常見陷阱
- 歷史案例不是現況：來源寫「過去」「歷史」「曾經」，要把時間點留在 body，supply_stage 不要填成現在的量產。
- 新產能不能全算給同一個客戶：來源說不可全歸給某客戶時，要保留這句話，不要寫成那家的專屬產能。
- 同時用在衛星和地面的元件，要確認是哪一邊；看不出來就寫進 not_confirmed。
- 計畫、合約和實際發射不同：宣布不等於部署。
- confidence 不要寫 verified；evidence_grade 已有的值不要改，那是人的判斷。
