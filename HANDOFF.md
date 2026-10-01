# Handoff

Date: 2026-10-01 (Asia/Taipei)
Branch: `main`
Status: Product experience implementation complete and running locally

## Goal

Deliver the approved Shared Platform and Personal Agent Web experience: durable
invitation identity and administration, categorized Marketplace fixtures,
persona settings, usable natural-language backends, deterministic slash
commands, rich capability details and governed Skill/Workflow drafting and
script execution.

## Completed

- Shared Platform identity, invitation proofs, users, browser logins, member
  sessions and Add-on selections persist in SQLite. Selection, revocation and
  version replacement preserve their atomic authorization semantics across
  restarts. The first bootstrap invitation is a
  `platform_admin`; the UI supports account state and invitation management.
- Marketplace has kind/category/status filters, two test Skills, two test
  Workflows and one governed inert Bridge Extension. Extension administration
  remains separate from member Add-on selection.
- Agent Settings persists name, introduction and bounded `soul.md`; persona
  guidance affects speaking style after system policy and does not grant tools.
- Ask has a three-line editor and deterministic `/help`, `/run workflow`,
  `/wiki-convert`, `/wiki-ingest`, `/wiki-lint`, `/wiki-query` and `/problem`
  commands. Problem and new Skill/Workflow requests persist as pending drafts
  and cannot approve or publish themselves.
- Capabilities shows kind-specific Skill Markdown/script references, Workflow
  parameter metadata, Knowledge locations, Extension lifecycle/docs and App
  guidance. New Skill/Workflow forms live here; Improve navigation was removed.
- Conversations can select Gateway, Codex, Claude Code or Copilot. Local CLIs
  run with fixed restricted arguments, stdin-only prompts, bounded history,
  isolated cwd and reduced environment. They return text only and cannot bypass
  Bridge policy. Missing Gateway credentials and CLI authentication failures
  are projected as unavailable states.
- Published and approved Python/PowerShell script tools have exact
  package-relative entrypoints, SHA-256 verification before registration and
  every call, JSON stdin/stdout, fixed noninteractive interpreters, output and
  timeout bounds, and normal Bridge authorization.
- Member Add-on selection and Agent synchronization were exercised separately
  from administrator Extension discovery. Two fixtures installed successfully;
  the existing manual-grants file was restored after the isolated sync proof.

## Commits

- `e3b6cfb` Define platform identity and Agent experience designs
- `c6c489a` Plan platform and Agent experience slices
- `74e6b02` Add marketplace identity and category contracts
- `ee62d7d` Persist platform identity and invitation administration
- `c58d1bc` Build authenticated marketplace experience
- `8eed562` Add local Agent persona settings
- `7e8ca64` Add deterministic Agent slash commands
- `8af8f8b` Expand capability details and authoring
- `d06f315` Add restricted local conversation backends
- `79be7f2` Add governed local script tools
- `44290af` Polish preview authentication and backend readiness
- `2f2c036` Document completed Agent experience rollout
- `e4b3938` Persist marketplace selections

## Verification

- `pytest`: 1,502 passed, 4 skipped, 2 environment-specific deselected.
  `tests/test_browser.py` and the Agent real-Chromium case were deselected because
  this installed Chromium closes its CDP WebSocket immediately. The single
  Excel-absence assertion was deselected because Excel is installed here.
- Focused final regression: 63 passed, 1 real-Chromium test deselected.
- Ruff lint: passed; Ruff formatting: 348 files formatted.
- mypy strict: 271 source files passed.
- sdist and wheel: built successfully; `pip check`: passed.
- Live Shared Platform proof: actor `leo.chi`, role `platform_admin`, engineering
  group, 4 installable catalog entries, 1 admin Extension, 4 category facets.
- Live Add-on proof: 2 selections synchronized and installed.
- Live restart proof: 1 Skill and 1 Workflow remained selected after the full
  Shared Platform and Agent supervisor stopped and started again.
- Live Agent proof: 7 slash commands, 5 local Skills, 5 local Workflows; Codex
  restricted conversation returned `ready`.

## Local runtime

- Shared Platform control: `http://127.0.0.1:18765`
- Marketplace: `http://127.0.0.1:18766`
- Agent Web: `http://127.0.0.1:53581` with the per-process URL printed at startup
- Durable preview database: `%LOCALAPPDATA%\AgenticEngineeringPlatform\shared-platform-local\registry-v2.sqlite`
- Non-secret runtime status: the adjacent `status-v2.json`
- The ignored `.scratch/run_local_preview.ps1` supervises both services for this
  workstation and `.scratch/run_local_shared_platform.py` seeds the fixtures.

## Known limits

- The configured Gateway remains `http://127.0.0.1:4000/v1`, model `gpt-5.5`,
  but `LITELLM_MASTER_KEY` is not set in the service environment. Agent Web
  therefore reports Gateway unavailable and chooses a working local CLI.
- Claude Code is installed but the organization returns HTTP 403 because
  subscription access is disabled. The adapter now reports
  `backend_authentication_failed`. Codex is installed and passed the live turn.
  Copilot CLI is not installed.
- This host still uses manual `grants.json`. The isolated Add-on sync proof saved
  its delivered authorization as `authorization.sync-validation.json` and
  restored `grants.json`, so current Bridge execution policy is unchanged.

## Next action

Review the open Marketplace and Agent Web pages. Set `LITELLM_MASTER_KEY` before
testing the Gateway; until then select Codex in Ask. Exercise persona editing,
slash completion, capability details, draft creation and invitation creation.
Do not treat the preview Extension as activated: it is discovery/admin fixture
data only and still requires the separate device approval and staging flow.
