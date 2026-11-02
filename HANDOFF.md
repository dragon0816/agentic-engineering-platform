# Handoff

Updated: 2026-11-02 (Asia/Taipei), by Claude Code (asking a vault from the general chat; earlier: BI charts in the chat and the Dashboard's sources: C1, C2, C1b, C3, K1, K2; earlier: voice input for Telegram and Agent Web: V1–V8; earlier: BI analysis dashboard: F1, F2, F3, P1, P2, P3, P4, D1, D2, D3, chains and coverage as analyses, golden answers, P5, D4; earlier: knowledge repositories R1, R2, R3 BI part, R4a, R4b, R5 BI side; earlier: BI vaults V9–V13; earlier: coding at scale S1–S4; earlier: BI vaults V1–V6; earlier: BI ingest phases 1–7 from the owner's proposal; earlier: delegation and gateway retries, #248 BI browser tests, graphify code graph, push of verified main; earlier: multi-agent V1 presentation, Settings switch and baseline benchmark; earlier: multi-agent V1 core delegation; earlier: multi-agent Phase 0.5 part B: P0-2, a side effect at most once per turn; earlier: multi-agent Phase 0.5 part A: G5 cross-domain suite and G4 bookkeeping; earlier: multi-agent Phase 0 review; earlier: SDE weekly report keys every ticket by its GitHub Issue; earlier: session memory of what was produced and task result summaries; earlier: yes/no inputs in plain words; earlier: fewer questions in a Workflow run and the activity read before a restart; earlier: Telegram delivery, reply context and claim-check fixes; BI dataset sharing slice 1 live-test fixes; session model scope; BI Knowledge Case A backend; accumulated memory M5: memory quality tools; accumulated memory M4: the Agent Web memory page; accumulated memory M3: preferences and notes; loan replies 06 / 06b as two Workflows; owner rule: new evidence updates organisational fields, email stays a proposal; accumulated memory M2: sync state and incremental org chart; accumulated memory M1: Memory Service and business-cards migration; interactive HTML org chart and files in the chat; agent recovery and reuse fixes; business-cards third-round fixes; business-cards second-round re-test fixes; business-cards live-test fixes; native business cards and org chart; three live-test fixes: image retry, progress end state, switched-off Skills; 2026-10-19: owner decisions on Knowledge Strategy v1.3 applied: competing_vendors, scoped priority, Opportunity, speaker notes in office.py, ADR-K9; earlier the same day: Knowledge Strategy v1.3, Telegram status on change, team-member revisions, Platform sync URL label, Personal Agent code sign-in and renewal)

## Asking a vault from the general chat (2026-11-02, Claude Code, worker D) — latest

**Goal.** Owner 2026-11-02: a knowledge vault (BI or wiki) imported into AEP can be asked from a general AI chat, with
cited answers. Design `docs/phases/BI_VAULT_ASKING.md`; decision `docs/DECISIONS.md` 2026-11-02; contract
`docs/CONTRACTS.md` "Asking a vault from the general chat"; runbook `docs/runbooks/R6_MARKET_BI.md`.

**Where.** Branch `bi-vault-asking` in Paseo worktree `2qnenase/bi-vault-asking` (own `.venv`, dev+office), from `main`
`a7629341`; `main` had not moved at this writing. Nothing pushed or merged; the BI orchestrator merges.

**Done.** `e1084359` design; `cc72c420` V1 (host-written source line, whole-chain test); `faab9904` V2 (`/api/knowledge/
askable`, `propose_change` kind `knowledge_binding`, page button); `7f255dbf` V4 (runbook, `scripts/r6_precheck.py`);
V3 `aep_bi_query` behind `assistant_bi_query`, off by default (see `docs/TASKS.md`).

**Verification (on `b8fe7f61`).** `ruff format --check .`, `ruff check .`, `mypy src tests` (916 files) clean. On the V3
code: `test_assistant_bi_query` (with a headless browser step), `test_assistant_tools`, `test_coding_agents_web`,
`test_coding_agent_setup`, `test_conversation_backends`, `test_host_wiring`, `test_host_models`,
`test_ai_proposed_changes`, `test_vault_asking_e2e`, `test_vault_asking_binding`, `test_r6_precheck`: 177 passed, 1
failed (`test_coding_agents_web`'s card count, my switch used its class); after the fix that file and
`test_assistant_bi_query` passed, 18. Earlier slices also ran `test_bi_chat_save`, `test_bi_chat_charts`,
`test_bi_chat_sql`, `test_bi_query_analyses`, `test_bi_vault_published`, `test_knowledge_repo_agent`,
`test_knowledge_repo_ui`, `test_knowledge_unified`, `test_harness_output_limit_g4`. **The full suite has not run**: it is
the orchestrator's, on the integrated branches. `r6_precheck` has not been run on the real OneDrive folder, and must not
be by an agent. No graphify graph in this worktree, so `graphify update` was not run.

**Not done.** V5 live acceptance with real models: not go yet, the model gateway did not answer its health route; the orchestrator sends the go and the credential
variable's name. Only under `%TEMP%`, its own Agent Web on a free loopback port, never 53583, the owner's workspace or
OneDrive; do not read the owner's `host.json`. The full suite is the orchestrator's, on the integrated branches: do not
run it here.

**Known points.**
- A never-published vault is answered from its pushed head, marked as such (decision 8, kept by the owner 2026-11-02);
  only local work and pushes after the tag are refused.
- The conversation offers a Knowledge Skill's tool only when the Skill's namespace is the host's.
- A host without `knowledge_pipeline` shows no wiki repository card, so no button; the route and the chat proposal work.
- R6 cannot reuse the id `market-bi` on the owner's PC (`vault_exists`): runbook D1. Other R6 decisions: D2–D5.

**Next action.** Orchestrator: integrate with A and C and run the one full suite. V5 after its go.

## BI charts in the chat and the Dashboard's sources (2026-11-01, Claude Code)

**Goal.** Owner decisions 2026-11-01, relayed by the BI orchestrator: (a) charts in the general AI chat inline
as a self-contained HTML in the chat file viewer; (b) a chat chart saved as a vault analysis with the owner's
approval; (c) a vault's Dashboard from the analysis AI or imported (order only) from an Atlas dashboard; plus
guarded read-only ad-hoc SQL in the chat (owner, C1b). Design `docs/phases/BI_CHAT_CHARTS_AND_DASHBOARD_SOURCES.md`;
decision `docs/DECISIONS.md` 2026-11-01 (with the C1b addendum); contract `docs/CONTRACTS.md` "BI charts in the
chat and the Dashboard's sources".

**Where.** Branch `bi-analysis-dashboard-f1-f3` in the Paseo worktree `sudden-mayfly` (own `.venv`), first
fast-forwarded to local `main` `2ea05220`; not pushed, not merged (the orchestrator fast-forwards `main` after
review). The Atlas repository was only read (its goldens at `49600737`).

**Done.** Commits `8fbea1dd` (design), `2ea5bd0b` (C1+C2), `5bcad315` (C1b), `f72b7f37` (C3), `e4be62e1` (K1),
`6b093e9f` (K2), and this handoff/contract commit; a row per slice in `docs/TASKS.md`.
- C1/C2: `analyses.chart_for`/`default_chart`; `host_runtime/bi_chart_html.py` (the Dashboard tab's renderer,
  spliced into `web_page.PAGE`, and the chat page); `bi_cards_tools.chart_page`/`bi_chart_files`; Agent Web
  shows the page in the answer (Telegram unchanged).
- C1b: `bi__query` `sql`/`chart` through `analyses.run_sql` on the published data, 10 s, 200 rows.
- C3: `propose_change` kind `bi_analysis` (web only); BI side `host_runtime/bi_chat_save.py`.
- K1: `bi_analysis__propose_dashboard`; `analysis_session` suggestion/apply; page 「套用 Dashboard」.
- K2: `capabilities/bi_cards/atlas_import.py`, `host_runtime/bi_atlas_import.py`, routes `atlas-dashboards` and
  `atlas-import`, page 「從 Atlas 匯入 Dashboard 順序」, goldens in `tests/fixtures/atlas_dashboard_golden/`,
  `scripts/check_atlas_dashboard_golden.py`.

**Verification.** Each slice before its commit: `ruff format --check .`, `ruff check .`, `mypy src tests` (911
files at K2) clean, and its tests (`test_bi_chat_charts` 8 incl. a real-browser turn, `test_bi_chat_sql` 6,
`test_bi_chat_save` 13, `test_bi_dashboard_proposal` 8, `test_bi_atlas_import` 9 incl. the drift check against
the Atlas checkout with `AEP_ATLAS_REPO`), plus `test_ai_proposed_changes`, `test_bi_analyses`,
`test_bi_vault_ui`, the page-script parse test; C1/C2 and C1b were also checked as exported slices. Full suite:
see "Full suite" below.

**Known points.**
- K1's and K2's page parts are covered by the script parse test only, not by a browser step.
- The chat's chart pages accumulate in `<workspace>/bi-chat-charts/` (small HTML files; no purge yet).
- C3 runs the SQL on the vault's working copy, so the card's numbers can differ from the chat's (published).
- The running Agent Web predates this code; the owner sees it after a restart (check `/api/tasks` first).

**Full suite.** On `6b093e9f` (worktree `.venv`, own `--basetemp`, 2026-11-01 23:11–23:53, after the
orchestrator's go; Atlas idle): 4664 passed, 38 skipped, 0 failed, 42 min. Skips are environment extras (pywin32,
matplotlib, Outlook, symlink/link privileges, IPv6, litellm, `av`, no voice model, expense mock) and the opt-in
Atlas drift test (`AEP_ATLAS_REPO` not set; it passed when set).

**Next actions.** (1) Orchestrator: review, fast-forward `main`. (2) Owner, after a restart: try a chart in the
chat, an ad-hoc SQL question, 「存成分析」 through the card, an AI dashboard, and an Atlas import (Atlas running
on 8127). (3) Optional: browser steps for K1/K2 on the Knowledge page; a purge of old chat chart pages.

## Voice input for Telegram and Agent Web (2026-11-01, Claude Code)

**Goal.** Owner 2026-11-01: a person speaks instead of typing, on Telegram (voice messages) and Agent Web
(microphone), for coding, asking and Workflow runs; speech becomes text on this PC, the person sees it, and the
text then follows exactly the typed path, rules and confirmations. Design and status:
`docs/phases/VOICE_INPUT.md` (§6.1 lists every slice with its commits); decisions: `docs/DECISIONS.md`
2026-11-01 (local STT only, no extra voice confirmation and none removed, transcript kept and audio never, plus
the accepted §7 points); contracts: `docs/CONTRACTS.md` "Voice input"; guide: `docs/guides/VOICE_INPUT.zh-TW.md`.

**Where.** Branch `voice-input-integration` in the Paseo worktree `C:\Users\Chi_L\.paseo\worktrees\2qnenase\
voice-input-integration`, from local `main` at `923bd641`; nothing pushed, no PR. The voice orchestrator
coordinates; Claude Code built the slices; Codex wrote the independent integration tests (`4bf57da4`).
Worktree `.venv` has only the CI extras (`dev,office`); a separate venv with the `voice` extra
(`%LOCALAPPDATA%\aep-voice-venv`, outside the repository) ran the PyAV/OpenCC tests.

**Done.** V1–V8 (`docs/phases/VOICE_INPUT.md` §6.1; rows in `docs/TASKS.md`): `src/voice/` (contracts, STT
interface, in-memory decoding, `VoiceService`, transcript record and store, local `FasterWhisperProvider`),
Telegram voice/audio in `channels/telegram.py`, `POST /api/voice/transcribe`, `GET /api/voice` and
`ConversationTurnRequest.voice_transcript` in `host_runtime/web.py`, the 🎤 button in `web_page.py`, host wiring
(`HostRuntime.voice`, `build_telegram(voice=)`, `AgentWebServer(voice=)`, CLI). Voice is off unless `host.json`
has `voice.enabled`; without it every channel behaves as before.

**Verification so far.** All voice test files, the touched Telegram/host/Agent Web/conversation/CLI/page tests,
the 52 integration tests (Telegram 27, Agent Web 25) on `a3b160db`: pass. `ruff format --check .`, `ruff check
.`, `mypy src tests` (902 files): clean. With the `voice` extra: the codec and OpenCC tests pass. Skipped: the
real-engine test (no model on the build PC). **Full suite** on `a3b160db` (own `--basetemp`): 4611 passed,
37 skipped, 1 failed, a BI fixture check that also failed on `main` (empty `vault/sources` folder git cannot
keep); fixed in `0acad6bd` with the owner's OK, BI tests pass after it.

**Known points.**
- Concurrent pytest sessions on one PC share `%TEMP%\pytest-of-<user>` and prune each other's base folders;
  one knowledge integration test failed once that way and never reproduced. Use `--basetemp=<own folder>` per
  agent when runs overlap.
- A spoken credential is refused like typed text (`transcript_credential`); a spoken 「好」 never confirms a
  Telegram card or an Agent Web form; spoken 「取消」/「修改」 work as typed.

**V0 done (2026-11-01).** The owner supplied `Systran/faster-whisper-small` (revision `536b0662`, int8) and
two recordings (outside the repository). Package hash `8d64e4da7ad18a60c68a4616ddc7c5ffb3ea4a405ed2c003a2222016952db2c9`;
CER limit 0.20 from the measurement; findings, speed and the dropped-clause risk in `VOICE_INPUT.md` §6.2.

**Open owner items.** The live checks of `VOICE_INPUT.md` §4.6, after hours: enable voice in `host.json`
(model path, the hash above, and `voice.hints` with the product and tool names the owner says; without
hints English names are unreliable). Enabling voice needs an Agent Web restart: check `/api/tasks` first.

**Next actions.** (1) Done: `main` pushed with the owner's OK (`8d743324`, after a pre-push full suite of 4622
passed); GitHub Platform verification run 41307727192 green, including the Windows preview bundle (fixed in
`8d743324`: python-dateutil 4 dropped six). (2) Owner: the open items above. (3) Optional, owner's call: an A/B of
`voice.hints` on the owner's own recordings with reference transcripts; telling the Agent that a turn was spoken.

## BI analysis dashboard and domain retirement (2026-11-01, Claude Code)

**Goal.** `docs/phases/BI_ANALYSIS_DASHBOARD.md` §7, AEP side, in the owner's order: F1 → F2 → F3, P1 → P2 →
P3/P4, D1 → D3, chains and coverage into the pack, golden answers, P5, D4. Codex builds the Atlas side (A1, A2,
I1) in its own repository from the golden files; the AEP agent never touches the Atlas repository. Each finished
task: checks, commit, rebase on `origin/main`, `git push origin HEAD:main` (no pull requests), TASKS and this
file updated. Work happens in the Paseo worktree `sudden-mayfly` with its own `.venv`. Do not restart the running
Agent Web.

**Done (all AEP tasks of §7).** Each has a row in `docs/TASKS.md`, a contract in `docs/CONTRACTS.md` and, where
choices were made, a decision in `docs/DECISIONS.md` (2026-11-01):
- F1–F3 feed for Atlas (`feed.py`, `bi_feed_api.py`, `scripts/bi_feed_fixtures.py`, `scripts/bi_feed_server.py`).
- P1–P4: analysis params/requires and the Dashboard order; the default pack `bi-market-default`; the Dashboard
  tab draws analyses (`board.py`); `bi__query` reads saved analyses.
- D1–D3: schema 3.0.0 (`tech_areas`, `chain`, `aliases`; 3.0.0 not 2.1.0, see the decision); name matching from
  card aliases; the domain migration.
- Chains A–A3 and the coverage matrix as pack analyses (`ea27af7f`); golden answers of the coded sections in
  `tests/fixtures/bi_default_pack/golden/` (`e18ec7c8`, frozen: a deliberate change of an answer edits the file
  with the reason); P5 removed `dashboard.py`/`market.py`/`coverage.py`, `/api/bi/coverage` and the matrix panel
  (`71574dc1`); D4 removed `domains.py`, `/api/bi/domains` and the 「領域設定」 editor, the migration now moving
  everything it can for vaults and local datasets (owner answers 2026-11-01).

**Verification (D4, final state).** `ruff format --check .`, `ruff check .`, `mypy src tests` (881 files) clean;
`pytest tests/test_bi_*.py` (every BI test, browser tests included): 334 passed. The full suite was run afterwards
on `b6a139c5` (below). No graphify graph in this worktree, so `graphify update`
was not run.

**Known points for the owner.**
- Vaults made before the chain/coverage analyses get them by importing the pack again (「建立與匯入」 step 3).
- A local dataset's migrated notes are an ingest method that must be chosen for an AI run (before, they were
  added to every run).
- The running Agent Web predates this code; after a restart (check `/api/tasks` first), a dataset or vault that
  still has a domain configuration shows the migration prompt on its Dashboard. `market-bi` (V4 format) is
  rebuilt at R6 anyway.

**Full suite (done).** On `b6a139c5` (worktree `.venv`, 2026-11-01): 4450 passed, 35 skipped (all environment
extras: 23 pywin32, 3 matplotlib, Outlook, symlink/link privileges, IPv6, litellm, expense mock), 55 min;
`ruff format --check`, `ruff check`, `mypy src tests` clean. `b6a139c5` added to design §5 that enum params carry
`params.<name>.values`. Local AEP `main` fast-forwarded to `b6a139c5` (not pushed).

**Atlas side (done, Codex).** Branch `bi-analysis-dashboard-atlas-brief-a1-a2-i1` (commits `81c86e1`,
`ef20cd0`, `bc8efda`) in the Atlas repository: 17 golden files vendored byte-identical from AEP `b6a139c5`; npm
test 141 passed; build pass; Python server tests 35 OK / 7 skipped; drift check pass. I1 against
`scripts/bi_feed_server.py --port 53611` passed all six cases (vault list, three panels' golden values, param
refetch, 409 then result, stale data with a warning after the server stops, foreign Origin 403). No contract
mismatch.

**Next actions.** (1) Owner: I2 live acceptance (§6.5), then R6 rebuilds `market-bi` on this structure.

## Knowledge repositories R1, R2, R3 (BI part), R4a and R5 (BI side) (2026-10-30/31, Claude Code)

**Goal.** Every knowledge base, wiki and BI, single or multi-maintainer, updated by one mechanism: commit
(purpose required), push, revert, tag/publish; schema and skills inside the repository. Owner decisions 1–11:
`docs/phases/KNOWLEDGE_REPO.md` §1 and `docs/DECISIONS.md` 2026-10-30.

**Done** (contracts in `docs/CONTRACTS.md` "Knowledge repositories: ..."; progress rows in `docs/TASKS.md`):
- R1 engine `src/knowledge/repo/repository.py` (units, commits, push with unit rebase, revert, tags, publish).
- R3 common skills, `REPO.md` generator, BI schema document, R4 core wiki type (library only, not wired).
- R2 BI type: `src/capabilities/bi_cards/vault.py` on R1, routes in `bi_vaults_api.py`.
- R5 BI side: the Agent (`bi__query`) reads only the published version (pushed head if never published)
  from `published/bi.sqlite`; `REPO.md` and the schema `.md` written on push/tag/publish; the 「版本」 area
  in 「建立與匯入」 step 1 (commit, push, conflicts, history, diff, revert, tag, publish confirm).
  Decision "How the Agent picks up a newly published BI version": live, at the next question.
- R3 BI part: `src/capabilities/bi_cards/vault_skills.py`. Generated classify skill; domain notes moved
  into `<domain>-extract` skills; an AI run in a vault takes `folder` and reads the classify skill and that
  folder's extract skill (refused with `skill_needs_update` when a skill is for another schema); routes
  `GET/POST /api/bi/vaults/<id>/skills`; skills list and editor in 「版本」, folder picker in step 3.
  Decision "Skills of a BI vault: which source folder, and what an AI run reads".
- R4a wiki backend (owner decisions 2026-10-30 "Wiring the wiki type (R4)", plus the `host.json`
  binding by `repo`): `src/knowledge/wiki_repos.py`, `src/host_runtime/knowledge_repos_api.py`
  (`/api/knowledge/repos`), the catalog's live entry (`KnowledgeCatalog.register_live`), the working
  folder `src/knowledge/wiki_work.py`, the benchmark push check `src/host_runtime/wiki_bench.py`.
- R4b part 1 (2026-10-31): every Knowledge tab step runs on a repository opened as `repo.<id>`
  (`Sandboxes.open`), what it wrote is staged at once; per-PC intake and question folders
  (`/api/knowledge/repos/<id>/settings`); 「測試」 on a repository runs `wiki_bench.run`. The working folder
  captures against what it was built from.
- R4b part 2 (2026-10-31): the Knowledge page lists repositories beside sandboxes (import a copy, create,
  join), runs the three steps on `repo.<id>`, shows this PC's folders in step 1 and the 「版本」 area in
  step 3 (commit, push, conflicts, history, diff, revert, tag, publish). Browser test
  `test_knowledge_repo_ui`. The old sandbox/push/publish path still works unchanged until R4c.
- Session B on a skill of a BI vault (2026-10-31, owner request): 「和 AI 一起修改」 per skill;
  `src/capabilities/bi_cards/skill_session.py`, session kind `skill`; applying stages the next revision.
- BI 「建立與匯入」 in three steps (2026-10-31, owner request): 1 資料輸入與轉換, 2 Schema 與 Ingest (parts:
  schema and skills, trial, review, write, result), 3 測試與 Push (「版本」 moved here). Layout only.
- BI T1 (2026-10-31): benchmarks of a BI vault, question sets and extraction cases kept in the vault, run on
  the working and published version through the Agent harness, regressions block the push; step 3 shows them.
  Design `docs/phases/BI_TEST_AND_TOOLS.md`; owner decisions in `docs/DECISIONS.md` 2026-10-31.
- BI T2 (2026-10-31): the skill AI runs on the Agent harness with tools (try a draft rule, compare,
  extraction cases, query); `host_runtime/bi_skill_agent.py`.
- BI T3 (2026-10-31): analyses by AI conversation (read-only SQL, guarded Python), saved in the vault and
  drawn on the Dashboard; `analyses.py`, `bi_analysis_agent.py`.
- Telegram: a 409 conflict is retried instead of stopping the loop (`ded9bfc0`, `ff4164fe`).

**Verification.** ruff format/check and mypy clean (848 files). BI + knowledge test files after the R3
BI part: see the commit message. The browser test `test_bi_vault_ui` drives the 「版本」 area and the skills
block (screenshots `.scratch/bi-vault/vault-versions*.png`, `vault-skills.png`). The full suite was not run (it slows the owner's Agent Web; run it
when the PC is free). Local commits are not pushed yet.

**Important.** The OneDrive `market-bi` vault is V4 format. The R2 code neither reads nor writes it. Once
Agent Web restarts on this code, `market-bi` is read-only until R6 rebuilds it (owner present).

**Next actions.** (1) Done 2026-10-31: full suite 4448 passed, 7 skipped (35 min); main pushed to `2957435b`. (1a) Next build: BI analysis dashboard and domain retirement, `docs/phases/BI_ANALYSIS_DASHBOARD.md` §7, AEP side starting with F1 (golden fixtures unblock Codex on Atlas, brief `BI_ANALYSIS_DASHBOARD_ATLAS_BRIEF.md`), run in parallel through Paseo worktrees; merge verified AEP worktree branches into main locally, no PRs. (1b) The owner tries BI T1-T3 with real models on a vault (benchmark questions through the Agent, the skill AI with tools, an analysis); fix what that shows. The script guard is not a sandbox (decision 2026-10-31 "AI analyses, implementation choices"). (2) R3 BI
follow-up if the owner wants it: sources inside the repository folder (Session B on a skill is done). (3) R4c, after the owner has tried a repository on the page (Agent Web was restarted on R4b at 09:38 on 2026-10-31; restart again for Session B on skills): review
proposals open a repository instead of a sandbox (`web.py` `_route`), then remove sandboxes, candidates, `knowledge_push`,
`knowledge_publish` and their tests. R5 for the wiki is complete (the 「版本」 area of R4b; the Agent reads the
published folder through a `repo` binding). (4) R6 with the owner present: rebuild `market-bi` from raw data, import an `rs-k` copy.

## BI vaults V9–V13 (2026-10-29, Claude Code)

**Goal.** The owner's manager built five BI knowledge bases by hand (Obsidian + Dataview), each needing Claude
Code to change the schema, ingest, seed and dashboard tools again. The owner chose one market BI vault for every
domain with the differences as configuration (`docs/phases/BI_VAULT.md` §12, `docs/DECISIONS.md` 2026-10-29
"One market BI vault for every domain") and asked for V9–V13 in order.

**Done** (contracts in `docs/CONTRACTS.md`; decisions under "BI vaults V9–V13, implementation choices"):
- V9 "BI schema 2.0, new kinds and widening": the manager's schema v8 shipped as `bi.schema/v1.1@2.0.0` (21
  types; fixture `tests/fixtures/bi_schema_v8/`, generator `scripts/build_bi_schema_v2.py`), `float`, allowed
  values on lists, widening kind changes migrated on upgrade, type from the file name, `%` on floats. A bare
  `bi.schema/v1.1` now means 2.0.0 (new vaults start on it); unbound datasets stay on 1.1.0.
- V10 "BI domain configuration": `aep.bi.domains/v1` in the dataset `meta` (shared by change files), panel
  「領域設定」, coverage matrix from it, enum and name aliases in imports and AI candidates, chains.
- V11 "BI extraction evidence rules": fixed rules in every AI extraction, A–D grades, domain `notes`, fact
  numbers checked against their quotes.
- V12 "BI market analyses": §20–§31 and chains A–A3 (`market.py`), sample switch, domain picker from the schema.
- V13 "BI quality checks": ten checks (`quality.py`, `/api/bi/quality`, Dashboard section Q).

**Checked on the manager's data** (local `files/aidc-bi-kb`, never committed): all 22 seed CSVs preview with
every column mapped into a 2.0.0 dataset (323 cards); the dashboard gives his README's numbers (evidence B 42,
C/D 9; compute chain 49 supply links, power and cooling 2); quality gives 0 issues and his 3 deliberate gaps.

**Verification.** ruff format/check clean, mypy clean (834 files). Full suite on the final state: 4348
passed, 7 skipped, 1 failed: `test_bi_markdown_ui` read the Skill picker before its list arrived (a test race,
worse under load); the test now waits for the value, and passes alone and among the browser tests.

**Owner decisions after the commit (2026-10-29).** No permission control (V8 dropped). 2.0.0's `segment` now
also takes the market chart's 11 segments (labels as aliases), so AIDC needs no schema step. The kt101
GitLab branch is the owner's to handle.

**Market vault created (2026-10-29, owner present).** `OneDrive - Rohde & Schwarz\BI_Knowledge\market-bi`,
dataset `vault-market-bi` on the preview workspace, schema 2.0.0: the manager's five bases merged and imported
(639 cards), domain configuration saved (revision 2), AIDC reports in `applications/aidc-*/sources/`. Details in
`docs/TASKS.md`. Merge and build scripts were one-off (Claude Code scratchpad), not part of AEP.

