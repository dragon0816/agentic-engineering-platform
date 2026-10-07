# business_workflow_lab — fix-007

Run at 2026-10-07T10:05:07, AEP commit `6abe617`, model `gpt-5.5`, Agent Web chat (Gateway conversation). Synthetic data seed 20261006; source manifest `34feccc65ca3…`.

## 1. Mock systems

Smoke checks: 41/41 passed (`operator/smoke.py`, recorded in `operator/state/smoke.json`).

## 2. Task results

Status counts: BLOCKED 1, FAIL 4, PASS 11

| Task | Status | Code generated | Executed | Excel correct | Workflow rerun | Seconds | Repair loops | Interventions | Interfaces | Blocked layer / reason |
|---|---|---|---|---|---|---|---|---|---|---|
| W01 | FAIL | yes | yes | yes | no | 446.3 | 0 | 6 | browser (SAP web), coding execution (restricted runner) | the parameter rerun did not succeed with unchanged workflow code |
| W02 | PASS | yes | yes | yes | – | 132.3 | 1 | 0 | browser (SAP web), coding execution (restricted runner) |  |
| W03 | PASS | yes | yes | yes | – | 82.1 | 0 | 0 | browser (SAP web), coding execution (restricted runner) |  |
| W04 | PASS | yes | yes | yes | – | 178.8 | 0 | 0 | browser (SAP web), coding execution (restricted runner) |  |
| D01 | PASS | yes | yes | yes | yes | 889.7 | 0 | 4 | desktop GUI (Expense), coding execution (restricted runner) |  |
| D02 | PASS | yes | yes | yes | – | 448.2 | 0 | 0 | desktop GUI (Expense), coding execution (restricted runner) |  |
| D03 | PASS | yes | yes | yes | – | 157.9 | 0 | 0 | desktop GUI (Expense), coding execution (restricted runner) |  |
| D04 | FAIL | no | no | no | – | 21.7 |  | 0 |  | the Expense desktop app was never operated |
| C01 | PASS | yes | yes | yes | yes | 129.4 | 0 | 3 | CLI subprocess (quote), coding execution (restricted runner) |  |
| C02 | PASS | yes | yes | yes | – | 121.5 | 1 | 0 | CLI subprocess (quote), coding execution (restricted runner) |  |
| C03 | PASS | yes | yes | yes | – | 146.6 | 2 | 0 | CLI subprocess (quote), coding execution (restricted runner) |  |
| C04 | PASS | yes | yes | yes | – | 188.7 | 3 | 0 | CLI subprocess (quote), coding execution (restricted runner) |  |
| X01 | FAIL | yes | yes | yes | no | 868.9 | 0 | 9 | browser (SAP web), desktop GUI (Expense), CLI subprocess (quote), coding execution (restricted runner) | the parameter rerun did not succeed with unchanged workflow code |
| X02 | FAIL | yes | yes | no | – | 242.0 | 0 | 1 | browser (SAP web), desktop GUI (Expense), CLI subprocess (quote), coding execution (restricted runner) | no Excel deliverable; conversation stopped: model_http_error |
| X03 | BLOCKED | – | – | – | – |  |  | 0 |  | dependency: X01 — X01 did not pass, so there is no workflow to reuse |
| C04-force_exit2 | PASS | yes | yes | yes | – | 53.4 | 0 | 0 | CLI subprocess (quote), coding execution (restricted runner) |  |

Columns are independent: *Excel correct* judges only the workbook against the template and the expected answer; the interface requirement (browser / desktop GUI / CLI subprocess) decides BLOCKED separately. `–` means not applicable or not observable.

## 3. Failed checks per task

**W01**
- rerun: an Excel deliverable exists: `"no .xlsx in output/"`

**D04**
- an Excel deliverable exists: `"no .xlsx in output/"`

**X01**
- rerun: an Excel deliverable exists: `"no .xlsx in output/"`

**X02**
- an Excel deliverable exists: `"no .xlsx in output/"`

## 4. Limits of this run

- Isolation: the Agent's restricted runner runs as the same Windows account and can read files that account can read, so source data and answers under `operator/` were readable in principle. The run scans every script the Agent ran for references to mock internals (`bypass_signals` in each result); it cannot prove no bypass happened.
- Repair loops are derived from script exit codes (a failing run followed by another run).
- Formula cached values: openpyxl does not calculate formulas, so a missing cached value is recorded as undecided, and totals are verified independently from the detail rows.

