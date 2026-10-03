# Architecture decisions

## 2026-10-02 — Incremental backend boundary before native Agent execution

Decision: Keep the existing Gateway as the sole task-capable backend in the
first slice. Introduce a typed backend profile and exact-selection router
around its conversation path. A Model backend uses the AEP harness and existing
Bridge policy; future native Agent backends own their internal loop and must
pass a separate data-policy and containment gate. Backend health describes
observed readiness, not execution permission. Selection never silently falls
back to another backend.

Reason: This preserves deterministic Workflow behavior and provides a small
regression boundary before changing data trust, CLI execution or completion
validation. Replacing Gateway and CLI paths together was rejected because it
would combine several security and migration risks. Web-only classification was
rejected because it would leave other ingresses unprotected.

## 2026-10-02 — Initial backend data rule

Decision: Unclassified data may use only a suitably approved internal Gateway.
Native Codex/Claude Code may receive a task only when the entire context sent
to them is explicitly classified `PUBLIC`. No Gateway outage or backend
availability change can weaken this rule. This is the owner's explicit choice;
implementation and denial tests belong to the next data-policy slice.

Reason: The existing local CLI text-chat path has no classification or
governed tool boundary. Treating it as a native AEP task backend would expose
unreviewed context and side effects. Pausing all unclassified work was
considered but rejected by the owner in favor of the approved internal Gateway.

## 2026-10-02 — Host-admin Gateway approval and PUBLIC session boundary

Decision: A host administrator must record the exact routed Gateway alias and
URL, approval reference, and accepted data classes in `models.data_approval`.
The host treats a complete model request as UNCLASSIFIED until field-level
source provenance exists. No approval means the provider transport is not
called. A localhost URL alone is not evidence of approval. This implements
the owner's explicit choice of host-admin approval over localhost inference.

The existing restricted external CLI text-chat path requires an explicitly
PUBLIC, empty conversation at selection time. It compares labels with every
message actually sent, omits local persona text and prevents slash commands
from bringing local data into the PUBLIC session. Existing conversation
history cannot be relabeled PUBLIC retroactively. A generic API that accepts
payload and classifications as unrelated arguments was rejected because a
caller could omit a material item while still sending it.

The alternative of trusting any configured/localhost Gateway was rejected:
LiteLLM may forward elsewhere, and a URL/credential cannot prove the upstream
data boundary. Retaining unrestricted CLI chat was rejected because signed-in
status does not classify the user's history or local persona.

## 2026-10-02 — Portable task state stores a digest, not task content

Decision: Keep the complete backend-neutral task objective in a caller-held
`TaskContract` and persist only its canonical SHA-256 digest with trace,
backend, state, observation codes, artifact references and validation metadata
in the local state store. Resumption requires the same contract. A separate
host-owned validator reads the actual artifact through a trusted resolver and
checks it against declared completion criteria; an Agent or model statement
cannot by itself mark the task complete. The SQLite change is an additive
version-5 table, leaving existing Workflow run/checkpoint semantics intact.

Reason: Copying prompts and source content into every durable run row would
expand the data exposure surface and mix task orchestration with conversation
storage. Treating a backend's success report as completion was rejected because
it would bypass the product requirement for observable independent evidence.
The initial validator is deliberately limited to artifact presence, non-empty
content and an optional known digest; richer domain validators belong to
later task adapters and product E2E cases.

## 2026-10-02 — Backend results are candidates and classification only rises

Decision: A normalized backend `completed` result moves a task only to
`awaiting_validation`. Its artifact references must be checked by the host's
independent validator before the task can be `validated`. The portable state
records backend use and effective classification; an increase requires an
evidence reference and cannot be silently lowered. Switching to another
backend is disabled until a fresh, complete-context policy decision and
explicit transition contract are implemented. `RESTRICTED` is recognized as
more sensitive than CONFIDENTIAL, but the current internal-Gateway approval
cannot include it without a separate approved restricted environment.

