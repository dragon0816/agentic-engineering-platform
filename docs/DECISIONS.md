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

## 2026-10-08: The Agent may use every web page; company IT governs network access

Decision (owner): the browser tool and web Workflow steps may open any web site. There is no per-site approval and no block list. Network access itself is governed by company IT (the Zscaler proxy).
- `web.allowed_origins` accepts `"*"`, meaning any http or https origin. `"*"` is also the default, so `"web": {}` enables every site.
- Listing explicit origins still restricts the Agent to those origins.
- The live host now uses `["*"]`; the backup is `host.json.bak-20261008-062556-before-any-origin`.

Kept boundaries:
- Only http and https pages are web pages. `file:`, `javascript:`, `data:` and browser pages are refused (`integrations.web_script.origin_permitted`).
- The Agent's Edge uses its own profile, apart from the person's browser.
- Downloads land only in a task workspace's `output/downloads/`.
- Page content is data, never instructions.

Reason: the owner asked a coding task to read Yahoo Finance (`tw.stock.yahoo.com`). Every attempt failed with `web_origin_not_allowed`. Telling the Agent "it is open now" changed nothing, because only host.json decides, and the change needed a restart.

Rejected alternatives:
- Per-site approval cards with "once" or "always" options, with a per-person list and an admin block list. The owner judged that too hard to use, since IT already controls access.

## 2026-10-08: Files can be attached to a conversation turn

Decision (owner): a person can attach images, PDF, CSV, HTML, TXT, JSON, YAML, MD and ZIP files to a message, both in Agent Web and in Telegram. Limits are 25 MB a file and 10 files a message. The company endpoint's `vision` is turned on, so the model sees attached pictures. The gateway was verified to read an image, and the host.json backup is `*.bak-*-before-vision`.

How it works (`host_runtime/attachments.py`):
- Files are kept per conversation under the workspace's `attachments/`, and deleted with the conversation.
- Text files and PDFs (via pypdf) give the newest message their opening text: 8,000 characters a file and 24,000 a message.
- Pictures up to 5 MB go to the model as images.
- A zip is unpacked beside itself. It must stay under 2,000 files and 200 MB actually written, and an entry may not leave its folder.
- Every file's absolute path is given, so coding tools work on the full file. Content is marked as data from the person, never instructions.
- The Gateway accepts images only on the person's newest message (older turns stay text), asks for a vision-capable model when there are images, and lets that message carry up to 40,000 characters. Older messages keep the 4,000-character limit.
- A stored question remembers its files' names and paths, so later turns can still point tools at them.
- A message with files always goes to the conversation model, not to the direct Knowledge or command paths. Other backends refuse files.

Agent Web uploads through the token-protected `/api/attachments` (base64, up to 36 MB a request). The page offers a paperclip button, drag-and-drop and pasting screenshots. Telegram follows in a separate change.

Reason: the owner's coding work needed files, and the Agent could not take any.

Rejected alternatives:
- Images as files only: the owner chose vision.
- Putting whole files into the conversation: a large file would crowd out the conversation, and the path gives tools the full file.

## 2026-10-08: Telegram accepts files and photos

Decision (owner): the Telegram channel takes the same attachments as Agent Web. A message with a document (png, jpg/jpeg, gif, webp, bmp, pdf, csv, html/htm, txt, json, yaml/yml, md, zip) or a photo is a conversation turn; its caption is the text, and "請看附件。" stands in when there is none.

