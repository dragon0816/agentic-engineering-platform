# Handoff

Updated: 2026-10-09 (Asia/Taipei), by Claude Code

## Where the current work stopped (2026-10-09)

knowledge_v1 is measured against Claude Code reference answers, and the
Knowledge retrieval was changed after the first comparison.

- References: `benchmarks/knowledge_v1/references/` (36 core questions,
  283 verified key points). Do not regenerate them without the owner (about
  $49 of Claude Code usage). Grade a run with `reference_grade.py --run-id <id>`.
- `runs/core-001` (Skill 1.6.0) and `runs/core-002` (Skill 1.7.0,
  `bilingual_retrieval`); compare them in `runs/core-002/review.zh-TW.md`.
  On the 22 answerable questions: PASS 13 -> 16, false "insufficient" 6 -> 0,
  coverage 0.27 -> 0.32. FAIL rose 3 -> 6, mostly answers stretching beyond
  their passages.
- Live: Knowledge Skill `company-agent/knowledge-query@1.7.0` installed in
  the workspace (1.6.0 moved to `disabled/`); Agent Web restarted on f729827.
- The company LLM returns short bursts of 503 (vLLM unavailable behind
  LiteLLM): 14 questions in sample-004, and about 20:54-20:56 Taipei time
  during the first core-002 attempt, which was discarded and re-run.
  Telemetry timestamps are UTC.
- The JEV/Laya tunnel host 172.25.228.141 is unreachable from this PC's new
  network (owner, 2026-10-09).
- Post-unification benchmarks: coding_v1 fix-run-016 20/20, lab fix-012 13
  pass (X02/X03 fail), knowledge sample-004 (grader 1.3).

- 2026-10-10: Knowledge Skill 1.8.0 installed (1.7.0 in `disabled/`), only
  `answer_guidance` changed. `runs/core-003`: on the 22 answerable questions
  PASS 18, FAIL 2, coverage 0.28; see `runs/core-003/review.zh-TW.md`.

- 2026-10-10: multi-round retrieval (13354e4) and Knowledge Skill 1.9.0
  (`retrieval_rounds: 2`; 1.8.0 in `disabled/`) are live. `runs/core-004`:
  retrieval clearly better (reference files offered 22% -> 41%), answer
  coverage flat (0.30), contradictions down, median latency +60 s.

Owner decision (2026-10-10): keep 1.9.0, then "try improving synthesis,
roll back if worse". Knowledge Skill 1.10.0 is now live (1.9.0 in
`disabled/`), adding the evidence budget (8 sections/page, 64 sections,
80,000 chars) and a "cover every part" guidance line. `runs/core-005`:
answerable coverage 0.30 -> 0.40, FAIL and contradictions about flat, overreach
items 35 -> 63. Kept under the owner's rule. To roll back, move 1.9.0 back from
`disabled/`, move 1.10.0 out, and restart Agent Web.

Knowledge state (2026-10-10, latest): Skill 1.10.0 is live. A no-support retry check
plus Skill 1.11.0 was tried in `runs/core-006`, came out worse and was rolled back
(code revert ca110b0). The coverage target is 0.50, set after calibration
(`benchmarks/knowledge_v1/references-b/`). Overreach remains the open problem.

Benchmark telemetry (2026-10-10, d29ac63): every knowledge_v1, coding_v1 and
business workflow lab run now writes a `benchmark_run` into
`telemetry.sqlite`, and reference grading writes a `benchmark_grading` under
it (contract v0.3 section 3a). Agent Web was restarted on this build. Smoke
run `benchmarks/knowledge_v1/runs/tel-smoke-001` proved the path end to end.

Atlas (`C:/Users/Chi_L/Documents/claude/atlas-analysis-dashboard`): Codex's
AEP consumer plus Claude Code's benchmark views and "AEP Benchmarks"
dashboard are committed as Atlas `e59655d` (by Codex, not pushed). Read
Atlas `docs/HANDOFF.md` first. Atlas backend tests pass on Python 3.13.15
(Atlas 8267f66). Only browser acceptance remains, which needs the owner.

