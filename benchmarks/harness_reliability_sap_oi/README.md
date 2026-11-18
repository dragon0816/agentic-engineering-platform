# 模擬 SAP OI → Excel 驗收

這是專供 Harness reliability 的虛構基準，未安裝到正式 AEP，也未改 BI Knowledge。
結果與限制見 RESULTS.md；業務程序見 SOP.md。

## 重跑

在此 worktree 的已建置 .venv 執行，先啟動 loopback 測試網頁：

```powershell
.venv/Scripts/python.exe -B -m benchmarks.harness_reliability_sap_oi.site --directory .scratch/sap-site-new --port 8766
```

另一終端設定 AEP_GATEWAY_59_KEY（由既有安全管道提供，不貼進命令歷史），
使用 models/credentials 結構的本機 JSON 設定，endpoint 為
http://172.25.228.59:4000/v1、模型 gpt-5.6，credential name gateway_59_key，
environment_variable AEP_GATEWAY_59_KEY，routing_alias company_59，
options.company_59.max_tokens_field 為 max_completion_tokens。設定檔不能包含金鑰。

```powershell
.venv/Scripts/python.exe -B -m benchmarks.harness_reliability_sap_oi.live --workspace .scratch/sap-oi-new --model-config <local-model-config.json>
.venv/Scripts/python.exe -B -m pytest tests/test_sap_oi_benchmark.py -q
```

每次 workspace 必須不存在。需要 Chromium 的既有 BrowserSession 環境、
既有受限 Python 執行環境及 openpyxl。模型有非決定性；不保證固定回合數。
可離線直接開 mock-sap.html 的已代入 records 版本操作查詢與 CSV 匯出。
原始模板內 __RECORDS__ 必須由 site.make_page 代入。

本 fixture 的 restricted Python network-rule presence 使用測試 stub，
不是 production firewall/security containment 驗證。瀏覽器僅允許 loopback origin。
run_tracked_thread 與既有 state/policy/Bridge 仍正常使用。

build.mjs 與 render.mjs 是保留的失敗 Artifact prototype，勿當成可用產檔器。
最終使用 workbook.py + pivot_package.py；desktop Excel 開啟/刷新需人工確認。
