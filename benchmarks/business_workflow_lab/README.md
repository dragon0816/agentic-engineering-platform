# business_workflow_lab

A local test bench for one question: can the AEP coding Agent build and run
the business workflows colleagues do by hand: query an SAP-like web system,
a native desktop Expense app and a CLI quote system, then fill company Excel
templates?

Everything here is synthetic (seed 20261006, dates 2026-08-01 to
2026-10-31). The web app only resembles an enterprise query system; it is
not a copy of SAP's interface, data model or behaviour, and passing here
does not prove anything about the real SAP, expense or quote tools.

Nothing under this folder changes the AEP product runtime.

## Layout

| Path | What | Agent may see |
|---|---|---|
| `sap_mock/server.py` | SAP-like query site (login, Customers / Sales Orders / Invoices, filters, 10-row pages, detail, CSV export) | URL and manual only |
| `expense_desktop_mock/expense_app.py` | Native Tk desktop Expense app (8-row pages, detail dialog, Save As export) | launch command and manual only |
| `quote_cli_mock/` | `quote_cli` (`quote_cli.cmd` or `run_quote_cli.py`) | command and `--help` |
| `templates/` | 4 Excel templates, their generator, `fx_rates.csv` (fixed test rates) | yes (copied per task) |
| `manuals/` | Operator-written usage notes, copied into each task's `input/` | yes |
| `prompts/` | The 15 natural-language requests, verbatim | yes (one per task) |
| `operator/` | Synthetic data, expected answers, checks, reset, smoke and batch scripts, fault and event state | **no** |
| `runs/<run_id>/` | Per-run results: `results.json`, `report.md`, one folder per task | evidence |

Isolation limit: the Agent's restricted runner runs as the same Windows
account and can read anything that account can read, including
`operator/`. The batch script scans every script the Agent ran for
references to mock internals and records `bypass_signals`. It cannot prove
that no bypass happened.

## Setup

Python 3.12 with `openpyxl` (already in the repository's `.venv`). The
browser check in the smoke test uses Playwright with the installed Edge
(`--browser`). Tkinter ships with CPython.

```powershell
cd C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform
.venv\Scripts\python benchmarks\business_workflow_lab\operator\data\generate.py      # source.json (fixed)
.venv\Scripts\python benchmarks\business_workflow_lab\templates\build_templates.py   # 4 templates + fx_rates.csv
.venv\Scripts\python benchmarks\business_workflow_lab\operator\smoke.py --browser    # 38+ checks
.venv\Scripts\python benchmarks\business_workflow_lab\operator\selftest.py           # grader self-test
```

`source.json` and the templates are committed. Regenerating gives the same
data; the `.xlsx` bytes differ by their timestamps only.

## Starting and stopping the mocks

| System | Start | Stop | Port / path |
|---|---|---|---|
| SAP-like site | `python benchmarks\business_workflow_lab\sap_mock\server.py --port 8810` | Ctrl+C | `http://127.0.0.1:8810/`, localhost only; `--host` sets another test address |
| Expense app | `python benchmarks\business_workflow_lab\expense_desktop_mock\expense_app.py` | close the window | needs an interactive Windows desktop |
| Quote CLI | `benchmarks\business_workflow_lab\quote_cli_mock\quote_cli.cmd --help` | n/a | `QUOTE_CLI_DATA` may point at another data file |

Test account for the site: `lab.analyst` / `Lab#2026` (synthetic, local only).

## Fault scenarios and reset

```powershell
python benchmarks\business_workflow_lab\operator\reset.py                          # all normal
python benchmarks\business_workflow_lab\operator\reset.py --sap expire_session_once
python benchmarks\business_workflow_lab\operator\reset.py --sap delay_once
python benchmarks\business_workflow_lab\operator\reset.py --expense export_fail_once
python benchmarks\business_workflow_lab\operator\reset.py --quote transient_once
python benchmarks\business_workflow_lab\operator\reset.py --quote force_exit2
```

The mocks read their mode from `operator/state/<system>_fault.json` on each
request, so no restart is needed. Each mock appends its events (logins,
queries, pages, details, exports, injected faults; the SAP log also has the
client's User-Agent) to `operator/state/<system>_events.jsonl`.

## Running the tasks against AEP

The tasks go through the existing Agent entry, Agent Web chat
(`POST /api/conversations`, `POST /api/conversations/turn`), with a new
session per task. Prerequisites:

1. Agent Web is running from this repository and its start line is in
   `.scratch\agent-web-*.out.log` (the script reads the URL and token there).
2. `coding.workspace_roots` in the host's `host.json` lists
   `...\benchmarks\business_workflow_lab\runs`, so `coding__run` may use the
   task workspaces.

```powershell
# entry check: W01, D01, C01
.venv\Scripts\python benchmarks\business_workflow_lab\operator\run_lab.py --run-id baseline-001 --tasks smoke
# all 15 (recorded tasks are skipped unless --force)
.venv\Scripts\python benchmarks\business_workflow_lab\operator\run_lab.py --run-id baseline-001 --tasks all
# some tasks
.venv\Scripts\python benchmarks\business_workflow_lab\operator\run_lab.py --run-id baseline-001 --tasks W02,W03
# rebuild report.md from results.json
.venv\Scripts\python benchmarks\business_workflow_lab\operator\run_lab.py --run-id baseline-001 --report-only
```

The operator script:

- resets the mocks to the task's scenario (W04 `expire_session_once`, D04 `export_fail_once`, C04 `transient_once`,
  plus a second C04 session with `force_exit2`);
- builds `runs/<run_id>/<task>/workspace/input` with only that task's template, `fx_rates.csv` and manuals;
- sends the prompt plus a short environment note (date 2026-10-06 Asia/Taipei, the workspace path, the attachments,
  and where to put deliverables);
- answers X02's fixed clarification only if the Agent actually asks;
- for W01, D01, C01 and X01, asks in the same session for a rerun with the second parameter set, then compares the
  hashes of `output/workflow/` before and after;
- runs X03 only when X01 passed, with X01's `output/workflow/` as an attachment;
- grades the workbook and records every result.

Time limits: 15 minutes per task, 30 for X01 to X03.

## What a result means

Each task records four separate flags: `code_generated`, `execution_succeeded`, `excel_correct` and
`workflow_rerun_succeeded`. Status:

- **PASS**: the required interface was really used (a real browser for the site, the desktop GUI, the CLI as a
  process), the workbook passed every check, and the rerun worked where one is required.
- **BLOCKED**: a needed tool does not exist on the AEP side. The `blocked_layer` field names it (for example, no
  native desktop tool, or the runner cannot start a subprocess). `excel_correct` is still reported.
- **FAIL**: the tools existed but the result was wrong or missing.
- **TIMEOUT**, **NOT_RUN**.

Workbook checks: sheet names and order, the fixed Report cells, the merge and footer, the Instructions sheet,
the row-4 column names, freeze panes, auto-filter, column widths, the SUM formulas kept and extended to the
data, the ID set (no duplicates, IDs stored as text), field values, TWD totals recomputed from the detail rows,
the summary groups, and the task-specific rules (Overdue, NeedsReview, Exceptions, findings.md). A formula
without a cached value is recorded as undecided, never as a pass or a failure.
