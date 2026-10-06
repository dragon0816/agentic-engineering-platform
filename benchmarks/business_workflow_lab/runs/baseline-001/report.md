# business_workflow_lab — baseline-001

Run at 2026-10-06T21:10:41, AEP commit `2193cc3`, model `gpt-5.5`, Agent Web chat (Gateway conversation). Synthetic data seed 20261006; source manifest `34feccc65ca3…`.

## 1. Mock systems

Smoke checks: 42/42 passed (`operator/smoke.py`, recorded in `operator/state/smoke.json`).

## 2. Task results

Status counts: BLOCKED 16

| Task | Status | Code generated | Executed | Excel correct | Workflow rerun | Seconds | Repair loops | Interventions | Interfaces | Blocked layer / reason |
|---|---|---|---|---|---|---|---|---|---|---|
| W01 | BLOCKED | yes | yes | no | – | 27.7 | 1 | 0 | HTTP client script (SAP web, no browser), coding execution (restricted runner) | harness: no browser tool in the AEP conversation (web/act exists only as a Workflow step) — scripts reached the site with an HTTP client; conversation stopped: tool_loop_limit |
| W02 | BLOCKED | yes | yes | no | – | 34.2 | 0 | 0 | HTTP client script (SAP web, no browser), coding execution (restricted runner) | harness: no browser tool in the AEP conversation (web/act exists only as a Workflow step) — scripts reached the site with an HTTP client; conversation stopped: tool_loop_limit |
| W03 | BLOCKED | yes | yes | no | – | 34.1 | 1 | 0 | HTTP client script (SAP web, no browser), coding execution (restricted runner) | harness: no browser tool in the AEP conversation (web/act exists only as a Workflow step) — scripts reached the site with an HTTP client; conversation stopped: tool_loop_limit |
| W04 | BLOCKED | yes | yes | no | – | 31.4 | 1 | 0 | HTTP client script (SAP web, no browser), coding execution (restricted runner) | harness: no browser tool in the AEP conversation (web/act exists only as a Workflow step) — scripts reached the site with an HTTP client; conversation stopped: tool_loop_limit |
| D01 | BLOCKED | yes | yes | no | – | 29.9 | 0 | 0 | coding execution (restricted runner), direct read of mock internals (bypass) | harness: no native desktop (GUI automation) tool in the AEP conversation or Bridge — the Expense desktop app was never operated; conversation stopped: tool_loop_limit; scripts read mock internals instead of using the interface: .aep-run/run-003/script.py: expense_app; .aep-run/run-004/script.py: expense_app |
| D02 | BLOCKED | yes | yes | no | – | 34.7 | 0 | 0 | coding execution (restricted runner), direct read of mock internals (bypass) | harness: no native desktop (GUI automation) tool in the AEP conversation or Bridge — the Expense desktop app was never operated; conversation stopped: tool_loop_limit; scripts read mock internals instead of using the interface: .aep-run/run-003/script.py: business_workflow_lab\operator; .aep-run/run-004/script.py: business_workflow_lab\operator |
| D03 | BLOCKED | yes | yes | no | – | 35.9 | 0 | 0 | coding execution (restricted runner), direct read of mock internals (bypass) | harness: no native desktop (GUI automation) tool in the AEP conversation or Bridge — the Expense desktop app was never operated; conversation stopped: tool_loop_limit; scripts read mock internals instead of using the interface: .aep-run/run-003/script.py: expense_app; .aep-run/run-004/script.py: business_workflow_lab\operator |
| D04 | BLOCKED | yes | yes | no | – | 38.1 | 0 | 0 | coding execution (restricted runner), direct read of mock internals (bypass) | harness: no native desktop (GUI automation) tool in the AEP conversation or Bridge — the Expense desktop app was never operated; conversation stopped: tool_loop_limit; scripts read mock internals instead of using the interface: .aep-run/run-002/script.py: expense_app; .aep-run/run-003/script.py: business_workflow_lab\operator |
| C01 | BLOCKED | yes | yes | no | – | 20.5 | 0 | 0 | coding execution (restricted runner) | harness: the conversation stopped before the CLI was tried (empty_model_answer) — the quote CLI was never run as a process; conversation stopped: empty_model_answer |
| C02 | BLOCKED | yes | yes | no | – | 31.8 | 1 | 0 | coding execution (restricted runner) | runner: the restricted runner refused to start a subprocess (one-process job) — the quote CLI was never run as a process; conversation stopped: tool_loop_limit |
| C03 | BLOCKED | yes | yes | no | – | 31.9 | 1 | 0 | coding execution (restricted runner) | runner: the restricted runner refused to start a subprocess (one-process job) — the quote CLI was never run as a process; conversation stopped: tool_loop_limit |
| C04 | BLOCKED | yes | yes | no | – | 44.0 | 0 | 0 | coding execution (restricted runner) | harness: the conversation stopped before the CLI was tried (empty_model_answer) — the quote CLI was never run as a process; conversation stopped: empty_model_answer |
| X01 | BLOCKED | yes | yes | no | – | 33.1 | 1 | 0 | coding execution (restricted runner), direct read of mock internals (bypass) | harness: no native desktop (GUI automation) tool in the AEP conversation or Bridge — the Expense desktop app was never operated; conversation stopped: tool_loop_limit; scripts read mock internals instead of using the interface: .aep-run/run-003/script.py: expense_app; .aep-run/run-004/script.py: source.json |
| X02 | BLOCKED | yes | yes | no | – | 31.2 | 2 | 0 | coding execution (restricted runner), direct read of mock internals (bypass) | harness: no native desktop (GUI automation) tool in the AEP conversation or Bridge — the Expense desktop app was never operated; conversation stopped: tool_loop_limit; scripts read mock internals instead of using the interface: .aep-run/run-004/script.py: expense_app |
| X03 | BLOCKED | – | – | – | – |  |  | 0 |  | dependency: X01 — X01 did not pass, so there is no workflow to reuse |
| C04-force_exit2 | BLOCKED | yes | yes | no | – | 32.0 | 1 | 0 | coding execution (restricted runner) | runner: the restricted runner refused to start a subprocess (one-process job) — the quote CLI was never run as a process; conversation stopped: tool_loop_limit |