Reason: A native Agent's own success claim and history are not independent
evidence. Carrying a classification that can silently decrease would let
later backend selection expose newly discovered sensitive context. Allowing
`RESTRICTED` under an ordinary internal-Gateway flag was rejected because
that flag does not attest a restricted execution environment.

## 2026-10-02 — Approve this workstation's loopback LiteLLM route by default

Decision: The owner explicitly approved `http://127.0.0.1:4000/v1` through
alias `company` for UNCLASSIFIED Agent model requests on this workstation.
Record this as an exact `models.data_approval` in the editable installed
`host.json` and provide a credential-free Gateway configuration fragment in
`deploy/windows-preview/gateway-default.json`. Keep the existing strict match:
changing URL, alias, provider or credential clears the approval. Changing only
the model ID at that same route retains it. Other hosts do not inherit this
machine's approval merely because they use localhost.

Reason: The owner supplied the LiteLLM upstream configuration and explicitly
asked that the known route be usable for subsequent tests without an approval
dialog or repeat configuration step. The alternative of automatically trusting
every localhost URL remains rejected because a local proxy can forward to an
unreviewed destination.

## 2026-10-02 — Keep JEV behind an optional Decision Service

Decision: Introduce a provider-neutral, typed Decision Service at the
existing Agent routing decision. Its `NONE` default calls the established
rule-first/Gateway baseline directly and never constructs or probes JEV.
Configuration names only a provider, endpoint, `SecretRef`, timeout,
confidence threshold and explicitly enabled decision types; it stores no
credential value. An accelerator requires a trusted egress authorizer before
its provider is constructed. Provider error, missing provider, unsupported
output or low confidence returns to the baseline, with payload-free trace
evidence. Final execution routing, security classification, completion and
planning decisions cannot be enabled as accelerator-authoritative types.

Reason: JEV may shorten repeated bounded classification later, but this
repository has no JEV adapter, golden decision benchmark or approved JEV data
boundary yet. Wiring JEV directly into the Gateway loop or replacing the
strong-model path would make the baseline depend on an unavailable service
and could create an unreviewed data-egress path. The alternative of a separate
JEV Harness was rejected because decisions are orchestration inputs, not an
execution plane.

## 2026-10-02 — Keep conversation Skill acceleration to installed candidates

Decision: Route the ordinary Agent conversation's installed Skill command
catalog through `DecisionService` as a `skill_selection` decision. With `NONE`,
return the original full catalog in order. A future accelerated result may
only narrow it to a nonempty subset of installed names. Apply the same subset
to the model's visible tools and the Gateway's dispatch bindings. The complete
request, including user message and command descriptions, requires trusted
egress authorization before any provider is constructed or called.

Reason: Normal Web conversation uses `Gateway.converse`, not `RequestRouter`'s
one-shot route; without this boundary a JEV-ready decision contract would not
cover the primary Agent interaction. Accepting arbitrary accelerator tool
names or filtering only the display catalog was rejected because a model could
then trigger a hidden or uninstalled command. No JEV provider is enabled by
this decision.

## 2026-10-02 — Execute explicit tasks through the approved Gateway first

Decision: Add a Host-owned executor for an explicit `TaskContract` submitted by
`aep-host run-task`. The first task output is one local answer artifact. It
admits the actor and device, requires the exact host-approved internal Gateway
for UNCLASSIFIED task material, and exposes only task-scoped installed
read-only capability commands through the existing Bridge. A task with no
allowed capabilities is tool-free. The existing model-client check still
authorizes each complete provider request. Durable progress stores bounded
step and issue references without objective or answer text. The Host rereads
the answer bytes for independent completion validation. Ordinary Web chat,
Workflow routing, native task backends and backend switching are unchanged.

Reason: This creates a runnable checkpoint for the portable contracts while
retaining the already proven execution and policy boundaries. Automatically
converting every Web turn into a task was deferred because those turns include
slash commands and Workflows with different completion evidence. Enabling a
native backend or implicit fallback was rejected until complete transfer
materials can be classified and re-authorized at the new destination.

