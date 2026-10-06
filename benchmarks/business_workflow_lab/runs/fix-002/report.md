# business_workflow_lab — fix-002

Run at 2026-10-07T03:37:30, AEP commit `27e4379`, model `gpt-5.5`, Agent Web chat (Gateway conversation). Synthetic data seed 20261006; source manifest `34feccc65ca3…`.

## 1. Mock systems

Smoke checks: 37/37 passed (`operator/smoke.py`, recorded in `operator/state/smoke.json`).

## 2. Task results

Status counts: BLOCKED 1, FAIL 10, PASS 5

| Task | Status | Code generated | Executed | Excel correct | Workflow rerun | Seconds | Repair loops | Interventions | Interfaces | Blocked layer / reason |
|---|---|---|---|---|---|---|---|---|---|---|
| W01 | FAIL | yes | yes | yes | yes | 204.4 | 2 | 4 | HTTP client script (SAP web, no browser), coding execution (restricted runner) | scripts reached the site with an HTTP client (the browser tool was available) |
| W02 | FAIL | yes | yes | yes | – | 114.2 | 2 | 0 | HTTP client script (SAP web, no browser), coding execution (restricted runner) | scripts reached the site with an HTTP client (the browser tool was available) |
| W03 | FAIL | yes | yes | yes | – | 156.1 | 3 | 0 | HTTP client script (SAP web, no browser), coding execution (restricted runner) | scripts reached the site with an HTTP client (the browser tool was available) |
| W04 | FAIL | yes | yes | no | – | 148.0 | 2 | 0 | HTTP client script (SAP web, no browser), coding execution (restricted runner) | scripts reached the site with an HTTP client (the browser tool was available) |
| D01 | PASS | yes | yes | yes | yes | 335.6 | 0 | 4 | desktop GUI (Expense), coding execution (restricted runner) |  |
| D02 | PASS | yes | yes | yes | – | 191.3 | 0 | 0 | desktop GUI (Expense), coding execution (restricted runner) |  |
| D03 | FAIL | no | no | no | – | 11.5 |  | 0 |  | the Expense desktop app was never operated |
| D04 | PASS | yes | yes | yes | – | 213.1 | 0 | 0 | desktop GUI (Expense), coding execution (restricted runner) |  |
| C01 | FAIL | yes | yes | yes | no | 169.7 | 0 | 3 | CLI subprocess (quote), coding execution (restricted runner) | the parameter rerun did not succeed with unchanged workflow code |
| C02 | FAIL | yes | yes | no | – | 111.9 | 1 | 0 | CLI subprocess (quote), coding execution (restricted runner) | Excel checks failed |
| C03 | PASS | yes | yes | yes | – | 96.9 | 1 | 0 | CLI subprocess (quote), coding execution (restricted runner) |  |
| C04 | FAIL | yes | yes | no | – | 131.1 | 2 | 0 | CLI subprocess (quote), coding execution (restricted runner) | Excel checks failed |
| X01 | FAIL | yes | yes | yes | no | 353.7 | 1 | 3 | HTTP client script (SAP web, no browser), desktop GUI (Expense), CLI subprocess (quote), coding execution (restricted runner) | scripts reached the site with an HTTP client (the browser tool was available) |
| X02 | FAIL | yes | yes | no | – | 348.4 | 2 | 1 | browser (SAP web), desktop GUI (Expense), CLI subprocess (quote), coding execution (restricted runner) | Excel checks failed; conversation stopped: multiple_tool_calls_not_supported |
| X03 | BLOCKED | – | – | – | – |  |  | 0 |  | dependency: X01 — X01 did not pass, so there is no workflow to reuse |
| C04-force_exit2 | PASS | yes | yes | yes | – | 69.0 | 0 | 0 | CLI subprocess (quote), coding execution (restricted runner) |  |

Columns are independent: *Excel correct* judges only the workbook against the template and the expected answer; the interface requirement (browser / desktop GUI / CLI subprocess) decides BLOCKED separately. `–` means not applicable or not observable.

## 3. Failed checks per task

**W04**
- Details: field values: `["0045000113.ProjectID: 'N/A' != ''", "0045000113.CustomerContact: 'N/A' != ''", "0045000115.ProjectID: 'N/A' != ''", "0045000116.ProjectID: 'N/A' != ''", "0045000120.ProjectID: 'N/A' != ''", "0045000124.ProjectID: 'N/A'`

**D03**
- an Excel deliverable exists: `"no .xlsx in output/"`

**C01**
- rerun: an Excel deliverable exists: `"no .xlsx in output/"`

**C02**
- template: column widths kept: `["Quotes!A", "Quotes!C", "Quotes!F", "Quotes!G", "Quotes!H", "Quotes!I", "Quotes!J", "Quotes!K", "Lines!A", "Lines!B"]`

**C04**
- Quotes: field values: `["Q0016.ProjectID: 'N/A' != ''", "Q0019.ProjectID: 'N/A' != ''"]`

**X01**
- rerun: an Excel deliverable exists: `"no .xlsx in output/"`

**X02**
- template: column widths kept: `["Orders!A", "Orders!B", "Orders!E", "Orders!F", "Orders!G", "Orders!H", "Invoices!A", "Invoices!C", "Invoices!E", "Invoices!G"]`
- Orders: every expected document, none from other projects: `{"missing": [], "other projects": ["0045000114"], "duplicates": []}`
- Expenses: every expected document, none from other projects: `{"missing": [], "other projects": ["EXP-00003", "EXP-00005", "EXP-00007", "EXP-00008", "EXP-00010", "EXP-00011", "EXP-00012", "EXP-00015", "EXP-00018"], "duplicates": []}`
- Exceptions: every attention item by the clarified rules: `["Invoices:0090000201"]`
- X02: asked for the missing rules before acting: `"完成。我已整理 2026-09（以 2026-10-06 的「上個月」計算）C001 的訂單、發票/費用、報價，套用 `project_template.xlsx`，並以 `fx_rates.csv` 換算為台幣。\n\n輸出檔案在：\n\n- `output\\C001_project_report_2026-09_TWD.xlsx`\n\n同時保留中間匯出資料：\n\n- `output\\orders_C001_2026-09.`

## 4. Limits of this run

- Isolation: the Agent's restricted runner runs as the same Windows account and can read files that account can read, so source data and answers under `operator/` were readable in principle. The run scans every script the Agent ran for references to mock internals (`bypass_signals` in each result); it cannot prove no bypass happened.
- Repair loops are derived from script exit codes (a failing run followed by another run).
- Formula cached values: openpyxl does not calculate formulas, so a missing cached value is recorded as undecided, and totals are verified independently from the detail rows.

