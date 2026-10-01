# Platform and Agent experience implementation plan

Date: 2026-10-01  
Approved specifications:

- `2026-10-01-shared-platform-identity-marketplace-design.md`
- `2026-10-01-agent-persona-chat-capability-authoring-design.md`

## Architectural guardrails

- Shared Platform remains the Registry, identity and selection control plane.
- Personal Agent and Bridge remain the reasoning and deterministic execution plane.
- Discovery, selection, synchronization, installation, activation and execution
  remain separate states.
- Known slash commands bypass LLM intent selection.
- Claude Code, Codex and Copilot are restricted conversation backends, not
  `ModelCatalog` providers and not alternate execution planes.
- Skills remain procedures. Python and PowerShell execute only as separately
  declared, installed and policy-authorized script tools.
- Persona content and contribution drafts cannot change policy, approve or publish.

## Slice 1 — identity and category contracts

Add backward-compatible roles to invitations/users, category metadata to
assets, member identity/admin invitation contracts and browser-login grant
contracts. Add validation tests before service code.

Verification: focused common contract tests, Ruff and mypy for touched modules.

## Slice 2 — durable identity and invitation administration

Introduce a SQLite identity store behind enrollment, invitation proof,
browser-login and member-session behavior. Add `me`, session refresh, admin
invitation issue/list/revoke HTTP operations. Migrate the composition to use
durable identity whenever `registry_path` is configured.

Verification: service and HTTP tests covering bootstrap admin, member denial,
restart, revocation and expiry.

## Slice 3 — Marketplace UI and fixture catalog

Replace the diagnostic page with signed-out/account/admin states, invitation
management, kind/category filters and clear selection/install status. Publish
harmless preview Skills, Workflows and a signed inert Extension idempotently.

Verification: real-socket and Chromium flows for admin/member catalogs and
category filtering; package/sync regression tests.

## Slice 4 — Agent persona settings

Add typed local profile/soul contracts, atomic persistence, settings endpoints
and UI. Inject bounded style guidance below system policy for subsequent turns.

Verification: contract, persistence, prompt-precedence and browser settings tests.

## Slice 5 — deterministic slash commands

Add a closed command registry and parsing/dispatch boundary for `/help`,
`/run workflow`, the four wiki commands and `/problem`. Replace hints with an
accessible command palette and multiline composer.

Verification: parser/route tests and Chromium keyboard interaction tests.

## Slice 6 — capability details and in-context drafts

Extend API projections for Skill files/docs/scripts, Workflow schema,
Knowledge configuration, Extension docs/lifecycle and Application docs. Add
Skill/Workflow draft forms in Capabilities and remove Improve navigation.

Verification: projection and browser tests for every kind and immutable pending drafts.

## Slice 7 — restricted local conversation backends

Add a provider-neutral conversation-backend protocol, fixed CLI discovery and
bounded adapters for Claude Code, Codex and Copilot. Persist backend per
conversation and add readiness/selection UI. No adapter inherits execution
authority or arbitrary command configuration.

Verification: fake-executable adapter tests for fixed argv/environment/cwd,
timeouts, output bounds, unavailable/authentication failures and tool-call revalidation.

## Slice 8 — governed Python and PowerShell script tools

Define script tool manifests, validate package-relative scripts, and add a
Bridge runner using JSON stdin/stdout, fixed interpreters, timeout, trace and
existing policy. Connect Skill detail and draft package validation without
making Skills executable themselves.

Verification: Python/PowerShell fixtures for success, malformed output,
timeout, path escape, hash mismatch and policy denial.

## Final verification and local deployment

Run focused tests after each slice and commit it independently. After all
slices run full pytest (excluding only the documented machine-specific Excel
absence assertion when Excel is present), Ruff, mypy, JavaScript syntax checks
and package build. Update `docs/TASKS.md`, `docs/DECISIONS.md` and `HANDOFF.md`,
restart the local Shared Platform and Agent Web, seed the preview catalog and
exercise the complete admin invitation, category, install, persona, command,
detail, draft and backend-readiness flows.