## Repository and runtime state

- Branch `main`, all work committed locally, nothing pushed.
- **Starting Agent Web (since 2026-10-08).** The desktop/Start menu shortcut "AEP Agent" runs `aep-host open --config <host.json>`. It opens the running server's address (recorded in `workspace\agent-web.json`), or starts the server in the background first with the environment re-read from the registry. Logs go to `workspace\logs\agent-web-*.log`. To restart, stop the process listening on 53583 and use the shortcut, or run `.venv\Scripts\python.exe -m host_runtime.cli open --config ...`.
- Live Agent Web, the older manual way: `aep-host web --config %LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0\host.json --port 53583 --open --schedules`
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

## Current work (2026-10-07): coding_v1, the business workflow lab, knowledge_v1

**Phase gate (owner):** this stage is done only when the lab tasks pass *and* coding_v1 passes all 20 on the same build.

**Build state:**
- HEAD is `286e30c` or later.
- Agent Web was restarted at 07:17 on 2026-10-08; its logs are `.scratch/agent-web-20261008-071743.*`. It serves:
  - avatars;
  - every web page (`web.allowed_origins: ["*"]`; the host.json backup is `*-before-any-origin`);
  - attachments in Agent Web and Telegram, with vision on for the company endpoint (backup `*-before-vision`).
- The Shared Platform was not restarted, so asset ownership step 2 is merged but not live. The owner confirmed its design choices on 2026-10-08.
- Nothing is running. Telegram file download has been tested only with a fake transport, so the owner should try a real photo.

**Phase gate status, build `db38f28`:**
- Lab fix-010: 14/16.
- coding_v1 fix-run-013 and fix-run-014: 19/20 each, with a different task failing each time (Agent diligence).

The owner has **paused** the gate decision (coding Skill 1.8.0 wording, from the rule-following analysis) and the Knowledge tool-route choice, to check the Agent by hand first.

### Owner rule (2026-10-07): GUI tests run only while the owner is away

Tests that drive Edge or the Expense desktop app open windows and can take focus from the owner's work. Run them only when the owner is not using the computer, such as evenings or after the owner says they have left.

| Can run during working hours (no GUI) | Only while the owner is away (GUI) |
|---|---|
| coding_v1, all 20 tasks | Lab W01–W04 (Edge) |
| knowledge_v1 | Lab D01–D04 (Expense desktop app) |
| Lab C02, C03, C04, C04 exit-2 (CLI only) | Lab C01 (desktop + CLI) |
| Plain `pytest`: the desktop test skips unless `AEP_GUI_TESTS=1`; browser tests run headless | Lab X01–X03 (all three systems) |
| | `AEP_GUI_TESTS=1 pytest` and `smoke.py --browser` |

Run only the CLI tasks with `--tasks C02,C03,C04` (comma-separated IDs). Both `all` and the default `smoke` include GUI tasks.

The project has **no** `live` pytest marker, so `-m "not live"` excludes nothing. Its GUI marker is `gui`.

**Commands** (repo root, repo `.venv`):

    .venv\Scripts\python benchmarks\coding_v1\run.py --run-id <new> --tasks all
    .venv\Scripts\python benchmarks\business_workflow_lab\operator\run_lab.py --run-id <new> --tasks all
    .venv\Scripts\python benchmarks\knowledge_v1\run.py --run-id <new> --set sample|all --workers 2

- Set `PYTHONIOENCODING=utf-8` when output goes to a cp950 console.
- Run one benchmark at a time, because they all use the same Agent Web.
- When a script waits for a runner, wait on its PID. A `pgrep -f` on the runner's name matches the waiting shell's own command line.

### Results so far

Each run folder holds a `findings.md`.

