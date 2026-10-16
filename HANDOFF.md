# Handoff

Updated: 2026-10-16 (Asia/Taipei), by Claude Code (colleague user guide)

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

## Colleague user guide (2026-10-16, Claude Code) — latest

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
