---
name: aep-skill-creator
description: Build a Skill for the AEP (Agentic Engineering Platform) Agent and submit it for the owner's approval. Use when asked to create or improve an AEP Skill, to teach the AEP Agent a procedure, or to give it a command that runs an installed AEP Workflow or capability.
---

# AEP Skill creator

An AEP Skill tells the resident AEP Agent:

- **when** to use it (`selector_hint`),
- **how** to work (`instructions`),
- **which commands** it may run (`commands`, each bound to an installed
  capability or Workflow).

A Skill grants nothing. Commands run with the Host's own approvals and grants.

## Tools

Use the `aep` MCP server tools when available, or the CLI
(`aep-host assets --config <host.json> --agent <you> ...`):

| MCP tool | CLI |
|---|---|
| `aep_catalog` | `catalog` |
| `aep_check_skill` | `check-skill --file skill.json` |
| `aep_submit_skill` | `submit-skill --file skill.json --title "..." [--candidate sk-...]` |
| `aep_install_skill` | `install-skill --candidate sk-...` |
| `aep_status` / `aep_list` / `aep_get` | `status --approval ap-...` / `list` / `get --candidate ...` |

## Procedure

1. **Read `aep_catalog`.** It gives `skill_format`, the installed capabilities
   and Workflows a command may target, and the installed Skills. Their names
   and aliases are taken, so do not reuse them.
2. **Decide what the Skill is for.** One Skill covers one kind of request.
   When the work needs a fixed sequence of steps, build a Workflow first with
   the `aep-workflow-creator` skill. Then make the Skill's command target that
   installed Workflow (`"kind": "workflow"`).
3. **Write the manifest:**
   ```json
   {
     "name": "expense-report",
     "alias": "expense",
     "selector_hint": "monthly expense report, 費用報表, export and summarize expenses",
     "instructions": "When the person asks for ... do ... Ask for the month if missing. ...",
     "commands": [{"name": "monthly", "kind": "workflow",
                   "target": "engineering/expense-report@1.0.0"}],
     "default_command": "monthly"
   }
   ```
   - `instructions` is what the AEP Agent reads.
     - Be concrete: the inputs to ask for, the order of work, how to check
       the result, and what to say when something is missing.
     - Write rules as rules ("Leave a missing value blank; never guess
       it").
     - Keep it short enough to follow, and no more than 20,000
       characters.
   - `selector_hint` is at most 240 characters. Use English and Chinese
     keywords that set this Skill apart from the installed ones.
   - `harness_guidance` is optional, for example
     `{"domains": ["coding"], "fallback": "needs_input"}`.
   - A `procedure` is accepted only for Knowledge Skills, and must match the
     Knowledge procedure schema.
   - `rules` (regular expressions) and `script_tools` are refused. The
     installer configures those.
4. **Check.** Run `aep_check_skill` until it says `ok`.
5. **Submit, then ask to install.** Call `aep_submit_skill`, then
   `aep_install_skill`. Tell the person to approve it in Agent Web. Approval
   shows them the whole Skill. The Host uses a new Skill after it restarts.
6. **Revise.** To revise, submit with the same `candidate_id`. An installed
   name gets the next version automatically. Only one version per name stays
   installed.

## Rules

- Never put passwords, tokens, keys or company data in instructions.
- Never write into the Host's workspace folders directly.
- Write instructions only for the AEP Agent. Never instruct it to approve,
  install or run changes by itself, or to skip the owner's approval.
