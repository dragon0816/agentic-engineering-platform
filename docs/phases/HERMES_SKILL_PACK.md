# Hermes skill pack

Status: done (phase A 2026-10-15, phase B and this PC 2026-10-16, Claude Code).

## Owner request (2026-10-15)

Port the Hermes agent's skills (`%LOCALAPPDATA%\hermes\skills\<category>\<name>\`,
`SKILL.md` with YAML frontmatter plus scripts, references and templates; read
only) into AEP, so they can be used in Agent Web and by Claude Code / Copilot in
agent mode, and ship them to colleagues **switched off** (a backup to switch on in
Capabilities), next to AEP's own in-use Skills, which ship **switched on**.

Owner decisions:

- **Skipped (9):** `apple/apple-notes`, `apple/apple-reminders`, `apple/findmy`,
  `apple/imessage`, `social-media/xurl`, `software-development/python-debugpy`
  (macOS/Linux only); `autonomous-ai-agents/hermes-agent`,
  `software-development/hermes-agent-skill-authoring`,
  `software-development/inspecting-hermes-desktop-dom` (Hermes itself).
- **Internal (8, license UNLICENSED), this PC only, never in the repository:**
  `email/outlook-email-workflows`, `productivity/business-cards`,
  `productivity/html-report-delivery`, `productivity/leo-work-automation`,
  `productivity/pdf-linked-markdown`, `productivity/rs-workflow-jobs`,
  `research/rs-knowledge-base`, `software-development/aep-platform-testing`.
  Exception: `business-cards` also ships, after a personal-data scrub.
- **Everything else (MIT):** the repository's Hermes skill pack, with each skill's
  license and authors kept and a NOTICE listing the sources.
- Default state everywhere: switched off.

## What a ported skill is

Each skill becomes two things, made by `scripts/port_hermes_skills.py`:

1. **An AEP Skill manifest** `packages/hermes-skill-pack/manifests/hermes__<name>__<version>.json`
   (`agent.skills.SkillManifest`):
   - identity `hermes/<name>@<version>` (frontmatter `version`, else `1.0.0`);
     alias `<name>` with `_` for `-`;
   - owner `organization/aep`, visibility `organization`, lifecycle `published`
     (the internal ones on this PC: owner `user/leo.chi`, visibility `private`);
   - categories `hermes`, the Hermes category and the frontmatter tags (slugs);
     `compatibility.platforms` from `platforms`; provenance `Hermes agent skill
     <category>/<name> (<license>; author <authors>; <homepage>)` with the
     `sha256` of the source `SKILL.md` as revision;
   - `selector_hint` = the frontmatter description (at most 240 characters);
   - `instructions` = the description, an AEP note, then the `SKILL.md` body,
     adapted: Hermes tool names in backticks become neutral words (`terminal` ->
     shell, `read_file` -> read file, `web_extract` -> web page reader,
     `browser_click` -> browser (click), `delegate_task` -> sub-agent, ...); the
     skill's own Hermes folder (`~/.hermes/skills/<name>/`) becomes `<this skill's
     folder>/`; anything the host's credential pattern sees (placeholders such as
     `Bearer $AIRTABLE_API_KEY`) becomes `[redacted]` and the note names the
     variable. The note says the skill came from Hermes, that a tool call written
     `terminal(command=...)` means "run it in a shell, if this runtime lets you",
     that it must say so when the runtime has no equivalent, which commands and
     environment variables it needs, and that its scripts and references are in the
     coding-agent copy. No command bindings, rules or script tools: these are
     procedures, not capabilities, and nothing is invented.
   - A body over the host's 20,000-character instruction limit
     (`skill_authoring.MAX_INSTRUCTIONS_CHARS`) is cut at a `## ` heading and the
     note lists the sections left out (full text in the agent copy). Shortened:
     `claude-code`, `claude-design`, `humanizer`, `p5js`, `llm-wiki` (and the
     internal `aep-platform-testing`).
   - Every manifest passes `host_runtime.skill_authoring.check_skill` (the
     `aep_check_skill` / `check-skill` check) and `SkillManifest` validation
     (`tests/test_hermes_skill_pack.py`).
