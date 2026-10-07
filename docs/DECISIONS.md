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

## 2026-10-04 — Keep the product/market matrix as read-only evidence discovery

Decision: Add a distinct, exact-grant Bridge capability for the owner's five
R&S product families by five target markets. Scan the current Raw passages in
one installed Knowledge Vault, recording nearby mentions, separate passages
and gaps with immutable source references. Agent Web detects a matrix request
deterministically and invokes this capability; an installed Skill explains how
to move from the overview into grounded single-cell investigation. The first
matrix makes no verified product/option-to-market claim and needs no model.

Reason: The earlier generic Knowledge answer over eight retrieved passages
joined separate technical and market facts into an unsupported fit claim.
Using a separate output contract preserves the existing cited-answer contract
and Bridge policy. Hard-coding 25 recommendations, treating lexical matches
as proof, and creating a separate per-market workflow were rejected. The
owner chose an evidence-and-gap overview before deep recommendations.

## 2026-10-04 — Render Ask Markdown with local, safe DOM construction

Decision: Keep Agent and Knowledge replies as plain text in the API and
conversation store. In Agent Web, render the common Markdown subset used by
answers—headings, paragraphs, lists, fenced and inline code, links and tables—
using explicit browser DOM elements and text nodes. Do not assign model output
to `innerHTML` or fetch a renderer from a CDN. Permit only absolute HTTP(S)
and mailto links; show raw HTML and disallowed links as text. Apply the same
renderer to new turns and saved-session history.

Reason: The offline Windows preview cannot depend on a CDN, and untrusted model
output must not become executable HTML. The initial 25-cell matrix was legible
as source Markdown but not as a user-facing table. A local DOM renderer fixes
that presentation without changing Bridge evidence or conversation storage.

## 2026-10-04 — Make evidence sufficiency explicit before expanding Agent routing

Decision: Improve the six-layer harness in the order recorded in
`docs/phases/HARNESS_6_LAYER_INCREMENTAL.md`. First, assess an exact selected
product/market matrix cell with a typed `needs_evidence` result and three
machine-readable missing facets. Existing matrix mentions remain discovery
evidence only. Bounded re-retrieval and independent claim validation must
precede any route that labels a product recommendation complete. Keep known
commands deterministic and all execution behind existing Bridge grants.

Reason: The matrix currently finds useful leads, but neither a nearby mention
nor separate product and market passages proves an application, option or
customer fit. A generic classifier or larger model prompt would not close
that evidence gap and could make unsupported recommendations look confident.
The typed gap result is reversible and can drive later retrieval and Web
feedback without adding model calls or bypassing policy.

## 2026-10-04 — Keep the six-layer harness cross-domain and Skill-guided

Decision: Treat the selected Knowledge matrix assessment above as an adapter
pilot, not the core harness. Add a provider-neutral plan envelope built from
the existing TaskContract and optional Skill guidance. It covers Workflow/Task,
Knowledge and Coding, preserving Host completion checks and the Task's exact
capability scope. A Skill declares evidence needs, context need and fallback
guidance, but cannot grant execution or validate its own output. The candidate
Knowledge Asking Skill is a new version; the published 1.0.0 asset is unchanged.

Reason: A Knowledge-only loop would overfit one domain and diverge from the
existing Workflow and Coding execution paths. The owner wants to test Knowledge
first, diagnose failures by process/Skill/data coverage, and keep the shared
runtime applicable to all three. The Knowledge adapter only translates
retrieval and Raw citations into common observations; the Skill owns the
question-answering procedure and the Host owns final acceptance.

## 2026-10-04 — Keep shared harness progress payload-free and bounded

Decision: The shared run state records only typed phase transitions and
references to observed context, execution and Host check evidence. It cannot
reach `validated` without every declared Host check passing. A failed check
routes to the Skill-guided fallback, with retry capped by the Task budget;
exhaustion stops. Domain adapters will feed this state but do not replace their
existing deterministic executors or validators.

Reason: Storing model prose or raw enterprise material in a generic run log
would widen data exposure and make later cross-domain reuse harder. A pure
state contract can be tested across Knowledge, Workflow and Coding before
binding any side-effecting capability. The alternative of building a separate
Knowledge-only loop was rejected after the owner's clarification.

## 2026-10-04 — Add an opt-in Knowledge Web path to the shared harness

Decision: Permit a browser Knowledge question to select one exact installed,
validated or published Knowledge Asking Skill. The Host builds a shared Task
plan and runs the existing exact Bridge Knowledge capability through the
provider-neutral runner. The Knowledge adapter only maps the Bridge result to
a Raw-grounding check. The Web explicitly reports that evidence facets remain
unassessed. Existing Knowledge questions without an explicit Skill keep their
current path until the candidate procedure and missing-facet checks are proven.

Reason: This provides an inspectable end-to-end Web slice without mutating the
published 1.0.0 Skill or weakening Bridge permissions. Automatically claiming
that Raw citations prove product/market recommendations, or silently routing
all existing questions through an unfinished candidate Skill, was rejected.

## 2026-10-04 — Enable live Knowledge Asking through the one installed candidate

Decision: For a natural Agent Web question that names an installed Knowledge
asset, select the Knowledge Asking harness Skill only when exactly one installed
Skill is eligible. Keep the existing route for zero or multiple candidates and
preserve Bridge authorization and Host Raw-citation validation. The Web exposes
the harness phase and states that evidence facets are not yet assessed.

Reason: The owner needs to test the shared harness in the real Agent Web before
the next analysis cycle. Automatic selection is unambiguous in the current
single-candidate Host, while silently choosing among multiple Skills would
hide a routing decision. The alternative of leaving natural chat on the legacy
path would make the new harness invisible to the owner's normal Ask workflow.

Knowledge retrieval now treats an explicitly named Raw filename as a strong
source hint and prioritizes Raw passages for a product code in the question.
A narrow Chinese test-term expansion finds English test material; it adds no
answer facts. These are deterministic retrieval changes inside Knowledge, not
shared harness rules. A model-generated search rewrite was deferred until a
bounded Skill-driven retrieval policy and evaluation cases can govern it.

## 2026-10-04 — Let the Knowledge Skill guide facet retrieval without specializing the shared runner

Decision: Add an optional opaque `procedure` to Skill manifests. The private
Knowledge Asking Skill 1.2.0 uses it to declare natural intent, requested
facets, bounded search queries and direct-link terms. Only the Knowledge
adapter interprets this procedure. The common plan, runner and Bridge grants
remain domain-neutral. The Host independently requires cited Raw support for
every requested facet, a connected direct relationship for combined questions
and a conservative lexical claim/source check. Missing support yields an
explicit gap, not a recommendation. Deterministic commands retain routing
precedence.

Reason: The previous Skill instructions had no executable retrieval plan, so
the harness accepted a Raw-cited answer without checking whether all requested
market, product, technical and competitor facets were supported. Putting
facet rules in the common runner would break its Workflow/Task and Coding use.
The rejected alternative was to treat multiple nearby Raw passages or a model
claim as proof of product-market fit. Lexical overlap is a limited preflight,
not semantic entailment; source and recommendation review remain necessary.

## 2026-10-04 — Navigate the owner's LLM Wiki before checking Raw evidence

Decision: The private Knowledge Skill candidate 1.3.0 opts into an
`index.md → Wiki page → linked source page → Raw` retrieval path. The Wiki
provides query context and source discovery; the existing Host still checks
immutable Raw citations for factual acceptance. Keep this Knowledge-specific
path inside the Knowledge adapter, leaving the common Workflow/Knowledge/Coding
harness unchanged. If an index entry or source link is unavailable, supplement
with the existing global retrieval rather than treating the Wiki as complete.

Reason: The owner's `RS_Knowledge/CLAUDE.md` and `ask-market` / `ask-competitor`
Skills explicitly say to orient with `index.md`, read relevant entity, concept,
synthesis and source pages, match model/option identifiers exactly, and trace
claims to sources. The 1.2.0 candidate searched Raw sections directly and
therefore missed that curated navigation. Raw-only lexical gates can reject a
useful partial answer or accept a marketing co-mention, so page discovery and
final answer quality must be evaluated separately. The rejected alternative
was to move Wiki rules into the shared harness or treat a Wiki summary alone
as verified source evidence.

## 2026-10-04 — Adapt the proven Hermes Knowledge procedure, keep answer acceptance separate

Decision: Use the owner's `rs-knowledge-base` Skill as a behavioral reference
for the private Knowledge candidate: orient through the Vault schema and index,
search Wiki and Raw bilingually, distinguish market demand, technical need and
product/options, and label facts, inference and gaps. The separate
`html-report-delivery` Skill governs a browser-viewable artifact when a report
is requested; it does not alter retrieval or answer validation. Adapt these
behaviors inside the Knowledge Skill and adapter, not the shared harness or a
copied Hermes runtime. Keep the configured Vault path rather than hardcoding
the personal path in the reference Skill.