## 2026-10-02 — Resolve numeric Workflow commands from installed manifests

Decision: A Workflow manifest may declare one optional positive `run_alias`.
`/run 11` and `/run workflow 11` resolve that number within the Agent Web
session namespace only when exactly one local manifest matches. The resolved
exact identity still goes through resident-Agent admission and Bridge policy.
The shipped Workflow 11 assigns `11` only to its read-only preview; apply and
mail have no numeric shortcut. Missing or ambiguous aliases require an exact
`namespace/name@version`. Older manifests remain valid with no alias.

Reason: The source Workflow number is useful at the keyboard, but mapping a
number in the Web implementation or choosing the latest matching version
would make the UI decide which execution asset to run. The manifest-based
shortcut remains declarative and fails closed when installation is ambiguous.
The CLI now returns a nonzero exit status for failed, unavailable, unresolved
or unrecorded runs, so shell validation cannot mistake a rendered failure for
success.

## 2026-10-02 — Validate Knowledge locally and replace Workflow 7 Jira reads

Decision: First validate Knowledge against a small independent test Vault.
Leave the supplied `RS_Knowledge` tree unchanged, and select an explicit
queryable subset before any of its content is sent to a model. Workflow 7's
replacement source is the same GitHub Project used by Workflow 11, with a
read-only preview as the first executable stage. The owner will update the
Project read permission for the configured Host credential.

Reason: The supplied tree has `drop/raw/wiki` but lacks the platform Vault's
required root index and log, so treating it as already publishable would lose
provenance or fail exact digest checks. The source Workflow 7 uses retired Jira
and writes an Excel workbook; a read-only GitHub preview permits source field
mapping and parity inspection without assuming write approval.

## 2026-10-02 — Declare Workflow run fields in the installed manifest

Decision: Add optional typed parameter definitions to Workflow manifests and
render runtime fields in Agent Web. Validate a submitted run against the exact
installed manifest before passing it to the resident Agent; older manifests
keep their JSON object editor. Scope static fields separately so a run cannot
submit them. Weekly-report preview, apply and mail share the same runtime
request fields, while the `11` alias still selects only read-only preview.

Reason: A developer should be able to define a Workflow's input once and
obtain the basic controls without editing Agent Web for each Workflow. This
incremental contract preserves installed-only routing and Bridge policy.
The alternatives of accepting untyped browser values or persisting static
settings through run arguments were rejected: both blur the boundary between
one run's input and trusted machine configuration. Static persistence,
dynamic options and Telegram controls remain separate migration steps.

## 2026-10-02 — Adapt Workflow 7 as a separate GitHub read preview

Decision: Use `ADAPT` for source W3-07's managed record order, Task/Issues
routing and comment formatting. Replace retired Jira reads with the Host's
existing configured GitHub Project client and one read-only capability. Keep
the source Excel writer out of this first Workflow. Add Issue creation time
and author login to the common Project read shape; mark any still-unavailable
source fields and incomplete comment threads in the output.

Reason: The user selected the same GitHub Project as Workflow 11 and a
read-only first validation. Copying Jira JQL or the source writer would use a
retired system or enable unverified writes. Folding Workflow 7 into Workflow
11 was rejected because they answer different questions and have different
workbook contracts. A typed preview can be tested and rolled back on its own,
then compared with source fixtures before any Excel parity claim.

## 2026-10-03 — Render Workflow 11's weekly mail and workbook presentation from data

Decision: Keep the Outlook recipients in the local Host's `weekly_report`
configuration. Render the SDE weekly draft from counted Project items with
the approved subject, activity count, member split, instrument/account counts
and shares. For Excel, colour planned `Done`, `In Progress` and `New` Status
cells by value, align the Comments column top-left, and use Excel's native
cell-colour sort on the complete scratch-sheet row range after all writes.
Refuse a workbook Excel opens read-only.

