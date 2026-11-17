# Feature Plugin 第一階段使用說明

本文件描述開發版的通用 Plugin 機制。LLM Wiki／BI Knowledge 尚未拆成 Plugin。
必須先啟動包含本分支實作的 AEP；既有常駐 AEP 尚未更新，舊版不會憑空出現
Plugins 入口。本次不要求改寫目前的 Knowledge 資料或重新建立資料庫。

## 一般使用者操作

1. 開啟支援 Feature Plugin API v1 的 AEP Agent Web，點側欄 **Plugins**。
2. 選擇 `examples/plugins/hello.aep-plugin.json`，點 **Install**。
   第一版 `.aep-plugin` 是 JSON 封裝，不是任意 ZIP；可以使用 `.json` 副檔名。
3. 安裝成功後會列出 `demo-hello.fixture` 的 active 狀態，側欄增加 Hello Plugin
   頁面入口。開啟後可看見文字、計數與表格；初始計數為 0。
4. 套件也提供 `demo-hello/read-summary@1.0.0`、`demo-hello/write-note@1.0.0`
   工具，以及 `demo-hello/summary-flow@1.0.0` Workflow。可透過 AEP 既有的工具
   與 Workflow 入口使用；寫入 note 後回頁面 Refresh，計數與表格會更新。
   此範例只保存本機合成筆記，不連公司系統，不代表任意自然語言模型選擇都已驗收。
5. **Disable** 會移除該 Plugin 的頁面與可用能力；**Enable** 可重新啟用。
   **Uninstall** 不會刪除使用者資料，重新安裝後仍可讀取原有筆記。

安裝與使用不需要 AEP／IT 核准。缺少執行環境、套件內容不一致、依賴不相容、
Plugin 正有工作執行等狀況，會回報實際錯誤；不假稱成功或已通過業務審核。
若某模型後端僅能接收執行摘要，資料未放行時仍須遵守既有模型資料規則。

## 第一階段支援範圍

- 同一台 Host 可同時啟用多個 Plugin，各自管理程序與具 namespace 的工具。
  第一版每個 Plugin 使用獨立 namespace，不得覆蓋核心或其他 Plugin 的名稱。
- 使用 AEP 的 Python interpreter 與 stdlib／現有依賴；不安裝套件到 AEP venv。
- 頁面是由核心渲染的 text／metric／table 宣告；不接受 Plugin HTML、JavaScript、
  iframe 或外部自動抓取內容。Worker 文字只當文字顯示。
- Web 管理 API 需既有身份驗證；Plugin read API 固定在自己的 namespace，
  不轉送管理 token／HTTP headers，不是任意網址 proxy。
- Skill／Workflow 使用既有安裝帳本，保留使用者改寫、關閉與移除的選擇。
- 防重複執行沿用每 turn 的既有語義，不承諾跨 AEP 程序重啟的 durable receipts。
- 執行中的工作阻止版本切換；有精確依賴的 Plugin 不可被不相容升級破壞。
- Plugin worker 是獨立程序，**不是 OS sandbox**；使用正常環境與 OS 身分。

## 資料位置

以 AEP 設定的 workspace 為準，不以程式安裝目錄為準：

```text
<workspace>/plugins/ledger.json
<workspace>/plugins/packages/<namespace>/<name>/<version>/
<workspace>/plugin-data/<namespace>/<name>/
```

Hello 範例資料位於 `plugin-data/demo-hello/fixture/`。不要把真實資料、帳號密碼
或 token 加進 Plugin 安裝封裝；封裝只有程式、manifest 與宣告資產。
程式更新不等於資料 migration；第一階段不提供 schema migration 或刪除資料 API。

## 開發者重建範例

在原始碼 checkout、具備既有 AEP dependencies 的 interpreter 執行：

```powershell
python scripts/build_feature_plugin_example.py
```

此 builder 是 source-checkout 測試工具，重用整合測試的 canonical worker／
manifest fixture；不是安裝後的公開 SDK。預設只重建範例 JSON，不安裝、啟動
Plugin、不修改 resident／Gateway／虛擬環境。

完整架構與授權範圍：`FEATURE_PLUGIN_ASSESSMENT_20261113.md`。
實作與驗收清單：`FEATURE_PLUGIN_SLICE1_PLAN_20261113.md`。
本階段通過後，BI／Wiki 真實功能抽離仍需按新的具體範圍接續，不視為已完成。

## 已知的非阻斷限制

若更新已完成提交，但退休舊資產後的最後一次 live registry 刷新失敗，API 尚無
獨立的成功 warning 欄位，舊版資產入口可能保留至安全重啟；目前工作完成後再
重啟可重新讀取磁碟上的正確版本。這不代表新版本的安裝被回復，也不會刪除
使用者資料。此項已列為後續改善，不能宣稱所有更新錯誤都能即時顯示 warning。

如果啟用後的程式檔案被更改，程序重啟會拒絕載入並回報
`plugin_staged_changed`；清單目前可能仍顯示設定版本為 active，直到停用或
重新啟用。執行結果會照實失敗，不會執行變更後的檔案；active 不是每次呼叫
都成功的保證。
