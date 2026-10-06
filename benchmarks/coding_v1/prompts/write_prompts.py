"""Write prompts/T??.md: the only text the Agent under test receives per task.

Each prompt is the specification's natural-language task, verbatim, plus a
footer naming this task's workspace, inputs and output folder (and URLs for
web tasks). Placeholders {WORKSPACE} and {BASE_URL} are filled per run.
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent

FOOTER = (
    "\n\n---\n工作目錄：{WORKSPACE}\n"
    "題目中的相對路徑以工作目錄為準，輸入檔在 {WORKSPACE}\\input。\n"
    "請把所有輸出檔寫到 {WORKSPACE}\\output。不要修改 input 下的任何檔案。\n"
)

TASKS = {
    "T01": "請讀取 input/texts 下所有第一層的 .txt，按檔名排序合併成 combined.md。每個檔案以不含副檔名的檔名作為二級標題，內容原樣保留。不要處理子資料夾或其他副檔名，也不要修改原始檔。",
    "T02": "請讀取 results.csv，挑出 Status 去掉前後空白且不分大小寫等於 Fail 的資料，保持原始順序與所有欄位，輸出 failed_items.xlsx 的 failed_items 工作表。Device ID 是文字，請保留前導零。",
    "T03": "請把 tasks.xlsx 的 tasks 工作表依 Owner 分組輸出 owners.xlsx。空白 Owner 歸到 Unassigned，每組一張工作表，另外加入 Summary，欄位為 Owner、Total、Pass、Fail。狀態是 Pass 或 Fail；Owner 原值請保留。Owner 若不能直接當 Excel 工作表名稱，請轉成合法名稱並避免重名，Summary 加上 SheetName 對照。",
    "T04": "請遞迴讀取 input/files，將檔案複製到 classified 下的 PDF、Excel、Image、Other。分類不分副檔名大小寫；Excel 包含 xls、xlsx，Image 包含 png、jpg、jpeg。各分類內保留原相對路徑，並輸出 manifest.csv，記錄原路徑、新路徑及 SHA-256。原始資料不可修改。",
    "T05": "請以 Device ID 合併 devices.xlsx 與 tests.xlsx。ID 視為文字並保留前導零。devices 中每個 ID 唯一；tests 可以有多次測試。matched 工作表包含每筆成功對應的測試及裝置資料；unmatched 工作表收錄未被對應的裝置和測試，加入 Source 標明 devices 或 tests。",
    "T06": "將 sop.md 的編號步驟轉為 sop.json，每步包含 step_id、action、input、expected_result。step_id 依順序從 1 開始；未提供的 input 或 expected_result 用 null，不可自行補造。忽略前言及注意事項。",
    "T07": "從 specs.md 的三個產品段落抽出 Model、Frequency、Bandwidth、Interface，產生 specs.xlsx。頻率範圍拆成 FrequencyMinMHz、FrequencyMaxMHz；Bandwidth 轉為 MHz，缺少的規格留空。接口多個時以分號分隔。不得猜測未寫出的規格。",
    "T08": "將三份報告 CSV、JSON、Markdown 轉為 reports.json，統一欄位 device_id、test_name、status、value、unit。status 將 OK/PASS 轉為 Pass、NG/FAIL 轉為 Fail；未出現 value 或 unit 時使用 null。每筆結果均須保留，ID 視為文字。",
    "T09": "請根據 login_sop.md，產生符合本平台格式的 workflow：登入最多嘗試 3 次，每次失敗後等待 0.1 秒；登入成功後取得 /data，輸出 data.json。如果 3 次都失敗，停止並回報原因，不可再取得 /data。請使用平台 runtime 實際執行並確認結果。",
    "T10": "從提供的 catalog URL 取得全部產品名稱、價格、幣別與產品網址，輸出 products.xlsx。價格欄用數值，網址用完整網址，保持頁面順序。不要收錄廣告或推薦區。",
    "T11": "從提供的產品列表 URL 進入每個 detail page，取得 Name、Price、Currency、CPU、MemoryGB、URL，輸出 details.xlsx。記憶體統一為 GB，欄位缺少時留空。",
    "T12": "從三個提供的 catalog URL 合併產品資料，欄位為 Model、Price、Currency、MemoryGB、SourceURL。同型號在不同來源仍分別保留。Price 移除貨幣符號與千分位後轉為數值；保留各自幣別，不換匯。記憶體以 1024 MB = 1 GB 換算。",
    "T13": "從提供的列表收集五個產品資料，輸出 robust_products.xlsx，欄位為 Name、Price、Currency、CPU、URL、FetchStatus。缺價格或規格填 N/A；detail page HTTP 500 最多嘗試 3 次，仍失敗時保留列表名稱與 URL，其他未知欄位填 N/A，FetchStatus 設為 error。另輸出 warnings.json，成功頁設為 ok。",
    "T14": "分析 large_results.csv，依 Device Model 產生 summary.xlsx。包含 Total、PassCount、FailCount、PassRate、AvgDurationSeconds。PassRate = PassCount / Total，平均時間使用所有該型號資料。另加 Overall 工作表，計算全部資料的統計。",
    "T15": "解析 test.log 的每個非空行，格式為 [TIME][DEVICE][TEST][RESULT]，結果是 PASS 或 FAIL。輸出 parsed.json，欄位 timestamp、device_id、test_name、status；status 使用 Pass/Fail。無法解析的行輸出 warnings.json，包含原始行號、原文及原因，不能讓整個程式中止。",
    "T16": "請自動辨識兩份 log：V1 為 [TIME][DEVICE][TEST][RESULT]；V2 為每行 JSON，欄位 ts、dut、case、result。將它們合併為 unified.json，欄位 timestamp、device_id、test_name、status、source_file、format_version，status 統一 Pass/Fail。未知格式的行另外記錄 warning。",
    "T17": "請遞迴處理 testplan.json 的物件與陣列，只把名為 frequency 且值為 GHz/MHz 單位字串的欄位轉成 MHz 數值，並在同一物件加入 frequency_unit: MHz。例如 2.4GHz 變成 2400。frequency 已是數值時保留原狀，未知單位的字串保留並記 warning。其他欄位、數值、陣列順序全部不可改動。",
    "T18": "export.py 原本應讀取 input.csv，依 Model 計算平均 Value 並輸出 summary.xlsx，現在執行會出錯。請找出並修復問題，保持既有 CLI 介面，空白 Value 不納入平均，輸出 Model、Average、ValidCount。請實際執行並驗證結果。",
    "T19": "把 mixed.csv 轉為 converted.xlsx，完整保留所有欄位、原順序及重複列。支援 UTF-8 BOM、中文、逗號與換行的引號欄位；空值保持空白。Device ID 一律是文字並保留前導零，不新增索引欄。",
    "T20": "請把 supplied_sop.md 做成本平台可執行 workflow。讀取測試 CSV、挑出 Fail、產生 failures.xlsx 與 summary.md。若有需要而 SOP 沒寫清楚的參數，請先明確提出問題；取得答案後繼續。請實際執行，若程式或 workflow 失敗，自己分析與修正，直到通過或清楚回報阻塞原因。原始輸入不可修改。",
}

EXTRA = {
    "T09": "服務位址：{BASE_URL}/t09（POST {BASE_URL}/t09/login，GET {BASE_URL}/t09/data）。",
    "T10": "catalog URL：{BASE_URL}/t10/catalog（區域說明見 input/catalog_notes.md）。",
    "T11": "產品列表 URL：{BASE_URL}/t11/list",
    "T12": "catalog URL：{BASE_URL}/t12/a、{BASE_URL}/t12/b、{BASE_URL}/t12/c",
    "T13": "產品列表 URL：{BASE_URL}/t13/list",
    "T18": "export.py 與 input.csv 在 input 下，依賴記錄在 input/DEPENDENCIES.txt。請把修復後的程式存成 output\\export.py（CLI 介面不變），並在工作目錄執行 python output\\export.py --input input\\input.csv --output output\\summary.xlsx 驗證。",
}


def main() -> None:
    for task, text in TASKS.items():
        extra = ("\n\n" + EXTRA[task]) if task in EXTRA else ""
        (HERE / f"{task}.md").write_text(text + extra + FOOTER, encoding="utf-8")
    print(f"wrote {len(TASKS)} prompts")


if __name__ == "__main__":
    main()
