# BI Overview：拆分前準備

目前只有唯讀 metadata reader 與合成資料測試，**尚不是可安裝的 Plugin**。
還沒有 worker 通訊入口、正式 manifest、封裝或頁面安裝驗收；既有 BI 功能
與常駐 AEP 沒有改變。H1／H4 核心介面仍需按 AGENTS.md 第 22 條另行核准。

程式位於 `worker/aep_plugin_bi_overview/reader.py`。呼叫者明確提供 `bi/`
資料夾；reader 不推算 Host workspace、不呼叫現有 BI 服務，也不建立、重建、
同步或遷移資料。SQLite 僅以 read-only URI 在單一讀取交易中取得每個資料集的
metadata。缺少、過期、損壞、忙碌或不支援的資料會列出狀態，不當成零筆。

一般資料集顯示目前本機資料庫；vault 顯示本機工作投影，**不是問答使用的已
發佈版本**，也不保證已套用所有 repository 變更。訂閱資料只讀本機訂閱記錄
所選的版本，不更新平台內容。不追蹤 vault 記錄中的外部資料夾路徑。

原有 BI 問答、來源引用、已發佈版本選擇與 Knowledge asking 都保留。這些
metadata 不取代卡片、原始文件或證據，不可把本機投影數量當成已發佈答案。

測試只建立暫存合成資料。完整下一階段範圍與相容性要求請參閱
`docs/phases/FEATURE_PLUGIN_BI_OVERVIEW_PLAN_20261114.md`。

讀取預算會在資料集之間檢查，並限制 SQLite 鎖定等待；它不是中斷檔案系統或
SQL 查詢的硬性時限。零長度 journal 仍採保守作法，顯示忙碌而不讀取。