| Benchmark | Run | Result | Note |
|---|---|---|---|
| coding_v1 | fix-run-011 | 20/20 | build `4becd6b` |
| coding_v1 | **fix-run-012** | **20/20** | build `967249b` (Skill 1.7.0) |
| Lab | fix-008 | 12/16 | 13/16 under grader 1.3 (W01) |
| Lab | fix-009 | stopped | W01–W04 PASS, D01 FAIL (it revised the Workflow on the rerun), the rest not run |
| knowledge_v1 | sample-001 | 64/110 acceptable | baseline: direct 22/34, tool 9/58, no Knowledge 18 |
| knowledge_v1 | sample-002 | 75/110 acceptable | Knowledge used every time, no cut-offs; tool route 15/76 PASS |
| Lab | **fix-010** | **14/16** | build `db38f28`. Every rerun reuses its Workflow, and X03 passes. C02 and X02 are Agent rule-following |
| coding_v1 | fix-run-013 | 19/20 | build `db38f28`. T13 parsing (Agent variance) |
| coding_v1 | fix-run-014 | 19/20 | build `db38f28`. T16 read only the top of `input/` |
| knowledge_v1 | sample-003 | 68/110 acceptable | direct 25/34 PASS (was 19/34), tool 10/74 (was 15/76) |

**What changed today for the lab gaps:**
- **Grader 1.3:** a rerun may use a version run *or installed* before the request, as long as no draft follows the request.
- **Draft guide and coding Skill 1.7.0:** run the installed Workflow and check its output before calling it reusable; rerun that version unchanged.
- **Ownership step 1:** versions continue from the highest installed one, so no more `workflow_version_exists` from a restarted 1.0.0.

**Open lab gaps:**
- **X02:** an overdue invoice dated before the period was missed (an Agent reading error).
- **X03:** X01's Workflow fixes the output name.
- **desktop save_as:** in fix-009 D01 it once wrote to an existing `output/tny.xlsx` instead of the given name. Investigate during the GUI run.

The operator presses approvals, replies 繼續 at most 3 times, and asks for the spec's reruns. Each of these is recorded as an intervention. Expected answers are never changed.

### knowledge_v1 (new, owner request)

See `benchmarks/knowledge_v1/README.md` and `docs/DECISIONS.md` (2026-10-07).
- The owner's 1,100 questions are pinned by sha256, and `.gitattributes` keeps their bytes exact.
- A question passes when the Knowledge loop ran, its citations are verified in the Vault, and a Gateway-model reviewer finds it reasonable.

Early observations, to confirm with the sample:
- Some questions are answered **without Knowledge**: the model answers from its own knowledge (`EXECUTION_GAP`).
- When a `knowledge__rs-knowledge` call fails with `knowledge_model_failed`, the conversation model still answers **without citations and without saying so**. The cause of `knowledge_model_failed` is not yet known. Synthesis defaults to 800 output tokens on the tool path (`handlers.py:169`). An offline repro with the default prompt did not fail.
- On the tool route, the model adds its own general knowledge around the evidence, and the reviewer fails some of those answers.

### Live host changes

A `.bak-*` backup sits next to each changed file.
- host.json:
  - `web.allowed_origins` has `http://127.0.0.1:8810`;
  - `desktop.applications.expense` is registered;
  - `coding.workspace_roots` includes the lab's runs folder.
- grants.json has grants for `browser/operate` and `desktop/operate`.
- Skill `engineering/coding@1.7.0` is in `workspace/assets/skills/`, and 1.6.0 has moved to `skills/disabled/`.
- The coding runner Python has `tzdata`.

**Restarting Agent Web:**
- Refresh the user environment variables (`AEP_*`, `LITELLM_MASTER_KEY`) first.
- `Stop-Process` leaves Edge running. The next start recovers from that (`close_leftover`).

### Platform pieces

Decisions are in `docs/DECISIONS.md` under 2026-10-06 and 2026-10-07:
- `agent.backend_contracts` sets the limits: 8000 tokens and 20 calls per turn.
- `Gateway.host_tools`; several calls in one reply run in order; a truncated reply is retried twice.
- `host_runtime/chat_authoring.py`:
  - G4 and `approval_text`;
  - versions continue from the highest installed one;
  - a name owned by someone else is refused.