Reason: The user's downloaded Skill files were byte-identical to the local
Hermes installation. AEP's fixed top-k filtering excluded existing valid Raw
sources; pooling all Wiki-linked Raw let one product dominate an open-ended
question; an oversized Raw section then consumed the model context. Focused
fixes now rank eligible Raw across the loaded corpus, retain one eligible
section per indexed source, preserve multiple discovery queries and bound the
text sent to the model. These improve discovery but do not make a sales
recommendation true. In isolated NTN probes the current Host still accepted
an answer that treated a target-market mention as a recommendation and
contained citation-only or clipped fragments. Therefore the candidate remains
undeployed pending source-aware recommendation and artifact validation. The
rejected alternative was to treat a passing lexical citation gate as evidence
of product/customer fit.

## 2026-10-04 — Preserve cited partial Knowledge facts without declaring the question complete

Decision: The candidate Knowledge Skill may return independently supported
facts when a requested facet or direct relationship remains unverified. The
Knowledge adapter removes unsupported recommendation lines, keeps only cited
claims that pass the Raw overlap check, and redacts credential-like strings in
retrieved passages before they enter an answer record. The Host reports a
`needs_input` harness phase with the exact missing facets and source paths;
it does not upgrade a partial answer to a complete comparison. The older
installed Skill path retains its current behavior during this candidate test.

Reason: The Hermes reference Skill distinguishes fact, inference and gap. The
earlier AEP candidate discarded every supported fact when one facet was
missing, while a broad `Target Markets: NTN` list could validate an unrelated
product recommendation. Live probes also showed that a sample `Bearer` phrase
in Raw triggered answer-record secret detection and that `Rel. 17` was split
into a misleading fragment. The rejected alternatives were to disable secret
checks, accept market-list co-mentions as product fit, or mark partial evidence
as a validated direct relationship.

## 2026-10-04 — Diversify product evidence before accepting open-ended market recommendations

Decision: For a Skill's open-ended product facet, rank eligible Raw passages
across the corpus, keep distinct instrument families within the bounded
evidence set, and prefer technical/product documents before press releases.
This selection remains inside the Knowledge adapter and retains each Raw
section's original citation. It does not claim that every product named in a
market document is suitable for a particular customer.

Reason: The real NTN question found a signal-generator slide, but several
CMX500 documents occupied the final evidence slots. Merely adding more search
queries did not bring the independent NTN whitepaper into the result, so that
trial was reverted. Source/family diversity did bring the whitepaper into the
real-Vault evidence set. The model or extractive fallback still returned only
a narrow CMX500 answer, so answer-quality acceptance remains open and the
candidate is not deployed. The rejected alternative was to increase the
context budget without controlling duplicate product and promotional sources.

## 2026-10-04 — Let the Knowledge Skill set synthesis output budget and preserve adjacent Raw citations

Decision: Add a bounded `synthesis_max_output_tokens` field to the Knowledge
procedure, defaulting to the prior 800-token behavior; private candidate 1.3.0
uses 3072. The Knowledge adapter may read adjacent Raw sections around a short
selected hit, retaining each section's own citation. These changes do not
alter the shared harness or grant new execution permissions. The adjacent
section step remains a candidate until real-Vault verification is complete.

Reason: The approved internal Gateway returned two successful but empty visible
responses for an 800-token NTN synthesis request. At 3072, the same isolated
question produced a substantial Chinese answer with Raw citations. Separately,
some PDF Raw sources split an option sentence across sections (`accord-` /
`ing`); sending only the matched section made both synthesis and citation
checking lose the rest of the claim. The rejected alternatives were to treat
the one-sentence extractive fallback as a good answer, disable citation checks,
or merge neighboring section text under one misleading citation.

## 2026-10-04 — Keep the richer grounded Knowledge draft and judge claims by cited source identity

Decision: In the Knowledge adapter, a second synthesis attempt no longer
replaces a first draft that retains more Raw-grounded sentences; sentence
splitting keeps list markers and grouped citations with their claim; a
subject check accepts a claim cited from a Raw document named for the subject;
a Skill focus check accepts a Raw document named for the focus when the cited
section names the product in a concrete test role; and stated numbers are
extracted with ASCII-only boundaries so CJK neighbors do not hide them. The
Skill candidate (not the harness) pools all market-trend queries. The shared
harness, Bridge grants and Raw citation contract are unchanged.

Reason: Real-Vault probes showed the model's first draft was often the most
complete and correctly cited, but formatting artifacts (`1.`, `。[5][7]`, an
uncited conclusion) or CJK-adjacent numbers failed it, and the retry was a
fresh, thinner generation. Option statements in CMP180's own feature and
specification documents omit "CMP180", which pushed a good answer into the
clipped extractive fallback. The rejected alternatives were to drop per-
sentence citation checks, to allow uncited conclusions into the record, or
to treat any document mentioning the focus anywhere as product-fit evidence.

## 2026-10-04 — Do not use n8n for scheduled tasks

Decision: Scheduled/recurring tasks use the existing native schedule store and
worker, triggered by a CLI tick (for Windows Task Scheduler) and/or an opt-in
Host-resident loop. n8n is not a scheduling dependency.

Reason: The owner finds deploying n8n on company PCs too burdensome, and the
architecture already treats n8n as optional. The rejected alternative was an
n8n-hosted schedule, which also conflicts with the 2026-10-03 decision that a
schedule must not exist only in n8n.

## 2026-10-04 — Allow bounded, labeled Knowledge inferences

Decision: A Knowledge Skill may opt into an `inference_label`. Lines carrying
that label are presented as inferences, not facts: they must cite the Raw
premises they connect, may not introduce product codes or numbers absent from
those premises, are limited to three, and survive only beside a supported
fact. The Host checks them with the same rule but never counts them toward
facet coverage or a direct relationship, so a missing link is still reported.

Reason: The owner wants the Hermes-style separation of fact, inference and
gap, with explicit labels. Without it, users saw cited market and option facts
but no stated connection, or the model blended a connection into factual
prose. The rejected alternatives were to keep inference out entirely, to let
an inference satisfy the direct-relationship check, or to accept unlabeled
cross-source conclusions.

## 2026-10-05 — Make the curated Wiki the primary Knowledge answer source

Decision: A Knowledge Skill may opt into the `wiki_primary` citation policy.
Under it, curated Wiki entity, concept, synthesis and source pages are cited
directly as answer evidence; Raw is cited where the Wiki does not cover a
claim. Every cited Wiki page carries a `WikiProvenance` entry listing the Raw
sources it was curated from (followed through the Wiki sources page's
`source_id` / `source_path`). A page with no traceable source stays citable
and is reported as unlinked for data experts to repair. `index.md` is
navigation, never evidence. The `raw_only` policy remains the default for
existing Skills. Wiki/Raw inconsistencies are resolved by data experts during
ingest; the answer layer does not override Wiki with Raw. Product acceptance
E2E-05 criterion 1 was amended accordingly with the owner's approval.

Reason: The owner's Vault is an LLM Wiki whose purpose is to curate Raw into
dense, navigable pages; forcing every answer back to Raw sections discarded
that work, limited breadth (one Wiki page summarizes dozens of Raw sections)
and fragmented answers. On the real Vault 2004 of 2007 Wiki pages trace to
Raw, so provenance survives. AGENTS.md requires that Raw remain immutable and
that the curation layer never be the only copy of source evidence; both still
hold. This supersedes the 2026-10-03 rejection of "using Wiki as substitute
evidence", which addressed whole-section citation errors now handled by
section-level Wiki chunks and per-claim checks. Rejected alternatives: keep
Raw-only citation; cite Wiki without provenance; flag runtime Wiki/Raw
mismatches in answers (owner assigns conflict resolution to ingest).

## 2026-10-04 — Scheduled tasks v1: separate grants, effect-tiered unattended runs

Decision: Implement the owner's scheduled-task decisions on the existing
native store and worker (contract details in `docs/CONTRACTS.md`,
"Scheduled tasks v1"):

1. Unattended execution needs a Host-owned `ScheduleExecutionGrant` that the
   owner creates through the CLI or Agent Web. It names the schedule's exact
   target and a maximum effect class and may expire. `read` targets run
   unattended with it. `write`/`execute` targets also need the Bridge's exact
   durable `CapabilityGrant` for every capability they reach. An
   `external_side_effect` target never runs unattended: each occurrence waits
   as `awaiting_approval` for an approve/deny decision, and the worker
   enforces this whatever authorizer it is given.
