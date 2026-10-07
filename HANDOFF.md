# Handoff

Updated: 2026-10-07 (Asia/Taipei), by Claude Code

## Repository and runtime state

- Branch `main`, all work committed locally, nothing pushed.
- Live Agent Web: `aep-host web --config %LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0\host.json --port 53583 --open --schedules`
  started from the repo `.venv` (editable install), logs `.scratch/agent-web-*.log`.
  Start it with the user environment refreshed (AEP_* and LITELLM_MASTER_KEY),
  or credentials set after the shell started are missing. The token changes on
  every restart. A restart right after stopping can hit WinError 10013 on the
  port for a moment; start again.
- Telegram bot is enabled with 1 allowed sender. Free text talks to the Agent;
  each request shows a status message edited with elapsed time and skills used.
- Workflow settings are shown with the Workflow under Capabilities (no longer
  on the Settings page).
- Installed live: W14 (`engineering/rs-ncc-improvement-plan`), W11 as one
  Workflow `engineering/sde-weekly-report`, and now `engineering/coding-change`
  with Skill `engineering/coding` (see below).
- Knowledge: host.json binds `engineering/rs-knowledge@1.0.1` (purpose
  written, boundaries empty); chat offers it as `knowledge__rs-knowledge`.
  Rollback: set the binding back to 1.0.0 and restart.
- JEV shadow mode is on (`decision_accelerator`), needs the SSH tunnel
  `ssh -N -p 2222 -L 18000:127.0.0.1:8000 openlab@172.25.228.141`; log
  `workspace\jev-shadow.jsonl`, replay `python -m evaluation.jev_shadow_report <log>`.
- GitLab token (`AEP_GITLAB_TOKEN`, mapped as `gitlab_token`) expires
  2026-10-06; the owner was advised to create a `read_api` token with a longer
  expiry before W12.

## Current work: coding on the Bridge

Plan and owner decisions: `docs/phases/CODING_ON_BRIDGE.md`; decision record
in `docs/DECISIONS.md` (2026-10-06). Done C1-C6:

- `harness/restricted_runner.py`: low-integrity process, Job object (one
  process, memory cap, kill on close), allowlisted environment, timeout.
  Works without admin rights. Refuses a venv `python.exe` (it starts a child).
- `harness/network_block.py`: checks an outbound firewall block rule on the
  runner interpreter (before every run) and a live probe (for install/doctor).
- `harness/git_worktree.py` + `harness/pytest_commands.py`: one detached
  worktree per run under `workspace\coding-runs\<run>`; `pytest-new` (the named
  golden tests) and `pytest-suite` (whole test folder) judged by JUnit XML.
- `harness/model_author.py`: Gateway model writes whole files as JSON; scope
  (file, commands) comes from the request, never from the model.
- `capabilities/coding_change/`: `coding/change@1.0.0`, Workflow
  `engineering/coding-change` (fields: repository, requirement, file, tests,
  max_repairs), Skill alias `coding`. Never commits; a failed run is a refusal
  with evidence in `<run>\result.json`.
- Live install: host.json `coding` section (backup
  `host.json.bak-*-before-coding`), runner
  `%LOCALAPPDATA%\AgenticEngineeringPlatform\coding-runner\cpython-3.12.14-windows-x86_64-none\python.exe`
  with pytest 9.1.1, practice repo `C:\Users\Chi_L\Documents\aep-coding-practice`
  (writable `src/practice/*.py`), grant for `leo.chi` (backup
  `grants.json.bak-*-before-coding`).

The firewall rule exists (created by the owner 2026-10-06) and blocks
direct egress (verified live). Loopback, including the company Zscaler
proxy, is reachable and allowed by the owner. Live `inspect_coding`: passed.
Agent Web was restarted with the fixed rule check (`8c337f0`).

## Verification (this commit series)

Ruff and mypy (`src`) pass. Full pytest before C5's export-list update:
2153 passed, 3 failed: `test_local_developer_environment` (cp950 stderr
decoding, fails the same at the earlier HEAD), `test_agent_web` header test
(flaky, passes on rerun) and the export list (fixed). All coding tests pass
(`test_restricted_runner.py`, `test_coding_worktree_pytest.py`,
`test_coding_model_author.py`, `test_coding_change_capability.py`, plus
E2E-01/03/04). Live doctor `inspect_coding` reports only the missing rule.

## SOP to Workflow state (2026-10-06)

- W1-W7 done and committed; W8 done up to preview (see docs/TASKS.md).
- host.json has `web` (allowed origin `http://127.0.0.1:8766`, backup
  `host.json.bak-20261006-174008-before-web`). That origin is the practice
  site, started with `python -m evaluation.sop_practice serve --port 8766`
  (run from `src` with the repo venv); it does not survive a reboot.
