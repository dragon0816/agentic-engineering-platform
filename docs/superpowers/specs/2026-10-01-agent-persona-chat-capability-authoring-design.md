# Agent persona, chat backends and capability authoring

Date: 2026-10-01  
Status: approved direction; pending written-spec review

## Problem

Agent Web currently has one gateway-backed conversation experience and a
capability workspace whose detail panel exposes only summary facts. It does not
let the operator define the Agent's name, introduction or speaking style; use
locally authenticated Claude Code, Codex or Copilot as a conversation backend;
discover deterministic slash commands; inspect complete capability content;
or create Skill and Workflow drafts where those assets are used.

The current Ask hints resemble commands without behaving like a command
palette, and the Improve page separates authoring from the capability context
that gives it meaning.

## Scope and acceptance criteria

This slice will:

1. add local Agent profile settings for name, introduction and `soul.md`;
2. allow each conversation to choose the configured Gateway, Claude Code,
   Codex or Copilot when the corresponding local backend is available;
3. add a deterministic slash-command registry and a keyboard-accessible command
   palette opened by typing `/`;
4. replace the one-line Ask input with a three-line, auto-growing textarea and
   remove `What can I ask?` plus the existing command-like hint controls;
5. expand the Capabilities master-detail view with kind-specific content and
   actions for Skills, Workflows, Knowledge, Extensions and Applications;
6. move new Skill and Workflow draft creation into Capabilities and remove the
   separate Improve page;
7. support governed Python and PowerShell script tools without redefining a
   Skill as executable code or permitting arbitrary shell input; and
8. preserve draft, review, publication, installation and execution as separate
   lifecycle steps.

## Agent profile and soul

The local workspace owns two files:

- `agent/profile.json`: schema version, display name and introduction;
- `agent/soul.md`: bounded Markdown describing voice, tone and interaction
  preferences.

Settings exposes both through typed read/update requests with atomic writes.
The name and introduction appear in navigation, empty conversation state and
new-conversation greetings. `soul.md` is included in the bounded model context
as style guidance only. The system safety policy, actor, Bridge identity,
installed targets, tool contracts and authorization always take precedence.

The Markdown is size-limited, rejects recognizable credential material and is
rendered as text/approved Markdown without active HTML. Saving profile changes
affects subsequent turns and requires no process restart.

## Conversation backends

Conversation backend is distinct from model/provider configuration. The
existing `ModelClient` path remains the Gateway backend. New adapters implement
a provider-neutral `ConversationBackend` boundary for locally installed and
authenticated CLIs:

- Claude Code;
- Codex;
- Copilot.

The Settings page reports detection, authentication readiness and a diagnostic
reason when a backend is unavailable. The Ask header selects one backend per
conversation, and that choice is persisted with the conversation. Existing
conversations keep their original backend unless the user explicitly changes
it for a new turn.

CLI adapters use fixed executable discovery, fixed non-interactive arguments,
a dedicated empty working directory, bounded input/output, timeout and
environment allowlist. Browser input cannot supply executable paths, flags,
working directories or environment variables. The CLI is used for inference;
its native autonomous shell, filesystem and external tools are disabled. A
backend may propose only the same structured installed-tool calls as the
Gateway. The Agent validates those calls and the Bridge enforces policy before
every execution. Backend failure becomes a typed conversation result and does
not silently fall back to another backend.

This explicitly supersedes the earlier Phase 5 scope decision that excluded
Claude Code and Codex as model providers: they remain outside `ModelCatalog`
and enter through the separate local conversation-backend boundary.

## Slash-command registry

Typing `/` at the start of the Ask textarea opens a searchable palette. Arrow
keys move, Enter accepts and Escape closes it. Each row shows syntax, purpose
and readiness. Known commands bypass LLM intent selection and are parsed by a
closed registry.

The first registry contains:

- `/help` — list supported commands and current readiness;
- `/run workflow` — choose an installed exact Workflow and open its typed
  parameter form;