**Open (owner).** (1) Restart Agent Web (`.scratch/restart_web.py`; it refuses while work is active): the
running host predates 2.0.0. (2) The manager's data issues the quality check lists (8 links to cards nobody
wrote, 致茂 and 鴻海 in two types, 7 revenue facts without source, 2 sample nodes off the name format, 1 A-grade
link without a date). (3) A `tech_areas` field for the coverage matrix (Session A).

**Next actions.** (1) Owner: restart Agent Web and open the vault. (2) Colleagues join the folder.

## Coding at scale S1–S4 (2026-10-29, Claude Code)

**Goal.** Team members must develop chipset-control programs (Qualcomm WMT, a 125 KB driver file) through
AEP. A colleague found `coding/change` could not: the author saw the first 20,000 characters of one file and
had to return it whole within 8,000 output tokens. The owner chose option B: make `coding/change` capable.
Plan `docs/phases/CODING_AT_SCALE.md`; decision `docs/DECISIONS.md` 2026-10-29 "Coding at scale"; contract
`docs/CONTRACTS.md` "Coding change at scale"; guide for team members `docs/guides/CODING_LARGE_REPO.zh-TW.md`.

**Done (commit `c1d48181`):** explore-then-edit author (list, outline, read ranges, search; exact
search/replace edits; CRLF and BOM kept), several declared files (`more_files`), host-declared module checks
(`checks`), limits in `host.json`, Workflow `coding-change` 1.1.0, Skill `coding` 1.9.0; fix: `pytest-suite`
ran declared checks' names as paths.

**Verification.** Clean worktree at `c1d48181` with the CI interpreter (dev,office extras, no pywin32): ruff clean, 1095 files formatted, mypy clean (826 files), pytest 4292 passed, 35 skipped, 0 failed. The Windows restricted-execution tests (`test_coding_at_scale.py`, `test_coding_change_capability.py`, `test_coding_worktree_pytest.py`, `test_restricted_runner.py`) need pywin32 and were run separately with the project `.venv`: 110 passed together with the harness and E2E-03 tests.

**Open (owner):**
1. The shared credential rule refuses a change whose text matches the secret pattern; `password: str` matches.
   A driver with such lines stops with `author_change_has_credential`. Decide whether code that names
   credentials (without containing one) should pass.
2. No live run: C7 (practice repository) first, then a real repository (S5). The colleague's PC needs its own
   runner interpreter (64-bit if WMT's dependencies need it), the firewall rule, the WMT tests and fixtures
   committed locally, and a `coding` block in `host.json` (guide §3).
3. Tests that need child processes, the network or a DUT cannot pass in the restricted runner;
   `change_max_processes` can be raised (residual risk in the plan).

**Next actions.** (1) Owner: C7 live run. (2) Owner decision on item 1. (3) Colleague: configure WMT per the
guide; consider extracting the OP2 table from the driver anyway (smaller files are easier to review).

## BI vaults V1–V6 (2026-10-28, Claude Code)

**Goal.** The owner's review of the built BI flow (2026-10-28): a purpose-built knowledge base (a *vault*) that
a team maintains together, the chain original → Markdown → schema + extraction Skill → cards + search index +
originals shown on the page, Sessions A/B visible, an extraction Skill to choose, a coverage view per market
segment and technology area, and the Agent finding the vault by purpose. Design `docs/phases/BI_VAULT.md`
(§8 owner answers: SharePoint, cards later, `segments` OK); decisions `docs/DECISIONS.md` 2026-10-28 "BI
vaults", "BI vault V4: writes are captured and replayed", "BI vaults V1, V5, V6: implementation choices",
"BI vault V2 and V3: implementation choices". Guide `docs/guides/BI_BUILD.zh-TW.md` (§3.0, §3.1, §5, §9.5,
§9.6). The owner asked to keep building what is clear and report the rest later.

**Done on local `main` (commits `41074f14`..`c53771bd`):**
- V1 page: Session A shown without a draft (first message makes one), step 3 「擷取 Skill 與試跑」 with built-ins
  「AI 擷取」/「表格規則」 and Session B always shown (a built-in is copied before a change), 「匯入 CSV」 tab
  removed (backend kept), bar counts refresh after a commit, 「在 Atlas 開啟個人 Dashboard」.
- V2/V3 (subagent backend, merged; page by me): every source converted to Markdown with immutable revisions,
  runs read the current revision (`path` ai/rules), PDF/Word/PowerPoint accepted; FTS5 trigram index
  `<dataset>/search.sqlite`, `/api/bi/index`, `/api/bi/search`; page: source formats, 「看／改」 Markdown editor
  with revisions and `markdown_stale`, full-text search in the cards view.
- V4 (subagent backend, merged; page by me): vault = dataset `vault-<id>` in a synced shared folder; every
  write captured as one change file `changes/<author>/<seq>.json`, replayed in (Lamport clock, author, seq)
  order, conflicts become proposals, merge flags; `/api/bi/vaults*`; step 1 「知識庫」 panel (choose, create,
  join, convert, sync, status).
- V5: `/api/bi/coverage` + shipped owner chart `coverage_matrix.json` (11 segments, 5 areas); Dashboard matrix.
- V6 (part): `bi__query` lists the vaults with their purpose and syncs a vault before reading it.
- Fixes found by the full suite: no literal URL in the page (`test_the_page_fetches_nothing_from_anywhere`),
  stale-reply guards for the Skill reload and the vault panel.

**Verification.** Full clean-worktree run at `c53771bd`: ruff clean, 1087 files formatted, mypy clean (820
files), pytest 4275 passed, 34 skipped, 1 failed: `test_bi_subscriptions.py::test_an_unreachable_platform_is_
offline_and_changes_nothing_else`, a Windows `PermissionError` renaming the freshly installed snapshot folder
(passed 3/3 alone). Fixed after the run by using the retrying `schema_versions.replace` for the snapshot and
subscription renames (sharing, snapshot and vault tests 50 passed); not re-run as a full suite. Earlier
full-run failures on the way (literal URLs in the page, two stale-reply races) were fixed and covered.

**Not done / open (for the owner):**
1. Cards (V7): the owner will bring ideas; the list still shows only type, name, key and field count.
2. Snapshots carrying evidence: needs format `aep-bi-dataset-snapshot/2` (readers check exact keys, older PCs
   would refuse); owner to decide.
3. 141 as backup and publisher of a vault: needs the owner and 141.
4. Permissions and per-folder classification (V8): last, by the owner's choice. For testing the owner approves
   INTERNAL in Settings (no code change).
5. The two placement fields (`segments`, `tech_areas`) are not in the shipped schema: a vault adds them through
   Session A (draft → publish → upgrade). Until then the matrix shows every card as unplaced, and says so.
6. Vault follow-ups: merge flag on the card detail; sources stored in the vault's `applications/`/`library/`
   folders (today they stay in the PC's local vault directory, so colleagues see the cards and evidence but
   not each other's source files); incremental sync scan.
7. No real model and no real SharePoint folder have been used: all tests use scripted models and temporary
   folders. Creating or joining the real SharePoint vault must be done with the owner present, after a backup.

**Next actions.** (1) Owner: restart Agent Web after checking `/api/activity`, approve INTERNAL in Settings,
try a vault on an empty test folder, then on SharePoint. (2) Decide items 2–3 above. (3) Owner's card ideas →
V7. (4) Sources into the vault folders (item 6).

## BI ingest from the owner's proposal, phases 1–7 (2026-10-28, Claude Code)

**Goal.** The owner's 「AEP BI 知識庫建立與 AI Ingest Proposal」 (2026-10-27), specified in
`docs/phases/BI_INGEST.md` (supersedes `BI_CASE_B.md`). Decisions: `docs/DECISIONS.md` 2026-10-27 "BI ingest:
the owner's proposal becomes the plan" and 2026-10-28 "BI ingest phases 3–6: implementation choices". User
guide: `docs/guides/BI_BUILD.zh-TW.md`.

**Done, all pushed to `main` up to `91e23651`** (contracts in `docs/CONTRACTS.md`: "BI ingest runs", "BI schema
drafts and dataset upgrade", "BI rule path: recipes and multi-table sources", "BI AI path: extraction runs",
"BI method sessions", "BI schema sessions"):
1. Staging store, review, version-checked atomic commit, evidence, proposal accept/reject.
2. Schema drafts, local `bi.schema/v1.1` superset versions, dataset schema upgrade with impact preview.
3. Rule path (recipes, Markdown/Excel/CSV readers, VE-05/VE-06) and Knowledge → BI 卡片 → 「建立與匯入」 six
   steps on the shared stepper.
4. AI path: chunked, tool-less structured extraction with code-located evidence; background runs, `partial`,
   retry; a source goes to the model only in an approved data class.
5. Session B: versioned ingest methods, method conversation, trial compare, revert, schema re-check.
6. Session A: schema conversation on drafts, suggestions as validated operations, draft sample trials.
7. Benchmark: five fictional notes with expected answers, scorer, `scripts/bi_ingest_benchmark.py`.

**Verification.** Clean worktree at `91e23651`: ruff clean, 1074 files formatted, mypy clean (808 files),
pytest 4237 passed, 34 skipped. Earlier pushes had single flakes under load (`test_multi_agent_ui`,
`test_memory_notes_ui`, `test_bi_cards_ui` dashboard order) that passed alone. Local `.mypy_cache` in the main
checkout can be stale (5 errors in untouched `control_plane` / `workflow` files); the clean run is the truth.

**Not done / owner actions.**
- No real model has run on the AI path or the sessions; every test uses a scripted model. Live trial: restart
  Agent Web on the new code (check `/api/activity` first), add a fictional note as UNCLASSIFIED (or approve
  INTERNAL for the model in Settings), run 試跑, then `scripts/bi_ingest_benchmark.py run --config <host json>
  --dataset <name>` (never commits; report under `<workspace>/bi/benchmarks/`).
- The domain owner should review `tests/fixtures/bi_ingest_benchmark/*.expected.json`.
- Not built: PDF/OCR sources, multi-user permissions, configurable chunking/fact policy in methods, an agent
  import tool. The old 「匯入 CSV」 tab still exists beside 「建立與匯入」.

**Next.** The owner's live trial and benchmark review; then decide whether to retire the old 「匯入 CSV」 tab and
whether to add PDF text.

## Retries, #248, graphify and the push of verified main (2026-10-27, Claude Code)

- Pushed to `origin/main` after full verification of 4a245bc4 in a clean worktree (`C:/aepci-wk/vh-4a245bc4`):
  ruff check, ruff format --check, mypy (787 files) clean; pytest 4169 passed, 34 skipped.
- Commits: 0bce059f Atlas integration proposal v0 (docs only); 60224666 read-only sub-agent retried up to its
  `max_retries` (`Failure.retryable` only, 30 s of the time limit left); 0054e92b gateway settings replace retried
  on Windows `PermissionError`; 71fe9c7d graphify wiring (see below); 4a245bc4 #248 (stale-reply guard in
  `biLoadCards` / `biLoadDashboard`, BI UI tests wait for the settled state). Rows in `docs/TASKS.md`.
- Live state: the multi-agent switch is on in `host.json`, `platform/knowledge-researcher@0.1.0` is installed with
  `engineering/rs-knowledge@1.0.3`, Agent Web was restarted with no active work (code before these commits).
- graphify: `CLAUDE.md` `## graphify`, PreToolUse hooks in `.claude/settings.json` call `graphify` from `PATH`;
  `graphify-out/` and `.claude/settings.local.json` are git-ignored (decision `docs/DECISIONS.md` 2026-10-27).
  Each clone: `uv tool install graphifyy`, `graphify extract . --code-only` (about 12 minutes here),
  `graphify hook install` (not run: this session was not permitted to add git hooks). Symbol queries
  (`graphify explain "DelegationService"`) are precise; loose natural-language queries are not.
- Open, not reproduced: browser `profile_in_use` on a second start (row in `docs/TASKS.md` with what to record).
- Owner decisions waiting: delegation cancel contract; GUI/MCP `side_effect` classification; weekly report manifest
  wording and version bump; Atlas `/v1` slice 1 (`docs/proposals/ATLAS_INTEGRATION_V0.md` §9); BI Knowledge Case
  B–E (only Case A approved in Knowledge Strategy v1.3) and v1.3 §5.5, ADR-K11 rubric, §7.3.
- Next: the owner's live delegation trial (「請用 knowledge-researcher 查 …」) after checking `/api/activity`, then
  the live baseline; restart Agent Web on this code first (rule 19: check `/api/activity`).

## Multi-agent V1: Agent Web / Telegram presentation, Settings switch, baseline benchmark (2026-10-27, Claude Code)

- Commits on main (see `git log`); not pushed, Agent Web not restarted, no real bot or hardware, live benchmark
  not run. Row in `docs/TASKS.md` (Multi-agent section); decision `docs/DECISIONS.md` 2026-10-27 "Multi-agent V1:
  what the person sees…"; contract subsection at the end of `docs/CONTRACTS.md`; user guide §4.12.
- Built: sub-agent lines in the live progress (`turn_progress.delegation_started` → `SubAgentProgress`), the
  collapsible 委派紀錄 under answers (`host_runtime/delegation_record.py`, `ConversationMessage.delegations`),
  Telegram status lines and reply record, Settings 「多 Agent 委派」 (`host_runtime/multi_agent_switch.py`,
  `/api/settings/multi-agent`), `benchmarks/multi_agent_v1` (7 scenarios, fake mode in tests, live mode for the
  owner, mock CMP180).
- The core wires the hook (2a8d5bda): `DelegationService` calls `delegation_started`, sets the line as the
  sub-run's `TURN_PROGRESS` and calls `finish(status)`; the 委派紀錄 and Telegram record read the tool's host data.
- Verification on the committed code (72bde036, 1b2acce0): ruff check, ruff format --check, mypy (786 files)
  clean. Full pytest, project venv: 4191 passed, 7 skipped. `C:/aepci-wk/venv`: 4163 passed, 34 skipped, 1 failed
  (`test_bi_dataset_platform.py::test_the_publish_body_has_its_own_limit…`, ConnectionAbortedError while both
  suites ran together; passes alone). Fake benchmark: 7/7. Browser screenshots: `.scratch/multi-agent-ui/`.
- The Settings card names the docs as text (no links): the page must not contain any external URL
  (`test_the_page_fetches_nothing_from_anywhere`).
- Next: the owner's live baseline (README "Live mode": switch on in Settings, check `/api/activity`, restart,
  run `run.py --mode live`), then set thresholds. Before a restart, check `/api/activity`.

## Multi-agent V1 core delegation (2026-10-27, Claude Code)

- Commits on main: ef0c94a0 (contract), 5d844036 (flag + profile fields), 2a8d5bda (code + tests), then docs; not
  pushed, Agent Web not restarted, no real model, Bridge or hardware used. Row in `docs/TASKS.md`; decision
  `docs/DECISIONS.md` 2026-10-27 "Multi-agent V1 core delegation"; user guide §4.11.
- Verification: ruff, format, mypy clean (on the exact commit content in a clean worktree). Full pytest, project
  venv: 4166 passed, 7 skipped, 2 failed (`test_bi_cards_end_to_end_in_a_browser`,
  `test_health_and_bad_requests_over_http`), both pass alone; `C:/aepci-wk/venv` (host_runtime from the repo):
  4140 passed, 34 skipped, 1 failed (the same browser test), passes alone. Runs were concurrent with the UI
  agent's uncommitted work. `tests/test_delegation.py` 30 passed in both venvs.
- Live check (owner, after checking `/api/activity`): `host.json` `"multi_agent": {"enabled": true}`; copy
  `agents/examples/knowledge-researcher.json` to `<workspace>\assets\agents\platform__knowledge-researcher__0.1.0.json`
  and put your vault's exact identity in `knowledge`; restart Agent Web; ask 「請用 knowledge-researcher 查
  <vault 裡的問題>」. Expect one `agent__delegate` call, the answer from the result, `/api/activity`
  `delegations: 1` while it runs, and an `agent_delegation` telemetry run under the turn.
- Open: no cancel button; `max_retries` not read; sub-run Workflow runs go to the session ledger, not the local run
  history; GUI / MCP tools are not offered to sub-agents until their `side_effect` is decided.

## Multi-agent Phase 0.5 part B: P0-2, a side effect at most once per turn (2026-10-27, Claude Code)

- Commits on main (code+tests 825a5cff, then docs); not pushed, Agent Web not restarted. Row in
  `docs/TASKS.md` (Multi-agent section); decision `docs/DECISIONS.md` 2026-10-27; AGENTS.md rule 21;
  `docs/CONTRACTS.md` (`HostTool.side_effect`, `ConversationToolExecution.replayed`); telemetry contract.
- `src/agent/turn_effects.py` + `Gateway.converse` / `_converse` / `execute_workflow`: a succeeded
  side-effecting call is not executed again in the same turn (retry pass and nested runs included); the
  model gets the earlier outcome marked `replayed`. Tests `tests/test_turn_effects.py` (12).
- Verification: ruff check, ruff format --check, mypy (779 files) clean. Full pytest, project venv:
  4133 passed, 7 skipped, 5 failed — 2 in `test_harness_cross_domain.py` against part A's then
  uncommitted work (pass after its commit), 2 business-card store tests and the bi_cards browser test,
  all passing when re-run alone. `C:/aepci-wk/venv` (host_runtime from the repo): 4110 passed, 34
  skipped, 1 failed (`test_bi_cards_ui` browser test; passes re-run alone and in a clean worktree with
  this change). The two full runs ran concurrently with part A's runs (about 65 min each).
- Next: V1 Phase 1 (`AgentProfile` extension). Before `agent__delegate` offers GUI or MCP tools to a
  sub-agent, decide their `side_effect` (today unguarded: identical GUI actions are also used to poll).

## Multi-agent Phase 0.5 part A: G5 suite and G4 bookkeeping (2026-10-27, Claude Code)

- Gate 0 was approved 2026-10-26 (`docs/DECISIONS.md` "Multi-agent Gate 0"). Part A is committed on
  main, not pushed, Agent Web not restarted. Row in `docs/TASKS.md` (Multi-agent section).
- `tests/test_harness_cross_domain.py` (55 tests, fakes only): conversation, Knowledge, Workflow and
  Coding through their real adapters; failed Host check never `validated`, G1, G2, claim check, G4
  output cut notes, bounded retries, honest `needs_input`.
- Bug fixed (test first, no xfail): a Coding Harness run that failed its declared commands arrives as a
  refused capability (`repair_budget_exceeded`) and got no G1 note; `agent/harness_handoff.py`
  `HOST_CHECK_FAILURE_CODES` now marks it. Docs: `docs/HARNESS_DESIGN.zh-TW.md` (dev slice G4 done via
  U2/U3, the two meanings of "G4", §11.3), `docs/HARNESS_6_LAYER_STATUS.md` limits 151/150.
- Verification: ruff check, ruff format --check, mypy (779 files) clean; full pytest project venv
  4137 passed, 7 skipped, 1 failed; `C:/aepci-wk/venv` (host_runtime from the repo) 4110 passed,
  34 skipped, 1 failed. The two failures (`test_bi_cards_end_to_end_in_a_browser`,
  `test_powershell_fixture_uses_noninteractive_json_io` script timeout) ran under four concurrent full
  suites and pass alone in both venvs. The runs included part B's uncommitted working-tree changes.
- Next: part B (P0-2 idempotent side-effect retries, another agent), then Phase 1 (`AgentProfile`
  extension behind a flag). G6 (Agent Web proof) stays open.

## Multi-agent Phase 0 review, awaiting owner Gate 0 (2026-10-26, Claude Code)

- Docs only, committed on main, not pushed; no code, contract, permission, config or issue change.
  Source plan `docs/proposals/MULTI_AGENT_AUTO_DISCOVERY_v0_source.md` (verbatim); review
  `docs/proposals/MULTI_AGENT_PHASE0_REVIEW.md`; row in `docs/TASKS.md`.
- Stopped at Gate 0 as the plan requires. Next: the owner answers the review's §13 open questions
  (defaults: keep direct-to-main with no PR; G5 and P0-2 first; extend `AgentProfile`; no CLI-backend
  parents in V1; a sub-agent cap plus token logging, no cost cap before the baseline) and approves
  ADR-MA1–MA5. Then append the approved ADRs to `docs/DECISIONS.md` and start Phase 0.5 (G5
  `tests/test_harness_cross_domain.py`, P0-2 idempotency cache, G4 bookkeeping).
- Do not lift `profile_delegation_unsupported` (`src/host_runtime/profiles.py:73`) or add
  `agent__delegate` before Gate 0. Verification: none needed (docs only; no tests run).

## SDE weekly report keys every ticket by its GitHub Issue (2026-10-26, Claude Code)

- Commits on main (code+tests, then docs); not pushed, Agent Web not restarted, no Workflow run, no
  Outlook, the real workbook not written. Row in `docs/TASKS.md`; decision `docs/DECISIONS.md`
  2026-10-26 "Workflow 11 keys every ticket by its GitHub Issue…"; parity table at the end of
  `docs/PHASE_7_MIGRATION.md`.
- Cause: selection and keys came from the old `[GTM-n]` title key, so Issues filed on GitHub were
  dropped. Now keyed `#<number>`, the week's own sheet is the target (`sheet_target: week`), `SDE
  Assignee` is the fallback, days are Taiwan days.
- Verification: ruff check, ruff format --check and mypy (776 files) clean; full pytest project venv 4071 passed, 7 skipped; `C:/aepci-wk/venv` (host_runtime from the repo) 4043 passed, 34 skipped, 1 failed (the preview test asserted the chart title without matplotlib), fixed and re-run alone: 4 passed in both venvs.
- Owner check, no restart needed (writes only into the folder given):
  `.venv\Scripts\python.exe -m capabilities.weekly_report.preview --week 2026_43W --out $env:TEMP\aep-weekly-43W`
  (real: reads host.json, GitHub read-only, copies the workbook) and the same with `--fixture`
  (synthetic). Open `email.html`, `workbook-preview.xlsx` (sheet 2026_43W, Key links) and
  `plan.json`. Then, after the next restart (check `/api/activity` first), Telegram 「幫我執行 43W SDE
  weekly report」 → 「只看計畫」 → 確認執行.
- Open: the Workflow manifest still says "scratch sheet" (version bump needed); an older scratch
  sheet keyed `GTM-n` is not matched to `#n` (only with `sheet_target: temp`).

## A session remembers what it produced; task result summaries (2026-10-25, Claude Code)

- Commits a454ce8f (ledger, attach tool, run pictures), d258ff4d (docs), f3d934d7 (task result
  summaries), 21fed834 (docs) plus a TASKS/HANDOFF commit on main; not pushed, Agent Web not
  restarted, no real bot message, no Outlook, no Workflow run. Row in `docs/TASKS.md`; decisions
  `docs/DECISIONS.md` 2026-10-25 "A session remembers what it produced" and "Task result summaries,
  kept 30 days"; contracts `docs/CONTRACTS.md`; `AGENTS.md` 20; user guide §4.6.
- Verification: ruff, format, mypy (773 files) clean; full pytest project venv 4059 passed, 7 skipped;
  `C:/aepci-wk/venv` 4032 passed, 34 skipped.
- Owner check after the next restart (check `/api/activity` first): in Telegram 「幫我執行 43W SDE weekly
  report」 → 確認執行 → the run's reply ends with 「結果摘要」 and a 存成筆記 button, and
  `effort-chart.png` arrives as a photo; a few messages later 「把統計圖貼給我」 → the photo again (no
  path asked); 「剛剛算了幾項？」 → answered from the summary; tap 存成筆記 → 「已存成筆記（…）」. Agent Web:
  run it from the chat form → the chart shows under the result with 「結果摘要存成筆記」; 記憶 → 紀錄 →
  任務摘要 lists it (保留 30 天, 刪除).
- New files on the PC: `workspace\session-artifacts\*.json` (ledgers) and `task-summaries.sqlite`;
  both purged nightly after the retention.
- Not done: a summary is composed only for Workflow runs and turns with two or more successful tools;
  the condensing model call is used only when the outputs give fewer than two facts.

## A yes/no input says what each choice does (2026-10-25, Claude Code)

- Commit fef4eb67 plus a docs commit on main; not pushed, Agent Web not restarted, no real bot
  message, no Workflow run. Row in `docs/TASKS.md`; decision `docs/DECISIONS.md` 2026-10-25 "A yes/no
  input says what each choice does"; contract `docs/CONTRACTS.md` "Boolean choice labels"; `AGENTS.md` 18.
- Verification: ruff, format, mypy (769 files) clean; full pytest project venv 4047 passed, 7 skipped;
  `C:/aepci-wk/venv` 4019 passed, 34 skipped, 1 failed (`test_bi_schemas_ui.py`, untouched browser
  test, passed alone).
- Owner check after the next restart (check activity first, as below): 「幫我執行 43W SDE weekly report」
  → card line 「執行方式：正式執行（寫入週報、起草郵件）（預設）」; type 「只看計畫」 → 「已改：執行方式 =
  只看計畫（不寫入、不寄信）」; 「改成正式執行」 changes it back; 修改 → 執行方式 shows two buttons with those
  words, no Yes/No. Agent Web chat 「執行 sde-weekly-report」 → 執行方式 shows two radio options.

## Fewer questions in a Workflow run; activity before a restart (2026-10-25, Claude Code)

- Commits 397ea989 (prefill reading), 429e4b47 (Telegram card, stale taps/replies, Agent Web form),
  94de93d6 (`/api/activity`, `launcher.restart_blockers`) plus a docs commit on main; not pushed, Agent
  Web not restarted, no real bot message, no Workflow run. Row in `docs/TASKS.md`; decision
  `docs/DECISIONS.md` 2026-10-25 "Fewer questions…"; contract `docs/CONTRACTS.md` "Agent Web activity".
- Verification: ruff check, ruff format --check, mypy (768 files) clean; full pytest project venv 4024 passed, 7 skipped (`--basetemp=C:/aepci-wk/bt-pf`); `C:/aepci-wk/venv` (`host_runtime` from this repo) 3997 passed, 34 skipped (`--basetemp=C:/aepci-wk/bt-pfc`).
- **Restart procedure:** the local helper `.scratch/restart_web.py` (gitignored) now calls
  `launcher.restart_blockers` first and exits 2 listing the active items unless `--force`. The Agent Web
  running now predates `/api/activity`, so the check reports "activity unknown" until the restart that
  deploys this: for that one restart, check `/api/tasks` and that the owner is not in a Telegram flow,
  then pass `--force`.
- Owner check after that restart: 「幫我執行 43W SDE weekly report」 → no questions, one card with
  「Report week：2026_43W（從你的訊息）」 and 「Save the weekly mail draft：是（預設）」, buttons 確認執行 / 修改;
  type 「dry run 改成是」 → the card again with Dry run 是; tap an older message's Yes during a flow → 「這個
  按鈕屬於較早的問題，沒有採用。」; Agent Web chat 「執行 sde-weekly-report 43W」 → the form says 「已從你的訊息
  帶入：Report week = 2026_43W」 with optional fields folded; `GET /api/activity` with the page token shows
  `telegram_flow` while a card is open and `busy: false` after.
