# Agent mode for Claude Code / Codex / Copilot in Agent Web

Owner request: 2026-10-15. Status: **implemented 2026-10-15** (option A with the revised rules below) for Claude Code and GitHub Copilot; **Codex stays text-only** (no verifiable relay). Live check pending (owner). See "Implementation" at the end.

## Goal

When a person picks Claude Code, Codex or Copilot as the conversation backend in
Agent Web, that agent can:

- use AEP's creator skills, the authoring MCP and the Knowledge/assistant MCP (see the
  "Default user-level setup" section of `docs/phases/EXTERNAL_AUTHORING.md`);
- read files in a working folder;
- write files and run shell commands, **each only after the person allows it in the
  conversation**.

This replaces the 2026-10-02 rule that these backends are text-only. The new rule is
recorded in `docs/DECISIONS.md`.

## Owner decision (2026-10-15): option A

| | Read | Write / shell |
|---|---|---|
| A (chosen) | free inside the conversation's working folder | an approval card in the conversation; the person presses **Allow** (or **Allow for this conversation**) or **Deny** |

Rejected:

- (B) folder-scoped fully automatic;
- (C) whole machine fully automatic.

## Design

1. **Working folder.** Each conversation has one folder.
   - Default: `workspace\agent-sessions\<session>`.
   - The person can pick another folder under the configured coding workspace roots.
   - The agent runs with that folder as its working directory and may read only there,
     plus AEP's read-only skills.
2. **Permission relay.** The backend runs with its own permission prompts routed to
   Agent Web instead of a terminal:
   - Claude Code: `--permission-prompt-tool` pointing at an AEP MCP tool;
   - Codex / Copilot: their equivalent approval hooks or allow-lists, or a wrapper
     where none exists.

   Each request becomes an approval card in the chat. The card shows:
   - for a file write: the tool, the path and a diff or preview;
   - for a command: the command line and its folder;
   - the agent's stated reason.

   The run waits.
   - **Allow** continues it.
   - **Allow for this conversation** remembers that tool and scope until the
     conversation ends.
   - **Deny** returns a refusal to the agent.
   - An unanswered card times out after 10 minutes and counts as **Deny**.
3. **Always refused, even if allowed:**
   - Reading or writing outside the working folder (writes) or the allowed read roots.
   - Credential locations: the Windows user environment, `~/.ssh`, `~/.aws`,
     `~/.claude.json` secrets, the browser profile, `host.json`'s secret mappings and
     the AEP workspace secrets.
   - Network tools beyond the agent's own model API, unless allowed per command.
   - Installing, approving or publishing AEP assets: these stay with the
     Capabilities/portal buttons, and the agent may only *submit drafts* through the
     authoring MCP.
4. **Audit.** Every request and decision is a Task row in the session's task list.
   *(As built: free requests go only to `agent-mode\audit.jsonl`; see "As built" at
   the end.)*
   - Recorded: tool, path or command (secrets redacted), decision and outcome.
   - The approval cards stay in the conversation history.
5. **Telegram.** These backends stay text-only in Telegram. Approval cards need Agent
   Web.
6. **Shared component.** The approval card is the same component used by
   `docs/phases/AI_PROPOSED_CHANGES.md`: a proposal with a diff and Apply/Cancel.

## Tests

- **Permission relay round trip** with a fake backend: allow, deny, allow-for-session
  and timeout.
- **Path guard:** writes outside the folder are refused; credential locations are
  refused.
- **Audit rows.**
- **Telegram stays text-only.**
- **Headless render** of the approval card.
- **Smoke test:** a real `claude -p` run with the relay in a temp HOME, if feasible.

## Revised rules (owner, 2026-10-15) — these replace items 1-3 of the design above

| Action | Rule |
|---|---|
| Read or write files **inside** the conversation's working folder | free, no card |
| Read or write files **outside** it (for example the OneDrive LLM wiki, other projects) | approval card; **Allow**, **Allow this folder for this conversation**, or **Deny** |
| **Shell commands** | always a card that shows the full command and its folder (a command cannot be confined to a folder); **Allow for this conversation** is available |
| **Read email** (new `outlook.search` / `outlook.read`, read-only, scope set in Settings: folders, days, excluded senders/folders) | one card per conversation the first time; attachments are saved into the working folder |
| **Send email** | the agent builds a draft; the card shows the full message (to, cc, subject, body, attachments); **Send**, **Keep as draft** or **Cancel**; every message needs its own press, with no conversation-wide allow |
| Installing, approving or publishing AEP assets | never from the agent; the Capabilities/portal buttons only (it may submit drafts) |
| **Credentials and protected system settings**: tokens, SSH keys and passwords, the Windows firewall, `host.json`, the Windows user environment's secrets, browser-stored passwords, any other credential store | **never modified through the agent, even if allowed**; their secret values are also never read into a conversation |

