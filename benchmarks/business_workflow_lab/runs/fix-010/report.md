# business_workflow_lab — fix-010

Run at 2026-10-07T18:53:10, AEP commit `db38f28`, model `gpt-5.5`, Agent Web chat (Gateway conversation). Synthetic data seed 20261006; source manifest `34feccc65ca3…`.

## 1. Mock systems

Smoke checks: 41/41 passed (`operator/smoke.py`, recorded in `operator/state/smoke.json`).

## 2. Task results

Status counts: FAIL 2, PASS 14

| Task | Status | Code generated | Executed | Excel correct | Workflow rerun | Seconds | Repair loops | Interventions | Interfaces | Blocked layer / reason |
|---|---|---|---|---|---|---|---|---|---|---|
| W01 | PASS | yes | yes | yes | yes | 258.8 | 0 | 5 | browser (SAP web), coding execution (restricted runner) |  |
| W02 | PASS | yes | yes | yes | – | 108.4 | 1 | 0 | browser (SAP web), coding execution (restricted runner) |  |
| W03 | PASS | yes | yes | yes | – | 71.4 | 0 | 0 | browser (SAP web), coding execution (restricted runner) |  |
| W04 | PASS | yes | yes | yes | – | 107.8 | 0 | 0 | browser (SAP web), coding execution (restricted runner) |  |
| D01 | PASS | yes | yes | yes | yes | 363.1 | 1 | 4 | desktop GUI (Expense), coding execution (restricted runner) |  |
| D02 | PASS | yes | yes | yes | – | 263.3 | 1 | 0 | desktop GUI (Expense), coding execution (restricted runner) |  |
| D03 | PASS | yes | yes | yes | – | 132.0 | 0 | 0 | desktop GUI (Expense), coding execution (restricted runner) |  |
| D04 | PASS | yes | yes | yes | – | 97.5 | 0 | 0 | desktop GUI (Expense), coding execution (restricted runner) |  |
| C01 | PASS | yes | yes | yes | yes | 93.4 | 0 | 4 | CLI subprocess (quote), coding execution (restricted runner) |  |
| C02 | FAIL | yes | yes | no | – | 91.3 | 1 | 0 | CLI subprocess (quote), coding execution (restricted runner) | Excel checks failed |
| C03 | PASS | yes | yes | yes | – | 55.4 | 0 | 0 | CLI subprocess (quote), coding execution (restricted runner) |  |
| C04 | PASS | yes | yes | yes | – | 67.1 | 0 | 0 | CLI subprocess (quote), coding execution (restricted runner) |  |
| X01 | PASS | yes | yes | yes | yes | 409.2 | 0 | 5 | browser (SAP web), desktop GUI (Expense), CLI subprocess (quote), coding execution (restricted runner) |  |
| X02 | FAIL | yes | yes | no | – | 570.2 | 1 | 4 | browser (SAP web), desktop GUI (Expense), CLI subprocess (quote), coding execution (restricted runner) | Excel checks failed |
| X03 | PASS | yes | yes | yes | – | 157.2 | 0 | 1 | browser (SAP web), desktop GUI (Expense), CLI subprocess (quote), coding execution (restricted runner) |  |
| C04-force_exit2 | PASS | yes | yes | yes | – | 63.6 | 0 | 0 | CLI subprocess (quote), coding execution (restricted runner) |  |

Columns are independent: *Excel correct* judges only the workbook against the template and the expected answer; the interface requirement (browser / desktop GUI / CLI subprocess) decides BLOCKED separately. `–` means not applicable or not observable.

## 3. Failed checks per task

**C02**
- formula kept: Summary!B2: `"Total NetAmountTWD"`
- Quotes: field values: `["Q0016.ProjectID: 'N/A' != ''", "Q0019.ProjectID: 'N/A' != ''", "Q0020.ProjectID: 'N/A' != ''", "Q0021.ProjectID: 'N/A' != ''"]`

**X02**
- Exceptions: every attention item by the clarified rules: `["Invoices:0090000201"]`

## 4. Limits of this run

- Isolation: the Agent's restricted runner runs as the same Windows account and can read files that account can read, so source data and answers under `operator/` were readable in principle. The run scans every script the Agent ran for references to mock internals (`bypass_signals` in each result); it cannot prove no bypass happened.
- Repair loops are derived from script exit codes (a failing run followed by another run).
- Formula cached values: openpyxl does not calculate formulas, so a missing cached value is recorded as undecided, and totals are verified independently from the detail rows.

