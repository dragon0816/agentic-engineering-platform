# Agent Web capability workspace redesign

Date: 2026-10-01
Status: approved direction; token/session changes explicitly deferred

## Problem

The installed Agent Web page renders, but its inline JavaScript does not parse because Python template escaping turns JavaScript newline escapes into literal line breaks inside quoted strings. The resulting startup failure prevents every interactive control from registering its event handler. The current Installed and Shared Platform views also expose platform data as diagnostic tables instead of a task-oriented capability workspace.

## Scope

This change will:

1. repair the JavaScript startup failure and make initialization failures visible;
2. add interaction feedback and accessible busy/focus states to actionable controls;
3. replace the separate Installed and Shared Platform presentations with one capability workspace patterned after the supplied Hermes reference;
4. present installed Skills, Workflows, Knowledge, Bridge Extensions and Applications with searchable category navigation and a list/detail layout;
5. present the shared catalog below the installed inventory with search, type/status filters, truthful lifecycle badges, a link to the authenticated Member Marketplace and an explicit synchronization action;
6. add focused tests for script validity and browser-visible interactions.

This change will not alter the query-token bootstrap, authentication contract, process token lifetime, model settings, Bridge authorization, marketplace selection, extension activation policy, publication workflow or contribution governance.

## User experience

The primary navigation gains a `Capabilities` destination. Its first region, `Installed on this Agent`, uses category tabs for Skills, Workflows, Knowledge, Extensions and Apps. A searchable list occupies the left side and a selected-item detail panel occupies the right side on wide screens. On narrow screens they stack vertically. Details show exact identity and version, description, owner, compatibility, authorization/install/runtime state and only actions that the current contracts can perform.

Workflow execution and Knowledge asking remain available through their existing typed endpoints. Extension rows show lifecycle evidence and their device-administrator activation gate; they do not expose a fake toggle. Applications are identified as independently launched software and link to their declared launch or marketplace destination when one exists.

The second region, `Shared Platform`, uses searchable/filterable cards. Each card distinguishes `available`, `selected`, `authorized` and `installed`. Selection stays in the separately authenticated Member Marketplace. The local Agent Web offers `Open Marketplace` and `Synchronize selected assets`; simply browsing the catalog performs no synchronization or install.

## Interaction and error behavior

The page shows a top-level startup state while required projections load. A JavaScript initialization error becomes a visible error panel instead of leaving a frozen page. Actions expose a busy label and `aria-busy`, prevent duplicate activation, preserve keyboard focus, and render success/refusal text next to the action. Tabs use tab semantics and support keyboard activation. Focus indicators remain visible and controls meet a 44-pixel minimum target where practical.

A failed projection affects its own region and does not disable unrelated navigation. A failed synchronization leaves the prior installed/catalog rendering intact and displays the typed failure. Existing authorization and policy refusals remain authoritative.

## Architecture

Personal Agent Web remains a loopback projection and ingress. Agent, Gateway, Workflow and Bridge components continue to own routing and execution. Registry and Member Marketplace remain the control plane; the local page consumes the existing catalog and installed-asset projections. Publishing, selection, authorization, synchronization, installation and execution remain distinct operations.

No new endpoint is required for the first implementation slice. If the current projections cannot truthfully populate an Applications installed category, the UI will render the known external application/catalog state and explicitly label unavailable local lifecycle data instead of inventing it.

## Verification

Focused verification will cover:

- the emitted inline script parses as JavaScript;
- the first page load registers navigation and action handlers;
- capability category, search and detail selection work with projected data;
- Shared Platform filters and lifecycle badges reflect the API projection;
- Workflow, Knowledge, Marketplace and synchronization actions call only their existing endpoints;
- Extension activation is not presented as a local Web action;
- loading, success and error states are visible and accessible;
- existing Agent Web API and authorization tests remain green.

Repository lint, formatting, type checking, the focused Agent Web suite and full test suite will run before completion.
