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

## Verification

HEAD `3a102e3` or later, with the repo `.venv`, after the subagent merges of 2026-10-07/08 (asset ownership step 2, test stability, knowledge_v1 `compare.py`):
- ruff passes.
- mypy (`src`) passes.
- Full pytest: **2318 passed, 6 skipped, 0 failed**. The skips are environment-dependent: symlink rights, no IPv6, an unbuilt lab mock, and the GUI test without `AEP_GUI_TESTS=1`.

These earlier failures are fixed and no longer excluded:
- the cp950 loader test;
- Defender rename locks, now retried briefly in `common/filesystem.publish_directory`;
- the SOP PDF wait;
- the Agent Web refused-POST reset.

`test_browser::test_a_signed_in_profile_is_what_carries_the_session` failed once on 2026-10-05; that is still open and unreproduced.

Use the repo `.venv`: the system Python has matplotlib 3.7.3 with numpy 2.2.6.

**Left over:**
- Headless Edge PID 7956 (child 13048) from the test-stability probe needs closing by the owner; the subagent's kill was denied.
- An unrelated headless Edge, PID 10352, has run since 2026-10-06 23:08.

## Next recommended action

1. When sample-002 finishes:
   - write its findings, comparing with sample-001 by route;
   - install Knowledge Skill 1.5.0 live and restart Agent Web;
   - run sample-003 on `72af226` or later.
   - Then run the full 1,100 (`--set all`, several hours, no GUI).
2. Agent Web restarts: wait until a benchmark run ends.
3. **While the owner is away:** run lab `fix-010`, all tasks. If the platform changed since `967249b`, also rerun coding_v1 on the same build.
4. After this stage:
   - asset ownership step 2 (`docs/phases/ASSET_OWNERSHIP.md`);
   - conversational authoring A1–A3, A7, A8.