How it works (`channels/telegram.py`, shared core `host_runtime/attachments.py` unchanged):
- The sender map is checked first; a stranger's file is never downloaded. Type, size and count are checked from Telegram's own metadata before any download, then again by the store.
- A photo uses its largest size. A file is fetched with `getFile`, then a GET of `<api_base>/file/bot<token>/<file_path>` through the bot's own transport. The token is resolved for that one URL and dropped. A download failure is reported by code only, so no URL or exception text reaches a reply, the history or a log. The `file_path` Telegram returns is checked before it goes into the URL.
- Limits: our 25 MB a file and 10 files a message, plus Telegram's 20 MB bot download limit. Each refusal is a Traditional-Chinese reply; an unsupported type lists the supported ones.
- Files are kept in the shared `AttachmentStore` under the workspace, per chat and sender (`telegram-chat-<chat>-sender-<sender>`, the same key as the chat's history). `/new` clears that history and deletes those files.
- `for_model` builds the note and pictures, which ride on the newest user message only, as in Agent Web. The stored history keeps the caption plus a `[附件]` list of names, kinds and paths, never the content.
- Album: the items of one `media_group_id` (same chat and sender) that arrive in the same `getUpdates` batch become one turn with one reply. An item that arrives in a later batch is its own turn. Telegram normally delivers an album together, and buffering across polls would need timers in the poll loop.
- Without a conversation model, or on a host without an attachment store, files are refused with a reply.

Reason: the owner's Telegram use needed the same files as Agent Web (decision of the same date).

Rejected alternatives:
- Waiting a short time to gather every album item across polls: it adds state and timing to the cursor-confirmed loop for a rare case.
- POSTing the download like other Bot API calls: the file endpoint is read with GET, and the transport already offers `request`.

## 2026-10-08: Claude Code, Codex and Copilot author Skills and Workflows through AEP

Decision (owner): the resident harness may not yet be strong enough for advanced coding and Knowledge work, so connected coding agents build assets with AEP's own creators.

Owner choices:
- **Connection:** a CLI and an MCP server, both offering the same operations.
- **Scope:** Workflows and Skills.
- **Data:** the PUBLIC rule is kept.

Full scope: `docs/phases/EXTERNAL_AUTHORING.md`.

How it works:
- **One facade.** `host_runtime/external_authoring.py` serves both `aep-host assets ...` and `aep-host mcp`. The MCP server is a stdio JSON-RPC server written with the standard library only; it covers initialize, ping, `tools/list` and `tools/call`. The facade wraps `ChatAuthoring`, so external submissions share the resident Agent's candidates and approval queue. Each one is marked `source: external:<agent>`; the agent name is self-declared.
- **Nothing installs without the owner.** An external agent can check, submit and revise a candidate:
  - a read-only Workflow runs at once;
  - every other run, and every install, becomes an approval decided only by the owner's button. Agent Web lists these submissions under Installed with the whole draft.
- **What the agent can see** (PUBLIC rule):
  - the catalog gives the platform's capabilities (descriptions and input schemas), the run-python workspace roots, and installed asset names, owners and parameter names;
  - it never gives a Workflow's description or steps, or a Skill's instructions or selector hint;
  - run results are statuses and failure codes only.
- **Skill authoring** (`host_runtime/skill_authoring.py`):
  - the host sets owner, version and lifecycle;
  - `rules` and `script_tools` are refused; commands must target installed capabilities or Workflows;
  - a `procedure` is allowed only on a Knowledge Skill and must validate as a `KnowledgeProcedure`; secrets in instructions are refused;
  - name ownership and alias uniqueness follow the 2026-10-07 rule;
  - install rechecks everything, writes the Skill published, and moves the actor's earlier versions to `skills/disabled/`. It takes effect after a restart.
- **Creator Skills ship as package data.** `aep-host assets connect --for claude-code|codex|copilot --project DIR` writes them where each agent reads project skills (`.claude/skills`, `.agents/skills`, `.github/skills`).
  - For Claude Code it also writes the project's `.mcp.json`.
  - For Codex and Copilot it prints the MCP block for the person's own configuration, which AEP never edits.
- **Verification.** `benchmarks/authoring_v1` runs each agent headless in a sandbox Host. The runner approves as the owner. The installed Workflows are run with hidden values, and the installed Skill is loaded beside all the others.

Reason: the creators already existed only inside the resident Agent. The external agents needed the same governed path, without a second, unreviewed way to install.

Rejected alternatives:
- The `mcp` Python SDK: it adds a web stack the Host does not use, and the needed protocol surface is small.
- Letting agents write manifest files into the workspace: that bypasses review and ownership.
- Returning run data to the external agent: it would break the PUBLIC rule. The owner and the resident Agent see the data in Agent Web.
- Editing `~/.codex/config.toml` or `~/.copilot/mcp-config.json` automatically: those are the person's own settings.

## 2026-10-08: Task folders are checked when a Workflow is drafted, and the Agent is told the roots

Decision (owner): the Agent is told where task folders may be, and a drafted Workflow is checked against that. The owner's live host also gets a narrow personal root.

Trigger: the resident Agent suggested `C:\Users\Chi_L\Documents\ChatGPT\stock-workflow` for a stock-price Workflow. That folder is outside `coding.workspace_roots` and did not exist. The draft and its preview passed, and only the approved run failed, with `coding_workspace_not_allowed`.

Changes:
- **One containment rule** (`capabilities/coding_change/workspaces.containing_root`). The run-python handler uses it at run time, and Workflow drafting uses it before anything runs.
- **Draft-time check.** `ChatAuthoring.check` refuses a fixed `coding/run-python` or `browser/operate` workspace outside the roots, and names the roots in the problem. A folder that is inside a root but missing is created at draft time, with `input/` and `output/`.
  - The resident Agent and external agents share this check.
  - `ExternalAuthoring` now reads the roots from `ChatAuthoring`.
- **The Agent is told.** The Gateway's system prompt and the `authoring__draft_workflow` description list the roots, and say to suggest a new folder under the first root, named after the task.
- **Live host.json** (backup `*-before-aep-workflows-root`): `C:\Users\Chi_L\Documents\aep-workflows` added as the first root.

Rejected alternative: widening the roots to `Documents\ChatGPT`. It would let scripts write next to this repository and would not stop the Agent from inventing the next folder.

## 2026-10-08: Workflow 13 runs up to the commit, as two approved Workflows

Decision (owner): migrate Workflow 13 `release_package` from `rs_workflow_system` (local checkout at the pinned revision) up to the commit. Push follows in a later round, still behind the owner's approval.

What was built:
- **Two Workflows.** The source's one job becomes `release-package-prepare` (resolve, checkout and write; it reports the plan and a fingerprint) and `release-package-commit` (commits only the reviewed fingerprint, and only if nothing has changed). Each is a separate approved run, so the commit has its own approval.
- **Settings.** Only a local origin inside a marked isolated root is accepted until push is approved. That keeps the real GitLab out of reach in this round.
- **Git runs without a shell.** It is called with an argument list. The commit text still follows the source's quoting rule, so both produce the same message.
- **Parity.** `benchmarks/w13_parity` runs the unchanged source job against AEP on identical repositories. All four cases matched.

Details: `docs/WORKFLOW_13_SOURCE_CONTRACT.md`.

Rejected alternatives:
- Prepare and commit in one run with one approval: the owner wanted the commit approved on its own.
- Running the source job directly as a script: that bypasses Bridge admission and grants (decision of 2026-10-03).
- Porting upload sets now: on AEP files arrive as attachments, and that route needs its own design.

## 2026-10-08: Agent Web opens from a desktop shortcut; the token still changes every start

Decision (owner): pasting the token address was tedious, so Agent Web now opens with one click.

How it works (`host_runtime/launcher.py`):
- **The server records its address.** `aep-host web` writes `<workspace>/agent-web.json` (address, port and process) once it listens, and removes it on stop. The workspace is under the user's own profile.
- **`aep-host open`.** It opens that address in the browser when the server answers. Otherwise it starts `aep-host web --schedules` in the background with no console window, re-reads the user's and machine's `AEP_*`, `LITELLM_*`, `ARTIFACTORY_*` and `OPS_*` variables from the registry, and then opens the page.
  - Output goes to `<workspace>/logs/agent-web-*.log`.
  - A record left by a server that died is discarded.
- **`aep-host shortcut`.** It puts "AEP Agent" on the desktop and in the Start menu. The shortcut runs `pythonw -m host_runtime.cli open --config <host.json>`.

Reason: the owner wanted it easier to open, and chose the shortcut over a fixed address.

Rejected alternative: a fixed token plus a cookie, so a plain bookmark would work. It would leave a long-lived key to the machine's Agent, and the owner did not choose it.

## 2026-10-08: Capabilities shows the owner's uninstalled drafts; the old authoring forms are gone

Decision (owner):
- **Two sections removed.** "Create a Workflow from an SOP" (the AuthoringStudio form) and "Create a Skill or Workflow draft" (the contribution form) are removed from Agent Web's Capabilities page. Workflows are now drafted in the conversation or by an external agent. Their backend routes stay for now, unlinked from the page.
- **A "我的草稿（尚未安裝）" card replaces them.** It sits under Installed and lists every Workflow and Skill candidate that is not installed. Each entry shows its steps or commands, its parameters, its last run, and the full draft.
  - **Install** is the owner's approval. `ChatAuthoring.install_now` makes an install request and decides it in the same press. A Workflow is reusable at once; a Skill takes effect after a restart.
  - **Delete** forgets the draft and closes its waiting requests as rejected. An installed version is untouched.

Reason: the owner approved runs of a drafted Workflow and then could not find it installed. "Run once" never installs, and nothing on the page showed drafts.

## 2026-10-08: An installed Workflow runs without asking again and works without a restart

Decision (owner): installing a Workflow is the approval. A run of the installed version, unchanged, does not ask again.

Changes:
- `authoring__run_workflow` runs a candidate directly when it is installed and its digest equals the installed digest. A revised draft is no longer the installed version, so it asks again.
- **Live registration.** On install, `ChatAuthoring.on_installed` registers the Workflow in the running engine and adds its grants to the running `LocalPolicy` (`LocalPolicy.add`). The Capabilities page and conversations can then run it immediately. Before this, running it said `workflow_not_installed` until a restart.

Page layout (owner):
- The draft list sits under the capability browser.
- "Agent profile" moved from Capabilities to Settings.

This supersedes the 2026-10-06 rule that every non-read run of a conversation Workflow waits for the button. That rule still applies to drafts and changed versions.

## 2026-10-08: Conversation feedback goes to the Shared Platform, queued locally until it answers

Decision (owner): a person's rating in Agent Web is uploaded to the Shared Platform, so Skills and Workflows can be improved. The upload carries the rating, the reason, the question and answer text, the tools used, the actor, the session and the trace. When the platform cannot be reached, the rating waits on the machine and is sent automatically once the platform answers.

This changes the earlier boundary (ARCHITECTURE "Conversation feedback uses a separate local contribution boundary"; conversations are "local-only"). From now on, rated exchanges leave the machine.

Scope (owner choices):
- Only ratings made from this release on are uploaded. Earlier ratings were given without knowing they would leave the machine.
- Agent Web only. Telegram has no rating yet.

How it works:
- **Wire.** A new Bridge operation, `feedback` (`common.sync.FeedbackRequest`/`FeedbackRecord`/`FeedbackReply`), authenticated by the device token. Every record must name the calling device.
  - There is one `feedback_id` per rated answer, so a newer rating replaces the older one. A late copy of an older rating never overwrites a newer one.
  - Question and answer are capped at 20,000 characters each, and a batch at 50 records.
- **Platform** (`control_plane/feedback.FeedbackStore`): a `feedback` table in the registry's SQLite file. `aep-platform feedback --config ...` prints it as JSON lines, newest first.
- **Host.**
  - `SqliteLocalState` schema 6 adds `feedback_outbox`. `set_message_feedback(..., queue=True)` keeps the rating and queues its record in one transaction.
  - `host_runtime/feedback_sync.FeedbackSync` runs inside Agent Web. It sends the outbox every 60 seconds, and soon after each rating.
  - A record leaves the outbox only when the platform acknowledges it, and only if it was not rated again while in flight. Without a platform binding, or while unreachable, records wait and their attempts and last error are kept.

Not done: a page on the platform for reading feedback (the CLI export is the reader for now), and Telegram ratings.

## 2026-10-08: MCP servers add capabilities to the Bridge from Agent Web Settings

Decision (owner): the Settings page gains MCP servers, so the Bridge can be extended through the Model Context Protocol.

Owner choices:
- **Connection:** a local command (stdio) or a remote URL (Streamable HTTP).
- **Permission:** adding a server makes all of its tools usable.
- **Use:** conversations, Workflows and coding.

How it works:
- **Client** (`integrations/mcp_client.py`, standard library only). The stdio client keeps one long-lived process, sends JSON-RPC lines and logs stderr to `workspace\logs\mcp-<name>.log`. The HTTP client POSTs, accepts JSON or an event stream, and keeps the `Mcp-Session-Id`. Both run initialize, then `tools/list` (paged) and `tools/call`, one request at a time per server.
- **Hub** (`host_runtime/mcp_servers.McpHub`). Settings live in `workspace\mcp-servers.json`, and servers connect in the background when Agent Web starts or a server is saved.
  - Each tool becomes the capability `mcp-<server>/<tool>@1.0.0`. It is `read` when the server marks it `readOnlyHint`, otherwise `external_side_effect` with approval required.
  - Each tool is granted to the host's actor with `approval_ref settings:mcp:<server>`: adding the server is the approval.
  - Each connected tool is offered as the conversation tool `mcp__<server>__<tool>` and dispatched through the Bridge (`CapabilityInvocation`). Host tools are added after Skill selection, so they are present during coding too.
  - A Workflow step can name the capability, and drafting finds it installed.
  - A removed or disconnected server's capability refuses with `mcp_server_unavailable`.
- **Secrets.** Secret environment values (stdio) and a bearer token (HTTP) are written only to the Windows user environment as `AEP_MCP_<SERVER>_<NAME>`. The page shows only whether one is present. Plain `env` and `headers` refuse credential-shaped values and an `Authorization` header.
- **Limit.** A coding/run-python script cannot call an MCP tool: its sandbox has no network. The Agent calls the tool in the conversation instead.

Rejected alternatives:
- The `mcp` Python SDK: it brings a web stack, and the protocol surface needed is small.
- Approving each tool or each call: the owner chose server-level approval.

## 2026-10-08: Harness telemetry for Atlas (aep.telemetry.v1, contract v0.2)

Decision (owner): expose the harness's state so real operation can be observed, strategy changes compared, and problems traced, without hurting performance. The target is the Atlas dashboard, with realtime tracking and history replay.

The owner supplied contract v0.1. v0.2 (`docs/telemetry/AEP_ATLAS_TELEMETRY_CONTRACT.md`) settles its problems:
- Atlas has no ingest or replay today. The owner chose to build the AEP side only, so AEP is the store and the stream.
- Atlas cannot send a token. The owner decided the reads need none. They are loopback only, GET only, and readable cross-origin only by pages on this machine, so other web sites stay out.
- `ingest_seq` is a host-wide stream cursor, beside the per-run `sequence`.
- New attributes `run_kind` and `parent_run_id`.
- `strategy_id` is generated from build, model, accelerator, limits and Skill versions, plus an optional `strategy_label`.
- Token usage that was not reported is null, not zero.
- Each harness gets a recommended state vocabulary.

How it works (`src/telemetry`):
- **Events.** `TelemetryEvent` with `sanitize`, which keeps metadata only and redacts credential-shaped text.
- **Recorder.** Runs and spans live in context variables, which flow through `asyncio.to_thread` and tasks. `emit` uses `put_nowait` onto a bounded queue, a writer thread stores batches, and nothing raises into the harness. Measured at about 8 µs per event.
- **Store.** `TelemetryStore` is `<workspace>/telemetry.sqlite` (WAL): idempotent by `event_id`, with a runs summary. Retention is 30 days or 500 MB (owner).
- **Hooks.** Agent Web routing, the Gateway loop (skill selection, model state, tool spans, truncation retry), every model call (`ApprovedModelClient`), every Bridge capability call, the Workflow engine (runs, steps, retries), the Knowledge harness runner (phases, verifications, retries) and the coding harness (plan, change, validate, repair).
- **Read API.** `/api/v1/telemetry/...` on Agent Web, with a WebSocket stream (backfill, then live). The CLI is `aep-host telemetry runs|export`.
- **Recording processes.** `web`, `ask`, `run-task`, `chat`, `telegram`, `jobs` and `schedules`.

Not changed: routing strategy, `ExecutionTrace`, Bridge authorization.

Rejected alternatives:
- A token on the reads: Atlas cannot send one, and the owner declined it.
- Writing synchronously on the caller's thread, as `jev-shadow.jsonl` does: it would add disk latency to every model and tool call.
- Building Atlas's ingest here: the owner kept it to the AEP side.

## 2026-10-09: One Harness skeleton for Coding, Workflow, Knowledge and conversation

Decision (owner, after reviewing `docs/HARNESS_DESIGN.zh-TW.md`): the four domains run on one skeleton, the shared plan → collect → execute → validate → retry state machine. Their differences live in Skills (guidance, evidence, Host checks, retry budget) and in domain adapters. The Workflow engine's journal and recovery, the coding runner's isolation and the Bridge's authorization stay as they are, as ways of executing. The Knowledge tool route returns the Harness-validated answer: option (a) of the paused choice. GUI benchmarks wait for the owner's absence.

Reason: the separate loops were history, not need. The Workflow engine and the Coding Harness predate the shared contract (G1/G2, 2026-10-04), and their loops duplicate it. The real differences are ways of executing and security boundaries, and the skeleton keeps them.

Rejected alternatives:
- Rewriting the Workflow engine's journal and recovery into the state machine: high risk to installed Workflows for no gain in control.
- Only patching gaps: it would leave four loops with different stop reasons, retries and evidence.

Plan: `docs/phases/HARNESS_UNIFICATION.md` (U1-U7).

## 2026-10-09: Claude Code reference answers for knowledge_v1, graded by key-point coverage

Decision (owner): Claude Code answers the coverage-selected questions first, and the Harness + company LLM answers are measured against those reference answers. The trial ran on 2 questions (Q0011, Q1001). Expanding to the 36 core questions waits until the comparison has been checked end to end (the owner chose this order to save Claude Code usage).

- **Reference.** `benchmarks/knowledge_v1/reference.py` runs `claude -p` headless in the Vault folder with Read, Grep and Glob only (no Bash, edits, web or MCP). It writes an answer, 2-8 key points each with a source file and a verbatim quote, and what the Vault lacks. Every quote is checked against the cited file; an unverified point is marked, not trusted.
- **Data exception.** This is the one place native Claude Code reads Vault content, which the PUBLIC rule otherwise withholds from external agents. It is allowed because host.json marks this Vault `privacy: public` and the owner approved the trial. Other Vaults or company data stay under the PUBLIC rule.
- **Grading.** `benchmarks/knowledge_v1/reference_grade.py` has the company Gateway model label each reference key point `covered`, `partial`, `missing` or `contradicted` in the AEP answer, and list claims the answer states as fact that the reference says the Vault lacks. Coverage is (covered + partial / 2) / key points. It is reported next to run.py's verdict and does not replace it: an answer can be right in other words or with other evidence.
- **Tool-route record.** A validated tool-route Knowledge answer now carries its record (the cited passages), its phase and its failure code in the host record, so citations can be checked as on the direct route. An unvalidated one goes back to the model without the record, to keep the observation small. knowledge_v1 grader 1.2 reads it. Traces recorded before this change are NEEDS_HUMAN_REVIEW, not FAIL.

Rejected alternatives:
- Claude Code as the grader of every run: it would spend owner usage on every benchmark run, while the reference is written once per question.
- Exact text match against the reference: a correct answer in other words would fail.

## 2026-10-09: Bilingual retrieval for wiki-primary Knowledge (Skill 1.7.0)

Decision (owner asked to fix the Harness after core-001): a Knowledge Skill opt-in, `bilingual_retrieval`, changes how the wiki-primary path retrieves; checks and citation rules are unchanged. Skill `company-agent/knowledge-query@1.7.0` turns it on; 1.6.0 moved to `disabled/`.

Investigation: the core-001 misses were not the facet check and not a missing retry. Retrieval missed the pages: for "What is EVM ...", `wiki/concepts/EVM.md` ranked 20th behind pages matched by the question template's words and by question-independent facet queries ("product option specification feature"). Measured against the files the Claude Code reference answers cite (22 answerable core questions, 120 files), one lexical pass found 12%. Many reference files are Traditional Chinese pages that English question words cannot reach.

What the opt-in does, measured as one set (recall 0.12 → 0.26; questions with at least one reference file 9 → 16 of 22):
- The Gateway model writes up to six bilingual keyword queries before retrieval (`knowledge/query_rewrite.py`). A failed rewrite leaves retrieval as before.
- English function words are dropped from query ranking.
- Facet queries carry the question's own words when no subject or focus prefix names them.
- 36 Wiki sections are kept instead of 24.

Each change alone gave 0.11-0.20. A larger budget alone reached 0.23 with 48 sections.

Rejected alternatives:
- Changing the facet trigger for definition questions: the facet was covered once the right pages were retrieved.
- Tuning focus-hint expansions per market: fits the benchmark's grid, not retrieval in general.
- A model-driven multi-round search, as Claude Code and NousResearch hermes-agent do: likely the next step if recall stays low. It changes the Harness's retrieval step, so it waits for the owner.

Also fixed: the tool route's `failure_code` is read from the capability result, not the outcome root.

## 2026-10-10: Knowledge Skill 1.8.0 holds answers to links their passages state

Decision (owner: try Skill guidance first, then multi-round retrieval only if it does not help): `company-agent/knowledge-query@1.8.0` changes only `answer_guidance`; 1.7.0 moved to `disabled/`. The new rules:
- A product is claimed to fit a market, application or customer only where a cited passage states that link. Otherwise the answer gives the product facts and writes 知識庫未證實 for the link, including under `推薦先賣`.
- Nothing is ranked (strongest, most important) unless a passage ranks it.
- No table cell or heading states a link the passages do not.
- The instructions' own evidence rules and facet names (such as `direct_relationship`) are never presented as findings or cited.

Reason: in core-002, the new FAILs came from the reviewer finding the answer's main claims beyond its passages. Three patterns did that: products recommended for a market no passage tied them to (Q0196, Q0351); the Host's evidence rules quoted as cited findings (Q0039, Q0339); and an inferred chain put into a table (Q0871). The old guidance required a `推薦先賣` section for every product/market question, which pushed the model to recommend.

Measured by `runs/core-003` against `runs/core-002`. If it does not improve, the next step is model-driven multi-round retrieval (owner, 2026-10-10).

## 2026-10-10: Model-directed search rounds for wiki-primary Knowledge (Skill 1.9.0)

Decision (owner: "try it" after 1.8.0 left coverage flat): the wiki-primary Knowledge capability may run model-directed search rounds after its first retrieval. The design is `docs/phases/KNOWLEDGE_MULTI_ROUND_RETRIEVAL.md`.
- The Gateway model sees search results and marks relevant pages.
- It asks for new searches; the Host runs them and reads only pages a search showed.
- Citation and Host checks are unchanged.
- A Skill opts in with `retrieval_rounds` (0-3, default 0). Skill 1.9.0 sets 2.

Result (`runs/core-004`): reference files offered to synthesis rose from 22% to 41%, and those cited from 17% to 26%. Answer key-point coverage stayed flat (0.28 to 0.30). Contradictions fell from 7 to 4. Median latency rose from 137 to 200 s. The limit has moved from retrieval to synthesis. The owner kept 1.9.0 (2026-10-10): better grounding is worth about 60 s more per answer.

Rejected alternatives:
- Giving the model file-reading tools directly: the model would supply evidence text and step outside the Bridge capability's boundary.
- An unbounded loop: cost and latency without a stop.

## 2026-10-10: Knowledge Skill 1.10.0 widens the evidence synthesis reads

Decision (owner: "try improving synthesis; roll back if worse"): the wiki-primary evidence budget is a Skill setting (`evidence_sections`, `evidence_chars`, `evidence_sections_per_page`). Skill 1.10.0 sets 64 sections, 80,000 characters and 8 sections per page, and its guidance asks the answer to state each cited fact for every part of the question.

Reason: of the reference key points missing from core-004 answers, 26 of 33 sat on a page synthesis saw but in a section it was not given (three sections per page). Offline, the wider budget raised the share of reference quotes present in the evidence from 0.21 to 0.29.

Result (`runs/core-005`): coverage on the 22 answerable questions rose from 0.30 to 0.40, and on the 14 insufficient ones from 0.18 to 0.29. FAIL went from 3 to 4 and contradictions stayed at 4. Overreach items rose from 35 to 63. The change was kept under the owner's rule, and overreach is the next point to work on.

Rejected alternatives:
- Changing the guidance alone: 7 of 33 misses were synthesis omissions, while 26 were evidence never offered.

## 2026-10-10: Benchmark progress and results go into Harness telemetry (contract v0.3)

Decision (owner: watch test status and results live in the Atlas dashboard, with replay; build the Atlas side too where accessible): benchmark runners write `benchmark_run` runs, and knowledge_v1 reference grading writes `benchmark_grading` runs, into the Host's `telemetry.sqlite` through `src/telemetry/benchmark.py`.
- Events are `benchmark.case_started`, `benchmark.case_completed` and `benchmark.case_graded`, with the verdict, tags, checks and the answering `aep_trace_ids`.
- Agent Web's read API and stream carry them unchanged. `/runs` gains `trace_id` and `parent_run_id` filters for the drill-down.
- Attributes are metadata only. `sanitize` also drops content keys.

Reason: the runners are separate processes, and the stream already polls the store. Writing to the store directly needs no new channel and no Agent Web endpoint that accepts writes.

Atlas side: Codex had already built the AEP consumer in the Atlas working tree, uncommitted. Claude Code added benchmark views and an "AEP Benchmarks" dashboard on top. That work is uncommitted for the same reason, and is handed off in Atlas `docs/HANDOFF.md`.

Rejected alternatives:
- A write endpoint on Agent Web: it widens a loopback API the owner chose to keep read-only.
- Atlas reading benchmark files directly: it would miss the live view and the trace link.

## 2026-10-10: Knowledge targets after calibration; no-support replies; Skill 1.11.0

Decision (owner agreed): the knowledge_v1 coverage target is a 0.50 mean on the 22 answerable core questions, not 0.7. Overreach is tracked beside coverage and should fall.

Calibration (`benchmarks/knowledge_v1/references-b/`): a second, independent Claude Code answer reaches 0.53 against the reference, graded in the same direction as AEP (0.60 both ways). On those five questions AEP scores 0.50. Coverage of 0.7 is above what a second strong answer reaches, and chasing it would mostly lengthen answers and add overreach.

Two changes followed from the per-question analysis of core-005:
- **Harness (839711b).** A short reply whose opening says no passage supports an answer no longer passes `answer_nonempty`, even with a citation, so the Skill's retry runs. If the retry gives the same reply, it is shown unvalidated. In Q0296 the retry returned "no passage supports…" and was validated, while the same evidence gave a 10,000-character cited answer on another try.
- **Skill 1.11.0 (guidance only).** The product table drops the speculative "為什麼適合" column. The scenario table lists only scenarios a passage names and has an evidence column instead of "切入重點". A sentence that does not restate a cited passage goes on a labeled inference line or is left out. Reason: overreach clustered in answers longer than 10,000 characters, inside those speculative columns.

Measured by `runs/core-006` against core-005.

**Result: rolled back (2026-10-10).** core-006 was worse. Answerable PASS fell from 17 to 12 and FAIL rose from 4 to 7, with 1 timeout. Coverage fell from 0.40 to 0.37. Overreach fell only from 65 to 57. Median latency rose from 156 to 206 s, and p90 from 236 to 429 s.
- The no-support check fired on more replies than intended, and its retries added minutes.
- The 1.11.0 guidance left some answers not addressing the question.

Code reverted in ca110b0. Skill 1.10.0 is live again (1.11.0 is in `disabled/`). Review: `runs/core-006/review.zh-TW.md`.

## 2026-10-11: Knowledge pipeline release direction

Decision (owner): Knowledge convert, ingest, query and lint/conflict are released inside Agent Web, as a "Knowledge" page plus conversation, not as a separate app. Everyone analyses data with the Karpathy LLM Wiki schema Skill plus their own domain Skill, and access to a vault is controlled by the vault itself. The first domain is the 5 market × 4 product-line vault, with a customised domain matrix Skill.

Concurrent ingest does not write to the published vault. Each person ingests into a sandbox (a candidate vault, on the existing `knowledge_evolution` flow), scoped by the domain Skill, and merges back. The merge does a three-way comparison by section, then lint, a conflict scan and domain validation, then approval. Conversion covers Excel (tables kept as tables; charts become a number table plus an analysis summary), HTML and legacy `.ppt`. Images use gpt-5.5/5.6 or Copilot.

Reason: the Personal Agent is the product's main interface. Skills, approvals, Harness validation, telemetry and Knowledge versioning already live there. A write lock alone prevents simultaneous writes but not semantic interference on shared pages.

Rejected alternatives:
- A standalone app: it would duplicate the Skill system, approvals and the model gateway.
- Git on the OneDrive-synced vault: sync corrupts `.git`.
- Two parallel language copies as authoritative pages: they drift, and translation errors would become evidence. Use bilingual aliases and summaries, and retrieval-only derived translations if needed.

Plan: `docs/phases/KNOWLEDGE_PIPELINE_RELEASE.zh-TW.md` (K1-K6).

## 2026-10-11: Owner mode — what this computer may do, its owner may do

Decision (owner chose option 1): on a local host, one without the shared platform's member decisions, authorization follows the person.
- **Owner holds everything.** The device owner (the active membership binding) holds every installed capability. No `grants.json` entry is needed; one written there is kept as written.
- **A person's request runs.** A request the person makes runs without a recorded approval: an Agent Web button, the CLI, or a Workflow they installed or started (`CapabilityInvocation.origin = "person"`). Writing steps should offer a dry run or preview first, as the Knowledge pipeline does.
- **A model's side effect waits.** A side effect the conversation model chose by itself (`origin = "model"`, set by the Gateway) is not run. The Bridge returns `approval_required`. Showing an Approve button in the conversation that runs it as the person is the next step.
- **Reads run** whoever asks.
- **The switch.** `host.json` `local_owner_grants` (default `true`). `false` restores the strict rules: an explicit grant with an `approval_ref` per side-effecting capability. A host with control-plane member decisions keeps the strict rules regardless.

Reason: the owner found per-capability grants and approval references a burden on their own computer. The risk the approvals guard against is the model acting on its own, for example on instructions hidden in an ingested document. Owner mode keeps that guard and drops the bookkeeping. The capability-spec rule is unchanged (a side effect must declare an approval policy); in owner mode a person's request satisfies it.

Rejected alternatives:
- Removing confirmation for model-initiated writes too (option 2): ingested PDFs, web pages and slides can carry instructions.
- Keeping `grants.json` mandatory: the bookkeeping the owner asked to remove.

Tests: `tests/test_owner_policy.py` covers owner mode. The shared host fixtures in `tests/test_host_wiring.py` set `local_owner_grants: false`, so the existing grant tests still verify the strict rules.

## 2026-10-11: K2 layered bilingual index — owner agreed

The owner agreed to the three points in `docs/phases/KNOWLEDGE_K2.md`:
- **Categories:** 5 markets, 4 product lines, technical, companies, and sources by year.
- **Cost:** about 100 company-model calls to write bilingual `aliases` and `summary` for all pages.
- **Scope:** all K2 changes stay in a sandbox of `rs-k` until the K3 merge.

## 2026-10-11: K2.4 index-led retrieval reverted after core-007

Decision: the K2.4 change (query and ingest walking the layered index; e097aa0) is
reverted (405e9d7) under the owner's rule that a change that makes results worse is
rolled back. On the 36 core questions against candidate `rs-knowledge@1.1.0-k2.1`
(core-007), answerable coverage fell from 0.395 to 0.349 and PASS from 16 to 11 of
22; p90 latency rose 21%. The change also altered retrieval on the live flat index.

Kept: K2.2-K2.3 (enrichment and index build act on sandboxes only) and the enriched
sandbox. Not chosen yet: re-measuring data and code separately, or limiting the
index to ingest planning; the owner decides (see the core-007 review).

## 2026-10-11: The layered index serves ingest; query keeps the flat list

Decision (owner, after core-008): the layered bilingual index is used for ingest
planning (pick at most 3 categories, then choose pages among them), while query keeps
ranking the previous flat index list, read from `wiki/index/all.md` once `index.md` is
layered. Pages under `wiki/index/` are never evidence.

Why: both measured ways of letting the layered index drive query were worse
(core-007 0.349, core-008 0.386 vs core-005 0.395 answerable coverage). Keeping the
flat list makes the K3 merge of the layered index neutral for query: offline, the live
vault and the K2 sandbox return identical passages on the 36 core questions (180/180).

Rejected for now: index lines taking search slots (core-007); a category-only
`index.md` as query navigation (core-008). Still open: bilingual lines as an addition
to the flat list.

## 2026-10-11: K3 ingest rules live in the vault; one approval publishes a merge

Decision (owner), spec `docs/phases/KNOWLEDGE_K3.md`:
1. The ingest schema (`CLAUDE.md`) and the per-category rules
   (`skills/ingest-<category>/SKILL.md`, chosen by the source's Raw folder) live in the
   vault, so domain owners edit them in Obsidian without a platform release. Rejected:
   packaging them as platform Skill assets (each change would need a reinstall).
2. Rules follow the owner's four data categories (Market, Productions, Knowledge,
   Competitor); merge-review scope follows the 5 markets x 4 product lines matrix through
   `index_categories`, and out-of-domain or shared-page changes are marked "proposal",
   not blocked.
3. Publishing a merged Knowledge version needs one person's confirm click; per-domain
   approval was not required.

## 2026-10-11: Knowledge collaboration works like branches and pull requests

Decision (owner), design `docs/phases/KNOWLEDGE_COLLAB.md`:
- Workflow: Pull -> edit skills -> Convert -> Ingest -> Benchmark -> Push.
- The project vault (the team's shared folder) is configured per project; for this
  project it is OneDrive `RS_Knowledge`. Nothing is tied to that folder.
- Pull copies chosen `drop/` folders (any depth) into a sandbox; the pulled folders are
  the sandbox's scope.
- Benchmark questions follow the drop folders: `checks/questions/<folder>/` and
  combinations such as `market_productions/`; a sandbox runs the sets inside its scope by
  default and the maintainer can adjust them. Grading is the owner's existing
  must-mention / must-not-say string match.
- Co-developers may push without a second approval. A push merges three ways into the
  project vault, records who pushed and from which sandbox, and keeps backups.

Why: several maintainers will develop one vault; sandboxes, section-level merge, scoped
benchmarks and push records keep their work from colliding or silently degrading
another domain. Rejected: git in the OneDrive folder (sync corrupts `.git`).

## 2026-10-11: Knowledge pushes have no lock; a benchmark gate decides

Decision (owner): no file lock while maintainers work. The first push wins; a later push
re-merges against the current project vault and is allowed only when no question
regresses and its merged result scores no lower than the vault (a regression blocks).
The first live pushes go to a copy of RS_Knowledge.

Rejected: an SVN-style push lock with a timeout.

## 2026-10-11: Category rules layer from general to specific

Decision: every skill whose `applies_to` folder holds a source applies, ordered from the
general to the specific (`raw/Productions` then `raw/Productions/VNA`), instead of only
the most specific one. Product lines under a category (owner question: four product
lines, each with its own skill) then share one `ingest-productions` and add only their
own rules. Question-set defaults count every folder of a pulled path.

Rejected: most-specific-only selection (K3.1), which would force each product line's
skill to repeat the shared rules and let them drift apart.

## 2026-10-12: Knowledge answer quality — three accepted changes after a fresh baseline

Owner request: "with the current data, see whether the harness can be improved further".
A fresh baseline on HEAD 0be2b14 with Skill 1.10.0 (`runs/core-009`) gave answerable
coverage 0.372, 21 PASS / 6 INSUFFICIENT / 8 FAIL of 36, median 185 s, p90 329 s
(core-005 two days earlier: 0.395, 156 s). Each candidate was measured on the same 36
questions and kept only if answerable coverage beat the baseline and median latency
worsened by no more than 20%.

1. **C1, kept (core-010): the person's question reaches the vault unchanged, and
   retrieval is reused.** The conversation tool `knowledge__rs-knowledge` was described by
   the old `engineering/knowledge-query@1.0.0` Skill ("can answer only with citations to
   Raw evidence"). The conversation model rewrote 25 of 26 tool questions in core-005,
   adding "cite Raw evidence", a focus, product names or "rank by strength"; synthesis then
   cited only the four Raw fallback passages and answered that nothing supports the
   question (Q0296, Q0546, Q0911, Q0051). `engineering/knowledge-query@1.0.1` (1.0.0 in
   `disabled/`) and the vault tool's `question` description (9d0d74c) now ask for the
   person's own words with no added instructions. Separately (204dcfa), the retrieval
   snapshot is kept per Vault until any file under it changes and large-corpus BM25
   statistics are memoized; retrieval output is identical (22/22 questions) and about ten
   times faster. Result: coverage 0.423, 26/2/8, contradicted 27 -> 12, median 72 s.
2. **C2, kept (core-011): evidence spread over more relevant pages.** Search rounds read up
   to 20 relevant pages (was 12), every page gives its best three sections before any page
   goes deeper, and sections are ranked by the question plus its bilingual rewrites
   (43dcd76). Skill `company-agent/knowledge-query@1.12.0` raises `evidence_sections` from
   64 to 96 (the contract bound rises to 128); 1.10.0 is in `disabled/`. Offline, reference
   quotes present in the evidence rose 0.34 -> 0.44. Result: coverage 0.466, invented
   67 -> 54, median 84 s (+17% on C1). run.py PASS fell to 23 because its reviewer sees
   only the first 16 cited passages; with up to 48 visible, PASS is 29 vs C1's 28.
3. **C3, kept (core-012): the first draft cites every line.** 7 of 8 first drafts failed the
   unchanged citation preflight only on uncited lead-in, short-answer or gap lines, so
   almost every answer paid a fresh, shorter rewrite. A prompt paragraph asks for that form
   (425c5f6). Questions needing only one synthesis call: 3 -> 13 of 26. Result: coverage
   0.477, 28/2/6 (33/2/1 with the wider reviewer window), median 74 s, p90 115 s;
   invented 54 -> 67.

Not changed: Host validation and grounding rules, refusal behaviour, the number of Harness
phases and model calls, references and the question bank.

Remaining gap: in core-012, 42 of 56 missing and 33 of 64 partial answerable key points sit on
pages that never reached synthesis, while all 283 reference sources exist in the Vault.
Retrieval, not data, is the limit. Structural options for the owner are in HANDOFF.md.

Rejected alternatives:
- Passing the person's raw message instead of the tool argument: follow-up questions need the
  model to make them self-contained.
- Treating uncited bold labels as formatting in the preflight: it changes the grounding rule,
  which needs the owner.
- A larger evidence budget (128 sections): offline gain over 96 was small (0.44 -> 0.48) for
  about 20% more synthesis input.

## 2026-10-12: Run the last search plan's queries, outside the evidence budget

Decision (owner chose proposal 1): the final planner round's searches, previously
dropped, run; the best section of up to three pages per query is added after the
evidence budget. Kept after core-013: answerable coverage 0.477 -> 0.508, median latency
+12% (rule: no more than +20%). Rejected placements, measured offline: inside the budget
at the end (no effect, the budget was already full) and ahead of deeper sections (more
reference pages but fewer reference quotes).
Caveats: one run; run.py PASS fell 28 -> 25 with changes in both directions; p90 +26%.

## 2026-10-12: Proposal 1 rolled back after a repeat run

Decision (owner): revert 677e18a. A repeat run (core-014) put the coverage gain at about
0.02 (0.477 -> mean 0.500), near run-to-run noise, while Q1041 and Q1061 turned from
answered to "not validated" in both runs. Grader 1.4 (48 cited passages) is kept.
Making wider evidence pass validation would touch the validation rules (proposal 2).

## 2026-10-12: Answer rules live in the vault too

Decision (owner): domain experts must be able to change how questions are answered, not
only how data is ingested. A vault skill with `mode: answer` (optional `topics: [..]`)
is appended to the synthesis prompt after the installed Knowledge Skill's guidance and
before the citation form; the platform's citation and grounding rules still apply. A
vault without answering skills answers exactly as before. Each skill is capped at
6,000 characters. Existing `skills/ask-*` files without `mode: answer` are ignored, so
nothing changes until a rule is written for this platform.

The owner's `ask-knowledge` came from another project (code graph, Hermes and Claude
Code examples, an uncited follow-up section that would fail citation checks); it is
rewritten as `src/knowledge/skill_guide/answer.SKILL.md`. The writing guide and the
ingest template ship beside it and are shown on the Knowledge page.

Rejected: routing questions to an ask skill by a model call (one more call per
question); concatenating every `ask-*` file regardless of `mode` (old files would
change answers unannounced).

## 2026-10-12: Publish rs-knowledge 1.0.3 with the vault answer rule

Decision (owner, option A): publish the exact candidate measured in core-015 (1.0.2
content plus `skills/ask-knowledge/SKILL.md`) as rs-knowledge 1.0.3 so users get the
better answers now, instead of waiting for a Refresh from the project vault. Rollback:
restore the host.json backup (1.0.2 vault and manifest are kept) and restart.

## 2026-10-12: Experience review defaults

Decision (owner), design `docs/phases/EXPERIENCE_REVIEW.md`: collect every signal already
recorded; review nightly when there are new cases (and by hand); conversation excerpts
may go to the company model endpoint with secrets redacted; domain owners review
vault-rule proposals and the owner reviews platform Skill proposals; case retention is a
user setting with a 30-day default.

## 2026-10-12: GitHub Copilot as an agent mode with AEP assistant tools

Decision (owner), design `docs/phases/COPILOT_INTEGRATION.md`: integrate GitHub Copilot
(company-approved, one account per user) as a selectable Agent Web conversation mode
while AEP's harness matures; the AEP harness stays the default. All data may be sent to
Copilot. Copilot gets AEP's assistant tools (Knowledge search/read/ask, installed
Workflows) over MCP served by the running Agent Web; file writes and shell stay denied
and Workflow side effects still need the person's approval.

This changes the external-agent data boundary for the assistant tools only: the
authoring tools keep returning statuses and codes.
Rejected: letting Copilot read the vault folders directly (no access control, no
record, not pinned to the published version); a stdio MCP server per turn (rebuilds
the Host each time).

## 2026-10-13: Rule changes are tried by re-ingesting Raw, not by pulling again

Decision (owner accepted the proposal): Pull keeps skipping originals that are already
ingested, because their Raw is already in the sandbox; its message now says so, names
the Raw documents and can tick them in the Ingest step. After a skill change the
maintainer re-ingests ticked Raw (a folder or a hand-picked sample) with the current
rules as a background run (`host_runtime/knowledge_reingest.py`): each document goes
through the same `ingest-plan` and `ingest-apply` steps a person presses, a clean plan
is applied in the sandbox, and a plan with problems or contradictions waits for the
person to compare and apply. The run can be stopped and continued; its record lives in
the sandbox's `.reingest/`. Recommended practice: try a small sample first, then the
whole folder, then benchmark and push.
Not done: a Pull option to convert already-ingested originals again. Raw is write-once
and content-addressed, so the same original converts to `duplicate`; re-converting
would change that architecture and is only needed when the converter itself changes,
which vault skills do not control. Left for the owner to decide.
Rejected: re-ingesting everything automatically after each rule save (hours of model
calls, many shared pages changed at once, more push conflicts).

## 2026-10-13: A sandbox maintains one folder and edits only its rules

Decision (owner): merge Pull and Rules into one Knowledge-page step. The scope is one
project-vault folder chosen when the sandbox is created; Pull accepts only it and its
sub-folders. Its ingest and answer skills (by `applies_to`; legacy answer skills by the
name `ask-<folder>`) are editable; more general layers and `CLAUDE.md` are read only;
other folders' skills are hidden. The pipeline refuses out-of-scope rule writes. Answer
skills may now carry `applies_to` to name their owning folder; ingest rule layering
ignores answer skills. Design: `docs/phases/KNOWLEDGE_COLLAB.md` section 4.
Rejected: listing every skill for every sandbox (unclear ownership, edits to other
domains' rules), and making the general layer editable from a product-line sandbox
(changes every product line).