- `bridge_tools.py` provides `browser__operate` and `desktop__operate`.
- `turn_summary.py` provides the tool record.
- Approvals: Agent Web `/api/approvals` and Telegram buttons.
- Bridge failures: `invalid_input` names its fields, and `CapabilityRefused.where` names the place in the request.
- `ConversationMessage` redacts credential-shaped text instead of refusing it.
- Web access: `web.allowed_origins` `"*"` means any http(s) page and is the default (`integrations.web_script.origin_permitted`).
- Attachments: `host_runtime/attachments.py`, `/api/attachments`, and images on the newest message only (`agent/gateway.py`).
- Avatars: `host_runtime/avatars.py`, `/api/avatars`, `/api/preferences`.
- Asset ownership step 2: `common/ownership.py` and `control_plane/ownership.py`.

## Verification

HEAD at the latest handoff commit, with the repo `.venv`:
- ruff passes on `src` and `tests`.
- mypy (`src`) passes.
- Full pytest at `a2bceda`: **2365 passed, 1 failed, 6 skipped**. The failure was the export-assets list in `test_weekly_report_workflow.py`, which did not yet name the two new Workflow 13 Workflows. The list is fixed in the handoff commit, and that file now passes (16 passed).
- `benchmarks/w13_parity` p001: the source job and AEP match on all 4 cases.
- Full pytest at `059f54c` (before the last catalog field): **2351 passed, 6 skipped, 0 failed**. The authoring tests passed again after that change: 28 passed. The skips are environment-dependent: symlink rights, no IPv6, an unbuilt lab mock, and the GUI test without `AEP_GUI_TESTS=1`.
- Live run of `benchmarks/authoring_v1` r001: Claude Code PASS on W1, W2 and S1; Codex and Copilot NOT_RUN because they are not installed.

The 2026-10-08 test-stability work fixed the cp950 loader test, the Windows rename locks (`common/filesystem.publish_directory`), the SOP PDF wait, the Agent Web refused-POST reset and the snapshot line endings.

`test_browser::test_a_signed_in_profile_is_what_carries_the_session` failed once on 2026-10-05; that is still open and unreproduced.

Use the repo `.venv`: the system Python has matplotlib 3.7.3 with numpy 2.2.6.

Left over: headless Edge PID 7956 (child 13048) from the test-stability probe, which the owner should close, and an unrelated headless Edge, PID 10352, that has run since 2026-10-06 23:08.

## Current work (2026-10-08): external agents author Skills and Workflows

Scope and owner decisions are in `docs/phases/EXTERNAL_AUTHORING.md` and DECISIONS 2026-10-08.
- `aep-host assets ...` (CLI) and `aep-host mcp` (stdio MCP) are the same operations (`host_runtime/external_authoring.py`, `mcp_server.py`).
- Skills now have candidates and installs (`skill_authoring.py`, `ChatAuthoring.install_skill`).
- Agent Web lists external submissions under Installed (`/api/approvals/external`).
- `aep-host assets --config <host.json> connect --for claude-code|codex|copilot --project DIR` installs the creator skills.
- Agent Web was restarted at 10:13 on 2026-10-08 (log `.scratch/agent-web-20261008-101259.*`). External submissions, the workspace-root fix and the two Workflow 13 Workflows are live in code. The Workflow 13 Workflows are shipped assets (`export-assets`) but are not installed on the live host.

## Current work (2026-10-08): task folders and Workflow 13

- **Task folders** (`af1450d`):
  - A drafted Workflow whose fixed run-python or browser workspace lies outside `coding.workspace_roots` is refused, and the problem names the roots.
  - A missing folder inside a root is created at draft time.
  - The system prompt lists the roots.
  - Live host.json now has `C:\Users\Chi_L\Documents\aep-workflows` as the first root (backup `*-before-aep-workflows-root`).
  - The owner's failed `yahoo-stock-last-price` candidate still names the old folder; it needs a redraft.
