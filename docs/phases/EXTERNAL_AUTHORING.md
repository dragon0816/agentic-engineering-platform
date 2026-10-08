# External coding agents author Skills and Workflows

Owner request 2026-10-08: the resident harness may not yet be strong enough for
advanced coding and Knowledge work, so Claude Code, Codex and GitHub Copilot,
connected to AEP, must be able to use AEP's own Skill creator and Workflow
creator to develop Skills and Workflows this platform can use.

Owner decisions (2026-10-08):

- **Connection:** a CLI (`aep-host assets ...`) and an MCP server
  (`aep-host mcp`) that expose the same operations, so any of the three agents
  connects the same way.
- **Scope:** Workflows and Skills together.
- **Data:** the PUBLIC rule stays (`docs/DECISIONS.md`, 2026-09 data rule). An
  external agent receives schemas, the capability catalog, its own
  submissions and status codes only. Run and preview results never return
  step data or failure messages to it; the owner sees them in Agent Web.

## What already exists

`host_runtime/chat_authoring.py` lets the resident Agent draft, preview, run
and ask to install a Workflow; the owner's Agent Web button decides. Skills had
no authoring path (CONVERSATIONAL_AUTHORING H6/A4).

## Boundaries

- An external agent never approves, installs or runs a change. Every run and
  install becomes an `ApprovalRequest` decided by the owner's button, the same
  queue the resident Agent uses. Submissions carry `source: external:<agent>`;
  the agent name is self-declared and shown as such.
- A name belongs to whoever installed it first (owner decision 2026-10-07);
  versions only go up; the host fills owner, version and lifecycle.
- A Skill's `instructions` reach the model's prompt, so the approval shows the
  whole manifest. An externally authored Skill may not carry keyword `rules`
  (regexes are trusted installation configuration) or `script_tools`; its
  commands must target installed capabilities or Workflows; a `procedure` is
  accepted only for the Knowledge domain and must validate as a
  `KnowledgeProcedure`.
- Installing a Skill version moves the actor's earlier versions of that name to
  `skills/disabled/` (one installed version per name). Skills load at host
  start, so a new Skill is used after a restart.

## Slices

| Slice | What |
|---|---|
| X1 | `ChatAuthoring`: source tag, check without saving, Skill candidates, `install_skill` approvals, external status view without data |
| X2 | `aep-host assets catalog / check / submit / run / install / status / list / connect` |
| X3 | `aep-host mcp`: stdio MCP server with the same tools, standard library only |
| X4 | Creator Skills (`aep-workflow-creator`, `aep-skill-creator`) shipped as package data; `assets connect` writes them where each agent reads skills and prints its MCP configuration |
| X5 | Agent Web: external submissions waiting for approval, with the full manifest |
| X6 | `benchmarks/authoring_v1`: each agent, headless, builds assets from PUBLIC task descriptions; the operator approves; the installed asset is run and checked |

Agent skill and MCP locations used by `connect` (checked 2026-10-08):

| Agent | Project skills | MCP configuration |
|---|---|---|
| Claude Code | `.claude/skills/<name>/SKILL.md` | `.mcp.json` in the project |
| Codex | `.agents/skills/<name>/SKILL.md` | `[mcp_servers.aep]` in `~/.codex/config.toml` |
| Copilot CLI | `.github/skills/<name>/SKILL.md` | `~/.copilot/mcp-config.json` |