2. **A coding-agent skill folder** `packages/hermes-skill-pack/skills/vendor/hermes-<name>/`:
   the Hermes folder byte for byte (without `__pycache__`/`.pyc`), except the
   frontmatter `name: hermes-<name>` (Claude Code and Copilot expect the name to
   match the folder; the prefix avoids clashes with the person's own skills, e.g.
   an existing `ui-ux-pro-max`) and the skill-folder path above. The folder sits
   under `vendor/` so ruff leaves it alone (`packages/*/*/vendor`, like the
   migrated rs_workflow_system jobs) and pytest never collects its tests.

`packages/hermes-skill-pack/pack.json` lists every skill with source, version,
license, authors, source hash, file names, `default_enabled: false` and the
adaptations made; `NOTICE.md` is the attribution table.

Regenerate (deterministic; refuses on any finding below):

```text
.venv\Scripts\python.exe scripts\port_hermes_skills.py --source %LOCALAPPDATA%\hermes\skills --out packages\hermes-skill-pack [--personal-out <folder outside the repository>]
```

## Contents (51 skills)

| Hermes category | Ported |
|---|---|
| autonomous-ai-agents | claude-code, codex, computer-use, opencode |
| creative | architecture-diagram, ascii-video, baoyu-infographic, claude-design, design-md, humanizer, manim-video, p5js, popular-web-designs, songwriting-and-ai-music |
| devops | sdlc-review |
| email | email-inbox-triage, himalaya |
| media | gif-search, songsee, youtube-content |
| note-taking | obsidian |
| productivity | airtable, box, business-cards (scrubbed), document-to-action-items, docx, google-workspace, maps, meeting-action-items, notion, pdf, powerpoint, product-price-monitor, teams-meeting-pipeline, weekly-review-planning, xlsx |
| research | arxiv, competitor-news-monitor, grounded-citations, llm-wiki |
| software-development | codebase-inspection, dogfood, github, node-inspect-debugger, requesting-code-review, simplify-code, spike, systematic-debugging, test-driven-development |
| web | blocked-page-recovery |
| (no category) | ui-ux-pro-max |

Notes:

- `ui-ux-pro-max` sits at the top of the Hermes folder (no category) and its
  frontmatter states no license or author; the upstream repository
  (nextlevelbuilder/ui-ux-pro-max-skill) is MIT, recorded in `pack.json`. It is
  3.7 MB of the pack's 7.6 MB (search data and its own tests).
- `teams-meeting-pipeline` runs the `hermes teams` CLI and `sdlc-review` needs
  Hermes' kanban toolset; they port as procedures but only work where those exist
  (the AEP note says what they need).
- Five skills ship their own `LICENSE` (docx, pdf, powerpoint, xlsx, humanizer),
  kept in their folders.

## Personal-data and credential scan

`scan_text` / `scan_tree` run over every shipped file and manifest and refuse:
real credential shapes (GitHub, OpenAI/Anthropic, Slack, AWS, Google keys, JWTs,
private keys, Telegram bot tokens), the owner's name, account and addresses,
internal network and company domains, and any email address outside the example
and public-attribution domains. Findings of the 2026-10-15 run:

- No real credential in any of the 51. Placeholders only (`API_KEY=pat_your_token_here`,
  `Bearer $NOTION_API_KEY`, `password=args.password` in scripts); in the
  manifests they read `[redacted]` (airtable 18, notion 14, gif-search 1,
  blocked-page-recovery 1).
