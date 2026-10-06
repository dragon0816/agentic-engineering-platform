# Handoff

Updated: 2026-10-06 (Asia/Taipei), by Claude Code

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

## Business workflow lab (2026-10-06)

- `benchmarks/business_workflow_lab/` (README has every command): SAP-like
  site (port 8810), Tk Expense desktop app, `quote_cli`, 4 templates, 15
  prompts, expected answers, grader with self-test, `operator/run_lab.py`.
- host.json `coding.workspace_roots` now also lists
  `benchmarks\business_workflow_lab\runs` (backup `host.json.bak-before-lab`);
  Agent Web was restarted for it (token in the newest `.scratch/agent-web-*.out.log`).
- `baseline-001` (AEP `2193cc3`): 16/16 BLOCKED; mocks 42/42 smoke checks.
  Findings and gap list L1-L7: `runs/baseline-001/findings.md`. Scripts read
  mock internals when the desktop app could not be operated.
- `smoke.py --browser` needs the system Python (Playwright is not in `.venv`).

## Approved but not done: D3, G3, G4

The owner approved (2026-10-06, "你提的1~3我覺得沒問題，可以執行"):
1. D3: conversation output cap 1024 → 8000 in `agent/gateway.py`
   (`_converse`, both `ModelRequest(max_output_tokens=1024)`), and report a
   provider `finish_reason == "length"` as its own failure (for example
   `model_output_truncated` in `models/openai_compatible.py` `_answer`).
2. G3: tool calls per turn 4 → 8 (the `len(evidence) >= 4` break, turn limit
   5 → 9 in `gateway.py` and `agent/backend_contracts.py`; update
   `tests/test_gateway.py::test_conversation_cannot_execute_an_invented_tool_and_stops`).
3. G4: install and run a drafted Workflow from chat (conversational authoring
   A4-A6 in `docs/phases/CONVERSATIONAL_AUTHORING.md`).
Claude Code's auto-mode permission check refused the edit to
`src/agent/gateway.py` as a change to a shared core module, so nothing was
changed. It needs the owner to allow that edit, or a person or another agent
to make it. After it: rerun Knowledge asking, W14 dry run and run-task, then
coding_v1 and the lab under new run IDs.

## Next recommended action

1. Owner: allow the D3/G3 edit (see above), then implement, verify, and run
   coding_v1 `fix-run-003` and lab `fix-001`.
2. Owner: decide the lab gaps L1-L3 (browser, desktop, process tool for the
   Agent, including whether the Agent may sign in with test credentials) and
   L7 (mock data isolation: another account or machine).
3. Owner: approve and install the practice Workflow, restart Agent Web, run
   it (customer C001), check the workbook and `http://127.0.0.1:8766/state.json`.
4. One real SOP chosen by the owner (its sites go into `web.allowed_origins`).
5. W9 business cards (Gateway vision approval and data-approval record first).
6. Coding C7 live run on the practice repository (runner ready).
