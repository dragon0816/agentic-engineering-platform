# Agent mode for Claude Code / Codex / Copilot in Agent Web

Owner request: 2026-10-15. Status: **approved (option A, rules revised 2026-10-15 below); implementation after the push.**

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
