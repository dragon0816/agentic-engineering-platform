# business_workflow_lab — fix-006

Run at 2026-10-07T07:00:33, AEP commit `a3816ba`, model `gpt-5.5`, Agent Web chat (Gateway conversation). Synthetic data seed 20261006; source manifest `34feccc65ca3…`.

## 1. Mock systems

Smoke checks: 41/41 passed (`operator/smoke.py`, recorded in `operator/state/smoke.json`).

## 2. Task results

Status counts: BLOCKED 1, FAIL 2, PASS 13

| Task | Status | Code generated | Executed | Excel correct | Workflow rerun | Seconds | Repair loops | Interventions | Interfaces | Blocked layer / reason |
|---|---|---|---|---|---|---|---|---|---|---|
| W01 | PASS | yes | yes | yes | yes | 417.3 | 2 | 4 | browser (SAP web), coding execution (restricted runner) |  |
| W02 | PASS | yes | yes | yes | – | 131.4 | 1 | 0 | browser (SAP web), coding execution (restricted runner) |  |
| W03 | PASS | yes | yes | yes | – | 87.6 | 0 | 0 | browser (SAP web), coding execution (restricted runner) |  |
| W04 | PASS | yes | yes | yes | – | 127.3 | 0 | 0 | browser (SAP web), coding execution (restricted runner) |  |
| D01 | PASS | yes | yes | yes | yes | 400.0 | 2 | 4 | desktop GUI (Expense), coding execution (restricted runner) |  |
| D02 | PASS | yes | yes | yes | – | 218.6 | 1 | 0 | desktop GUI (Expense), coding execution (restricted runner) |  |
| D03 | PASS | yes | yes | yes | – | 153.0 | 1 | 0 | desktop GUI (Expense), coding execution (restricted runner) |  |
| D04 | PASS | yes | yes | yes | – | 110.4 | 0 | 0 | desktop GUI (Expense), coding execution (restricted runner) |  |
| C01 | PASS | yes | yes | yes | yes | 385.9 | 0 | 6 | CLI subprocess (quote), coding execution (restricted runner), direct read of mock internals (bypass) |  |
| C02 | PASS | yes | yes | yes | – | 107.4 | 1 | 0 | CLI subprocess (quote), coding execution (restricted runner) |  |
| C03 | PASS | yes | yes | yes | – | 92.9 | 0 | 0 | CLI subprocess (quote), coding execution (restricted runner) |  |
| C04 | PASS | yes | yes | yes | – | 133.0 | 2 | 0 | CLI subprocess (quote), coding execution (restricted runner) |  |
| X01 | FAIL | yes | yes | yes | no | 708.4 | 3 | 5 | browser (SAP web), desktop GUI (Expense), CLI subprocess (quote), coding execution (restricted runner), direct read of mock internals (bypass) | the parameter rerun did not succeed with unchanged workflow code; scripts read mock internals instead of using the interface: .aep-run/run-003/script.py: expense_app; .aep-run/run-004/script.py: expense_app; .aep-run/run-005/script.py: expense_app |
| X02 | FAIL | yes | yes | no | – | 351.2 | 0 | 1 | browser (SAP web), desktop GUI (Expense), CLI subprocess (quote), coding execution (restricted runner) | Excel checks failed |
| X03 | BLOCKED | – | – | – | – |  |  | 0 |  | dependency: X01 — X01 did not pass, so there is no workflow to reuse |
| C04-force_exit2 | PASS | yes | yes | yes | – | 49.1 | 0 | 0 | CLI subprocess (quote), coding execution (restricted runner) |  |

Columns are independent: *Excel correct* judges only the workbook against the template and the expected answer; the interface requirement (browser / desktop GUI / CLI subprocess) decides BLOCKED separately. `–` means not applicable or not observable.

## 3. Failed checks per task

**X02**
- Orders: every expected document, none from other projects: `{"missing": [], "other projects": ["0045000114"], "duplicates": []}`
- Expenses: every expected document, none from other projects: `{"missing": [], "other projects": ["EXP-00003", "EXP-00005", "EXP-00007", "EXP-00008", "EXP-00010", "EXP-00011", "EXP-00012", "EXP-00015", "EXP-00018"], "duplicates": []}`
- Summary: one row per project with the expected TWD totals: `["P001.OrderTWD: 1076162 != 693570.00"]`
- Exceptions: every attention item by the clarified rules: `["Expenses:EXP-00006", "Invoices:0090000201"]`
- X02: asked for the missing rules before acting: `"已完成報表並建立可重跑的 workflow 草稿。\n\n交付物已寫到：\n\n`C:\\Users\\Chi_L\\Documents\\ChatGPT\\agentic-engineering-platform\\benchmarks\\business_workflow_lab\\runs\\fix-006\\X02\\workspace\\output\\project_C001_2026-09_report.xlsx`\n\`

## 4. Limits of this run

- Isolation: the Agent's restricted runner runs as the same Windows account and can read files that account can read, so source data and answers under `operator/` were readable in principle. The run scans every script the Agent ran for references to mock internals (`bypass_signals` in each result); it cannot prove no bypass happened.
- Repair loops are derived from script exit codes (a failing run followed by another run).
- Formula cached values: openpyxl does not calculate formulas, so a missing cached value is recorded as undecided, and totals are verified independently from the detail rows.