- Email addresses: documentation examples (`user@example.com`, `you@gmail.com`,
  `work@company.com`, ...) and two public upstream contacts kept for attribution
  (`hello@cocoon-ai.com` in architecture-diagram's author line, `hermes@agent.ai` in
  maps' HTTP user agent).
- Only `business-cards` held personal data. Scrubbed in the shipped copy (each
  replacement is a reviewed pattern in `BUSINESS_CARDS_SCRUB`, refused when the
  source changes): the owner's name (description, author and four sentences) ->
  "the user"; author -> `AEP (from an internal Hermes skill)`; license
  `UNLICENSED` -> `Internal use`; the related personal skill `rs-workflow-jobs`
  removed; Telegram as the channel and the `hermes send -t telegram` delivery ->
  "attach the PNG to your reply, or tell them its path"; the owner's data path
  `%LOCALAPPDATA%\hermes\business-cards\cards.db` and the script's `HERMES_HOME`
  -> `BUSINESS_CARDS_HOME` (default `~/.business-cards`, chart default there);
  the person and company names in the examples -> placeholders 王小明 /
  Hsiao-Ming Wang and 範例公司.
- `ui-ux-pro-max/data/stacks/avalonia.csv` holds `C:\Users\data\config.json` as an
  anti-pattern example: generic, kept.

## AEP in-use Skills in the bundle (owner-approved 2026-10-16)

Read from this PC's live workspace (`assets/skills`, `assets/workflows`, read only)
on 2026-10-15. Installed switched **on**:

- Every manifest `aep-host export-assets` ships (`host_runtime.assets.shipped()`):
  `company-agent/workflow-author@1.1.0`, `company-agent/knowledge-query@1.0.0`
  (set aside by 1.12.0 below), `company-agent/market-alignment@1.1.0`,
  `company-agent/personal-proof@1.1.0`, `engineering/coding@1.7.0`,
  `engineering/rs-ncc-improvement-plan-skill@1.0.0`, `engineering/team-tickets@2.1.0`,
  `engineering/weekly-report@2.0.0`, `engineering/sales-to-chipset@1.0.0`,
  `engineering/release-package-guide@1.0.0` and the Workflows they call.
- The bundle's `aep-skills/` (`deploy/windows-preview/aep-skills/skills/`), the
  owner's evolved Knowledge pair, live since 425c5f6, no personal data:
  `company-agent/knowledge-query@1.12.0` (team `engineering`; the Knowledge
  procedure for the shared RS_Knowledge vault, unchanged) and
  `engineering/knowledge-query@1.0.1` (tool route to `knowledge-query/ask`), re-owned
  from `user/leo.chi` to `team/engineering`, visibility `organization` (owner decision
  2026-10-16).

Not shipped: `preview/checklist-review-skill` + `preview/checklist-review` (built-in
preview catalog demo) and every `user/leo.chi` private Workflow (monthly / expense /
quote / SAP / SOP reports, `release-package-push`, `rs-wmt-package-release`,
`yahoo-stock-last-price`, `sync-test`): personal.

## Phase B: bundle, installer, switch semantics

Decision: `docs/DECISIONS.md` 2026-10-16 "Bundled Skills: in-use on, skill packs off,
a person's choices kept; pack copies in coding agents follow the switch".

- **Bundle** (`scripts/build_windows_preview.py`): `hermes/pack.json`,
  `hermes/NOTICE.md`, `hermes/manifests/*.json` and `hermes/agent/hermes-<name>/`
  (the vendor folders, flattened; deepest path 93 characters below the bundle root,
  within the 259-character budget); `aep-skills/` comes with the template. The
  credential scan accepts exactly the pack's seven documented placeholders
  (`ALLOWED_PLACEHOLDERS`, file + exact text); any other assignment still stops the
  build. `scripts/release_windows.py` notes say what is on and off.
- **Install / update** (`install.ps1`, run by `update.ps1`): after the coding-agent
  setup, `aep-host assets --config host.json install-bundled --bundle <bundle>`
  (`--no-agent-skills` with `-NoAgentSkills`), `host_runtime/skill_packs.py`:
  - shipped manifests and `aep-skills/` go on; `hermes/manifests` go to
    `assets/skills/disabled/`; `hermes/agent/*` go to AEP's store
    `workspace/agent-skills/<folder>` with `.aep-managed.json`
    (`{"managed_by": "aep", "pack": "hermes", "version": <tree digest>}`);
  - an identity already here, on or off, is left as it is (never overwritten,
    never switched on again); one in `workspace/removed/removed.jsonl` is not
    brought back;
  - a Skill meant to be on stays off when an earlier version was switched off or a
    newer one is here; one that goes on sets older active versions aside; an alias
    another switched-on Skill of its namespace uses keeps it off;
  - a store folder of another pack (this PC's `hermes-personal`) is not replaced.
  Also usable for extra sources: `--off <manifests>`, `--agent-skills <folders>`,
  `--agent-pack <name>`, `--no-shipped`.
- **Switch semantics in coding agents** (owner decision 2026-10-16): a pack skill's
  folder is copied into Claude Code's (`~/.claude/skills`) and Copilot's
  (`~/.copilot/skills`) skills folder only while its Skill is switched on
  (Capabilities > Switch on; `asset_shelf.switch_on(..., environment)` ->
  `skill_packs.sync_agent_copy` -> `agent_setup.link_pack_skill`), and taken out on
  Switch off or Remove. Only for an agent where AEP's own setup is present (so
  `-NoAgentSkills` or a removed setup is respected); a same-named folder of the
  person's own is never replaced or removed; an update refreshes the copies of
  switched-on pack skills; `connect --user --remove` and `uninstall.ps1 -Apply` take
  every pack copy out. The Agent Web switch message says what changed there.
- **Manual** `INSTALL.zh-TW.md`: install and update steps, file locations, section 12
  "安裝包附帶的 Skills" (what is on, the Hermes backups, how to switch on / off).
- **CI** (`verify.yml`, committed in 96f551b5): after the bundle install, the
  Knowledge Skill is on, `hermes__docx` is off and stored; a Skill moved to
  `disabled/` stays off after installing again.
- **Tests**: `tests/test_hermes_skill_pack.py`, `tests/test_bundled_skills.py`
  (default states, host start, update keeps choices, version and alias rules,
  agent copies follow the switch, `-NoAgentSkills`, CLI, other-pack store folders),
  `tests/test_windows_preview_bundle.py` (pack contents byte for byte, no skipped or
  internal skill except `business-cards`, allow-list refusal).
- **Local bundle smoke** (2026-10-16): built from the working tree with the previous
  release's dependency wheels, installed twice into a temporary root with
  `-NoShortcut -NoAgentSkills`: 26 on (24 shipped + 2; the shipped Knowledge 1.0.0
  then set aside), 51 off, 51 store folders; doctor `assets: 11 skill(s) and 14
  workflow(s)`; `ask "files.read nothing.txt"` still needs_input / unknown_skill; a
  Skill moved to `disabled/` stayed off on the second install. Temporary root removed.

## This PC (step 3, 2026-10-16)

- Backup first: `%LOCALAPPDATA%\AgenticEngineeringPlatform\backups\20261016-before-hermes-pack\`
  (`skills/`, `workflows/` of the live workspace).
- Internal skills generated outside the repository:
  `%LOCALAPPDATA%\AgenticEngineeringPlatform\hermes-personal-pack` (`--personal-out`;
  the repository pack regenerated identical).
- Installed with the same code the installer runs, without the shipped manifests and
  without touching any coding agent (`--no-shipped --no-agent-skills`): first the 8
  internal skills (`--agent-pack hermes-personal`), then the 51 of the pack. Result:
  58 `hermes__*` manifests in `workspace/assets/skills/disabled/` (this PC keeps its
  own internal `business-cards`; the scrubbed one was "already here"), 58 folders in
  `workspace/agent-skills/` (`hermes-business-cards` is the internal one), nothing
  switched on, every other file in `assets/skills` unchanged, nothing written to
  `~/.claude` or `~/.copilot`. No press was needed; Agent Web was not restarted (the
  Capabilities list reads `disabled/` from disk).
- Copying into Claude Code / Copilot on Switch on needs Agent Web running this code
  (restart by the owner).
