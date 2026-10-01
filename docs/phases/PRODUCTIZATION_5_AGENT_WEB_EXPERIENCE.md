# Productization 5 — Agent Web Experience Refinement

Status: completed and verified locally on 2026-10-02

## Problem

The Personal Agent Web exposes the required functions, but Ask spends the top
of the page on readiness cards and separates backend selection from the message
composer. A configured Gateway is disabled when its credential is temporarily
unavailable, while local conversation CLIs expose no sign-in path. Capabilities
contains the necessary data but does not present installed details and Shared
Platform discovery as one coherent capability browser.

## Requirements

### Slice 1 — Ask composer and backend authentication

1. Remove the three readiness cards from Ask. Readiness remains available
   through typed API state and compact inline backend status.
2. Move conversation selection into the persistent sidebar. Move backend
   selection into the composer footer below the multiline message input.
3. A configured Gateway is selectable even when its mapped credential is not
   currently present. The composer explains the missing credential and links
   the operator to Settings; selecting it does not fabricate readiness.
4. Codex, Claude Code and Copilot remain fixed restricted text-only adapters.
   The browser cannot submit an executable name or arguments.
5. When an installed CLI needs authentication, selecting it opens a local
   authentication dialog. Only an explicit **Authenticate** click may launch
   the fixed official login command (`codex login`, `claude auth login`, or
   `copilot login`) in a separate local console/browser flow.
6. A missing CLI gets installation guidance and cannot be treated as ready.
   Authentication output, account identifiers and tokens never enter the Web
   API response, conversation history or logs.

### Slice 2 — Capability browser and Share Platform Library

1. Replace the top Ask/Capabilities/Settings tabs with a persistent left
   workspace sidebar. Its primary actions are New session, Capabilities and
   Settings; selecting a Session opens Ask in the content area.
2. Put searchable multi-session management below those primary actions. The
   active Session is visibly selected and newly created Sessions appear there
   without a page reload.
3. Use top-level capability tabs, a left selectable list and a right detail
   pane. Keep the layout responsive below tablet width.
4. Skill detail renders its complete installed procedure Markdown plus command
   and script-tool metadata. Workflow, Knowledge, Extension and App detail
   preserve their existing type-specific controls and governance text.
5. Place an Agent-native Share Platform Library below the installed browser.
   It has Skills, Workflows, Extensions and Apps tabs plus search, category and
   lifecycle/status filters.
6. Shared package cards expose published, selected and installed as separate
   states. A selected package can start the existing all-or-nothing sync; an
   unselected package opens the authenticated Marketplace for selection.
7. Extension review and Application discovery link to the authenticated
   Marketplace. They do not reuse Add-on selection or imply local activation.
8. The UI remains dependency-free and inline in the installed wheel. It fetches
   no fonts, scripts, styles or images from external origins.

## Safety and contract boundaries

- Backend authentication is an explicit local side effect initiated by the
  operator. It never accepts shell text, credentials or arbitrary arguments.
- Gateway credential values remain external to configuration and continue to
  resolve through `SecretRef` and the execution environment.
- Publishing, Marketplace selection, synchronization, Extension activation and
  Application lifecycle remain distinct operations.
- Every conversation turn still uses the restricted backend adapter or the
  existing Gateway/Bridge path; authentication grants no capability permission.

## Verification

- Contract tests cover configured-but-unready Gateway selection, fixed login
  command launch, signed-out and missing CLI states, and API authentication.
- Page tests cover the compact composer, authentication dialog, sidebar session
  management, capability layout, Skill Markdown panel and Share Platform tabs/actions.
- JavaScript parses with Node, Python passes Ruff and mypy, and focused HTTP/UI
  regression tests pass before each slice is committed.
- The final local preview is restarted and exercised with the configured
  Gateway plus every installed CLI backend status.
