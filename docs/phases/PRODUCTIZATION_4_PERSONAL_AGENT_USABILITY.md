# Productization 4 — Personal Agent Usability

Status: complete; slices 1–5 complete

## User outcome

The Personal Agent Web is a usable local workspace rather than a diagnostic
page. A member can tell whether natural-language routing is ready, discover
what installed commands can do, configure a provider-neutral model endpoint
without storing a secret value, and navigate the existing governed paths for
Agent Add-ons, Workflows, Knowledge, Bridge Extensions and Applications.

The known company gateway is OpenAI-compatible and is normally available at
`http://127.0.0.1:4000/v1`. The model id remains explicit host configuration;
the runtime must not guess one.

## Architecture guard

- The Web remains a loopback ingress and projection. Routing and execution
  remain in Agent, Gateway, Workflow and Bridge components.
- Model configuration reuses `ModelBinding`, `ModelCatalog`, `SecretRef` and
  `CredentialBinding`; no provider-specific secret is introduced.
- A saved setting is validated as a complete `CompanyHostConfiguration` and
  written atomically. Runtime changes take effect only after restart.
- Installed commands are projected from `SkillManifest`; the page does not
  hard-code product workflows.
- Marketplace selection and synchronization remain distinct from execution
  authorization. Extension activation remains device-admin governed.

## Slices

1. **Readiness and command discovery** — show actionable readiness, installed
   capability counts and clickable command examples derived from manifests.
2. **Safe model settings** — configure endpoint, model, alias and optional
   environment-backed `SecretRef` through a closed Web contract.
3. **Conversation workspace** — durable local sessions, clarification and
   human-readable history over the existing request contract.
4. **Bounded tool loop** — provider-neutral tool calls, progress/evidence and
   bounded repair while policy remains external to the model.
5. **Capability management and feedback** — integrated install status,
   contribution drafts and standardized improvement requests.

Each slice requires a reproducible Windows/Python 3.12 green path before the
next slice is declared complete.

## Slice 3 acceptance criteria

- A first Web visit creates a host-owned local conversation and cannot claim a
  different actor, namespace, Bridge or permission.
- User and assistant messages, result status and trace identifiers survive a
  runtime restart in the Bridge's existing SQLite state.
- A bounded recent-conversation list and bounded message history prevent the
  page from treating an unbounded transcript as runtime context.
- Every submitted turn carries its stable session id through the existing
  `LocalAgentRequest`; routing and Bridge policy remain unchanged.
- Refreshing or switching conversations causes no execution.

## Slice 4 acceptance criteria

- An OpenAI-compatible model sees only commands derived from installed Skill
  manifests. Provider tool names map back to one exact capability or Workflow.
- Every accepted call crosses the existing Gateway, Workflow and Bridge policy
  boundaries. Model output cannot add a target, grant or execution permission.
- A model may make at most four tool calls across five model turns. Unknown
  tools are never executed, repeated failure stops with a typed reason, and
  conversation history/tool observations are size bounded.
- Known dot commands remain deterministic and bypass model selection.
- Tool execution evidence, status and trace identifiers are returned through
  the conversation API and Workflow runs remain in durable local state.
- The normal company endpoint remains `http://127.0.0.1:4000/v1`; its served
  model id is still explicit host configuration.

## Slice 5 acceptance criteria

- A member can capture recent immutable conversation excerpts as either an
  improvement request for one exact installed Skill, Workflow or Knowledge
  version, or a new Skill/Workflow proposal.
- Actor, namespace and owner are derived by the Host. Browser input cannot
  claim those fields or an approval, lifecycle or publication state.
- Each draft records the problem or opportunity, expected and actual behavior,
  one or more acceptance criteria, exact conversation message ids and any
  assistant trace identifiers.
- Drafts survive restart in actor-filtered local state and perform no
  capability execution or external write.
- Every captured item remains `draft`, non-publishable and separately pending
  business and technical-policy review. Capture cannot mutate, install or
  publish an asset.

## Slice 1–2 acceptance criteria

- A host without a routing model visibly says natural-language routing is not
  configured and still lists deterministic commands.
- Installed Knowledge without a routing model does not prevent the local Web
  or deterministic Workflows from starting; it remains unavailable until the
  prerequisite is configured.
- Every command hint is derived from the installed Skill manifest and fills
  the Ask input without executing anything.
- Settings can save an OpenAI-compatible endpoint at
  `http://127.0.0.1:4000/v1` with an explicit model id and alias.
- The request cannot carry a credential value. An optional credential is only
  a `SecretRef` plus environment-variable name.
- Invalid settings or settings that would invalidate installed Knowledge leave
  the existing `host.json` unchanged.
- A valid update is atomic, reports restart required, and exposes no secret
  through the API or page.
- The existing loopback host and per-process bearer protections cover all new
  endpoints.