Reason: The owner supplied the recipient list and reference draft, and asked
for status colours and highlighted Key rows first. Local recipients avoid
publishing a team-specific distribution list as a shared asset. A native
whole-row sort keeps hand-maintained Comments and other columns attached to
their Key. A prior pink fill meaning merely "new row" conflicted with the
requested New status; a row border continues to show first appearance.
Sorting just Key cells or treating a read-only Excel save as successful were
rejected because either can report a workbook that is wrong.

## 2026-10-03 — Require original-source behavior as the migration baseline

Decision: Apply the Source Workflow migration parity contract in
`docs/CONTRACTS.md` to all later `rs_workflow_system` migrations. Pin the
source files and revision or individual hashes, derive regression evidence
from the original behavior, and record approved AEP differences explicitly.

Reason: Workflow 11's first AEP port simplified a proven mail layout and
formatting. A successful AEP run therefore did not meet the owner's expected
output. Reimplementing from screenshots without a source comparison, or
treating a transport change as permission to change output, was rejected.

## 2026-10-03 — Keep the first Agent schedule slice as an inert local claim queue

Decision: Model daily/weekly local-time recurrence and exact installed
Workflow/Agent Task targets as provider-neutral contracts. Persist definitions,
due claims and outcomes in a separate Bridge-bound SQLite file. Claiming
advances the next due time atomically and retains a stable key for later
reconciliation. A paused schedule skips missed occurrences. Add the PSF's
Apache-2.0 `tzdata` package for IANA timezone rules on Windows.

Reason: The existing resident Agent and Bridge already own admission and
effect approval. A timer that directly invokes a capability would bypass that
boundary, and placing pending claims into the existing run database would
make a separate feature change its schema and recovery semantics. An n8n-only
schedule was rejected because optional n8n cannot be required for local work.
Automatic replay of a claimed but unfinished job was rejected until a worker
can reconcile its actual outcome with the run ledger.

## 2026-10-03 — Restore company Jira as Workflow 7's source

Decision: Workflow 7's first AEP slice is a read-only preview of the original
company Jira project through the Host's Jira client and `AEP_JIRA_TOKEN`
reference. Workflow 11 alone uses the GitHub Project. Keep Workflow 7's source
JQL, managed columns, ticket routing and bounded comment reads as the
behavioral baseline; Excel writes remain a separate parity slice.

Reason: The owner clarified that Jira remains available at
`https://jira.rsint.net/` for Workflow 7. The earlier GitHub substitution
changed this Workflow's data source and could not establish source parity.
The GitHub preview asset was superseded rather than promoted to a default.

## 2026-10-03 — Preserve record visibility through Workflow 11's Excel sort

Decision: Sort the entire weekly scratch sheet by the Key cell's highlight,
including manually hidden records. Carry a temporary row identifier in an
unused column, temporarily reveal rows, sort complete rows, then restore each
record's hidden state and remove the helper column. Keep the existing
AutoFilter range. Refuse an active filter before changing the sheet because
its applied criteria cannot be restored reliably by this adapter.

Reason: Excel's ordinary cell-colour sort left three highlighted records below
hidden rows in the owner's workbook while reporting success. Sorting visible
rows alone was rejected because it broke the requested highlighted-Key order;
leaving all rows visible was rejected because it changed the owner's view.
The copy-based Excel check preserved the hidden-record multiset and filter
range, and the installed Workflow's saved workbook placed all 22 highlighted
rows contiguously at the top.

## 2026-10-03 — Keep scheduled execution explicit until authorization is wired

Decision: A Schedule worker must receive a trusted authorization decision for
each due occurrence and execute only exact installed targets through the
resident Agent and Bridge. Do not start it from Host construction. An
unresolved claim blocks later occurrences of that schedule; an ambiguous
dispatch is never automatically replayed across process restarts.

