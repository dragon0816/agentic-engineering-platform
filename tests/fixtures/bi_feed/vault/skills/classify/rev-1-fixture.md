---
name: classify
revision: 1
schema: bi.schema/v1.1@2.0.0
role: classify
applies_to: []
generated: true
---

這個知識庫用 schema bi.schema/v1.1@2.0.0。判讀來源時，先決定每段內容屬於哪一種卡片，
只用下面的類型；看不出是哪一種的內容不要做成卡片。

卡片類型：
- Opportunity：商機（領域 one）
- TestSolution：測試方案（領域 multi）
- Application：應用（領域 one）
- Competitor：競品（領域 multi）
- CustomerProduct：客戶產品（領域 one）
- Ecosystem：生態系（領域 multi）
- Account：客戶（領域 multi）
- Node：價值鏈節點（領域 multi）
- Technology：技術（領域 multi）
- Concept：概念（領域 multi）
- Trend：趨勢（領域 one）
- Signal：訊號（領域 one）
- WinLoss：輸贏分析（領域 one）
- RoadmapRequest：產品需求（領域 one）
- Pitch：簡報（領域 multi）
- DemoScript：展示腳本（領域 multi）
- Battlecard：對戰卡（領域 multi）
- Contact：聯絡人（領域 multi）
- VisitLog：拜訪紀錄（領域 one）
- SupplyLink：供貨關係（領域 multi）
- RevenueFact：收入事實（領域 multi）

市場區隔（來源放在 sources/applications/<資料夾>）：
- cell-phone：Cell Phone
- ap-cpe：AP/CPE
- module-iot：Module/IoT
- aidc-computing：AIDC Computing
- aidc-power：AIDC Power
- car-ebus-electronics：Car/eBus electronics
- robotics-amr：Robotics/AMR
- space-satellite：Space Satellite
- uav：UAV
- radar-ew：Radar/EW
- osat：OSAT

產品、競爭者與技術的通用資料放在 sources/library/，不屬於任何一個區隔。
