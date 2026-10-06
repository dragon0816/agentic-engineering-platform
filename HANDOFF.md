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

**coding_v1.**
- fix-run-006 passed 20/20 with validator 1.3.
- The build has changed since then: 20 calls per turn, the tool record, several calls per reply, Edge and desktop fixes, and coding 1.5.0. Re-verify with a new run ID once lab fix-005 is done.
- Run it with:

    .venv\Scripts\python benchmarks\coding_v1un.py --run-id <new> --tasks all

**Lab.** `benchmarks/business_workflow_lab/`, grader 1.2.
- Run it with:

    .venv\Scripts\python benchmarksusiness_workflow_lab\operatorun_lab.py --run-id <new> --tasks all

- Mocks: run `python ...\operator\smoke.py --browser` with the system Python.
- Results so far: fix-001 4/16, fix-002 5/16, fix-003 invalid, fix-004 9/16, fix-005 running. Each run's `findings.md` lists its causes and the fixes that followed.
- The operator presses approval buttons, replies 繼續 at most 3 times when a turn stops at the budget, and asks for the spec's reruns. Each of these is recorded as an intervention.

**Live host.** The changes below each have a `.bak-*` backup next to the file.
- host.json:
  - `web.allowed_origins` has `http://127.0.0.1:8810`;
  - `desktop.applications` registers `expense`, pointing at `...\expense_desktop_mockin\ExpenseApp.exe`;
  - `coding.workspace_roots` includes the lab's runs folder.
- grants.json has grants for `browser/operate` and `desktop/operate`.
- Skill `engineering/coding@1.5.0` is installed.
- The coding runner Python has `tzdata`.
- Agent Web runs from `src` with the repo `.venv`. Restarting it with `Stop-Process` leaves its Edge running. The next start now recovers from that, but closing Agent Web normally is cleaner.

**Platform pieces.** The decisions are in `docs/DECISIONS.md`, 2026-10-06 and 2026-10-07:
- `agent.backend_contracts` sets the limits: 8000 tokens and 20 calls per turn.
- `Gateway.host_tools`; several calls in one reply run in order.
- `host_runtime/chat_authoring.py`: G4, plus `approval_text`.
- `host_runtime/bridge_tools.py`: `browser__operate` and `desktop__operate`, which list the registered apps.
- `host_runtime/turn_summary.py`: the tool record.
- Agent Web `/api/approvals` and Telegram approval buttons.
- `capabilities/browser_session` (leftover recovery) and `capabilities/desktop_session` (placeholders, `clear_dialogs`); `integrations/desktop(.py, _uia.cs)`.
- run-python `AEP_WORKFLOW_PARAMS` and child processes.

## Verification

ruff and mypy (`src`) pass. In the full pytest, only these fail:
- `test_local_developer_environment` (cp950), which is excluded;
- `test_knowledge_stage`, `test_browser::test_the_whole_flow_the_owner_described` and `test_sop_practice::test_the_sop_pdf_carries_the_routine_as_text`, which fail only now and then inside the full run under load and pass alone.

The last full run: 2235 passed.

Live checks after every Gateway change, all unchanged: Knowledge direct and in chat (no coding or authoring tool used), the W14 dry run and `run-task`.

## Next recommended action

1. Read lab fix-005's results and fix what they show, then rerun the lab and coding_v1 on the same build under new run IDs.
2. Conversational authoring A1-A3, A7, A8.
3. The practice SOP Workflow install, a real SOP, W9 business cards, coding C7 (unchanged).
