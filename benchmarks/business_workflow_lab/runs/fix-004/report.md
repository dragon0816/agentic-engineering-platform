# business_workflow_lab — fix-004

Run at 2026-10-07T04:37:56, AEP commit `9f335c2`, model `gpt-5.5`, Agent Web chat (Gateway conversation). Synthetic data seed 20261006; source manifest `34feccc65ca3…`.

## 1. Mock systems

Smoke checks: 37/37 passed (`operator/smoke.py`, recorded in `operator/state/smoke.json`).

## 2. Task results

Status counts: BLOCKED 1, FAIL 5, PASS 9, TIMEOUT 1

| Task | Status | Code generated | Executed | Excel correct | Workflow rerun | Seconds | Repair loops | Interventions | Interfaces | Blocked layer / reason |
|---|---|---|---|---|---|---|---|---|---|---|
| W01 | TIMEOUT | yes | yes | no | no | 900.1 | 4 | 8 | browser (SAP web), coding execution (restricted runner) | the turn did not finish within the time limit |
| W02 | PASS | yes | yes | yes | – | 94.4 | 0 | 0 | browser (SAP web), coding execution (restricted runner) |  |
| W03 | PASS | yes | yes | yes | – | 132.1 | 2 | 0 | browser (SAP web), coding execution (restricted runner) |  |
| W04 | FAIL | yes | yes | no | – | 235.1 | 0 | 1 | browser (SAP web), coding execution (restricted runner) | Excel checks failed; conversation stopped: tool_loop_limit |
| D01 | FAIL | yes | yes | yes | no | 303.7 | 1 | 4 | desktop GUI (Expense), coding execution (restricted runner) | the parameter rerun did not succeed with unchanged workflow code |
| D02 | PASS | yes | yes | yes | – | 179.4 | 0 | 0 | desktop GUI (Expense), coding execution (restricted runner) |  |
| D03 | FAIL | yes | yes | no | – | 125.0 | 1 | 0 | desktop GUI (Expense), coding execution (restricted runner) | Excel checks failed |
| D04 | PASS | yes | yes | yes | – | 163.0 | 0 | 0 | desktop GUI (Expense), coding execution (restricted runner) |  |
| C01 | PASS | yes | yes | yes | yes | 88.8 | 0 | 3 | CLI subprocess (quote), coding execution (restricted runner) |  |
| C02 | PASS | yes | yes | yes | – | 69.0 | 0 | 0 | CLI subprocess (quote), coding execution (restricted runner) |  |
| C03 | PASS | yes | yes | yes | – | 84.3 | 0 | 0 | CLI subprocess (quote), coding execution (restricted runner) |  |
| C04 | PASS | yes | yes | yes | – | 80.8 | 0 | 0 | CLI subprocess (quote), coding execution (restricted runner) |  |
| X01 | FAIL | yes | yes | no | no | 198.0 | 0 | 4 | browser (SAP web), desktop GUI (Expense), CLI subprocess (quote), coding execution (restricted runner), direct read of mock internals (bypass) | Excel checks failed; scripts read mock internals instead of using the interface: .aep-run/run-002/script.py: expense_app; .aep-run/run-003/script.py: expense_app |
| X02 | FAIL | yes | yes | no | – | 303.7 | 1 | 1 | browser (SAP web), desktop GUI (Expense), CLI subprocess (quote), coding execution (restricted runner) | Excel checks failed |
| X03 | BLOCKED | – | – | – | – |  |  | 0 |  | dependency: X01 — X01 did not pass, so there is no workflow to reuse |
| C04-force_exit2 | PASS | yes | yes | yes | – | 53.2 | 0 | 0 | CLI subprocess (quote), coding execution (restricted runner) |  |

Columns are independent: *Excel correct* judges only the workbook against the template and the expected answer; the interface requirement (browser / desktop GUI / CLI subprocess) decides BLOCKED separately. `–` means not applicable or not observable.

## 3. Failed checks per task

**W01**
- template: Report fixed labels and footer cell: `["A1", "A3"]`
- template: row-4 column names kept: `["Details", "Summary"]`
- formula kept: Summary!B2: `"2026-09-01"`
- rerun: an Excel deliverable exists: `"no .xlsx in output/"`

**W04**
- W04: the injected session expiry happened and the Agent signed in again: `{"user_agents": ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/154.0.0.0 Safari/537.36 Edg/154.0.0.0"], "browser": true, "logins": 1, "queries": 3, "details": ["00450001`

**D01**
- rerun: an Excel deliverable exists: `"no .xlsx in output/"`

**D03**
- Summary: every expected group row (keys, amounts): `["E001|Travel|TWD: amount 4430.00, TWD 4430.00", "E001|Hotel|USD: amount 200.00, TWD 6400.00", "E001|Supplies|EUR: amount 42.50, TWD 1487.50", "E001|Meals|TWD: amount 620.00, TWD 620.00", "E001|Travel|EUR: amount 60.00, `

**X01**
- template: Report fixed labels and footer cell: `["A9"]`
- rerun: an Excel deliverable exists: `"no .xlsx in output/"`

**X02**
- Orders: every expected document, none from other projects: `{"missing": [], "other projects": ["0045000114"], "duplicates": []}`
- Expenses: every expected document, none from other projects: `{"missing": [], "other projects": ["EXP-00003", "EXP-00005", "EXP-00007", "EXP-00008", "EXP-00010", "EXP-00011", "EXP-00012", "EXP-00015", "EXP-00018"], "duplicates": []}`
- Summary: one row per project with the expected TWD totals: `["P001.OrderTWD: 1076162 != 693570.00"]`
- Exceptions: every attention item by the clarified rules: `["Invoices:0090000201"]`
- X02: asked for the missing rules before acting: `"已完成整理並產出報表：\n\n- 報表檔案：`workspace\\output\\project_report_C001_2026-09.xlsx`\n- 中間資料：\n  - `workspace\\output\\downloads\\orders_C001_2026-09.csv`\n  - `workspace\\output\\downloads\\invoices_C001_2026-09.csv`\n  - `work`

## 4. Limits of this run

- Isolation: the Agent's restricted runner runs as the same Windows account and can read files that account can read, so source data and answers under `operator/` were readable in principle. The run scans every script the Agent ran for references to mock internals (`bypass_signals` in each result); it cannot prove no bypass happened.
- Repair loops are derived from script exit codes (a failing run followed by another run).
- Formula cached values: openpyxl does not calculate formulas, so a missing cached value is recorded as undecided, and totals are verified independently from the detail rows.

