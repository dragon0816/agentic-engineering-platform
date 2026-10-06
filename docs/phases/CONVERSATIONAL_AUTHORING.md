# Conversational authoring and candidates

Owner direction 2026-10-06: develop Workflows and Skills in any conversation
(Agent Web or Telegram), with files attached to the conversation, instead of
dedicated pages; run a temporary custom task the same way; tag Skills and
Workflows for the Marketplace; manage everything not yet published in one
Candidates area, where a candidate can be reopened in a conversation and
changed. Supersedes the W7 page panel of `docs/phases/SOP_TO_WORKFLOW.md`;
W1-W6 (building blocks, fixed inputs, preview runs, authoring sessions, the
drafter) are reused unchanged.

## Owner decisions (2026-10-06)

1. Approval is a button in the conversation: a message button in Agent Web,
   an inline button in Telegram. Only the owner can press it; the model has
   no tool that approves, installs or runs a change.
2. A temporary task that only reads runs directly. A task with any write or
   external step shows a preview first and runs only after the owner
   presses approve.
3. Tags: one category from a fixed list, plus free tags.
4. The "Create a Workflow from an SOP" and "Create a Skill or Workflow draft"
   panels are removed. Existing contribution drafts move to Candidates.

## Harness changes

| # | Change | Where |
|---|---|---|
| H1 | Conversation attachments: a file added in Agent Web chat or sent to the Telegram bot by an allowed sender is stored under `<workspace>/attachments/<session>/`. The model sees name, type, size and extracted text (PDF, text); never raw bytes | conversation contracts, Agent Web, Telegram ingress |
| H2 | Authoring tools in conversations: draft or revise a Workflow or Skill from the conversation and its attachments, and preview it. A preview's results go back to the model so it can fix the draft; web content stays data, never instructions | Gateway tool list, `host_runtime/authoring.py` |
| H3 | Approval buttons: a conversation reply can carry an approval request (install a candidate, or run a temporary task once). Pressing it is an owner action handled by the host, never a model tool call | conversation reply contract, Agent Web page, Telegram callbacks |
| H4 | Temporary tasks: a drafted Workflow run once with the grants it needs, not installed. Read-only runs directly; otherwise preview, then approve | `host_runtime/authoring.py`, engine `execute` on an uninstalled manifest |
| H5 | Candidates: one store for drafts in development, previewed drafts, installed-but-unpublished Workflows and Skills, and contribution proposals; list, view, delete, reopen in a conversation, approve and install | `host_runtime/authoring.py`, Capabilities page |
| H6 | Skills are authored as well as Workflows (alias, instructions, commands, selector hint, category, tags) | drafter |

Tags use the existing `AssetMetadata.categories`: the first entry is the
category from the fixed list, the rest are free tags. No manifest format
change.

## Slices

| Id | Slice |
|---|---|
| A1 | Category list and tags: validation, drafter suggestions, Capabilities and Marketplace filter |
| A2 | Candidates store and Capabilities "Candidates" area (list, view, delete); remove both panels; migrate contribution drafts |
| A3 | Conversation attachments (H1), Agent Web then Telegram |
| A4 | Authoring tools in conversations (H2), Workflows first, then Skills (H6) |
| A5 | Approval buttons (H3) for install, in Agent Web and Telegram |
| A6 | Temporary tasks (H4) |
| A7 | Reopen a candidate in a conversation and revise it |
| A8 | Live: the practice SOP end to end from a Telegram conversation with the PDF attached |
