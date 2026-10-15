# AI proposes, the person applies

Owner request: 2026-10-15. Status: **approved 2026-10-15; implementation starts after `CHAT_WORKFLOW_FORMS.md` lands.**

## Goal

Lower the learning cost: a person says in Agent Web chat (or Telegram) what they want
changed, such as "turn Laya to shadow at 0.9", "enroll this PC on the shared platform",
"install the sync-test Workflow" or "switch off the old coding Skill". The Agent
answers with a **change proposal card**, and nothing changes until the person presses
**Apply**.

This keeps the rule that a model never approves, installs or runs changes itself
(owner mode: model-chosen side effects wait for a person). It removes the need to know
which Settings card or Capabilities button does what.

## What exists

- **Settings cards** with validated writers and a host.json backup:
  - Laya: `update_laya`;
  - Shared platform: `update_shared_platform` (+ enroll);
  - natural-language model;
  - Telegram;
  - per-Workflow settings (`WorkflowSettingsStore`).
- **Capabilities actions:**
  - install a draft (owner approval);
  - switch on/off, remove (recoverable);
  - `+ Add to this Agent` (select + sync);
  - publish to the shared platform.
- **Chat:**
  - the Agent's tool schema (`agent/gateway.py`);
  - Workflow forms rendered inline in chat (`docs/phases/CHAT_WORKFLOW_FORMS.md`, in
    progress);
  - the Knowledge AI session's "proposal goes to Current file; press Save" pattern.

## Design

### 1. One tool for the model: `propose_change`

The model may call `propose_change(kind, values, reason)`. It cannot call any writer
directly. Kinds in version 1:

| Kind | Values the model may propose | Applies through |
|---|---|---|
| `laya` | host, ports, user, mode (off/shadow/active), threshold, timeout, auto tunnel | `update_laya` |
| `shared_platform` | Member Portal URL, Bridge API URL, enroll this PC (yes/no) | `update_shared_platform` |
| `model` | provider, alias, gateway URL, model name, secret *name* and variable *name* | the model settings writer |
| `telegram` | enable / disable, allowed chat names | the Telegram settings writer |
| `workflow_settings` | static settings of one installed Workflow | `WorkflowSettingsStore` |
| `capability` | install a draft, switch on/off, remove (recoverable) one Skill/Workflow | the Capabilities actions |
| `platform_add` | add one shared Skill/Workflow version to this PC | `+ Add to this Agent` |
| `publish` | submit one installed Skill/Workflow (change level, who can use it, note) | the publish card |

### 2. The proposal record

The server validates the values with the same contract the Settings card uses, and
stores a proposal with:

- its id, kind and the values;
- a **before → after diff of only the fields that change**;
- the reason in the model's words;
- the conversation it came from;
- a "current" fingerprint of the settings it was based on;
- a status (pending / applied / cancelled / expired / stale).

A proposal expires after 30 minutes. If the setting changed in the meantime, Apply
refuses with `stale` and the Agent can propose again.

### 3. The card

- **Agent Web chat.** A card titled with the change, for example "Change Laya
  decision acceleration". It shows the diff table, the reason, any effect to know (for
  example "this enrolls this PC; a Bridge token is saved for your Windows user"), and
  two buttons: **Apply** and **Cancel**. After Apply, the card shows the result in place
  (the same message the Settings card would show) and links to the Settings card.
- **Telegram.** The same text with Apply / Cancel buttons for the low-risk kinds:
  `laya`, `workflow_settings` and capability switch on/off. The higher-risk kinds
  (`shared_platform` enroll, `capability` remove, `platform_add`, `publish`, `model`,
  `telegram`) show the card with "Open in Agent Web to apply" (see the open question).

### 4. What is never proposed or applied from chat

- **Secret values:** tokens, passwords, Personal Agent codes, API keys. The model may
  name a secret or a variable, never its value. If one is needed, the card says
  "paste it in Settings → …" with a link. A value that looks like a credential in the
  proposed values is refused.
- **Permissions:** `grants.json` and capability grants, i.e. what this PC may run.
- **The platform:** approving or rejecting submissions on the shared platform,
  inviting members, changing another person's access.
- **Running a Workflow** that changes something: that keeps its own confirmation and
  form.
- **Restarting Agent Web** or changing the install itself.

### 5. Audit

- Every proposal and its outcome is a Task (kind `proposal`) with the diff summary.
  Secret names may appear in it; values never do.
- The DECISIONS-style history is the Tasks list plus the host.json backups the writers
  already make.

## Tests

- The model cannot reach a writer except through `propose_change`.
- Validation errors come back as a refusal message, not a card.
- Apply equals the Settings card's effect, including the backup.
- Stale, expired and double Apply are refused.
- Secret-looking values are refused.
- Telegram low-risk Apply works; the high-risk kinds only link to Agent Web.
- Headless render of the card.
- End to end: "turn Laya to shadow" → card → Apply → host.json changed → the Laya card
  shows it.

## Owner decisions (2026-10-15)

1. Telegram applies only the low-risk kinds (`laya`, `workflow_settings`, capability
   switch on/off); every other kind links to Agent Web.
2. Version 1 covers every kind in the table above.
