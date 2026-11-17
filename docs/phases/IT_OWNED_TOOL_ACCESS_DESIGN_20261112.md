# IT-owned tool access and installation

Status: owner policy and the concrete four-part harness scope explicitly
approved2026-11-12:「同意上述 harness 範圍並開始實作」. Implementation proceeds
in the isolated it-owned-tool-access-20261112 worktree according to the plan.
The original resident, delivered package and remote main remain unchanged.

## Owner decision and acceptance

Current clarification2026-11-13:「不用保留IT，在電腦上可以執行，就可以用」.
Tools available in the actual execution environment can run directly; no IT
approval, IT identity or IT-managed allowlist is required by AEP. The following
November12 wording is historical, not an additional prerequisite. Existing file
names retain the original phase identifier for traceability.

Owner,2026-11-12: AEP agents should access all AEP tools and install any tool
usable in the execution environment; company IT decides whether a computer may
use a tool. Explicit clarification:「取消工具安裝與執行核准，由公司 IT 控制」.

Consequently AEP will not have an application tool allowlist, per-tool grant,
risk-based execution approval or installation approval. This is the requested
product behavior, not an optional development bypass. The currently signed-in
OS/service identity and actual environment determine execution results.
AEP must not claim an operation was approved by IT without evidence; it reports
the actual execution result or technical dependency/authentication/OS error.

Agent Web users should ask for a task. The agent discovers tools, installs a
missing tool when necessary, uses it and returns the real outcome. A user does
not have to select a different conversation mode or find an approval card to
obtain an otherwise executable tool. Tools connected to a remote Bridge/MCP
are evaluated at that execution target, not at the browser's operating system.

## Skill-first causal evidence

The applicable aep-skill-creator procedure can bind only installed capabilities.
Assessment read-only probes with valid Skill aliases returned:

- outlook/search@1.0.0: capability is not installed;
- outlook/read@1.0.0: capability is not installed.

The direct live capability lookup returned capability_unknown. No candidate was
submitted or installed. host.py only registers these handlers if an installed
asset already uses them. Capability runtime authorize/confirmation_needed checks
grants/approval independently of instructions. Native agent-mode settings and
backend launch code supply a separate tool set. Skill text is not consulted by
these registration/permission/install branches and cannot change their result.
Improving a Skill remains appropriate for how to query/summarize a thread or
validate a report; it cannot provide the requested tool-access semantics.
The detailed prior assessment is DATA_DASHBOARD_MAIL_CAPABILITY_ASSESSMENT_20261112.md.

## Alternatives considered

1. Recommended: one discoverable tool inventory and normal installation path,
   with no AEP tool permission/approval layer. Retain typed contracts, identity,
   truthful outcomes and execution evidence. Matches the owner's direction and
   avoids different default behavior across local/Shared/native/MCP routes.
2. A development flag that auto-approves while retaining production gates:
   rejected as the target design; the owner explicitly does not want AEP to
   implement tool governance. Do not implement this as owner_mode=true alone.
3. Leave each CLI/MCP to be manually configured by IT and keep AEP a thin caller:
   technically possible but insufficient for the requested agent-driven tool
   installation and consistent same-session discovery.

## Smallest coherent implementation scope

### A. Inventory, discovery and same-session use

- Register built-in capabilities independently of whether a Skill/Workflow first
  references them. Dependencies are checked lazily: discovering Outlook must not
  open COM or read a mailbox. Show missing dependencies with an install/setup
  explanation instead of hiding the tool or calling it unapproved.
- Make Bridge and connected MCP tools available through the same agent-facing
  discovery/description/invocation contracts. Skills guide selection, not whether
  a tool exists. A bounded paginated/searchable catalog avoids context overflow;
  pagination/selection is not a tool authorization boundary.
- A newly installed/connected tool becomes discoverable in the same session on
  the next tool lookup/turn, without an application restart or mode toggle.
- Supported conversation adapters consume this inventory. Remove AEP-imposed
  per-backend tool restrictions and approval-relay requirements; if an adapter,
  model or executable genuinely lacks the required tool-call protocol, report
  that actual incompatibility. Do not claim all third-party CLIs already work.

### B. Execute under the actual IT-managed environment

- Remove AEP capability-grant and per-operation approval admission checks for
  reads, writes, execute and external side effects. No approval/pending card for
  tool execution, sending mail, deleting or writing external systems.
- Remove AEP-added command/folder/mail allow/deny boundaries. Folder/date/sender
  arguments remain ordinary task/query filters, not a ceiling on IT-accessible
  data. Provider page/body limits remain explicit with continuation/truncation
  information; never present a partial result as complete.
- Do not grant administrator privileges, synthesize credentials or bypass an
  actual external permission denial. Let the OS/source service/IT-managed CLI
  decide and return its technical error. Remove AEP-added ask/deny overrides;
  do not rewrite third-party permission settings after a refusal.
- Preserve user intent: draft means save a draft, not send. Sending is a separate
  executable action; it no longer requires an AEP send-card press. Expose the
  existing send operation through the common typed execution path instead of
  keeping it reachable only from a card decision.

### C. Install tools and assets without a human AEP approval gate

- Expose normal agent installation/connection operations using the existing
  stdio/HTTP MCP manager and local execution/install mechanisms. Support sources
  supplied by the user/agent without an AEP package/registry allowlist.
- Skill/Workflow/tool installation must not require the owner to press Install
  approval. Parse manifests, detect broken dependencies/protocols and report
  failures as technical problems; untested is a visible quality status, not
  fabricated verification or a tool-use approval condition.
