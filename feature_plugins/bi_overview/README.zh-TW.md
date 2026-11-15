# BI 資料集概覽 Plugin（0.1.0）

這是唯讀概覽 Plugin，需使用支援 Plugin API1.1 的 AEP。它顯示本機 BI 資料集的
卡片數、schema、更新時間與可讀狀態；完整的匯入、編輯、dashboard 與 BI 問答
仍使用既有 Knowledge → BI 卡片入口。本次不更新常駐 AEP，也不自動安裝套件。

## 安裝與使用

1. 在支援 API1.1 的 Agent Web 開啟側欄 Plugins。
2. 選擇 examples/plugins/bi-overview.aep-plugin.json，再按 Install。
3. 開啟新增的「BI 資料集概覽」頁面，查看涵蓋範圍、資料來源與狀態。
4. 已安裝但沒有 BI 資料夾時，頁面會顯示 missing；不會建立資料或把未知數量
   當成已確認零筆。資料庫忙碌、過期或無法讀取時，該列數量顯示「—」。
5. Disable 隱藏頁面；Enable 重新啟用。Uninstall 保留原有 BI 資料。

安裝不需要額外 AEP／IT 核准。此套件沒有 Skill、Workflow 或 Agent 工具，
不改模型工具清單、資料分類或 Knowledge 的來源引用規則。它也沒有維護表單、
檔案上傳或 SQL 輸入。舊版 API1.0 的封閉契約無法解析新欄位，請先使用支援
API1.1 的 AEP；不是把這份 JSON 安裝到舊版就能升級核心。

## 數量代表什麼

- 本機一般資料集：目前本機資料庫的卡片數。
- Vault：本機工作投影，**不是已發佈問答來源**，也不保證已套用所有 repository
  變更。不要拿工作投影的數量推論已發佈版本內容。
- 訂閱資料集：本機訂閱記錄選定的副本與版本，不向平台抓取或更新內容。

每列列出來源類型。只要有無法讀取、截斷或無效註冊，完整合計顯示「—」，
另列出的可讀卡片數是部分本機副本數。即使涵蓋範圍為「完整」，也是對本機
資料集副本的加總，不是跨資料集去重或已發佈的權威業務總數。

## 開發與封裝

python scripts/build_bi_overview_plugin.py
python scripts/build_bi_overview_plugin.py --check

Builder 只讀 manifest 與列明的三個 worker 檔案，統一換行後產生相同套件內容。
原始碼隨 sdist 提供，不作為核心 wheel 內的 BI 模組或預設自動安裝項目。
Worker 使用 stdlib 與內附 reader；不呼叫 BI 服務、不重建、同步或遷移資料。
它由 Host 透過宣告的 AEP_PLUGIN_READ_BI 接收資料位置，不推算其他資料夾。
這是介面契約，不是作業系統 sandbox；一般環境仍依原有規則傳給 worker。

一次最多顯示200列。資料過長而超出回應上限時會截斷並標記不完整。讀取預算
在資料集之間檢查並限制鎖定等待，不會硬性中斷所有檔案系統或 SQL 查詢。
零長度 journal 採保守作法，仍顯示忙碌。重新導向／junction 的 workspace/bi
不在目前明確資料位置契約的支援範圍，會回報 plugin_path_invalid。

正式驗收以 docs/phases/ 下的 BI overview 驗收文件為準。這不是完整 BI／Wiki
抽離，也不代表任何真實模型回答品質已經獲得保證。測試只使用暫存合成資料。
