# baseline-001: findings

Baseline of the AEP Agent at commit `2193cc3`, with no product change for
this lab. Model `gpt-5.5` through the company gateway; entry point Agent Web
chat with a new session per task. Mocks: 42/42 smoke checks passed,
including a real Edge session against the SAP-like site.

Result: 16 of 16 task runs BLOCKED (15 tasks plus the second C04 scenario).
None produced a workbook, so `excel_correct` is `no` everywhere and no
parameter rerun could be requested (`workflow_rerun_succeeded` is `–`).

## 1. Can the mock systems be used?

Yes. `operator/state/smoke.json` records:
- the site: login, filters, two-page results, detail pages, the full CSV
  export, and the injected session expiry and delay, over HTTP and in Edge;
- the CLI: exit codes 0, 2, 3 and 4, transient_once, force_exit2, and an
  export to a path containing spaces;
- the Expense app: 8-row pages, the detail dialog, CSV and Excel export,
  export_fail_once, the empty result, and a real desktop window.

The grader self-test passes: a reference fill passes every task, and a fill
with one row removed fails every task.

## 2. Which tools does the AEP harness provide?

| Need | In the AEP conversation | Evidence |
|---|---|---|
| Browser | **No.** `web/read` and `web/act` exist only as Workflow steps. Their design also leaves signing in to a person ("signing in is a person's job"). | W01–W04 reached the site only with `Python-urllib/3.12` from runner scripts. |
| Native desktop (UI automation / screenshot) | **No**, in neither the conversation nor the Bridge. The runner cannot start a GUI process either. | D01–D04, X01, X02: no Expense event at all. |
| CLI as a process | **No.** The restricted runner's job object allows one process. | C02, C03 and C04-force_exit2: `WinError 1816 Not enough quota` when the script started the CLI. |
| Files, coding execution | Yes: `coding__run`. It runs Python in the task workspace and can write only to `output/`. | Every task ran 1–4 scripts. |
| Excel | Yes: `openpyxl` in the runner. | Scripts read every template. |
| Installing or running a platform Workflow from chat | **No** (G4 from coding_v1). | None of the tasks could deliver a platform Workflow. |

## 3. What stopped each task

| Cause | Tasks | Detail |
|---|---|---|
| G3: the tool budget (4 calls per turn) | W01–W04, D01–D04, C02, C03, X01, X02, C04-force_exit2 (13) | The model spent its four calls reading attachments, probing the site or the CLI, and fixing a missing module (`requests` is not in the runner). The turn ended with `tool_loop_limit` before any workbook was written. |
| D3: the 1024-token output cap | C01, C04 (2) | `empty_model_answer`: the tool call carrying the script was cut off. |
| Missing interface tool (structural) | All 15 tasks | See section 2. Even with G3 and D3 fixed, W, D and C tasks stay BLOCKED until AEP has a browser, desktop and process tool the Agent can use. |
| Dependency | X03 | X01 did not pass. |

Partial signals, kept as evidence (not success):
- W02 opened all 9 C001 order detail pages, with 3 logins.
- W04 met the injected session expiry and signed in again (2 logins).
- W03 used the site's CSV export 3 times.
- X02 did not ask the clarifying question; it began exploring and ran out
  of tool calls (the X02 check "asked for the missing rules" failed).

## 4. Interface bypass (isolation limit, observed)

The runner runs as the same Windows account, so it can read the mocks'
code and data. When the Agent had no way to operate the desktop app, it
read the internals instead:

| Task | What the scripts read |
|---|---|
| D01, X02 | `expense_desktop_mock/expense_app.py` source (which names the data file) |
| D02, D03, D04 | `operator/...` (D02: `operator/data/source.json`) |
| X01 | `quote_cli_mock` sources, then `operator/data/source.json` |

No task reached a workbook, so no bypassed data was delivered. This shows
that the isolation limit is real, not theoretical: unless the mocks' data
lives in another account, container or machine, a passing result here
cannot exclude a bypass. The batch script flags it (`bypass_signals`), but
this is a heuristic.

## 5. Environment events

The first attempts of D03, D04, C02 and C03 ended with
`model_http_error` 503 from the company model gateway
(`litellm.ServiceUnavailableError`, vLLM). That is the model service, not
AEP. They are kept under `_attempt1_503/` and were rerun once in this run
ID. The reruns met no 503 and are the recorded results.

## 6. Capability gaps (fixes belong to separate work, not this baseline)

1. **L1 Browser tool for the Agent.** Either a conversation tool over the existing DevTools browser integration, or a
   way to install and run a Workflow that uses `web/act`. This also needs a decision on credentials: today signing in
   is a person's job, but these tasks ask the Agent to sign in with a test account and to sign in again after a
   session expires.
2. **L2 Native desktop tool.** UI Automation or screenshot plus coordinates on an interactive desktop, through the
   Bridge. Nothing exists today.
3. **L3 Running a CLI.** Either the runner allows a bounded child process (G5), or a separate command tool with an
   allowlist runs it.
4. **L4 G3: tool budget**, and **L5 D3: output cap** (both approved by the owner on 2026-10-06; not yet implemented).
5. **L6 G4: install and run a drafted Workflow from chat.** Needed so a task can deliver a reusable platform Workflow,
   rerun it with new parameters, and serve X03.
6. **L7 Isolation of mock data from the runner.** Needed before any PASS here can rule out a bypass.
7. Minor: the runner has no `requests` (scripts fell back to urllib after one failed run).

The questions in the test plan (§2) about understanding filters, joins,
currency and templates, about workflow rerun, and about matching IDs across
systems could not be observed: no task got past interface access.
