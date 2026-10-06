# business_workflow_lab — fix-001

Run at 2026-10-06T23:57:17, AEP commit `0999b4a`, model `gpt-5.5`, Agent Web chat (Gateway conversation). Synthetic data seed 20261006; source manifest `34feccc65ca3…`.

## 1. Mock systems

Smoke checks: 59/59 passed (`operator/smoke.py`, recorded in `operator/state/smoke.json`).

## 2. Task results

Status counts: BLOCKED 1, FAIL 11, PASS 4

| Task | Status | Code generated | Executed | Excel correct | Workflow rerun | Seconds | Repair loops | Interventions | Interfaces | Blocked layer / reason |
|---|---|---|---|---|---|---|---|---|---|---|
| W01 | FAIL | yes | yes | no | – | 46.9 | 0 | 0 | browser (SAP web), coding execution (restricted runner) | no Excel deliverable; conversation stopped: tool_loop_limit |
| W02 | FAIL | yes | yes | no | – | 33.0 | 0 | 0 | browser (SAP web), coding execution (restricted runner) | no Excel deliverable; conversation stopped: tool_loop_limit |
| W03 | PASS | yes | yes | yes | – | 93.9 | 2 | 0 | browser (SAP web), coding execution (restricted runner) |  |
| W04 | FAIL | yes | yes | no | – | 44.6 | 0 | 0 | browser (SAP web), coding execution (restricted runner) | no Excel deliverable; conversation stopped: tool_loop_limit |
| D01 | FAIL | yes | yes | no | no | 170.6 | 1 | 1 | desktop GUI (Expense), coding execution (restricted runner) | Excel checks failed; conversation stopped: tool_loop_limit |
| D02 | FAIL | yes | yes | no | – | 142.4 | 0 | 0 | desktop GUI (Expense), coding execution (restricted runner) | no Excel deliverable; conversation stopped: tool_loop_limit |
| D03 | FAIL | yes | yes | no | – | 37.2 | 0 | 0 | coding execution (restricted runner) | the Expense desktop app was never operated |
| D04 | FAIL | yes | yes | no | – | 137.7 | 0 | 0 | desktop GUI (Expense), coding execution (restricted runner) | no Excel deliverable; conversation stopped: tool_loop_limit |
| C01 | FAIL | yes | yes | yes | no | 102.8 | 0 | 3 | CLI subprocess (quote), coding execution (restricted runner) | the parameter rerun did not succeed with unchanged workflow code |
| C02 | FAIL | yes | yes | no | – | 62.7 | 0 | 0 | CLI subprocess (quote), coding execution (restricted runner) | Excel checks failed |
| C03 | PASS | yes | yes | yes | – | 43.3 | 0 | 0 | CLI subprocess (quote), coding execution (restricted runner) |  |
| C04 | PASS | yes | yes | yes | – | 108.1 | 1 | 0 | CLI subprocess (quote), coding execution (restricted runner) |  |
| X01 | FAIL | yes | yes | no | – | 104.4 | 0 | 0 | browser (SAP web), CLI subprocess (quote), coding execution (restricted runner), direct read of mock internals (bypass) | the Expense desktop app was never operated; conversation stopped: tool_loop_limit; scripts read mock internals instead of using the interface: .aep-run/run-004/script.py: expense_app |
| X02 | FAIL | yes | yes | no | – | 75.0 | 0 | 0 | browser (SAP web), CLI subprocess (quote), coding execution (restricted runner) | the Expense desktop app was never operated; conversation stopped: tool_loop_limit |
| X03 | BLOCKED | – | – | – | – |  |  | 0 |  | dependency: X01 — X01 did not pass, so there is no workflow to reuse |
| C04-force_exit2 | PASS | yes | yes | yes | – | 54.9 | 0 | 0 | CLI subprocess (quote), coding execution (restricted runner) |  |

Columns are independent: *Excel correct* judges only the workbook against the template and the expected answer; the interface requirement (browser / desktop GUI / CLI subprocess) decides BLOCKED separately. `–` means not applicable or not observable.

## 3. Failed checks per task

**W01**
- an Excel deliverable exists: `"no .xlsx in output/"`

**W02**
- an Excel deliverable exists: `"no .xlsx in output/"`
- W02: every order's detail page was opened: `["0045000114", "0045000119", "0045000125", "0045000129", "0045000132", "0045000136"]`

**W04**
- an Excel deliverable exists: `"no .xlsx in output/"`
- W04: the injected session expiry happened and the Agent signed in again: `{"user_agents": ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/154.0.0.0 Safari/537.36 Edg/154.0.0.0"], "browser": true, "logins": 1, "queries": 2, "details": ["00450001`

**D01**
- template: column widths kept: `["Details!A", "Details!C", "Details!D", "Details!E", "Details!F", "Details!G", "Details!H", "Details!I", "Details!J", "Details!K"]`
- rerun: an Excel deliverable exists: `"no .xlsx in output/"`

**D02**
- an Excel deliverable exists: `"no .xlsx in output/"`

**D03**
- an Excel deliverable exists: `"no .xlsx in output/"`

**D04**
- an Excel deliverable exists: `"no .xlsx in output/"`

**C01**
- rerun: an Excel deliverable exists: `"no .xlsx in output/"`

**C02**
- Summary: every expected group row (keys, amounts): `["TWD: amount 1835921.63, TWD 1835921.63", "USD: amount 10850.18, TWD 347205.76", "EUR: amount 25726.41, TWD 900424.35"]`

**X01**
- an Excel deliverable exists: `"no .xlsx in output/"`

**X02**
- an Excel deliverable exists: `"no .xlsx in output/"`
- X02: asked for the missing rules before acting: `"I need more information or a supported installed tool before I can continue."`

## 4. Limits of this run

- Isolation: the Agent's restricted runner runs as the same Windows account and can read files that account can read, so source data and answers under `operator/` were readable in principle. The run scans every script the Agent ran for references to mock internals (`bypass_signals` in each result); it cannot prove no bypass happened.
- Repair loops are derived from script exit codes (a failing run followed by another run).
- Formula cached values: openpyxl does not calculate formulas, so a missing cached value is recorded as undecided, and totals are verified independently from the detail rows.