- **Workflow 13 up to the commit** (`a2bceda`):
  - `release-package-prepare` and `release-package-commit`, two approved runs. See `docs/WORKFLOW_13_SOURCE_CONTRACT.md` (2026-10-08 section).
  - The source checkout is at `C:\Users\Chi_L\Documents\claude\n8n_workflow_system` (GH_TOKEN cannot read the GitHub repo).
  - Parity: `benchmarks/w13_parity` p001 matches on all 4 cases. Rerun it with the system Python, which has `requests`.
  - The real release working copy at `C:\Users\Chi_L\Documents\git_repository\_release_repository` was not touched.
  - **Push is not built.** It needs a valid GitLab token (`AEP_GITLAB_TOKEN` expired on 2026-10-06), the owner's approval for each push, and lifting the isolated-root rule for that install.
- Codex and Copilot CLIs are not on this machine. Run authoring_v1 r002 for them after they are installed and signed in.

## Current work (2026-10-08, afternoon): drafts, installed runs, feedback upload

- **Drafts card** (`879afc8`, `fdf05d9`): Capabilities lists uninstalled drafts under the capability browser; Install is the owner's approval. The old SOP and contribution forms are gone, and Agent profile moved to Settings.
- **Installed Workflows** run without asking again, and an install takes effect without a restart.
- **Feedback upload** (`462f4d7`): Agent Web ratings are queued in `feedback_outbox` (state schema 6) and sent through the `feedback` Bridge operation.
  - **The local Shared Platform (127.0.0.1:18765) was not running on 2026-10-08**, so ratings wait in the outbox. They are sent automatically when a platform built from this code is started.
  - The platform must be restarted from this code before it knows the `feedback` operation. `aep-platform feedback --config <platform.json>` exports what it holds.
- Full pytest before the last test fix: 2378 passed, 2 failed. One was the schema-version test, now fixed. The other, `test_workflow_preview`, passed when rerun alone and is timing-dependent.

## Current work (2026-10-08, evening): MCP servers and harness telemetry

- **MCP servers** (`f3175fc`): Settings → "MCP servers" adds stdio or HTTP servers. Their tools become granted Bridge capabilities `mcp-<server>/<tool>@1.0.0`. No server is configured yet.
- **Harness telemetry** (`3dd08bc`, contract v0.2 in `docs/telemetry/`): recording is live in Agent Web. The store is `workspace\telemetry.sqlite`, with 30 days / 500 MB retention. Atlas reads `http://127.0.0.1:53583/api/v1/telemetry/...` without a token, and only from local origins.
  - The strategy label goes in `workspace\telemetry.json` (`{"strategy_label": "..."}`) and takes effect at restart.
  - Export with `aep-host telemetry export --config <host.json> --out x.jsonl`.
  - The Atlas side (an event-stream provider and the views) is not built; see contract §8.
- Full pytest at `3dd08bc`: **2394 passed, 6 skipped, 0 failed**.

## Next recommended action

0. Start the Shared Platform from this code, then check that a new rating leaves `feedback_outbox` and shows in `aep-platform feedback`.

1. The owner redrafts the stock Workflow; the Agent should now suggest a folder under `aep-workflows`. Then the owner connects their own Claude Code project (`assets connect`) and tries a real asset.
2. Workflow 13 push round: ask the owner for the release remote, the working copy and a new GitLab token; then add push with its own approval, a dry-run comparison on the real repository, and the pipeline watch.
3. Install and sign in to Codex and Copilot, then run `benchmarks/authoring_v1/run.py --run-id r002 --agents codex,copilot`.
4. Check the owner's first real Telegram photo or file, since download has only been tested with a fake transport.
5. **Paused by the owner, who will check the Agent by hand first:**
   - the phase gate (coding Skill 1.8.0 wording: read rules in full, missing values follow the request or template, keep template formulas, check outputs against inputs; X02's period/as-of wording to be tested separately);
   - the Knowledge tool route: (a) return the harness answer as it is, (b) route more questions directly, or (c) leave it.
6. The knowledge_v1 full 1,100 run (`--set all`, several hours, no GUI) once the tool-route choice is made.
7. Later:
   - asset ownership step 2 follow-ups: member publish route with a review queue, a UI, and a Shared Platform restart to go live;
   - conversational authoring A1–A3, A7, A8.