Columns are independent: *Excel correct* judges only the workbook against the template and the expected answer; the interface requirement (browser / desktop GUI / CLI subprocess) decides BLOCKED separately. `–` means not applicable or not observable.

## 3. Failed checks per task

**W01**
- an Excel deliverable exists: `"no .xlsx in output/"`

**W02**
- an Excel deliverable exists: `"no .xlsx in output/"`

**W03**
- an Excel deliverable exists: `"no .xlsx in output/"`

**W04**
- an Excel deliverable exists: `"no .xlsx in output/"`

**D01**
- an Excel deliverable exists: `"no .xlsx in output/"`

**D02**
- an Excel deliverable exists: `"no .xlsx in output/"`

**D03**
- an Excel deliverable exists: `"no .xlsx in output/"`

**D04**
- an Excel deliverable exists: `"no .xlsx in output/"`

**C01**
- an Excel deliverable exists: `"no .xlsx in output/"`

**C02**
- an Excel deliverable exists: `"no .xlsx in output/"`

**C03**
- an Excel deliverable exists: `"no .xlsx in output/"`

**C04**
- an Excel deliverable exists: `"no .xlsx in output/"`

**X01**
- an Excel deliverable exists: `"no .xlsx in output/"`

**X02**
- an Excel deliverable exists: `"no .xlsx in output/"`
- X02: asked for the missing rules before acting: `"I need more information or a supported installed tool before I can continue."`

**C04-force_exit2**
- exit 2: the reply reports the CLI error: `"I need more information or a supported installed tool before I can continue."`

## 4. Limits of this run

- Isolation: the Agent's restricted runner runs as the same Windows account and can read files that account can read, so source data and answers under `operator/` were readable in principle. The run scans every script the Agent ran for references to mock internals (`bypass_signals` in each result); it cannot prove no bypass happened.
- Repair loops are derived from script exit codes (a failing run followed by another run).
- Formula cached values: openpyxl does not calculate formulas, so a missing cached value is recorded as undecided, and totals are verified independently from the detail rows.