- Not done: values in a replied-to ordinary message (not a flow question) are read only by the model's
  run form; flow state is not persisted (decision explains why).

## Telegram delivery, reply context and claim-check fixes (2026-10-25, Claude Code)

- Commits bbe7297f, 910bc686, 3b928bff, 506a70d4, 8aa4acf0, ae1d5e6e, 7c6689af plus a docs commit
  on main; not pushed, Agent Web not restarted, no real bot message sent, no Workflow run. Row in
  `docs/TASKS.md` "Telegram delivery, reply context and claim-check fixes"; decisions
  `docs/DECISIONS.md` 2026-10-25; user guide §8.2.
- The 09:34 cause is narrowed, not proven: a 429 beyond the old 5 s retry, or a transport fault
  (the reply was the `sde-weekly-report` question flow; length and blank text are ruled out).
- Owner check after a restart (when `/api/tasks` is idle): 「幫我執行 43W SDE weekly report」 → the
  question flow arrives; if anything fails, `workspace\logs\agent-web-*.err.log` (newest) has a line
  `Telegram sendMessage refused: HTTP …` or `Telegram sendMessage failed …`; Reply on any bot
  message with 「再跑一次」 → the answer refers to that message; an answer like 「如果是已安裝
  Workflow，我會…」 has no 「（系統檢查：…）」 line; a very long answer arrives as `answer-<time>.md`.
- Verification: ruff, format, mypy clean; full pytest 4007 passed (project venv) and 3980 passed
  (`C:/aepci-wk/venv`), each with one browser BI test that failed only under parallel load and
  passed alone.

## BI dataset sharing slice 1, live-test fixes 1–5 (2026-10-24, Claude Code)

- Commits 66210d2b (credentials per install), d2c8ef56 (source line), 65de8cbe (no-change edit),
  44c62231 (unknown dataset 404), f03331fd (page opens on an existing dataset), plus a docs commit;
  not pushed, Agent Web not restarted, live data, user environment, registry, 141 and the gateway
  untouched. Row in `docs/TASKS.md` "BI dataset sharing slice 1: fixes from the live test";
  decisions `docs/DECISIONS.md` 2026-10-24.
- Verification: ruff check, ruff format --check, mypy (761 files) clean; full pytest project venv 3963 passed, 7 skipped (`--basetemp=C:/aepci-wk/bt-fx5`); `C:/aepci-wk/venv` 3935 passed, 34 skipped, 1 failed (`test_capability_shelf.py::test_removing_moves_the_file_to_a_dated_folder_and_refuses_shipped_assets`, untouched code; the file passed 9/9 when re-run alone, `--basetemp=C:/aepci-wk/bt-fx5c2`).
- Owner check after a restart (when `/api/tasks` is idle): BI 卡片 opens on the dataset chosen
  last; save a field with the same value → 「沒有變更」 and no new history line; a chat answer on
  a subscribed dataset always ends with 「資料來源：…」 (also Telegram); a second install with
  `-InstallRoot` (or `update.ps1` on one) prints 「This install keeps its shared_platform_token in
  AEP_SHARED_PLATFORM_TOKEN_<hash>」 and its host.json gets that mapping; the default install's
  host.json and saved values are unchanged. A non-default install that already enrolled under the
  legacy name keeps it until that mapping is removed and it is enrolled again.

## BI dataset sharing slice 1, Agent Web UI and publish route (2026-10-22, Claude Code, agent 3 of 3)

- Commits 97042163 (page), 6c706ac3 (line wrap), e5531ba5 (publish route) on main, plus a docs
  commit; not pushed, Agent Web not restarted, 141 and live data untouched. Row in
  `docs/TASKS.md` "BI dataset sharing slice 1: Agent Web UI and the publish route"; contract
  `docs/CONTRACTS.md` "Agent publish API"; user guide §6.8.2.
- Owner check after a restart (when `/api/tasks` is idle): Knowledge → BI 卡片 → 發佈到 Shared
  Platform on `demo` (team by default; 開放給全公司 needs the confirmation) → 「待審核」 until an
  administrator approves the first version → publish again → 「已發佈 v1.1.0」; on the second PC
  展開「已訂閱的資料集」 → 瀏覽平台上的資料集 → 訂閱 → open it: 「唯讀：… 發佈的 v…」, no import/edit.
- Next: the two-PC live test in `docs/TASKS.md` once 141 runs a platform from d39d0927+.

## BI dataset sharing slice 1, Agent side (2026-10-22, Claude Code, agent 2 of 3)

- Commit 58239639 on main (not pushed, Agent Web not restarted, 141 and live data untouched):
  subscribed read-only copies, `bi_dataset` sync installer, update badge and manual 「更新」,
  revoked access keeps the copy and marks it 已停止更新（無權限）, offline status, `/api/bi/subscriptions*`,
  `bi__query` cites the version. Contract `docs/CONTRACTS.md` "Agent subscriptions"; row in
  `docs/TASKS.md`. Agents 1 (platform, d39d0927, 25b2c640) and 3 (UI 97042163; publish route
  in `bi_cards_api.py` still being finished) own the rest.
- Next: the live two-PC test listed in `docs/TASKS.md` once 141 runs a platform from d39d0927+.

## Session model scope (2026-10-22, Claude Code)

- Commits d81fab8b (backend, Telegram, tests) and eee157fa (page) on main, plus a docs commit;
  not pushed, Agent Web not restarted, `host.json`, live data and the gateway on port 4000
  untouched. Row in `docs/TASKS.md` "Session model scope"; decision `docs/DECISIONS.md`
  2026-10-22; contract `docs/CONTRACTS.md` "Chat composer model choice"; user guide §4.2.1.
- Whatever a session does uses its model (Knowledge answers, Workflow drafting, cards, the
  conversation); Telegram chats use their own choice or the person's default (`/model`);
  schedules, the nightly job, experience review and the Knowledge page's jobs keep the Settings
  model. Each answer records and shows 「模型：<id>」.
- Verification: ruff, format, mypy clean; full pytest 3886 passed (project venv), 3859 passed
  (`C:/aepci-wk/venv`).
- Owner check after a restart (when `/api/tasks` is idle): choose `claude-sonnet-5` in a chat, ask
  something → 「模型：claude-sonnet-5」 under the answer; ask a Knowledge question in the same chat →
  the same model line; open a new chat without a pick → your default; Telegram: `/model` lists,
  `/model 2` chooses, the next answer uses it.

## BI cards: per-dataset schemas (2026-10-21, Claude Code)

- Commits 7d245e19 (backend) and f0759c94 (page) on main, plus a docs commit; not pushed, Agent
  Web not restarted, live data untouched. Row in `docs/TASKS.md` "BI cards: per-dataset
  schemas"; decision `docs/DECISIONS.md`; contract `docs/CONTRACTS.md` "Per-dataset schemas";
  user guide §6.8.1.
- Continued from a stopped agent's uncommitted draft. Kept: `catalog.py` (validation, install,
  resolve), the store binding, the per-dataset registry in import/search/detail/edit, the
  `schema_not_bi` refusal. Changed: the Dashboard for a non-BI dataset is a 200 empty state
  (`dashboard: false`, `code: no_dashboard`) instead of a 400; an immutable-version clash is 409;
  `GET /api/bi/schemas` lists types as `{name, label}`; added `GET /api/bi/schemas/example`
  and packaged `samples/` (`pyproject.toml`). UI, tests and docs were new.
- Verification: ruff, format, mypy clean; full pytest 3873 passed (project venv), 3846 passed
  (`C:/aepci-wk/venv`).
- Owner check after a restart (when `/api/tasks` is idle): Knowledge → BI 卡片: `demo` still shows
  its Dashboard; 安裝 schema → 安裝範例 schema（產品規格） → 用這個 schema 新增資料集 `spec` →
  Dashboard shows 「這個 schema 沒有 Dashboard」, no chat hint → 匯入 CSV the four example CSVs in
  order (suppliers, components, products, spec items) → open a 零組件 card; in chat, asking about
  dataset `spec` gets the 「不是 BI schema」 refusal.

## Chat composer model menu (2026-10-21, Claude Code)

- Commits 9e4b67f5 (backend) and 6b572b7c (page) on main, not pushed, Agent Web not restarted,
  `host.json`, live data and the gateway on port 4000 untouched. Row in `docs/TASKS.md` "Chat
  composer: backend selector on top, LLM model menu"; contract `docs/CONTRACTS.md` "Chat composer
  model choice"; decision `docs/DECISIONS.md` 2026-10-21; user guide 4.2 / 4.2.1.
- The backend selector is in the chat's top bar; the composer has an LLM model menu with what the
  approved Gateway lists, per conversation and remembered as the person's default, applied from
  the next message (no restart) through `SelectableModelClient` inside `ApprovedModelClient`.
- Verification: ruff, format, mypy clean; full pytest 3842 passed (project venv) and 3815 passed
  (`C:/aepci-wk/venv`).
- Owner check after a restart on this code (when `/api/tasks` is idle): the top bar shows
  「Configured LLM Gateway · Configured and ready」 left of 「as … on …」; the menu under the box
  lists the Gateway's models (`gpt-5.5 · Settings default` first); pick another, ask 「你是哪個
  模型？」, then open a new session: it shows `Your default`; Settings shows the default-model note.

## Windows installer fixes from a colleague's PC (2026-10-21, Claude Code)

- Committed on main, not pushed, no release built, Agent Web not restarted; this PC's real
  install untouched. Row in `docs/TASKS.md` "Windows installer fixes from a colleague's PC";
  namespace decision appended to `docs/DECISIONS.md`.
- `deploy/windows-preview/install.ps1`: namespace always `engineering` (`-Namespace` accepted,
  ignored with one line; an existing `host.json` is corrected); SHA-256 via .NET instead of
  `Get-FileHash`; `.cmd` wrappers clear `PSModulePath`; a default `python` that is not 3.12 falls
  back to `py`'s 3.12, otherwise an actionable English + 中文 error; after install/update a
  running Agent Web gets a printed restart reminder (nothing is stopped). Manual:
  `INSTALL.zh-TW.md` §2, §4 「停止／重新啟動 Agent Web」, §9; `USER_GUIDE.zh-TW.md` §16.1.
- Next: build a release with these scripts (`scripts/release_windows.py` as before) and send it;
  colleagues already broken run the new bundle's `update.cmd` (or `install.cmd -Actor <id>`).
  Note: `update.ps1` still stops a running Agent Web itself before updating (unchanged, documented
  in INSTALL §5).

## BI release for the owner's boss (2026-10-21 15:50, Claude Code)