Reason: A saved recurrence is not permission to execute a future write or
external effect, and an interrupted worker cannot assume that no effect
happened. Direct timer-to-capability execution and automatic replay were
rejected because they could bypass existing approval or duplicate effects.
Host lifecycle, authorization configuration and an operator reconciliation
surface are required before enabling unattended scheduled jobs.

## 2026-10-03 — Reserve Raw evidence facets for broad Knowledge questions

Decision: The Agent's installed Knowledge question capability may opt in to a
bounded bilingual retrieval mode for broad market/product questions. It
reserves Raw market and distinct Raw product/option candidates before filling
remaining slots by the existing lexical ranking. Narrow questions retain the
established order. This selection never grants an answer: every final claim
must still cite exact Raw evidence, and failed grounding is refused.

Reason: In the owner-authorized Vault, generic Chinese market passages
crowded out English product specifications for the exact mixed-language
question. Adding product names or answer mappings to the ranker was rejected
because retrieval must remain source-driven. A live repeated query still
showed model-format variability, so a candidate-set improvement alone is not
accepted as proof of reliable answer quality.

## 2026-10-03 — Correct Raw citation drafts once and narrow long evidence

Decision: For the installed Raw-grounded Knowledge route, detect a cited
draft that violates Raw-only or per-sentence citation rules and retry once
with the same numbered Raw passages. Never feed the rejected answer back or
relax final `KnowledgeAnswerRecord` validation. For broad evidence-coverage
questions, show the model the most relevant consecutive five-line excerpt
from each long retrieved Raw section while retaining its source citation.
Reject an option-code claim with uppercase technical acronyms unless at least
one cited excerpt contains the code and those acronyms together.

Reason: The model sometimes produced an otherwise useful answer with an
invalid citation format. The owner's SMBV specification also had a 40-line
section in which the B81 RF-output option and high-speed USB input appeared
far apart; citing that whole section allowed a false B81/high-speed link.
Using Wiki as substitute evidence, silently fixing a citation, or claiming
that lexical overlap proves general semantic entailment were rejected. The
source Vault remains unchanged, and broad answer quality still requires
source-backed evaluation.

## 2026-10-03 — Stage Workflow 10 writes and defer Workflow 13 release effects

Decision: Migrate Workflows 10 and 13 against the pinned original
`rs_workflow_system` revision, preserving source transformation and packaging
rules through typed local capabilities. Workflow 10 previews before it writes,
requires a separate approved `excel.write` step, edits a staged workbook copy,
and checks the managed and other sheets and VBA bytes before copyback. The
source-diff baseline advances only after verified copyback. Workflow 13 first
exposes a read-only preview and an explicitly isolated preparation path; Git
commit, push, published-version lookup, upload transfer and production release
remain separate governed work.

Reason: The source scripts interleave deterministic rules with local file and
release side effects. A direct script launch from chat would bypass AEP's
Bridge admission and approval boundaries. A broad rewrite was rejected because
the owner's explicit migration contract makes the original output the baseline.
The safe slices can be tested with synthetic files, while real Workflow 10
Excel parity requires the team's source workbooks and mapping rules and full
Workflow 13 parity requires controlled release dependencies.

## 2026-10-03 — Reuse proven Workflow jobs behind a thin Bridge adapter

Decision: For the next `rs_workflow_system` migrations, treat its pinned Python
jobs and PowerShell helpers as the implementation baseline and first assess
`REUSE` or `WRAP`. Keep their deterministic business logic intact where it can
run in AEP, exposing its existing static/runtime parameters through the
platform Workflow form and a thin typed Bridge entry point. Port or rewrite a
piece only when a concrete incompatibility or failed parity case is recorded.
The source n8n JSON may be read only as historical evidence for triggers and
parameter defaults. n8n development is outside the current owner-approved
scope; do not add a parallel n8n implementation or schedule it as required work.

For owner-authorized local effects such as writing the configured weekly Excel
workbook or saving an Outlook draft, install the exact persistent Host grant
and effect policy for that capability, then run through it without repeatedly
asking the owner to authorize the same operation. Saving a draft and sending a
message are different effects; a draft grant never authorizes send. The
existing Workflow 11 `outlook.draft` grant and successful unsent Drafts
read-back are the precedent. Remote release/push and other effects not yet
authorized retain their separate policy.

