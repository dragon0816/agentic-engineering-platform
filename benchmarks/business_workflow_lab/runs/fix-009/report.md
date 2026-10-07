# business_workflow_lab — fix-009

Run at 2026-10-07T13:47:42, AEP commit `fa09c03`, model `gpt-5.5`, Agent Web chat (Gateway conversation). Synthetic data seed 20261006; source manifest `34feccc65ca3…`.

## 1. Mock systems

Smoke checks: 41/41 passed (`operator/smoke.py`, recorded in `operator/state/smoke.json`).

## 2. Task results

Status counts: FAIL 1, NOT_RUN 10, PASS 4

| Task | Status | Code generated | Executed | Excel correct | Workflow rerun | Seconds | Repair loops | Interventions | Interfaces | Blocked layer / reason |
|---|---|---|---|---|---|---|---|---|---|---|
| W01 | PASS | yes | yes | yes | yes | 401.4 | 0 | 4 | browser (SAP web), coding execution (restricted runner) |  |
| W02 | PASS | yes | yes | yes | – | 122.4 | 1 | 0 | browser (SAP web), coding execution (restricted runner) |  |
| W03 | PASS | yes | yes | yes | – | 98.0 | 1 | 0 | browser (SAP web), coding execution (restricted runner) |  |
| W04 | PASS | yes | yes | yes | – | 107.2 | 0 | 0 | browser (SAP web), coding execution (restricted runner) |  |
| D01 | FAIL | yes | yes | yes | no | 589.0 | 4 | 7 | desktop GUI (Expense), coding execution (restricted runner) | the parameter rerun did not succeed with unchanged workflow code |
| D02 | NOT_RUN | – | – | – | – |  |  | 0 |  |  |
| D03 | NOT_RUN | – | – | – | – |  |  | 0 |  |  |
| D04 | NOT_RUN | – | – | – | – |  |  | 0 |  |  |
| C01 | NOT_RUN | – | – | – | – |  |  | 0 |  |  |
| C02 | NOT_RUN | – | – | – | – |  |  | 0 |  |  |
| C03 | NOT_RUN | – | – | – | – |  |  | 0 |  |  |
| C04 | NOT_RUN | – | – | – | – |  |  | 0 |  |  |
| X01 | NOT_RUN | – | – | – | – |  |  | 0 |  |  |
| X02 | NOT_RUN | – | – | – | – |  |  | 0 |  |  |
| X03 | NOT_RUN | – | – | – | – |  |  | 0 |  |  |

Columns are independent: *Excel correct* judges only the workbook against the template and the expected answer; the interface requirement (browser / desktop GUI / CLI subprocess) decides BLOCKED separately. `–` means not applicable or not observable.

## 3. Failed checks per task

## 4. Limits of this run

- Isolation: the Agent's restricted runner runs as the same Windows account and can read files that account can read, so source data and answers under `operator/` were readable in principle. The run scans every script the Agent ran for references to mock internals (`bypass_signals` in each result); it cannot prove no bypass happened.
- Repair loops are derived from script exit codes (a failing run followed by another run).
- Formula cached values: openpyxl does not calculate formulas, so a missing cached value is recorded as undecided, and totals are verified independently from the detail rows.