- main ee730407 pushed; release `dist/releases/20261021-1550-ee730407/` and a copy with
  `BI_DEMO.zh-TW.md` (demo steps) in `S:\AE\leo\`. Agent Web on this PC runs it; the `demo` BI
  dataset is loaded. Verification: see `docs/TASKS.md` (the last full suite ran on 8305b57e; ee730407
  ran lint, types and the related 590 tests). Watch CI on ee730407.
- BI scope is v1.3 Case A on the robotics sample (schema v4 as `bi.schema/v1.1`); priority is not
  stored (#222). Not built: K06 document extraction, K08 hybrid retrieval, K02/K10 benchmark,
  K09 API, K15 Obsidian adapter, accepting/rejecting proposals in the UI, a mapping editor.
- Next: CI result; owner feedback from the demo; then the v1.3 follow-ups in that order.

## BI Knowledge Case A backend (2026-10-21, Claude Code)

Owner approved Knowledge Strategy v1.3 for Case A only, with the robotics sample
(`tests/fixtures/robotics_kb_sample/`, schema v4, 104 cards) as demo data (decision
`docs/DECISIONS.md` 2026-10-21 "BI Knowledge Case A is approved and built on `bi.schema/v1.1`…";
contract `docs/CONTRACTS.md` "BI cards API and capability"; row in `docs/TASKS.md`).
Commits on main, not pushed, Agent Web not restarted, live data untouched. The backend files
landed in the front-end agent's commit 136c5cca (shared index), then 5addaea4 and 227f911c.

- Built: `src/capabilities/bi_cards/` (registry `bi_schema_v1_1.json` from
  `scripts/build_bi_schema_v1_1.py`, SQLite store with field provenance at
  `<workspace>/bi/<dataset>/bi.sqlite`, CSV preview/apply/undo, demo loader, dashboard, the
  `bi-cards/query@1.0.0` capability and the `engineering/bi-knowledge@1.0.0` Skill shipped on),
  `src/host_runtime/bi_cards_api.py` (`/api/bi/*`), `src/host_runtime/bi_cards_tools.py`
  (`bi__query`). UI: Knowledge → BI 卡片 (front-end agent, `web_page.py`).
- Demo (after restart on this code, when `/api/tasks` is idle): Knowledge → BI 卡片 → 載入示範資料
  (104 cards) → Dashboard (robotics: §6 BMS and 下線測試 red; §10 快充 trend no solution; §19
  BMS no opportunity; §18 5G private network no active opportunity; §16 大銀 no ecosystem;
  §14 technologies without Concept) → import `tests/fixtures/robotics_kb_sample/tools/samples/
  robotics/application_robotics.csv` to see 優先度 ignored and all rows unchanged → edit a field,
  re-import to see human_kept → chat 「哪些應用對手有方案、我方沒有？」 (needs `assets
  install-bundled` so the Skill is on; answers cite `[卡片 …]`).
- Not done (deferred, see the decision): proposal accept/reject routes, mapping explode /
  derive / compose, DQ-7 conflict records, vault adapter, PostgreSQL backend, Cases B–E.
- Next: owner live demo check; then release.

## BI 卡片 UI, Knowledge Strategy v1.3 Case A (2026-10-21, Claude Code)

The Agent Web side of Case A is in `src/host_runtime/web_page.py` (commit 136c5cca, not pushed,
Agent Web not restarted): Knowledge tab → sub-tab 「BI 卡片」 (beside 「知識庫維護」, the vault
pipeline): dataset / domain bar (robotics default) with 載入示範資料; Dashboard (`/api/bi/dashboard`,
sections 6, 10, 19, 18 first and open; red / amber flag rows with text badges; matrix; funnel;
cells naming a card open it); 卡片 (type filter, search, review badge 「範例資料／待驗證」, detail
with field class 事實 / 判斷 / 衍生, source and time, links with missing targets, pending
proposals, history; edit with `base_version` + 理由, 409 `stale_edit` shows who / when / current and
offers a reload); 匯入 CSV (UTF-8 / BOM file → preview → mapping table and chips → per-row diff with
`human_kept` → 確認寫入 for the ticked rows → 復原). The API is the backend agent's
(`docs/CONTRACTS.md` "BI cards API"); the UI was checked once against it (demo load: 104 cards,
dashboard and a card detail render). Test: `tests/test_bi_cards_ui.py` (stub of the contract
behind a proxy to the real Agent Web; screenshots `.scratch/bi-ui/`).

Owner check after a restart on this code: Knowledge → BI 卡片 → 載入示範資料 → Dashboard → click a
red-gap application → edit a field with a reason → 匯入 CSV with a robotics CSV → 確認寫入 → 復原.

## #233 Agent Web follow-ups (2026-10-21, Claude Code)

Commits on main after a7f72e3c (89d8389a … the docs commit), not pushed, Agent Web not restarted,
live data only read. All ten items of #233 fixed (row in `docs/TASKS.md`; decision
`docs/DECISIONS.md` "Pending changes leave out draft install cards; undoing a health fix reopens
its finding at once (#233)"). Item 10's causes are inferred: the model's tool arguments are not
stored anywhere (only names and codes), so the `cards__list` cause (most likely `limit` > 200) could
not be confirmed; storing scrubbed arguments would make the next such case diagnosable.

Owner re-check (after `/api/tasks` is idle and Agent Web restarted on this code): (1) New session,
then type and press Enter at once: Send is disabled briefly, the message lands in the new session;
(2) open 記憶 → 資料 → a person's 歷史, go to 對話, press 「為什麼？」 → 到記憶頁修改或刪除: 偏好 shows at
once with 「開啟中…」/「更新中…」; (3) 待確認 → a health card's fix → 復原: the card is back at once;
(4) propose a rule to ask (「以後都先問我…」): the card says 「照這條先問你」; (5) Settings → Teams
on a platform-connected PC: field and Save disabled with "Not used…"; (6) a draft revised twice shows
"draft edit 3"; (7) a coding Harness turn ends with 「整理回答中…」.

## Release 20261021-0810-607a59ea and where work stands (2026-10-21, Claude Code)

- main 607a59ea is pushed and CI green; Agent Web on this PC runs it. Release
  `dist/releases/20261021-0810-607a59ea/` (SHA-256 in `docs/TASKS.md`), commented on #218, tag local.
- Live re-checks done: M2–M4, B1, M5, B3 timing (see `docs/TASKS.md`). Open: B2 live (needs new
  signature mail), Telegram `/why` live, loans 06/06b live (owner present for portal/C4C login).
- (Now #233, fixed above.) Known UX issues: 「為什麼？」 links show the old place for ~5 s with no indicator; a
  health card disappears after 復原 until the next check; preference card effects text always says
  「不再詢問」; Outlook read failures are swallowed without a log (`OutlookMail._call`).
- Next: #220 API-level trial (running), #219 141 reboot test at a quiet time (evening/weekend, not
  during office hours), then the remaining owner-decision issues (#212, #215, #216, #217).

## Live-check fix B3: the slow 記憶 page (2026-10-21, Claude Code)

Commits on main, not pushed, Agent Web not restarted, live data untouched. Decision
`docs/DECISIONS.md` 2026-10-21 "The memory page reads the installed manifests and sets up a memory
database once (B3)"; row in `docs/TASKS.md`; `?only=` in `docs/CONTRACTS.md` (Memory page).
- Cause: each overview rebuilt the memory registry five times (all ~70 installed manifests parsed
  each time) and set up the memory database on every `MemoryService` (46 opens of `memory.sqlite`).
- Fix: manifests/registry cached by file signature (`memory_spaces`, `one_scan`), setup skipped while
  the database file is unchanged, `MemoryService.session()` (one connection per request),
  `GET /api/memory/overview?only=…`; the page shows 「載入中…」/「更新中…」 per pane, 「…」 counts, an
  inline error with 重試, and reloads only what an action changed.
- Fixture (owner's sizes, synthetic): overview 1.66 s → 0.13 s. Verification: see `docs/TASKS.md`.

Owner re-check: (1) `/api/tasks` idle; (2) restart Agent Web on this code; (3) open 記憶: each tab
shows 「載入中…」 and counts 「…」 briefly, then the data (expect ~1–2 s at most instead of 7–18 s);
(4) DevTools → Network: `/api/memory/overview` well under 2 s; (5) delete and 復原 a note, edit a
preference, 保留原值 on a proposal: each finishes in about a second, the request is
`/api/memory/overview?only=notes,spaces` (or the matching sections), other tabs keep their data;
(6) 更新 still reloads everything; (7) switch the business-cards Skill off and on in Capabilities: 資料
shows 已關閉/已開啟 at once (the cache follows the files).

## Live-check fixes B1 / B2 (2026-10-21, Claude Code) — beside M5

Two commits on main, not pushed, Agent Web not restarted, live data untouched (decisions in
`docs/DECISIONS.md` 2026-10-21, rows in `docs/TASKS.md`):
- **B1** `install-bundled` now refreshes a shipped manifest AEP wrote and nobody changed (ledger
  `workspace/bundled-assets.json`; on/off kept; "updated …" in the output); files from before the
  ledger are refreshed once with a copy in `workspace/replaced-assets/`. 資料 shows an installed
  manager without its declaration as 「Skill 已安裝但版本較舊…」, not 「無主」.
- **B2** a harvested signature of a stored person with nothing new is `already_stored_people`, not
  a candidate.

Owner re-check: (1) check `/api/tasks` is idle; (2) run `update.ps1` (or `aep-host assets
install-bundled --bundle <bundle>`): the output lists `updated skill engineering/business-cards@1.0.0`
and where the earlier file was kept; (3) restart Agent Web; (4) 記憶 → 資料: `contacts/org` shows
已開啟, no 「無主」; (5) a business-card turn (e.g. 「WNC 的人有哪些筆記？」) offers `notes__search`;
(6) 「整理 WNC 的簽名檔」 (or 「重新整理 wnc.com.tw 的簽名檔」): KevinRK Chen is said to be already
stored, not offered.

## Accumulated memory M5: memory quality tools (2026-10-21, Claude Code) — latest

**Goal / scope:** M5 of `docs/phases/ACCUMULATED_MEMORY.md` (§7–§8): freshness rules as data, a nightly
and on-demand memory health check, 「為什麼這樣做」, settings. Spec §16 "M5 as built"; decision
`docs/DECISIONS.md` 2026-10-21 "Accumulated memory M5"; contracts `docs/CONTRACTS.md` (Memory quality);
user guide §4.10. Not pushed; Agent Web not restarted; live data untouched.

**Done (commits on main):** 1ae662ef "Add memory health check and "why" to the Memory Service and Agent
Web" (code + tests); then the docs commit.
- `MergeRules.freshness` (`FreshnessRule`); `contacts/org`: 12 months 「{name} 是否仍在職？」, sync 30 days.
- `src/memory/health.py` (`run_check`, table `health_findings`, settings in `meta.health_settings`);
  `src/host_runtime/memory_health.py` (`MemoryHealth`: per actor, presses, bounded contradiction
  question via `review_model` + `structured_call`, telemetry counts only); `AgentWeb.nightly_tick`
  (health check every night after 02:00, then the review; `ReviewReport.memory_health`).
- `CardStore.merge_people/confirm_active/duplicates/last_seen`; `Preferences.mark_used/last_used`;
  `MemoryService.set_meta`, `meta.actor`.
- 「為什麼」: `ConversationMessage.memory_used`, `src/host_runtime/memory_why.py`,
  `GET /api/memory/why`, the 「為什麼？」 button under answers, Telegram `/why`.
- Memory page: health cards in 待確認 (「立即檢查」), settings in 紀錄.

**Verification:** ruff check, ruff format --check, mypy clean; full pytest project `.venv` 3743 passed,
9 skipped, 2 failed (telegram settings load flake, passes alone; one new test's tie-order assumption,
fixed); CI-like `C:/aepci-wk/venv` (this repo, `.[dev,office]`, `--basetemp=C:/aepci-wk/bt-m5`):
3726 passed, 34 skipped, 0 failed. Real-browser test `tests/test_memory_why_ui.py` passes; screenshots
`.scratch/memory-why/`.

**Live check (owner, after `/api/tasks` is idle and Agent Web is restarted on this code):**
1. 記憶 → 待確認 → 「立即檢查」: health cards appear with 「健康檢查：…」 tags (e.g. 可能重複, 很久沒出現).
2. On a duplicate: 「合併（保留第 1 筆）」 → 復原 in the notice brings both back; 「不是同一人」 is not asked again.
3. On a stale contact: 仍在職 / 已離職 (復原). On a preference contradiction: 停用第 1 條 → 復原.
4. 紀錄 → 健康檢查: change months/days, 儲存; switch off → 「立即檢查」 is disabled.
5. Ask 「WNC 組織圖」 with a saved preference: the answer shows 「為什麼？」; its links open the item on 記憶.
6. Telegram: send a question, then `/why`.
7. Next morning: Reviews' latest report has a "Memory health" section (counts only); Tasks lists
   "Memory health check (nightly)".

**Open / risks:**
- A concurrent session committed B1 / B2 (above) on main meanwhile; its manager state `outdated` is
  not an orphan for the health check either (only `missing` is).
- 「整理進度停住」 uses `sync_state.updated_at`; incremental passes with no new mail do not move it,
  so a quiet domain may be listed (a reminder only).
- Telegram `/why` is in memory, last turn per chat only. Merge always keeps 第 1 筆.

**Next:**
1. Owner live check above (and the M4 / M3 ones below).
2. M6 (cross-space reads, promotion to team knowledge) when the owner asks.

## Accumulated memory M4: the Agent Web memory page (2026-10-21, Claude Code)

**Goal / scope:** M4 of `docs/phases/ACCUMULATED_MEMORY.md` (§6, §3.6, §3.9): a 「記憶」 tab for the
signed-in actor. Spec §15 "M4 as built"; decision `docs/DECISIONS.md` 2026-10-21 "Accumulated memory
M4"; contracts `docs/CONTRACTS.md` (Memory page); user guide §4.9. Not pushed; Agent Web not restarted;
live data untouched. Telegram out of scope.

**Done (commits on main):** 336a0f08 "Add the memory page to Agent Web" (code + tests); then the docs
commit.
- `src/host_runtime/memory_page.py` (`AgentWeb.memory_page`): GET `/api/memory/overview`, `people`,
  `person`, `export`, `notes/export`; POST `proposals/decide` (保留原值 = `CardStore.edit(confirm=)`,
  改用新值 = the proposal's value; other spaces keep-only), `proposals/undo`, `preferences/edit`
  (`Preferences.edit`, M3 conflict check), `notes/edit`, `sync/reset`, `sync/restore`,
  `space/delete` (typed confirmation). M3's `/api/memory/delete` and `/undo` are reused. Every change
  `<actor> via web`; no model tool.
- `MemoryService`: `owned`, `overview`, `open_proposals`, `proposal`, `sync_overview`,
  `export_space`, `delete_space` (one transaction; observations' trigger dropped and re-created
  inside it), `deletions`; table `space_deletions` (no content).
- `memory_spaces.manager_states` → orphan flag; the 記憶 tab (待確認, 偏好, 筆記, 資料 with the
  contacts list and history, 同步進度, 紀錄 with retention, JSON export and delete).

**Verification:** ruff check, ruff format --check, mypy clean; full pytest project `.venv` 3725 passed,
9 skipped, 1 failed (`test_loan_reply_parity`: a concurrent session's commit e7247e3e changed
`loan_reply/queue.py` during the run; re-run alone: 16 passed); CI-like `C:/aepci-wk/venv` (points at
this repo, `.[dev,office]`, `--basetemp=C:/aepci-wk/bt-m4`): 3701 passed, 34 skipped, 0 failed.
Real-browser test `tests/test_memory_page_ui.py` passes; screenshots `.scratch/memory-page/`.

**Live check (owner, after `/api/tasks` is idle and Agent Web is restarted on this code):**
1. Left side → 「記憶」. The tab counts match what you expect.
2. 待確認: an Email proposal from a new card shows stored / new / 證據; press 改用新值, then 復原 in the
   notice, then 保留原值. The person's history (資料 → 開啟聯絡人 → 歷史) shows `<you> via web`.
3. 偏好: 修改 a rule into its opposite of another one → 取代舊的 / 兩條都留; 刪除 → 復原; 來源對話 opens
   the conversation at the message.
4. 筆記: search, tag and contact filters; 加標籤, 連結聯絡人, × to remove; tick two → 匯出選取（Markdown）.
5. 資料: spaces with counts; an uninstalled manager shows 「無主」.
6. 同步進度: 重新整理 `wnc.com.tw` (asks first) → 復原上次重設.
7. 紀錄: 匯出 JSON of 筆記. Only on a test actor: 刪除資料… needs the space name; a row appears under 刪除紀錄.

**Open / risks:**
- Deleting `contacts/org` does not delete the old `business-cards/<actor>/cards.db` and its backups
  (said on the page); owner to decide.
- Space retention is display-only; no expiry processing. No date-based conversation retention.
- Spaces without a manager adapter can only keep the stored value.
- A concurrent session is committing on main (e7247e3e); only M4 files were committed here.

**Next:**
1. Owner live check above (and the M3 one below).
2. M5 quality tools (freshness, nightly health check, 「為什麼這樣做」).

## Accumulated memory M3: preferences and notes (2026-10-21, Claude Code)

**Goal / scope:** M3 of `docs/phases/ACCUMULATED_MEMORY.md` (§5, §3.9, §9; owner decisions §10.3
「按一下才存、Agent Web 可管理」 and §10.8). Spec §14 "M3 as built"; decision `docs/DECISIONS.md`
2026-10-21 "Accumulated memory M3"; contracts `docs/CONTRACTS.md` (Preferences and notes); user guide
§4.8. Not pushed; Agent Web not restarted; live data untouched. No memory page yet (M4).

**Done (commits on main):** 2228b1e6 "Add preferences and notes to the Memory Service and the
chat" (code + tests `tests/test_memory_preferences.py`, `tests/test_memory_notes.py`,
`tests/test_memory_notes_ui.py`, screenshots `.scratch/notes-ui/`); then the docs commit.
- Host-managed spaces `personal/preferences` / `personal/notes` (`src/memory/personal.py`,
  `preferences.py`, `notes.py`; `SpaceTx.changed_after`; registries declare them first).
- `src/host_runtime/personal_memory.py`: `memory__propose_preference`, `memory__propose_note`
  (once per conversation; Telegram per chat per day), `notes__search` (declared read or
  `NOTES_ASKED`), `mm-` cards with `ends_turn=false`, the press saves (deterministic conflict check →
  取代舊的 / 兩條都留 / 不用), `Gateway.turn_memory` injects the in-use Skills' preferences (≤ 12,
  ≤ 1,600 chars) and records `preferences_used`; Agent Web routes `/api/memory/notes/save`, `/delete`,
  `/undo`, `GET /api/memory/notes|preferences`.
- Agent Web: 📝「存成筆記」 in each answer's tools (and the context menu), 「存選取內容」 for a selection;
  Telegram: one branch puts the answer before a non-ending card; HTML org chart: 「相關筆記」.
- The business-cards Skill declares a `personal/notes` read (its manifest digest changes).

**Verification:** ruff check, ruff format --check, mypy clean; full pytest project `.venv` 3707 passed,
9 skipped, 0 failed (E2E-01 included; one earlier run caught the turn-renderer harness, fixed by
moving the notes script out of the Turn groups section); CI-like `C:/aepci-wk/venv` (confirmed
pointing at this repo, `.[dev,office]`, `--basetemp=C:/aepci-wk/bt-m3`): 3681 passed, 34 skipped,
1 failed (`test_agent_web.py::test_capability_workspace_is_interactive_in_a_real_browser`,
real-browser load flake; re-run alone with `tests/test_memory_notes_ui.py`: 3 passed).

**Live check (owner, after `/api/tasks` is idle and Agent Web is restarted on this code):**
1. Say 「WNC 組織圖，執行時不需要問是否包含在職人員」: the answer comes first, then the card
   「要把這條記成『名片／組織圖』的偏好嗎？」. Press 存成偏好 → 「已存成偏好（p-…）」.
2. New conversation, 「WNC 組織圖」: it should not ask about current staff. (The answer JSON /
   stored message carries `preferences_used`.)
3. Say 「執行時要問是否包含在職人員，記成偏好」 and press 存成偏好: the card asks first with both rules;
   try 取代舊的.
4. Hover an answer → 📝: 「已存成筆記（n-…）」 and 復原. Select a sentence → 「存選取內容」.
5. 「我之前有記過什麼關於 WNC 的？」: the answer cites `[筆記 n-…]`.
6. Telegram: state a rule; the reply ends with the card and 存成偏好 / 不用 buttons.
7. A note linked to a contact (from an Agent proposal with `contacts/org:person:<id>`) shows under
   「相關筆記」 on that person's card in the HTML org chart.

**Open / risks:**
- While the business-cards Skill is on, `notes__search` is offered every turn (its declared read);
  narrow it if the owner prefers (spec §14.5).
- Conflict check is wording-based (same subject, opposite polarity); different wordings of the same
  rule are not caught (M5 health check).
- One-click note saving is Agent Web only; Telegram has only the Agent's proposal card.
- Linking a one-click note to a contact needs the M4 page (or an Agent proposal with `entities`).

**Next:**
1. Owner live check above.
2. M4: the memory page (preferences and notes sections use the existing APIs).

## Loan replies 06 / 06b without n8n (2026-10-20/21, Claude Code)

**Goal / scope:** owner request 2026-10-20: port rs_workflow_system 06 (loan_scan) and 06b
(loan_process) as two AEP Workflows; drafts by default, optional send with one approval per
message; no schedule. Not pushed; Agent Web not restarted; no real mail, portal or send touched.

**Done (commits on main):**
1. a982725f Ported jobs (`src/capabilities/loan_reply/`: rules, templates, queue verbatim plus
   declared replacements; scan, process with seams; `process_one` = `look_up` + `draft_reply`);
   source tests vendored as the oracle (`tests/test_loan_*_source.py`, `tests/loan_oracle.py`).
2. eb96b149 `LoanBridge` (Outlook HTML listing with SMTP sender, reply drafts never sent, Edge
   profiles per system, Playwright selectors via page script and DevTools input).
3. 7e8bfe2c Workflows `engineering/rs-loan-customer-block-scan` (`/run 6`) and
   `engineering/rs-loan-queue-reply`; capabilities `loan/scan-mail` (read), `loan/enqueue`
   (write), `loan/look-up` (read), `loan/draft-replies` (write), `loan/offer-send` (write),
   `loan/send-reply` (external_side_effect, never installed); `ls-` send cards
   (`host_runtime/loan_reply_cards.py`, Agent Web only, one press one mail); `follow_up` /
   `action_cards` result keys drawn by Agent Web (run form, cards) and Telegram (summary, cards,
   `/run` button); shipped switched off (`assets.shipped_off`).
4. (this commit) Docs: RS_WORKFLOW_MIGRATION (row, decisions, question 5 closed, real-PC
   checklist), CONTRACTS parity record, USER_GUIDE §9.3, TASKS. The DECISIONS entry
   ("Loan replies 06 / 06b") was swept into d7adf4c0 by a concurrent session's commit.

**Verification (2026-10-21):** ruff check, ruff format --check, mypy (709 files) clean. Isolated
worktree of 7e8bfe2c with `C:\aepci-wk\venv` (confirmed editable at this repo, `.[dev,office]`
reinstalled, `--basetemp=C:/aepci-wk/bt-loan`): 3656 passed, 34 skipped, 0 failed. Project
`.venv` full run on the shared tree: 3681 passed, 9 skipped, 0 failed. New tests: 162 vendored
source cases, `test_loan_reply_workflows.py` (19), `test_loan_reply_send.py` (12),
`test_loan_reply_parity.py` (16), `test_loan_bridge.py` (9, one real headless Edge).
Note: another session works on accumulated memory M3 in this same working tree; its files were
not part of these commits.

**Open / risks:**
- Unproven until the owner's company-PC run: Outlook COM HTML listing and reply draft, the
  selectors on the real portal and SAPUI5 C4C (fill via `Input.insertText`, Enter via
  `Input.dispatchKeyEvent`), Entra account tile in the persistent profile, screenshot size
  (viewport, not full page).
- The reply goes to whoever Outlook's Reply addresses (the approval notice's sender), as in the
  source; the owner should confirm that is the intended recipient before pressing 寄出.
- Send cards are Agent Web only (as mail cards); pressing in Telegram would be a new decision.

**Next:**
1. Owner live check: `docs/phases/RS_WORKFLOW_MIGRATION.md` "Loan replies: what the owner
   verifies on the company PC" (switch on, settings, dry runs, one real run, one card press).
2. If the owner wants a timed scan: Schedules > rs-loan-customer-block-scan, effect `write`.

## Accumulated memory M2: sync state and the incremental org chart (2026-10-20, Claude Code)

**Goal / scope:** M2 of `docs/phases/ACCUMULATED_MEMORY.md` (§3.3, §4, §9; owner decision §10.1:
the org chart reads new mail first, new people still need confirmation; no nightly harvest).
Spec §12 "M2 as built". Not pushed; Agent Web not restarted; live data and real mail untouched.

**Done (commits on main):**
1. 9f6a5080 Generic sync state in the Memory Service: tables `sync_state`, `sync_history`
   (created on open, no migration); `SpaceTx`/`MemorySpace` `sync_state`, `sync_states`,
   `advance_sync` (only forward; reset needed before another extractor version), `reset_sync`,
   `restore_sync`, `sync_history`; only for spaces declaring the `sync_state` kind. `contacts/org`
   declares it (only the business-cards manifest digest changes).
2. bbaeb442 Incremental harvest (`capabilities/business_cards/harvest.py`): key
   `(contacts/org, "mail:<folder>", <domain>)`; first pass = full scope; then from the last
   processed message minus 1 day, ids at the boundary and observed messages skipped; scope caps
   the window; unreadable / deferred messages hold the state back; `EXTRACTOR_VERSION` change or
   `full: true` (「重新整理」) re-reads the full scope (extractor change re-reads stored mail, lists
   only people whose reading changed). `scan_note` names the window. `harvest-signatures` takes
   `company` instead of `domain`. `org-chart` `harvest_first` (capability default false; the Skill
   procedure asks for true): one call harvests the company's domains, returns `harvest`
   candidates (never stored, not on the chart) or `harvest_note`, and draws the chart.
3. 835e4867 Docs: spec §12, CONTRACTS, DECISIONS, BUSINESS_CARDS §5/§6, TASKS, USER_GUIDE §4.7.
4. f4d491ca Owner rule 2026-10-20 (closes the M1 open point; spec §3.8.3 "新證據", §13): a value
   the person set is touched only by new evidence: a card image never observed for that person
   (cards carry no evidence date; re-scans and cards without an image are old evidence) or a
   signature sent after the day of the person's change. Old evidence is ignored silently. New
   evidence updates title / department / division / business group / honorific / phone / ext /
   mobile / fax / address directly (history `new card <ref>` / `newer email <id>`, undoable);
   the email and the other fields stay proposals. One-time cleanup on first open (after the
   `cards.db` migration) dismisses open proposals from old evidence (kind `proposal_rule`,
   undoable with `cards__undo` on its change id; meta marker so it runs once).
5. (this commit) Docs for 4: spec §3.8 / §11.4 / §12.4 / §13, CONTRACTS, DECISIONS, BUSINESS_CARDS
   §2, TASKS, USER_GUIDE §4.7.

**Verification for 4 (2026-10-20):** ruff check, ruff format --check, mypy clean; full pytest
project `.venv` 3461 passed, 9 skipped, 2 failed (one conversation test then adapted to the rule,
one real-browser timing test; both re-run alone: passed); CI-like `C:epci-wkenv`: 3438 passed, 34 skipped, 0 failed.
New: `tests/test_business_cards_new_evidence.py` (5).

**Verification for 1–3 (2026-10-20):** ruff check, ruff format --check, mypy clean. Full pytest project
`.venv`: 3453 passed, 9 skipped, 1 failed (`test_schedule_web` real-browser timing under load;
re-run alone 5 passed). CI-like `C:epci-wkenv` (confirmed pointing at this repo,
`.[dev,office]`, `--basetemp=C:/aepci-wk/bt-m2`): 3428 passed, 34 skipped, 1 failed (`test_workflow_preview` practice SOP under load; re-run alone: 4 passed). New tests:
`tests/test_memory_sync_state.py` (4), `tests/test_business_cards_incremental.py` (11).

**Live check (owner, after `/api/tasks` is idle and Agent Web is restarted on this code):**
1. 「WNC 組織圖」: the reply says 「首次整理（收件匣 180 天內）：掃描 N 封…」, lists new people as
   s1, s2… and the chart shows only stored people.
2. 「都存進去」: stored, chart redrawn with them, no mail re-read.
3. 「WNC 組織圖」 again: 「從 M/D 之後的新信：掃描 …」, only new mail (fast, few or no model calls).
4. 「重新整理 WNC 的簽名檔」: 「重新整理（收件匣 180 天內）：…」.
5. With Outlook closed: the chart is still drawn with 「這次沒有先整理新信：…」.
6. New-evidence rule: the first card call after the restart runs the one-time cleanup; B's
   「研展處 I → 研展處」 (a re-scan of the same old card) should no longer be listed by
   「有哪些待確認？」 and 「B 的歷史」 shows a 依規則關閉的待確認讀值 row (「復原」 reopens it). Re-send
   an old card photo: nothing changes and nothing is asked. Send a new card with another
   department: the department updates with 「上次是…，現在是…」.

**Open / risks:**
- The card's `source_date` is still the scan day: it orders readings of fields the person did
  not set (newest-evidence rule) and shows "seen on"; it is never compared with the person's
  change. A misread re-scan of the same card can still change a field the person did not set
  when filed under a later date (existing behaviour, rule 3 of the owner's decision).
- The 50-message search cap stays; a pass that hits it says 「只處理了最新的 50 封」; older mail in
  the window is not reachable incrementally (same as before M2). Paging would need a reader
  "until" parameter.
- Candidates the person never answers expire in an hour and the state has moved past them;
  「重新整理」 brings them back.
- The tool default for `harvest_first` is false; the conversation relies on the procedure.

**Next:**
1. Owner live check above (steps 1–6).
2. M3: preferences and notes (§5, §3.9).

## Accumulated memory M1: Memory Service and the business-cards migration (2026-10-20, Claude Code)

**Goal / scope:** M1 of `docs/phases/ACCUMULATED_MEMORY.md` (owner-approved 2026-10-20): the
Memory Service skeleton (spaces declared in manifests, shared observations / provenance /
history / undo / proposals / external ids, per-actor isolation, merge rules as data) and the
business-cards `cards.db` moved into the first space, `contacts/org`, with every existing
business-cards behaviour and test kept. No UI (M4), no sync state (M2), no preferences or notes
(M3). Not pushed; Agent Web not restarted; the owner's live `cards.db` untouched (the live
migration runs when Agent Web restarts on this code, after the owner's review).

**Done (commits on main):**
1. ab31240b Memory Service and declarations: `common/memory.py` (contracts),
   `memory/service.py`, `memory/merge.py`, `memory/registry.py`, `memory_spaces` on Skill and
   Workflow manifests (omitted when empty: no digest changes), `host_runtime/memory_spaces.py`
   (Host registry from shipped + installed manifests; one manager per space refused at sync and
   switch-on), `capabilities/business_cards/space.py` (`contacts/org` declaration, merge rules,
   space tables), the business-cards Skill declares itself manager. Tests
   `tests/test_memory_service.py`.
2. 58de8bb8 Business cards on the Memory Service: `store.py` rewritten on `SpaceTx` (matching,
   honorific / tax id, companies, lines, chart data stay in the package), `migration.py`
   (verified byte backup, one transaction, ids kept, read-back compare, marker,
   `memory_legacy_changed`), handlers and Host pass the registry, Chinese failure texts. Tests
   `tests/test_business_cards_migration.py`; two existing tests adapted in storage access only
   (raw SQL now names `contacts_org__people`; the leak check reads `memory/*/memory.sqlite`).
3. (this commit) Docs: spec §11 "M1 as built", `docs/CONTRACTS.md`, `docs/DECISIONS.md`,
   `docs/phases/BUSINESS_CARDS.md` §2, `docs/TASKS.md`.

**Verification (2026-10-20):** `ruff check .` passed; `ruff format --check .` 931 files formatted;
`mypy` no issues (679 files). Full pytest, project `.venv`: 3437 passed, 9 skipped, 0 failed.
CI-like `C:epci-wk env` (confirmed pointing at this repo, `pip install -e ".[dev,office]"`,
`--basetemp=C:/aepci-wk/bt-m1`): 3414 passed, 34 skipped, 0 failed. The existing business-cards
suites (store, capabilities, conversation, html, telegram, file viewer: 96 tests) pass; two of them
changed only in raw storage access (table `contacts_org__people`, file `memory/*/memory.sqlite`).
New: `tests/test_memory_service.py` (29), `tests/test_business_cards_migration.py` (8).

**What the live start will do:** on the first `cards__*` call (or `aep-host cards import`) per
actor: back up `%LOCALAPPDATA%\...\workspace\business-cards\<actor-key>\cards.db` to
`cards.db.bak-<UTC stamp>` beside it (verified), copy every row into
`workspace\memory\<actor-key>\memory.sqlite` in one transaction, compare, mark. `cards.db` is never
written again. **Rollback:** stop Agent Web and run the code from before ab31240b (for example
`git revert 58de8bb8 ab31240b`); the old code uses `cards.db` as before. Changes made on the new code are only in `memory.sqlite`. To upgrade
again after using the old code: move `memory\<actor-key>\memory.sqlite` aside so the migration
runs again from `cards.db` (otherwise the store refuses with `memory_legacy_changed`).

**Open / risks:**
- The live Host's installed copy of the business-cards Skill JSON predates `memory_spaces`; the
  Host registry takes the shipped manifest for that identity, so access works; a re-export
  (`aep-host export-assets`) writes the new manifest.
- The registry is built at Host start; a Skill installed later reaches memory after a restart.
- Merge rules for managers that are not native code cannot be loaded from a Skill package yet.
- The person's value proposes on any differing evidence (older too), the store's existing
  behaviour; the owner's wording says "newer". `propose_if_newer` exists as data if the owner
  wants the narrower rule.

**Next:**
1. Owner review; then check `/api/tasks`, restart Agent Web, send a card or ask 「列出名片」 and
   confirm the backup file and `memory\<actor-key>\memory.sqlite` appear and the contacts are
   all there (`cards__list`), history and undo still work.
2. M2: sync state + incremental org chart (`docs/phases/ACCUMULATED_MEMORY.md` §4, §9; extension
   points in §11.7).

## Interactive HTML org chart and files in the chat (2026-10-20, Claude Code)

**Goal / scope:** owner 2026-10-20 「請幫我全做」: the org chart as interactive HTML (tree view,
grouped view, search opening a person card), general (no company built in), shown in the chat;
extended the same day: every chat file opens in a viewer panel with Preview / Code, as in Codex
and Claude Code. Not pushed; Agent Web not restarted (the owner may be testing live); the live
`cards.db` and mail untouched.

**Done (commits on main):**
1. 69d12960 `org-chart` / `cards__org_chart` `format` png (default) | html | both
   (`capabilities/business_cards/chart_html.py`): one self-contained page (inline CSS, script,
   escaped JSON data; no network), tree (reporting tree first when lines exist, solid/dashed),
   grouped boxes, search (name, romanised, title, BG/division/department, email), person card
   (all fields, 在職/已離職, 需確認, sources with dates, reporting lines with evidence), 顯示已離職
   toggle (hidden by default), dark mode, 390 px, keyboard, 44 px. Skill procedure: html for
   interactive / HTML / searchable / tree requests, never a script.
2. c8189832 Agent Web: file chips on answers and on the person's attachments open the viewer
   panel (side panel; full-screen under 760 px): HTML Preview (sandboxed frame) / Code, Markdown
   Preview (existing DOM renderer) / Code, CSV table / Code, images preview, text files Code
   with line numbers (5,000 lines / 1 MB cap with notice), copy, download, open in browser,
   Esc closes. HTML is framed only from `/view/file?nonce=` (15 min, page asks
   `/api/conversations/view-link` with its token) with CSP `default-src 'none'; script-src
   'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; ... sandbox allow-scripts`, in
   `<iframe sandbox="allow-scripts">` without `allow-same-origin`. The chart shows inline in its
   answer (480 px, resizable, 放大, 在面板開啟, 在瀏覽器開啟). `/api/conversations/file` now also
   serves the person's attachments listed on the conversation and serves text (HTML included)
   as `text/plain`.
3. bc7de7c1 Telegram: the HTML as `sendDocument` with a one-line caption; PNG kept for `both`.
4. Docs: `docs/phases/BUSINESS_CARDS.md` §6–§7, `docs/CONTRACTS.md`, `docs/DECISIONS.md`
   2026-10-20 "In-chat HTML runs in an opaque-origin sandbox from a nonce address; files open in
   a viewer panel" (why not `srcdoc`, blob or the token route), `docs/TASKS.md`, user guide §4.1
   and §4.7.

**Verification (2026-10-20):** `ruff check .` passed; `ruff format --check .` 921 files
formatted; `mypy` no issues (669 files). Full pytest, project `.venv`: 3401 passed, 7 skipped,
1 failed: `test_store_a_card_draw_the_chart_record_a_departure_and_undo_it` asserted that the
person's own attached photo is not served, which the viewer now does on purpose; the assertion
now uses a file attached in another conversation (still refused) and passed when re-run alone.
CI-like run: the shared `C:\aepci-wk\venv` had been re-pointed (editable install) at another
agent's worktree `C:\aepci-wk\wt-recovery`, so a separate venv `C:\aepci-wk\venv-cards`
(`pip install -e ".[dev,office]"`, `--basetemp=C:/aepci-wk/bt-cards`) was used: 3375 passed,
34 skipped, 0 failed. Headless browser tests ran here; screenshots in `.scratch/org-chart-html/`
and `.scratch/file-viewer/`.

**Open / risks:**
- HTML written by `coding/run-python` in a workspace is not attached to answers (attachments
  come only from `cards__org_chart`), so it is not shown inline yet; the viewer would show it the
  same way once it is attached.
- Esc pressed while focus is inside the sandboxed frame goes to the frame (it closes the chart's
  own person card), not to the panel; Esc outside the frame closes the panel.
- A view nonce lives 15 minutes; an answer re-rendered after that asks for a new one (each render
  and each "在瀏覽器開啟" asks afresh).
- The reporting tree in the HTML is an indented list, not a drawn graph.

**Next (owner live check; check `/api/tasks` before restarting Agent Web):**
1. Restart Agent Web so the new code loads.
2. In Agent Web: 「用 HTML 互動式呈現 <公司> 的組織圖」 → the answer shows the chart inline;
   switch 樹狀 / 分組, search a name (the card opens), toggle 顯示已離職, try dark mode.
3. Click the chips under the answer: the .html (Preview / Code), the .md legend (Preview /
   Code); Esc closes; 在瀏覽器開啟 opens the chart in a tab.
4. Telegram: the same request → the PNG (if both), the .html document with the caption, the .md
   legend; open the .html on a phone browser.

## Agent recovery and reuse fixes (2026-10-20, Claude Code)

**Goal / scope:** four owner-approved improvements (2026-10-20, 「請幫我全做」) from a live Gateway
conversation in which the owner asked for an interactive HTML org chart: `coding__run` failed with
`coding_workspace_missing` and the Agent asked the owner twice to create the folder by hand; it
answered 「規則我已改成…」 after only `cards__list` (nothing saved, Host check passed it); and it ran
one-off code where the owner expected a reusable Workflow. Not pushed; Agent Web not restarted;
live install untouched. A parallel agent works on the native HTML org chart / in-chat file viewer
(business_cards, web.py, web_page.py, telegram.py); its uncommitted work is not part of these
commits.

**Done (commits on main):**
1. 48650111 `coding/run-python` creates a missing task folder under a coding root (with `input/`
   and `output/`, after the runner and network-block checks; result `workspace_created`). Outside
   the roots → `coding_workspace_not_allowed`; any `..` refused; a file →
   `coding_workspace_not_a_folder`. Workspace note: never ask the person to create it. No default
   folder when none is given (the run-python Workflow keeps `workspace` required; changing it
   needs new Workflow and Skill versions). Tests `tests/test_run_python.py`.
2. 9ad33be2 every failed conversation tool call carries `recovery {recoverable, hint}`
   (`agent/tool_recovery.py`, Host-decided from the failure code); system prompt: fix and retry
   recoverable ones in the same turn, ask only when the person is needed. Tests
   `tests/test_tool_recovery.py` (reactive fake model: fails once with `invalid_input`, retries,
   succeeds; `permission_denied` → asks).
3. 301e39e6 `no_unbacked_action_claim` also catches lasting-change claims (「規則我已改成」「已改成」
   「已設定」「已更新規則」「已記住」「以後都會」, "I've updated the rule", "from now on I will")
   unless a changing (non-read) tool succeeded; prompt `MEMORY_GUIDANCE` says there is no rule
   memory, propose a Workflow draft or `propose_change`. Tests
   `tests/test_persistent_change_claims.py`.
4. a054384b reusable requests → Workflow draft: `REUSABLE_GUIDANCE` in the Gateway prompt when
   `authoring__draft_workflow` is offered, `DRAFT_GUIDE`, coding Skill `engineering/coding@1.8.0`
   (1.7.0 set aside on install), and a new Host check `reusable_request_drafted` (reusable
   request + `coding__…` succeeded + no draft → one retry). Tests `tests/test_reusable_drafts.py`
   (incl. Agent Web: the draft card appears, nothing installed or run until Install).
5. Docs commit: `docs/DECISIONS.md` (2026-10-20 "Fixable tool failures are retried, …"),
   `docs/TASKS.md`, user guide §4.5 (「做成可以重複用的」), this file;
   `docs/HARNESS_DESIGN.zh-TW.md` §5.4, §8.2, §8.4 went with the code commits.

**Verification (2026-10-20, on a clean worktree of a054384b, so the parallel agent's uncommitted
files were not included):** `ruff check .` passed; `ruff format --check .` 917 files formatted;
`mypy` no issues (666 files). Full pytest, project `.venv`: 3387 passed, 7 skipped, 1 failed
(`test_browser.py::test_a_throwaway_profile_is_removed_although_the_browser_holds_it`, timing;
passed when re-run alone). CI-like venv `C:\aepci-wk\venv` (`pip install -e ".[dev,office]"`,
`--basetemp=C:/aepci-wk/bt`): 3344 passed, 34 skipped, 1 failed
(`test_telegram_turn_progress.py::test_a_rate_limit_is_waited_out…`, timing) and 16 setup errors
(basetemp clean-up collisions on `C:/aepci-wk/bt`); all 17 passed when re-run alone in a separate
basetemp. E2E-01 (`tests/test_product_e2e_01.py`) 7 passed. The CI venv's editable install points
back at the main repo afterwards. Only docs text changed after the suites.

**Open / risks:**
- The model's behaviour (retrying, not claiming, drafting) is covered by fake-model tests only;
  prompts guide it, Host checks catch the claim and the missing draft with one retry.
- Read-tool detection for item 3 is by command name (list, get, show, preview, search, read,
  find, lookup, view, history, proposals, inspect, query, ask); an unknown name counts as changing
  (errs toward not flagging).
- 「，以後都會…」 in a neutral sentence without a changing tool is flagged (one retry).
- browser/operate still refuses a missing workspace (`browser_workspace_missing`); not in scope.

**Next (owner live check; check `/api/tasks` before restarting Agent Web):**
1. Restart Agent Web so the new code and coding Skill 1.8.0 load.
2. 「幫我做一個互動式 HTML 組織圖，放在 aep-workflows\org-chart-test」 (folder absent) → the folder
   is created, the script runs, no request to create it.
3. 「執行時不需要問是否包含在職人員」 → the reply says it applies to this conversation and offers a
   Workflow draft or proposal, never 「規則我已改成」.
4. 「把這個做成可重複使用的 workflow」 → an install card appears; nothing in Capabilities until
   Install; after Install it runs from the card's form.

## Business-cards third-round fixes (2026-10-20, Claude Code)

**Goal / scope:** the five minor issues from the owner's third live test (2026-10-20, owner:
「幫忙把上面1~5小問題也修掉」), Gateway backend. Not pushed; Agent Web not restarted (the owner was
live-testing Telegram); the live `cards.db` and mail untouched.

**Done (commits on main; every fix has a failing-first test):**
1. 078e0d6d phone, fax and mobile compare by digits + extension (`names.phone_key`; spaces,
   hyphens, dots, parentheses ignored; +886 = leading 0): a formatting-only difference keeps the
   stored value, records nothing, reports nothing.
2. 5184a031 (+ d941745b typing) any automatic reading that differs from a user-set or confirmed
   value is one open proposal (stored, read, observation id), sure or unsure, and the field needs
   confirmation (chart 需確認). `edit-person` `confirm` rejects it and writes a `confirm` row;
   `accept` (「用新的」) or the read value in `fields` accepts it (`field` row); undo reopens.
   New read capability `business-cards.proposals` / tool `cards__proposals` with a `note`.
   The full chat cycle is tested with a fake model, including the `confirm` row.
3. 6c65fb22 `add-card` results carry `match` {`by`, `by_label`, person, `changed`, `kept`,
   `needs_confirmation`, `lead` 「已對到既有聯絡人 <姓名>（<公司>），依…比對。」 / 「已新增聯絡人 …」};
   the summary says 「更新了…」 (no dangling 也); the procedure opens with `lead`.
4. 77c3375e display strings: `status_label` (在職 / 已離職), `source_label` (名片 / 郵件簽名檔 /
   使用者), `kind_label`, `field_label`, `old_display` / `new_display`, `at_local` (Asia/Taipei,
   2026-10-20 14:03); `set-status` `undo_hint`, `undo` `note`; ids only on a specific undo.
5. 3938c5e7 harvest: `without_signature`, `same_sender`, `unreadable_signature`, `scan_note`
   (「掃描 5 封，1 封有簽名檔，4 封沒有簽名檔。」), separate from `skipped`.
6. Docs commit: `docs/phases/BUSINESS_CARDS.md`, `docs/CONTRACTS.md`, `docs/DECISIONS.md`
   (2026-10-20 "A reading that differs from the person's own value needs confirmation"),
   `docs/TASKS.md`, user guide §4.7.

**Verification (2026-10-20):** `ruff check .` passed; `ruff format --check .` 913 files
formatted; `mypy` no issues (662 files). Full pytest, project `.venv`: 3370 passed, 7 skipped,
0 failed (includes the guarded live Outlook checks, read-only). CI-like venv `C:epci-wkenv`
(`pip install -e ".[dev,office]"`, `--basetemp=C:/aepci-wk/bt`): 3345 passed, 32 skipped, 0 failed (run
after the first suite finished). Both suites ran with the code, user guide and spec in place; only
HANDOFF.md, TASKS.md, DECISIONS.md and CONTRACTS.md text changed afterwards (no test reads them).

**Open / risks:**
- The `confirm` history row in a real chat is covered by fake-model tests only; still to see live.
- `less_complete` readings (a shorter 事業群) are not proposed even against the person's own value.
- A number that is not digits-only text (e.g. contains words) is compared as written.
- Adds the `business-cards/proposals` capability: on a host governed by members' decisions it
  needs a grant like the others (owner mode grants it).

**Next (owner live re-test; check `/api/tasks` before restarting Agent Web):**
1. Restart Agent Web so the new code loads.
2. Re-scan a card whose phone reads "(03) 666 7799" for "(03) 666-7799" → no change reported;
   「<某人> 的歷史」 shows no new field row.
3. Confirm an email, re-send the card with the email misread → reply opens 「已對到既有聯絡人 …」,
   says the two emails differ; chart legend lists 需確認：Email; 「有哪些待確認？」 lists it.
4. 「<某人> 的 email 正確」 → history shows a `confirm` row (確認, 使用者, Taipei time);
   repeat with 「用新的」 → the email changes, a 欄位變更 row.
5. 「<某人> 離職了」, 「<某人> 的歷史」, 「復原」 → 在職 / 已離職, 郵件簽名檔, local times; no change
   ids unless you ask to undo a specific one.
6. Harvest a domain → the reply says 「掃描 N 封，M 封有簽名檔，K 封沒有簽名檔。」.

## Business-cards second-round re-test fixes (2026-10-20, Claude Code)

**Goal / scope:** the ten issues the owner's 2026-10-20 re-test of the first-round fixes found
(Gateway backend). Not pushed; Agent Web not restarted; the live `cards.db` and mail untouched
except the guarded read-only Outlook checks in `tests/test_outlook_mail_folders.py` (folder
strings only; they ran and passed on this PC with Outlook running).

**Done (commits on main; each fix has a failing-first test, item 9 is a verification test that passed as written):**
1. ce8cfc99 [blocker] COM per thread: `integrations.com.apartment()` (CoInitialize/CoUninitialize,
   nested uses counted) around every `OutlookComMailbox` / `OutlookComDraft` /
   `OutlookComDraftSender` call (Outlook asked for inside it, no COM object kept, failures mapped
   to `mail_failed` / `draft_failed` / `send_failed`; new `connect=` parameter), and around the
   weekly and chipset Excel runs. Tests `tests/test_outlook_com_threads.py` (fake COM refusing
   uninitialised and cross-thread use; two `to_thread` workers) and a live test listing the
   Inbox from two worker threads (fails on the old adapter with com_error, passes now).
2. 06ab71d9 [blocker] harvest keeps candidates per conversation (`candidates` table, `s1`…,
   one hour, replaced by the next harvest); `store-candidates` / `cards__store_candidates`
   stores by id or `all`; procedure: never re-harvest to store.
3. 102d2925 matching: same image hash → that person; same name + company with another email →
   same person unless department/division differ; stored email kept, proposal, flagged,
   `email_differs`. Telegram fixtures now send a distinct photo per card.
4. 2b7ec0a2 統一編號 from `other_text` and the address; an old 統一編號 note tidied with history.
5. 0d7e95be a shorter reading never replaces a more complete value (`less_complete`; not title).
6. 4c738cf8 company queries resolve by name, capitalised short name or mail domain (WNC, 啟碁);
   results carry the canonical company.
7. 86b6a24d Chinese `label` / `field_labels`, `to_confirm` with stored values, summary never
   reports an unchanged value; procedure updated.
8. 01c07df6 chart box: 姓名 + 博士, title, phone #ext, 手機, 需確認; legend lists 需確認.
9. f8bac401 test: confirming in chat writes one `confirm` history row.
10. Docs commit: `docs/phases/BUSINESS_CARDS.md`, `docs/CONTRACTS.md`, `docs/DECISIONS.md` (three
    2026-10-20 entries: re-scanned card matching, company queries, COM per thread),
    `docs/TASKS.md`, user guide §4.7.

**Verification (2026-10-20):** `ruff check .` passed; `ruff format --check .` 913 files
formatted; `mypy` no issues (662 files). Full pytest, project `.venv`: 3359 passed, 7 skipped,
0 failed (includes both live Outlook checks). CI-like venv `C:\aepci-wk\venv`
(`pip install -e ".[dev,office]"`, no pywin32, `--basetemp=C:/aepci-wk/bt`): 3334 passed, 32 skipped, 0 failed (run after the first suite finished, with the docs in place).
Docs and user guide changed after the first full run; `tests/test_bundled_skills.py` re-run
after the guide change: 15 passed.

**Open / risks:**
- The matching rule takes namesakes at one company with the same (or unread) department and
  division, but different emails, as one person (documented limit; the email is flagged).
- Company aliases from mail domains join spellings that share a corporate domain; public mail
  services are excluded by a fixed list (`names.PUBLIC_DOMAINS`).
- Candidates live in `cards.db`; an Agent Web restart keeps them (one hour).
- The Excel apartment wrap is covered only by a fake; no live Excel run was made.

**Next (owner live re-test; check `/api/tasks` before restarting Agent Web):**
1. Restart Agent Web so the new code loads (`cards.db` gains the `candidates` table on open).
2. Gateway chat: 「從 wnc.com.tw 的信件簽名檔整理聯絡人」 → candidates listed as s1, s2, …;
   run it a second time → still works (no `handler_error`; COM fix).
3. 「都存進去」 → one `cards__store_candidates` call, no new harvest; 「<某人> 的歷史」 shows an
   `email_signature` observation with the message id.
4. 「WNC 的組織圖」, then 「wnc 組織圖」 and 「啟碁的組織圖」 → the same company, card and
   signature people together; boxes show 「王則閔 博士」, phone #ext, 手機; legend lists 需確認.
5. Re-send card A (same photo) → no new person; if the email reads differently the reply says the
   two emails differ and asks which is right; the stored one is kept.
6. Re-scan a card whose 事業群 reads shorter → stored value kept; summary never says
   「上次是X，現在是X」.
7. Card A with 統一編號 → stored in 統一編號; an old 「統一編號：…」 note disappears from notes.
8. Replies name fields in Chinese (英文名), and a question about a field states its stored value.
9. 「email 正確」 → 「<某人> 的歷史」 shows a `confirm` row by `<you> via local|telegram`.

## Business-cards live-test fixes (2026-10-20, Claude Code)

**Goal / scope:** the eight bugs from the 2026-10-20 live test of native business cards (Gateway
backend). Not pushed; Agent Web not restarted; the live `cards.db` and mail untouched except the
guarded read-only folder check (`tests/test_outlook_mail_folders.py`, last test: it lists one
Inbox message and compares folder strings only, when Outlook is already running).

**Done (commits on main):**
1. 77562560 — [blocker] `OutlookComMailbox.get()` named an Inbox message `<mailbox>/Inbox`
   (`_folder_path` did not stop at the store root: the MAPI Namespace has `Folders` too), so
   `outlook_mail.read()` refused every Inbox message with `message_unknown` — signature harvest,
   `outlook.read` (`capabilities/mail_read`) and agent mode (`host_runtime/agent_mail`). The walk
   now stops at the default store root (OlObjectClass + EntryID), names default folders
   canonically (Inbox also for 收件匣) and keeps another store's name in front. The fix is in the
   adapter, so all three callers are fixed; tests drive each through a fake of Outlook's object
   model. `HarvestHandler.collect` skips an unreadable message (`skipped`, `skipped_note`). The
   live check failed before the fix (`<address>/Inbox` vs `Inbox`) and passes after it.
2. 16d8c189 — a failed `cards__*` call carries `<中文說明>（<code>）` instead of "Capability
   invocation did not complete" (`business_cards_tools.FAILURE_TEXT`; Settings only for
   `folder_unknown` / `permission_denied`); procedure "IF A TOOL FAILS".
3. bc36e346 — who = `<actor> via <channel>` in history, `status_set_by`, lines, confirmations and
   undo; `SetStatusRequest.said_by` removed; the host tools drop identity keys from model args.
4. 1882da22 — `needs_confirmation` persists while any observation flagged a field and the value is
   not the person's (source `user`); `edit-person` `confirm: [...]` ("email 正確"), history kind
   `confirm`, undoable; chart label 「需確認：英文名、Email」 (`contracts.FIELD_LABELS`).
5. 643d8f7b — `romanised_name` kept only with `romanised_name_printed`; else dropped (`dropped`) and
   an email whose local part repeats it is marked uncertain; signatures keep it only when the
   block prints it; procedure / schema: never derive it from the email, never change the email.
6. ad3a15d4 — `honorific` and `company_tax_id` fields (decision `docs/DECISIONS.md` 2026-10-20
   "Degrees and the unified business number are contact fields"); Host moves 博士 / Dr. / PhD out
   of `title` (not 博士後) and 統一編號 out of notes; an existing `cards.db` gains the columns on
   open; procedure: copy division / department exactly (研展處 I).
7. 3e3a97e8 — `edit-person` `clear: [...]` empties a wrong field as the person's own value (a scan
   does not refill it), so the invented "Yanji Fan" can be removed.
8. Docs commit: `docs/phases/BUSINESS_CARDS.md`, `docs/CONTRACTS.md`, `docs/DECISIONS.md`,
   `docs/TASKS.md`, user guide §4.7.

**Verification (2026-10-20):** `ruff check .` passed; `ruff format --check .` 912 files
formatted; `mypy` no issues (661 files). Full pytest, project `.venv` at 3e3a97e8: 3329 passed,
7 skipped, 0 failed (includes the live Outlook folder check, which ran and passed).
`C:epci-wkenv` (`pip install -e ".[dev,office]"`, `--basetemp=C:/aepci-wk/bt`), run after the
first suite finished: 3305 passed, 31 skipped, 0 failed. Docs-only commit after that.

**Open / risks:**
- The model may still invent `romanised_name_printed`; the Host check only catches a missing or
  email-only evidence line. The email-misread flag fires only when a romanised name was dropped.
- The division suffix rule is procedure only (the Host cannot know a suffix was dropped).
- Values stored wrongly in the first live test stay until corrected: a re-scan of card A with the
  right email does not match the stored person (the stored email differs, and email decides), so
  it would create a second person. Correct the stored email and clear the English name in chat
  first (step 3 below).
- Other stores' (shared mailbox / PST) folders are now named `<store>/<folder>`, so a scope entry
  must name the store to read them (before, they were refused anyway).

**Next (live re-test; check `/api/tasks` before restarting Agent Web):**
1. Restart Agent Web so the new code loads (the existing `cards.db` gains `honorific` and
   `company_tax_id` on first use).
2. Agent Web Gateway chat: 「從 wnc.com.tw 的信件簽名檔整理聯絡人」 → candidates (no
   `message_unknown` for Inbox mail); if some message is unreadable, the reply says
   「讀信失敗：N 封信無法讀取（code），已略過；其餘 M 封已處理」.
3. First fix card A's old record in chat: 「范○○ 的 email 改成 ryan.rj.fan@wnc.com.tw」 and
   「把范○○ 的英文名刪掉」 (edit-person `fields` / `clear`). Then re-send card A (no English name): no romanised name stored, the reply says it was not on the
   card if the model tried; email as printed (ryan.rj.fan@...) or flagged 需確認.
4. Re-send card A again with a sure reading: the email stays 需確認 on the chart until
   「email 正確」; then 「范… 的歷史」 shows a `confirm` row by `<you> via local|telegram`.
5. Card with 「資深經理 博士」 and 「研展處 I」: title 資深經理, 學位 博士, division 研展處 I.
   Card B with 統一編號: stored as the company's 統一編號, not in notes.
6. 「X 已經離職」 → history / view shows `status_set_by` = `<you> via telegram` (Telegram) or
   `via local` (Agent Web), never 使用者; 「復原」 works.
7. Org chart: the 需確認 line shows Chinese field names.

## Native business cards and org chart (2026-10-20, Claude Code)

**Goal / scope:** owner 2026-10-20 "當然選a": business cards as a native AEP capability in Gateway chat
and Telegram (Telegram photos are the main way cards arrive, owner update the same day), switched on
by default, nothing sent to an external model, an org chart from cards and email signatures that
adjusts when someone left. Spec `docs/phases/BUSINESS_CARDS.md`; decision `docs/DECISIONS.md`
2026-10-20; contracts `docs/CONTRACTS.md` "Business cards and org chart"; user guide §4.7. Not
pushed; Agent Web not restarted; live install, the owner's real cards and mail untouched (no real
data in the repo). `gateway.py` / `conversation_harness.py` not edited.

**Done (commits on main):** 039a1724 spec; db7233a0 store + 13 capabilities +
`LocalPolicy.confirm_writes`; e9cd101f Host wiring, `cards__*` tools, Skill
`engineering/business-cards@1.0.0` shipped on, `aep-host cards import`, CI bundle checks; 21f05327
chart PNG in Agent Web (`GET /api/conversations/file`) and Telegram; ff845dac Telegram-first (bare
photo, photo as file, album = one card per photo, short reply, chart photo with the note + legend
document); 0b7f7c62 six-month mail-scope test; then the docs commit.

- Store: `<workspace>/business-cards/<actor-key>/cards.db` per actor; observations (source, date,
  image hash / message id), field provenance (user value never overwritten, newer evidence wins, an
  uncertain reading never replaces a value), reporting lines with evidence, history +
  `undo(change_id)`, proposals.
- Writes are `write` / risk low, confirmed standing by the Host (no approval card per call); reads
  and `harvest-signatures` are `read`. The capabilities install only when the Skill file is present
  (switched on or off).

**Verification (2026-10-20):** `ruff check .` passed; `ruff format --check .` 909 files formatted;
`mypy` no issues (658 files). Full pytest, project `.venv` (final code): 3304 passed, 7 skipped,
2 failed (`test_draft_install_cards` real-browser card, `test_telegram_settings` no-senders bot),
both passed when rerun alone (load from a parallel agent's suites). `C:\aepci-wk\venv`
(`pip install -e ".[dev,office]"`, `--basetemp=C:/aepci-wk/bt`): 3276 passed, 30 skipped, 0 failed
(run before the Telegram-first commit); after it, the business-cards, Telegram, bundled-Skill,
weekly-report and platform-transport tests there: 109 passed, 3 skipped. Bundle: wheel built and
contains the new modules; `aep-host assets install-bundled` replayed into a temp workspace (business
cards on, Hermes copy off). Full `install.ps1` replay not run: it writes the user's gateway settings,
user environment and coding-agent settings on this PC.

**Open / risks:**
- No Contacts page in Agent Web (chat covers find / list / history); proposals have no button.
- HEIC files sent as documents are refused (send as a photo); an album split across two polls
  becomes two turns.
- On a host governed by members' decisions (or an active profile) the cards capabilities need a
  selection like any other, else `permission_denied`.
- The org chart is nested boxes with routed lines; a very large company gives a wide image.

**Next (live test with the owner, after checking `/api/tasks` and restarting Agent Web):**
1. Capabilities shows `engineering/business-cards` on (an existing install gets it from the next
   bundle update or `aep-host assets install-bundled`).
2. Telegram: send one card photo without text → short reply, uncertain fields asked one per line;
   send the second card; re-send one → "上次是…, 現在是…"; both as an album → one line per card.
3. Telegram: "<company> 組織圖" → photo with the note, legend file, short text.
4. "X 已經離職" → recorded, chart without X; "復原" → back.
5. Agent Web Gateway chat: attach a card photo, store, ask for the chart → PNG under the answer.
6. "從 <domain> 的信件簽名檔整理聯絡人" (mail scope 6 months) → candidates, confirm, stored.
7. If `~/.business-cards/cards.db` exists: `aep-host cards import --config <host.json>` twice.

## Live test fixes 2026-10-20 (Claude Code) — latest

**Goal / scope:** three bugs from the 2026-10-20 live test. Code in `src/agent/gateway.py`,
`src/agent/conversation_harness.py`, `src/agent/turn_progress.py`, one JS line in
`src/host_runtime/web_page.py`, a three-line hook in `src/host_runtime/host.py`. Not pushed; Agent Web
not restarted; live install untouched. A parallel agent built native business cards
(`src/capabilities/business_cards/`, commits 039a1724..21f05327); not part of this work.

**Done (three commits on main):**
1. 17b607b5 — an image turn survives the conversation check's retry: the retry pair goes to
   `_converse(..., retry=...)` after the person's message (image sent once, on that message); a retry
   pass that fails returns the first answer with the Host note. `docs/HARNESS_DESIGN.zh-TW.md` §5.3.
2. 9ec22f74 — progress ends in the real outcome: a turn without an answer stops the conversation
   Harness in `execute` (`failed`, or `needs_input` shown as `stopped` ⏸); `TurnProgress` records the
   stage a run ended in. §5.5.1.
3. 0ba829e4 — switched-off Skills are named (names only, ≤80) in the Gateway system prompt with
   "switch it on in Agent Web > Capabilities; never install or re-create it". §5.1;
   `docs/DECISIONS.md` 2026-10-20.

**Verification (2026-10-20):** ruff check / format --check on the changed files passed (whole repo
after the business-cards commits: `ruff check .` passed, 909 files formatted); `mypy` no issues (645
files). Full pytest, project `.venv` (at 0ba829e4): 3272 passed, 7 skipped, 0 failed.
`C:\aepci-wk\venv` (`.[dev,office]`, `--basetemp=C:/aepci-wk/bt`, run while the business-cards agent
was committing): 3274 passed, 30 skipped, 2 failed
(`test_platform_transport::test_sync_installs_what_the_member_chose_onto_a_real_host`,
`test_weekly_report_workflow::test_doctor_reports_the_integrations_without_contacting_anything`);
both passed when rerun alone.

**Next:** live re-test after the owner restarts Agent Web: business-card photo + 「請解析這張名片並存進
名片資料庫」 (expect an answer, not `conversation_history_invalid`); progress shows ✗/⏸ on failed or
stopped turns; asking for business cards while `hermes/business-cards` is off gets the Capabilities hint.
Open question: should drafting a Skill whose name is switched off also be refused in
`chat_authoring.check_skill` (today only the prompt guards it)?


**Redeploy on 141 (2026-10-19, Claude Code):** the Shared Platform on 172.25.228.141 now runs
a1076c53 (includes 927e9b29 `POST /v1/member/logins/revoke`), bundle
`aep-shared-platform-preview-0.1.0-a1076c535fcd.zip`, downtime about 22 s. Verified: pinned-https
health ok, certificate fingerprint unchanged, Member Portal loads, `logins/revoke` without a
session answers 401, Agent Web `/api/platform` answered (18 catalog entries). The "not
redeployed" line below is superseded.

## Owner decisions on Knowledge Strategy v1.3 (2026-10-19, Claude Code) — latest

**Goal / scope:** apply the owner's answers to v1.3 section 8.2. v1.3 updated in place (no v1.4): closing
section "Owner 決定（2026-10-19）：對 §8.2 的回答", DIFF section 7. Only `src/` change: speaker notes in
`src/knowledge/office.py`. No AEP-K02 work, no live install / 141 / OneDrive vault / fixture / `files/`
touched, not pushed.

**Done (committed on main, see `git log`):**
- `competing_vendors` official (TestSolution → Competitor); new origin `owner-decision-2026-10-19`
  for things the owner made official that `bi_schema.py` lacks. Opportunity official (`name`,
  `account`, `customer_product`, `test_solutions`, `opportunity_stage` replacing
  `hypothesis_status`, `confidence`, `updated`). Suggested patch for the owner's `bi_schema.py`:
  `docs/proposals/bi_schema_v1/README.md` section 8 (test checks it equals the JSON's
  `suggested_code` lines).
- Priority scoped: Application `priorities` (market × quarter); market = `TargetMarket` +
  `unspecified`; JSON `priority_entry`, `priority_scoping`; mock, `entity_history.json` (`scope`),
  API `FieldChange.scope`, `Relationship.origin`, SUP-01 updated; strategy digest re-pinned.
- `PptxExtractor` → `pptx.v2`: per-slide `Speaker notes:` text section; old Raw not rewritten.
  `docs/CONTRACTS.md` updated. Tests in `tests/test_office.py`.
- ADR-K9 decided: `docs/DECISIONS.md` "Verified work is committed directly to main"; one line in
  `AGENTS.md`.

**Verification (2026-10-19):** `ruff check .` passed; `ruff format --check .` 893 files formatted; `mypy` no issues in 643
files. Full pytest, project `.venv`: 3256 passed, 7 skipped, 4 failed; `C:epci-wkenv` (`.[dev,office]`,
`--basetemp=C:/aepci-wk/bt`): 3233 passed, 30 skipped, 4 failed. The two suites ran at the same time; all
8 failures were browser / timing tests (`test_web_capabilities`, `test_web_script`, `test_workflow_preview`,
`test_schedule_web`, `test_telegram_turn_progress`) and passed when rerun alone in each venv (15 and 19
passed). `tests/test_knowledge_strategy_docs.py` 37 passed, `tests/test_office.py` 11 passed. Changed JSON
parses; `openapi.yaml` parses (15 paths).

**Open / to confirm with the owner:**
- Item 6 ("好" to "revise v0.1 in place or bump to 0.2") is ambiguous; read as keeping v0.1.
- Market definition: TargetMarket segments vs sales region / customer group.
- When the owner applies the section 8 patch to `bi_schema.py`: regenerate line refs, update
  `source.primary_sha256` and the pins, switch those origins back to `source-bi-schema-py`.
- Still pending: N2 reviewers, ADR-K8, link ranges, priority rubric (BD), v1.3 approval.

**Next:** owner confirms item 6 and the market definition; nothing in AEP-K02+ starts before v1.3
approval.

## Knowledge Strategy v1.3 (2026-10-19, Claude Code) — awaiting owner review (superseded in part by the section above)

**Goal / scope:** reconcile the Knowledge Strategy proposal's provisional BI Schema v0 with the real
BI tooling the owner supplied (now the test fixture `tests/fixtures/bi_vault_example/`, e30cd8bf);
fold in the owner's priority question (ADR-K11) and the owner-shared Codex "BI Knowledge Source
Brief v6" (each finding re-checked against the fixture with file:line). Docs, contracts and
benchmark data only: no `src/`, no AEP-K02, no issues / PRs, not pushed. Supersedes the "Knowledge
Strategy v1.2" section below as the current state of that track.

**Done (committed on main):**
- `docs/proposals/KNOWLEDGE_STRATEGY_v1.3.md` + `_v1.3_DIFF.md` (v1.2 unchanged). New: §0.3 inputs
  and "already decided, not reopened"; §4.3 Schema v1; §4.4 BI pipeline → Strategy = Workflow +
  Skills + Config; §4.5 DQ-1..9; §4.6 Dashboard caveats; §4.7 Case A–E; ADR-K11; issues AEP-K14
  (rewrite `bi_ingest.py` behaviour as capabilities), K15 (Legacy Obsidian adapter), K16 (vault-
  example runner); K13 marked done.
- `docs/proposals/bi_schema_v1/` (`bi_schema_v1.json` + README). Generated from `bi_schema.py` with
  `ast`; the generator was a one-off scratch script (not committed) — the test re-checks every
  `bi_schema.py:<line>` reference and the file's sha256, so drift is caught.
- Knowledge API v0.1 pre-freeze revision (README "Pre-freeze revision" table for the Atlas agent);
  mock upcast to v1; `entity_history.json`; strategies digest = sha256 of `bi_schema_v1.json`
  (re-pin it if that file changes: `test_strategy_config_pins_schema_v1_digest`).
- Benchmark: 33 triples renamed; SUP-01; `vault_example_questions.json` (8, real example names).
- `tests/test_knowledge_strategy_docs.py`: 36 tests (v0 pinned unchanged + upcast totality; mock vs
  v1; v1 traced to code lines; judgement provenance; history; digest; SUP-01; vault set vs fixture).

**Verification (2026-10-19, project `.venv`):** `ruff check .` passed; `ruff format --check .` 893
files formatted; `mypy` no issues in 643 files; `pytest -q -p no:cacheprovider
tests/test_knowledge_strategy_docs.py` 36 passed; `pytest -k "docs or readme or tasks or
knowledge_strategy"` 51 passed; every new or changed JSON parses and `openapi.yaml` parses (15 paths).
Full suite not run (no code changed).

**Open / risks:**
- Owner decisions listed in v1.3 §8.2 (Schema v1, ADR-K11 rubric and single vs scoped priority,
  `competing_vendors`, link-range inferences, Node extensions, Opportunity, speaker notes, in-place
  API revision vs 0.2). N2 reviewers still pending.
- The Atlas Coding Agent must apply the relationship renames in the contract README.
- `files/` (owner's working copy) stays untracked; the fixture is the committed snapshot.

**Next:** owner reviews v1.3. Nothing in AEP-K02+ starts before approval.

## Four owner-approved changes (2026-10-19, Claude Code) — latest

**Status:** committed on main (c3c5f1f8, 1b25b64b, 7310c3cd, 927e9b29, 75ee0f74), **not pushed**,
Agent Web **not restarted**, the Shared Platform on 141 **not redeployed**.

- **Telegram status on every change** (c3c5f1f8; decision 2026-10-19 "Telegram's status message
  is edited whenever the turn's state changes", superseding the 5 s rule): `TurnProgress.listener`;
  `channels/telegram.py` `_Progress` edits the one status message on each change, at most one
  edit per second per chat (deferred, never dropped; latest state shown), identical text skipped,
  429 `retry_after` honoured. Tests `tests/test_telegram_turn_progress.py`. Design §5.5.1.
- **Team members revise a team-owned Workflow in place** (1b25b64b; decision 2026-10-19 "A member
  of the owning team revises a team-owned Workflow in place"; spec `docs/phases/WORKFLOW_REVISION.md`):
  `host_runtime/team_membership.py`. Membership from the platform's existing `POST /v1/member/me`
  (own groups only; cached in `team-membership-cache.json`, used offline), else Settings → Shared
  platform "Teams I belong to on this PC" (`team-membership.json`, `/api/settings/teams`). Card line
  "Revision as a member of team X (declared on this PC)". Installing and platform publishing are
  unchanged. No new platform endpoint. Tests `tests/test_team_membership.py`.
- **Label** (7310c3cd): "Bridge API URL" → "Platform sync URL (Bridge API)" with the explanation;
  UI text and two guide sentences only.
- **Personal Agent code from Agent Web, renewed** (927e9b29 platform route, 75ee0f74 host; decision
  2026-10-19 "Agent Web gets the Personal Agent code by password sign-in and renews it"; spec
  `docs/phases/PASSWORD_SIGN_IN.md`): platform `logins/revoke` (own logins only, else 404
  `login_missing`); `host_runtime/agent_code.py`; `POST /api/settings/shared-platform/sign-in`;
  hourly renewal under 7 days left (`start_agent_code_renewal`, started by `aep-host web`); expiry
  of the code and the Bridge token in Settings, reminder under 14 days. Tests
  `tests/test_agent_code.py` (incl. headless browser, screenshots `.scratch/agent-code-signin-ui/`),
  `tests/test_member_login_revoke.py`.
- **Verification:** ruff, format, mypy clean in both venvs. Full suites: project `.venv` 3247
  passed, 7 skipped, 0 failed; `C:epci-wkenv` (`pip install -e ".[dev,office]"`,
  `--basetemp=C:/aepci-wk/bt`) 3224 passed, 30 skipped, 0 failed. Fakes and in-process platform
  fixtures only; weekly report Workflows never run, read or changed.
- **Risks / open:**
  - 141 needs a redeploy for `logins/revoke`. Until then renewal stores the new code and the old one
    expires on its own (recorded as `unrevoked`), and the sign-in's browser login stays until it
    expires (30 days). The team-membership change needs no redeploy.
  - A code pasted before this change has no record; the first hourly check renews it once to learn
    its expiry (the old code is revoked once the route exists).
  - The membership lookup calls the platform at most every 5 minutes; a refusal (revoked login)
    gives no teams.
- **Next:**
  1. Owner restarts Agent Web (check `/api/tasks` first). Telegram: a tool-using turn updates the one
     status message about every second, never a second message.
  2. Settings → Shared platform: "Platform sync URL (Bridge API)"; "Sign in to get a code" with the
     platform password → "Personal Agent code valid until …"; the Bridge token's expiry shows.
  3. Settings: "Teams I belong to on this PC" shows the platform's teams and source; with a fixture
     team Workflow (never the weekly report), Revise in chat gives "Revision of … 1.0.0 → 1.0.1" with
     the membership line.
  4. Redeploy 141 with the owner for `logins/revoke`.


## Revise an installed Workflow from chat (2026-10-19, Claude Code)

**Status:** committed on main, **not pushed**, Agent Web **not restarted**. Owner approved
2026-10-19. Spec `docs/phases/WORKFLOW_REVISION.md`; decision `docs/DECISIONS.md` 2026-10-19
"The Agent revises an installed Workflow by building on its real code"; contracts in
`docs/CONTRACTS.md` "Revising an installed Workflow"; `docs/TASKS.md` new section.

- **Goal:** asked to change an installed Workflow, the Agent rewrote a "v2" from scratch
  because it could not read installed Workflows or shipped capability source. Now it reads,
  copies one version up, edits, and the person installs from the card.
- **What changed:**
  - `src/host_runtime/workflow_revision.py` (new): reference resolution, who may read,
    the paged view (20,000 JSON characters per slice), the revision summary, read-only
    capability source.
  - `src/host_runtime/chat_authoring.py`: `authoring__get_workflow` takes `workflow` or
    `candidate_id` (+ `offset`); new `authoring__revise_workflow`,
    `authoring__show_capability_source`; `ChatCandidate.base_digest`; revisions keep
    `source: revision:<identity>` and one version above the installed one; fields the draft
    format cannot express are carried over; contributors count as co-editors;
    `ChatAuthoringError.detail` (model-only message).
  - `src/host_runtime/draft_cards.py`: "Revision of X a → b" / "Fork of X as Y" with a change
    summary; an unchanged revision gets no card.
  - `src/host_runtime/external_authoring.py`, `mcp_server.py`, `cli.py`:
    `aep_show_installed_workflow`, `aep_revise_workflow` (CLI `show-installed-workflow`,
    `revise-workflow`), only for Workflows installed from an authoring draft on this Host;
    else `workflow_withheld`.
  - `creators/aep-workflow-creator/SKILL.md`, `conversation_backends.AGENT_POLICY`: the flow.
  - `web_page.py`: Capabilities → installed Workflow → **Revise in chat** (new session, request
    typed in, unsent).
  - `deploy/windows-preview/USER_GUIDE.zh-TW.md` §5.4: one note.
- **Commits:** 1b7b854d (read, revise, card, external), 363c03bf (Revise in chat + chat and
  browser tests), then the docs commit.
- **Verification:** ruff, format and mypy clean in both venvs. Full suites (with the parallel
  turn-progress work in the tree): project `.venv` 3216 passed, 7 skipped, 0 failed;
  `C:\aepci-wk\venv` (reinstalled `-e ".[dev,office]"`, `--basetemp=C:/aepci-wk/bt`) 3192
  passed, 30 skipped, 1 failed (`test_member_portal_tabs.py` real-browser test, a flake under
  load; 2 passed alone). Tests `tests/test_workflow_revision.py` (24) and `tests/test_workflow_revision_chat.py`
  (3, one real browser; screenshots `.scratch/workflow-revise-ui/`). Fakes and fixtures only;
  the owner's weekly report Workflows were never run, read or changed.
- **Risks / open:**
  - A team-owned shipped Workflow (e.g. the weekly report, owned by `team:engineering`) is
    forked to `<name>-<actor>`, not bumped in place: the Host has no record that the person
    belongs to the team. If the owner wants in-place revisions of shipped Workflows, that needs a
    group-membership rule (decision needed).
  - External agents see only Workflows drafted here (PUBLIC rule); they have no
    capability-source tool.
  - Two versions of a name stay installed side by side; a bare name resolves to the highest.
- **Next:**
  1. After the owner's next Agent Web restart, with a fixture Workflow (never the weekly
     report): Capabilities → the fixture → **Revise in chat** → ask for a small change → the card
     shows "Revision of … 1.0.0 → 1.0.1" and the right changes → Install → both versions listed.
  2. Optional: ask the Agent to show `weekly_report` source (`authoring__show_capability_source`)
     to confirm the read-only view in the live install; do not run the Workflow.


## Tool cap 150 with guards; live Harness state in the chat (2026-10-19, Claude Code)

**Status:** committed on main (906716ce, bfe07ae7, plus the docs commit), **not pushed**, Agent
Web **not restarted**. Another agent worked in parallel on "revise an existing Workflow from chat"
(`workflow_revision.py`, authoring modules, a few `web_page.py` lines); none of its changes are
in these commits, which were staged as HEAD plus this work only.

- **Goal:** two owner-approved changes (2026-10-19): (1) 150 tool calls per conversation turn,
  with guards against spinning; (2) show the running turn's Harness state in the chat instead of
  "working…".
- **Change 1 (906716ce):**
  - `agent/backend_contracts.py`: `MAX_CONVERSATION_TOOL_CALLS` 150, `MAX_CONVERSATION_TURNS`
    151, `MAX_IDENTICAL_FAILURES` 3, `MAX_IDENTICAL_CALLS` 5, `ConversationLimits`
    (tool calls 1–150, time 60 s–120 min, default 30 min).
  - `agent/gateway.py` `_converse`: Host cap, time budget checked before every model and tool
    call, `tool_repeat_limit` (3 identical failures in a row, or a 6th identical call with no
    new call in between), telemetry `turn.stopped` (reason and counts only), old tool
    observations compacted past 160,000 characters per turn. `Gateway.conversation_limits`,
    `Gateway.clock`, `Gateway.limits()`.
  - `host_runtime/conversation_context.py`: settings `tool_call_limit`,
    `turn_time_limit_minutes`; `host.py` wires them to the Gateway (read at each turn).
  - Agent Web Settings (two fields with an explanation); stop replies in Agent Web and Telegram
    (`host_runtime/turn_summary.py` `stop_reply`); `AgentProfile.max_turns` bound 151.
  - `agent/task_execution.py` (scheduled tasks, `min(max_backend_turns, 5)`) left alone: a
    background task budget, not the conversation limit.
- **Change 2 (bfe07ae7):**
  - `agent/turn_progress.py`: `TurnProgress`, `TURN_PROGRESS`, `TurnProgressBoard`; reported by
    the Gateway tool loop and the shared Harness runner (`run_harness`, `run_harness_async`).
  - `GET /api/conversations/progress?session_id=` (page token; same actor only; null when no
    turn runs); `AgentMode.observer` adds agent-mode tool requests.
  - Agent Web progress view (polled every second while a turn runs); Telegram's single status
    message shows the same compact text and is edited at most every 5 s after the first edit.
- **Docs:** `docs/HARNESS_DESIGN.zh-TW.md` §5.3, §5.5, §5.5.1; `docs/DECISIONS.md` 2026-10-19;
  `docs/TASKS.md`; `deploy/windows-preview/USER_GUIDE.zh-TW.md` §3.4 and §4.1.
- **Verification:**
  - project `.venv`: ruff check, ruff format --check, mypy (637 files) clean; full pytest
    3216 passed, 7 skipped, 0 failed;
  - `C:\aepci-wk\venv` (reinstalled `-e ".[dev,office]"`, `--basetemp=C:/aepci-wk/bt`): ruff,
    format, mypy clean; full pytest 3193 passed, 30 skipped, 0 failed;
  - both runs include the other agent's uncommitted work in the tree;
  - commit 1's content alone was checked in an exported copy (ruff, format, mypy, 156 targeted
    tests passed);
  - E2E-01 (`tests/test_product_e2e_01.py`) passed in both suites;
  - real-browser test of the progress view (light, dark, 390 px, no horizontal scroll; the view
    has no buttons) with screenshots in `.scratch/turn-progress-ui/`.
  - One existing test changed: `tests/test_gateway.py`
    `test_conversation_cannot_execute_an_invented_tool_and_stops` now gives each invented call
    different arguments, so the count cap (now 150), not the new repetition guard, stops it; all
    its assertions are unchanged.
- **Decisions to note:**
  - Telegram still sends its status message at once (owner 2026-10-06, pinned by an existing
    test) rather than after 10 s; the 5 s edit limit is what prevents a stream.
  - The count cap and the repetition guard apply per pass of the tool loop (the conversation
    check's retry is a new pass); the time budget covers the whole turn.
  - A running model or tool call is not interrupted at the deadline.
- **Risks:**
  - Long turns now cost up to 150 model calls; the 30-minute budget is the practical bound.
  - A desktop or browser task that polls the same "look" more than 5 times with nothing in
    between stops with `tool_repeat_limit`; the person can reply 繼續.
  - Compaction removes old observations from the model's view in very long turns.
- **Next (after the owner's next Agent Web restart):**
  1. Settings → Conversation context shows "Tool calls per turn" 150 and "Time limit per turn"
     30.
  2. A multi-step chat turn shows the stepper, tool lines and "工具 n/150 · m:ss / 30:00",
     and the view disappears when the answer arrives.
  3. A Knowledge question shows "Knowledge：① 規劃 ✓ ② 查資料…".
  4. In Telegram, a slow turn edits one "⏳ Working on it…" message with the same lines.
  5. Telemetry: a stopped turn has a `turn.stopped` event.


## G2 anchor check made language-independent (2026-10-18, Claude Code)

**Status:** committed on main, **not pushed**, Agent Web **not restarted**. The owner's U7
rerun finished (commit 519b85a2) before the full suites were run; both are green.

- **Goal:** the G2 anchor check rejected correct translations (a Chinese question the model
  translated to English failed as "missing terms" and lost its English words as "added
  terms"). The owner approved a checker that needs no language knowledge.
- **What changed:**
  - `src/agent/gateway.py`: `VAULT_QUESTION_SCHEMA` gains optional `original_terms` (array) and
    `term_translations` (object); the tool route passes them to the Harness through
    `ToolAnchor.with_claims`; telemetry adds `anchor_verified`, `anchor_discarded`,
    `anchor_translations` counts.
  - `src/agent/harness_anchor.py`: `verify_claims` (substring check after whitespace, case and
    NFKC normalisation), coverage through verified terms, added terms licensed by verified
    translations, `AnchorCheck.translation_query` and the new record fields `verified_terms`,
    `discarded_terms`, `translations_used`.
  - `src/host_runtime/knowledge_harness.py`: `for_tool` passes the claims to `check_anchor`.
  - `src/capabilities/knowledge_query/handlers.py`: retrieval queries deduplicated by case and
    spacing (`_distinct`), so the translation query and the `query_rewrite.py` rewrites combine
    without searching the same query twice.
  - `benchmarks/knowledge_v1/questions/zh-core.json` (8 Traditional Chinese core questions) and
    `run.py --set zh` (`zh_core`, `choose`); README updated. The pinned bank is unchanged.
- **Where it is documented:** `docs/HARNESS_DESIGN.zh-TW.md` §5.6 G2; `docs/DECISIONS.md`
  2026-10-18 "G2 anchor check is language-independent"; `docs/TASKS.md` new section.
- **Verification (project `.venv`):**
  - ruff check, ruff format --check (873 files) and mypy on src + tests (627 files): clean;
  - targeted: `tests/test_harness_anchor_g2.py` (33), G1/G3/G4 rule tests, `test_gateway*.py`,
    every `test_knowledge_*.py`, `test_product_e2e_01.py`: all passed (156 in the rule/E2E
    subset; 383 in `test_knowledge_*` + `test_gateway*`);
  - full suites at 519b85a2 (after the U7 rerun): project `.venv` 3159 passed, 7 skipped,
    0 failed; `C:\aepci-wk\venv` (reinstalled `-e ".[dev,office]"`, `--basetemp=C:/aepci-wk/bt`)
    ruff, format and mypy clean, 3136 passed, 30 skipped, 0 failed.
  - No existing test was changed except the module docstring line of
    `tests/test_knowledge_benchmark_route.py`. All tests use fakes; the live benchmark was not run.
- **Risks:**
  - The model may not fill the new fields until it learns them from the schema description; then
    behaviour is exactly as before.
  - Translations themselves are not verified (only their keys); a wrong translation only widens
    retrieval.
  - Copying a required term into `original_terms` covers it even when the model's version
    dropped it; the model's version is still searched only as a supplement and any term it
    added that is not licensed is dropped.
- **Next:**
  1. After the owner's next Agent Web restart: ask a Chinese question in chat and check
     `host.data.anchor.translations_used`; then the owner decides when to run `--set zh`.


## Generic Harness hand-off rules G1–G4 implemented (2026-10-18, Claude Code)

**Status:** code, tests and docs committed on main, **not pushed**, Agent Web **not restarted**,
U7 **not rerun**. The owner approved G1–G4 after U7 ("好做"). Knowledge Strategy v1.2 K02+ stays
blocked on the owner.

- **Goal:** Knowledge Strategy v1.2 ADR-K6 option A. These are generic rules at the seam between
  the conversation tool loop and any domain Harness, not Knowledge special cases. They follow the
  regression plan in v1.2 §7.5: a frozen baseline, one commit per rule with failing-first tests,
  and E2E-01 assertions.
- **Commits:**
  - 6d0fe421 G1;
  - 9e89053b G2;
  - 209fb885 G3;
  - 0c9b1095 G4;
  - then one docs commit.
- **Where it is documented:**
  - design: `docs/HARNESS_DESIGN.zh-TW.md` §5.6 (§7.1 and §11.2 now carry the U7 figures);
  - decision: `docs/DECISIONS.md` 2026-10-18 "Generic Harness hand-off rules G1–G4";
  - v1.2 ADR-K6 is marked decided and implemented;
  - `docs/TASKS.md` has a new row, and the old tool-route decision line is ticked.
- **What changed:**
  - **G1:** `src/agent/harness_handoff.py` and `gateway.py`. A not-validated Knowledge result with
    a grounded record is the turn's answer, exactly the text the direct route shows; the record is
    kept.
    - With no output, the model answers and the Host appends a "Host 註記" note.
    - Failed Workflow runs, failed draft trial runs, and Host validator verdicts with
      `status: failed` (Coding Harness, DUT evidence) keep a Host note unless a later call of the
      same tool succeeded.
    - The Knowledge tool's `status` is now "succeeded" whenever the Harness produced output; the
      verdict lives in `harness_verdict` and `failure: knowledge_not_validated`. The benchmark
      grader therefore treats a tool-route partial answer like a direct-route one.
  - **G2:** `src/agent/harness_anchor.py`. The deterministic anchor check; the Knowledge adapter
    answers the original sentence.
    - An accepted model version goes into `KnowledgeQueryRequest.supplementary_queries`, which
      only the wiki-primary retrieval uses.
    - Every tool record has `arguments`; the Knowledge record has `anchor`.
  - **G3:** optional `SkillManifest.asset_bindings` and `bound_skill`; `harness_skill(skills, asset)`
    is used by the tool route, the direct route and the assistant tool.
  - **G4:** `output_limit_chars` and `full_result_hint` from the Knowledge adapter; `capped` in
    the loop.
- **Verification:**
  - Baseline at ac9221e9:
    - project `.venv` full pytest: 3099 passed, 7 skipped;
    - subset (E2E-01..05, DUT, the 47 test files that import `agent.gateway`, knowledge unified,
      conversation harness): 565 passed, 1 skipped, 1 order-dependent flake
      (`test_ai_proposed_changes`, passes alone);
    - `C:\aepci-wk\venv` (run from a worktree at HEAD): 3075 passed, 30 skipped, 1 failed
      (`test_script_tools` `script_timeout`, under CPU contention).
  - Final:
    - project `.venv`: ruff check, ruff format --check (873 files) and mypy (627 files) clean;
    - full pytest: 3136 passed, 7 skipped, 2 failed. Both failures are real-browser tests
      (`test_browser` signed-in profile, `test_schedule_web` panel) and pass on rerun;
    - `C:\aepci-wk\venv` (reinstalled `.[dev,office]`): ruff and mypy clean, full pytest 3115 passed, 30 skipped, 0 failed.
  - Each rule's subset run was green: 582, 623, 688 + 1 flake, 699 passed.
  - All tests use fakes. No live model, benchmark, install or vault was touched.
- **Changed existing tests:** both in `tests/test_knowledge_unified.py`, both required by the new
  rules.
  - G1: the unvalidated case now expects the Host note after the model's text.
  - G2: the three fakes take the anchor, and the first test also asserts that the original
    sentence reaches the adapter.
- **Risks:**
  - G2 can reject the model's version often for Chinese questions that the model translates.
    There is no bilingual dictionary; only the Skill procedure's terms act as a glossary. A
    rejection is safe (the original alone is used) but loses retrieval breadth.
  - The original sentence is now the question. A long multi-part message is asked as a whole.
  - G1's note can appear on turns where the model correctly explains a failed Workflow; that is
    intended.
  - Turns where the model wrote a Knowledge rewrite will differ from U7 on purpose.
- **Next:**
  1. The owner reviews, then checks `/api/tasks` and restarts Agent Web.
  2. Live checks:
     - a partial Knowledge answer in chat (for example Q1041 "What is an eye diagram…") should show
       the same "已查到可引用的部分資料：…未能以證據支持：…" text as the direct route;
     - the conversation's stored outcome should have `tools[].arguments` and `host.data.anchor`;
     - a long answer should not end at 12,000 characters.
  3. Rerun U7 with the same four commands, compare per question with `u7-report.zh-TW.md`, and
     compute the intent drift rate from `anchor.outcome`.

## U7 baseline measured (2026-10-18, Claude Code)

U7 ran on the 36-question core, chat and direct routes, two passes each:
`benchmarks/knowledge_v1/runs/u7-report.zh-TW.md`. The tool route is 11.5 pp behind the direct route
on the same 26 questions (threshold 5 pp); the gap is mostly Q1041/Q1061/Q1091 (partial answers marked
not validated: G1). (Done since: the owner approved G1–G4, implemented above.) Original next step: the owner decides whether to implement ADR-K6 G1–G4 (the G2 design
discussed 2026-10-18: original question as anchor, structured rewrite with an entity-preservation
check, added terms must come from history or the bilingual glossary, optional model check; first log
the tool's question argument). After G1–G4, rerun the same four commands and compare per question.
Knowledge Strategy v1.2 K02+ stays blocked on the owner.

## Knowledge Strategy v1.2 (2026-10-17, Claude Code) — awaiting owner confirmation

**Status:** docs and contract design only, committed on main, not pushed. **v1.2 awaits the owner's
confirmation of three things:**
1. the success thresholds (`docs/proposals/KNOWLEDGE_STRATEGY_v1.2.md` §5.5 and the reviewed-question
   precondition in §5.6);
2. BI Schema v0 (`docs/proposals/bi_schema_v0/`);
3. the integrated schedule (§7.3).

**AEP-K02 and everything after it are still blocked until the owner approves v1.2.** Do not start
AEP-K02. Do not create issues or PRs.

- **Goal:**
  - Apply the owner's decisions of 2026-10-17 (v1.2 §0.2, D1-D6). The owner's item 3, Harness rules
    G1-G4 versus measuring U7 first, is **not decided**; it stays pending as ADR-K6 / AEP-K13.
  - D2a: the owner supplied the BI Knowledge Base document (17-slide PDF, internal, kept out of the
    repo). Schema v0 keeps its entity types and relationships exactly and cites pages.
- **Files:**
  - `docs/proposals/KNOWLEDGE_STRATEGY_v1.2.md` and `KNOWLEDGE_STRATEGY_v1.2_DIFF.md`; v1.1 is kept
    unchanged.
  - `docs/proposals/bi_schema_v0/{bi_schema_v0.json,README.md}`.
  - `docs/proposals/knowledge_benchmark_v0/{questions.json,README.md}`.
  - `docs/contracts/knowledge-api/`: `openapi.yaml`, 11 files in `schemas/*.schema.json`, and 19 mock
    responses in `mock/*.json` plus `mock/index.json`, with a README for the Atlas Coding Agent.
  - `tests/test_knowledge_strategy_docs.py`.
  - The `docs/README.md` index and a `docs/TASKS.md` row.
- **How the JSON was made:**
  - The schema, benchmark and mock JSON were generated from one synthetic catalog by a throwaway
    script, so ids and triples agree.
  - The script is not in the repo. The committed JSON is the source now; edit it directly.
  - The test keeps it consistent.
- **Key facts:**
  - BI Schema v0:
    - 12 types, all `source-bi-doc`.
    - 14 relationship names over 22 (name, domain) sources: 18 `source-bi-doc` (8 with field names
      printed in the document, 10 `provisional` until `bi_schema.py` is available) and 4 `proposed-v0`
      (Opportunity `account` / `customer_product` / `test_solutions`, Signal `mentions`).
  - In the document, Ecosystem cards are supplier/partner companies, Account cards are customers, and
    Node is a fixed list of value-chain positions.
  - `tests/test_product_e2e_01.py:11, 331` builds `agent.gateway.Gateway`. The G1-G4 regression plan is
    in v1.2 §7.5.
  - v1.1's evidence-id backfill into Raw would break Phase 7 Knowledge parity; it is now a derived
    index (ADR-K4).
- **Verified:**
  - `.venv` `ruff check .` passed; `ruff format --check .`: 866 files formatted.
  - `mypy`: no issues in 620 source files.
  - The OpenAPI YAML parsed with PyYAML from the system Python 3.12; the repo `.venv` has no yaml
    library, so the repo test checks the YAML's `$ref` targets by text.
  - All 33 new JSON files parse.
  - `pytest tests/test_knowledge_strategy_docs.py`: 27 passed.
  - `pytest -q -p no:cacheprovider tests -k "docs or readme or tasks"`: 42 passed, 3057 deselected.
  - No model call, benchmark, live install or vault write.
- **Pending owner decisions:**
  - the thresholds, Schema v0 and the schedule;
  - D3 (G1-G4 or U7 first);
  - N1: `bi_schema.py` / `bi_ingest.py` for the provisional names, the 8th Node, the Opportunity and
    Signal links, the Node extension and real-card import;
  - N2: named Domain Reviewers;
  - Q10: Knowledge API scopes;
  - ADR-K2 central DB;
  - ADR-K5 domain review;
  - ADR-K8 BI data class;
  - ADR-K9 PR vs main;
  - the AEP- prefix;
  - freezing v0.1 with Atlas.
  The full list is in v1.2 §8.2.
- **Next:**
  1. The owner reviews v1.2 and answers §8.2.
  2. After approval, start with AEP-K02 (benchmark review, synthetic fixture, Wiki-only baseline) and
     AEP-K03 (Schema Registry). Both stay outside the E2E-01, Phase 7 and S3 hot spots.
  3. Meanwhile, the Atlas Coding Agent can build against `docs/contracts/knowledge-api/mock/`.


## Suggested Skills from experience, slice S2 (2026-10-16, Claude Code)

**Status after hand-back:** S2 pushed (897c28cb, CI green); full pytest in the project
`.venv` re-run after the fix: 3092 passed, 7 skipped. Agent Web restarted on it. **Next:
wait.** The owner wants to watch real Suggested Skill cards before S3; do not start S3
until asked.

Goal: S2 of `docs/phases/SKILL_SUGGESTIONS.md`: a group the nightly pass qualifies becomes a
"Suggested Skill" card in Agent Web → Reviews for the person whose requests formed it, with
evidence, Ignore / Snooze, and settings (on/off, Sensitivity Low / Normal / High, request
cap). No draft, candidate or install (S3). The owner confirmed S1's dry-run grouping
("looks reasonable") and asked that each person can set the sensitivity in Agent Web.
As built: that document's section "S2 as built"; decision `docs/DECISIONS.md` 2026-10-16
"Skill suggestions S2: cards per person, ids not text, sensitivity per Host"; row in
`docs/TASKS.md`; USER_GUIDE 6.6 "建議的 Skill". Code commit 46eb861f, docs commit after it,
on main, not pushed.
- **Code:** `experience_proposals.py` (`ReviewProposal.actor` / `reason_code` /
  `suggestion`, additive `actor` column migration, `all(actor)` / `get(id, actor)`,
  `suggest`, `make_cards`); `skill_suggestions.py` (`SENSITIVITY` rows, `ignored` group
  status and `set_ignored`, `updated` items, `card` / `card_note`, `evidence_excerpt`);
  `web.py` (`experience_review` makes cards, `reviews` / `review_decide` filter by
  `runtime.actor` and cut excerpts at view time, `/api/reviews/decide` takes
  `reason_code`); `web_page.py` (card, Ignore box, evidence opens the conversation at the
  request via `data-asked-id`, settings fieldset). Tests `tests/test_skill_suggestion_cards.py`
  (17); two exact-field assertions extended for the new fields
  (`test_skill_suggestions.py` report item, `test_knowledge_pipeline_web.py` settings).
- **Verified:** ruff check, ruff format --check, mypy (src+tests) in the project `.venv`
  and in `C:epci-wkenv` (reinstalled `.[dev,office]`). Full pytest: project `.venv`
  3091 passed, 7 skipped, 1 failed (the settings exact-dict test above, updated for the new
  field and re-run green); CI-like venv after the fix 3069 passed, 30 skipped. Real browser
  render of the card (light, dark, Ignore box, settings, opened conversation, 390 px wide):
  screenshots in `.scratch/skill-suggestion-ui/`. All models are fakes.
- **Not verified / not done:** no live pass, Agent Web not restarted (check `/api/tasks`
  first). Settings are per Host workspace, not per member: Agent Web serves one person
  (`runtime.actor`) with no per-request member sign-in, so a per-member map could not be
  edited; a member with their own Windows login has their own workspace. The nightly pass
  still mines only `runtime.actor`. No telemetry events or end-of-conversation card (S5).
- **Next (owner):** restart Agent Web on this working tree; Reviews → "Review settings and
  the latest report": the Suggested Skills box shows the switch, the three sensitivity
  rows in words and the cap; press **Review now** (one grouping call when there are new
  requests) or wait for the night; a qualified group appears under **To decide** as a
  Suggested Skill card counted in the header; press a request to open that conversation;
  try Ignore with and without a reason and Snooze. Then S3 (drafts and Create draft).

## Shared Platform on 172.25.228.141 over https with a pinned certificate (2026-10-16, Claude Code)

Goal: owner request 2026-10-16, colleagues reach the Shared Platform on 141 directly (no SSH
tunnel) with a self-signed certificate. Design and as-built: `docs/phases/BRIDGE_ENROLLMENT.md`
"TLS and certificate pinning"; decision `docs/DECISIONS.md` 2026-10-16 "A self-signed Shared
Platform is trusted by a pinned SHA-256 fingerprint"; row in `docs/TASKS.md`. Code commit
70ef34a6 + 33bf7d8c (not pushed), docs commit after them.
- **Hand out:** Member Portal `https://172.25.228.141:8776`, Bridge API
  `https://172.25.228.141:8775`, certificate SHA-256
  `83:95:B0:90:90:1A:28:1E:6B:0D:E9:92:F5:33:A6:2B:49:9D:5A:3A:19:08:8D:30:F6:C1:91:42:BA:C5:BA:8B`
  (valid until 2029-01-18). Members follow USER_GUIDE 10.1.1.
- **141 state:** bundle 70ef34a6 installed; `platform.json` `listen_host` 172.25.228.141, ports
  8775/8776, cert/key in `%LOCALAPPDATA%\AgenticEngineeringPlatform\shared-platform-tls\` (key
  ACL: OpenLab only; generated on 141 with Git's openssl, never copied); backup
  `platform.json.bak-20261016-*-before-tls`. Firewall rule "AEP Shared Platform" TCP 8775/8776
  inbound, all profiles but only on the Ethernet adapter (the LAN is an unidentified = Public
  network there). Scheduled task "AEP Shared Platform": `cmd /c start-platform.cmd >>
  C:\aep-platform\platform.log`, S4U as OpenLab, triggers at startup + every 5 minutes,
  IgnoreNew (a killed platform came back within 60 s). To redeploy: `Disable-ScheduledTask`,
  stop processes under the install root, unpack + install, `Enable-` and `Start-ScheduledTask`.
  The SSH tunnel 28775/28776 no longer works for the platform (it is TLS on the LAN address).
- **This PC:** host.json `platform`/`publishing` now https + the pin (backup
  `host.json.bak-20261016-183648-before-141-https`); Agent Web restarted on the working tree at
  18:37 with no task running. Live checks: Settings card shows the pin and `matches_pin`,
  catalog answered (18), signed-in portal link, Bridge probe as bridge-tp401555 (leo.chi).
- **Verified:** see the TASKS row (ruff, format, mypy, both full suites, bundle step replay).
- **Not verified:** a reboot of 141 (autostart at boot; only the 5-minute trigger was proven),
  a colleague's PC end to end, a real browser importing the `.cer`. `platform.log` stays empty
  until Python flushes its output (buffered).
- **Next (owner):** hand out the two URLs and the fingerprint; when 141 next reboots, check
  `https://172.25.228.141:8776` answers; consider removing the used bootstrap invitations from
  141's `platform.json` (each restart writes a new `invitation-links-*.json` for unused ones).

## Weekly report not bundled + starting page for the shortcut (2026-10-16, Claude Code)

Goal: two owner requests 2026-10-16. Done and committed on main (not pushed): 8598d172
(weekly report personal), 7826781d (starting page), c7aa1df9 (README grant test);
decisions `docs/DECISIONS.md` 2026-10-16 "The weekly report is personal, not bundled"
and "`aep-host open` shows a starting page ..."; rows in `docs/TASKS.md`.
- Weekly: `host_runtime.assets.shipped()` no longer has the weekly Skill/Workflow; they
  are `personal()`, installed/exported only with `--include-personal` or the user
  variable `AEP_INCLUDE_PERSONAL_ASSETS=1`. Owner's PC: his live workspace already has
  them (untouched); to get future weekly versions through `update.cmd`, set
  `AEP_INCLUDE_PERSONAL_ASSETS=1` in his user environment once (not done by this
  session). `weekly-*.cmd` and `schedule-weekly.ps1` deleted from the bundle dir.
- Startup page: `aep-host open` opens `workspace/agent-web-starting.html` at once and
  hands the token URL over through `agent-web-starting.js` (only while `ready`, 15 s).
- Verified: ruff check / format --check / mypy (src+tests) in the project `.venv` and a
  fresh `.[dev,office]` venv; full pytest in the fresh venv on 7826781d (3002 passed,
  30 skipped; the 2 README-grant failures fixed by c7aa1df9, re-run green); full pytest
  in the project `.venv` on the shared working tree (3033 passed; failures: the same 2
  README-grant tests, fixed, plus 2 browser tests that pass alone under less load —
  one is another agent's untracked `test_platform_certificate_pinning.py`); the
  `verify.yml` Windows bundle step replayed with temp USERPROFILE/LOCALAPPDATA
  (`-NoShortcut -NoAgentSkills`) to the end, including the new weekly assertions.
- NOT verified: the real desktop shortcut on this PC (needs Agent Web stopped; the owner's
  live Agent Web was not touched). Next (owner): set `AEP_INCLUDE_PERSONAL_ASSETS=1` on
  his PC if he wants weekly upgrades from bundles; try the shortcut once with Agent Web
  stopped (after checking /api/tasks) and see the starting page switch to Agent Web.

## Install card after a conversation drafts a Workflow or Skill (2026-10-16, Claude Code) — latest

Goal: owner request 2026-10-16 "bring back the small card that lets the person install a
Workflow right in the conversation". Done and committed on main (not pushed); decision
`docs/DECISIONS.md` 2026-10-16 "A conversation that drafts a Workflow or Skill shows its
install card", contract `docs/CONTRACTS.md` "Draft install card", row in `docs/TASKS.md`.
- Findings: the old card was only the `/api/approvals` request the resident model made when it
  chose `authoring__install_workflow` (often it did not); agent-mode Claude Code / Copilot drafts
  came through `/mcp/authoring` with the shared assistant token, so they had no conversation
  (and were all labelled `external:copilot`) and waited only in Capabilities.
- Now every turn that creates or revises a draft ends with one `dr-` card (Install / Run once to
  try / Not now) in Agent Web and Telegram (Install / Not now); `host_runtime/draft_cards.py`.
- Verified: ruff check, ruff format --check, mypy (src+tests); full pytest on a clean worktree
  of this change: project `.venv` 3031 passed, 7 skipped; fresh venv with only `.[dev,office]`
  3008 passed, 30 skipped. `tests/test_draft_install_cards.py` (14) includes Telegram (fake Bot
  API) and a real browser (card 394x346, Install 88x44).
- NOT verified live (owner): restart Agent Web on this code (not done by the agent); in a
  Gateway chat ask for a small Workflow: the card appears under the answer; press Install: the
  card says Installed and "Run <name>" opens below it. With Settings > Agent mode on for Claude
  Code, ask it to make a Workflow with the AEP creator skill: the same card after its turn.
  In Telegram ask for a Workflow: Install / Not now buttons under the answer.
- Risks: a Skill installed from the card is used after an Agent Web restart (as before); Try
  only appears for read-only Workflows whose required fields have defaults.

## Colleague user guide (2026-10-16, Claude Code)

Goal: owner request 2026-10-16, the manual shipped to colleagues explains every setting
and feature. Done and committed on main (not pushed): `deploy/windows-preview/INSTALL.zh-TW.md`
(install only) + `deploy/windows-preview/USER_GUIDE.zh-TW.md` (chapters 0-17), shipped in
the bundle and the release folder; row in `docs/TASKS.md`. Verified: ruff check, ruff
format --check, mypy, the bundle tests and the full suite in the project `.venv`.
Not verified: the guide against a live Agent Web screen (labels come from the code).
Next (owner): read the guide once on a colleague PC; fix the Knowledge page hints that
still say "step 2/3" for convert/ingest (code, not the guide); decide whether
`weekly-*.cmd` (they send `weekly.preview/apply/mail`) still match the current
`/weekly` Skill, which declares only `run`. Earlier work continues below.


## LLM gateway in the Windows installer (2026-10-16, Claude Code) — latest

Goal: owner decision 2026-10-16 "the installer must include the LLM gateway"; design and
as-built in `docs/phases/LLM_GATEWAY.md`, decision `docs/DECISIONS.md` 2026-10-16 "The
installer ships an LLM gateway ...", row in `docs/TASKS.md`. Committed on main, not
pushed (phase A 52aabea9, 5617be76; phase B commits after them).
- Code: `src/llm_gateway/` (launcher + streaming patch + offline LiteLLM flags,
  config/secrets/state, Kerberos token refresh, control, CLI), `aep-host gateway ...`
  (`host_runtime/cli.py`), `host_runtime/gateway_link.py` (failure explanation, card),
  Agent Web `GET/POST /api/settings/gateway` + card in `web_page.py`, Telegram
  `TelegramIngress.explain_failure` (set in `host.build_telegram`).
- Bundle: lock `deploy/windows-preview/gateway/requirements.txt` (106 wheels, no
  `litellm-enterprise`), builder `--gateway-wheel-dir` -> `wheels-gateway/`,
  `release_windows.py` downloads it; `install.ps1` (`-NoGateway`, `-GatewayInstallOnly`,
  long-path pre-check, `gateway-venv`, init + `--user-env`, model only when `host.json`
  has none, refresh/autostart/start), `update.ps1`, `uninstall.ps1`; `verify.yml`
  bundle smoke extended. Manual section "設定 LLM gateway（最重要）" right after section 2.
- This PC: the owner keeps his gateway (port 4000, task `LiteLLM_Gateway`, `.env` in
  `C:\Users\Chi_L\Documents\claude\customized_LLM_vscode_plugin`). AEP's gateway home
  `%LOCALAPPDATA%\AgenticEngineeringPlatform\gateway\gateway.json` was written with
  `managed: false`, `secrets_file` = that `.env` (read for the expiry only), `python` =
  his venv (for the LiteLLM version); AEP autostart off. `aep-host gateway status` here:
  serving (run outside AEP), token 9.8 days left, LiteLLM 1.94.1. No task, registry
  value, token, live host.json or live Agent Web was touched; Agent Web not restarted.
- Verified: ruff check / format --check and strict mypy (src+tests) in the project
  `.venv` and in a fresh venv with only `.[dev,office]`; full pytest in that CI-like
  venv (2993 passed, 30 skipped) and in the project `.venv` (see `docs/TASKS.md` /
  the final report); both `verify.yml` bundle steps replayed locally with a temporary
  USERPROFILE/LOCALAPPDATA (`-NoShortcut -NoAgentSkills` added). The Windows step ran in
  two parts: the first stopped on two CI-script issues, then fixed (the status check
  assumed nothing serves port 4000, which is false on this PC; `Add-Member credentials`
  needs `-Force` now that the installer maps the gateway key); the second part resumed
  there and ran to the uninstall. The Shared Platform step ran in one go. Real browser:
  card 717x348, Start 88x44.
- NOT verified: a real `refresh-token` against Keycloak, a real start of AEP's gateway
  from the bundle with a model answer on a domain PC, the Task Scheduler registration
  (tests use fakes; CI uses `-GatewayInstallOnly`), the card against the live Agent Web
  (needs a restart on this code).
- Next (owner): restart Agent Web on this code; Settings > LLM gateway shows "Running ·
  127.0.0.1:4000 · run outside AEP", the token expiry, and Test answers. On a colleague's
  domain PC: install a released bundle; the card shows Running and Test answers. Push
  and watch CI (the bundle step now downloads ~135 MB more and installs the gateway).

## Hermes skill pack and bundled Skills (2026-10-16, Claude Code)

Goal: owner request 2026-10-15 + decisions 2026-10-16, `docs/phases/HERMES_SKILL_PACK.md`
(design, scan findings, bundle list, phase B, this PC). Decision `docs/DECISIONS.md`
2026-10-16 "Bundled Skills: in-use on, skill packs off, ..."; row in `docs/TASKS.md`.
Committed on main, not pushed (phase A ad9811c9, 16e100f8; phase B commits after
them). The CI smoke assertions for it went into `verify.yml` with 96f551b5.
- Pack: `packages/hermes-skill-pack` (51 skills: manifests `hermes/<name>`, folders
  `skills/vendor/hermes-<name>`, `pack.json`, `NOTICE.md`), made by
  `scripts/port_hermes_skills.py --source %LOCALAPPDATA%\hermes\skills --out
  packages\hermes-skill-pack [--personal-out <outside repo>]` (deterministic; refuses
  credentials, owner data, non-MIT licences).
- Bundle/installer: builder copies `hermes/` + template `aep-skills/` (two
  knowledge-query manifests); `install.ps1`/`update.ps1` run `aep-host assets
  install-bundled --bundle <root>` (`host_runtime/skill_packs.py`): in-use on, pack
  off, never overwrite / re-enable / bring back removed. Pack folders in
  `workspace/agent-skills/`; copied to `~/.claude/skills` / `~/.copilot/skills` only
  while switched on and only where AEP's setup is (`asset_shelf` switch/remove with
  `environment`, `agent_setup.link_pack_skill` / `unlink_pack_skill`; `remove()` takes
  all pack copies out). Builder scan allow-list `ALLOWED_PLACEHOLDERS`.
- This PC: 58 Hermes skills (51 + 7 internal; internal `business-cards` kept) switched
  off in the live workspace, 58 folders in `workspace/agent-skills`; internal sources in
  `%LOCALAPPDATA%\AgenticEngineeringPlatform\hermes-personal-pack`; backup in
  `%LOCALAPPDATA%\AgenticEngineeringPlatform\backups\20261016-before-hermes-pack`. No
  coding-agent folder touched, Agent Web not restarted.
- Verified (2026-10-16): ruff check ., ruff format --check . (838 files), strict mypy
  src+tests (602 files) in the project `.venv` and a fresh CI-like venv
  (`%LOCALAPPDATA%\Temp\aepci3`, only `.[dev,office]`). Full pytest: project `.venv`
  2944 passed, 6 skipped, 1 failed; CI-like venv 2920 passed, 29 skipped, 2 failed. The
  common failure, `test_ai_proposed_changes.py::...[telegram-...-bot token is not saved]`,
  also fails on a clean worktree of e03a025a: it reads whether a Telegram bot token is
  saved on this PC (machine state, not this change). The other, `test_browser.py::
  test_a_throwaway_profile_is_removed_although_the_browser_holds_it`, passed on rerun
  (timing). The verify.yml "Build and install Windows offline preview" step was replayed
  locally with a throwaway USERPROFILE and `-NoShortcut`: bundle built from this tree,
  installed, every assertion passed (25 on, 52 off; the shipped Knowledge 1.0.0 set
  aside; knowledge-query moved to disabled stayed off on reinstall; ask
  needs_input/unknown_skill); `uninstall.ps1` refused the temporary root (it only removes
  under `%LOCALAPPDATA%\AgenticEngineeringPlatform`), as designed.
- NOT verified: a real Claude Code / Copilot session using a switched-on `hermes-*`
  skill (tests use a temporary home); Agent Web switch on/off against the live
  workspace (needs a restart on this code).
- Next (owner): restart Agent Web on this code; Capabilities > Skills > filter
  "Switched off" lists 58 `hermes/...`; switch one on (e.g. `hermes/docx`) and check
  `%USERPROFILE%\.claude\skills\hermes-docx` appears (only if AEP's coding-agent setup
  is installed there), switch off and check it is gone. Then release a bundle
  (`scripts/release_windows.py`).

## Agent mode for Claude Code / Copilot in Agent Web (2026-10-15, Claude Code)

Goal: owner-approved design `docs/phases/AGENT_MODE_BACKENDS.md` ("Revised rules (owner,
2026-10-15)" replace items 1-3). Decisions `docs/DECISIONS.md` 2026-10-15 "Agent mode for
Claude Code and Copilot in Agent Web; Codex stays text-only", "Agent mode email: read in
scope, send only from one card per message", "Agent mode audit: ...", "Knowledge pipeline
as agent tools; push stays on the Knowledge page"; contract `docs/CONTRACTS.md` "Agent
mode (approval cards for coding-agent backends)"; row in `docs/TASKS.md`; design doc
status and "Implementation" section updated. Committed on main, not pushed (146431dd,
f9528f3a, 1b2710e5, 86635d36 + the docs commit).
- Backends: **Claude Code** relays through `--permission-prompt-tool
  mcp__aep-agent__permission` (`--setting-sources ""`, run `--settings` that ask for every
  Bash/PowerShell/WebFetch/WebSearch, `--plugin-dir` with AEP's skills, strict MCP config
  with `aep-agent`, `aep-assistant`, `aep`); **Copilot** over ACP (`copilot --acp`,
  `host_runtime/acp_client.py`, allow once / reject once, never "always"); **Codex stays
  text-only** (`codex exec` has no relay; Codex is not installed here, nothing verifiable;
  Settings and the chat line say so, enabling it is refused). With agent mode off (the
  default) every backend runs exactly as before.
- Code: `common/agent_guard.py` (protected places, command guard, `judge`),
  `host_runtime/agent_mode_settings.py`, `host_runtime/agent_mode.py` (runs, `pm-` cards,
  10-minute Deny, audit, `/mcp/agent` tools incl. Knowledge), `host_runtime/agent_mail.py`
  (`outlook_search`/`outlook_read`/`outlook_draft`, `ml-` cards),
  `integrations/outlook_mail.py` (read only), `integrations/outlook_send.py` (send/discard,
  only from `AgentMail.decide`), `capabilities/mail_read` (`outlook.search`,
  `outlook.read`, registered when a Workflow uses them), `conversation_backends.py`
  (`AgentLaunch`, `_claude_agent`, `_copilot_agent`), `web.py` (routes `/api/agent-mode`,
  `/api/agent-mode/settings`, `/api/agent-mode/session`, `/api/cards?session_id=`,
  `/mcp/agent`), `web_page.py` (Settings > Agent mode; chat line "Agent mode · works in
  ..." + "Folders..."; cards polled under the waiting turn; `action_cards` in history),
  `conversations.py` (`ConversationMessage.action_cards`).
- Verified: ruff src tests clean; mypy src clean; `tests/test_agent_mode.py` +
  `tests/test_agent_mail.py` 59 passed (incl. real browser: permission card 640x359,
  Allow 88x44, Allow pressed in the page lets the fake run finish; mail card 640x314,
  Send 88x44; real `claude` 2.1.296 and `copilot` 1.0.95 accept every agent-mode flag in
  a temp home and stop at sign-in / answer ACP `initialize`); related suites
  (conversation backends, Outlook draft, mail draft capability, AI proposed changes)
  passed. Full suite after the last code change: 2914 passed, 6 skipped, 0 failed (17 min 27 s); an earlier full run found one page-source assertion (`test_avatars.py`), fixed in 86635d36.
- NOT verified: a real model turn through the relay (no sign-in in a temp home, and the
  person's own `~/.claude` / `~/.copilot` were not touched), Outlook COM against the real
  mailbox (search/read/send adapters are written to the object model and tested with
  fakes only), Copilot's real `session/request_permission` payloads (ACP spec shape).
- Live steps (owner; Agent Web restart is not done by the agent): (1) restart Agent Web
  on this code; (2) Settings > Agent mode: tick Claude Code (and/or GitHub Copilot), set
  the email scope (folders, days, excluded senders/folders), Save; (3) new conversation,
  choose Claude Code (PUBLIC session dialog as before): under the composer "Agent mode ·
  works in ...\workspace\agent-sessions\conversation-..."; "Folders..." to add a
  read-only folder (e.g. the OneDrive LLM wiki); (4) ask it to write a file in its folder
  (no card), to read a file elsewhere (card: Allow / Allow this folder for this
  conversation / Deny), to run `git status` (card with the command and folder); leave one
  card 10 minutes: Deny; (5) ask it to read `~/.ssh` or run `netsh advfirewall ...`:
  refused without a card; (6) ask it to find a mail: one card the first time, then
  results; ask it to email someone: draft in Outlook Drafts + card with Send / Keep as
  draft / Cancel (test with your own address first); (7) Tasks lists `agent_permission`,
  `agent_mail`, `agent_turn` rows; `workspace/agent-mode/audit.jsonl` has every request;
  (8) Telegram: unchanged (Gateway only).
- Risks: Copilot loads the person's user-level MCP servers and settings next to AEP's
  (a user-level "allow all" in Copilot's own settings could bypass the relay; not
  inspected); the command guard is pattern-based (a backstop: every command already needs
  a press); Outlook's object-model guard may prompt when reading sender addresses on a
  PC without up-to-date antivirus status; a turn can take up to 30 minutes when cards
  wait; cards of a turn whose Agent Web restarted are denied (no waiter).
- Next: owner live check; then optionally a Codex relay (verify `codex app-server`
  approval requests on a PC with Codex), and a Stop button for a running agent turn.

## AI proposes, the person applies (2026-10-15, Claude Code)

Goal: owner-approved design `docs/phases/AI_PROPOSED_CHANGES.md` (version 1, every kind;
Telegram applies only `laya`, `workflow_settings`, capability switch on/off). Decision
`docs/DECISIONS.md` 2026-10-15 "Change proposals: one tool, one card component, Apply
through the cards' own writers"; contract `docs/CONTRACTS.md` "Action card and change
proposal"; row in `docs/TASKS.md`. Committed on main, not pushed (6a7cd6aa, 36d2c29f +
this docs commit).
- Card component (for the agent-mode slice, `docs/phases/AGENT_MODE_BACKENDS.md`):
  `common/action_cards.py` (`ActionCard`, `CardButton` action/label/style, `CardRow`,
  `CardLink`, `card_in`, `telegram_card`, `CARD_TAP`), `host_runtime/card_store.py`
  (`PendingRecord`, `CardStore`, `new_card_id`); Agent Web `renderActionCard`,
  `/api/cards`, `/api/cards/decide`, Tasks > Pending changes; `AgentWeb.decide_card`
  dispatches by card-id prefix (`cp-`); `ConversationMessage.action_card`,
  `LocalState.set_message_card`.
- Proposals: `common/change_proposal.py` (tool `propose_change`, guidance, kinds,
  credential check), `host_runtime/change_proposals.py` (`ChangeProposals`: one plan,
  snapshot and apply per kind, store `workspace/proposals/change-proposals.json`,
  Tasks kind `proposal`). Gateway offers the tool only with a session id and ends the
  turn on a card. Telegram `_decide_card` (owner only) and the card in `_converse`.
- Also fixed: the Laya card showed old values after Save until a restart.
- Verified: ruff src tests clean; mypy src clean; `tests/test_ai_proposed_changes.py`
  48 passed (incl. Telegram end to end and a real browser: card 640x288, Apply 88x44);
  related suites (chat workflow forms + Telegram, Laya, Telegram ingress, conversation
  turns, gateway, tool schema, capability shelf, shared platform settings) 110 passed.
  Full suite after the last code change: 2854 passed, 6 skipped, 1 failed under load
  (`test_agent_web.py::test_capability_workspace_is_interactive_in_a_real_browser`,
  passed when rerun alone), 21 min 43 s.
- NOT done: live check (owner). Steps: (1) restart Agent Web on this code (never done
  by the agent); (2) in a Gateway chat type "把 Laya 改成 shadow" / "turn Laya to
  shadow": expect a card "Change Laya decision acceleration" with Mode off -> shadow,
  the reason, "takes effect after Agent Web restarts", Apply/Cancel; (3) Cancel once,
  ask again, Apply: the card shows "Applied: Saved to host.json ..." and "Open Settings
  > Laya" shows Shadow; host.json `laya.mode` is shadow (restart to run it); (4) ask
  "switch off <some Workflow>" in Telegram: Apply/Cancel buttons, tap Apply; (5) ask
  "remove <Workflow>" or "enroll this PC" in Telegram: no buttons, "Open in Agent Web to
  apply: Agent Web on this PC, Tasks > Pending changes"; apply it there; (6) ask to set
  a token in chat: refused with where to paste it; Tasks lists every proposal.
- Risks: the model must choose `propose_change` from the tool description (no
  deterministic intent route like "run X"); credential detection is a heuristic (a
  32+ character mixed-case alphanumeric value is refused even if harmless); cards
  stored in an answer are refreshed only while pending; Telegram's card edit falls back
  to a new message if Telegram refuses the edit.
- Next: the agent-mode slice reuses the component: add a `PendingRecord` subclass and a
  handler prefix (for example `pm-`) in `AgentWeb.decide_card`, buttons
  allow/allow_session/deny or send/keep_draft/cancel, `preview` for commands/diffs/mail.

## One-click Member Portal sign-in and Library card content (2026-10-15, Claude Code)

Goal: owner requests — Agent Web's "Open Marketplace" opens the Member Portal already
signed in as this PC's member; a Library card shows the asset's real content. Design
`docs/phases/PLATFORM_OVERVIEW.md` "One-click sign-in from Agent Web" and "Library card
content in Agent Web"; decision `docs/DECISIONS.md` 2026-10-15 "Agent Web opens the
Member Portal signed in with a single-use browser ticket"; contract `docs/CONTRACTS.md`
"Browser sign-in ticket"; row in `docs/TASKS.md`. Committed on main, not pushed
(e44f2652, 927de9e9, ff2a46c4 + this HANDOFF commit).
- Platform: `control_plane/member_ticket.py`; `member_http.py` routes `browser-ticket`
  (member session -> `ticket` id:secret, 60 s, single use, fingerprint in memory,
  refused for disabled members) and `sign-in/ticket` (`Authorization: Ticket ...` ->
  `session`, `login`, `expires_at`; earlier `Agent Web sign-in` login revoked). Portal
  page (`member_page.py`) redeems `#ticket=`, drops the fragment, opens `#tab=` and
  `#asset=` (Marketplace detail).
- Agent Web: `platform_publish.py` `browser_ticket`, `asset_content`; `web.py`
  `portal_link`, `asset_content`, routes `/api/platform/portal-link` and
  `/api/platform/asset-content`; `web_page.py` `openPortal` on every portal link
  (fallback: sign-in page + note to Settings > Shared platform), Library card content
  (Skill/Workflow sections, metadata facts, actions in an aside; stacked under 640 px),
  `contentMarkdown` keeps http(s) links only, per-version page cache.
- Verified: ruff src tests clean; mypy src clean; new tests
  `tests/test_browser_ticket.py` (7) and `tests/test_library_content_web.py` (6), both
  with real-browser checks, pass; related suites (capability shelf, shared platform
  settings, agent web, member password, portal tabs, platform overview, member publish)
  pass. Full suite: 2807 passed, 6 skipped, 0 failed
  (14 min 43 s, after the last code change).
- NOT done: live check (owner). Steps: (1) deploy this code to the Shared Platform
  (the portal page and the two routes are new; no schema change); (2) restart Agent Web
  on this PC; (3) Capabilities > Share Platform Library > "Open Marketplace": a new tab
  opens the portal already signed in, on Marketplace, the address bar without `#ticket`;
  (4) open a Library card: content (instructions or steps/parameters) beside the facts,
  "+ Add to this Agent" still there; (5) with the Personal Agent code removed from
  Settings the button opens the sign-in page and Agent Web says to save the code.
- Risks: a member who opens the portal from Agent Web in two browsers keeps only the
  newest one signed in through it (by design, bounded logins); tickets live in the
  portal process's memory, so a platform restart in the minute between click and
  redemption shows "not valid" (click again); the shared `renderMarkdown` used for chat
  answers still allows `mailto:` links (card content unwraps them).

## AEP skills and MCP for coding agents by default (2026-10-15, Claude Code)

Goal: owner requirements — Skills/Workflows made with Claude Code, Codex or Copilot must
work on AEP without a per-folder connect, and AEP's MCP and Knowledge must be usable from
them; plus live-test findings (catalog over the MCP output limit, check creating folders,
agent not asking). Design `docs/phases/EXTERNAL_AUTHORING.md` "Default user-level setup";
decision `docs/DECISIONS.md` 2026-10-15 "AEP skills and MCP servers in the coding agents'
user configuration by default"; row in `docs/TASKS.md`. Committed on main, not pushed
(87a098ab, 5a6e886a, 861ff17c, f1137dd8, b4fc2918 + the TASKS/HANDOFF commit).
- `host_runtime/agent_setup.py` + `aep-host assets --config host.json connect --for
  claude-code|codex|copilot|all --user [--status|--remove]`: skills `aep-workflow-creator`,
  `aep-skill-creator`, `aep-knowledge` and MCP servers `aep` (authoring stdio) and
  `aep-assistant` (`aep-host assistant-mcp`, `host_runtime/assistant_bridge.py`, forwards to
  the running Agent Web, reads `agent-web.json` + `assistant-mcp-token` per call) into
  `~/.claude/skills` + `~/.claude.json`; `~/.agents/skills` + `~/.codex/config.toml`
  (marked block); `~/.copilot/skills` + `~/.copilot/mcp-config.json`. AEP-marked entries
  only, backups `<file>.aep-backup-<time>`, versioned skills (`.aep-managed.json`).
- Installer/updater run it for detected agents unless `-NoAgentSkills`; uninstall `-Apply`
  removes it. Settings > Coding agents card (`/api/coding-agents`, install/remove).
- Agent Web serves authoring MCP at `/mcp/authoring`; the Copilot agent mode gets `aep` +
  `aep-assistant` and the skills (`.conversation-backends/.github/skills`, `--add-dir`).
  The text-only Claude Code/Codex/Copilot chat backends stay tool-less by design.
- Catalog compact (60 rich capabilities: 106,292 -> 11,809 chars; budget 15K) +
  `aep_capability`, `aep_workflow_format`, `aep_skill_format` (+ CLI). Checks have no side
  effects; folders made on submit/run/install. Creator skills ask first, typed params.
- Verified: ruff clean; mypy clean for these files; new/changed tests pass
  (`test_coding_agent_setup.py`, `test_coding_agents_web.py` incl. real browser,
  `test_external_authoring.py`, `test_conversation_backends.py`). Full suite: 2734 passed,
  6 skipped, 24 failed + 23 errors — control_plane/portal tests broken by another agent's
  uncommitted `src/control_plane` password-sign-in edits (they pass on committed HEAD) and
  pre-existing environment failures (numpy 2 vs matplotlib 3.7: weekly chart/report;
  coding doctor firewall check; same on 0354ab42). Smoke: `claude mcp list` in a temp home
  shows `aep` and `aep-assistant` Connected.
- NOT done: live check (owner). Not done by design, needs an owner decision: tool-using
  Claude Code/Codex agent modes inside Agent Web chat. Codex CLI is not installed here, so
  its file locations follow current docs and are unverified on a real Codex.
- Next for the owner: (1) `aep-host.exe assets --config host.json connect --for all --user`
  from the install folder (or Settings > Coding agents > Install; needs Agent Web restarted
  on this code); (2) restart Claude Code / VS Code; `claude mcp list` should show `aep` and
  `aep-assistant` Connected; (3) in any folder ask Claude Code "幫我做一個 AEP Workflow…"
  and expect clarifying questions first, then check/submit; (4) with Agent Web running ask
  "用 AEP 知識庫查 …" and expect cited page paths; (5) remove with `--remove` or the
  Settings button and confirm only AEP entries go.
- Risks: `~/.claude.json` is rewritten whole (formatting normalized, backup kept) while a
  Claude Code may be writing it; a person's own `aep`/`aep-assistant` entries are kept and
  then AEP's are missing (reported); Copilot also reads `~/.agents/skills`, so with Codex
  installed it may see the skills twice.

## Workflow run forms in the chat (2026-10-15, Claude Code)

Goal: owner finding — "我要執行rs-wmt-package-release" got prose in Agent Web (settings
and values asked in chat) and only "✅ Done" in Telegram. Now a person's run request is
the Workflow's generated form (Web, inline) or question flow (Telegram). Design
`docs/phases/CHAT_WORKFLOW_FORMS.md`; decision in `docs/DECISIONS.md` (2026-10-15 "A
person's "run X" in a chat is the Workflow's form"); row in `docs/TASKS.md`. Committed
on main, not pushed (85ef6f3c, 259e80ba, 0a2dabe7, b77d0fbb + this docs commit).
- Shared: `common/workflow_run_form.py` (intent, prefill, missing settings, offer);
  host tool `workflows__run_form` (`host_runtime/workflow_form_tool.py`, only when the
  request has a `session_id`); Gateway ends the turn on an offer; incomplete Skill
  Workflow tool calls and `authoring__run_workflow` (installed) become the offer.
- Web: route `workflow_form` before Skill rules/Knowledge; `/run <name>`;
  `ConversationMessage.workflow_form`; page `chatRunForm`/`drawChatRunForm`,
  `fillParameterValues`; `/api/workflows/run` takes `session_id` and records the run.
- Telegram: `_open_flow` (intent, model offer, `/run`), `telegram_flow.start(prefill=)`,
  `_no_answer_reply`, `_send_piece` (429/400 retry), `UNDELIVERED_REPLY`.
- Verified: ruff, mypy src clean; full suite 2746 passed, 6 skipped, 1 failed under load
  (`test_workflow_preview` capability timeout), rerun alone and passed. Headless check in
  `tests/test_chat_workflow_forms_web.py` (screenshot `.scratch/chat-forms-ui/`).
- NOT done: live check (owner). Restart Agent Web on this code; in a Gateway chat type
  "我要執行rs-wmt-package-release": expect the inline form (identity, chipset combo with
  Refresh list, versions, inbox picks/uploads, dryRun on, push off) or, if settings are
  missing, the notice with "Open rs-wmt-package-release settings". Try "run
  rs-wmt-package-release companyName=Foxconn" (prefilled). In Telegram (after the bot
  restarts with Agent Web) send "我要執行rs-wmt-package-release workflow": expect "same as
  last time?" or the first question; /cancel to stop. Do not press Run with push on.
- Risks: intent words are heuristics (a question with a run verb and a distinctive name
  but no question word opens the form; the person can just ignore it); two installed
  versions of one name are ambiguous and fall back to the model; the live Telegram
  silence cause is not confirmed (blank model text vs refused/rate-limited send), both
  are now covered.

## Capabilities redesign (2026-10-15, Claude Code)

Goal: owner's redesign of Agent Web "Capabilities" (Hermes skills page as reference):
Library as expandable cards with one-action "+ Add to this Agent"; drafts in the same
list as installed assets; Remove / Discard in the detail pane. Decision:
`docs/DECISIONS.md` (2026-10-15 "Switching off, removing and adding assets from Agent
Web Capabilities"); row in `docs/TASKS.md`. Committed on main, not pushed.
- Backend `host_runtime/asset_shelf.py`: switch off/on moves the manifest to/from the
  kind's `disabled/` folder (the place superseded Skills already go; live engine stops
  offering it); Remove moves it to `workspace/removed/<YYYY-MM-DD>/{skills,workflows}/`,
  appends `workspace/removed/removed.jsonl`, drops the `state.sqlite` inventory row;
  shipped manifests refused (`export-assets` writes them back) but may be switched off.
- "+ Add to this Agent" (`AgentWeb.add_to_agent`): portal `select` as the member, then
  `synchronize()`; reply carries `assets` + `sync.after`, the page redraws badge, left
  list (new item selected), counts and status. Assets-only: a new Workflow is offered
  live; Skills or platform-managed mode say "Restart Agent Web". "Remove selection" =
  `revoke` + sync. Errors (not configured, no login, not enrolled =
  `actor_not_admitted`, unreachable) explained, pointing to Settings > Shared platform.
- The enable/disable toggle the owner mentioned did not exist before; it was built here.
- Verified: ruff, mypy src clean; full suite 2713 passed, 6 skipped, 2 failed under
  load (script timeouts in `test_release_run`, `test_script_tools`), both passed alone.
  Headless check `.scratch/capabilities_ui.py` (sizes: chips/switch/buttons 44 px,
  dialog 500x214, no horizontal scroll at 390 px; screenshots `.scratch/capabilities-ui/`).
- NOT done: live check (owner). Restart Agent Web on this code, open Capabilities:
  drafts show first with Install; on the Library card of `company-agent/sync-test`
  (or another asset) press "+ Add to this Agent" and expect the badge to turn Installed
  and the Workflow to appear selected on the left without F5.
- Risks: removing a still-selected asset is reinstalled by the next sync (the reply says
  so); a removed Workflow's schedules and settings are kept and would fail until it is
  back; switched-on Skills need a restart.

## Owner and who can use a member-published asset (2026-10-15, Claude Code)

Goal: fix the live finding that `leo`'s two published assets were invisible to
`leo.chi`, with the owner's five decisions. Design and decisions:
`docs/phases/MEMBER_PUBLISH.md` "Owner and who can use it"; `docs/DECISIONS.md`
(2026-10-15 "Owner and who can use a member-published asset"); row in
`docs/TASKS.md`. Committed on main, not pushed.
- Submit keeps a declared team/organization owner when the submitter belongs to it;
  the publisher's `visibility` (request field, Agent Web select, CLI `--visibility`)
  replaces the manifest's. `AssetSubmission` records owner and visibility.
- `NameAccess` record per name (visibility override + extra members/groups) in the
  additive `name_access` table; `entitled(..., access)` via `entitled_in` everywhere
  (portal catalog, select, replace, Bridge catalog, extension catalog, ownership
  visibility). Portal routes `assets/access` (`scope` mine/all) and
  `assets/access/update` (owner, owning-team member or administrator; else
  `not_name_owner`). Portal "My published assets" / "All published assets" with a
  "Who can use it" editor.
- Portal fixes: `leo.chi` placeholder and in-page name check; `reason`/`message` on
  refused names; session renewed from the stored login and retried once.
- `aep-host assets publish --file <manifest.json>`; sample
  `deploy/samples/sync-test.workflow.json` (not installed anywhere).
- Verified: ruff, mypy src clean; full suite 2702 passed, 6 skipped, 4 failed under load (three browser tests lost their DevTools socket, incl. the new portal browser test; one checkpoint-store 'unavailable'), all four rerun alone and passed.
- NOT done: deploy and live test on 172.25.228.141 (owner). Steps: redeploy the
  platform bundle; as `leo` open the portal, "My published assets", "Who can use it"
  on each of the two assets, choose "Everyone in the organization" (or add member
  `leo.chi`), Save; as `leo.chi` load add-ons for the Bridge and select them; in
  Agent Web press Synchronize selected. For a fresh test publish:
  `aep-host assets publish --config <host.json> --kind workflow --file
  deploy\samples\sync-test.workflow.json --visibility organization`, approve as
  `leo-review`, then select and sync as `leo.chi`.
- Risks: narrowing access does not withdraw existing selections (documented);
  the two existing assets stay owned by `user leo` (transfer to team `engineering`
  via `assets/transfer` if wanted); a Bridge whose member lacks a group sees a
  team-owned `team` asset only if the access record names them.

## Bridge self-enrollment on the Shared Platform (2026-10-15, Claude Code)

Goal: the install half of the Shared Platform (platform to PC). Design
`docs/phases/BRIDGE_ENROLLMENT.md` (approved with option (a)), decision in
`docs/DECISIONS.md` (2026-10-15 "Bridge self-enrollment and assets-only sync"), row in
`docs/TASKS.md`. Committed on main, not pushed.
- Platform: member portal `bridges/enroll` (member session; registers/reuses the
  company workstation, binds the member as device_admin, 90-day token shown once,
  re-enroll rotates), `admin/bridges/list|disable` and a "Bridges" portal panel.
  Portal reads `#bridge=<id>` from "Open Marketplace".
- Agent Web: Settings > "Shared platform" card (Member Portal URL feeding both
  `publishing` and `platform`, Bridge API URL, Personal Agent code moved from
  Capabilities, "Enroll this PC"). Token saved as `AEP_SHARED_PLATFORM_TOKEN` (user
  environment + process), host.json backed up as
  `host.json.bak-<stamp>-before-shared-platform`, client swapped without restart.
- Assets-only sync when `workspace\grants.json` exists: files installed, bundle kept in
  `platform-selections.json` (display only), `authorization.json` never written.
- Verified: ruff, mypy src clean; full suite 2679 passed, 6 skipped, 1 failed
  (`http://` in placeholders; fixed and rerun green, see TASKS).
- NOT done: live test on 172.25.228.141 (owner's main session deploys). Steps: redeploy
  the platform; in Agent Web Settings set Member Portal `http://127.0.0.1:28776` and
  Bridge API `http://127.0.0.1:28775` (SSH tunnel), paste a fresh Personal Agent code if
  needed, press Enroll this PC; Library should list the two assets published on
  2026-10-15; select them in the portal; press Synchronize selected.
- Risks: the PC's host.json `device.registered_by` must equal the portal account
  (else `device_owner_mismatch`, shown by name). A synced Skill/Workflow whose name is
  already installed locally at another version lands as a second file; a newly
  installed Workflow may need an Agent Web restart to be offered (unchanged behaviour).

## Workflow forms v2 and the one-run release (2026-10-15, Claude Code)

Goal (owner decisions A, B, C): authors only declare parameters; AEP draws Web and
Telegram forms. Design `docs/phases/WORKFLOW_FORMS_V2.md`, decision in
`docs/DECISIONS.md` (2026-10-15 "Workflow forms v2"), rows in `docs/TASKS.md`.
All committed on main, not pushed (9d4f9f61 .. 456c0ef6).
- Built: `allow_other` pick-or-type, `fn:` lists on Web, Telegram multi-select toggles,
  `fn:folder_files`, real uploads (`workspace\workflow-uploads`, engine confinement),
  identity presets (`workspace\identity-presets.json`), creator format/Skill, and
  `engineering/rs-wmt-package-release@1.0.0` (prepare -> commit -> push, dry run on, push
  off; preview alias 13 removed; `schema.py` deleted).
- Verified: ruff, mypy src; full suite 2660 passed, 6 skipped, 1 failed (export snapshot
  list), fixed and that file rerun green. Headless Web check `.scratch/forms_v2_ui.py`
  (combo box, fn: list, folder picks, upload, "Use last values"; sizes measured).
  Telegram checked only against the fake Bot API, not the live bot.
- Live: settings for `engineering/rs-wmt-package-release` copied from prepare (backup
  `workflow-settings.json.bak-20261015-before-rs-wmt-package-release`; `remote_release`
  still OFF). Draft wf-20261014-181908-f31f09 submitted. Agent Web restarted on 456c0ef6.
  The earlier three step drafts (prepare, commit) are still drafts; push 1.0.0 is
  installed.
- Owner next: Capabilities -> 我的草稿 -> Install rs-wmt-package-release (and prepare /
  commit if the step Workflows are wanted); create
  `Documents\git_repository\.aep-isolated-release-root` (content
  `AEP_ISOLATED_RELEASE_ROOT_V1` + newline) and the inbox `_release_inputs`; turn
  `remote_release` on in that Workflow's settings only when ready for GitLab; first run
  with dry run on.
- Known: a release Workflow run fails with `workflow_input_missing` if
  `artifactory_base_url` or `readiness_base_url` is unset (steps map every setting); the
  live install has both. Commit 04995b03 alone does not import (host.py names RELEASE,
  added in 456c0ef6).

## Latest (2026-10-13)

All of the following is committed on main (not pushed); rows are in `docs/TASKS.md`,
decisions in `docs/DECISIONS.md`.

- Knowledge tab: one folder per sandbox (Scope and rules); progress bars for create and
  pull; Convert/Preview run in the background with picture progress and Stop (a convert
  in one request outlived the 600 s step limit); every step shows its running time;
  Ingest shows the clicked Raw beside a keyboard-tickable list; new Raw is ticked green.
- Tasks tab: Workflows (telemetry) and background jobs (`workspace/tasks.json`), newest 50.
- Reviews tab (experience review E3/E5): proposals are accepted, rejected with a reason,
  snoozed, done or reopened; accept opens a review sandbox (rule edit, draft question),
  adds a gap or tracks an issue. Push now merges `checks/`. 16 proposals are waiting for
  the owner (mostly Workflow issues). Next: E4 (platform Skill and Workflow routes).
- Releases: `scripts
elease.cmd` (verify, build from `git archive HEAD`, bundle, release
  folder, tag `release-<id>`); colleague manual `deploy/windows-preview/INSTALL.zh-TW.md`,
  publisher guide `docs/RELEASING.zh-TW.md`. Last release `20261013-1349-fd87def6` predates
  the icon, Tasks, Reviews and Ingest changes: make a new one before delivering.
- Laya: Settings card (`laya` in host.json, optional Agent Web SSH tunnel). The SSH key for
  openlab@172.25.228.141 is rejected; the scratch loopback relay ran only in that session.
  `docs/phases/LAYA_ACCELERATION.md` is ON HOLD for a week of shadow data and owner review.
- Load-sensitive tests seen under full load (pass alone): two browser tests,
  `test_application_catalog` endpoint test, `test_telegram_ingress` back-off test.
- Verified last: ruff, mypy src, full suite 2578 passed / 1 load-sensitive failure /
  6 skipped; headless checks of each new page. Agent Web restarted on 25adad87.
- Owner to decide: Pull "convert again" option (not built); very large Raw (split or
  skip); SSH key on 141 versus the relay.

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

Knowledge pipeline and collaboration (2026-10-12, latest). Read
`docs/phases/KNOWLEDGE_COLLAB.md` (owner design: Pull -> Rules -> Convert -> Ingest ->
Lint -> Benchmark -> Push) and the K1-K3 specs; progress rows are in `docs/TASKS.md`.
- Built and committed: K1-K3 (sandboxes, vault rules layered general to specific,
  section edits with a sourced-line guard, three-way merge) and C1-C5 (pull, rule
  editor and previews, question-set benchmark, push behind a benchmark gate with
  first-push-wins compare-and-write, backups and push records, workflow-ordered
  Knowledge tab). Last full run: 2513 passed, 6 skipped; ruff and mypy src clean.
- Live config: host.json `knowledge_pipeline` has `k-test`, `rs-k` and `rs-project`
  (the local RS_Knowledge copy `%LOCALAPPDATA%\AEP\projects\rsk-copy`, `knowledge_asset: rs-knowledge`). The Agent
  still answers from rs-knowledge 1.0.2 (`AEP\rs-k`); nothing was refreshed.
  The real OneDrive RS_Knowledge was only read (copied), never written.
- C6 trial results are in TASKS. Test sandboxes `sb-c6-*` and `sb-probe-*` are in
  `AEP\sb`; the copy holds four test pushes (`pushes/`, `log.md`, `.ingest-backup/`).
- Open: the owner validates in Agent Web (Knowledge tab, project `rs-project`);
  domain experts add question sets under `checks/questions/<folder>/`; the free-form
  ZNAEXT question needs must-mention terms; before the real RS_Knowledge goes live it
  needs one adopt pass and a host.json switch; an intermittent single test failure
  (passes on rerun) is unidentified (see TASKS); the OCNG image failure is fixed
  (b293aeb). Next stage after validation: K4 (Excel, HTML, .ppt, images).

Copilot integration (2026-10-12, latest): design `docs/phases/COPILOT_INTEGRATION.md`.
CP1 (assistant tools at `/mcp`) and CP2 (Copilot agent conversation mode) are committed.
CP3 waits for the owner's company Copilot seat: dragon0816 has no organization. The
Copilot CLI is installed. Experience review E1-E2 is live (Knowledge tab, nightly).
claude-mem 13.35.0 was installed for Claude Code at the owner's request (worker on
port 37777, local only).

Knowledge answer rules (2026-10-12): vault skills with `mode: answer` now shape
answers; the rewritten ask-knowledge measured better in core-015 (coverage 0.503,
invented 31 vs 67) and is LIVE as rs-knowledge 1.0.3 (`AEP\rs-k-v1.0.3`, published
2026-10-12; host.json backup `host.json.bak-20261012-143652-before-rs-knowledge-1.0.3`,
1.0.2 kept). It is also in the project vault copy. The Skill assistant is on
the Knowledge page (Rules card).

Knowledge answer quality update (2026-10-12): owner proposal 1 was tried at
677e18a and ROLLED BACK (2df2faf1) after core-014; live is the core-012 setup.
Earlier note: proposal 1 was live at
677e18a (the last search plan's queries run, pages added beyond the budget).
core-013: answerable coverage 0.508 (target 0.50), median 83 s, p90 144 s. To roll it
back, revert 677e18a and restart Agent Web. Proposals 2-4 below are not implemented.

Knowledge state (2026-10-12): answer quality was tuned against a fresh baseline
(see DECISIONS 2026-10-12 and `runs/core-009` … `core-012` reviews). Live now, commit
425c5f6: Knowledge Skill `company-agent/knowledge-query@1.12.0` (1.10.0 in `disabled/`),
`engineering/knowledge-query@1.0.1` (1.0.0 in `disabled/`), Agent Web restarted on 425c5f6.
Baseline core-009 -> core-012: answerable coverage 0.372 -> 0.477 (target 0.50), 36-question
PASS/INSUFFICIENT/FAIL 21/6/8 -> 28/2/6, contradicted 27 -> 15, invented 47 -> 67, median
185 -> 74 s, p90 329 -> 115 s. Verification on 425c5f6: ruff and mypy clean; full pytest
2519 passed, 6 skipped. Rollback per change: C3 revert 425c5f6; C2 revert 43dcd76 and move
1.10.0 back for 1.12.0; C1 revert 9d0d74c and move engineering 1.0.0 back (204dcfa is a pure
speed-up with identical retrieval output); restart Agent Web after each.

Open for the owner (structural, not implemented):
1. Retrieval recall is the remaining gap (75% of missed answerable key points sit on pages
   never offered; all reference sources exist). Options: run the last planner round's
   queries (today they are discarded), or a fourth round (`retrieval_rounds` 3, about +8 s);
   a per-question "page title + summary" recall pass using the K2 bilingual index lines.
2. The citation preflight still fails first drafts on a sentence split at "vs." and on
   labeled inferences; deciding whether a bold label line is formatting changes the rule.
3. run.py's reviewer sees only the first 16 cited passages (1,500 chars each); answers now
   cite more, which turns supported answers into FAIL (core-012: 28 PASS with 16, 33 with 48).
   Widening it changes the grader, so earlier runs would need regrading for comparison.
4. Invented claims rose with fuller answers (47 -> 67); a claim-level check against the
   cited passage would add one model call per answer.

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
