# business_workflow_lab — fix-003

Run at 2026-10-07T04:28:58, AEP commit `282b0f4`, model `gpt-5.5`, Agent Web chat (Gateway conversation). Synthetic data seed 20261006; source manifest `34feccc65ca3…`.

## 1. Mock systems

Smoke checks: 37/37 passed (`operator/smoke.py`, recorded in `operator/state/smoke.json`).

## 2. Task results

Status counts: FAIL 3, NOT_RUN 12

| Task | Status | Code generated | Executed | Excel correct | Workflow rerun | Seconds | Repair loops | Interventions | Interfaces | Blocked layer / reason |
|---|---|---|---|---|---|---|---|---|---|---|
| W01 | FAIL | yes | yes | no | – | 119.6 | 0 | 6 | coding execution (restricted runner) | the site was never reached (the browser tool was available) |
| W02 | FAIL | yes | yes | no | – | 25.4 | 0 | 0 | coding execution (restricted runner) | the site was never reached (the browser tool was available) |
| W03 | FAIL | yes | yes | no | – | 24.1 | 0 | 0 | coding execution (restricted runner) | the site was never reached (the browser tool was available) |
| W04 | NOT_RUN | – | – | – | – |  |  | 0 |  |  |
| D01 | NOT_RUN | – | – | – | – |  |  | 0 |  |  |
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

**W01**
- an Excel deliverable exists: `"no .xlsx in output/"`

**W02**
- an Excel deliverable exists: `"no .xlsx in output/"`
- W02: every order's detail page was opened: `["0045000101", "0045000107", "0045000109", "0045000114", "0045000119", "0045000125", "0045000129", "0045000132", "0045000136"]`

**W03**
- an Excel deliverable exists: `"no .xlsx in output/"`

## 4. Limits of this run

- Isolation: the Agent's restricted runner runs as the same Windows account and can read files that account can read, so source data and answers under `operator/` were readable in principle. The run scans every script the Agent ran for references to mock internals (`bypass_signals` in each result); it cannot prove no bypass happened.
- Repair loops are derived from script exit codes (a failing run followed by another run).
- Formula cached values: openpyxl does not calculate formulas, so a missing cached value is recorded as undecided, and totals are verified independently from the detail rows.