2. Workflows and Agent Tasks are both targets. Because there is no Registry
   kind or installer for Agent Tasks, v1 reads exact owner-installed
   `AgentTaskTemplate` files from `assets/agent-tasks/` and runs them through
   `LocalAgent.run_task`, the path `aep-host run-task` uses. Templates take
   no runtime inputs yet.
3. The trigger is an opt-in `ScheduleLoop` inside the long-running
   `aep-host web` process (`--schedules` or `schedules.resident_loop`), plus
   `aep-host schedules tick` for Windows Task Scheduler and recovery, and
   `aep-host schedules run` for a host without a page. Each poll holds Agent
   Web's one-request-at-a-time lock.
4. After downtime, only the latest due occurrence is claimed, and only if it
   is within `schedules.catch_up_hours` (default 24); otherwise it is
   recorded as `schedule_missed`. Uncertain claims still block and are
   never replayed. An operator records a resolution (outcome, who, when,
   note) that dispatches nothing.
5. The store moves to schema version 2 with in-place migration and a
   five-second busy wait.

Reason: A saved recurrence is not permission (2026-10-03). Tying the grant to
the exact target and an effect ceiling lets a read report run unattended
while keeping writes behind the Bridge's own durable grant and every send
behind a person, as the owner required. The Bridge/Host process is where
deterministic execution near resources already happens, so the loop lives
there rather than in a separate service. Approval reopens the occurrence as
a claim before dispatch, so a crash during an approved send is blocked for
resolution rather than repeated.

Rejected alternatives: n8n or another external scheduler as the source of
truth (owner decision; optional dependency). Treating a schedule's creation,
or a published asset's approval metadata, as execution permission. Allowing
an `external_side_effect` grant to auto-send. Replaying every missed
occurrence after downtime (a backlog flood) or none at all (silently losing
the weekly run). Starting the loop whenever a Host is built, which would make
every CLI command a scheduler. Letting a model choose a scheduled target or
fill Agent Task inputs. Adding a Registry asset kind for Agent Tasks inside
this slice; that is a separate platform contract change.

## 2026-10-05 — Run Agent Web sessions concurrently; keep effects serialized at the Bridge

Decision: Agent Web no longer serializes every request on one process lock.
Conversation turns take a per-session turn lock (a session's turns run in
order; the page queues them and keeps the input usable), and a short
per-session record lock guards read-modify-write of the stored record, so a
rating, backend switch or deletion during a running turn is preserved.
Knowledge asking, external backends and Gateway conversation run in parallel
across sessions. Commands that may run workflows, settings, synchronization,
profile activation and scheduled runs still take the exclusive lock. The
Bridge holds a reentrant `BridgeExecutor.exclusive` lock around every
workflow run and every non-read capability call, so whichever path starts
them (chat tool, command, schedule), two effects never act on the same
workbook or draft at once.

Reason: The owner needs several sessions and a second message while one is
working; a single global lock made a 1-2 minute Knowledge answer block every
other session and session management. The original reason for the lock — one
state file and one workbook — is addressed narrowly: the SQLite state store
already serializes its own reads and writes, and effects are serialized
where the architecture puts resource access (the Bridge). The workflow
engine's run table is tied to one event loop, which is why workflow runs are
serialized too. Rejected alternatives: run turns of one session in parallel
(scrambles conversation history, owner rejected); remove the lock entirely
(concurrent workbook writes); keep conversation turns under the exclusive
lock (does not meet the multi-session requirement).

## 2026-10-05 — rs_workflow_system migration decisions and one parameter declaration

Decision: Migrate every rs_workflow_system workflow/job per
`docs/phases/RS_WORKFLOW_MIGRATION.md`. Owner decisions: (1) Telegram runs of
`write` / `external_side_effect` workflows require a per-run approval tap;
(2) credentials are configured in the install path's `host.json` as SecretRef
-> environment-variable mappings (values stay in the environment, never in
the file or an asset); (3) published reference sets (`ref:`) live in the
local SQLite store; (4) "occupies the machine" is a manifest field
(`occupies_machine`); (5) customer-facing loan replies stay drafts and are
never sent unattended. `WorkflowParameter` is extended in place with optional
fields (`default`, `help`, `examples`, `order`, `group`, `pattern`,
`min_length`, labelled `choices`, `choices_source` `ref:`/`fn:` with
`{field}` placeholders, `needs`, `multiple`, `accept`, `channels`, `confirm`;
kinds `number`, `text_list`, `emails`, `file`, `folder`, `upload`) and
`WorkflowManifest` gains `progress_steps` and `occupies_machine`. Fields that
are unused serialize as before, so published manifests keep their bytes and
digests.

Reason: The source's `PARAMS_SCHEMA` + `x-ui` is what lets one declaration
drive the dashboard form and Telegram flow; AEP needs the same expressiveness
before generators can replace the hand-written forms. Interpretation of (2):
storing token values in `host.json` would contradict AGENTS.md rule 17 and
the owner's security baseline, so the file holds the mapping only; the owner
can revisit this. Rejected alternatives: a new contract version (breaks
existing manifests), embedding raw JSON Schema (loses the closed, validated
field set), keeping per-workflow settings in `HostIntegrations` (requires
core changes per workflow).

## 2026-10-05 — Per-install Workflow settings live in the workspace, merged by the engine

Decision: A Workflow's pre-run settings (`scope: static`; for example where
its reference data lives) are stored in `<workspace>/workflow-settings.json`
keyed by `namespace/name`, edited on Agent Web's Settings page from the
declaration, and merged by `WorkflowEngine.execute` into every run. A missing
required setting rejects the run before anything executes
(`workflow_settings_incomplete`); a run that tries to supply a setting is
rejected. Run-time parameters (`scope: runtime`) remain the only fields any
run interface asks for. Credentials stay SecretRef mappings in `host.json`.

Reason: The owner distinguishes settings that adapt a Workflow to a person's
computer, set once, from parameters that change every run. Merging in the
engine covers Agent Web, schedules, Telegram and Agent tool calls in one
place. A workspace file rather than `host.json` lets every process read the
current values on each run without a restart, and keying by name keeps them
across upgrades. Rejected alternatives: settings in `host.json` (needs a
restart and the config path in every process), per-workflow typed members of
`HostIntegrations` (core change per Workflow), asking settings at run time.

## 2026-10-05 — Natural-language Workflow authoring: compose first, extract blocks during migration

Decision: Agent-authored Workflows are compositions of installed
capabilities with one parameter declaration; the bounded coding harness adds
a capability only when a building block is missing, as a candidate without
execution rights. Modifications are new versions with a diff and regression;
published versions are never edited in place and stay available for
rollback. Owner decisions: the owner may approve Agent-generated Workflows
alone; web capture covers internal (C4C, portals) and external sites;
generated Workflows are private by default and the publisher chooses who may
install them; reusable web, Excel, email and GitLab capabilities are
extracted during the rs_workflow_system migration. Captured web content is
treated as data, never as instructions; external sites never receive company
credentials or the corporate browser profile. Plan:
`docs/phases/NL_WORKFLOW_AUTHORING.md`.

Reason: Composing reviewed, typed capabilities is deterministic and
reviewable, while generating code per request is not; the migration is the
cheapest place to learn which tools the Agent needs. Rejected alternatives:
generating whole Workflow code from each request; editing installed
Workflows in place; wrapping every migrated job only as an opaque script
(prevents reuse); trusting page text as Agent guidance.

## 2026-10-05 — `fn:` choice functions read a Workflow's own settings

Decision: a parameter's `choices_source` may name `fn:<name>?arg={field}`, a
read-only host function registered in `host_runtime.host.CHOICE_FUNCTIONS`.
It receives the Workflow's per-install settings and the bound arguments,
never a credential, and an error it raises means "unavailable". One resolver
(`host_runtime.choice_sources.ChoiceSources`) serves the engine (run
validation, rejection `choice_function_unavailable`), Agent Web
(`/api/workflow-options`) and Telegram buttons. The engine's choices provider
now receives the manifest. First use: Workflow 14's station menu
(`fn:ncc_plan.stations`), read from the catalogue file its settings name.

