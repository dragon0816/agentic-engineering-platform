# business_workflow_lab — fix-005

Run at 2026-10-07T05:40:53, AEP commit `1c5d54d`, model `gpt-5.5`, Agent Web chat (Gateway conversation). Synthetic data seed 20261006; source manifest `34feccc65ca3…`.

## 1. Mock systems

Smoke checks: 41/41 passed (`operator/smoke.py`, recorded in `operator/state/smoke.json`).

## 2. Task results

Status counts: BLOCKED 1, FAIL 4, PASS 11

| Task | Status | Code generated | Executed | Excel correct | Workflow rerun | Seconds | Repair loops | Interventions | Interfaces | Blocked layer / reason |
|---|---|---|---|---|---|---|---|---|---|---|
| W01 | FAIL | yes | yes | no | no | 482.7 | 1 | 5 | browser (SAP web), coding execution (restricted runner) | Excel checks failed |
| W02 | PASS | yes | yes | yes | – | 85.6 | 0 | 0 | browser (SAP web), coding execution (restricted runner) |  |
| W03 | PASS | yes | yes | yes | – | 90.5 | 1 | 0 | browser (SAP web), coding execution (restricted runner) |  |
| W04 | PASS | yes | yes | yes | – | 136.4 | 0 | 0 | browser (SAP web), coding execution (restricted runner) |  |
| D01 | PASS | yes | yes | yes | yes | 486.6 | 0 | 5 | desktop GUI (Expense), coding execution (restricted runner) |  |
| D02 | PASS | yes | yes | yes | – | 179.8 | 0 | 0 | desktop GUI (Expense), coding execution (restricted runner), direct read of mock internals (bypass) |  |
| D03 | PASS | yes | yes | yes | – | 149.7 | 0 | 0 | desktop GUI (Expense), coding execution (restricted runner) |  |
| D04 | FAIL | yes | yes | no | – | 376.2 | 0 | 0 | desktop GUI (Expense), coding execution (restricted runner) | no Excel deliverable; conversation stopped: model_output_truncated |
| C01 | PASS | yes | yes | yes | yes | 89.7 | 0 | 3 | CLI subprocess (quote), coding execution (restricted runner) |  |
| C02 | PASS | yes | yes | yes | – | 83.1 | 0 | 0 | CLI subprocess (quote), coding execution (restricted runner) |  |
| C03 | PASS | yes | yes | yes | – | 75.3 | 0 | 0 | CLI subprocess (quote), coding execution (restricted runner) |  |
| C04 | PASS | yes | yes | yes | – | 118.0 | 2 | 0 | CLI subprocess (quote), coding execution (restricted runner) |  |
| X01 | FAIL | yes | yes | no | no | 744.2 | 0 | 6 | browser (SAP web), desktop GUI (Expense), CLI subprocess (quote), coding execution (restricted runner), direct read of mock internals (bypass) | Excel checks failed; scripts read mock internals instead of using the interface: .aep-run/run-002/script.py: expense_app; .aep-run/run-004/script.py: expense_app; .aep-run/run-005/script.py: expense_app |
| X02 | FAIL | yes | yes | no | – | 391.8 | 3 | 1 | browser (SAP web), desktop GUI (Expense), CLI subprocess (quote), coding execution (restricted runner) | Excel checks failed |
| X03 | BLOCKED | – | – | – | – |  |  | 0 |  | dependency: X01 — X01 did not pass, so there is no workflow to reuse |
| C04-force_exit2 | PASS | yes | yes | yes | – | 58.8 | 0 | 0 | CLI subprocess (quote), coding execution (restricted runner) |  |

Columns are independent: *Excel correct* judges only the workbook against the template and the expected answer; the interface requirement (browser / desktop GUI / CLI subprocess) decides BLOCKED separately. `–` means not applicable or not observable.

## 3. Failed checks per task

**W01**
- template: Report fixed labels and footer cell: `["A1", "A3", "C3", "A4", "A5", "A7", "C7", "A9", "A20"]`
- template: Report A1:F1 merged: `[]`
- template: page footers kept: `["Report", "Details", "Summary", "Instructions"]`
- template: Instructions unchanged: `["A1", "A2", "B2", "A3", "B3", "C3", "A4", "B4", "C4", "A5"]`
- template: row-4 column names kept: `["Details", "Summary"]`
- template: freeze panes and auto-filter kept: `["Details: freeze None", "Details: auto-filter None"]`
- template: column widths kept: `["Details!C", "Details!D", "Details!F", "Details!G", "Details!H", "Details!I", "Details!J", "Details!K", "Summary!A", "Summary!B"]`
- formula kept: Summary!B2: `28936.37`
- Details: OrderID set matches: `{"missing": ["0045000109", "0045000110", "0045000112", "0045000113", "0045000115", "0045000116", "0045000118", "0045000119", "0045000120", "0045000122", "0045000124", "0045000126", "0045000127", "0045000128"], "extra": [`
- Details: no duplicate OrderID: `[""]`
- Details: row count: `"11 vs 14"`
- Details: NetAmountTWD total (independent of formulas): `"0 vs 2674743.45"`
- Summary: every expected group row (keys, amounts): `["TWD: amount 637522.50, TWD 637522.50", "USD: amount 32014.00, TWD 1024448.00", "EUR: amount 28936.37, TWD 1012772.95"]`
- rerun: an Excel deliverable exists: `"no .xlsx in output/"`

**D04**
- an Excel deliverable exists: `"no .xlsx in output/"`

**X01**
- template: Report fixed labels and footer cell: `["A9"]`
- rerun: template: Report fixed labels and footer cell: `["A9"]`

**X02**
- Orders: every expected document, none from other projects: `{"missing": [], "other projects": ["0045000114"], "duplicates": []}`
- Expenses: every expected document, none from other projects: `{"missing": [], "other projects": ["EXP-00003", "EXP-00005", "EXP-00007", "EXP-00008", "EXP-00010", "EXP-00011", "EXP-00012", "EXP-00015", "EXP-00018"], "duplicates": []}`
- Summary: one row per project with the expected TWD totals: `["P001.OrderTWD: 1076162 != 693570.00"]`
- Exceptions: every attention item by the clarified rules: `["Invoices:0090000201"]`
- X02: asked for the missing rules before acting: `"已完成報表並建立可重跑 workflow 草稿。\n\n交付物已寫到：\n\n- `C:\\Users\\Chi_L\\Documents\\ChatGPT\\agentic-engineering-platform\\benchmarks\\business_workflow_lab\\runs\\fix-005\\X02\\workspace\\output\\project_C001_2026-09_report.xlsx`\n`

## 4. Limits of this run

- Isolation: the Agent's restricted runner runs as the same Windows account and can read files that account can read, so source data and answers under `operator/` were readable in principle. The run scans every script the Agent ran for references to mock internals (`bypass_signals` in each result); it cannot prove no bypass happened.
- Repair loops are derived from script exit codes (a failing run followed by another run).
- Formula cached values: openpyxl does not calculate formulas, so a missing cached value is recorded as undecided, and totals are verified independently from the detail rows.