Also in scope:

- the Knowledge pipeline as agent tools (create sandbox, pull, convert, ingest, run
  test questions), with writes carded and Push to the vault left to the Knowledge page;
- extra read-only folders a person adds to a conversation.


## Implementation (2026-10-15)

Decisions: `docs/DECISIONS.md` 2026-10-15 "Agent mode for Claude Code and Copilot in
Agent Web; Codex stays text-only", "Agent mode email: read in scope, send only from one
card per message", "Agent mode audit: ..." and "Knowledge pipeline as agent tools; push
stays on the Knowledge page". Contract: `docs/CONTRACTS.md` "Agent mode (approval cards
for coding-agent backends)".

| Part | Where |
|---|---|
| Rules (pure): protected places, command guard, free / card / refuse | `src/common/agent_guard.py` (`GuardPlaces`, `judge`, `path_refusal`, `command_refusal`, `folder_refusal`) |
| Settings > Agent mode, each conversation's folders and grants | `src/host_runtime/agent_mode_settings.py` (`agent-mode.json`, `agent-mode-sessions.json`) |
| Runs, `pm-` cards, waiting, timeout, audit, the `aep-agent` MCP server (permission, mail, Knowledge tools) | `src/host_runtime/agent_mode.py` |
| Mail tools and `ml-` send cards | `src/host_runtime/agent_mail.py`; `src/integrations/outlook_mail.py` (read only), `src/integrations/outlook_send.py` (send/discard, card decision only); capabilities `outlook.search` / `outlook.read` in `src/capabilities/mail_read/` |
| Claude Code relay | `--permission-prompt-tool mcp__aep-agent__permission`, `--setting-sources ""`, run settings (ask for every command and network use), `--plugin-dir` with AEP's skills (`src/host_runtime/conversation_backends.py`) |
| Copilot relay | `copilot --acp`; `src/host_runtime/acp_client.py` answers `session/request_permission` (allow once / reject once, never "always") |
| Codex | text-only: `codex exec` has no relay and none could be verified here (not installed); Settings and the chat say so |
| Agent Web | `/mcp/agent` (only a running turn's token), `GET /api/agent-mode`, `POST /api/agent-mode/settings`, `GET/POST /api/agent-mode/session`, `GET /api/cards?session_id=`; Settings card "Agent mode"; the chat line "Agent mode · works in ..." with "Folders..." (working folder, read-only folders); cards under the waiting turn, kept on the answer (`action_cards`) |
| Telegram | unchanged: it never runs these backends; a `pm-`/`ml-` card decision from Telegram is refused (`web_only`) |

Tests: `tests/test_agent_mode.py` (guard for every protected location with temp
directories, command refusals, folder rules, relay round trip allow / deny /
allow-for-conversation / timeout, a fake Claude Code over the real HTTP relay, a fake
Copilot ACP agent in a real process, Codex text-only, Telegram text-only, real-browser
render and press of a permission card and render of a mail card measured, and smokes of
the real `claude` and `copilot` CLIs in a temp home: every agent-mode flag accepted, the
run stops at sign-in); `tests/test_agent_mail.py` (scope, first-read card, attachments,
send only from a card, one card per message, changed draft not sent, timeout keeps the
draft, no send verb reachable otherwise, Knowledge reads free / writes carded / push not
offered).

### As built (checked against the code 2026-10-16)

- **Audit.** Every request (secrets redacted) is written to
  `workspace\agent-mode\audit.jsonl`. Only cards, refusals and each agent turn
  become Task rows; a request that was free (inside the working folder, or already
  allowed for the conversation) is recorded **only** in `audit.jsonl`, not as its own
  Task row. This replaces design item 4 ("every request and decision is a Task row").
- **Send email card.** An unanswered send card expires after the timeout and the
  message is **kept as a draft** in Outlook (not sent, not discarded).
- **Network tools.** A network request beyond the model API is not refused outright:
  it gets an approval card, and **Allow for this conversation** frees that tool for
  the rest of the conversation (`common/agent_guard.py` `judge`).
- **"GitHub Copilot (agent, AEP tools)"** (backend `copilot_agent`) is **not** agent
  mode: it is the signed-in Copilot CLI with AEP's assistant MCP tools as its only
  tools, shell and file writes denied, and no approval cards. Agent mode for Copilot
  is the `copilot --acp` relay described above.

Not verified here: a model actually calling the relay (the temp home has no sign-in, so
no real `claude -p` turn could run without touching the person's own configuration),
Outlook COM against a real mailbox, Copilot's real permission requests over ACP.