Reason: some choice lists are a property of the install, not something a run
publishes; with `ref:` the menu would be empty and the run refused until a
separate publish run, and the settings would be configured twice. Rejected
alternatives: a refresh Workflow that publishes `ref:nccStations` (chicken
and egg, duplicated settings); publishing on settings save (a hook per
Workflow); a free-text station field (loses the source's menu).

## 2026-10-05 — Workflow 14 is ADAPTed, not WRAPped; `outlook.draft` is the shared email block

Decision: rs_workflow_system Workflow 14 (ncc_improvement_plan) runs as an AEP
Workflow of three capabilities: `ncc_plan.prepare` (read; resolves every
document string from the catalogue, and is the dry run), `ncc_plan.render`
(write; edits the template with python-docx from the `office` extra) and the
new generic `outlook.draft` (write, draft only, file attachments, `skip` and
`best_effort`). The source's pure rules module is carried with only its
import line modernised and its 51 rule tests as the oracle; the docx edit and
run are ported, and a local parity test compares the document text with the
source job on the real template and catalogue. Per-install settings name the
catalogue (the source's `workflow-14.json`, content sections only; `paths`,
`params` and `ops` are not read), template, output folder and photo folder.
Not carried yet: re-importing the station table, price PDF and template
system list (`reimportSources`, uploads), and the hidden one-off overrides
(`services`, `equipmentModel`, `power`, `serviceChannels`, `contractor`,
`planYear`).

Reason: the job needs python-docx/lxml, pdfplumber, requests and the source's
ops/Bridge clients, none of which the stdlib-only `python -I -S` script-tool
runtime provides, while AEP already ships python-docx and an Outlook draft
writer; a typed draft step is also the building block NL authoring needs.
Rejected alternatives: WRAP with vendored third-party wheels (compiled lxml
per Python version inside a hash-pinned package); a script-tool runtime with
site-packages (weakens isolation for one job); keeping the draft inside the
NCC capability (not reusable).

## 2026-10-05 — The Telegram bot token may be entered on the settings page

Decision (owner request): Agent Web Settings has a Telegram section that
accepts the bot token, the allowed senders (Telegram user id -> actor) and an
on/off switch. The token is written only to this Windows user's environment
(`HKCU\Environment` variable `AEP_TELEGRAM_BOT_TOKEN`, plus the running
process); `host.json` gains only the mapping `telegram_bot ->
AEP_TELEGRAM_BOT_TOKEN` and `telegram.json` only the SecretRef name, Bridge
and senders. The page never shows the token again, only whether one is
present. Agent Web now polls Telegram in its own process when configured and
replaces the polling loop after a save, so no restart and no separate
`aep-host telegram` process are needed (the command remains for hosts without
Agent Web). Turning the bot off moves `telegram.json` to
`telegram.disabled.json`.

Reason: entering an environment variable by hand was a barrier, and the
project rule is that secret values never live in files; a per-user
environment variable is the same store the operator would use manually. The
model Gateway section still accepts names only. Rejected alternatives: a
token field saved in `host.json` or `telegram.json` (secret in a file);
Windows Credential Manager (a second secret store the rest of the host does
not read); requiring a restart after saving.

## 2026-10-05 — Workflow 11 is one Workflow that follows the GitHub source job

Decision (owner request): the three Workflow 11 assets
(`jira-weekly-report-preview`, `jira-weekly-report`, `jira-weekly-report-mail`)
are replaced by one Workflow `engineering/gtm-weekly-report@1.0.0`
(`/run 11`): resolve the window, read the GitHub board, read the scratch
sheet, plan, write the workbook, save the week's mail as a draft (never
sent), as source Workflow 11 runs report then mail in one trigger. Run
parameters: `dry_run` (default off, owner decision; plans and touches neither
the workbook nor the mail), `draft_mail` (default on), week, since, until,
max_issues, `start_time`, `end_time`; command text accepts `dry-run` and
`no-mail`. The Skill `weekly-report@2.0.0` has one command. Board selection
follows `host-bridge/jobs/github_weekly_report.py` (untracked in the source
after 896046e; sha256 9293c7eff57f363b57d37e496e93dcbc388396697a54fbc5893a0ba80010a1ea,
email job 62c5220c8757f3596e55757d438e64efa03466e5bf5e5010326d821f08bf458d):
only `[GTM-n]` items (`tracked_key_prefix`), Project status closed/close/done
skipped (`closed_statuses`), included when the issue or an active comment is
in the window, a comment edited inside the window counts at its edit time,
the migrated `## Weekly report comments` body log is used only when no real
marker comment is in the window, and `start_time`/`end_time` select by moment
(a date alone is the whole day; no offset means Taiwan time). Assignee stays
the GitHub Issue Assignees field with no "SDE Assignee" fallback (owner
decision, consistent with 2026-10-03). The read-only preview manifest stays
in code only for the marketplace's read-only default candidate.

Reason: the owner does not want Workflow 11 split; the source now reads
GitHub, and AEP lacked several of its selection rules. Rejected alternatives:
keeping three assets with a Skill that chains them (still three things to
install and grant); dry run on by default (the source schedule writes for
real, and writes still need approval); following the source's assignee
fallback (owner chose the Assignees field).

## 2026-10-05 — Workflow 11 is named `sde-weekly-report`

Decision (owner request): the merged Workflow 11 recorded above is named
`engineering/sde-weekly-report@1.0.0` instead of `gtm-weekly-report`, matching
the report's own title (SDE Weekly Report). Steps, parameters, `/run 11` and
the `weekly` Skill command are unchanged. The earlier name was never
published beyond this install.

## 2026-10-05 — Skills carry a `selector_hint` for Skill selectors

