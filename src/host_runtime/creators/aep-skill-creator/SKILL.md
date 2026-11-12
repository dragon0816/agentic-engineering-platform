---
name: aep-skill-creator
description: Build a Skill for the AEP (Agentic Engineering Platform) Agent and install it locally with actual validation evidence. Use when asked to create or improve an AEP Skill, to teach the AEP Agent a procedure, or to give it a command that runs an installed AEP Workflow or capability.
---

# AEP Skill creator

An AEP Skill tells the resident AEP Agent:

- **when** to use it (`selector_hint`),
- **how** to work (`instructions`),
- **which commands** it may run (`commands`, each bound to an installed
  capability or Workflow).

A Skill is procedure guidance. Tools run under IT/OS/service permissions; AEP does
not require tool grants or local installation/execution approval.

## Tools

Use the `aep` MCP server tools when available, or the CLI
(`aep-host assets --config <host.json> --agent <you> ...`):

| MCP tool | CLI |
|---|---|
| `aep_catalog` | `catalog` |
| `aep_skill_format` | `skill-format` |
| `aep_capability` | `capability --target ns/name@1.2.3` |
| `aep_check_skill` | `check-skill --file skill.json` |
| `aep_submit_skill` | `submit-skill --file skill.json --title "..." [--candidate sk-...]` |
| `aep_install_skill` | `install-skill --candidate sk-...` |
| `aep_status` / `aep_list` / `aep_get` | `status --approval ap-...` / `list` / `get --candidate ...` |

## Procedure

0. **Understand the request before writing anything.** Restate in two or
   three lines when the AEP Agent should use the Skill, what it should do,
   which inputs it must ask the person for, and whether any command changes
   something (sends, uploads, writes outside its output). When any of this is
   unclear, ask the person short, concrete questions and wait for the
   answers. Never assume formats, defaults or side effects.
1. **Read `aep_catalog` and `aep_skill_format`.** The catalog lists the
   installed capabilities and Workflows a command may target, and the
   installed Skills. Their names and aliases are taken, so do not reuse them.
   `aep_skill_format` is the full Skill format.
2. **Decide what the Skill is for.** One Skill covers one kind of request.
   When the work needs a fixed sequence of steps, build a Workflow first with
   the `aep-workflow-creator` skill, with typed parameters (`select`, `date`,
   `upload`, `folder`, ...) so the person gets a good form on the Web and in
   Telegram. Then make the Skill's command target that
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
5. **Submit and install locally.** Call `aep_submit_skill`, then
   `aep_install_skill`. Inspect its actual result. The installed Skill becomes
   available in the same session without an AEP approval card or restart.
   Installation does not imply business review or successful evaluation.
6. **Revise.** To revise, submit with the same `candidate_id`. An installed
   name gets the next version automatically. Only one version per name stays
   installed.

## Rules

- Never put passwords, tokens, keys or company data in instructions.
- Never write into the Host's workspace folders directly.
- Write instructions for the AEP Agent, including how to discover and use tools
  for the person's task. It may install/connect tools and use them in the same
  session. Preserve actual errors, at-most-once effects and model/data rules.
- Shared publication is separate from local installation; never forge review or
  validation evidence or decide historical approval records automatically.
