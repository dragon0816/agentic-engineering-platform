# Suggested Skills from experience (planned)

Owner request: 2026-10-16. Status: **backlog — planned, not started.** A design for owner
review comes first, after the Hermes skill pack release.

## Why

Hermes nudges the agent to save a skill after repeated work (`creation_nudge_interval`)
and writes it itself. AEP deliberately never lets the Agent add or change a Skill on its
own: a model may not install or approve what changes behaviour. The owner still wants
AEP to notice reusable work and offer it as a Skill.

## Intended shape (to be designed)

- **Detect.** In the nightly Experience review, or at the end of a conversation, look
  for:
  - the same kind of request repeated across conversations;
  - a long multi-step success that is likely to recur;
  - a person correcting the Agent the same way again.
- **Propose.** The Agent drafts a **Skill draft** (or a Workflow draft when the steps are
  fixed). It is shown as a card in Reviews or in the conversation, with:
  - why it is suggested, with links to the evidence conversations;
  - the draft content;
  - the run parameters, so the form it would produce is visible;
  - any existing Skill it overlaps with.
- **The person decides.** Create draft / Ignore / Update the existing Skill instead.
  - A created draft is installed only by the Capabilities **Install** press, as today.
  - The person can refine the draft with Claude Code first (the creator skills and the
    authoring MCP are installed by default).
- **No duplicates.** A similar installed or pending Skill turns the suggestion into an
  update proposal instead of a new Skill.
- **Reuse:**
  - the action card (`common/action_cards.py`);
  - the Experience review store (`host_runtime/experience_proposals.py`);
  - the authoring check (`check-skill` / `check-workflow`).