Decision (owner approval): `SkillManifest.selector_hint` is an optional
single line (at most 240 characters, English and Chinese keywords) telling a
Skill selector such as JEV SystemOne what the Skill is for and how it differs
from the others; `instructions` remains the model guidance. It is omitted from
serialization when unset, so earlier manifests keep their bytes and digests.
The Gateway passes each hinted tool's hint in `SkillCandidateRequest
.selector_hints`; the JEV adapter uses the hint, or the tool description
without the shared "Executes installed ..." suffix, and words its "keep the
whole catalogue" option concretely (chat, greetings, capability questions,
several tasks). Hints were added to the weekly report and NCC Skills and, as
new versions, to team-tickets 2.1.0 and the company-agent knowledge,
market-alignment, personal-proof and workflow-author Skills 1.1.0 (published
versions are not edited in place). The checklist preview Skill and the
Knowledge 1.4.0 candidate use the fallback.

Reason: on the self-hosted Laya service the full instructions plus the shared
suffix buried what told tools apart; short distinctive hints raised accuracy
on 20 held-out cases from 50 % to 80 %. Rejected alternatives: rewriting
`instructions` (they guide the model, not the selector); deriving hints
automatically (measured worse than written ones); a two-stage "one tool?"
then "which tool?" question (more misses).

## 2026-10-05 — JEV shadow mode, most-likely tool lists, and an explicit egress approval

Decision (owner agreed to the order: improve selection, then shadow mode):
`decision_accelerator` gains `mode` (`active` default, or `shadow`),
`skill_max_tools` (1 = single best; more keeps the most likely commands until
their probability reaches the threshold) and `egress_approval`
(`approval_ref`, scope `latest_user_message`). The Host now wires the JEV
Skill selector when configured, but the authorizer admits a request only with
an egress approval, so nothing is sent before the owner records one. In
shadow mode the DecisionService asks the accelerator on a background thread
and always answers with the baseline; `workspace/jev-shadow.jsonl` records
what it would have chosen (tool names, probabilities, confidence, latency)
next to the tools the model called, never message text;
`python -m evaluation.jev_shadow_report` replays any threshold and list
length. A second "several tasks?" question in the same Laya call was measured
and dropped (no accuracy change, latency nearly doubled).

Reason: choosing a threshold and list length from four dozen written cases is
guesswork; shadow mode measures real requests at no cost to the person's turn.
Rejected alternatives: going straight to active mode (a wrong narrowing hides
the right tool); synchronous shadow calls (adds Laya's latency to every
turn); logging message text for later review (unnecessary for the replay and
widens what is stored).

## 2026-10-06 — Tool progress reaches a channel through a context variable

Decision: the Gateway reports each conversation tool call as it starts and
ends (`running`, `succeeded`, `failed`) to a listener in the context variable
`agent.gateway.TOOL_PROGRESS`, by tool name only. Telegram sets it around
`converse` and edits one status message in place (elapsed time, each skill
and how it ended), refreshed every 5 s; the answer follows as its own
message. Progress that cannot be sent is dropped and never fails the request.

Reason: the owner could not tell whether the bot was working during long
Workflows. Rejected alternatives: a callback field on
`GatewayConversationRequest` (a frozen contract shared by every backend;
progress is presentation, not policy); editing the status message into the
answer (answers can span several messages); Telegram's 5-second "typing"
action alone (shows activity but not which skill).


## 2026-10-06 — Coding on the Bridge: Gateway author, pytest, restricted Windows execution

Decision (owner): coding runs first through the in-house bounded harness with
the internal Gateway model as the change author; native Claude Code follows
later for PUBLIC-only tasks. Validation is pytest only, as declared commands.
The first repository is a new practice repository. Generated code executes
under restricted Windows execution: low-integrity process, one-process Job
object with memory and time limits, an allowlisted environment, and an
outbound firewall block on a dedicated runner interpreter, which the host
checks before every run. Plan: `docs/phases/CODING_ON_BRIDGE.md`.

Reason: E2E-03 proved the loop only with a scripted author and in-process
validators; coding needs real tests to run. Low integrity is used in addition
to the owner's choice because it stops writes outside the run folder without
admin rights or new software. The firewall rule targets a separate
interpreter, because a venv's python.exe on Windows starts the base
interpreter, so a rule on it would also cut off AEP's own Gateway calls.
Rejected alternatives: WSL (slower, separate Python to maintain); Docker
(installation and licence approval on a company machine); running pytest
with no isolation (secrets in the environment, writes anywhere); native
Claude Code first (data rule allows PUBLIC context only and needs a
classifier first).

## 2026-10-06 — SOP to Workflow: fixed web targets, preview before install, authoring sessions

Decision (owner): SOP or SOP PDF plus discussion produces a Workflow composed
of building blocks, including new web and Excel blocks. Web steps replay
targets recorded at authoring time with no model at run time. A generated
Workflow is installed only after a preview run the owner approves (read steps
run, write steps report what they would do). Discussion state lives in a
dedicated authoring session. The SOP PDF is uploaded in Agent Web. Harness
structure changes (engine preview mode, authoring session) are confirmed by
the owner before they are built. Plan: `docs/phases/SOP_TO_WORKFLOW.md`.

Reason: replaying fixed targets is reproducible and sends no page content to
a model per run. Preview shows real data before anything is written. A
session survives the 12-message chat window and keeps approval out of the
model's reach. Rejected alternatives: a model choosing elements at run time
(non-deterministic, page content leaves the machine every run); exact
expected-output fixtures for every generated Workflow (too heavy for web and
Excel work); chat-only discussion (limited to 12 turns and 4,000 characters per
message); a drop folder only for PDFs.

## 2026-10-06 — Owner approves engine preview mode and authoring sessions; business cards stay local

Decision (owner): designs A (engine preview run) and B (Workflow authoring
session) in `docs/phases/SOP_TO_WORKFLOW.md` are approved. Today's harness
additions for coding (Gateway `TOOL_PROGRESS`, the
`change_made_no_difference` stop, the new `src/harness/` modules) are
accepted as they are. Business cards (W9, after SOP to Workflow): OCR and
field extraction run only on this computer (Windows OCR plus rules), the
owner confirms the fields before they are saved, and Telegram accepts photos
from allowed senders only.

Reason: cards are customers' personal data and the Gateway is approved for
UNCLASSIFIED data only. Rejected alternatives: Gateway field structuring of
OCR text, and Gateway vision on the photo, both of which would send personal
data to the Gateway; Agent Web upload only, which loses taking a photo on the
phone.

## 2026-10-06 — Business cards are read by the Gateway model, as in the owner's Hermes skill

Decision (owner, replacing the earlier local-only choice for W9): business
card photos are read by the internal Gateway model (local LiteLLM, gpt-5.5),
as the owner's Hermes `business-cards` skill already does. Only card photos
are sent; the store and other personal data stay local. AEP adopts the
skill's design: a JSON object with an `uncertain` field list, confirmation
of only those fields, append-only scan history with change reporting, and a
chart grouped by department and title seniority that always says it is not a
reporting chart. The 14 cards in Hermes' `cards.db` are imported once, with
their history.

Reason: the skill's quality comes from the model reading the image, not from
OCR. Local Windows OCR plus rules would be noticeably worse at telling name
from title, at vertical cards and at mixed scripts. The photos already reach
the same Gateway through Hermes. Rejected alternatives: local-only OCR (lower
accuracy); local first with per-card escalation (more steps for the owner);
sharing Hermes' database file (it would tie AEP to Hermes' location and
schema); de-duplicated upserts (they lose job and company changes).

## 2026-10-06 — Coding runner may use the company Zscaler proxy; AppContainer not adopted

Decision (owner): Zscaler routing is company IT's configuration and is treated
as legitimate. Code under test in the coding runner may reach the network
through it. The runner keeps restricted Windows execution (low integrity,
one-process Job object, allowlisted environment, timeout). The firewall rule
stays and blocks direct outbound connections.

Context: a live probe showed the firewall rule blocks direct egress, but
loopback is not filtered by Windows Firewall, so the runner reaches the
Zscaler proxy on 127.0.0.1:9000 (and n8n and the Laya tunnel). An
AppContainer prototype blocked all of that and personal-file reads without
admin rights. Rejected alternatives: AppContainer (owner prefers IT
governance of egress over a stricter sandbox); AppContainer with network
allowed but reads blocked (most complex, weakest exfiltration protection).

## 2026-10-06 — The shipped Knowledge Skill stays 1.0.0 without a selector hint

Decision (owner): `company-agent/knowledge-query` in
`capabilities/company_agent/manifest.py` goes back to 1.0.0 with no
`selector_hint`. This corrects the 2026-10-05 selector-hint entry for this
one Skill; the other hinted Skills keep their new versions. The live 1.1.0
installed on 2026-10-05 was moved to `assets/skills/disabled/`.

Reason: versions 1.1.0-1.4.0 of this Skill already exist on the host from
Knowledge evolution, with different content (1.4.0 is the current
candidate). The hinted 1.1.0 changed a published version and re-enabled a
superseded Skill under a second `knowledge` alias. Later versions come from
Knowledge evolution, not from the shipped manifest. Rejected alternative:
an unused 1.5.0, which would sort above the 1.4.0 candidate and look newer.

## 2026-10-06 — Each Knowledge vault is its own conversation tool, described by the vault's manifest

Decision (owner): a Knowledge vault's purpose and boundaries are written in
the vault's own manifest (`KnowledgeManifest.purpose`, `.boundaries`), not in
host.json. The Gateway offers a Skill command that names the Knowledge query
capability once per queryable vault, as `<alias>__<vault name>`. The tool's
description is the vault's purpose and boundaries, its only field is
`question`, and the host binds the vault, so the model cannot redirect a tool
to another vault. The model, or a Skill selector such as JEV, therefore
chooses the vault when it chooses the tool, and adding a vault adds a tool. A
vault published before these fields is described by its domain until a new
version says more.

Reason: chat Knowledge questions always failed. The single `knowledge__ask`
tool had no schema, so the model never sent the required `asset` (checked
live, before and after the 2026-10-05 Skill changes). The vault location was
already in host.json; the gap was telling the model which vaults exist and
what each covers. Rejected alternatives: a generic schema for every
capability tool (the model would still have to spell exact asset identities);
an automatic default when only one vault exists (a special case that breaks
at the second vault); descriptions in host.json (they would not travel with a
shared vault).

## 2026-10-06 — A Workflow step may take a fixed value written into the manifest

Decision (owner): `WorkflowStep.inputs` gains a third source,
`{"source": "fixed", "value": <JSON>}`, beside `run` and `step`. A generated
Workflow carries its recorded web procedure, URLs, labels and sheet names this
way, so they are part of the manifest the owner reviews, approves and
versions. A fixed value that looks like a credential is refused when the
manifest is read. Existing manifests serialize unchanged.

Reason: a step could read only the run's arguments or an earlier step's
output, so SOP to Workflow had nowhere to put what it recorded. Rejected
alternatives: hidden per-install Workflow settings (what runs would not be in
the approved manifest and could be edited on the Settings page); a separate
procedure file referenced by path (a second artifact to version and approve).

## 2026-10-06 — Preview runs are a separate engine method

Implementation of the approved design A: `WorkflowEngine.preview(context,
workflow, arguments)` returns a `WorkflowPreview` of `PreviewStep`s (`ran`,
`planned`, `blocked`, `failed`, `not_permitted`) instead of adding a mode and
a `previewed` status to `execute` and `RunStatus`. Behaviour is as approved:
read steps run through the Bridge under the actor's grants; other steps are
not dispatched and show their resolved inputs plus, when the handler has
`preview(inputs)`, what it computes it would do (`excel/upsert-rows` does);
nothing is journaled. A Workflow without a read step is refused
(`preview_has_no_read_step`).

Reason: `RunStatus` and the run journal are shared by every execution path
(Agent Web, Telegram, schedules, recovery); a separate result type changes
none of them. Rejected alternative: a `mode` on `execute` with a new run
status, which every consumer of run status would have to learn.

## 2026-10-06 — Author in conversations, approve with buttons, keep candidates in one place

Decision (owner): Workflows and Skills are developed in any conversation
(Agent Web or Telegram) with files attached to it, not on dedicated pages; the
"Create a Workflow from an SOP" and "Create a Skill or Workflow draft" panels
are removed and contribution drafts move to a Candidates area on the
Capabilities page. Approval to install a candidate or to run a temporary task
once is a button in the conversation that only the owner can press; the model
has no tool that approves, installs or runs a change. A temporary task that
only reads runs directly; one with a write or external step is previewed and
waits for approval. Skills and Workflows carry one category from a fixed list
plus free tags, stored in the existing `AssetMetadata.categories`. Plan:
`docs/phases/CONVERSATIONAL_AUTHORING.md`.

Reason: a dedicated page fixes authoring to one surface and one kind of
asset; conversations already exist in both channels, and the approval
guarantee of design B is kept by making approval a human action outside the
model's tools. Rejected alternatives: approval only on the Candidates page
(Telegram could not finish a task); preview-and-approve for every temporary
task (an extra press for a lookup); free tags only (synonyms drift); a fixed
list only (a list to maintain for every niche).

## 2026-10-06 — Conversation coding tool and a narrower Knowledge intent route (coding_v1 G1, D1)

Decision (owner, on the condition that Knowledge asking and task/Workflow
execution are not affected and that JEV does not turn every task into
coding):

- G1: Workflow `engineering/run-python` (capability `coding/run-python@1.0.0`)
  lets the conversation Agent run one Python script in a task workspace under
  a folder listed in `coding.workspace_roots`, with the restricted runner.
  The script writes only to the workspace's `output/` and its own run folder;
  `input/` stays read-only. The result (exit code, output, output files) goes
  back to the model, which can fix and run again within the conversation's
  tool budget. The capability's side effect is `execute`, and it has a
  standing grant. Skill `engineering/coding` moves to 1.1.0 with commands
  `change` and `run`; its instructions and selector hint limit it to
  requests to process local files or to write and run a program.
- D1: the Knowledge intent route in Agent Web chat no longer takes a message
  that names local work (a URL, a drive or UNC path, or a file name with a
  common extension); the model handles that message. Questions without such
  references route as before.

Reason: coding_v1 baseline-run-001 was 20/20 BLOCKED. Every task lacked a
file and execution tool (G1); five web and spec tasks never reached the model
(D1). Rejected alternatives: removing the Knowledge intent route (it carries
the 1.4.0 evidence procedure the owner reviews answers with); a capability
tool without a schema (the model cannot fill its fields; a Workflow gives the
tool its schema without a Gateway change); per-run approval buttons for
script runs (conversational authoring A5 is not built yet; writes are
confined to the workspace's output folder instead).

## 2026-10-06 — A Skill selector never narrows the tools to coding

Decision (owner: "don't let JEV turn every task into the coding harness"):
the Gateway refuses an accelerator (JEV) narrowing that contains a tool of an
excluded Skill alias; the host excludes `coding`. Such a narrowing falls back
to the whole catalogue and the model chooses. Narrowings without coding tools
apply as before.

Reason: live shadow records after `coding/run-python` was installed showed
JEV ranking `coding__run` first for a Knowledge question (low confidence, so
it had no effect in shadow mode). In active mode that would leave the model
only coding tools. Rejected alternatives: relying on the selector hint alone
(the hint was already narrow); removing coding from JEV's candidate list
(shadow evaluation would lose the signal).

## 2026-10-06 — Business workflow lab: grading rules and isolation

Decision: the lab (`benchmarks/business_workflow_lab/`) grades each task with
four separate flags (code generated, executed, Excel correct, workflow
rerun) and marks a task BLOCKED, never FAIL, when a needed interface tool is
missing. The BLOCKED layer names only what was observed: a refused
subprocess, a stopped conversation, or a missing tool. A browser task counts
only with a browser User-Agent in the site's own log; an HTTP-client script
reaching the same pages is recorded but does not satisfy the browser
requirement. The mocks keep their data under `operator/`, and the batch
script flags scripts that reference mock internals.

Reason: the owner's test plan requires that one success flag never hides
another gap, and that the Agent not be credited for reading data behind an
interface. Baseline-001 showed the Agent does read mock internals when it
cannot operate an interface, so the flag is needed. Rejected alternatives:
counting HTTP scraping as browser use (the plan requires real browser
operation); moving the mock data to another Windows account now (it needs
the owner's machine setup, so it is recorded as gap L7 instead); treating
model-gateway 503s as task results (they are kept as evidence and the tasks
were rerun once).

## 2026-10-06: Conversation output cap 8000 and 8 tool calls per turn (D3, G3)

Decision (owner: "你提的1~3我覺得沒問題，可以執行"):
- Every conversation request asks for up to 8000 output tokens (was 1024).
- A turn may make 8 tool calls, which is 9 model turns (was 4 calls and 5 turns).
- A provider reply that stopped at the output limit with nothing usable is `model_output_truncated`, not an empty answer. A text answer at the limit is still returned.
- The limits live in `agent.backend_contracts`, so the chat request default, the loop and the result contract agree.

Reason: coding_v1 fix-run-002 had 11 tasks stop on truncated tool calls and one on the 4-call budget. Rejected alternatives:
- raising the cap only for coding turns: the model decides on a tool within the same turn, so the cap must be in place before that choice;
- unlimited calls: the loop must stay bounded (AGENTS.md rule 9).

Live checks after the change were the same as before: Knowledge asking direct and in chat, the W14 dry run and `run-task`.

## 2026-10-06: Workflows drafted, run and installed from a conversation (G4)

Decision (owner approval of G4, and of conversational authoring A4 to A6):
- **Authoring tools.** The host offers conversation tools `authoring__draft/preview/run/install/list_workflows`. A draft is a private candidate under `<workspace>/authoring/chat/`.
- **When a run needs approval.** A run whose steps only read runs at once. Any other run, and every install, becomes an approval request. Only the owner's button decides it: Agent Web `POST /api/approvals/decide`. The model has no approving tool.
- **What a run uses.** Runs go through the Bridge with exactly the grants the candidate's steps need.
- **Install.** It writes the Workflow published, with the owner as business approver, and adds the grants it needs.
- **The decision in the conversation.** The decision and its result join the conversation as one turn, so the model reads the outcome next.
- **Run values for scripts.** `coding/run-python` takes a step's run values as `params.json` (`AEP_WORKFLOW_PARAMS`). A saved script reruns with new values and the same digest.

For coding_v1 and the lab, the operator script presses the button and records each press as a human intervention.

Rejected alternatives:
- an approve tool for the model: owner decision 1 forbids it;
- a restart-only install: a conversation must be able to rerun what it installed.

Telegram buttons are a follow-up.

## 2026-10-06: Agent tools for browser, desktop and CLI (lab gaps L1 to L3)

Owner decisions:
- **L1, Edge.** The company uses Edge for SAP, and IT signs people in automatically, so signing in is clicking through.
  - Built: `browser/operate@1.0.0` keeps one Edge open and replays web-script actions on `web.allowed_origins`. It adds `download` into a task workspace and `read_record`. It returns a look at the page.
  - Built: conversation tool `browser__operate`.
- **L2, Windows UI Automation with built-in .NET.**
  - Built: `desktop/operate@1.0.0`. A C# helper is compiled by the Framework's csc on first use.
  - It starts only applications registered in `host.json desktop.applications`, touches only that process's windows, and saves files only under a task workspace's `output/`.
  - Built: conversation tool `desktop__operate`. The lab's Expense mock was rewritten in WinForms, because Tk exposes nothing to UI Automation.
- **L3, relax the runner.** `coding/run-python` may have 4 processes alive (`coding.run_python_max_processes`); `coding/change` stays at 1.
  - Residual risk, accepted with the decision: a child other than the runner interpreter is not covered by its firewall rule.

Both interface tools are host conversation tools that dispatch a `CapabilityInvocation` through the Bridge, so the actor's grant decides (grants recorded as owner-approved 2026-10-06). Drafted Workflows can use the same capabilities as steps.

Rejected alternatives:
- screenshots with coordinates: less stable, and they need vision;
- a host allowlisted-command tool for the CLI: the owner chose to relax the runner;
- letting runner scripts drive Edge over DevTools: that would bypass the origin allowlist and the runner's network block.

## 2026-10-06: coding_v1 validators 1.1 to 1.3

Each change makes a check follow the owner's written acceptance or when it is measured; no expected answer changed. Every version is recorded in each run's metadata.
- **1.1:** T20's fault check reads the operator's injection evidence. While no platform write existed, it was fixed to BLOCKED.
- **1.2:** T12 accepts xlsx, CSV or JSON. The acceptance names six rows and their values, not a format.
- **1.3:** T09's `data.json` is checked as the success scenario left it. T13 counts the 500 page's requests during the delivered program's final run, with the session total reported beside it.

Rejected alternatives:
- changing prompts or expected answers;
- accepting FAILs that came from the operator's own measurement defects.

## 2026-10-06: Lab environment, SSO sign-in and no separate isolation

Owner:
- the lab's SAP-like site signs in like company SSO, with one button and no password;
- the mocks do not move to another computer, because the lab tests whether the Agent can operate each kind of application.

Bypass detection (`bypass_signals`) stays in the results.

## 2026-10-07: 20 tool calls per turn, and a tool record carried across turns

Decision (owner, after lab fix-001):
- **Budget.** Every conversation turn may make 20 tool calls, which is 21 model turns.
- **Tool record.** Each Agent Web answer keeps a compact record of the tools it used: the tool, the outcome, the files written, and the candidate, approval and run ids. It never holds page text, file content or scripts.
- **The next turn.** Later turns give the model that record with the answer's text, so a stopped turn can be continued.
- **A stopped turn.** It says how far it got and that 繼續 continues it.
- **Benchmarks.** The lab operator replies 繼續 at most three times per task when a turn stops at the budget, and records each reply as an intervention.

Reason: in lab fix-001, 8 of 16 runs ended with `tool_loop_limit` before a workbook existed. The next turn could not continue, because history kept only text.

Rejected alternatives:
- raising the budget only when coding or interface tools are present: harder to reason about, and the owner chose one rule;
- keeping full tool output in history: page and file content would flow into every later turn.

Knowledge turns normally end after one or two calls.

## 2026-10-07: Tool and runtime fixes from lab fix-002 and fix-003

**Several tool calls in one reply run in order.** Each call counts against the turn's budget, and each gets its tool message back. The Gateway used to end the turn with `multiple_tool_calls_not_supported` (X02).
- Rejected: running the calls in parallel. Two calls may touch the same browser or the same workspace.

**Telegram approval buttons (A5).**
- A chat reply carries approve and reject buttons for each request the Agent made in that chat.
- Only the Bridge owner's tap decides. A sender acting on the owner's behalf is refused.
- Telegram history keeps the same tool record as Agent Web.

**Leftover Edge on the Agent's profile.** `browser/operate` uses a profile no person signs in to. A browser holding that profile can only be one that an earlier host process left behind. The handler asks that browser to close over DevTools, which keeps the profile intact, and then starts again. `HostRuntime.close` ends the Edge and the desktop applications it started.
- Rejected: killing every `msedge.exe`. That could close a person's own windows.

**Workflow steps for interfaces.**
- The draft guide shows `browser/operate` and `desktop/operate` as Workflow steps.
- `desktop/operate` fills `{placeholders}` from run values.
- coding 1.4.0 says a system the person signs in to or operates is used through these tools and never fetched by a script.
- Desktop app names match regardless of case, and the tool text lists the registered apps.

**Lab template Instructions.** Two rules are now stated in the Instructions: layout stays as is, and missing values stay blank. Grading had relied on both without the templates saying so.

**Coding runner gains `tzdata`.** It was installed offline from a wheel downloaded by the system Python. Apache-2.0, maintained by Python core developers.

## 2026-10-07: Ask before guessing a rule that changes the result (shared prompt)

Decision (owner, after lab X02 failed three times): the shared conversation system prompt says that when a request for work leaves open a rule that would change the result (which records count, which period or status, what to flag), the model asks that question first and does no other work in that turn.

Verified after the change:
- Knowledge asking, direct and in chat, answered without extra questions.
- The W14 dry run and `run-task` were unchanged.
- coding_v1 fix-run-008 asked no needless questions. Its two FAILs were a parsing error and a validator layout defect.

Rejected alternatives:
- the coding Skill hint alone: three runs showed no effect;
- a per-task operator nudge: it would be the operator doing the Agent's work.

## 2026-10-07: Smaller lab-driven fixes

- **The output limit.** A reply cut at the limit is retried twice within the turn, with a notice to answer more briefly. A reply that keeps getting cut still fails with `model_output_truncated`.
- **Desktop Save As.** `replace: true` overwrites a file left by an earlier run, still only inside the workspace's `output/`.
- **The draft guide.** It says to put run values in output file names, so reruns do not collide with earlier results.
- **coding Skill 1.6.0.** It fills a copy of a given template and follows the template's instructions; it never rebuilds a look-alike workbook.
- **coding_v1 validator 1.4.** T14's Overall statistics may be name/value rows. The owner's acceptance names the values; the expected values are unchanged.

## 2026-10-07: A refusal may say where in the request it happened

Decision: `CapabilityRefused` takes an optional `where`, a place in the request built only from its structure, such as `action 7 (wait_dialog)`. The Bridge turns it into the failure message "Refused at action 7 (wait_dialog)". `desktop/operate` fills it from the helper's failed step index and the action's kind.

Reason: in lab fix-008 D01, every run of a platform Workflow failed with `desktop_dialog_missing` and the generic "Capability invocation did not complete". The step waited for a dialog the app never showed after Query. The Agent could not tell which of 13 actions failed, so it retried the same code three times and then revised the Workflow.

Boundaries:
- The helper's own message still never travels, because it can quote dialog titles or control values.
- A step index outside the request names no place.
- This follows the 2026-10-07 `invalid_input` field locations: positions and kinds, never values.

Rejected alternatives:
- Passing the helper message through: it carries window content.
- Encoding the index into the failure code: codes are a fixed vocabulary the UI and the tests rely on.

## 2026-10-07: Conversation messages redact credential-shaped text instead of refusing it

Decision (owner approved): `ConversationMessage` cuts credential-shaped text out of `text` and `tool_summary` with the shared `SECRET_PATTERN`, replacing it with `[redacted]`, before validation. The rejection check stays as a backstop. The shared pattern is unchanged.

Reason: in coding_v1 fix-run-010 T09, the Agent's reply quoted the task's SOP line `Authorization: Bearer <token>`. Building the stored message raised a validation error that nobody caught. Agent Web dropped the connection, the turn was lost with no message to the person, and the benchmark runner crashed. A person pasting a password into chat would have hit the same failure.

Rejected alternatives:
- Refusing the reply and telling the person: the answer is usually useful apart from the quoted line.
- Loosening the shared pattern for `<placeholder>` values: the pattern is the one definition every redactor uses.

## 2026-10-07: Asset ownership and versions (owner decisions)

Decision (owner):
- The first publisher of a Skill or Workflow name owns it. The owner may be a person or a team, and ownership can be transferred.
- The owner names co-editors, who publish new versions directly. The owner may deprecate versions and remove co-editors.
- The platform assigns version numbers by increasing the highest existing one; the publisher picks patch, minor or major.
- Each person has one active version per name.

Plan: `docs/phases/ASSET_OWNERSHIP.md`.
- Step 1 is done now for chat-authored Workflows: versions continue from the highest installed one, and a name installed by another owner is refused with that owner's id.
- Step 2, the Registry-wide ownership record, publish check, automatic versions, one active version per person and a publish UI, follows the business workflow lab stage.

Reason: lab fix-008 W01 hit `workflow_version_exists`. Every new chat candidate restarted at 1.0.0, and the only guard was a Host-local file check. A code survey also found that nothing stops one person from publishing a new version under another person's name.

Rejected alternatives:
- Per-version owner approval for co-editors: it stalls when the owner is away.
- Publisher-chosen version numbers without an ordering rule: they collide.

## 2026-10-07: knowledge_v1, a harness benchmark for Knowledge asking

Decision (owner):
- The owner's 1,100 questions (`benchmarks/knowledge_v1/questions/source.md`, pinned by sha256) are asked through Agent Web chat as written, without naming a knowledge base.
- A fixed, stratified sample of 110 runs first; the full set follows.
- An answer passes when the Knowledge loop ran, its citations are verified in the Vault, and the answer is reasonable. INSUFFICIENT_KNOWLEDGE from a completed loop is acceptable.
- Reasonableness is judged by the company Gateway model on the cited passages only, against a "reasonable, evidence-backed" bar rather than a line-by-line audit. Over-reaching claims are listed but do not fail an answer by themselves. Verdicts and reasons are stored for spot-checks.

Reason: the owner wants the harness proven on realistic questions without golden answers. Deterministic checks prove the loop ran and the evidence is real; the model review covers what code cannot judge.

Rejected alternatives:
- Deterministic checks only: they cannot say whether a conclusion follows.
- A strict per-claim grounding audit: the first trial failed a well-supported answer for its framing sentences. That is stricter than the owner's bar.
- Naming the knowledge base in each prompt: it would skip the Agent's own tool choice, which is part of what is tested.

## 2026-10-07: Knowledge synthesis limit, and saying when Knowledge gave no answer

Decision (owner approved):
1. **Synthesis limit.** Knowledge synthesis gets 4000 output tokens when no Skill procedure sets a limit (`DEFAULT_SYNTHESIS_MAX_OUTPUT_TOKENS`; the procedure default is also 4000). A synthesis cut off at the limit is asked once more, from the same evidence, for a shorter answer. Only if that also fails is it `knowledge_model_failed`.
2. **Saying so.** The shared conversation prompt says: when a knowledge tool fails or finds no evidence, say first that the knowledge base gave no answer, and mark anything added from general knowledge as not from the knowledge base and uncited.

Reason: in knowledge_v1 sample-001, 3 of the first 19 questions failed with `knowledge_model_failed`. On the conversation-tool route the limit was 800, and an offline repro showed Q0046 cut off (`model_output_truncated`) at 800 but answered at 4000. After a failed call, the conversation model answered from memory without citations and without saying so. The direct route was unaffected, because the installed Knowledge Skill 1.4.0 sets 8192.

Rejected alternatives:
- Raising the limit without a retry: a long answer could still be cut off.
- Forbidding any answer after a failed lookup: the person would get nothing useful.
- Leaving the behaviour and only recording it: an uncited answer presented as knowledge is misleading.

## 2026-10-07: Knowledge harness credits cited facets, keeps supported answers, and the tool route uses the Skill procedure

Decision (owner approved, from knowledge_v1 sample-001 and an offline study):

1. **Facet credit.** A requested facet is covered when any cited passage meets the installed Skill's own rule for that facet (`knowledge.evidence.facet_supported_by`, used by `KnowledgeBridgeActions.facet_report`), under the Skill's citation policy. Before, only the first few passages retrieval listed for the facet counted. In 5 of 7 discarded answers, the answer had cited a passage that met the rule but sat outside that list.
2. **No discarding.** When the claims are supported but a facet is still uncited, Agent Web shows the supported answer with its sources and `未能以證據支持：<facet>`, instead of a one-line refusal. `ok` stays false and the phase stays `needs_input`. Under `wiki_primary`, messages no longer say "Raw evidence".
3. **Skill `company-agent/knowledge-query@1.5.0`.** It adds focus hints for Aerospace / Defense, Automotive and AI.
   - In an offline retrieval study, the share of market evidence on topic rose from 0–33% to 83–100% with no regressions.
   - The Semiconductor hint was left out: it cut competitor retrieval from 4/4 to 1/4.
   - Adding "radar" to the A&D pattern was left out: it captured automotive radar questions.
4. **Tool route uses the harness procedure.** The live vault tool comes from `engineering/knowledge-query@1.0.0`, which has no procedure, so tool-route questions ran raw-only, without facets and with an 800-token limit. They passed 9 of 58, against 22 of 34 on the direct route. The host now binds the procedure of the one Knowledge Skill the direct route uses (`_harness_knowledge_procedure`) into vault tools offered by a Skill without one. The model cannot set or change it. If there is not exactly one such Skill, none is bound.

Rejected alternatives:
- One targeted re-synthesis asking the model to cite the uncited facet's passages. In 4 of 5 offline trials it passed the check only by citing irrelevant passages, sometimes to say they did not apply. That is a false validation.
- Copying the procedure into the engineering Skill: two sources of truth.
- Routing every Knowledge question to the direct route: it cannot handle questions that mix Knowledge with other work.

## 2026-10-07: Per-person pixel-art avatars in Agent Web

Decision (owner):
- Each person picks an avatar in Settings.
- It shows at the top left of Agent Web. Frame 1 shows at rest; while a conversation turn runs, the character's other frames loop about every 180 ms, and frame 1 returns when the last turn ends. Under the system's reduce-motion setting, one action frame shows instead of the loop.
- The choice is per person: it is stored per actor under `workspace/user-preferences/` (the file is named by a digest of the actor), and only a character the manifest lists can be chosen.

The frames come from a 10-character sheet the owner supplied. `scripts/slice_avatars.py` cuts it into transparent two-tone PNGs (`src/host_runtime/avatars/`, about 50 KB). The frames reach the page as data URIs through the token-protected `/api/avatars`, so no image route is served without the token. In dark mode the black ink is inverted.

**The characters are from One Piece (© Eiichiro Oda / Shueisha / Toei).** The owner was told about the copyright risk and chose to keep the sheet in the repository rather than keep it local or use original characters. The mechanism takes any N-row, multi-frame sheet, so the art can be replaced by re-running the slicer.

Rejected alternatives:
- One avatar for the whole Agent: the owner chose per person.
- An unauthenticated image route: data URIs over the existing API need no new route.

## 2026-10-07: Asset ownership step 2 in the Registry (implementation decisions)

This implements the owner decisions of the 2026-10-07 entry "Asset ownership and versions" in the control plane. Plan and status: `docs/phases/ASSET_OWNERSHIP.md`. Contract: `docs/CONTRACTS.md`, "Asset name ownership and versions".

Decisions:
1. **The record and the rule live in the Registry.** The `(namespace, name)` ownership record is stored next to the packages. `publish_as` applies the publish check inside the transaction that inserts the version, so two publishers cannot both pass it.
2. **The platform's own publish stays separate.** `publish(package)` is the preview seed and migration path, with no member identity. It keeps a name with its owner (`owner_mismatch`) but does not order versions, so a historical catalog can be imported as it was. Members publish only through `publish_as`.
3. **Additive schema.** The `name_owners` table is added without changing `schema_version` (`1`), so the previous code still opens a migrated database, which makes a rollback safe. A name without a record, whether it is older or was published meanwhile by the previous code, gets one from the owner declared by its earliest version (lowest SemVer precedence). That happens when the database is opened and inside each publish.
4. **Assigned versions do not renumber packages.** A package's artifact (a manifest, or a signed extension envelope) carries its own version. So the platform assigns the version first (`next_version`), the publisher builds for it, and the publish checks that the version is still the assigned one (`version_not_assigned`). `publish_next(change, build)` does this and retries when another publisher took the version.
5. **Deprecation is recorded beside the name, not in the package.** The owner asked for the existing `deprecated` lifecycle. But `PublishedAssetPackage` accepts only `lifecycle="published"`, and the owner also decided that published versions are immutable. Rewriting a stored package would break both, and a Host on older code would then reject the catalog. A `VersionDeprecation` (version, reason, optional replacement, deprecated_by) is therefore recorded on the ownership record. A deprecated version is no longer offered (`available`) or chosen anew (`asset_deprecated` in `select` and `replace`). Existing selections and installs keep it for rollback.
6. **One active version per member, device and name.** `select()` revokes the member's other active version of the name on that device in the same storage write, like `replace()`. Tool (capability) selections are not affected. `DeviceAuthorization` does not reject two versions, because stored authorizations from before this change may hold two and must still load.
7. **Co-editors are member actor ids.** Managing a name (co-editors, transfer, deprecation) belongs to the owner, or to any member of an owning team. That is the same `owns()` rule `entitled()` uses. A transfer to a user requires an active member. A transfer to a team is accepted as named, because the platform has no registry of groups.
8. **No member publish route yet.** The member portal exposes reading a record, the next version and the owner operations. A publish route needs artifact upload and a review queue. Without them, a member could submit a package that asserts its own business approval and technical review.

Rejected alternatives:
- Marking `lifecycle="deprecated"` in the stored package: it breaks the immutability and the `PublishedAssetPackage` contract (see 5).
- Bumping `schema_version` to 2: the previous code would refuse the database (`unsupported_schema`), so rollback would need a restore.
- Letting the Registry rewrite the version of a submitted package: the artifact bytes and their digest would disagree with it.
- A `DeviceAuthorization` validator for one version per name: it would fail on stored authorizations that already hold two versions.

## 2026-10-08: Asset ownership step 2 design choices confirmed

The owner confirmed the five choices made while implementing step 2 (`9a81382`):
1. Deprecation is recorded beside the name, not by rewriting a published package's lifecycle. A deprecated version is no longer offered or selectable, while existing selections and installs keep working for rollback.
2. "Automatic" versions are assigned before the package is built, and publish checks that the version is still the assigned one.
3. Co-editors are individual people only. A transfer to a team is accepted as named.
4. The platform's own seed publish does not enforce version order.
5. Two active versions selected before this change are cleaned up at the member's next selection of that name.

Still to do: a member publish route with artifact upload and a review queue, a publish and ownership UI, showing deprecations to Hosts, and reconciling the Host-local step 1 with the Registry record. Step 2 goes live when the Shared Platform restarts.