- Preserve source/version/integrity and actual test provenance. Do not forge an
  approval_ref, business review or passed trial just to satisfy an old schema.
  Adjust local installation metadata/contracts where needed. Publishing to a
  shared registry remains distinct from local installation and is not part of
  this tool-access change.
- Old grants/cards remain readable history; they no longer authorize tool use.
  Do not approve old cards on the owner's behalf or replay historical actions.
  Active continuations must consult execution receipts before resuming so a
  successful side effect is never repeated.

### D. Preserve unrelated contracts

- Keep authenticated user/session/Bridge identities and correct execution target;
  removing tool ACLs does not mean an unauthenticated service endpoint.
- Keep model/data-routing requirements separate. Do not relabel company email
  PUBLIC or remove the native PUBLIC-session condition as part of tool access.
  All tools on an eligible company Gateway route should work without mode
  switching. Any remaining data-route incompatibility must be reported as such,
  not as an absent tool. A later model/data-policy change needs its own decision.
- Keep secret references/redacted logs, input/output validation, deterministic
  Workflow execution, dry-run intent, at-most-once effects, artifact ownership,
  bounded retries and honest failure/completion/coverage statuses.
- Preserve Knowledge grounding/citations/scope and its existing read-answer
  behavior. Merely making tools discoverable must not mutate a knowledge base
  when the user asks a read-only question.
- Do not indiscriminately delete every allowed_tools parameter: a deterministic
  retrieval/evaluation helper still implements its declared query/check contract.
  It is not a general Agent tool-permission profile. The general Agent retains
  the common catalog and can separately invoke other tools for the requested
  task; choosing Knowledge never revokes its tools. Preserve helper isolation
  regressions and measure actual query behavior rather than weakening them.
- The coding agent's external permission guard is outside AEP; this design is
  not authorization to circumvent a guard that rejects the coding agent itself.

## Harness/contract surfaces and bounded stages

Stage1: built-in discovery and execution, unified Gateway/MCP access, no local
tool grants/approval admission; tests prove a clean profile can search/read mail
using fakes and execute declared effects once. Principal surfaces:
host_runtime/host.py, agent/gateway.py, capabilities/runtime.py, common execution
contracts, integrations/outlook_mail.py, capabilities/mail_read and agent_mail.

Stage2: ordinary local install/connect operations and truthful metadata, live
catalog refresh; host_runtime/chat_authoring.py, external_authoring.py,
mcp_servers.py, mcp_server.py, assistant/tool wrappers and relevant asset metadata.

Stage3: conversation adapter exposure and UI terminology; agent_mode.py,
agent_mode_settings.py, conversation_backends.py and Agent Web routes/page.
Remove AEP's permission-relay prerequisite; keep technical provider limitations
honest. Update Skills/guides that still tell agents to wait for AEP install cards.

These stages define the requested consent scope, not permission for unrelated
chat-form persistence, new data-routing policy, a new mail-thread algorithm or
changes to Knowledge retrieval/ranking. If a new harness surface is required
outside this scope, explain the evidence and obtain further consent first.
Implement in a separate managed worktree after approval; do not modify the
delivered C4C package or running resident while developing.

## Verification before completion

Use a recorded before/after matrix, with no real mailbox writes or external
messages. Existing approval tests encode the old contract: replace their
expectations with the owner's new behavior and stronger outcome assertions;
do not delete assertions just to make a failing implementation pass.

1. Clean profile with no referencing Skill/Workflow discovers built-in tools;
   discovery performs zero COM/mail operations. Existing unknown Outlook lookup
   and Skill-binding probes now find the real registered capability.
2. Gateway, supported native adapters and MCP see the same callable identities;
   catalog pagination never makes a tool permanently inaccessible. A tool used
   without a selected Skill works under the same execution contract.
3. No app grant/approval is needed for read/write/execute/external effects.
   Recording handlers verify actual calls and outputs with zero pending cards;
   duplicate/retry/delegation paths execute a successful effect at most once.
4. Fake mailboxes read IT-accessible Inbox/Sent/custom folders; requested filters
   still apply, failures/truncation are explicit. A draft-only request sends
   zero messages; a send request invokes the recording sender once without a
   card. This does not claim a complete-thread algorithm has been added.
5. Agent installs/connects a local fixture tool/MCP server, discovers and invokes
   it in the same session without approval/restart. Unsupported OS/dependency,
   authentication and OS-denied examples return truthful technical errors.
6. No forged approvals, fake verification, automatic historical-card replay,
   secret leakage or cross-session artifact substitution. Existing installs
   migrate without grants becoming an execution prerequisite.
7. Run the same445 baseline Knowledge test identities and compare outcomes;
   retain retrieval/citation/evidence/classification and read-only-query tests.
   Check prompt/tool availability effects explicitly; deterministic cases alone
   are not a guarantee about every stochastic model answer.
8. Run affected tests per stage and once at final source freeze run full pytest,
   Ruff check/format, mypy, build and pip check. Retain original failures and
   before/after evidence. No repeated full suites without new changes/failures.
9. Only after acceptance, prepare a new package with updated instructions;
   any resident restart first checks active work. Do not deploy during design.

## Review checkpoint

Self-review complete: owner policy is explicit, no temporary development flag,
no invented IT approval, no unscoped model-policy change, no fabricated thread
completion and no implication that an unavailable third-party protocol was
implemented. The recorded Skill-first evidence explains why harness work is
necessary. The scope and regression checks above are ready for the owner's
single explicit review/approval under AGENTS22 before implementation.