- Practice files: `C:\Users\Chi_L\Documents\aep-sop-practice` (workbook and
  SOP PDF). Authoring session `sop-20261006-094136-07236f` is `previewed`;
  the owner installs it from Agent Web (Capabilities, "Create a Workflow from
  an SOP"), then restarts Agent Web.

## Current work: coding_v1 and the business workflow lab (2026-10-07)

**Phase gate (owner):** this stage is done only when the lab tasks pass *and* coding_v1 passes all 20 on the same build.

**Build under test:** `4becd6b`.
- It contains the refusal location for desktop steps and redaction of credential-shaped text in stored conversation messages.
- Agent Web was restarted on it at 13:30. Its logs are `.scratch/agent-web-20261007-133033.*`.

### Owner rule (2026-10-07): GUI tests run only while the owner is away

Tests that drive Edge or the Expense desktop app open windows and can take focus from the owner's work. Run them only when the owner is not using the computer, such as evenings or after the owner says they have left.

| Can run during working hours (no GUI) | Only while the owner is away (GUI) |
|---|---|
| coding_v1, all 20 tasks | Lab W01–W04 (Edge) |
| Lab C02, C03, C04, C04 exit-2 (CLI only) | Lab D01–D04 (Expense desktop app) |
| pytest with `-m "not live"` | Lab C01 (desktop + CLI) |
| | Lab X01–X03 (all three systems) |
| | The live desktop pytest test (`-m live`) |
| | `smoke.py --browser` |

Run only the CLI tasks with `--tasks C02,C03,C04` (comma-separated IDs). Both `all` and the default `smoke` may include GUI tasks.

**Stopped at the owner's request:** lab `fix-009` (13:5x). Finished before the stop:
- W01–W04: PASS. W01's rerun with unchanged code passed for the first time.
- D01: FAIL (rerun).

D02's folder is incomplete. Details are in `runs/fix-009/findings.md`. The Expense app and the lab's Edge were closed. The SAP mock web server (`sap_mock/server.py --port 8810`) still runs headless; it does not use the screen.

**Next GUI run:** a new run ID (`fix-010`), all tasks, on the same build. Check first:
- Agent Web is up: port 53583 returns 401 without the token.
- No ExpenseApp process is left over.

**Commands** (repo root, repo `.venv`):

    .venv\Scripts\python benchmarks\coding_v1\run.py --run-id <new> --tasks all
    .venv\Scripts\python benchmarks\business_workflow_lab\operator\run_lab.py --run-id <new> --tasks all

- Mock smoke checks: `python benchmarks\business_workflow_lab\operator\smoke.py --browser` (GUI).
- Set `PYTHONIOENCODING=utf-8` when output goes to a cp950 console.
- Run one benchmark at a time, because both use the same Agent Web.
- When a script waits for a runner, wait on its PID. A `pgrep -f` on the runner's name matches the waiting shell's own command line.

**Results so far.** Each run folder holds a `findings.md`.

| Benchmark | Run | Result | Note |
|---|---|---|---|
| coding_v1 | fix-run-006 / 007 | 20/20, 20/20 | |
| coding_v1 | fix-run-008 / 009 | 18/20, 19/20 | T14 validator (since fixed); T08 Agent variance |
| coding_v1 | fix-run-010 | interrupted at T09 | Agent Web defect, fixed in `4becd6b` |
| coding_v1 | **fix-run-011** | **20/20** | build `4becd6b`: the coding_v1 half of the gate is met |
| Lab | fix-005 / 006 / 007 | 11, 13, 12 of 16 | |
| Lab | fix-008 | 12/16 | X01 passes for the first time |
| Lab | fix-009 | stopped | W01–W04 PASS, D01 FAIL, the rest not run |

**Open lab gaps:**
- **Reruns where the Agent revises the Workflow instead of reusing it:** fix-008 W01, fix-009 D01. The Agent fixes the Workflow until a run succeeds, then changes it once more before the rerun, so "same code" fails.
- **X02:** an overdue invoice dated before the period was missed (fix-008).
- **X03:** X01's Workflow fixes the output name and filters by customer, so the Agent asked instead of running (fix-008).

The operator presses approvals, replies 繼續 at most 3 times, and asks for the spec's reruns. Each of these is recorded as an intervention. Expected answers are never changed; grader and operator changes are versioned (grader 1.2).

**Live host changes** (a `.bak-*` backup sits next to each changed file):
- host.json:
  - `web.allowed_origins` has `http://127.0.0.1:8810`;
  - `desktop.applications.expense` points at `...\expense_desktop_mock\bin\ExpenseApp.exe`;
  - `coding.workspace_roots` includes the lab's runs folder.
- grants.json has grants for `browser/operate` and `desktop/operate`.
- Skill `engineering/coding@1.6.0` is installed.
- The coding runner Python has `tzdata`.

**Restarting Agent Web:**
- Refresh the user environment variables (`AEP_*`, `LITELLM_MASTER_KEY`) first.
- `Stop-Process` leaves Edge running. The next start recovers from that (`close_leftover`).

**Platform pieces.** Decisions are in `docs/DECISIONS.md` under 2026-10-06 and 2026-10-07:
- `agent.backend_contracts` sets the limits: 8000 tokens and 20 calls per turn.
- `Gateway.host_tools`; several calls in one reply run in order; a truncated reply is retried twice.
- `host_runtime/chat_authoring.py` provides G4 and `approval_text`.
- `bridge_tools.py` provides `browser__operate` and `desktop__operate`.
- `turn_summary.py` provides the tool record.
- Approvals: Agent Web `/api/approvals` and Telegram buttons.
- Bridge failures: `invalid_input` names its fields, and `CapabilityRefused.where` names the place in the request.
- `ConversationMessage` redacts credential-shaped text instead of refusing it.

## Verification

Build `4becd6b`:
- ruff passes.
- mypy (`src`) passes with the repo `.venv`.
- Full pytest with the repo `.venv` (`-m "not live"`): 2259 passed, 1 failed. The failure is `test_local_developer_environment`, which fails on cp950 stderr decoding, also fails on a clean tree, and is excluded.

Use the repo `.venv`. The system Python has matplotlib 3.7.3 with numpy 2.2.6, which breaks the chart tests.

## Next recommended action

1. **While the owner is away:** run lab `fix-010`, all tasks, on build `4becd6b`, then record its findings.
2. During working hours, work that needs no GUI is fine, such as code changes for the open lab gaps and coding_v1 reruns.
3. For the rerun gap, consider whether the draft guide or the coding Skill should say: once a Workflow run has succeeded and the result was delivered, a rerun uses that installed version unchanged. Discuss with the owner before changing the harness.
4. After this stage: conversational authoring A1–A3, A7, A8.