- `/wiki-convert` — run the installed deterministic document conversion route;
- `/wiki-ingest` — run the installed governed ingestion route;
- `/wiki-lint` — validate one configured Knowledge source;
- `/wiki-query` — query an exact accessible Knowledge asset;
- `/problem` — create a local problem/improvement draft from the current
  conversation.

Unavailable commands remain visible with their missing installed asset or
configuration. They return a typed `needs_input` result rather than being sent
as natural language. Unknown slash commands show command help and never run.

## Capability details

Selecting an item in the left list populates one right-side detail section:

- **Skill** shows its rendered Markdown procedure, package file inventory,
  bundled Python/PowerShell scripts, command aliases, required capabilities,
  permissions and exact version.
- **Workflow** shows documentation, deterministic steps, dependencies and a
  parameter form generated from its declared input contract. Run submits the
  existing exact Workflow request.
- **Knowledge** shows source kind, local Vault location or source URL,
  provenance, ingestion/lint state and exact query action. Secret-bearing URLs
  are forbidden.
- **Extension** shows its documentation, publisher/signature, compatibility,
  declared capabilities, process boundary, health and activation status.
- **Application** shows documentation, owner, release, repository and declared
  integration links. It is not presented as an Agent package.

The API returns structured detail projections; the browser does not read local
paths or packages directly. Missing or malformed documentation affects only the
selected detail panel.

## Governed script support

A Skill may bundle scripts as supporting resources but remains a procedure, not
a function. Executable scripts are declared separately as atomic script tools
with exact package-relative path, runtime (`python` or `powershell`), input and
output contracts, timeout, side-effect classification and required approval.

The Bridge runs only installed, hash-verified scripts from their staged package
directory. Arguments cross JSON over stdin and results cross JSON over stdout;
no command string interpolation or arbitrary path is accepted. PowerShell uses
the fixed installed host and non-interactive mode. Python uses the preview's
fixed interpreter or an approved isolated environment. The normal Bridge
policy, timeout, trace and approval gates apply.

## Skill and Workflow draft creation

Capabilities gains `New Skill` and `New Workflow`. Forms create local candidate
drafts with host-owned actor and namespace, generated identity, description,
categories and kind-specific content. Skill drafts may add Markdown and script
resources; Workflow drafts define parameters and deterministic steps by
selecting installed capabilities.

Drafts are persisted in the existing contribution store with pending business
and technical-policy reviews. They cannot install, execute, approve or publish
themselves. Editing creates a new immutable draft revision. The separate
Improve navigation and page are removed; `/problem` and the two creation
actions cover its supported outcomes in context.

## Failure and security behavior

Persona text never changes policy priority. CLI output is untrusted provider
output and passes the same bounded parsing and tool admission as Gateway
output. A CLI process cannot inherit platform, board or model credentials that
its adapter does not explicitly require. Script drafts are inert until the
normal validation, review, publication, selection, synchronization and Bridge
authorization lifecycle completes.

Knowledge paths and URLs are configuration metadata; the detail page cannot
turn display into ingestion. Workflow forms reject arguments outside the exact
input contract. All write actions expose success, validation and refusal state
beside the initiating control.

## Verification

Tests will cover profile validation and atomic persistence, soul prompt
precedence, backend detection, fixed CLI invocation, unavailable/authentication
failures, timeout/output bounds and tool-call revalidation. Slash-command tests
will cover completion, keyboard behavior, deterministic routing, unavailable
commands and `/problem` draft creation.

Capability API/browser tests will cover each detail kind, Workflow parameter
forms, Knowledge settings, Extension/Application documentation and draft
creation. Script tests will prove fixed interpreter/path behavior, JSON I/O,
hash verification, timeout and policy denial. The emitted JavaScript will be
syntax-checked and exercised in real Chromium. Repository lint, type checking,
focused tests, full tests and the Windows build must pass before completion.

