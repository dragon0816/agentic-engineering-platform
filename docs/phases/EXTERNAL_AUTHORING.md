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

## Default user-level setup (owner 2026-10-15)

Owner requirement: Skills and Workflows produced with this platform must work on
it, and that is what sets AEP + Claude Code apart from plain Claude Code. So the
installed Agent carries, by default, the skills that produce platform-ready Skills
and Workflows, and Claude Code, Codex and Copilot can use them, and AEP's Knowledge
and installed Workflows, without a per-folder `connect`. Decision in
`docs/DECISIONS.md` (2026-10-15 "AEP skills and MCP servers in the coding agents'
user configuration by default").

What each detected agent gets (`host_runtime/agent_setup.py`):

| Agent | Skills (`aep-workflow-creator`, `aep-skill-creator`, `aep-knowledge`) | MCP servers `aep` and `aep-assistant` |
|---|---|---|
| Claude Code | `~/.claude/skills/` (`$CLAUDE_CONFIG_DIR/skills`) | top-level `mcpServers` of `~/.claude.json` (user scope, what `claude mcp add --scope user` writes) |
| Codex | `~/.agents/skills/` | `[mcp_servers."aep"]` and `[mcp_servers."aep-assistant"]` in `$CODEX_HOME/config.toml` (`~/.codex`), between `# >>> AEP managed` and `# <<< AEP managed` |
| Copilot CLI | `$COPILOT_HOME/skills/` (`~/.copilot`) | `mcpServers` of `~/.copilot/mcp-config.json` (`type: local`, `tools: ["*"]`) |

- `aep` is the authoring server (`aep-host mcp --agent <agent>`), statuses and codes
  only. `aep-assistant` (`aep-host assistant-mcp`, `host_runtime/assistant_bridge.py`)
  answers `initialize`/`tools/list` itself and forwards each `tools/call` to the
  running Agent Web's `POST /mcp`, reading `agent-web.json` (address) and
  `assistant-mcp-token` at call time: no token in any agent configuration, and an
  Agent Web restart on another port needs nothing. When Agent Web is not running the
  tool says so; the bridge does not start it.
- Managed marks: a skill folder carries `.aep-managed.json` (with the skill bundle
  version, a hash of the shipped texts); a JSON server entry is AEP's when its args
  run `host_runtime.cli`; the Codex entries are the marked block. Install/update
  replaces only those; a same-named skill or server of the person's own is kept and
  reported. Every edited file is copied to `<name>.aep-backup-<time>` first; an
  unreadable file is left unchanged.
- Entry points, all the same code: `aep-host assets --config host.json connect --for
  claude-code|codex|copilot|all --user [--remove|--status]`; `install.ps1` and
  `update.ps1` run `--for all --user` unless `-NoAgentSkills` (the update brings the
  skills to the new version); `uninstall.ps1 -Apply` runs `--remove` first; Agent
  Web Settings > Coding agents (`GET /api/coding-agents`, `POST
  /api/coding-agents/install|remove`).
- `--for all` skips an agent that is not here (command not on PATH and no
  configuration folder) with a note; naming one agent installs it regardless.
- The per-project `connect --project` now also writes `aep-knowledge` and, for
  Claude Code, the `aep-assistant` server.

Agent Web chat backends: the text-only Claude Code, Codex and Copilot backends stay
tool-less (2026-10-02 backend rule; `--restricted --strict-mcp-config`,
`--ignore-user-config`, `--available-tools=`), so the user-level setup does not reach
them. The Copilot agent mode (`copilot_agent`, CP2) gets AEP's tools explicitly: its
`--additional-mcp-config` names `aep-assistant` (`/mcp`) and `aep` (`/mcp/authoring`,
the authoring tools served by the same Agent Web with the assistant token, actor =
the Host's owner, source `external:copilot`), both allowed with `--allow-tool`, and
the three skills are written to `.conversation-backends/.github/skills/`, trusted with
`--add-dir`. Since 2026-10-15 Claude Code and Copilot also have an agent mode with
in-chat approval cards (`docs/phases/AGENT_MODE_BACKENDS.md`, Settings > Agent mode,
off by default); it loads AEP's skills (`--plugin-dir` for Claude Code, `--add-dir`
for Copilot) and the `aep`, `aep-assistant` and `aep-agent` servers. Codex stays
text-only.

Live-test fixes (2026-10-15):

- `aep_catalog` is compact (purpose, side effect and input field names per
  capability; installed Workflows and Skills) and kept under 15,000 characters; the
  rest is dropped with an `omitted` count. `aep_capability` gives one input schema,
  `aep_workflow_format` / `aep_skill_format` the full formats with a complete
  example (CLI `capability --target`, `workflow-format`, `skill-format`).
- Checking creates nothing: `check-workflow` used to create the task folder's
  `input/` and `output/`; now `prepare_workspaces` does it on submit, run and install.
- The creator skills start by restating the request and asking short questions when
  inputs, outputs, formats (encodings, dates), parameters or side effects are
  unclear, and prefer typed parameters for the generated forms.
