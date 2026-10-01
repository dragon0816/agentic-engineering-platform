# Handoff

Date: 2026-10-02 (Asia/Taipei)

Branch: `main`

Status: Productization 5 Agent Web experience refinement and Gateway chat repair are complete and running locally

## Goal

Make Personal Agent Web usable as the primary local Agent workspace: a compact
Ask composer with switchable conversation backends, persistent sidebar session
management, an inspectable installed-capability workspace and a native Share
Platform library for governed discovery and synchronization.

## Completed

- Ask no longer spends space on readiness cards. The multiline composer owns
  the backend selector and compact readiness state.
- A configured Gateway remains selectable even when its mapped credential is
  absent. Settings explains the missing environment mapping without accepting
  or storing a token value.
- Codex, Claude Code and Copilot expose fixed authentication actions. The Web
  request cannot supply a command or arguments; the host launches only the
  adapter's fixed official login vector in a separate local process.
- New session, Capabilities and Settings now live in a persistent left sidebar.
  Searchable durable Sessions appear below them, show their backend/message
  count and open Ask when selected. The former top-level page tabs and Ask
  conversation dropdown were removed.
- Capabilities uses type tabs, a searchable installed list and a scrollable
  detail pane. Skill details show complete `SKILL.md`, commands and script-tool
  metadata. Workflow, Knowledge, Extension and App details retain their typed
  controls and governance guidance.
- Share Platform Library provides Skills, Workflows, Extensions and Apps tabs,
  category/status/search filters and cards that keep published, selected and
  installed states distinct. Selected packages invoke the existing explicit
  all-or-nothing synchronization; unselected packages and independent Apps
  link to the authenticated Marketplace.
- The shared-catalog Web projection now carries published asset categories for
  filtering. Categories remain display metadata and do not grant entitlement,
  authorization, installation or execution permission.
- Headless Edge visual verification found and fixed an underscore-to-hyphen DOM
  key mismatch for the Bridge Extension library tab. Ask, installed Skill
  details and the Share Platform library were then rendered without an error
  banner.
- Gateway chat failed before reaching LiteLLM because the Agent preview process
  lacked its configured `LITELLM_MASTER_KEY`. The ignored local supervisor now
  loads that key from the existing Gateway `.env` into the Agent process only;
  no credential value is stored in host settings or committed files.
- A missing mapped Gateway credential now produces an actionable conversation
  error naming the configured environment variable. The underlying typed
  `credential_unavailable` failure remains available to clients.

## Commits

- `5e8eea0` Define Agent Web experience refinement
- `d1959f9` Refine Agent workspace navigation requirements
- `57af999` Refine Agent composer and backend authentication
- `6151a47` Build Agent workspace sidebar and capability library
- `9ae722c` Fix Share Platform extension tab rendering
- `730b6cf` Explain missing Gateway credentials in Agent chat

## Verification

- Final full suite: 1,510 passed, 4 skipped, 2 environment-specific deselected.
  The deselected cases are the known Edge CDP harness case and the assertion
  that Excel is absent on a machine where Excel is installed.
- Focused Agent Web suite: 53 passed, 1 real-Chromium case deselected.
- Emitted browser JavaScript parses with Node.
- Ruff lint passed and all 349 tracked Python files are formatted.
- mypy strict passed for 271 source files.
- Offline `python -m build --no-isolation` produced both sdist and wheel.
- A new missing-credential regression test passed. Live Agent Web API status
  reported the Gateway ready with `gpt-5.5`, and a natural-language Chinese turn
  completed through the configured LiteLLM Gateway.
- Direct Edge DevTools visual checks loaded current local API data, switched to
  Capabilities, rendered full Skill Markdown and scrolled through Share
  Platform Skills/category/status/install controls. All three local listeners
  are active.

## Local runtime

- Shared Platform control: `http://127.0.0.1:18765`
- Marketplace: `http://127.0.0.1:18766`
- Agent Web: `http://127.0.0.1:53581` with the per-process bootstrap URL printed
  by the ignored `.scratch/run_local_preview.ps1` supervisor
- Durable preview database:
  `%LOCALAPPDATA%\AgenticEngineeringPlatform\shared-platform-local\registry-v2.sqlite`

Current backend status after restart: Gateway, Codex and Claude Code are ready;
Copilot is not installed. `gpt-5.5` completed a live natural-language Agent
Web turn in Traditional Chinese through the Gateway.

## Known limits

- This workstation's repository browser harness loses Edge's CDP WebSocket at
  the first page command. Direct isolated-profile Edge DevTools verification
  succeeds and was used for the final rendered-page evidence.
- Claude Code authentication is ready, but earlier live turns received the
  organization's subscription-disabled HTTP 403. Backend authentication and
  provider service access therefore remain separate status facts.
- Applications keep an independent release lifecycle. The Agent library links
  to Marketplace discovery and does not claim to install an Application into
  the Bridge runtime.
- The Gateway key loader in `.scratch/run_local_preview.ps1` is a workstation
  preview convenience and is ignored by Git. Other launch methods must provide
  the mapped environment variable to the Agent process through their normal
  secret provisioning mechanism.

## Next action

Review the running Agent Web in the in-app browser. The Gateway is selectable
in the Ask composer and can now answer ordinary chat. Also check New session,
Session switching, installed capability details and Share Platform filters.