Reason: The owner reported that reconstructing already validated jobs and
overly narrow approvals delayed working Workflow parity. `WRAP` keeps source
behavior testable while preserving AEP's member/device admission and Bridge
boundary. A direct chat-launched script was rejected because it would skip
that boundary; a broad reimplementation and n8n integration were
rejected because neither improves fidelity to the proven jobs.

## 2026-10-03 — Benchmark TypeSafe JEV with PUBLIC data before live Agent wiring

Decision: Use the official TypeSafe SystemOne choice API for the first optional
JEV decision adapter, initially limited to `skill_selection`. The owner chose
PUBLIC-only content. Keep `NONE` as the default; construct the provider only
after a trusted caller authorizes the complete request, including system and
persona text, conversation history and installed tool descriptions. A
high-confidence result may narrow to one installed command; uncertain,
invalid, refused or failed responses retain the baseline installed catalog.
The 16-case PUBLIC synthetic benchmark and offline transport tests precede
Host wiring. The normal UNCLASSIFIED Gateway route stays on the approved
internal LiteLLM endpoint.

Reason: The TypeSafe [OpenAPI schema](https://api.typesafe.ai/openapi.json)
specifies `POST /v1/systemone`, Bearer authentication, named questions and a
choice answer with confidence. A conceptual `DecisionResult` is not the wire
contract. Sending UNCLASSIFIED Agent context to this external endpoint or
turning a selector into an authorization decision was rejected. Live use still
requires exact-endpoint egress approval, PUBLIC provenance for every outbound
material, an operator credential, circuit breaker and repeated benchmark
evidence.

## 2026-10-03 — Resolve an explicitly named installed Knowledge source before model tool selection

Decision: In an Agent Web Gateway conversation, an unambiguous mention of one
installed Knowledge asset name resolves to that exact asset version. The Host
then invokes the existing `knowledge-query/ask@1.0.0` capability through the
Agent and Bridge, including its actor grant, Raw-only grounding and internal
Gateway model route. The conversation displays the answer's numbered Raw
source references and a specific failure code when the query fails. `/wiki-query`
uses the same reply path. General requests without an explicit installed
source continue through the bounded model tool loop; PUBLIC external-backend
conversations do not gain Knowledge access.

Reason: The model-facing generic command schema does not carry the required
exact `KnowledgeQueryRequest(asset, question)` arguments reliably. The owner's
natural-language `RS_Knowledge` request could therefore fail before querying
the installed Vault even though direct Knowledge asking worked. Explicitly
named local sources are deterministic input, so resolving them before intent
selection removes that failure without granting new capability authority or
sending RS Knowledge to the external JEV service. Arbitrary fuzzy source
matching and a second ungoverned Vault reader were rejected.

## 2026-10-03 — Let the owner set privacy per Knowledge Vault

Decision: Each exact Host Knowledge binding has one editable `privacy` field,
either `private` (the default for old configurations) or `public`. The owner
declared the complete current RS_Knowledge Vault public and its installed
binding is set to `public`. That supersedes the earlier RS_Knowledge-specific
prohibition on TypeSafe use. The owner may change this setting for any Vault
in `host.json`; no separate classifier identity or multi-level label is
required for this setting.

Reason: The owner decides which Vaults are private or public. A small per-Vault
setting expresses that decision without treating all local Knowledge as one
class or adding an approval workflow to edit it. The existing TypeSafe JEV
adapter is a decision selector, not a Knowledge answer model, so this privacy
setting alone does not create a new JEV query path.

## 2026-10-03 — Make conversation history limits explicit and local

Decision: Store Agent Web context controls in a host-local
`conversation-context.json`, separate from the model catalog's declared
context capacity. Ordinary Gateway and restricted local CLI chat use the same
recent-message and UTF-8 history-text budgets, effective on the next turn.
The current question must fit in full or return `needs_input`; prior messages
are taken as a contiguous recent tail. Saved session transcripts retain up to
100 messages and can be explicitly deleted by their owner. Knowledge Ask and
deterministic commands keep their own routing. This slice adds no cross-session
memory or automatic summary.

Reason: The catalog's 128k context declaration was a routing capability, not
a control over what Web sent to the model. The previous hard-coded 12-message
window hid that distinction. A conservative text budget works with the
provider-neutral model contract without adding a tokenizer dependency, while
retaining local session evidence. A global learned-memory store was deferred
at the owner's request; changing the model's declared capacity alone was
rejected because it cannot bound or expand the active transcript.

## 2026-10-03 — Audit market-fit claims against pinned Raw evidence

Decision: Keep the RS_Knowledge high-speed-market evaluation separate from
runtime authorization. Pin the three reviewed Raw files by hash and excerpt:
one market-demand note and two product specifications. The diagnostic reports
source integrity, retrieval coverage and unsupported affirmative links from
a named product or option to a specific market rate. It always retains a
human semantic-review requirement. For broad Raw-only market questions,
Knowledge synthesis now explicitly distinguishes directly stated technical
capabilities from market suitability. A narrow guard retries and then refuses
an affirmative product-to-rate claim when its cited Raw excerpt does not name
both; it does not claim general semantic entailment.

Reason: A real Agent Web answer cited the correct Raw documents but inferred
CMX-B200A/SMBV100B applicability to 800G/1.6T from separate interface and
market notes. Citation validity alone did not establish that relationship.
Hard-coding R&S product assertions into the general retriever or treating a
JEV Skill selector as an answer validator were rejected. The pinned evidence
and regression make the observed failure reproducible without sending Vault
content to TypeSafe.

## 2026-10-03 — Compare local Laya before any JEV accelerator activation

Decision: Use `NandhaKishorM/laya` 0.3.24, the local typed-decision model, for
the next offline decision comparison instead of calling TypeSafe. Pin the
existing PUBLIC synthetic 16-case corpus and map all four decision types to
Laya `choice` questions. Keep Laya in a separately installed diagnostic
environment, with the checkpoint cached before measured runs and Hugging Face
offline mode enforced during measurement. Record its package version and
checkpoint revision, warm-up time and aggregate scoring. Neither Laya nor
TypeSafe is enabled in Agent Web by this decision.

Reason: Laya offers the same System One decision shape while avoiding a new
external egress path for the owner's first comparison. The similarly named
`aayushch/laya` is a notification application and was rejected for this
purpose. The current Host has about 2 GiB free RAM under load, so preparing
the test here and measuring the 421-million-parameter checkpoint on another
computer avoids a misleading latency result. Treating synthetic-case accuracy
as production authorization or replacing the deterministic baseline was
rejected.

## 2026-10-03 — Restore Workflow 11's source-style composite mail chart

Decision: Adapt the pinned `rs_workflow_system` Workflow 11 renderer at the
mail-chart boundary. Generate its instrument pie and stacked per-member bars
as one headless Matplotlib image from AEP's tested Issue-assignee and Project
Production series. Ship the plotting stack in an optional `weekly-mail` extra
and the Windows offline preview bundle. Continue all Production names through
the sequential blue palette instead of folding minor names into `Other`, as
the owner requested. Use GitHub Issue assignees for both mail statistics and
the workbook Assignee cell, and the Issue URL for the workbook Key hyperlink.

Reason: The AEP-only stdlib pie plus HTML bars was valid data but visibly
different from the owner's already-tuned original draft. A thin renderer
adapter preserves the source's presentation without replacing AEP's governed
Outlook draft and Excel contracts. Keeping the plotting dependency optional
limits its footprint to hosts that generate this mail. Copying the entire
source job or rewriting its chart from screenshots would either bypass the
Bridge boundary or lose the original as a regression baseline.
