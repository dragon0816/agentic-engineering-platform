
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

## 2026-10-13: Laya settings on the Settings page, tunnel kept by Agent Web

Decision (owner): host.json gains `laya` (SSH host, port, account, remote and local port,
automatic tunnel, mode off/shadow/active, threshold, timeout, approval reference), edited
on the Settings page; `decision_accelerator` is derived from it and always points at a
loopback port. Agent Web may keep the SSH tunnel open itself in batch mode (no password
prompts) and reopens it when it drops. Host and account are validated names placed after
`--`/`-l`, so they cannot inject ssh options.
Rejected: accepting a plaintext LAN endpoint (the loopback-or-HTTPS rule stays); storing
an SSH password (keys only).

## 2026-10-13: Releases for colleagues are built from the committed revision

Decision (owner request): one command (`scripts\release.cmd`) makes a deliverable release:
verification, then the platform wheel and the bundle's scripts and manuals from
`git archive HEAD`, the CI dependency list for 64-bit Windows Python 3.12, the existing
hash-verified bundle builder, and a release folder with release notes since the previous
release. Updates use `update.cmd`, which reuses the installed user and Bridge ID and keeps
host.json and the workspace. Rejected: building from the working tree (uncommitted changes
would ship under a revision that does not contain them); a self-extracting .exe (the zip
with `install.cmd` already installs offline and keeps the per-file hash check).

## 2026-10-13: Review proposals are decided by a person; push carries question sets

Decision (owner chose the full experience review): every review finding with a proposal
is stored and shown on a Reviews tab. A person accepts, rejects (reason required, so the
same cases are not proposed again) or snoozes it. Accept never changes a running system:
a vault rule edit or a draft test question opens a review sandbox that goes through the
normal benchmark and push gate; missing knowledge goes to a gap list; platform issues
are tracked. To let questions reach the project vault, merge and push now include
`checks/`; a scoped sandbox may edit only the question sets named for its folder
(`market`, `market_production` for Market), never the general set or other folders'.
Rejected: applying accepted rule text directly to the project vault (bypasses the
benchmark gate); letting any sandbox edit any question set (could weaken another
folder's gate).

## 2026-10-14: The Knowledge tab is a three-step guide

Decision (owner): the maintenance flow is shown as three steps with one page each and a
stepper to move freely: Pull data (pull, add files, convert), Ingest data (edit the
folder's skills, ingest) and Testing data (questions and their coverage, test, push).
Element ids and the pipeline calls are unchanged, so the steps only regroup existing
features; advanced tools stay folded under step 3. Coverage is a stated guideline (at
least 5 graded questions, about one per 10 Raw documents), not a gate.
Rejected: one long page with numbered cards (the previous layout: too much at once).

## 2026-10-15: Workflow 13 gets its push, behind a setting and its own approved run

Decision (owner asked for n8n workflow 13 to be ported in full and installed, with no
n8n): the release run gains a third Workflow, `engineering/release-package-push`
(capability `release-package/push@1.0.0`, `external_side_effect`, risk high, approval
required). It pushes only the commit that `release-package-commit` made and recorded in
the checkout's `.git`, and only when the branch, HEAD, a clean working tree and origin
still match. It runs `git push -u origin <branch>` as the source does, never forced; a
branch that moved on origin is refused by git and reported, not retried.

The settings reach the real release repository only when the per-install
`remote_release` setting is on (default off). Then `release_repo_url` must be an https
or ssh URL with no user, password or token in it (git's own credential manager answers,
never prompting); the working copy and inbox must still lie in a root carrying the
`.aep-isolated-release-root` marker, as the source required `terminal.allowedRoots`.
With the setting off, the 2026-10-08 rule stands: a local origin inside the marked root.

The three release capabilities (prepare, commit, push) are registered when an installed
Workflow uses them or when the install already holds Workflow settings for one of the
release Workflows (`workflow-settings.json`). That is how a host that does releases says
so before the Workflows exist, so they can be installed like any draft (`aep-host assets
submit-workflow`, then the owner's Install in Agent Web). Grants come only from that
install. Registering them on every host was tried and rejected: every host would then
advertise release capabilities to the Shared Platform.

Rejected alternatives:
- Pushing from the commit step: the owner wanted each effect approved on its own.
- Allowing any remote whenever push exists: an install that was set up for the isolated
  test root would then reach GitLab without anybody choosing it.
- Writing the manifests and grants into the live workspace directly, as earlier slices
  did after a conversational yes: that is the model approving its own install.

## 2026-10-15 — Workflow forms v2 and one release Workflow

Decision (owner, items A, B, C): the parameter declaration gains `allow_other`
(a `select` whose list is a suggestion), Agent Web resolves `fn:` lists like
`ref:` sets, Telegram offers multi-select buttons (up to 96, toggled in place, then
Done), a built-in `fn:folder_files` lists the files of a folder named by a setting
or an earlier field (bare names only), `kind: upload` becomes a real upload into a
per-run folder under the workspace (25 MB a file, `accept` enforced, sanitized
names; the engine rejects an upload value outside that store), and identity-group
values are remembered per member and Workflow for "same as last time". Placeholders
in a choice source may name static settings. Workflow 13 becomes one Workflow,
`engineering/rs-wmt-package-release@1.0.0` (prepare, commit, push in one run; dry run
on and push off by default; started by name, no numeric alias; alias 13 removed from
the preview). The prepare step accepts uploaded files only from the host's upload
store and copies them straight into the branch. Design:
`docs/phases/WORKFLOW_FORMS_V2.md`.

Reason: authors should only declare parameters; the n8n-era dashboard and bot
offered combo boxes, multi-select buttons, uploads and identity presets, and the
port had fallen back to text boxes and three hand-chained runs (branch, fingerprint
and commit typed by hand).

Rejected alternatives:
- `allow_other` with `multiple`: a multi-select combo has no plain HTML control;
  not needed by any Workflow yet.
- Copying uploads into the release inbox: it would write a folder the person
  curates and mix runs; the step reads them from the store instead.
- A new combined release capability: the three proven capabilities chained by step
  inputs keep each effect's classification and approval policy.
- Keeping the engine's choice check for `allow_other` fields: a slow index would
  block runs the owner wants to go through with a typed value.
- Storing presets in browser storage: Telegram and Web would not share them.

## 2026-10-15 — Bridge self-enrollment and assets-only sync beside grants.json

Decision (owner): build Bridge enrollment to the Shared Platform
(`docs/phases/BRIDGE_ENROLLMENT.md`). A member's own Agent enrolls its company
workstation through the Member Portal (`bridges/enroll`, member session from the
`Personal Agent` login). The platform registers or reuses the device, binds the member
as `device_admin` and returns a 90-day Bridge token once; enrolling again rotates it.
Administrators list Bridges and can disable one (its tokens are revoked). The Member
Portal URL that "Open Marketplace" uses is set by the user in Agent Web Settings; the
one field feeds `publishing.member_portal_url` and `platform.member_portal_url`. The
token is kept for the Windows user as `AEP_SHARED_PLATFORM_TOKEN`, so an older
platform's token variable is untouched, and the running Agent switches without a
restart. For a PC with a hand-written workspace `grants.json`, the owner chose option
(a): **assets-only sync**. Sync installs the selected Skill and Workflow files but
writes the device bundle to `platform-selections.json` (display only) instead of
`authorization.json`, so `grants.json` keeps deciding what the PC may run; the
Library says so.

Reason: the publish half (PC to platform) was live; the install half needed a Bridge
token that only tests could issue. Asking the member to paste a second credential
would add a step for no security gain, since the member's own session is the
authority to enroll their own computer. Option (a) lets this PC receive published
assets today without silently changing what it may run.

Rejected alternatives:
- (b) Rename `grants.json` away and let the platform's bundle decide: the intended end
  state for colleagues, but it changes what this PC may run today.
- (c) Keep refusing sync while `grants.json` exists: this PC could never install from
  the platform.
- An administrator-issued token pasted into Agent Web: an extra secret to move by
  hand, and the platform cannot tell it was the member who asked.
- Reusing `AEP_LOCAL_PLATFORM_TOKEN`: it would overwrite the old local platform's
  token and mix two platforms' credentials in one variable.
- Self-enrolling a shared test workstation: it has a virtual member of its own; it
  stays an administrator's act.


## 2026-10-15 — Owner and who can use a member-published asset

Decision (owner): after the live finding that `leo`'s two published assets were
invisible to `leo.chi` (`docs/phases/MEMBER_PUBLISH.md`, "Owner and who can use
it"):
1. A submission for a new name keeps the team or organization owner its manifest
   declares when the submitter belongs to that group; otherwise the submitter owns
   it. An existing name keeps its recorded owner.
2. The publisher chooses the visibility when submitting (optional
   `AssetSubmitRequest.visibility`; Agent Web select and `--visibility`).
3. After publication the name's owner, a member of an owning team or a platform
   administrator changes who may use it in the Member Portal. The decision is a
   `NameAccess` record beside the name (visibility override plus extra members and
   groups) in an additive `name_access` SQLite table; `schema_version` stays `1`.
   `entitled` takes the record, and every caller goes through
   `control_plane.distribution.entitled_in`, so catalog, select, replace and the
   Bridge catalog agree. Narrowing access does not withdraw existing selections.
4. Portal: valid-account placeholder and in-page check, a `reason`/`message` for
   refused names, transparent session renewal from the stored login.
5. `aep-host assets publish --file` and a read-only sample Workflow for the live
   sync test.

Reason: a team-declared asset owned by the person who happened to publish it is
invisible to the team; and because packages are immutable, the only way to fix
access after publication without a new version is a record beside the name, as
deprecations already are.

Rejected alternatives:
- Keeping any declared owner: anybody could publish in another person's name.
- Republishing a new version to change visibility: needs another review and leaves
  older versions with the old answer.
- Storing access inside the `name_owners` payload: code from before this change
  parses that record strictly and could no longer open the database; a separate
  table stays invisible to it.
- Withdrawing selections when access narrows: would remove what a member already
  installed, unlike deprecation; left for a later decision.
- Refusing combinations that leave nobody but the owner (e.g. `team` on a
  person-owned asset): the owner chose to keep it simple; the dialog explains the
  effect instead.

## 2026-10-15 — Switching off, removing and adding assets from Agent Web Capabilities

Decision (owner request 2026-10-15, Capabilities redesign; design choices by Claude
Code, to be confirmed by the owner):
1. **Switch off / on.** An installed Skill or Workflow is switched off by moving its
   manifest into its kind's `disabled/` subfolder
   (`assets\skills\disabled`, `assets\workflows\disabled`). The host reads only the top
   level of those folders, and installing a newer Skill already sets older versions
   aside there, so "superseded" and "switched off" are one state. The running engine
   stops offering it at once (`InstalledWorkflows.remove`, `SkillRegistry.remove`). A
   Skill is not switched on while another version with the same alias is on
   (`alias_in_use`), because the host refuses to start with two.
2. **Remove from this Agent** never deletes. The file moves to
   `workspace\removed\<YYYY-MM-DD>\{skills,workflows}\` (a second removal of the same
   version that day gets a time suffix), a line is appended to
   `workspace\removed\removed.jsonl` (at, actor, kind, asset, from, to), and the
   inventory row in `state.sqlite` is dropped (`SqliteLocalState.forget`), so the asset
   is neither offered nor reported, and a later sync may install it again. Putting it
   back means moving the file back. When the platform still selects it for this PC
   the reply says so (the next sync would reinstall it) and points to "Remove
   selection". Removing does not revoke the selection on its own.
3. **Shipped manifests are refused** for removal (`shipped_asset`): the host does not
   re-install them at start-up, but `aep-host export-assets` (install and upgrade)
   writes them back, so a removal would not last. They can be switched off.
4. **"+ Add to this Agent"** is one action: the Agent calls the Member Portal `select`
   as the member (Personal Agent login, never the Bridge token) for this PC's Bridge,
   then runs the existing verified sync, and the reply carries the new catalog and the
   installed list so the page redraws without a second request. `duplicate_selection`
   counts as already selected. In assets-only mode a newly installed Workflow is
   registered in the running engine at once (grants.json still decides each step);
   otherwise, and for Skills, the reply says a restart is needed. "Remove selection"
   calls `revoke` and syncs; the installed file stays. "Synchronize selected" is kept
   as a secondary "Sync again" for selections made in the portal.

Reason: the owner wants to switch off assets that crowd the Agent's choices and to
remove assets without losing them; a second "disabled" convention or a hard delete
would contradict the one that exists. The live finding (a portal selection showed
nothing until a manual sync) shows a separate sync step is easy to miss.

Rejected alternatives:
- A `disabled.json` list beside the files: the host and `chat_authoring` already treat
  the `disabled/` folder as "not offered"; a second mechanism could disagree with it.
- Hard delete, or the recycle bin: not recoverable from the workspace alone.
- Removing shipped manifests with a warning: the removal silently undoes on upgrade.
- Revoking the platform selection on removal: removal is a local act; the member's
  platform decision stays theirs to change (one button away on the card).

## 2026-10-15 — A person's "run X" in a chat is the Workflow's form

Decision: when a person asks in Agent Web or Telegram to run an installed Workflow,
the answer is that Workflow's generated run form (Web, inline under the answer) or
question flow (Telegram), never the model collecting values in prose. Details in
`docs/phases/CHAT_WORKFLOW_FORMS.md`.
1. An explicit request (run verb + exactly one installed Workflow named) is routed
   deterministically before the model, Skill rules and Knowledge routing; `name=value`
   pairs typed with it are prefill. `/run <name>` in Agent Web opens the form too.
2. When the model decides, it calls the host tool `workflows__run_form`; a Skill-bound
   Workflow tool or `authoring__run_workflow` (installed) with incomplete or refused
   values in a person's conversation returns the same offer. The offer ends the turn.
   A complete, valid model call still runs, so a Workflow can remain a step the Agent
   orchestrates. Only in a conversation with a `session_id`; tasks keep failures.
3. A model may prefill only agent-channel, non-`confirm` fields; uploads and settings
   are never prefilled. Settings are never asked in the chat: missing required
   settings are named with a link to the Workflow's settings (Web) or a pointer to
   Agent Web (Telegram), and the Run button stays disabled.
4. A run from the inline form is recorded in that conversation as a question/answer
   pair; Telegram prefill is shown in the Run/Cancel confirmation.
5. A Telegram turn is never silent: blank model text, rate limits and refused messages
   get a retry or a short notice.

Reason: authors declare parameters once and never write GUI; the same declaration
already draws the Capabilities form and the `/run` flow, so a chat request must reuse
it. A model filling run values breaks the `channels`/`confirm` contract and asks for
settings that are not run values.

Rejected alternatives:
- Better prompting only: the model still decides the shape, cannot show pick lists,
  uploads or "same as last time", and was observed listing settings.
- Exposing every installed Workflow as a model tool with its schema: the model would
  fill values itself, the opposite of the owner's requirement.
- A separate chat-only form renderer: two renderers would drift; the inline form uses
  `renderParameterForm` as Capabilities does.
- Running immediately when no field is required: a chat sentence is not a Run click;
  the form (or Telegram confirmation for non-read runs) stays the confirmation.

## 2026-10-15 — Administrators manage the sharing of any published name

Context: the owner asked for a platform overview on the Member Portal from which an
administrator adjusts the sharing of any published asset (who can use it, co-editors,
owner), and for co-editor and transfer UI because an owner could not let another account
publish new versions. `docs/phases/PLATFORM_OVERVIEW.md`.

Decision:
1. A platform administrator may add and remove co-editors, transfer and deprecate any
   name, besides the owner and members of an owning team (`AssetOwnershipService._managed`
   and `_visible`). They already could decide who may use any name
   (`assets/access/update`).
2. Publishing a new version is unchanged: only the owner, an owning-team member or a
   co-editor (`AssetNameOwnership.may_publish`); an administrator is not a publisher.
3. Administrators set members' role and groups (`admin/members/update`), audited in
   `identity_user_changes`; the last active platform administrator keeps the role.
4. The portal is in tabs kept in the URL hash, and an asset's published content is
   readable by everyone it is shared with (`assets/manifest`).

Reason: an orphaned or wrongly owned name (for example the two assets `leo` published on
2026-10-15) must be fixable without the owner, and the administrator is the platform's
accountable operator. Keeping publishing out of the administrator role keeps the review
separation (an administrator reviews, owners and co-editors publish).

Rejected alternatives:
- Owner-only management (as of 2026-10-07): leaves names stuck when the owner is away.
- Letting administrators publish any name: mixes reviewing and authoring.
- Group changes only through new invitations: an accepted member could never join a team.

## 2026-10-15 — AEP skills and MCP servers in the coding agents' user configuration by default

Context: the owner requires that Skills and Workflows produced with this platform work
on it, and that AEP's Knowledge and MCP tools are usable from Claude Code, Codex and
Copilot, without a per-folder `aep-host assets connect`. A live test also found the
authoring catalog (~82K characters) above Claude Code's MCP output limit, `check-workflow`
creating folders, and agents assuming unclear inputs instead of asking.
`docs/phases/EXTERNAL_AUTHORING.md` "Default user-level setup".

Decision:
1. The installer and updater (unless `-NoAgentSkills`), Agent Web Settings > Coding
   agents and `assets connect --user` put, for each detected agent, the
   `aep-workflow-creator`, `aep-skill-creator` and `aep-knowledge` skills in its personal
   skills folder and the `aep` (authoring) and `aep-assistant` (Knowledge and Workflows)
   MCP servers in its user configuration. Files touched: `~/.claude/skills/aep-*`,
   `~/.claude.json` (`mcpServers`); `~/.agents/skills/aep-*`, `~/.codex/config.toml`
   (marked block); `~/.copilot/skills/aep-*`, `~/.copilot/mcp-config.json`
   (`CLAUDE_CONFIG_DIR`, `CODEX_HOME`, `COPILOT_HOME` respected). `uninstall -Apply`
   removes them.
2. Only AEP-marked entries are replaced or removed (skill marker file, server args
   running `host_runtime.cli`, the TOML block); the person's own same-named entries are
   kept; each edited file is backed up first.
3. `aep-assistant` is a stdio bridge to the running Agent Web that reads its address
   and token at call time; no token is written into an agent's configuration.
4. This extends the 2026-10-12 Copilot data decision (assistant tools return company
   content) to the person's own Claude Code, Codex and Copilot sessions, at the owner's
   request ("MCP and Knowledge too — they must be usable"). Authoring tools keep
   returning statuses and codes only.
5. Agent Web's text-only chat backends stay tool-less; the Copilot agent mode gets the
   authoring tools (`/mcp/authoring`) and the skills explicitly.
6. `aep_catalog` is compact (≤15K characters); schemas and formats come from
   `aep_capability`, `aep_workflow_format`, `aep_skill_format`. Checks have no side
   effects; task folders are created on submit, run or install.

Reason: AEP's value over a plain coding agent is that what it builds runs here, and a
per-folder step was forgotten (live test: a fresh session knew nothing about AEP).
User-level configuration is where each agent looks in every folder.

Rejected alternatives:
- Per-folder `connect` only: forgotten in practice, and new folders start without AEP.
- A fixed `http://127.0.0.1:<port>/mcp` URL with the token in the agent's config: the
  port can change and the token would sit in plain configuration files.
- Running `claude mcp add` / `codex mcp add` / `copilot mcp add`: needs each CLI on PATH
  in the installer's session and is not testable against a temporary home; the files are
  the documented user configuration.
- Giving Agent Web's Claude Code and Codex chat backends tools: changes the 2026-10-02
  text-only backend rule and the data boundary; left for an owner decision.

## 2026-10-15 — Members sign in to the Member Portal with an account and a password

Context: the owner found invitation-only sign-in too cumbersome ("signing in only by
invitation link"). Design and routes: `docs/phases/PASSWORD_SIGN_IN.md`.

Decision:
1. The Member Portal signs members in with account + password. An invitation stays the
   only way to become a member; the page asks for the password in the same step
   (`sign-in` with `{"password"}`), and the policy is checked before the invitation is
   used up. The API still accepts an empty invitation body (automation, older pages);
   such a member sets a password later from the portal (`password/set`).
2. Only an scrypt hash is kept (`n=2**15, r=8, p=1`, 16-byte random salt, cost stored
   per record, `hmac.compare_digest`) in the additive identity table
   `identity_passwords`; `schema_version` unchanged. Password bodies are parsed by hand,
   never as a `Contract`, so no validation error, dump or log can carry one.
3. Policy: 12 to 256 characters; refused when it contains the account name, is in a small
   built-in common list or is one repeated character (`password_rejected` with a reason).
4. Every sign-in failure is `authentication_failed` (unknown account, no password, wrong
   password, disabled member, locked). Counters in memory: 5 failures per account or 20
   per client address within 15 minutes lock that key for 15 minutes.
5. Forgot password: an administrator issues a single-use reset link (`#reset=`, SHA-256
   fingerprint stored as for invitations, 60 minutes by default, at most 24 hours, a new
   link revokes the earlier one). Redeeming it and changing the password revoke the
   member's browser logins and sessions and keep the Personal Agent login; "Force
   sign-out" revokes every login including the Agent's, and all sessions.
6. A disabled member's stored login no longer renews a session (`actor_disabled`).

Reason: an account + password is what members expect and what a browser password
manager supports, while invitations still decide who is a member. scrypt is in the
standard library (no new dependency) and memory-hard. The address limit is higher than
the account limit because the live platform is reached through an SSH tunnel or relay,
where every member arrives from 127.0.0.1; at 5, one person could lock everybody out.

Rejected alternatives:
- PBKDF2-HMAC-SHA256: also standard library, but not memory-hard.
- `p=3` (the full OWASP-equivalent scrypt setting): over a second per check on the busy
  office PC that hosts the platform; the cost is per record, so it can be raised later.
- Persisting lockout counters: a restart clearing them is acceptable for a preview and
  avoids a write on every failed attempt.
- Revoking the Personal Agent login on reset: a forgotten password says nothing about the
  separately issued Agent login; an administrator uses Force sign-out when it might.
- An external identity provider or e-mailed reset links: no mail service or IdP in the
  preview; the administrator delivers the link like an invitation.

## 2026-10-15 — Agent Web opens the Member Portal signed in with a single-use browser ticket

Context: owner request 2026-10-15: "Open Marketplace" in Agent Web must open the Member
Portal already signed in as this PC's member, with nothing to type, and a Library card
must show the asset's real content. Agent Web holds the member's Personal Agent login.
Design: `docs/phases/PLATFORM_OVERVIEW.md` "One-click sign-in from Agent Web" and
"Library card content in Agent Web".

Decision:
1. New platform routes `browser-ticket` (member session; answers a single-use ticket
   bound to that member, valid 60 seconds at most) and `sign-in/ticket`
   (`Authorization: Ticket id:secret`; answers the same browser login and one-hour
   session as a password sign-in, method `agent-ticket`, login label
   `Agent Web sign-in`).
2. Tickets are kept only as SHA-256 fingerprints, in memory, at most five open per
   member; refused for a disabled member at issue and at redemption; used up by the
   first redemption with the right secret; `ticket_used` / `ticket_expired` /
   `authentication_failed` otherwise.
3. Agent Web obtains the ticket server side with the Personal Agent session and opens
   `<portal>/#ticket=...` (fragment, never a query string, never logged); the portal
   drops the fragment from history at once. The Personal Agent login never reaches
   the browser or a URL. Without a saved code the portal opens on its sign-in page and
   Agent Web points to Settings > Shared platform.
4. A new ticket sign-in revokes the member's earlier `Agent Web sign-in` login.
5. Library card content comes from `assets/manifest` through the member's session,
   server side, uncached on the Agent and cached per version in the page.

Reason: the fragment never travels in a request, so neither the portal's access log, a
proxy nor a Referer sees it; a minute-long single-use ticket bounds the damage if a URL
is copied. Handing the browser the Agent's own 30-day login would give every browser
tab the Agent's credential, which could not be told apart or revoked separately.

Rejected alternatives:
- Putting the Personal Agent login (or its session) in the URL: long-lived, the same
  credential the Agent publishes with, and indistinguishable from the Agent in audits.
- A query-string ticket or a server-side redirect carrying it: lands in server logs,
  history and Referer headers.
- Persisting tickets in the identity database: a minute-long credential gains nothing
  from surviving a restart, and every click would be a durable write.
- A one-off session per click without a browser login: the page could not renew it,
  so the member would be signed out after an hour on that tab.
- Caching content on the Agent: a withdrawn share would keep showing until a restart.

## 2026-10-15 — Change proposals: one tool, one card component, Apply through the cards' own writers

Context: owner-approved design `docs/phases/AI_PROPOSED_CHANGES.md` (AI proposes, the
person applies), and the agent-mode slice (`docs/phases/AGENT_MODE_BACKENDS.md`) that
must reuse the same approval card.

Decision:
1. The model gets exactly one host tool, `propose_change(kind, values, reason)`,
   offered only in a person's conversation (a session id), like `workflows__run_form`.
   It validates and stores a proposal; it never calls a writer. The turn ends with the
   card.
2. One generic card (`common/action_cards.py` `ActionCard`) with server-defined button
   actions and labels; one server record type (`host_runtime/card_store.py`
   `PendingRecord` in a `CardStore` JSON file with expiry and a decide lock); one
   Agent Web renderer (`renderActionCard`) and one Telegram renderer
   (`telegram_card`). Card ids carry a two-letter handler prefix (`cp-` proposals);
   `AgentWeb.decide_card` dispatches by it.
3. Apply calls the very `AgentWeb` method the Settings/Capabilities card calls, with
   the current values merged with the proposal's, so backups, live switches, Tasks and
   messages are identical. Laya, model and Telegram writers make no host.json backup
   today, and Apply does not add one: "the same effect" includes the same backups
   (the shared-platform writer's).
4. Staleness is a SHA-256 fingerprint of the setting's current values (from host.json
   on disk for Laya and the model; the runtime's view otherwise); expiry 30 minutes;
   any non-pending status refuses a press. A failed Apply is final (`failed`); the
   Agent proposes again.
5. Values are checked against the writer's contract at proposal time; secret-named
   fields and credential-shaped values are refused naming the field only; permission
   fields (`approval_ref`, grants, data approval, `require_local_model`) are refused.
   Laya's owner approval reference stays a Settings-card-only field.
6. Telegram applies only `laya`, `workflow_settings` and capability switch on/off
   (owner decision); the server enforces it (`web_only`), not only the button layout.
   Its "Open in Agent Web" text names the place (Tasks > Pending changes) but no
   address, because Agent Web's address carries the page key. Agent Web lists open
   cards from every channel there.
7. The decided card is redrawn on its stored answer and its outcome appended to that
   answer's tool record, so later turns tell the model what happened, without adding
   chat messages.
8. Fixed in passing: the Laya card showed the previous values after Save until a
   restart (`runtime.config.laya` now follows the saved settings; the running mode
   still applies after a restart).

Rejected alternatives:
- One tool per kind or per writer: more schema for the model and more ways to reach a
  writer; one tool with a kind enum keeps the boundary in one handler.
- Letting the model continue the turn after proposing: it could narrate as if applied;
  ending on the card is deterministic.
- Adding a chat message pair on Apply (as G4 approvals do): duplicates the in-place
  result; the tool-record line carries it to the model.
- A clickable Agent Web link with its token in Telegram: the token is a standing key to
  this machine's Agent.
- Making the card status a closed enum: the agent-mode slice needs allowed/denied/sent
  statuses; the handler owns its statuses, the card only knows `pending` is open.

## 2026-10-15 — Agent mode for Claude Code and Copilot in Agent Web; Codex stays text-only

Context: owner-approved design `docs/phases/AGENT_MODE_BACKENDS.md` (option A with the
"Revised rules (owner, 2026-10-15)"). It replaces, for Agent Web, the 2026-10-02 rule
that the Claude Code, Codex and Copilot conversation backends are text-only
(`--restricted --strict-mcp-config`, `--ignore-user-config`, `--available-tools=`).

Decision:
1. Agent mode is a per-backend switch in Settings > Agent mode, **off by default**;
   with it off the backend runs exactly as before (text-only flags unchanged). The
   conversation must still be a PUBLIC session (the 2026-10-02 data boundary); what the
   agent reads beyond the chat is governed by the cards below and the owner's switch.
2. Each conversation has one working folder (default `workspace\agent-sessions\<session>`,
   or a folder under `workspace\agent-sessions` or a configured `coding.workspace_roots`
   entry) and optional read-only folders a person adds. A folder that is, or contains,
   a protected location is refused.
3. Relay, verified against the CLIs on this PC (Claude Code 2.1.296, Copilot CLI
   1.0.95):
   - Claude Code: `--print --setting-sources "" --strict-mcp-config --mcp-config <run>
     --settings <run> --permission-mode manual --permission-prompts host
     --permission-prompt-tool mcp__aep-agent__permission --plugin-dir <AEP skills>`.
     The run's settings make every Bash/PowerShell/WebFetch/WebSearch ask, allow only
     AEP's MCP servers, deny credential file patterns and disable hooks; the person's
     own user/project settings (which could allow commands) are not loaded.
     `MCP_TOOL_TIMEOUT` is raised so one tool call can wait ten minutes.
   - Copilot: `copilot --acp` (Agent Client Protocol). Agent Web is the ACP client
     (`host_runtime/acp_client.py`), answers `session/request_permission` through the
     card, never picks "allow always" (nothing persists in Copilot's configuration), and
     passes the MCP servers in `session/new`; `--disallow-temp-dir`,
     `--secret-env-vars=COPILOT_GITHUB_TOKEN`, `--allow-tool` only for AEP's servers.
   - Codex: **text-only**. `codex exec` has no relay; Codex is not installed on this PC,
     so no flag of a relay (app-server or MCP elicitation) could be verified. Settings
     and the chat say so; enabling it is refused.
4. One pure decision function (`common/agent_guard.py` `judge`): inside the working or
   a read-only folder free; outside a card (Allow / Allow this folder for this
   conversation / Deny); every command a card (Allow for this conversation remembers
   the program, e.g. `git`); network and unknown tools a card; a coding agent's tool
   configuration inside the folder (`.claude`, `.github/hooks`, `.mcp.json` ...) a card
   without a conversation-wide button. Refused even when allowed: SSH keys, cloud and
   CLI credentials, Windows credential stores, browser profiles, `host.json`, AEP
   workspace secrets (including each run's MCP configuration), credential file names
   anywhere, writes to the coding agents' own configuration, `%SystemRoot%`, Program
   Files and the whole AEP workspace outside `agent-sessions` (so installing, approving
   or publishing can never happen by writing a file); commands touching the firewall,
   the user environment's secrets, the registry, credential stores, sign-ins, AEP
   install/approve/publish, a protected path, or carrying a credential.
5. Cards are `pm-` records (`host_runtime/agent_mode.py`) in the shared card component;
   the MCP/ACP call blocks on the record; ten minutes without an answer is Deny. They
   are decided in Agent Web only (Telegram is refused `web_only`; Telegram never runs
   these backends). During a turn the page polls `GET /api/cards?session_id=` and draws
   them under the waiting turn; the answer keeps them
   (`ConversationMessage.action_cards`) and a tool-record line per card, so a later
   turn knows the outcome.
6. `/mcp/agent` (the `aep-agent` server: permission, mail and Knowledge tools) accepts
   only a running turn's own random token; the run's files are deleted after the turn.

Rejected alternatives:
- `--restricted` for Claude Code agent mode: it refuses files outside the working
  directories instead of asking, which contradicts "outside: a card".
- `--permission-mode acceptEdits`: in-folder edits would bypass the guard (a credential
  file or a tool configuration inside the folder).
- Copilot `preToolUse` hooks: they live in configuration the agent can reach and their
  allow semantics are not documented for this version; ACP is a public protocol with an
  explicit permission request.
- Answering ACP with "allow always": it would persist in the person's Copilot settings
  beyond the conversation.
- A Codex wrapper over `codex app-server`: unverifiable here (not installed); left as a
  follow-up instead of shipping guessed flags.

## 2026-10-15 — Agent mode email: read in scope, send only from one card per message

Context: `docs/phases/AGENT_MODE_BACKENDS.md` revised rules (read email, send email).

Decision:
1. `outlook.search` / `outlook.read` are read-only capabilities
   (`capabilities/mail_read`, `integrations/outlook_mail.py`, Outlook COM like the draft
   adapter; injectable readers for tests). The scope (folders, max days, excluded
   senders/domains and folders) comes from Settings > Agent mode and is applied inside
   the integration on every call; a message outside it is `message_unknown`.
   Credential-shaped text in subjects and bodies is redacted. A source test keeps the
   module free of any verb that changes a mailbox. The capabilities are registered for
   a Workflow only when it uses them, like `outlook.draft`.
2. The agent gets them as `aep-agent` MCP tools; the first read in a conversation shows
   one card (Allow for this conversation / Deny); attachments are saved into the
   working folder (`mail-attachments/`).
3. Sending: `outlook_draft` saves a draft with the existing `outlook.draft` writer and
   shows an `ml-` card (to, cc, subject, body, attachments; Send / Keep as draft /
   Cancel). Every message is its own card; there is no conversation-wide allow; no
   answer in ten minutes keeps the draft. `integrations/outlook_send.py` (the only
   delivering module) is called from `AgentMail.decide` only, after comparing the
   draft's recipients, subject and attachment names with what the card showed
   (Outlook rewrites HTML, so the body is shown but not compared); a changed draft is
   not sent. A source test checks that nothing else imports it.

Rejected alternatives:
- Sending through SMTP: needs a mailbox credential on the workstation.
- A "send all" or per-conversation allow: the owner's rule is one press per message.
- Putting the send verb into `integrations/outlook_draft.py`: that module's promise
  (and test) is that it never sends.

## 2026-10-15 — Agent mode audit: Task rows for decisions, every request in a log

Decision: every carded request, every refusal and every agent turn is a Task row
(`agent_permission`, `agent_mail`, `agent_turn`; the turn row counts asked, refused and
free requests and names the first free ones), with secret-shaped text redacted; every
request, free ones included, and every decision is a line in
`workspace/agent-mode/audit.jsonl` (redacted). For Copilot the card's Task row also
records whether the tool then completed or failed (ACP `tool_call_update`).

Rejected alternative: a Task row for every free in-folder read or write: the task list
keeps the newest 50 and one busy turn would push Workflow runs out of it.

## 2026-10-15 — Knowledge pipeline as agent tools; push stays on the Knowledge page

Decision: the `aep-agent` server offers `knowledge_sandboxes`, `knowledge_step` and
`knowledge_run_questions` / `knowledge_questions_status`. Read steps (sandbox list and
contents, drop folders, question sets, lint, ingest plan, file read, plan page, skill
guide, convert dry run) run freely; writes (sandbox create, pull, drop add, convert
apply, ingest apply, running test questions) show a card (Allow / Allow for this
conversation / Deny). Merge, discard, adopt, index, rule write, push and publish are not
offered. Steps run through `AgentWeb.pipeline_call` as the Host's owner, the same path
as the Knowledge page.

## 2026-10-15 — CI type-checks without the optional plotting extra; recorded artefacts stay out of ruff

Decision: `[tool.mypy]` gets an `ignore_missing_imports` override for `matplotlib`
(like the pywin32 and lxml ones). The `weekly-mail` extra is optional and
`capabilities/weekly_report/chart.py` imports it lazily, so CI and hosts without it must
still pass strict mypy; with the extra installed matplotlib's own inline types are used.
Ruff excludes `benchmarks/*/runs` (recorded agent output, including scripts that do not
parse, kept as evidence) and `src/capabilities/ncc_plan/rules.py` (kept text-identical
to the source module, which `tests/test_rs_w14_ncc_plan.py` compares), and exempts
from E501 only `benchmarks/business_workflow_lab/operator/smoke.py` (embedded
PowerShell) and `benchmarks/coding_v1/fixtures/build_fixtures.py` (prompts whose bytes
the fixture manifest hashes).

Reason: make `verify.yml` pass on a runner that installs only `.[dev,office]` without
weakening strict mypy or rewriting evidence and verbatim ports.

Rejected alternatives: installing the `weekly-mail` extra in CI (the job deliberately
mirrors a host without it); `ignore_errors` for tests or dropping `tests` from mypy
`files`; reformatting the benchmark runs or the NCC rules (changes recorded evidence
and breaks the verbatim-port test).

## 2026-10-16 — Bundled Skills: in-use on, skill packs off, a person's choices kept; pack copies in coding agents follow the switch

Decision (owner 2026-10-15/16, `docs/phases/HERMES_SKILL_PACK.md`): the Windows bundle
installs, through `aep-host assets install-bundled` (`host_runtime/skill_packs.py`),
the shipped manifests and its `aep-skills/` switched on and the Hermes skill pack
switched off (`assets/skills/disabled/`). An identity already here (on or off) is never
overwritten or switched on; one in `workspace/removed/removed.jsonl` is not brought
back; a newer Skill stays off when the person switched an earlier version off, and a
newer one going on sets the older aside (as installing a Skill always did); an alias
clash keeps it off. Pack coding-agent folders live in AEP's store
`workspace/agent-skills/<namespace>-<name>` (marker `.aep-managed.json` with `pack`)
and are copied into Claude Code's and Copilot's skills folders only while the Skill is
switched on, only for agents with AEP's own setup, never over a person's same-named
folder; switching off, removing, or removing AEP's setup takes them out. A store
folder of another pack (this PC's internal `hermes-personal`) is not replaced. The
builder's credential scan accepts the pack's documented placeholders one by one (file
and exact text).

Reason: colleagues get the Skills AEP uses and a large backup set that does not crowd
the Agent's choices; updates must not undo what a person switched, edited or removed;
coding agents load every folder in their skills directory, so "off" can only mean
"not there".

Rejected alternatives: running `export-assets` from the installer (it rewrites shipped
files and would switch on what a person switched off); writing every pack folder into
the agents and relying on `disable-model-invocation` (Claude Code only, still listed);
a global `[redacted]` exemption in the builder's scan (weakens it for every file).

## 2026-10-16 — The installer ships an LLM gateway (LiteLLM without its enterprise package, own venv)

Decision: the Windows bundle installs `llm_gateway` (docs/phases/LLM_GATEWAY.md): the
owner's verified LiteLLM 1.94.1 proxy on `127.0.0.1:4000`, chatrs models via
`hosted_vllm/` (11 names incl. the `claude-*` aliases, AEP default `gpt-5.5`), the
empty-`choices` streaming patch (refuses to start when LiteLLM's internals moved),
offline LiteLLM flags set before LiteLLM is imported (`LITELLM_LOCAL_MODEL_COST_MAP`
and three more; a reboot otherwise waited 9-12 minutes on a GitHub fetch behind the
company proxy), Kerberos/SPNEGO token renewal, status/start/stop/test/autostart
(`aep-host gateway ...`, Agent Web Settings > LLM gateway). It is installed offline
from an exact lock of the owner's versions (`deploy/windows-preview/gateway/
requirements.txt`, 106 wheels, ~135 MB) into `<install root>\gateway-venv` with the AEP
wheel `--no-deps`. `litellm[proxy]` is not installed: its `litellm-enterprise`
dependency is proprietary and may not be redistributed; LiteLLM imports it only inside
`try/except`, and the extra's other requirements are listed explicitly. Settings,
configuration (secrets only as `os.environ/...`) and the token file live in
`%LOCALAPPDATA%\AgenticEngineeringPlatform\gateway\` and survive updates and
uninstall; the local key is generated once and exported to the user variable
`LITELLM_MASTER_KEY` only when none exists. `host.json` gets `gateway-default.json`'s
model only when it has none. Autostart is a current-user logon task without
elevation and without a restart loop (fallback: the user's Run key). A gateway run
outside AEP (`gateway.json` `managed: false`) is shown and tested only, never
started, stopped, refreshed or autostarted. Failed model turns on a loopback endpoint
say "not running", "still starting (started N s ago)" or "401: token probably expired"
with a pointer to Settings > LLM gateway, in Agent Web and Telegram.

Reason: without a gateway AEP's Agent reaches no model (owner, 2026-10-16); the owner's
hand-built gateway is verified, so its knowledge (prefix, patch, settings, token
renewal) is ported, not rediscovered. Owner decisions 2026-10-16: all 11 models, a
separate venv, no enterprise package and the bundle growth accepted, this PC keeps
its own gateway.

Rejected alternatives: bundling `litellm[proxy]` (redistributes proprietary code); a
trimmed dependency set (LiteLLM's `run_server` refuses to start without boto3);
shipping the 153 MB `chatrs-gateway.exe` (opaque PyInstaller build of the same set);
writing an own proxy (loses the Anthropic `/v1/messages` translation Claude Code
needs); the AEP venv (numpy `<2` vs 2.5.1 and other pin conflicts); downloading at
install time (company PCs install offline); a restart-on-failure task (masks a bad
token as a crash loop); a probe inside `agent/gateway.py` (the agent layer stays
provider-neutral; the explanation lives in `host_runtime/gateway_link.py`).

## 2026-10-16 — The weekly report is personal, not bundled

Decision (owner, 2026-10-16): the SDE weekly report (`engineering/weekly-report` Skill
2.0.0 and `engineering/sde-weekly-report` Workflow 1.0.0) is the owner's personal
Workflow and is never shipped or shared. `host_runtime.assets` keeps two sets:
`shipped()` (what every installation gets: the bundle's `assets install-bundled`, the
Capabilities "ships with AEP" refusal, `export-assets`) and `personal()` (the weekly
report). The personal set is installed or written only with `--include-personal` on
`aep-host assets install-bundled` / `aep-host export-assets`, or with the user
environment variable `AEP_INCLUDE_PERSONAL_ASSETS=1` (set once on the owner's PC, so
his normal `update.cmd` keeps bringing new weekly versions). The capability code and
the manifests stay in the package. Updates remove nothing: a colleague PC that got the
weekly assets from an earlier bundle keeps them as they are, may now remove them
(they are no longer "shipped"), and no update adds them again. The broken
`weekly-preview.cmd` / `weekly-apply.cmd` / `weekly-mail.cmd` (they sent
`weekly.preview/apply/mail`, which the Skill no longer declares) and the superseded
`schedule-weekly.ps1` are deleted from `deploy/windows-preview/` (git history keeps
them); the manuals no longer describe the weekly report and say instead that personal
Workflows are not bundled. CI asserts the install has no weekly Workflow and that
`export-assets` writes `engineering/rs-wmt-package-release` but not the weekly Skill.

Reason: the weekly report reads one team's board and workbook and mails one team; on a
colleague's PC it is noise at best and a wrong Workflow at worst, and its double-click
scripts were broken.

Rejected alternatives: removing the code from the repository (breaks the owner's own
install and upgrade); a separate personal pack folder outside the bundle (a second
install path to maintain for two manifests); an installer switch `-IncludePersonal`
(names a personal feature in the colleague installer); uninstalling the weekly assets
from colleague PCs on update (updates never remove what a person has); dropping the
`weekly-mail` extra (matplotlib) from the bundle (the owner's upgrade reinstalls from
the same bundle and his weekly mail chart needs it; it is a dependency, not a
Workflow).

## 2026-10-16 — `aep-host open` shows a starting page while Agent Web starts

Decision (owner request 2026-10-16: a shortcut click showed nothing for 10-30 s): when
Agent Web is not running, `aep-host open` first writes and opens a static page,
`workspace/agent-web-starting.html` (no server; light/dark; spinner; elapsed time),
then starts the server. The page reads `workspace/agent-web-starting.js` every second
through a `<script>` tag (a `file://` page may not `fetch` another file); the launcher
writes it as `starting`, `ready`, `failed` (server exited, with its exit code, or no
answer within 180 s) or `opened`. After 120 s the page says it is slow and where the
logs are. Only `ready` carries Agent Web's address (the token URL already kept in
`agent-web.json` and opened before); the page goes there with `location.replace`
(loopback addresses only), and after 15 s the launcher rewrites the status without it.
The page never holds the address. When the browser could not be asked to open the
page, Agent Web is opened directly as before; a running Agent Web is opened directly.

Reason: an immediate page tells the person the click worked and, if it fails, where
the log is, without a second server or a new credential.

Rejected alternatives: a token-free redirect route on Agent Web (lets any page open an
authenticated Agent Web and weakens the token guard); writing the address into the
page itself (left on disk in another file indefinitely); opening Agent Web in a
second tab from the launcher (two tabs; the starting tab cannot close itself); a
small loopback server for the page (another listener to secure).

## 2026-10-16 — A conversation that drafts a Workflow or Skill shows its install card

Decision (owner request 2026-10-16, "bring back the small card so nobody has to go to
Capabilities to install"): whenever a Workflow or Skill draft is created or revised as part
of an Agent Web or Telegram conversation, whatever backend answered, the conversation shows
one install card right after that turn. The card (`dr-` ids, `ActionCard.kind`
`draft_install`, `host_runtime/draft_cards.py`, records in
`workspace/authoring/draft-cards.json`) shows the title, what it does, the steps with their
side effect, the parameters and "Will become a form with fields ...", the check result and
any test run; buttons **Install** (the owner's press is the approval: it decides the agent's
own pending install request when there is one, so `aep_status` reads approved, else runs
`ChatAuthoring.install_now`), **Run once to try** (read-only Workflows whose required run
fields all have defaults; the existing `ChatAuthoring.execute` test-run path; the card stays
open and shows statuses and codes only) and **Not now** (the draft stays in Capabilities).
After Install the answer gets the Workflow's run form (`workflow_form`, origin `install`)
under the card and the Workflow runs at once (the existing `on_installed`). Nothing
installs without the press.

Why the card had gone: it was never tied to drafting. The old in-chat card was the
`/api/approvals` request the resident model made only if it chose to call
`authoring__install_workflow` (often it stopped after drafting or running), and agent-mode
Claude Code / Copilot drafts went through `/mcp/authoring` with the shared assistant token,
so they had no conversation (`session_id` None, and always labelled `external:copilot`) and
their install requests were listed only in Capabilities.

Rules:
- Attribution: `/mcp/authoring` now also takes a running turn's own token (an agent-mode
  run's token, or a per-turn token for the `copilot_agent` conversation backend); with it
  `ExternalAuthoring` carries that `session_id` and the right agent name. Drafts and install
  requests get the conversation; run requests do not (a run's data must never enter a
  conversation an external agent reads, PUBLIC rule). `SkillCandidate.session_id` added.
- One open card per draft and conversation: a later revision, or the agent asking to install
  again, closes the earlier card as "Replaced" (redrawn in place) and shows the new one under
  the newer answer; several revisions in one turn give one card; an unchanged draft is not
  carded again. An install request answered on a card is no longer shown as a second,
  old-style approval card (`/api/approvals?session_id=` and Telegram's approval buttons skip
  it); run approvals keep the old card.
- Telegram: installs were already approvable there by the owner (approval buttons), so the
  card shows Install / Not now (no Try); decided through Agent Web's `decide_card`, owner
  only, as every card.
- Drafts from an external agent outside Agent Web (stdio `aep-host mcp`, CLI) keep appearing
  only in Capabilities. No notification in the latest conversation (decided: keep simple; a
  conversation the person did not use for it would be the wrong place).

Rejected: auto-installing a draft that passed its checks (installing stays the owner's
press); a card per revision (duplicates); attributing `/mcp/authoring` calls to whichever
conversation turn is running (wrong when two conversations run at once); adding Try to
Telegram (runs belong to the run form there).

## 2026-10-16 — A self-signed Shared Platform is trusted by a pinned SHA-256 fingerprint

Context: owner request 2026-10-16, open the Shared Platform on 172.25.228.141 to colleagues on
the company network with a self-signed certificate (141 is a public test machine; no company
CA certificate is available for it). Agents had no way to trust it except importing it into
Windows, and every call would otherwise fail verification.

Decision:
- host.json `platform` and `publishing` take an optional `certificate_sha256` (the exact
  certificate, stored `AB:CD:...`) or `ca_file` (PEM), not both. The Bridge client, the
  member publisher (publish, enroll, browser ticket, Library content) and the enrollment
  check use it. Without either, the Windows trust store decides, as before.
- A pinned connection completes the handshake, compares the certificate's SHA-256 and closes
  on a mismatch before any request byte is sent; only that connection skips chain and name
  checks. Nothing changes the process-wide `ssl` default. Failure code
  `certificate_untrusted`, not retryable.
- Members trust the platform in Agent Web (Settings > Shared platform > "Platform
  certificate": Fetch & show fingerprint, compare with the administrator's value, Trust this
  certificate). The administrator gets the value from `aep-platform certificate-fingerprint`
  and hands it out through a trusted channel.
- Browsers: accept the warning after comparing the fingerprint, or import the public `.cer`
  (downloadable from the card) into the user's Trusted Root, with the risk explained in the
  guide (chapter 10.1.1). The private key is generated on the platform machine, readable only
  by its service account, never copied off.
- Platform: the TLS handshake moved from the accepting thread to each request's thread
  (10-second limit), because a silent client otherwise stopped the platform for everybody.
- 141: certificate in `%LOCALAPPDATA%\AgenticEngineeringPlatform\shared-platform-tls\`,
  `listen_host` 172.25.228.141, ports 8775/8776, firewall rule "AEP Shared Platform" (TCP
  8775/8776 inbound; all profiles but only on the Ethernet adapter that holds
  172.25.228.141, because Windows classifies the company LAN there as an unidentified,
  Public network, so a Domain/Private-only rule would never apply), scheduled task "AEP
  Shared Platform" (at startup and a 5-minute check, S4U as openlab, IgnoreNew, so it
  restarts the platform when it stopped).

Rejected: disabling verification (globally or per call); trusting on first use without a
human comparison (a man in the middle on the first call would be pinned); requiring every
member to import a root certificate (wide trust for one internal host); shipping a pure-Python
certificate generator (openssl from Git for Windows is on the machine; no new crypto code);
a scheduled task that stores the account password (S4U needs none); opening the ports for
every Public network or changing the LAN's network category (an unidentified network's
category is policy, not a setting that reliably stays).

## 2026-10-16 — Skill suggestions S1: the model groups, the score only filters

Decision (owner decisions 2026-10-16 in `docs/phases/SKILL_SUGGESTIONS.md`, implemented as
slice S1, report only): repeated work is found by one structured model call a night that
groups the person's own requests; the deterministic score never joins requests.

- **Pre-filter floor 0.2** (0.6 x IDF-weighted Jaccard over `knowledge.query.tokens` +
  0.4 x tool shape) against any request in *another session*. Below it a new request is a
  one-off: not sent, and not marked as sent, so it is reconsidered when a similar request
  arrives. Low on purpose: it only removes obvious one-offs; the model decides.
- **Cap default 120 request excerpts per pass** (`suggestion_max_requests`, 10-1000),
  stored groups shown with at most 2 examples each and at most half the cap; the rest
  waits for the next night. 120 excerpts of 300 characters stay well inside one model
  call and cover a busy month of one person's opening requests.
- **Persistence:** two tables in `experience.sqlite` (`suggestion_sent`,
  `suggestion_groups`) holding request ids, group ids, task names, status `open | reported
  | dropped` and reason; never request text. Excerpts are rebuilt from the conversations
  each night, so deleting a conversation removes it from the evidence. A sent request the
  model matched with nothing becomes a group of one so it can still be joined later; only
  stored groups that resemble the night's new requests are sent again.
- **Model output is untrusted:** only ids from the prompt (`R1..`, `G1..`), each once, two
  or more per group; counts and any other field ignored; task line redacted and cut. A
  failure or malformed reply changes nothing.
- **Dedupe drops permanently with the reason** (installed Workflow run in the evidence,
  installed Skill or Workflow covering the task words, a pending candidate, an earlier
  suggestion); requests that later join a dropped or reported group only add evidence.
- **Secrets:** requests matching `SECRET_PATTERN` or still holding `[redacted]` are
  dropped before anything else. The report's counts carry no text.
- **Shared code:** the nightly job and `aep-host experience suggest --dry-run` call the
  same `suggest_for_runtime`; the dry run opens the store read-only and writes no report.
  The model call shares `experience_review.structured_call` with the failure review.

Rejected: deterministic single-link clustering as the joiner (section 4.1's
recommendation, overridden by the owner); sending every request each night (cost grows
with history); persisting request excerpts (a second copy of conversation text outside
the conversation store); marking one-offs as sent (a one-off could then never meet the
request that repeats it); mining every actor on the Host in the nightly job for now (S1
mines the device owner; per-member passes come with the Reviews card in S2).

## 2026-10-16 — Skill suggestions S2: cards per person, ids not text, sensitivity per Host

Decision (slice S2 of `docs/phases/SKILL_SUGGESTIONS.md`, section "S2 as built"): a group
the nightly pass qualifies becomes one `skill_suggestion` proposal in the existing
`ProposalStore`, owned by the person whose requests formed it.

- **Actor field, additive migration.** `ReviewProposal` gains `actor` (default None), and
  the `proposals` table gains a nullable `actor` column through `ALTER TABLE ... ADD
  COLUMN` when it is missing (checked with `PRAGMA table_info` on every open, so it runs
  once). Old rows keep NULL and their JSON records are untouched; a NULL actor means the
  device owner (`ProposalStore(owner=runtime.actor)`), which keeps every failure-review
  proposal visible exactly where it was. Inserts now name their columns.
- **Visibility is enforced in the store, not the page.** `all(actor)` and `get(id, actor)`
  return only that person's proposals; another person's id answers `unknown_proposal`, the
  same as a missing one, so its existence is not disclosed. Agent Web passes
  `runtime.actor`: it has no per-request member identity (the Personal Agent login is per
  Windows user), so that is the person signed in to this Agent Web.
- **Cards keep ids, not request text.** The card stores session id, message id and date;
  `/api/reviews` cuts the excerpt from the person's conversation when listing (redacted
  again). This follows the S1 decision of no second copy of conversation text, and a
  deleted conversation leaves the evidence ("This conversation was deleted.").
- **One open card per group.** Card id `suggest-<group id>`; a later `updated` item (a
  reported group that gained requests) updates the open card's counts, evidence and
  `seen_more`. An Ignore is a `reject` with an optional quick-pick `reason_code` and an
  optional text; it marks the S1 group `ignored` with the time and the request ids held.
  The group comes back (as card `-2`, ...) only when the requests that joined after the
  Ignore meet the whole threshold on their own (requests, sessions, days), the strict
  reading of 6.4.3 so one busy session cannot bring it back.
- **Sensitivity is one setting per Host workspace** (`suggestion_sensitivity`, Low /
  Normal / High from section 5's repeated-requests column; High's missing day count is 1),
  read on every pass, so no restart is needed.
- **No accept in S2.** `accept` and `done` are refused for a suggestion until S3 adds
  Create draft; the model gets no tool for any decision.

Rejected: storing excerpts in the card (second copy of text, outlives a deleted
conversation); a per-member settings map in `experience-settings.json` (nothing can edit
another member's entry while Agent Web serves one person; revisit with per-member sign-in);
filtering only in the page (an id would still be decidable); reopening the rejected card
on re-proposal (it would erase the recorded Ignore); counting only the number of new
requests after an Ignore (two in one session would bring a card back).

## 2026-10-17 — AEP does not integrate n8n

Owner: "n8n的東西請取消整合" / "我們不在Agent上面串接N8N的工作流". The Agent never calls or
is called by n8n workflows.

- Removed the offline n8n adapter: `src/integrations/n8n.py` (`N8nAdapter`,
  `N8nSubmission`, `N8nWorkflowBinding`), `tests/test_n8n.py` and `integrations/n8n/`.
  Nothing else imported it.
- `AGENTS.md` rule 3, `docs/ARCHITECTURE.md` (core rule, section 2, the n8n section,
  layout and rule 20), the architecture-guard skill, README and CONTRACTS now say AEP does not
  integrate n8n; schedules, triggers and notifications are the host's own (schedule store,
  Agent Web, Telegram). This replaces the earlier "n8n is optional integration" rule.
- Kept: old n8n workflows as a specification source for migration (`tests/fixtures/source_n8n_release.json`,
  `tests/test_source_n8n.py` characterize the source; `benchmarks/w13_parity`), and
  historical records in DECISIONS, TASKS and phase documents.

Rejected: keeping the adapter as an unused optional seam (it suggests n8n is a supported
integration and keeps a contract nobody may use).

## 2026-10-18 — Generic Harness hand-off rules G1–G4

Owner, 2026-10-18, after the U7 baseline ("好做"): implement Knowledge Strategy v1.2 ADR-K6
option A. U7 measured the tool route 11.5 pp behind the direct route on the same 26 questions
(threshold 5 pp), mostly Q1041/Q1061/Q1091: partial answers with supported claims that the tool
route marked not validated and handed back to the model. The rules sit at the seam between the
conversation tool loop and any domain Harness, so they are generic, not Knowledge cases. As built:
`docs/HARNESS_DESIGN.zh-TW.md` §5.6; commits 6d0fe421 (G1), 9e89053b (G2), 209fb885 (G3),
0c9b1095 (G4).

- **G1, a result that failed Host checks is not rewritten by the model.** A Harness result that
  is not validated but has output (for Knowledge, a grounded record) is the turn's answer as the
  Harness wrote it, Host note included, with record and evidence kept: the same text the direct
  route shows. With no output, the model answers and the Host appends a visible "not verified"
  note. Workflow and Coding Harnesses produce a status, not answer text, so they take the second
  branch: a failed Workflow run (steps or output checks), a failed draft trial run, or a Host
  validator's `status: failed` (Coding Harness, DUT evidence) keeps a Host note on the model's
  answer unless a later call of the same tool in the turn succeeded. Plain capabilities and host
  tools are unchanged. The Knowledge tool's `status` now says whether the Harness produced a
  result (as the direct route's Bridge status does); the verdict is `harness_verdict` and
  `failure: knowledge_not_validated`.
- **G2, the person's original sentence is the anchor.** The Host passes the current turn's text
  and recent conversation with the model's argument. The adapter answers and validates the
  original. The model's version only adds: a supplementary retrieval query, after a
  deterministic check that keeps every entity-like term of the original (digits, capitals, time
  words, glossary terms; else rejected and the original alone is used) and drops added terms
  found in neither the conversation nor the glossary (the Knowledge Skill procedure's terms). It
  joins the question only when it resolved terms from the conversation. Every tool call now
  records its arguments (no credentials, bounded, not sent back to the model) and Knowledge
  records the anchor outcome, so a benchmark can compute an intent drift rate.
- **G3, Skill selection by bound asset.** Optional `SkillManifest.asset_bindings` (kind, asset,
  optional exact version, priority), omitted from the bytes when empty. The bound Skill wins by
  priority, ties by identity, never installation order; without a binding, the first eligible
  Skill as before. Tool and direct routes use the same binding.
- **G4, consistent output length.** The loop returns a Harness result up to the domain's
  declared limit (Knowledge: synthesis tokens × 4 characters plus the Host's own text), and a
  cut appends a Host note saying where the full result is. Replaces the fixed 12,000 characters.

Rejected: Knowledge-only special cases in the Gateway (the seam is shared by every domain);
ending the turn on every failed Workflow or Coding result (it would remove the model's repair
loop, so a repaired run clears the note instead); a model-based equivalence check for G2 (not
in scope; the check stays deterministic); letting the model's version replace the question when
it passes the check (synthesis and validation must answer what the person asked); deciding equal
binding priorities by installation order; feature flags (each rule is one revertible commit,
per v1.2 §7.5).

## 2026-10-18 — G2 anchor check is language-independent

Owner approved 2026-10-18. G2 (commit 9e89053b) compared the conversation model's version of a
Knowledge question with the person's sentence by string matching. The model (GPT-5.5) is
bilingual; the checker is not: a Chinese question such as 「眼圖會影響哪些產品決策」 that the model
correctly translated to English failed as "missing terms" and its English words were dropped as
"added terms", although retrieval is lexical BM25 over a mixed-language vault and bilingual
queries are exactly what helps it.

Decision: the model supplies the language knowledge, the Host only checks substrings.

- The `knowledge__<vault>` tool input gains two optional fields: `original_terms` (key terms
  copied verbatim from the person's message) and `term_translations` (each such term mapped to
  its translation or synonym in the other language). `question` is unchanged and still the only
  required field; callers without the new fields behave exactly as before.
- Verbatim check: an `original_terms` entry or a `term_translations` key is verified only when it
  is a substring of the original after whitespace, case and width (NFKC) normalisation; anything
  else is discarded and recorded. A verified translation key counts as a verified term.
- Coverage: a required term is satisfied by the model's version or by a verified term; reject only
  when it is in neither. Added terms: also allowed when they appear in the value of a verified
  translation. A translation whose key is not in the original licenses nothing.
- Still deterministic, no extra model call. Synthesis and validation still answer the original;
  the model's version and the translations only widen retrieval. The verified translations form
  one bilingual keyword query (term, translation, term, translation...) added to
  `supplementary_queries` for the outcomes same and accepted, never for rejected.
- `query_rewrite.py` already writes bilingual keyword queries, but with a separate Knowledge-side
  model call, only when the procedure sets `bilingual_retrieval`, and about synonyms and related
  topics rather than the person's own terms. The two are combined, not substituted: retrieval asks
  the original, the rewrites, then the supplementary queries, deduplicated by case and spacing
  (`handlers._distinct`), so a query both produce is searched once.
- Logging: `host.data.anchor` gains `verified_terms`, `discarded_terms` and `translations_used`;
  telemetry adds only counts (`anchor_verified`, `anchor_discarded`, `anchor_translations`).
- Benchmark: `benchmarks/knowledge_v1/questions/zh-core.json` holds Traditional Chinese
  translations of 8 core questions (ids `Qxxxx-zh`, `source_id`, the source's tags), run with
  `run.py --set zh` and graded the same way, the reviewer seeing the Chinese text. The pinned
  bank (`questions.json`, `source_sha256`) is unchanged; the runner refuses a zh file whose bank
  hash, source ids or tags do not match.

Rejected: a bilingual dictionary in the repository (large, domain-specific, never complete);
a model call to judge equivalence (not deterministic, extra latency and cost); verifying the
translations themselves (the Host has no language knowledge; a wrong translation can only widen
retrieval, and every claim is still cited and Host-checked); letting the translations or the
model's version become the question; replacing `query_rewrite.py` with the translations (the
rewrite's synonyms measurably raised recall, 2026-10-09); adding the translation query when the
model's version was rejected (a rejected turn uses the original alone, as before); changing
`questions.json` to add Chinese questions (it is pinned by hash).

## 2026-10-19 — Conversation tool cap 150 with guards; live Harness state in the chat

Owner approved 2026-10-19, both together.

**Cap and guards.** One conversation turn may make up to 150 tool calls (was 20; the turn
budget is 151 model turns). The cap is a Host setting (`conversation-context.json`
`tool_call_limit`, 1–150, default 150) shown in Agent Web Settings and read at every turn, so a
change applies without a restart. The higher cap came with three guards:

- `tool_repeat_limit`: the same tool with the same arguments (a digest of name and canonical
  JSON, kept in memory only) failing 3 times in a row stops the turn.
- `tool_repeat_limit` also when an identical call would run a 6th time since the last call
  never made before in the pass (N = 5). Identical input usually means identical output, and
  five looks are enough to wait for a change; a call that is new in the turn is progress and
  resets the counts, so draft → run → fix draft → run the same Workflow is never stopped.
  Knowledge and Workflow retries happen inside the Harness (one tool call) and are not counted.
- `turn_time_limit`: a per-turn wall-clock budget, default 30 minutes (`turn_time_limit_minutes`,
  1–120), checked before each model call and each tool call; a running call is not interrupted.
- `tool_loop_limit` stays the count stop. All three end the turn as `needs_input` with the tool
  record kept; Agent Web and Telegram explain the reason and keep 「回覆『繼續』我會接著做」.
- Each stop emits telemetry `turn.stopped` with the reason and counts, never content.
- The count cap and the repetition guard apply per pass of the tool loop (the conversation
  check's retry is a new pass); the time budget covers the whole turn.
- Context growth: 150 observations of up to 16,000 characters would outgrow any context window
  (`prepare_history` bounds only the carried transcript), so observations kept in one turn's
  messages are capped at 160,000 characters; the oldest are replaced by a short note, the newest
  is always kept. No token budget was added: output per model call stays 8,000 tokens and the
  turn total is bounded by the cap and the time limit.
- `AgentProfile.max_turns` is now bounded by the Gateway turn budget (151, was 100) so the two
  bounds cannot disagree. The scheduled task executor keeps its own `min(max_backend_turns, 5)`:
  a background task budget, not the conversation limit.

**Live Harness state.** A running turn records content-free progress in memory, by session:
tool calls started and finished (name, status, duration), Harness phase transitions reported by
the shared runner with the `AgentHarnessRun` phase names and retry number, the tool count against
the cap and the elapsed time against the budget. `GET /api/conversations/progress?session_id=`
returns it only to the actor that started the turn and only while it runs. Agent Web polls it
every second during a turn and draws a stepper, the recent tool lines and 「工具 n/150 · m:ss /
30:00」. Agent-mode backends show their tool requests (waiting, allowed, refused); Codex shows only
the elapsed time. Telegram keeps its single status message, now with the same compact text, and
edits it at most every 5 s after the first edit.

Rejected: a fixed cap without guards (a spinning model would burn 150 calls); counting identical
calls per turn without the progress reset (breaks fix-and-rerun cycles and polling a window
between actions); interrupting a running tool at the deadline (a Workflow or Bridge call has no
safe cancel point); a per-turn token budget (no gap beyond the context growth handled above);
streaming tool arguments or partial answers to the page (the owner asked for state, not content);
delaying the Telegram status message to 10 s (the owner asked on 2026-10-06 for it to appear at
once, and an existing test pins that behaviour; the edit rate limit is what prevents a stream).

## 2026-10-19 — The Agent revises an installed Workflow by building on its real code

Owner approved 2026-10-19. Asked to change the Issue Key fallback rule (`GH-76` when there is no
`GTM-xxx`) of an installed Workflow, the Agent said the platform did not expose its source and
rewrote a "v2" from scratch with the whole logic as one embedded `coding/run-python` script.
`authoring__get_workflow` claimed to show installed Workflows but read only chat candidates, and
a Workflow whose logic ships as a capability package had no readable source.

Decision (spec `docs/phases/WORKFLOW_REVISION.md`):

- `authoring__get_workflow` takes `workflow` (an installed identity, or a name for its highest
  installed version) as well as `candidate_id`, and returns the full manifest the model needs,
  embedded scripts included, in 20,000-character slices with a notice and `offset`.
- Readable: the owner and contributors always; otherwise published and either owned by a team,
  organization or service (bundle, Marketplace, Shared Platform selection) or visible to the
  organization. Another person's `private`/`team` Workflow answers `workflow_unknown`.
- `authoring__revise_workflow` copies an installed Workflow into a chat candidate one patch
  version up with `source: revision:<identity>` and `base_digest`. The owner or a co-editor
  (`metadata.contributors`) keeps the name; a co-editor's version keeps the original owner.
  Anyone else, including for a team-owned shipped Workflow, forks to `<name>-<actor>` and is
  told so. Editing a revision does not climb versions. Fields the draft format cannot express
  (`progress_steps`, `occupies_machine`, `secrets`, central execution, categories) are carried
  over from the Workflow a draft continues.
- Installing stays the person's press on the in-chat card (or Capabilities) through the existing
  install path: a new version file beside the old, which stays installed with its history. The
  card reads "Revision of X 1.0.0 → 1.0.1" with changed steps, inputs, parameters and the script
  line delta; an unchanged revision gets no card.
- `authoring__show_capability_source` reads, never edits, Python and manifest files under one
  package folder of the installed `capabilities` package, size-capped, path traversal refused,
  credential-looking lines masked. Behaviour changes go through a revision Workflow.
- External agents get `aep_show_installed_workflow` and `aep_revise_workflow` (CLI
  `show-installed-workflow`, `revise-workflow`) only for Workflows installed from an authoring
  draft on this Host by its owner, the drafts `aep_get` already shows; everything else is
  `workflow_withheld` (PUBLIC rule). No capability-source tool for them.
- Agent Web Capabilities: an installed Workflow has **Revise in chat**, which opens a new
  session with the request typed in, unsent.

Rejected: letting the model edit installed files or the AEP package (bypasses review and
breaks published immutability); showing every installed Workflow to external agents (the PUBLIC
rule withholds person-written steps); a separate `authoring__show_installed_workflow` tool (one
read tool with two keys is easier for the model to find); keying a fork on the Shared Platform's
co-editor records (not available on a local Host; `contributors` is what the manifest carries);
installing a revision under the original team-owned name with a person as owner (it would claim
the team's name and collide with the next bundle upgrade).

## 2026-10-19 — Telegram's status message is edited whenever the turn's state changes

Owner approved 2026-10-19 (「狀態有變就發」). Supersedes the Telegram part of 2026-10-19
"Conversation tool cap 150 with guards; live Harness state in the chat" ("edits it at most every
5 s after the first edit"); that entry is kept as history.

- The one status message ("⏳ Working on it…", sent at the start as since 2026-10-06) is edited
  whenever the shown state changes: a new Harness phase, a tool starting or finishing, a retry,
  a stop. `TurnProgress` calls a `listener` after each change; Telegram's `_Progress` redraws
  from it (thread-safe: a Harness in a worker thread hops to the event loop).
- Rate: at most one status edit per second per chat (`STATUS_EDIT_INTERVAL_SECONDS`). A change
  inside the window is rendered when the window ends, so the newest state is shown and none is
  dropped; the events of one step become one edit. Identical text is never sent. A 429 defers
  the next edit by its `retry_after` (capped at 60 s), then the newest state is sent.
- The elapsed-time line still refreshes every 5 s when nothing else changes. The final
  "✅ Done / ⚠️ Stopped" edit keeps the window (waiting at most 5 s). Still one message per turn,
  never one message per change.

Rejected: a new message per change (floods the chat; the owner has never wanted that); keeping
the 5 s timer (the owner wants changes shown as they happen); editing on every event without a
window (Telegram rate-limits about one edit a second per chat and would answer 429s); dropping
changes inside the window instead of deferring them (the last state of a burst could be lost).

## 2026-10-19 — A member of the owning team revises a team-owned Workflow in place

Owner approved 2026-10-19. Amends 2026-10-19 "The Agent revises an installed Workflow by building
on its real code", where a team-owned shipped Workflow always forked to `<name>-<actor>` because
the Host had no record of team membership.

- A Workflow owned by `team:<id>` (in the Host's authoring namespace) is revised in place
  (1.0.0 → 1.0.1, same name, owner stays the team) by a member of `<id>`. Non-members still fork.
- Membership source, in order: (1) the Shared Platform, when host.json `publishing` is set:
  the existing `POST /v1/member/me` returns the signed-in member's own groups, through the
  existing `MemberPortalPublisher` and its certificate pinning; only this PC's account gets
  them; reused for 5 minutes and cached in the workspace with `checked_at`, the cache answering
  while the platform cannot be reached; a platform refusal means no teams. (2) Otherwise "Teams
  I belong to on this PC" in Agent Web Settings, kept in the workspace (`team-membership.json`),
  never in host.json.
- The rule only names the local draft. Installing still needs the person's Install; publishing
  back to the platform is checked by the platform against its own records, so a team claimed on
  a PC grants nothing there. The install card says where membership came from, e.g. "Revision as
  a member of team engineering (declared on this PC)".
- No new platform endpoint: `me` already exposes only the caller's own groups (tested), so the
  Shared Platform on 141 needs no redeploy for this change.

Rejected: adding a separate `GET` teams endpoint (`me` already answers it with the same auth);
trusting the declaration when the platform is reachable (the platform's record is the source of
truth); using a stale cache after the platform refused the login (a revoked member would keep a
team); adding the member to `contributors` on revision (membership, not a recorded co-editor, is
the basis, and it would outlive leaving the team); keeping the declaration in host.json (it is a
preference, not configuration, and host.json holds credential references).

## 2026-10-19 — Agent Web gets the Personal Agent code by password sign-in and renews it

Owner approved 2026-10-19 ("先用執行A方案").

- Settings → Shared platform can get the code: account and password, one
  `sign-in/password` over the pinned client, `logins/issue-agent` with that session,
  the code stored as the paste path stores it, the sign-in's browser login revoked,
  the session dropped. The password is used in one request and kept nowhere (not in
  files, the environment, logs, the task list, telemetry, replies or conversations).
  An Agent Web settings route only; no model or agent tool reaches it. The paste
  field remains.
- The Host keeps `personal-agent-code.json` (login id, expiry, source, renewals; no
  secret) and renews the code about hourly-checked when under 7 days are left: a
  new code from the current one, stored, then the old one revoked.
- New platform route `logins/revoke`: a member revokes only their own login
  (`login_missing` otherwise). Until the platform is redeployed, renewal still works
  and the old code expires on its own; the miss is recorded without the secret.
- Settings shows the code's and the Bridge token's expiry and reminds the person to
  enroll again under 14 days.

Rejected: storing the password to sign in again later (a long-lived password copy on
every PC); renewing by re-signing in with a password (needs that copy); a longer code
lifetime instead of renewal (a leaked code would live longer); revoking through
`admin/members/sign-out` (an administrator route, and it ends every login of the
member); leaving the sign-in's browser login active (a 30-day credential nobody uses).

## 2026-10-19 — CI skips record-only pushes and cancels superseded runs

Owner: "可以先做1, 2項" (ahead of a possible switch to a private repository, where Windows Actions
minutes count double against a monthly quota; the last 19 days ran 43 verify builds of about 14
minutes each).

- `verify.yml` runs only when a push or pull request touches something a test can read: it skips
  `benchmarks/*/runs/**`, `HANDOFF.md`, `docs/*.md`, `docs/archive/**`, `docs/phases/**` and
  `docs/proposals/*.md`, and re-includes the docs tests read (`docs/deployment-validation-loop.md`,
  `docs/remote-testing-codex-loop.md`, `docs/phases/LLM_GATEWAY.md`). `docs/contracts/**`, the
  `docs/proposals/` data files, `deploy/**` and all code still trigger it.
- `concurrency: verify-<ref>` with `cancel-in-progress`: a newer push cancels the older run. A
  cancelled run is not `success`, so it never raises a deployment-validation request.

Rejected for now: moving most steps to Linux runners (would halve the cost but needs a parity check
of the Windows-only tests); a self-hosted runner (machine must stay on and runs repository code).
When a test starts reading a skipped document, add it back to the include list.

## 2026-10-19 — Verified work is committed directly to main

Owner, answering Knowledge Strategy v1.3 ADR-K9 (PR flow or direct commits to main): "如果寫好了，可以進main".

- Finished work that passed the repository's verification is committed directly to `main`. No feature
  branch or pull request is required, for documentation or code. This is the practice since 2026-10-05,
  now stated as a rule (one line in `AGENTS.md`).
- When to push stays with the owner; an agent pushes only when told to.
- Knowledge Strategy v1.3 marks ADR-K9 decided (option A).

Rejected: a feature branch and pull request for every K02+ change (option B) and pull requests for code
only (option C): with one owner reviewing and agents verifying locally and in CI, they add waiting
without adding a reviewer.


## 2026-10-19 — Open items live in GitHub Issues, and who closes them

Owner: "把現在留下來的問題和任務放在github issues"; then agreed ("同意") to the closing rules.
Issues #211–#222 hold the open decisions and verification tasks; `docs/TASKS.md` stays the record of
completed work. Closing rules (also in `AGENTS.md`): decision and meeting issues are closed by the owner
or a named decision maker after the decision is in this file (an agent may close one only on a stated
owner decision, saying so); verification issues by whoever verified; implementation issues by the
completing commit (`Closes #N`), reopened if CI fails; coordination and on-hold issues by the owner.
Every closing links its evidence. Owner-only security items are not filed as issues.

Rejected: any contributor closing any issue (a decision could be closed by someone other than the
decider); keeping the open items only in `docs/TASKS.md` (the owner kept forgetting them and wants to
discuss them with colleagues).


## 2026-10-20 — Switched-off Skills are named in the Gateway system prompt

Live test 2026-10-20: with `hermes/business-cards` installed but switched off, the Gateway model
offered to install it and asked for its name and version, because a switched-off Skill is not among
its tools and nothing else told it the Skill exists. The Gateway system prompt now names the
switched-off Skills (`namespace/name` only, at most 80, leaving out any name with another version
switched on) and says: installed but switched off, switch it on in Agent Web > Capabilities, never
install, draft or re-create it. The Host supplies the names from `assets/skills/disabled/` each turn.

Rejected: offering switched-off Skills as tools (a switched-off Skill must not run, and its tools
would crowd the catalogue it was switched off to keep small); a host tool listing them (one more
model call before every such answer); descriptions or versions in the list (the Hermes pack alone
ships about fifty switched off; names are enough to recognise one).


## 2026-10-20 — Business cards are a native AEP capability

Owner, 2026-10-20: "當然選a" (option a: build business cards into AEP rather than keep the Hermes
coding-agent Skill). A live test showed the Gateway chat reads a card photo well through the
internal gateway, but only the Hermes Skill (`cards.py`, agent mode and a shell) could store it,
and its store has no source, status, update, fax, business group or reporting lines. The owner
wants it in normal Agent Web chat and Telegram, switched on by default, nothing sent to an
external model, and an org chart from cards and email signatures that adjusts when someone left.

Decision (spec `docs/phases/BUSINESS_CARDS.md`):

- Capabilities `business-cards/*@1.0.0` with typed contracts, executed on the Bridge; a SQLite
  store per actor under the workspace, never shared. Every observation kept (source, date, ref:
  image hash or message id, never a body or an image); field-level provenance as in ADR-K11: a
  user-set value is never overwritten by an automatic source (a proposal instead), newer
  evidence updates an automatic value, everything in history and undoable by change id.
- Identity: email first; else name + company, romanised names matching the local name.
- Writes to the contact store are `write`, risk `low`, and the Host confirms them standing
  (`LocalPolicy.confirm_writes`), so a model-chosen store, departure or line runs without an
  approval card each time. Host code declares it, never an asset; only a low-risk `write`
  qualifies; grants still apply; switching the Skill off removes the tools.
- The Skill `engineering/business-cards` is shipped switched on and carries the procedure; the
  Host offers `cards__*` tools with argument schemas while it is on (a Skill command to a
  capability carries no schema). The Hermes pack's copy stays switched off; an idempotent import
  (`aep-host cards import`, `cards__import_hermes`) keeps every old row as a `card` observation.
- Org chart: Pillow (in the bundle with `weekly-mail`, in CI with `office`), nested boxes by
  business group → division → department, solid evidenced and dashed inferred lines, people who
  left omitted or grey, a Markdown legend that says when it is not a reporting chart. Agent Web
  shows the PNG under the answer (a token-guarded route serving only files listed on that
  conversation's answers); Telegram sends it with `sendPhoto`.
- Email signatures: a read-only harvest within the mail scope set in Settings (never wider),
  only messages from the named domain, only the cut signature block (≤ 1,200 characters,
  secrets redacted) to the internal gateway model; it proposes, the person confirms, then
  `add-from-signature` stores fields, message id and date.

Rejected: an approval card for every stored card or departure (the store is the person's own,
local and undoable; per-call cards would make photographing a stack of cards unusable); one-step
Workflows wrapping each write (a Workflow run, journal and form for each contact edit, and
Workflow parameters cannot carry the card's field lists); host tools that dispatch as the person
(`origin` would misstate who chose the call); Graphviz or matplotlib for the chart (Graphviz is not
on a colleague's PC, matplotlib is not in CI; Pillow is in both); storing email bodies or card
images; a Contacts page in Agent Web in this slice (the chat covers find, list and history).

## 2026-10-20 — Degrees and the unified business number are contact fields

Context: the second business-cards live test (2026-10-20) stored card A's title as "資深經理 博士"
(the degree absorbed into the title) and its division 研展處 I as 研展處; card B put its 統一編號 in
notes while card A did not. The procedure said "omit rather than invent" but nothing kept those
values apart.

Decision (`docs/phases/BUSINESS_CARDS.md` §2 "Host checks on a reading"):

- A person has `honorific` (博士, Dr., PhD) and `company_tax_id` (統一編號). The Host moves a degree
  out of `title` (博士後 stays: it is a job title) and an 8-digit unified business number out of
  `notes` on every automatic reading; the Skill, the tool schema and the signature prompt say
  the same. An existing `cards.db` gains the two columns when it is opened.
- `company_tax_id` is on the person, not a company record: the store has no company table, and
  a number on the person is shown and merged with the same provenance rules as every field.
- Division and department text is never normalised; the procedure says to copy suffixes such as
  I, II or 一處 exactly, so 研展處 I and 研展處 II are two boxes on the chart.
- With these: a romanised name is kept only when the reading says where it is printed, a field
  stays "needs confirmation" until the person confirms or corrects it, and who made a change is
  the request's actor and channel, never a model argument.

Rejected: degrees and the tax number in `notes` (the minimal option; notes are free text, so the
chart, find and the merge could not use them and two cards would again differ); a separate company
table for the tax number (a larger schema change for one value); stripping roman numerals or
"一處" when matching divisions (they name different divisions).

## 2026-10-20 — How a re-scanned card finds its person, and which reading wins

Context: in the second live re-test (2026-10-20) re-sending card A created a second person. The
reading misread the email without flagging it, and the name + company match was skipped whenever
the two emails differed, although the image's sha256 was the same as an earlier observation's. A
re-scan also replaced the stored business group "Connectivity & Solutions 事業群" with the shorter
reading "Connectivity & Solutions".

Decision (`capabilities/business_cards/store.py`, `docs/phases/BUSINESS_CARDS.md` §2):

- Matching, in order: (1) the same card image (`sha256:` source ref) as an earlier observation →
  the person that observation was stored as; (2) the same email (case-insensitive); (3) the same
  name (local or romanised) at the same company. A different email no longer makes it someone
  else, unless their place differs too: both readings have a department and they differ, or
  both have a division and they differ.
- When a match by image or name brings another email, the stored email stays; the new one is an
  open proposal; the email needs confirmation (the reading's observation lists it as uncertain)
  unless the person set or confirmed the stored one; the result carries `email_differs` and its
  summary says so.
- An automatic reading that is a strict prefix or substring of the stored value (spaces and case
  ignored) leaves the value as it is (`kept`, reason `less_complete`), for every field except
  `title` (副總經理 → 總經理 is a real change), `notes` (appended) and `email` (the key). A more
  complete reading still replaces a shorter one under the usual evidence-date rule. A user-set
  value is never overwritten, for `business_group` as for every field.

Limits: two namesakes at one company with different emails and the same (or an unread)
department and division are taken to be one person; the flagged email and the proposal let the
person correct it, and `edit-person` / `undo` remain. A wrong but identical-looking image hash is
impossible in practice; a cropped or re-photographed card has another hash and falls through to
email and name.

Rejected: email always decides (it is the field most often misread on a photo, which is how the
duplicate arose); replacing the stored email with the newer reading (the newer reading was the
wrong one in the live test); matching on name + company alone even when the department differs
(namesakes at a large company are common); treating any shorter title as partial (promotions
shorten titles).

## 2026-10-20 — How a company query finds the company

Context: "WNC" drew the company's org chart once and failed the next time: the stored company was
啟碁科技股份有限公司, people from signatures were stored as "WNC", and only a suffix-stripped name
comparison was made.

Decision (`CardStore.resolve_company`): the store groups its company spellings into companies,
joining two spellings that are the same name without legal suffixes or that share an alias. An
alias is a 2–6 letter word printed in capitals in the name (`WNC`, `ASUS`) or the company part of
an email address or website (`wnc` for `@wnc.com.tw`), never a public mail service (gmail,
yahoo, hotmail, outlook, hinet, ...). A query resolves, in order, by the exact or
suffix-stripped name, by alias, or by being part of exactly one company's name (啟碁 → 啟碁科技);
two candidates at any step mean no answer, and `org-chart`, `list` and `find` then fall back to
the name comparison. Results name the canonical spelling: the one most people carry, the
longest on a tie.

Rejected: an alias table the person maintains (more work for the person than the data already
carries); every English word of a name as an alias ("Technology" would join unrelated companies);
asking the model to pass the stored company name (it does not know it before a call, which is
how the inconsistency arose).

## 2026-10-20 — COM is initialised on the thread that uses it

Context: after an Agent Web restart the first signature harvest worked and every later mail call
failed with `handler_error`. A probe confirmed `Dispatch("Outlook.Application")` inside
`asyncio.to_thread` raised CO_E_NOTINITIALIZED: only the thread that first imported pywin32 had COM
initialised, and the adapters kept a dispatch object across calls.

Decision: `integrations.com.apartment()` initialises COM (CoInitialize / CoUninitialize, nested
uses counted) around each use. The Outlook mailbox, draft writer and draft sender ask for
Outlook inside it on every call and keep no COM object afterwards; their failures are caught
inside the block (so no COM object outlives it) and mapped to their own codes. The weekly-report
and chipset Excel runs, which hold Excel from the first write to `close` on one worker thread,
run inside one apartment each. Without pywin32 the apartment does nothing and the adapters refuse
with `library_missing` as before.

Rejected: a dedicated COM thread for all Office calls (a queue and lifetime to manage for calls
that already run on worker threads); initialising each worker thread once and never releasing it
(threads of the default pool are shared with unrelated work); `pythoncom.CoInitializeEx` with a
multithreaded apartment (Outlook's object model expects a single-threaded apartment).

## 2026-10-20 — A reading that differs from the person's own value needs confirmation

Context: in the third live test (2026-10-20) a re-scan read another email than the one the person
had confirmed. The reply asked which was right, but the field was not flagged and no proposal was
open (the reading had listed the email as uncertain, which kept it without a proposal, and a
user-set field was never flagged), so 「X 的 email 正確」 found nothing to confirm. A re-scan also
logged "(03) 666-7799" → "(03) 666 7799" as a change.

Decision (`capabilities/business_cards/store.py`, `docs/phases/BUSINESS_CARDS.md` §2):

- Any automatic reading that differs from the person's own (set or confirmed) value is one open
  proposal (stored value, read value, observation id; the same value is not proposed twice), sure
  or unsure. A field needs confirmation while it has an open proposal, whatever its source, so the
  chart and legend show 需確認. A reading that is part of the stored value (`less_complete`) is not
  a conflict and is not proposed.
- `edit-person` closes proposals: `confirm` keeps the stored value, rejects the field's open
  proposals and writes a `confirm` row; the read value in `fields`, or `accept` (「用新的」),
  takes it and accepts them (a `field` row). Undo opens them again. `proposals` lists the open
  ones.
- Phone, fax and mobile compare by digits and extension (`names.phone_key`: spaces, hyphens, dots
  and parentheses ignored, +886 is a leading 0); a formatting-only difference is no change.

Supersedes the part of "How a re-scanned card finds its person" that left a user-set email
without a flag. Rejected: flagging only email (the owner asked for every field); proposing a
partial reading (it would flag every shortened 事業群); keeping the newest format of a number (each
re-scan would flip it).

## 2026-10-20 — Fixable tool failures are retried, lasting-change claims need a changing tool, reusable means a Workflow draft

Context: a live Gateway conversation on 2026-10-20 (interactive HTML org chart). `coding__run`
failed with `coding_workspace_missing` for a folder under `Documents\aep-workflows`, and the Agent
twice asked the owner to create it by hand, after two or three tool calls of a 150-call budget.
Told 「執行時不需要問是否包含在職人員…」, it answered 「規則我已改成…」 after only `cards__list`;
nothing was saved and the Host check passed it, because any successful tool backed any claim. The
owner expected something to apply again, but only one-off code ran: no draft, no install card,
nothing in Capabilities. Owner approval 2026-10-20: 「請幫我全做」.

Decisions:

1. **A missing task folder under a coding root is created** (`capabilities/coding_change/run_python.py`,
   `workspaces.py`): after every pre-run check (runner, network block), with `input/` and
   `output/`; the result carries `workspace_created`. Outside the roots it stays
   `coding_workspace_not_allowed`; a path with `..` is refused even when it resolves inside a root;
   a file is `coding_workspace_not_a_folder`. The workspace note tells the model the folder is
   created. No default folder when the model gives none: `engineering/run-python@1.0.0` keeps
   `workspace` required (making it optional needs new Workflow and Skill versions; the model picks
   a task-named folder under the root as the note says).
2. **Every failed conversation tool call carries `recovery {recoverable, hint}`**
   (`agent/tool_recovery.py`), decided by the Host from the failure code: wrong or missing
   arguments (`invalid_input` with the field named, Workflow run values, draft problems, a folder
   outside the roots, an unknown tool name) and retryable failures are recoverable; permission,
   approval, credentials, missing installs, connectivity and mail scope need the person; unknown
   codes are not recoverable. The system prompt: fix a recoverable call and retry in the same turn;
   ask the person only when it needs them or the corrected call failed too. The repetition guard
   stays.
3. **A claim of a lasting change needs a tool that changes something** (`no_unbacked_action_claim`,
   `agent/conversation_harness.py`): 「規則我已改成」「已改成」「已設定」「已更新規則」「已記住」
   「以後都會」, "I've updated the rule", "from now on I will", "I'll remember". Chinese phrases
   count at a clause start or after a first-person subject. Read-only tools (Knowledge answers;
   commands starting list, get, show, preview, search, read, find, lookup, view, history,
   proposals, inspect, query, ask) and failed tools do not back it. The system prompt says the
   Agent keeps no rules between conversations unless a tool saves them, and should propose a
   Workflow draft or a settings proposal instead.
4. **Reusable means a Workflow draft**: the Gateway prompt (when `authoring__draft_workflow` is
   offered), the draft tool description and coding Skill `engineering/coding@1.8.0` say that a
   reusable request is answered with a Workflow draft whose step is `coding/run-python@1.0.0` with
   the script fixed and typed parameters; a one-off request may use `coding__run` alone. A new Host
   check `reusable_request_drafted` sends back once a turn whose person asked for something
   reusable, that ran `coding__…` and drafted nothing, while a draft tool was offered. The person's
   press on the install card remains the only install.

Rejected: a model-judged "is this fixable" (the Host decides from codes, deterministic); treating
every non-read capability by its manifest side effect for item 3 (the claim check sees only the
turn's tool record; command names are enough and err toward not flagging); auto-drafting a
Workflow from a `coding__run` without the model (the model writes the parameters); naming the
coding Skill revision 1.7.1 (the change is a behaviour rule, a minor version; the paused
rule-following wording proposal once called "1.8.0" stays paused and would come later).

## 2026-10-20 — In-chat HTML runs in an opaque-origin sandbox from a nonce address; files open in a viewer panel

Owner (2026-10-20, 「請幫我全做」, then extended the same day): the org chart can be interactive
HTML, shown in the chat; every file on an answer opens in a viewer panel with Preview / Code, as
in Codex and Claude Code.

Decision:

1. **The org chart gains `format` (`png` default, `html`, `both`)**, generated natively
   (`capabilities/business_cards/chart_html.py`) from the same rows as the PNG, as one
   self-contained file: inline CSS, script and JSON data, no network, no CDN, a `<meta>` CSP
   `default-src 'none'`. Data is escaped for the `<script>` block and the script uses only text
   nodes, so contact data cannot inject markup. General: no company is built in.
2. **HTML in Agent Web is framed from a short-lived nonce address, not `srcdoc` and not the
   token route.** The page asks `GET /api/conversations/view-link` with its token; the Host
   returns `/view/file?nonce=<24 random bytes>` (15 minutes, bound to one conversation and one
   listed file, which must still be listed and under the workspace). That address is served with
   `Content-Security-Policy: default-src 'none'; script-src 'unsafe-inline'; style-src
   'unsafe-inline'; img-src data:; font-src data:; form-action 'none'; base-uri 'none';
   frame-ancestors 'self'; sandbox allow-scripts`, `X-Frame-Options: SAMEORIGIN`,
   `Referrer-Policy: no-referrer`, and framed with `<iframe sandbox="allow-scripts">`, never
   `allow-same-origin`. So the frame has an opaque origin: it cannot read the page, its
   `TOKEN`, storage or cookies, cannot call the API with the token, cannot reach any network,
   and its own address carries only the nonce, which opens that one file. Opened in a tab of its
   own ("在瀏覽器開啟"), the CSP `sandbox` keeps it opaque-origin too.
3. **The token route serves text as plain text.** `/api/conversations/file` (token header) now
   also serves the person's own attachments listed on the conversation, and serves HTML and other
   text as `text/plain; charset=utf-8` (images as themselves, `.md` as `text/markdown`) with
   `X-Frame-Options: DENY`; the page shows text with `textContent` (Code view) or the existing
   DOM-building Markdown renderer (no raw HTML). The viewer never builds a path: it only asks
   for paths listed on the conversation's messages.
4. **The viewer panel** (side panel; full-screen sheet under 760 px): chip per file; Preview /
   Code where both apply (HTML, Markdown, CSV table), image preview only, text files Code only
   with line numbers, a 5,000-line / 1 MB cap with a notice, copy, download, open in browser,
   Esc to close, focus kept inside, 44 px targets.
5. **Telegram** sends the HTML with `sendDocument` and a one-line caption to open it in a
   browser; the PNG photo stays when the format is `both`.

Rejected: `srcdoc` fetched by the parent (a `srcdoc` document inherits the parent's policy and
gets no response header of its own, so the required CSP header could not be set, and the parent
would hold and inject the markup); `iframe src` on the token route (the token would have to be in
the frame's URL, where the frame and history can read it, and the route sends
`X-Frame-Options: DENY`); a blob URL (inherits the parent's origin policy, no CSP header);
`allow-same-origin` (would give the file the page's origin and so its token); a Markdown or
syntax-highlighting library (the page is one inline string with no external code). HTML a
`coding/run-python` step writes in a workspace is not attached to answers today, so it is not
shown inline; the viewer shows any file that does become an answer attachment the same way.

## 2026-10-20 — Accumulated memory M1: one memory database per actor, spaces declared in manifests, merge rules as data

Context: the owner approved the accumulated-memory design (`docs/phases/ACCUMULATED_MEMORY.md`,
decisions §10) and asked for M1: the Memory Service skeleton, space registration in manifests,
the shared provenance / history / undo / proposals, per-actor isolation, and the business-cards
`cards.db` moved into the first space with every existing behaviour and test kept.

Decisions (Claude Code, within the approved design; §11 of the spec has the details):

1. **One SQLite file per actor** (`<workspace>/memory/<actor-key>/memory.sqlite`), the shared
   facilities in **shared tables keyed by `space`** (observations, field_sources, history, undone,
   proposals, external_ids) and each manager's own tables **named after the space**
   (`contacts_org__people`). Shared tables let M4 list everything to confirm across spaces with
   one query; change ids, observation ids and proposal ids stay unique per actor.
2. **Declarations in the manifest** (`memory_spaces` on Skill and Workflow manifests), optional and
   omitted when empty so no existing manifest's bytes or digest change (only the business-cards
   Skill gains one). Roles nest (manager ⊃ contributor ⊃ reader); an asset is known by namespace
   and name, so every version keeps its access. One manager per space, refused at sync and when
   switching a Skill or Workflow on; the Host's registry also takes the shipped manifests (the
   Host's own code), so the native business-cards capabilities keep their access even while the
   installed copy of the Skill predates the section.
3. **Merge rules are data** (`MergeRules`, stored as JSON in the space's registry row), evaluated by
   one generic `decide`: the person's statement wins; a value the person set is never replaced and
   differing evidence becomes a proposal; `precedence` by trust class for the company (card over
   C4C, C4C mismatches propose); newest evidence for title and place; uncertain or older readings
   kept out; external ids match only; reporting lines solid only on `user`, `signature` or
   `email_content`; auto-merge across sources only on an identical email or a mapped external id.
   For contacts the person's value proposes on **any** differing evidence, older included, as
   the store already did after the third live test; `propose_if_newer` exists as data for spaces
   that want the owner's narrower wording. Business-card matching (image hash, email, name +
   company) stays the business-cards package's own rule; the cross-source auto-merge rule is for
   other contributors.
4. **Writes are observations only.** Observations are append-only (SQLite triggers refuse DELETE
   and any UPDATE but setting `retracted_by` once). The person's edits, confirmations,
   departures and reporting lines are `user` observations plus history; undoing a change retracts
   the person's statements in it, while card and signature sightings stay. Undoing a creation now
   retracts that person's observations instead of deleting them. `cards__history` keeps listing
   only sightings.
5. **Provenance in ADR-K11 terms**: `field_sources` gains `origin` (`human` | `tool` | `import` |
   `agent` | `migration`), `set_by` (the Host's `<actor> via <channel>`), `set_at`, `reason`.
   Contracts are shared with Knowledge Strategy, never the data (owner §10.5).
6. **Migration once, lossless, transactional**, with a verified byte copy first
   (`cards.db.bak-<UTC stamp>`, under SQLite's shared read lock, same SHA-256, integrity check,
   same row counts; an identical copy is reused), every id kept so every reference still holds,
   each row read back and compared before commit, a marker with the source's size, time and hash.
   `cards.db` is opened read-only and never written again. On failure: **a clear error, not a
   read-only fallback** (one code path; the old file and its backup stay for the previous version).
   If `cards.db` changes after the migration (the previous version was run again), the store
   refuses (`memory_legacy_changed`) instead of silently ignoring that data.

Rejected: one table set per space for everything (duplicates the shared facilities and needs a
union per space for the cross-space confirm page); a generic key-value store (§3.10); deleting
observations on undo (breaks append-only); SQLite's backup API for the copy (its output is not
byte-identical, so an identical earlier backup could not be recognised and repeated failures
would pile up copies); keeping `cards.db` as a live fallback store (two stores to keep in step);
re-migrating automatically when `cards.db` changes after the migration (would merge two
histories with clashing ids).

## 2026-10-20 — Accumulated memory M2: generic sync state, incremental harvest, the org chart harvests in the same call

Context: M2 of `docs/phases/ACCUMULATED_MEMORY.md` (§3.3, §4, §9; owner decision §10.1: when the
org chart is asked for, first read the company's new mail incrementally; new people still need
confirmation; no nightly background harvest). Spec §12 "M2 as built".

Decisions:

1. **Sync state is a Memory Service facility, not a business-cards table.** Shared tables
   `sync_state` (`space`, `source`, `key` → `last_message_date`, a bounded id set (500),
   `extractor_version`, `updated_at`, `updated_by`) and `sync_history` (every advance, reset and
   restore with the full state before and after), usable by any space whose manager declares the
   `sync_state` kind. It only moves forward; another extractor version needs a reset first; a
   reset deletes the row and keeps the old value in history, and `restore_sync` puts any earlier
   state back. The business-cards declaration adds the kind (only its manifest digest changes).
2. **The window**: first pass = the configured scope; then from the last processed message minus
   one day of overlap, skipping the ids processed near the boundary; the configured scope always
   caps it. Messages already observed (`source_ref`) are skipped and counted. After a failure
   nothing moves; with messages left unprocessed (unreadable, or beyond the people limit) the state
   stops just before the oldest of them. Only processed-before messages in an incremental pass:
   nothing moves and no history row is written.
3. **Extractor changes re-read stored mail but propose only differences.** `EXTRACTOR_VERSION` in
   `signatures.py`; a mismatch resets and reads the full scope, including messages already
   observed, and lists a stored person again only when the new reading would change a field. A
   manual 「重新整理」 (`full: true`) resets and reads the full scope but still skips observed
   messages (declined or expired candidates come back).
4. **The org chart harvests inside the same capability call** (`org-chart` `harvest_first`), with
   the Skill procedure telling the conversation to pass `true` when the person asks for a chart.
   One tool call returns the chart of what is stored plus the harvest's candidates (never stored,
   not on the chart) or a `harvest_note` saying why the harvest was skipped (no known domain, mail
   or model unavailable); the chart is drawn either way. The capability default stays `false`.
5. **The 50-message search cap stays**; a pass that hits it says so (`truncated`, 「只處理了最新的
   50 封」) instead of pretending to be complete.
6. The M1 open point (the person's value proposes on any differing evidence vs only newer,
   `propose_if_newer`) is left to the owner; M2 changes no merge rule.

Rejected: per-skill sync tables (§3.3: one shared facility); advancing the state only when the
person stores the candidates (a declined person would be proposed forever, and a harvest the
person ignores would re-read the same mail every time); a separate orchestrated "harvest then
chart" step or Workflow (an extra layer, and it invites auto-storing); defaulting `harvest_first`
to true in the Host (every existing caller, CLI and Workflow included, would start reading mail);
re-reading observed mail on a manual reset (re-proposes everyone already stored); moving the state
to the newest message even when some could not be read (silently loses them).

## 2026-10-20 — New evidence updates organisational fields directly; email stays a proposal (owner)

Context: the M1 open point (a value the person set: propose on any differing evidence, or only on
newer evidence). Owner decision 2026-10-20, final wording 「換部門, 或換職位, 就修改那一筆資料」:
a department or title change simply updates that person's record. Spec
`docs/phases/ACCUMULATED_MEMORY.md` §3.8.3 "新證據" and §13.

Decisions:

1. **What is new evidence** against a value the person set:
   - a **business card** carries no evidence date: a card image hash **never observed before for
     that person** is new; a re-scan of a seen image is old evidence. A card without an image (and
     an imported Hermes card) has no stable identity and is never new evidence. The card's scan
     date is never compared with the person's change;
   - an **email signature** is new when its **sent date** (by day) is after the day of the
     person's last change to that field (`field_sources.source_date` of the `user` value, the
     local day of `set_at`); the same day or earlier is old. The sent date also drives the sync
     window (M2);
   - future sources without a date follow the card rule only with a stable identity (an image
     hash); otherwise they are never new evidence, because nothing tells whether the person has
     already seen and corrected them.
2. **Old evidence** never changes or challenges a value the person set: no change, no proposal,
   no `kept` entry, no `email_differs`. Fields the person did not set keep the existing
   newest-evidence and precedence rules.
3. **New evidence updates the organisational fields directly**, even over the person's value:
   title, department, division, business group, honorific, phone, ext, mobile, fax, address
   (`user_conflict: take_if_newer`). A normal `field` history row (reason `new card <image ref>` or
   `newer email <message id>`), undoable; the reply leads with 「上次是…，現在是…」. An uncertain
   reading only proposes.
4. **The email stays a proposal** (the identity key; the model has misread emails on cards
   several times): new evidence with another email is a 需確認 proposal, never an overwrite. The
   company's official name keeps its precedence rule (card over C4C) and, like the remaining
   fields, new evidence against the person's value proposes (`propose_if_newer`).
5. **Rules as data**: `FieldMergeRule.user_conflict` gains `take_if_newer`; `MergeRules.undated`
   lists the undated kinds (`card`, `import`); `merge.decide(novel=)`; `contacts.org.merge.v2`.
6. **One-time cleanup**: on the first open of each actor's store (after the `cards.db` migration,
   so moved data is covered), open proposals against a user-set value that came from old evidence
   (a re-scanned seen image, a signature not newer than the change) are dismissed in one change
   group, a `proposal_rule` history row each (reason "older than the person's change, rule
   2026-10-20"), undoable with `cards__undo` (rows `proposal_reopen`); a meta marker makes it run
   once, so an undo is not redone. Proposals from new evidence stay open for the person.

Rejected: comparing a card's scan date (a re-scan would always look newer; the first-seen-date
variant the owner considered first still invents a date a card does not have); proposing on new
evidence for the organisational fields too (the owner wants the record simply updated);
overwriting the email on new evidence (repeated misreads of the identity key); re-running the
cleanup on every open (an undo would be silently redone).

## 2026-10-20 — Opt-in browser diagnostics (`AEP_BROWSER_DIAG_DIR`) for the CI real-browser failures

Context: since 2026-10-20 04:58 UTC every "Platform verification" run has failed
`tests/test_browser.py::test_a_signed_in_profile_is_what_carries_the_session` (and in the latest
run two more real-browser tests) with `WebSocketError: closed` then `BrowserError: no_page`.
Locally they pass. The logs disproved the leading hypothesis: the green run a794b590 and all red
runs ran on the same runner image (`windows-2025-vs2026` 20261007.264.1, provisioner
20261002.596), and the same test had already failed once at 4b87b145 (2026-10-19 13:11) on that
image. The first red commit, d0c1009e, changed no browser code. The Edge version was never logged,
so an Edge change inside the same image (an in-place update) can be neither confirmed nor ruled
out.

Decision: diagnose before any further fix, and do not skip, xfail or weaken the tests (owner,
option A).

1. `integrations.browser` reads `AEP_BROWSER_DIAG_DIR` once per `Browser`. When it is set and not
   blank, the browser gets `--enable-logging=stderr --v=0` and its stderr is appended to
   `browser-<ns>-<pid>.stderr.log` in that folder (first line: the arguments and the current
   pytest test id), and every `no_page` and `navigation_failed` writes
   `browser-<ns>-<pid>-<code>.json` with `/json/version` and `/json/list` reduced to each target's
   `type` and `url`. No titles or page content are written. A diagnostic that cannot be written is
   ignored, and the original error is still raised.
2. Unset or blank, nothing changes: the same arguments, stderr to `DEVNULL`, no endpoint fetched
   and no file written (`tests/test_browser_diagnostics.py`).
3. `.github/workflows/verify.yml` logs the Edge/Chrome version, version folders, staged
   `new_*.exe` updates and the Edge update services before pytest. It sets the variable for
   pytest and, on failure, records the same listing again and uploads the folder as
   `browser-diagnostics-<sha>`.

Lead from the first local run with the switch on (Edge 155.0.4283.45, not yet seen on CI): a
fresh headless profile publishes an `edge://sync-confirmation-dialog/` target of type `page`,
listed before the `about:blank` tab, in 7 of 8 samples. `Browser.page()` takes the first `page`
target, so it drives that browser-UI dialog rather than the tab. If Edge closes that dialog, the
socket would close mid-navigation and a reattach could pick the dialog again, which is the CI
signature. The image ships Edge 154.0.4258.62 and Chrome 155.0.8059.40. Whether the runner's Edge
updates itself or shows this dialog is exactly what the artifact will show. Proposed fix, not
applied: `page()` prefers a `page` target that is not browser UI (`edge://`, `chrome://`), and
only falls back to the first `page` target.

Rejected: changing launch flags now (`--no-startup-window` plus `Target.createTarget`, disabling
Edge features or the updater). Nothing in the logs proves which startup behaviour closes the tab,
and three blind hardening commits (24ecf729, 7c4ef3b1, 99949c63) did not stop it. Always-on
logging was also rejected: it would change what every installed Agent writes, and the browser log
can be large.

## 2026-10-20 — Later CI checks run when pytest fails

Context: owner, 2026-10-20. Since the real-browser failures began, every red pytest step skipped
the rest of "Platform verification": ruff, ruff format, mypy, build, pip check and both bundle
build/install steps. A red run reported one problem and hid any others.

Decision: in `.github/workflows/verify.yml` the pytest step has `id: pytest`. The checks after it
use `if: ${{ !cancelled() && (success() || steps.pytest.outcome == 'failure') }}`, so they run when
every earlier step passed or when pytest failed. The two bundle build/install steps also require
`steps.build.outcome == 'success'`, so a broken wheel build is not followed by confusing install
failures. "Annotate failed tests" and the browser-diagnostics steps keep `if: failure()`. The two
preview uploads keep the default `success()`, so a red commit never publishes a bundle (deployment
already takes only successful runs).

The job still ends failed whenever pytest or any other step fails, and every test still runs.

Rejected: `continue-on-error: true` on pytest (the job would turn green with failing tests);
`always()` (it would run after cancellation and after a failed install, where every later step
fails for that reason alone).

## 2026-10-20 — Loan replies 06 / 06b: two Workflows, drafts, per-message send

Context: owner, 2026-10-20: port rs_workflow_system 06 (loan_scan) and 06b (loan_process) without
n8n; two Workflows; drafts by default with an optional send that needs one approval per message;
no schedule for now. Closes owner question 5 of `docs/phases/RS_WORKFLOW_MIGRATION.md`.

Decision:
1. Two Workflows, `engineering/rs-loan-customer-block-scan` (`/run 6`) and
   `engineering/rs-loan-queue-reply`, each runnable alone. The producer does not start the
   consumer: its last step returns a `follow_up` (a Workflow identity and a label) that Agent Web
   draws as the consumer's run form under the answer (`workflow_form`, origin `follow_up`) and
   Telegram as a button sending `/run engineering/rs-loan-queue-reply`, which opens the question
   flow. The consumer writes customer-facing drafts and drives signed-in browsers; a chain would
   skip the per-run confirmation the run-approval model requires for `write` Workflows.
2. ADAPT with the source modules carried: `rules`, `templates`, `queue` are the source text plus
   declared replacements; `scan`, `process` are the source jobs with seams (bridge, queue root,
   stamp switch) and `process_one` split into `look_up` + `draft_reply`. The source tests are
   vendored unchanged apart from imports as the oracle (`tests/loan_oracle.py`). WRAP was not
   possible: the jobs need the source's HTTP Bridge, `requests` and its PowerShell Edge sessions.
3. Capabilities: `loan/scan-mail` (read), `loan/enqueue` (write), `loan/look-up` (read, web),
   `loan/draft-replies` (write, Outlook draft), `loan/offer-send` (write, local cards); the send
   `loan/send-reply` is `external_side_effect`, declared and never installed.
4. Sending: `host_runtime/loan_reply_cards.py` keeps `ls-` cards (CardStore, shared file between
   the offering step and Agent Web). Send / Keep as draft; one card per draft; no send-all; Agent
   Web only (Telegram shows the card, `web_only`), as for the agent's mail cards; the draft is
   sent only if its recipients, subject and attachment names still match the card
   (`integrations.outlook_send`); a card expires after 24 hours and the draft stays. The guard
   test now allows exactly two importers of `outlook_send` besides Agent Web and pins one
   `send(` call in each card's `decide`.
5. Queue: the source's dedicated file queue under `workspace/loan-reply/loan-queue` (pending /
   claimed / done / failed, atomic-rename claims, reclaim TTL, run lock), not the Memory Service
   `sync_state`, which is a forward-only cursor and has no per-item claim or failed state.
6. Credentials: none are stored or asked. The loan portal and C4C sign in through persistent
   Edge profiles under `workspace/loan-reply/edge/`; the portal's Entra account tile is clicked as
   in the source (`loan_account` setting is an address, not a secret).
7. A queued link is opened only when it points at `portal_origin` (default
   `https://rstw-portal.rsint.net`); the source opened any FastView link from a mail.
8. A dry run writes nothing: the first-run cut-off is stamped by the first real scan (the
   source's dry scan stamped it).
9. Shipped switched off (`host_runtime.assets.shipped_off`, installed into `disabled/` once by
   `install-bundled` and written there by `export-assets`): a loan desk's business Workflows; a
   colleague who needs them switches them on.
10. No schedule is created; the person may add one in Schedules (USER_GUIDE §9.3).

Rejected alternatives:
- One Workflow with an automatic chain (the n8n shape): the consumer would run unconfirmed.
- Sending in bulk or from Telegram: the owner's rule is one press per message; mail cards are
  decided in Agent Web.
- Reusing the agent's `ml-` mail cards: they belong to a waiting agent turn and expire when it
  ends; Workflow drafts have no waiting turn.
- Memory Service `sync_state` as the queue (see 5).
- A send capability a Workflow step could call: any caller other than a card press could send.

## 2026-10-21 — Knowledge Strategy v1.3 approved; BI domain review; priority lives in the Skill

Owner answers on GitHub issues #211, #213 and #222 (2026-10-21):

- **#211 Knowledge Strategy v1.3 approved** ("核準"): BI Schema v1, the revised MVP scope (Case A first) and
  the integrated schedule. AEP-K02 and later are no longer blocked on owner approval; they follow the
  schedule in v1.3 §7 and the E2E-01 priority.
- **#213 BI knowledge gets domain-owner review** ("是的"). This is a BI exception to
  `docs/phases/KNOWLEDGE_COLLAB.md` (no domain-owner approval for the general Wiki), which stays as it is
  for the general Wiki. ADR-K5 is decided. The E2E-05 / ARCHITECTURE wording that required domain-owner
  approval is to be reconciled to "BI: yes; general Wiki: no" when K07 is built.
- **#222 priority is not stored per document or record.** Owner: priority means "how much this helps a
  company opportunity", a domain-knowledge judgement; it belongs in the **Skill** (its procedure and rubric),
  not as a field set on every document. This supersedes the 2026-10-19 decision to scope a stored
  `priorities` collection by market and period, and the ADR-K11 priority rubric as stored data: Schema v1
  and the mock drop the stored `priorities`; ranking is computed by the BI Skill when asked, and the
  dashboard ranks by the Skill's assessment with its reasons shown. The "market" question (#222) is
  therefore closed.

## 2026-10-21 — BI data is INTERNAL; classification routes models, sharing decides access

Owner on GitHub #214 ("按你的意思做"): BI customer data (and the BI vault / contacts memory derived from it)
is classified **INTERNAL**. Classification decides which model may receive the data — INTERNAL goes only to the
company's internal gateway, never to external agents such as Claude Code or Codex — and does **not** add access
control. Who may read is decided by who the vault or database is shared with, as the owner described; no extra
per-user permission layer is added. ADR-K8 is decided. CONFIDENTIAL and RESTRICTED stay available for data the
owner marks explicitly.

## 2026-10-21 — Accumulated memory M3: preferences and notes are Host-managed spaces; only the person's press saves

Context: M3 of `docs/phases/ACCUMULATED_MEMORY.md` (§5, §3.9, §9; owner decisions §10.3 「按一下才存、
Agent Web 可管理」 and §10.8: notes saved in one click, the Agent may propose at most once per
conversation, notes are queried only when a Skill or Workflow declares a read or when the person asks
about earlier notes). Spec §14 "M3 as built"; contracts in `docs/CONTRACTS.md` (Preferences and notes).

Decisions:

1. **Two spaces the Host manages, not a Skill**: `personal/preferences` and `personal/notes`
   (`memory.personal`, manager `host/memory`, declared before any manifest so no installed asset can
   take them). They live in the same per-actor `memory.sqlite`, reuse M1's history and undo, and add
   `SpaceTx.changed_after` (an undo is refused when a later change touched the same row). A Skill or
   Workflow reads notes by declaring `personal/notes` as reader and going through the manager's API
   (`memory.notes.for_reader`); preferences are read only by the Host.
2. **No model tool saves.** The model gets `memory__propose_preference` and `memory__propose_note`,
   which only create a card (`mm-` ids, 24 h); the press in Agent Web or Telegram saves, recorded as
   `<actor> via <channel>` with the conversation and message as the source. One-click note saving is an
   Agent Web route (`/api/memory/notes/save`) that takes the text from the stored answer; a selection
   must be inside it (compared on letters and digits, so Markdown marks do not matter).
3. **Memory cards do not end the turn** (`ActionCard.ends_turn`, default true for every existing
   card): the model finishes its answer and the card shows under it. Telegram needed one branch to put
   the answer before such a card.
4. **The conflict check is deterministic**: same scope, same subject (the text without negation and
   filler words, equal or `difflib` ratio ≥ 0.8, or equal given subjects) and opposite polarity
   (negation words, with 別 inside words such as 特別 excluded). A conflict turns the card into a
   question showing both (取代舊的 / 兩條都留 / 不用); a duplicate is not saved again. No model check:
   the deterministic rule covers "the same thing, the other way round" with no egress and no latency;
   different wordings of the same rule are left to the M5 health check.
5. **Injection follows the tools a pass offers**: the Gateway asks the Host (`Gateway.turn_memory`)
   with the Skills whose tools are offered after selection (commands `<alias>__…` and host tools under
   the alias, such as `cards__…`); the Host adds those Skills' active preferences (the Skill scope and
   the spaces it declares), newest first, at most 12 and 1,600 characters, labelled as the person's.
   Their ids are recorded on the result and the stored answer (`preferences_used`) for M5.
6. **Notes search**: `notes__search` is offered when a Skill in use declares a notes read, or the
   person's message matches `NOTES_ASKED` (documented phrases). Results carry `[筆記 <note_id>]`.
   Notes are never injected. The business-cards Skill declares the read for the org chart's 「相關筆記」,
   so while it is switched on the search is offered in every turn.
7. **The note proposal limit** is counted by the Host from its card records per conversation; a
   Telegram chat (whose session never ends) counts per Asia/Taipei day. The Host check's retry in the
   same turn gets the same card back.
8. The proposals never back a "lasting change" claim (`PROPOSAL_ONLY_TOOLS`); `MEMORY_GUIDANCE` and
   the claim check's retry text point to `memory__propose_preference`.

Rejected: a model tool that saves directly (against §10.3); ending the turn on a memory card (the
answer to the actual request would be lost, in Telegram entirely); a model-based conflict check at
save (egress and latency for each press, and the owner asked for cheap); per-Skill preference tables
(§3.3: one shared facility); injecting notes (§3.9); offering `notes__search` in every turn regardless
of declarations.

## 2026-10-21 — Accumulated memory M4: the memory page acts as the owner of the actor's database

Context: M4 of `docs/phases/ACCUMULATED_MEMORY.md` (§6 memory page, §3.6 export and delete, §3.9
notes management). Spec §15 "M4 as built"; contracts in `docs/CONTRACTS.md` (Memory page); user guide
§4.9.

Decisions:

1. **The page is the person's own management, not an asset.** Host routes for the signed-in actor
   open spaces through `MemoryService.owned(space)` with the manager's reach; no asset declaration is
   involved and no model tool reaches any of it (the three M3 tools stay the only memory tools). Each
   change is recorded as `<actor> via web`.
2. **Proposal decisions reuse the manager.** For `contacts/org`, 保留原值 / 改用新值 are the same
   `CardStore.edit` calls as 「Email 正確」 / 「用新的」 in the chat (confirm the field; take that
   proposal's value), so provenance, history and undo are the store's. A space without such an adapter
   can only keep the stored value (the proposal is rejected with a history row); taking a value there
   would bypass its manager's merge rules.
3. **A preference edit keeps its id** (`Preferences.edit`, history `preference_edit`) and goes through
   the same deterministic check as a save: another active preference with the same rule refuses, a
   contradiction is asked about (取代舊的 replaces it in the same change / 兩條都留).
4. **Deleting a space's data is the one exception to append-only observations**: in one transaction
   the space's own tables and its rows of every shared table go (the observations trigger is dropped
   and re-created inside it); the space stays registered; one `space_deletions` row keeps time, actor,
   reason and row counts, never content (§3.6). Not undoable, so the page offers the export first and
   asks for the space name, which the route checks too. `meta` stays, so a migrated `cards.db` is not
   migrated again; the old `cards.db` and its backups are outside the memory database and are not
   deleted (said on the page and in the guide; owner to decide if they should be).
5. **Retention uses what exists.** Conversations (kept until deleted, 100 messages each) and run
   records (30 days / 500 MB) are shown read-only; the experience-case retention is the existing
   Reviews setting; the spaces' declared retention is shown read-only. No new retention settings and no
   expiry processing in M4.
6. **One overview call**, filtering notes in the browser; an orphan is a space whose manager is neither
   the Host nor an installed (on or off) Skill or Workflow.

Rejected: a generic "take the new value" for any space (bypasses the manager's own view and rules);
deleting by marking rows (content would stay, against §3.6); a new conversation-retention setting
(not asked for; changes record handling beyond M4); a model tool for any of these (§3.4, §10.3).

## 2026-10-21 — Accumulated memory M5: the health check only finds; every fix is a press

Context: M5 of `docs/phases/ACCUMULATED_MEMORY.md` (§7 what goes wrong, §8.2 freshness, §8.4 nightly
health check, §8.5 「為什麼這樣做」). Spec §16 "M5 as built"; contracts in `docs/CONTRACTS.md` (Memory
quality); user guide §4.10.

Decisions:

1. **Freshness is merge-rule data.** `MergeRules.freshness` (`FreshnessRule`: `entities` with an
   entity kind, a period, the statuses asked about and a question with `{name}`; `sync_state` with a
   period). `contacts/org` ships 12 months / 「{name} 是否仍在職？」 for active people and 30 days for
   sync states. The rules id stays `contacts.org.merge.v2` (an added, defaulted field; the stored
   `rules_json` updates on open); the person's `freshness_months` setting overrides the entity period.
   "Seen" is the newest observation of any source, the person's own word included, so 仍在職 is a
   `user` observation and needs no new field.
2. **The check reads; its only output is its own table.** `health_findings` in the actor's database,
   keyed (`space`, `kind`, `key`) so a second run updates rather than repeats: dismissed stays
   dismissed (an unused preference is asked again after another `unused_days`), a fix that was undone
   opens again, an open one no longer found goes. Fixes are the person's presses through the stores'
   existing, undoable writes (`set_status`, `Preferences.remove`) and one new one, `merge_people`.
3. **Merging keeps observations append-only.** The dropped entry's row goes (kept whole in its
   `merged_away` history row, so `CardStore.undo` puts it back first); its observations stay under its
   old id; `keep` takes only values it lacks, as the person's (`user`), and the dropped entry's lines.
   Never automatic, and only for pairs the check offered (same email, or same name and company the
   matcher kept apart).
4. **Contradictions: one bounded structured question per scope**, to the internal model the experience
   review already uses (`review_model`, through the internal gateway): only scopes with ≥ 2 active
   preferences, ≤ 5 scopes, ≤ 12 rules each, rule texts only, `max_output_tokens` 500, ≤ 5 pairs back,
   numbers checked. Pairs the deterministic M3 check finds are dropped (they were kept on purpose).
   No model: skipped and said so; the other checks still run. Switched off or fewer than two: no call.
5. **Unused = not carried by an answer**, from a small `uses` table (ids and times; Agent Web and
   Telegram both record) plus the stored conversations' `preferences_used` from before M5.
6. **Per actor, nightly with the experience review.** `nightly_tick` runs the check for every memory
   database on the Host (each names its actor in `meta.actor`, written on open), each with its own
   switch, then the review as before; the report gets counts only (`ReviewReport.memory_health`), and a
   night without a review writes a counts-only report. Telemetry: counts and the model state only.
7. **「為什麼」 records references, not content.** `ConversationMessage.memory_used` (≤ 40
   `<space>:<kind>:<id>`), derived from the turn's tool results (contacts returned by `cards__*`, sync
   keys a harvest moved, notes the answer cites from `notes__search`); labels are looked up when the
   person asks. Telegram keeps the last turn per chat in memory for `/why`.

Rejected: auto-merging duplicates or auto-marking people as left (against §10.7 and "按一下才存");
a model call on every preference save (M3 decided deterministic; the nightly bounded question covers
the rest); storing the "why" text on each message (content duplicated, stale after edits); a separate
health-report file outside `review-*` (the owner asked for it in the nightly report); hard-coded
freshness periods in the check.

## 2026-10-21 — CI real-browser failures, round 2: socket traces, a pong fix, and the hung-navigation lead

Context: CI run 39479473515 (e7247e3e) failed `tests/test_browser.py::test_the_element_list_is_what_can_be_used_and_nothing_else`
with `no_page`. Its diagnostics artifact showed one target, a `page` already at the test site's
`/index.html`; no `edge://` dialog (the 2026-10-20 sync-dialog lead is not supported). Edge
154.0.4258.62, `--headless=new`, running elevated. The browser was launched at 19:03:09 and the
`no_page` record written at 19:05:10: 121 s, two of the fixture's 60 s socket timeouts.

Findings:

1. `integrations.websocket` reports a socket **timeout** as `closed`: `TimeoutError` is an
   `OSError`, and `_take` maps every `OSError` to `closed`. So "every new socket to the tab was
   closed" may have been "every DevTools command to the tab went unanswered".
2. Reproduced locally (Edge 155, not elevated) by holding one idle TCP connection open to the
   single-threaded `http.server.HTTPServer` that `tests/test_browser.py` serves the site with, then
   navigating: `Page.navigate` got `frameStartedNavigating`/`frameStartedLoading` and no answer
   until the socket timeout; every re-attach then timed out under `Page.enable` (a tab with a
   pending navigation does not answer it); `/json/list` already showed the target at
   `/index.html`. That is the CI signature, including the 2 × timeout duration.
3. Not reproduced naturally: 30 runs of the three real-browser test files alone and 15 under
   full-suite load passed (attach max 3.2 s). Edge was seen opening speculative connections that
   send nothing (2 of 5 short probe sessions), which is what wedges a one-connection-at-a-time
   server; whether that happens on the runner is what the new traces will show. Elevation could
   not be tried: this machine's shell is not elevated and UAC was not bypassed.
4. Review of `websocket.py`: no extension or compression negotiated, so no compressed frames; no
   `Origin` header is sent, so `--remote-allow-origins` does not apply; client frames are masked;
   continuation frames and pings between fragments are handled; the 64 MiB limit is far above any
   `Page.enable` burst; `Sec-WebSocket-Accept` is checked; sockets to one target are independent.
   **One bug:** the pong for a server ping was sent unguarded, so a ping on a socket that could no
   longer send escaped as a bare `ConnectionAbortedError` (WinError 10053) that no caller catches.
   Minor, not changed: a new data frame during a fragmented message silently restarts it; the
   receive buffer is re-sliced per frame (quadratic only for very large messages).

Decisions:

1. Fix the pong: it is sent like every other frame and a failure is `WebSocketError("closed")`
   (test with a socket that cannot send).
2. Extend the opt-in diagnostics, same switch `AEP_BROWSER_DIAG_DIR`, no behaviour change unset:
   `SocketTrace` per DevTools socket (handshake status and headers, last 40 frames' direction,
   opcode, FIN and length, last 40 DevTools ids and method names, the server's close code and
   reason, and the first failure's phase, code, OS error class, errno and winerror or "end of
   stream"); `Browser.page` records every attach attempt (target id, outcome, elapsed) to
   `browser-<ns>-<pid>-sockets.jsonl` with the trace, sockets lost under navigate, evaluate,
   load waiting and screenshot are appended there, and `no_page`/`navigation_failed` records repeat
   the attempts and name the log. No payloads, titles or page content are recorded.
3. The socket lost under `Page.navigate` is closed explicitly before reattaching (it was left to
   the garbage collector).
4. `AEP_BROWSER_EXECUTABLE`, when set, is the browser to drive, used as given (a wrong path fails
   loudly at start). CI does not set it; switching CI to Chrome is the owner's decision.

Not done, proposed for the owner: serve the `tests/test_browser.py` site with
`ThreadingHTTPServer` (a test-harness fix that changes no assertion), and give a socket timeout its
own handling so one unanswered command does not consume the whole `page()` budget. Both wait for
the next red run's traces to confirm a timeout under a pending navigation.

Rejected: a new `timed_out` error code now (a contract change on a guess; the trace already tells
timeout from abort); switching CI to Chrome (owner's call).

## 2026-10-21 — An update refreshes a shipped manifest AEP wrote and nobody changed; a manager without its declaration is "outdated", not orphaned

Context (live check after updating to accumulated memory M1–M4): the installed
`engineering/business-cards@1.0.0` (written 10/20) had no `memory_spaces`, so the memory page
called `contacts/org` 「無主」, `notes__search` was not offered on business-card turns, and every
procedure fix made to that Skill since 10/20 had never reached the PC. `install-bundled`
(`update.ps1`) kept any file whose identity was already present ("kept"), and the business-cards
manifest had been changed in place at 1.0.0 some twenty times since 10/20 (other shipped Skills
changed in M1–M4 or the loan work were bumped, e.g. `coding` 1.7.0 → 1.8.0, or are new, the loan
Skill and Workflows; business-cards is the only shipped manifest with `memory_spaces`).

Decision:
1. `skill_packs.install` records the sha256 of every manifest file it writes in
   `workspace/bundled-assets.json` (`<kind>/<file name>`). On an update, an identity already
   present, on or off, is refreshed in place to the shipped content when the file is what AEP
   wrote (digest matches the record). It never moves, so a switched-off Skill stays off and a
   switched-on one stays on; nothing is switched on again; removed ones are still not brought back.
   The installer prints `Updated to this version's content, switched on or off as before: N` and
   `updated <kind> <ns>/<name>@<version>` per asset.
2. Left as they are: a file whose bytes differ from the record (changed on this PC: "changed on
   this PC since it was installed, so not updated"), and an identity this PC takes from the Shared
   Platform (`platform-selections.json` / `authorization.json` select it: published versions are
   immutable and a sync refuses another file under the same identity). Identities AEP does not
   ship are never touched.
3. A file installed before the record existed (every PC updated before today) is refreshed once,
   and its earlier bytes are kept in `workspace/replaced-assets/<UTC time>/skills|workflows/[disabled/]`
   so a hand edit, if there was one, can be recovered; the output names the copy.
4. `memory_spaces.manager_states` marks a Skill or Workflow that is installed but whose file
   declares no manager role (an older copy) `outdated`, not missing. The 資料 tab shows
   「Skill 已安裝但版本較舊：請更新 AEP，資料不必刪除」, and the M5 health check does not count it as
   an orphan.

Reason: a general fix, so any shipped manifest change (procedure, `memory_spaces`, selector hints)
reaches existing installs without a version bump; the switch state and the person's edits stay
theirs. A bump to 1.1.0 was checked and rejected for this case: the old 1.0.0 would be set aside in
`disabled/` (or the new one kept off when the person had switched 1.0.0 off), the
`business-cards/*@1.0.0` capabilities and their grants are separate identities and stay 1.0.0, the
memory registry's manager key is `<namespace>/<name>` (unchanged), the tools are offered for any
switched-on version, `CardStore` opens the space as `CARDS_SKILL` (would follow the constant), and
draft-card twin detection keys on the name with the newer version on — workable, yet it fixes only
this one Skill, leaves any later in-place change of another shipped manifest stuck, and every future
procedure fix would need another bump.

Rejected alternatives: bumping business-cards to 1.1.0 only (above); always overwriting shipped
identities (loses hand edits and breaks Shared Platform syncs); refreshing legacy files without a
backup (a hand edit before the record existed could not be told apart); a provenance field inside
the manifest (changes the bytes and digests of every published manifest).

## 2026-10-21 — A harvested signature of a stored person with nothing new is not a candidate

Context (live check, WNC first harvest): KevinRK Chen was already stored (same email); the
result carried `existing_person_id` and `would_change=[]`, yet he was listed as a candidate and the
answer said 「尚未存入通訊錄」. Only a re-read after an extractor change skipped such a match.

Decision: in `_Harvesting.harvest` any signature whose `CardStore.preview` matches a stored person
and changes no field is counted in `HarvestResult.already_stored` and listed in
`already_stored_people` (`StoredMatch`: person_id, name, company, email), never in `candidates`.
`scan_note` says 「N 位已在通訊錄、沒有新資料，不列為候選」 (the signature still counts in 「有簽名檔」),
the result's `note` tells the model to say they are already stored and never ask to store them, and
the business-cards procedure says the same. A stored person whose signature changes something is
still proposed with `existing_person_id` and `would_change`.

Rejected alternatives: leaving them as candidates with a flag (the model already ignored
`existing_person_id`); storing an observation for them silently (a harvest stores nothing without
the person's confirmation).

## 2026-10-21 — The memory page reads the installed manifests and sets up a memory database once (B3)

Context (live check B3): on the owner's PC `GET /api/memory/overview` took 17–18 s and every action
8–14 s (it reloads the overview). Profiled on a fixture of the owner's sizes (about 70 installed
Skill/Workflow files, 200 conversations, 9 people, a few preferences and notes; synthetic content):
1.66 s per overview on this PC, of which about 85 % was the memory registry being rebuilt five
times per call (every installed manifest parsed and validated each time, plus the shipped manifests
built again) and the Memory Service setting up the same database (schema script, every space's
registration, the owner row) on each of the dozen `MemoryService` objects a call made; the actor's
`memory.sqlite` was opened 46 times per overview. The owner's PC is about ten times slower on file
opens (company endpoint protection), which matches the 17 s.

Decision:
1. `host_runtime.memory_spaces` keeps each parsed installed manifest while its file's size and
   modification time are unchanged, builds the shipped manifests once per process, and keeps the
   registry built from one set of installed files (keyed by every file's path, size and
   modification time). A changed, added, removed or moved file (switching a Skill off) is seen on
   the next call; nothing needs a restart. `one_scan(layout)` lets one request look at the folders
   once.
2. `MemoryService` skips its setup when this process set up the same file with the same registry
   and actor and the file's identity (inode, size, modification time) is unchanged since. Any write
   from elsewhere or a replaced file runs the setup again, as before.
3. `MemoryService.session()`: inside it, everything one thread does on one database (through any
   service of the same path) shares one connection, one transaction at a time; a nested `connect()`
   during a transaction still opens its own. The memory page wraps each GET and POST in it, so one
   overview opens the actor's database once. The overview builds every store on one service and
   reads the conversations once.
4. `GET /api/memory/overview?only=a,b` answers only the named sections; the page reloads only what
   an action changed and shows 「載入中…」/「更新中…」 per pane, 「…」 counts until the first answer
   and an inline error with 重試.

Result on the fixture: overview 1.66 s → 0.12–0.14 s; single sections 8–110 ms; the M3
preference and note lists about 0.25 s → 13–15 ms; one overview opens `memory.sqlite` once and
reads no manifest twice (tests count it).

Rejected alternatives: a time-based cache (a just-installed or switched-off Skill would show late);
caching `MemoryService` objects per actor (would hide changes made by the Bridge or another
process); keeping one connection per actor for the whole process (a long-lived connection across
threads and requests, and the nightly check works from another thread); moving the conversations'
`preferences_used` into an index table (the parse is about 0.1 s here; not the cause).

## 2026-10-21 — Pending changes leave out draft install cards; undoing a health fix reopens its finding at once (#233)

Context: two follow-ups from the 2026-10-21 live checks (#233) had more than one reasonable fix.
`GET /api/cards` said "every card still waiting" but never listed draft install cards (`dr-`).
After 復原 under a health card's fix, the change was reverted but the finding stayed `resolved`
until the next check, although §16 of `docs/phases/ACCUMULATED_MEMORY.md` says a fix that is
undone reopens it.

Decision:
1. `GET /api/cards` keeps leaving out `dr-` cards; its docstring and `docs/CONTRACTS.md` now say
   so. A draft's card is answered on the answer that drafted it (Install opens the Workflow's run
   form there), a draft not installed already waits in Capabilities > Drafts, the agent-mode poll
   draws only `pm-`/`ml-` cards, and Telegram never reads this list (it draws a draft's card with
   its own answer).
2. 復原 under a finding's fix goes through `POST /api/memory/health/undo` {`finding_id`, `kind`,
   `change_id`}: the store's own undo (contacts or preference), then the `resolved` finding is
   `open` again in the same request. A refused undo leaves it closed.

Rejected alternatives: listing `dr-` cards under Tasks > Pending changes (the draft would show
twice, and Install there would not open the run form); reopening the finding only at the next
check (the card is missing in between, the reported problem); reopening it from the generic
`/api/memory/undo` and `/api/memory/proposals/undo` with an optional `finding_id` (two routes to
change for one page action, and a finding id on routes that are not about findings).

## 2026-10-21 — BI Knowledge Case A is approved and built on `bi.schema/v1.1` with the robotics sample as demo data

Context: Knowledge Strategy v1.3 §7 kept AEP-K02 and later waiting for owner approval. The owner
wants a Case A demo for his boss today (release before ~15:30). During the work he changed the
demo data: his boss's target sample is the robotics BI knowledge base (`files/robotics_kb_sample/`,
schema v4 of the owner's BI tools, 12 types, 104 cards), not the small wireless fixture.

Decision (owner, 2026-10-21):
1. **Scope approved: Case A only** (v1.3 §4.7: CSV → mapping preview with warnings → per-card
   diff → confirm → write → query → dataset-scoped gap answer). The §7 gate is lifted for this
   scope only. The data is example data only (no real customer data).
2. **Schema `bi.schema/v1.1`**, derived from the robotics sample's schema v4
   (`tests/fixtures/robotics_kb_sample/tools/bi_schema.py`, committed verbatim as a fixture) by
   the one-off converter `scripts/build_bi_schema_v1_1.py` (reads with `ast`, never imports or
   runs it). The generated `src/capabilities/bi_cards/bi_schema_v1_1.json` ships inside the
   package; a test checks it equals the converter's output and covers every v4 type and field.
   It keeps v1's `id_rules` and `field_classes`, and ADR-K11's judgement list. v4 additions:
   `domain` (list on the shared and company types, one value on the others; wireless / AIDC /
   robotics), `nodes` on Account, Ecosystem, Competitor and CustomerProduct (`node` merged into
   `nodes`), CustomerProduct `ecosystem` and `launch_date`, Opportunity with `deal_stage`,
   `test_type` EMC, Ecosystem `role` institute and ipc, Chinese column aliases. Link targets
   (untyped in v4) follow v1's relationship ranges plus `ecosystem` → Ecosystem or Account. The
   proposal file `docs/proposals/bi_schema_v1/bi_schema_v1.json` is unchanged; it is not shipped.
3. **Priority (#222 kept):** Application `priority` is not in the registry; an imported 優先度
   column is shown as ignored with 「優先度由 Skill 依事實判斷，不存資料」 and each row with a value
   gets a `priority_ignored` warning. Trend `measurement_impact`, `our_fit` and `market_impact` are
   facts (`sourced`), stored. Trend priority is computed (measurement_impact × our_fit) for the
   dashboard and never stored. v1's `priorities` (per market and period) is therefore not used.
4. **Store:** one SQLite per dataset at `<workspace>/bi/<dataset>/bi.sqlite` (default `demo`),
   cards keyed by `(entity_type, canonical_key)`, field-level provenance and append-only history
   inside `capabilities.bi_cards` (ADR-K11 behaviour: human values never overwritten, imports
   become proposals, `base_version` stale-edit check, whole-import undo). Every demo card is
   synthetic and `confidence: assumed`; a card is trusted only when a person verified it and it
   is not synthetic (DQ-1).
5. **Demo:** the 12 robotics CSVs are copied into the package (`capabilities/bi_cards/demo/`,
   package data) and loaded in link order. The older 3-sample wireless fixture is not part of the
   demo (dropped to keep the demo to one dataset; its CSVs still import through the preview).
6. **Chat:** Bridge capability `bi-cards/query@1.0.0` (read only) and Skill
   `engineering/bi-knowledge@1.0.0`, shipped switched on like business cards.

Deferred: v1.3's PostgreSQL backend and the Knowledge storage interface (ADR-K2), the Strategy
Config reference and Schema Registry install/upcast (ADR-K10 steps 1–4), Graph candidates and
the push gate (AEP-K05–K08), conflict records for two sources disagreeing (DQ-7), the vault
adapter and snapshot import (DQ-2, DQ-6), mapping `explode` / `derive` / `compose` (Case B),
Concept candidates (Case C), proposal accept/reject routes, Cases B–E, real customer data.

Why: the demo needs working software today; the store is local, per dataset and internal
(#214: BI data is INTERNAL, internal model routing is fine, access follows database sharing).
Building inside one capability package keeps the Harness and storage type-agnostic (ADR-K10)
and lets the later Knowledge storage backend replace the SQLite file without changing the API.

Rejected alternatives: shipping `bi.schema/v1` (it lacks the robotics fields and types, so 9 of
12 robotics CSVs would have unknown columns); importing the owner's `bi_ingest.py` (v1.3: the
tools are a specification source, not code we run); storing Trend priority (owner: computed);
keeping both demo sets (two datasets for one demo and more to test today).

## 2026-10-21 — The chat composer chooses the Gateway model per conversation, from the next message, without a restart

Context: the owner asked to move the backend selector ("Configured LLM Gateway" / "Configured
and ready") to the top of the chat and put an LLM model menu where it was. Before this, the
conversation model was fixed per host: Settings → Natural-language model saves one endpoint and
model in `host.json`, applied at the next Agent start. The built-in LiteLLM Gateway serves several
models at one URL, and the data approval (`ModelBinding.data_approval`) names that URL, not a
model id; Settings already keeps the approval when only the model name changes.

Decision (owner request, scope as recommended in the request):
1. **Scope**: per conversation, remembered as the person's default for conversations that have
   not picked one, applied from the next message without restarting the Agent. Stored in
   `<workspace>/conversation-models.json`, not in the conversation record, so a rollback to an
   older build still reads its conversations.
2. **Which models**: only what the configured, approved Gateway lists at `/models` (read by the
   Host with its credential mapping), plus the configured model. Unreachable list: the configured
   model alone.
3. **How it is applied**: a per-turn context variable (`models.selection.TURN_MODEL`) read by a
   `SelectableModelClient` placed *inside* `ApprovedModelClient` on the router: data policy first,
   then the same endpoint with a different model id; anything not approved is refused with
   `model_not_approved` and never sent. `ModelRequest` and the alias layer are unchanged; callers
   still name the alias.
4. **Reach**: Gateway-backend conversation turns (the router's model). Knowledge answers made by
   capabilities through the drafting client, Workflow drafting, schedules and Telegram keep the
   configured model. Settings still defines the Gateway, its URL and the default model.

Why: the approval is tied to the URL and data classes, so a model at the same Gateway needs no
new approval; a context variable keeps the choice to the one turn (asyncio.to_thread copies it)
without threading a model id through every caller; data classification (BI is INTERNAL) is
untouched because the destination and the policy check are the same.

Rejected alternatives: saving the pick into `host.json` and restarting (the owner wants it per
conversation and immediate); a `model` field on `ModelRequest` (changes a shared contract and
every caller); a field on `ConversationRecord` (breaks reading conversations after a rollback);
letting the page send any model id (the Gateway's list is the policy); switching the drafting
client too (wider reach than the chat menu suggests; can follow if the owner wants it).

## 2026-10-21 — The Windows installer always writes the engineering namespace; -Namespace is accepted and ignored

Context: commit 4b051234 (same day) gave a fresh install `"namespace": "engineering"` only when
neither `-Namespace` nor an existing `host.json` set one, and the manual documented `-Namespace`
for colleagues whose chats answered "No namespace is configured". The owner then decided
(2026-10-21): 「不應該讓使用者安裝的時候選 namespace……直接設定 namespace 就好」.

Decision:
1. `deploy/windows-preview/install.ps1` puts `namespace = "engineering"` in the configuration it
   owns (`$Config`, beside the device identity and the workspace path), so it is written on every
   install and update; an existing `host.json` with another value is corrected and the installer
   prints `Changed the namespace in host.json from '<old>' to engineering`.
2. `-Namespace` stays as a plain `[string]` parameter (no validation) so commands already sent to
   colleagues (`install.cmd -Actor x -Namespace engineering`) keep working; another value prints
   one line, `The namespace is fixed to engineering; -Namespace <value> was ignored.`
3. `update.ps1` has no `-Namespace` and passes none; it gets the rule through `install.ps1`.
4. The manual marks `-Namespace` 「已不需要」.

Why: colleagues do not know what a namespace is, and a wrong or missing one breaks every chat;
there is one team namespace today. Writing it in `$Config` (not as a default after the merge) is
what makes an update repair a host that already has a wrong one.

Rejected alternatives: keeping the default-when-missing rule of 4b051234 (leaves a wrong value in
place); removing `-Namespace` (breaks the commands already sent: PowerShell rejects an unknown
parameter); making the namespace a bundle manifest setting (no second namespace exists yet; can be
done when one does).

## 2026-10-21 — Knowledge storage stays on SQLite; no central PostgreSQL (ADR-K2, #212)

- **Decision (owner, 2026-10-21):** 「好換成sqlite而且他的可攜性比較好」. AEP keeps SQLite for knowledge
  storage (BI cards, memory, the Shared Platform registry). The central PostgreSQL in ADR-K2 option C
  is not introduced; this replaces the owner's earlier 2026-10-21 agreement in #212 to adopt it,
  which had stalled on where to host it.
- **Why:** SQLite is portable (one file per dataset, no server, works offline, local-first per
  AGENTS.md), and covers what is needed now: one maintainer per dataset, read-only sharing through
  Shared Platform snapshots (`docs/proposals/BI_DATASET_SHARING.md` option A), the dashboard and chat
  queries. PostgreSQL would add an operated component and a hosting decision with no near-term gain.
- **Kept:** every storage stays behind the type-agnostic backend interface and its contract tests
  (ADR-K2, ADR-K10), so a PostgreSQL (or other) backend can be added later without changing callers.
  SQLite files are never shared through OneDrive or network drives (corruption risk); sharing goes
  through snapshots.
- **Revisit when:** several people must edit the same dataset live, row-level access by data
  classification is required, or data volume or query load outgrows SQLite.
- **Rejected:** PostgreSQL on host 141 (LAN only, one more service to run); a cloud PostgreSQL (no
  server available).

## 2026-10-21 — BI cards: each dataset is bound to one schema; Dashboard and chat stay BI-only

- **Decision (owner, 2026-10-21):** 「只讓資料集換 schema」. A BI-cards dataset is created with a name
  and one schema id@version, kept in its `bi.sqlite` (`meta.schema`) and never changed. Import,
  the card list, card detail, field edits and history follow the dataset's schema. The Dashboard,
  the demo load and the chat's `bi__query` stay BI-only: they work for `bi.schema/*` datasets; any
  other dataset gets the 「這個 schema 沒有 Dashboard」 empty state, and `bi__query` refuses it with
  `schema_not_bi`.
- **Schema sources:** the shipped `bi.schema/v1.1` plus files a person installs under
  `<workspace>/bi/schemas/<schema_id>@<version>.json`, in the shipped registry's JSON format,
  validated strictly (every error names its place) and immutable per id@version (identical
  content is a no-op; different content is refused). The `bi.schema/` prefix is reserved for
  shipped schemas, so "BI" always means the tested types the Dashboard and the Skill are written
  for. One non-BI example (「產品規格」, `example/product-spec@1.0.0`, four linked types) ships as a
  sample and is not installed by default.
- **Legacy:** a dataset written before this has no binding and is read as
  `bi.schema/v1.1@1.1.0`; its next write records that. A dataset first written by an import or
  the demo load, without being created, is bound the same way, so existing flows are unchanged.
- **Why:** colleagues want to keep other structured data (product specs, suppliers) as cards
  with sources and history, without waiting for a Dashboard and a Skill per schema. Binding at
  creation keeps every stored card consistent with one schema; immutability means a binding
  always resolves to the same types.
- **Rejected / deferred:** a full "schema pack" (a declarative Dashboard and a per-pack chat Skill)
  — considered and deferred; changing a dataset's schema in place (would need a migration of
  every card); allowing installed schemas under `bi.schema/` (the Dashboard and the Skill assume
  its types); comparing installs byte for byte (re-saving the same file with other formatting
  would be refused for no reason).

## 2026-10-22 — BI dataset sharing: owner answers to the five questions

- Proposal `docs/proposals/BI_DATASET_SHARING.md` (option A: immutable dataset snapshots as a Shared
  Platform asset kind, read-only subscribed copies). Owner answers (2026-10-22), recorded in §8.5:
  Q1 real INTERNAL BI data may be published to host 141; Q2 when access is revoked the colleague's
  copy is **kept and stops updating** (not deleted); Q3 snapshots carry provenance and history
  without pending proposals, file names only, platform accounts as names; Q4 readers default to the
  owner's team, organization-wide needs an explicit confirmation, never public; Q5 only the first
  version of a new name needs admin review.
- Q1 and Q2 differ from the proposal's defaults; they are the owner's choice.

## 2026-10-22 — Everything done inside a session uses that session's model

- **Decision (owner, 2026-10-22):** 「現在先根據處在那個session 就用那個模型」. Whichever session a
  request belongs to uses that session's selected model. This widens item 4 ("Reach") of the
  2026-10-21 composer decision, which kept the drafting client on the configured model.
- **Follows the session** (the session entry point enters `models.selection.session_model` once
  per turn; every client of the turn reads `TURN_MODEL`):
  - Agent Web Gateway-backend turns (`AgentWeb.conversation_turn`): the conversation, the
    Knowledge Harness answer on the direct route and the tool route, Workflow drafting
    (`workflow_author.draft`), business-card reading, the coding change capability and the
    Knowledge pipeline capability when called in the turn, conversational Workflow/Skill drafting
    (the conversation model writes the draft), memory proposals and preference checks (made by
    the conversation model's tools).
  - Telegram turns (`TelegramIngress._deliver_guarded`): the chat is the session
    `telegram-chat-<chat id>`; its own choice, else the person's default, else the Settings
    model. `/model` lists and chooses, consistent with the composer menu (a choice is also the
    person's default).
- **How:** the host builds **one** `SelectableModelClient` for the routing alias and shares it
  between the router and every drafting client (`build_gateway` passes it to `build_router`);
  each is still wrapped by `ApprovedModelClient`, so the data approval decides first and a model
  the approved Gateway does not serve is refused (`model_not_approved`) with nothing sent. Data
  classification and routing are unchanged. `asyncio.run`, `asyncio.to_thread` and new tasks copy
  the context; no session-turn path hands a model call to a plain thread or executor today.
- **Keeps the Settings model, explicitly** (`models.selection.settings_model`): schedule ticks
  and approved scheduled runs (`ScheduleControl.tick` / `approve`), the nightly job
  (`AgentWeb.nightly_tick`), the experience review, and the Knowledge page's own jobs (ask,
  benchmark, convert, re-ingest, Skill assistant), which run in their own threads with no
  session. CLI-backend sessions (Claude Code, Copilot, Codex) use their backend's model; what
  AEP itself asks a model for during them uses the Settings model. The JEV Skill-selection
  accelerator is a separate configured endpoint and is not switched.
- **Visible:** each answer records `ConversationMessage.model`, the model id its requests were
  sent to (None when no model was asked), shown under the answer as 「模型：<id>」, so the owner
  can check which model answered.
- **Rejected alternatives:** a separate switch per client with its own approved list (two places
  to keep in sync); passing a model id through capability inputs (changes shared contracts);
  making schedules follow the person's default (a schedule has no session and should not change
  when someone picks a model in a chat).

## 2026-10-22 — BI dataset sharing slice 1 scope trimmed

- Owner (2026-10-22): 8–10 days is too long; agreed to a trimmed slice 1 built by three agents in
  parallel, then a 141 deployment and a two-PC live test. Pinning, rollback and the Marketplace /
  Overview listing move to slice 2. Scope in `docs/proposals/BI_DATASET_SHARING.md` §8.6.

## 2026-10-22 — BI dataset snapshots: format, size limit and platform rules (sharing slice 1)

- **Snapshot** `aep-bi-dataset-snapshot/1`: gzip (mtime 0) of canonical JSON (sorted keys,
  compact). The content digest covers everything except `digest` and `publication`, so the owner's
  build is deterministic and the platform's publication stamp (version, publisher, time, note)
  does not change it; the package SHA-256 is of the stamped bytes. Proposals are never read;
  folders are cut from refs and import file names; actors map to platform accounts through an
  optional mapping and are kept as they are otherwise (on a PC whose Agent actor is the platform
  account nothing changes). A credential-like string (`common.assets.SECRET_PATTERN` /
  `SECRET_FIELD`) fails build and publish, naming card and field only.
- **Size limit**: 20 MiB gzip per snapshot (configurable on the platform as
  `max_bi_dataset_bytes`, 1–64 MiB), 256 MiB decompressed, 50 000 cards. The proposal suggested
  8 MiB; 20 MiB was chosen in the slice 1 brief so a real INTERNAL dataset (owner Q1) fits with
  room, while the sync reply that embeds the artifact stays a single bounded response. The
  publish route has its own body limit (limit × 4/3 + 64 KiB); every other Member Portal route
  keeps 256 KiB.
- **Platform**: new `AssetKind`/`RunnableKind` `bi_dataset`; versions minor + 1 (major + 1 when
  the schema's major changes); `base_version` must equal the highest published version
  (`version_superseded`); the first version of a new name reuses the review queue as an
  `AssetSubmission` of kind `bi_dataset` (owner Q5); readers `team` by default, `organization`
  only with `confirm_organization`, `public` refused also by `assets/access/update` (Q4).
- **Revocation** (Q2): a `bi_dataset` selection whose member is no longer entitled is not planned
  by sync (audited once as `sync_refused`); the Agent learns it from `bi-datasets/status`
  (`entitled: false`) and keeps its copy. Other kinds keep the earlier rule (selections stand).
- **Audit**: a dedicated append-only `bi_dataset_audit` table in the registry SQLite file
  (memory when not durable): submitted, approved, rejected, withdrawn, published, selected,
  replaced, revoked, synced (with the Bridge), sync_refused, downloaded.
- **ADR-K10 exception**: `control_plane/bi_datasets.py` is the one module outside the BI package
  and the Host's BI wiring that imports `capabilities.bi_cards` (the snapshot reader), because the
  platform must validate every snapshot itself; the guard test lists it.
- **Rejected alternatives**: storing the raw `bi.sqlite` (carries proposals, paths and SQLite
  internals, cannot be scanned per value); a new field in `SyncReply` for the revoked signal
  (closed contracts: an older Agent would refuse every reply); letting the platform rewrite the
  content digest on stamping (the owner could no longer tell the published content is theirs);
  widening the generic `assets/submit` route to data (its 192 KiB manifest rules and per-version
  review do not fit).

## 2026-10-24 — Fixes from the BI dataset sharing slice 1 live test

Owner (2026-10-24): fix all five bugs of the live test. Three of them needed a design decision.

- **Platform credentials per install (bug 1).** Two Agent installs of one Windows user saved the
  Bridge token under the fixed `AEP_SHARED_PLATFORM_TOKEN`, so enrolling one replaced the other's
  token. Decision: the Agent always saves and reads the variable host.json maps the secret to
  (`shared_platform_token`; the Personal Agent code `platform_member_login` already worked that
  way), and `deploy/windows-preview/install.ps1` writes per-install mappings for an install
  outside the default folder: `<legacy name>_<first 8 hex digits of SHA-256 of the lower-cased
  full install path, upper case>`, e.g. `AEP_SHARED_PLATFORM_TOKEN_1A2B3C4D`. The default
  install (`%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0`) gets no mapping from the
  installer and keeps the legacy names; a mapping host.json already has is never changed, so the
  owner's install and its saved values are untouched (migration-free). `update.ps1` runs the same
  installer, so an existing non-default install gets its mapping on its next update; one that was
  already enrolled with the legacy mapping keeps it (re-enrol after removing that mapping by hand
  if two installs already collided). Rejected: deriving names in the Agent from the workspace path
  (every hand-made or test workspace would change names and the "default" would be guessed at run
  time); suffixing by the device bridge id (two installs of one PC usually share it); a marker
  claiming the legacy name in the user environment (writes to the owner's environment).
- **The Host appends a subscribed dataset's source line (bug 2).** In 2 of 9 live answers the
  model left out 「資料來源：<ns>/<name> v<ver>（發佈者 …）」 although `bi__query` returned it.
  After an answered turn, Agent Web and Telegram append the tool result's own line
  (`host_runtime.bi_cards_tools.with_bi_sources`, the same post-answer pattern as an org chart's
  legend) once per dataset and version, unless one line of the answer already names that dataset
  and version; own datasets add nothing. This is the Host adding a factual citation copied from a
  tool result, not a rewrite of the model's claims, so the Harness rules G1–G4 are unchanged.
  Rejected: a stronger procedure instruction alone (already present, still missed); a Harness
  verification that refuses or retries the turn (costs a model round for a fact the Host has).
- **Saving a field with its current value is no change (bug 3, owner decision).** No version
  bump, no history entry, nothing different in a snapshot; the route answers `unchanged: true`
  and the page says 「沒有變更」. Values are compared as normalised stored JSON, as an import
  compares (enum case and aliases, a domain list's canonical spelling, list whitespace).
  Rejected: recording a no-op edit for audit (it would bump the version and change what is
  published without a change in content).

## 2026-10-25 — Telegram delivery, reply context, failed-turn history and the claim-check wording

Owner report (live, Telegram): 09:34 「幫我執行 43W SDE weekly report」 got 「The answer could not be
delivered here (Telegram refused the message)」 although the answer was short; at 10:26 a Reply on
it with 「再跑一次」 got "what should I re-run?" plus an English Host note saying a completed action
had been claimed, for an answer that only said 「如果是已安裝 Workflow，我會開它的執行表單」.

- **What the code and the records support for 09:34.** Not length and not an empty reply.
  `TelegramDelivery.reply` is `Text` (at least one non-space character) and `TelegramPollResult`
  validates its deliveries again, so a blank reply can never reach `_reply`; it fails as
  「That request could not be handled on this Bridge.」 instead. The message matched `run_intent`
  for `engineering/sde-weekly-report`, so the reply was that Workflow's first question (about 200
  plain characters, Yes/No buttons): the Host's telemetry has no conversation turn and no run at
  09:34, only the 10:26 turn, and Agent Web had been running since 2026-10-24 10:45 (no restart). A
  keyboard Telegram refuses was already retried without it, so a 400 is unlikely. What the code
  leaves is a 429 outlasting the single retry after at most 5 s, or a call that raised (a timeout or a
  reset connection on the way to Telegram); neither was logged, so which one is unconfirmed until the
  new warning line shows it live.
- **An answer waits out a rate limit and survives one transport fault**: up to 60 s per wait, up
  to 4 attempts; a call that raised is tried once more after 1 s (a timeout after delivery may show
  the piece twice, which beats losing it). A 429 never falls back to a file (the file would be
  rate-limited too). Rejected: keeping the 5 s cap (loses the answer); unbounded waits (one poll
  batch could stall for minutes).
- **A text with nothing to show sends a completion notice, never `UNDELIVERED_REPLY`**:
  「<workflow> 已完成」 above the files when there are files, 「已完成（沒有文字結果）」 (with the
  Workflow's name when one ran) otherwise. This is a second line behind the contract above.
  `UNDELIVERED_REPLY` now means Telegram refused (or never answered) a real answer and its file.
- **An edit Telegram answers with "message is not modified" counts as delivered** (the message
  already shows that text and keyboard); any other refused edit still sends a new message.
  Rejected: falling back to a new message for it too (a duplicate of what is already on screen).
- **Pieces are cut by Telegram's own measure.** Telegram's 4096 limit counts UTF-16 code units, so
  an emoji is two; `channels.telegram.chunks` now cuts at 4000 units (was 4000 code points),
  prefers a newline as before and never splits a surrogate pair. Status messages and the
  multi-select edit use the same measure; the Codex control channel truncates by it too.
- **A piece Telegram still refuses (400) after the rate-limit and keyboard retries sends the whole
  answer as `answer-<time>.md`** through `sendDocument`, followed by 「回答太長或格式無法顯示，已改用檔案傳送」
  (with the keyboard, if any); the temporary file is removed. `UNDELIVERED_REPLY` is sent only when
  the file fails too. Rejected: re-splitting smaller and retrying (a 400 may not be about length, and
  the earlier pieces have already gone); sending only the refused piece as a file (a fragment).
- **Every refused or failed Bot API call is logged at warning** (`channels.telegram` logger; no
  handler is configured, so Python writes it to stderr, which the launcher keeps in
  `workspace\logs\agent-web-*.err.log`): method, HTTP status, Telegram's `description` (redacted,
  200 characters), piece position and UTF-16 length, or the redacted transport error. Never the text,
  the chat content or the token.
- **A Telegram Reply carries what it replies to.** `_parse` keeps `reply_to_message`: its text, else
  its caption, else 「（附件）」, redacted and trimmed to 1000 characters, for the person's own messages
  and the bot's answers alike. The conversation turn reads 「（回覆先前的訊息：「…」）\n<words>」 and the
  history keeps it; the routed request (`LocalAgentRequest.message`) and `run_intent` see only the
  person's words. Rejected: matching `run_intent` on the quote too (a quoted Workflow name would
  open its questions without the person naming it).
- **Failed turns and Workflow flows stay in the chat history.** It kept a turn only when the model
  answered or a guard stopped it. A failed or refused turn now keeps the request with
  「（上一輪沒有完成：<code>）」; a run request answered by a Workflow's own questions keeps the request
  with 「（交給 Workflow <namespace>/<name> 的執行問題）」 and the first question, and a finished run keeps
  「【執行】<name>」 with its result line. The history is still in memory only (`MAX_CHAT_HISTORY` = 12
  messages per chat and sender) and is lost when Agent Web restarts. Persisting it would be cheap (the
  Bridge's `state.sqlite` already has a `conversations` table keyed by session) but not free of risk:
  it would keep what people typed on disk with no retention rule yet, so it is not built here.
- **The completed-action claim check reads conditions and offers.** 「已」 as an adjective
  (「已安裝的」, 「已完成的」) is not a claim, and a match does not count after a condition, offer or
  promise earlier in its sentence (如果, 若, 要是, 的話, 我可以, 我會, 是否; if, unless, once, can,
  will, shall, should, would). Real claims are still caught, now also 「已完成」, 「已經幫你…」 and "I
  have done / completed / finished". Rejected: dropping 安裝 from the verbs (「我已安裝」 is a real
  claim); clause-level scope (a comma would excuse 「如果需要，我已經寄出」 less predictably).
- **The person reads a short Traditional Chinese note per failed check**, e.g.
  「（系統檢查：這一輪沒有成功執行任何工具，回答中『已完成』的說法未經驗證）」 (also for a lasting-change
  claim, missing files and the reuse check). Agent Web and Telegram both show the Gateway's answer, so
  the text is the same in both. The English reasons go to the model's retry and to a warning line
  (`agent.conversation_harness`); telemetry still records which check failed. Rejected: keeping the
  English reason in the answer (the owner read it as noise).

## 2026-10-25 — Design principles: never re-ask given values; never interrupt mid-interaction

- **Decision (owner, 2026-10-25):** 「這個部分應該要寫到設計原則裡面吧不然每次又遇到一樣問題」. Added
  `AGENTS.md` rules 18 and 19 and `docs/PRODUCT_VISION.md` principle 10.
- **Why:** live, 「幫我執行 43W SDE weekly report」 in Telegram asked for the report week again, asked
  optional inputs one by one, moved on before a Yes/No was answered, and an Agent Web restart for an
  update dropped the owner's open question flow because the restart check looked only at tasks.
- **Rules:** prefill and validate given values (message, replied-to message, model run arguments); optional
  inputs take defaults; ask only required missing values, one at a time; one confirmation card with
  every value and its origin, editable in plain words; nothing consumed without input. Maintenance
  restarts check running tasks, in-progress turns and open flows or forms on every channel, and wait
  or ask.

## 2026-10-25 — Fewer questions in a Workflow run; the activity read before a restart

Implements `AGENTS.md` rules 18 and 19 for Workflow runs (owner, Telegram, 2026-10-25:
「不是已經講了為什麼要再回一次」, 「有輸入過的參數能不能自己填啊？」).

- **Values in the request are read deterministically, from the Workflow's declaration**
  (`common/run_prefill.py`, through `workflow_run_form.prefill_from_text`, so Agent Web's run form and
  Telegram's flow read the same values): a week (`43W`, `W43`, `第43週`, `2026_43W`) for the one text
  field about a week whose label, description, help or examples show the format (`2026_40W`), in that
  format, the ISO year of today when omitted; an explicit date for the only date field, or a from/to
  range (`… 到 …`, `to`, `~`) for exactly two; a declared choice named once in one select; a dry-run
  phrase (dry run, 只看計畫, 試跑 / 正式, 寫入) for the one dry-run switch, never when both or a negation
  appear. Anything else is left for the form. Values go through `person_prefill` (the field rules and
  the embedded-secret check), so an invalid one is dropped and asked; credentials are never parameters
  (`SECRET_FIELD`). Rejected: a new model call to fill inputs. The model path already exists
  (`workflows__run_form` with `agent_prefill`) and both channels use it the same way; a second model
  call on every run request would add latency and a non-deterministic step to a rule that covers the
  reported cases.
- **Telegram asks only missing required inputs, then one card.** Given values, last time's identity
  values and declared defaults are never asked; optional inputs are not asked one by one. The card
  lists every value with 「（從你的訊息）」, 「（預設）」 or 「（上次的值）」 and 「未填（不使用）」, with
  **確認執行** and **修改**; 修改 shows one button per input, and plain text such as 「Dry run 改成否」,
  「From date 2026-10-19」 or `week=2026_44W` (label, label head or name, then the value; a switch's name
  alone flips it) changes a value and shows the card again, checked like a typed answer. Every run now
  shows the card, except a read-only Workflow with no inputs. The separate 「Same as last time?」 question
  is gone; its values are on the card. Rejected: a `/skip` per optional input (the reported problem); a
  cancel button on the card (`/cancel` and 「取消」 still cancel; the owner asked for two buttons).
- **A button counts only on the question it was sent with.** The ingress keeps the message id Telegram
  gave the current question (`FlowState.prompt_message_id`) and refuses a tap on any other message
  with 「這個按鈕屬於較早的問題，沒有採用。」 and the current question. Live cause, 12:51: after the
  restart a new flow was at 1/9 (Dry run) and 3/9 followed at once, then 「From date must be a
  YYYY-MM-DD date」 with no answer; the logs are empty, and the most likely inputs are a tap on the old
  flow's Yes button and the owner's next message, both taken as answers to whatever the new flow
  asked. Rejected: a flow token in the callback data (every button's data and its 64-byte limit change).
- **A Reply on a flow question.** On another question of the same open flow it sets that input; on a
  question whose flow is gone (restart, time limit) the flow starts again with that value given and says
  「那個流程已經結束，已用你的值重新開始。」. A tap under a gone flow's message says 「那個流程已經結束。…」
  and is never sent to the model as text. A question is recognised by its first lines
  (`<name> (2/9)` or `<name> (修改)`, then the label).
- **`GET /api/activity` and `launcher.restart_blockers`.** Running background tasks, chat turns in
  progress, open Telegram flows and Telegram updates being handled, with `busy`. No message content; a
  Telegram chat is a 12-character hash salted per process. `restart_blockers` reports an Agent Web that
  does not answer the route (or predates it) as unknown, never as idle. Agent Web's run form keeps no
  server state (an open form survives a restart as long as the page does), so it is not listed.
- **Flow state is not persisted.** A flow holds the manifest, a live choice provider and upload paths;
  storing it would need a store, a schema and an expiry for little gain now that a run asks only missing
  required inputs, a restart is refused while a flow is open, and a Reply on a lost question restarts it
  with the value.

## 2026-10-25 — A yes/no input says what each choice does

Owner, Telegram, 2026-10-25: the question 「Dry run: show the plan only … Default: False」 with buttons
**Yes / No** — 「這個yes, 和No讓人很confused, 是要dry run 還是不要呀」 — and a card line 「Dry run：否」.

- **Decision:** a boolean input is presented by what each choice does, everywhere (Telegram buttons,
  card lines, the Agent Web run form, the Agent tool schema). The Workflow declares the two choices in
  optional `true_label` / `false_label` (boolean only, additive, omitted while unset so older manifest
  digests do not change); without them the choices are the label and 「不要：<label>」. Typed answers and
  edits accept the choice words as well as 是／否／yes／no (「只看計畫」, 「改成正式執行」). Agent Web shows
  two labelled radio options instead of a checkbox. Added to `AGENTS.md` rule 18.
- Every bundled boolean declares its two choices; the dry-run switches are relabelled 「執行方式」 (English
  Workflows: "Run mode" where the label described one choice), and the weekly report reads 「只看計畫（不寫入、
  不寄信）」 / 「正式執行（寫入週報、起草郵件）」.
- **Rejected:** a generic 「是／否」 pair (the same ambiguity as Yes/No: it depends on how the question is
  phrased); turning booleans into `select` fields with two values (changes the run argument type from
  a JSON boolean to text for every existing Workflow and schedule); a separate `card_label` field (the
  label already is what the card and the form show, so relabelling the switch is enough); changing the
  button callback data (old buttons and the stale-tap check keep working with `yes` / `no`).

## 2026-10-25 — A session remembers what it produced

Owner, Telegram, 2026-10-25: the SDE weekly report ran at about 15:15 (Outlook draft and
`workspace\weekly-mail\2026_43W\effort-chart.png`); at 16:57 in the same chat 「那你可以把統計圖片貼在這個
session 嗎」 got "I have no image file, give me a path" — 「這個workflow 做完之後他都忘記了…這個記憶也太短了吧」.

- **Cause:** after a run from the Telegram question flow, the chat history (memory only,
  `MAX_CHAT_HISTORY` = 12 messages) got one pair: 「【執行】sde-weekly-report」 and
  「sde-weekly-report run <id>: succeeded, 3 step(s)」. No output was named (the mail step's
  `chart_path` stayed in the run record), each later turn adds two messages, so six turns pushed even
  that line out, and the Gateway trims to its own 12. No tool could attach an existing file, and the
  flow never sent the chart (only the org chart tool's files were sent as photos). Agent Web's form
  run kept the readable answer only, likewise without outputs, in a 12-message recent window.
- **Decision:** a per-session, per-actor ledger (`src/host_runtime/session_artifacts.py`,
  `<workspace>/session-artifacts/<hash>.json`) keeps each run (workflow, run id, status, one-line
  summary) and what it made: files under known output fields (`chart_path`, `png_path`, `html_path`,
  `output_path`, `attach` / `files` lists) that lie in the workspace, and mail drafts (Outlook
  `entry_id` + subject, not attachable), each with a short id `f<n>`, a kind and a file name. Files a
  host tool made for an answer (org chart) are recorded too. The history gets a compact
  「【執行結果】…」 entry with that list (Telegram history; Agent Web's stored run answer or the
  turn's tool record).
- **Surviving the window:** the Gateway appends the ledger's last 8 runs and up to 24 files to each
  turn's system prompt (`Gateway.session_context`, capped at 4,000 characters), instead of pinning
  messages or raising `MAX_CHAT_HISTORY`. One place serves both channels and every trimming step
  (Telegram's 12, Agent Web's recent window, the Gateway's own 12), the list is small and
  content-free, and the conversation window keeps its size and budget.
- **Attaching:** host tool `session__attach_file {artifact_id}` accepts only an id recorded for the
  request's session and actor whose file still lies in the workspace; a path, another session's or
  another actor's id, a mail draft, or a missing file is refused by code. The model's tool data
  carries the id, kind and name only; the channel resolves the id again before sending (Telegram: a
  photo for `.png`/`.jpg`, a document otherwise, captioned with the file name; Agent Web: a listed
  attachment of the answer, opened by the existing sandboxed file route). Logs carry counts and codes.
- **End of a run:** the pictures a run made are sent at its end (Telegram flow, `/`-commands handled
  directly and runs the model started; Agent Web shows them under the run's answer). Telegram `/new`
  clears the chat's ledger. Rule: `AGENTS.md` 20.
- **Rejected:** pinning run entries in `_histories` beyond the window (Telegram only; the Gateway
  would still cut them); raising the window for everything (costs every turn's budget for one fact);
  sending a path to the model and letting it pass a path back (an arbitrary-path read); keeping the
  ledger in memory only (an Agent Web conversation outlives a restart).

## 2026-10-25 — Task result summaries, kept 30 days

Owner, 2026-10-25: 「每次跑完任務是不是應該要compose，把重要的結果結論記下來」; storage: 「存硬碟，保留 30 天」.
Builds on "A session remembers what it produced" above.

- **Decision:** when a task completes in a session — a Workflow run (Telegram flow, a directly
  handled command, Agent Web's run form, or a run the model started) or a model turn with at least
  two successful tool calls and no run — the Host composes a `TaskSummary`: `task` (the Workflow and
  up to three of its values by label, booleans by their choice words; or the person's message),
  `status`, up to five `key_results`, `artifacts` (the attach tool's ids), `follow_ups` (「郵件草稿已存在
  Outlook，尚未寄出」, 「這次沒有寫入或起草郵件」, a failure with 「再跑一次」), `at`, `session_id`.
- **Deterministic first:** key results are the run's one-line summary plus numbers and short words
  from step data (files, ids, bodies and inputs skipped). Only when that gives fewer than two and the
  run has a text `preview`, one bounded call condenses the preview (system prompt + preview ≤ 3,000
  characters, `max_output_tokens` 200, JSON array answer) on the gateway's approved model client,
  inside the channel's `session_model` context so it uses the session's model. No model configured:
  nothing is called. A fault: the deterministic fields stand.
- **Shown and remembered:** the 「結果摘要」 block (3–5 lines) ends the reply in Telegram and Agent
  Web; the latest 5 summaries of the session are listed in each turn's system prompt with the
  session's ledger (read from disk each turn, so they survive the window and a restart). Telegram's
  history entry also carries the block.
- **Storage:** one small SQLite file `<workspace>/session-artifacts/task-summaries.sqlite`, table
  `task_summaries (summary_id, actor, session_id, at, body)`; every read filters by actor.
  Rejected: `state.sqlite` (the Bridge's durable state with its own schema, cursor and locking; a
  30-day log of task results does not belong in it and would couple its schema to a UI feature);
  the actor's `memory.sqlite` (curated memory with provenance, undo and per-space retention rules;
  a summary is a transient record, and becomes curated only when the person presses 存成筆記);
  JSON files per session (a purge and a per-actor list across sessions would scan every file).
- **Retention:** `retention_days` default 30 (1–365) in `task-summaries-settings.json` beside it,
  set on the memory page's 紀錄 tab (additive file; absent means 30). Reads ignore older rows at once;
  the nightly job (`_nightly_tick`, once a day, no model) deletes them, and the session ledgers
  (`*.json`) last written before the cutoff.
- **Notes:** 「存成筆記」 under the block (Agent Web button `/api/memory/task-summaries/note`;
  Telegram button `sumnote:<id>` or the words 「存成筆記」 for the chat's latest summary) saves the
  block as one M3 note (`source_kind` answer, `source_message` `summary:<id>`, tag 任務摘要); a
  second press finds it saved. Nothing is saved automatically.
- **Visibility:** the memory page's 紀錄 tab lists the recent summaries with 存成筆記 and 刪除, and the
  retention. Rule: `AGENTS.md` 20.

## 2026-10-26 — Workflow 11 keys every ticket by its GitHub Issue, as the source Hermes runs does

Owner requests 2026-10-25 and 2026-10-26: Jira had problems, so every ticket moved to the GitHub
Project `rs-sde-projects`; the SDE weekly report missed updated GitHub Issues that the owner's
Hermes agent showed. Key every ticket by its GitHub Issue, link the Key cell to it, follow the
current workbook, match the owner's target mail, port the source job's behaviour, and give a
read-only preview. Strategy ADAPT (one slice, capability package only).

Source, read only: Hermes's skill `rs-workflow-jobs` (`%LOCALAPPDATA%\hermes\skills\productivity\
rs-workflow-jobs`) calls the source Host Bridge jobs `github_weekly_report` and
`github_weekly_email` (`n8n_workflow_system\host-bridge\jobs\`). Both, and
`tests/test_github_weekly_report.py`, exist only in that repository's working tree (untracked; its
HEAD 896046e does not contain them). Revisions read: report sha256
6cdbd56f02bc02fa453a509bc7b8c9926de497cba586d9eed2f7b22871570326 (2026-10-16, not the 9293c7ef…
pinned 2026-10-05), email 62c5220c8757f3596e55757d438e64efa03466e5bf5e5010326d821f08bf458d
(unchanged).

Root cause: AEP selected and keyed board items by the old Jira key in the title. Only titles
carrying `[GTM-n]` were selected (`tracked_key_prefix`, named explicitly in the owner's Host
settings), so an Issue filed on GitHub, which has no Jira key, was dropped before the window was
checked. In the read-only preview of 2026_43W, 15 of the 22 Issues in scope had no Jira key.

Ported (now equal to the source):

- **Key**: every ticket is keyed by its GitHub Issue, `#<number>` (source `_github_ticket_id`);
  an Issue from a repository other than the board's main one keeps `owner/repo#<number>` so two
  Issues never share a key. `ReportItem` carries `repository`, `number` and an optional
  `jira_key` (source `sourceKey`, found anywhere in the title; a leading `[GTM-n]` is cut from the
  summary). `tracked_key_prefix` now only names that Jira prefix; `board_key_prefix` is inert and
  kept so existing settings load. New contract type `ReportKey` accepts `#n`, `owner/repo#n` and
  the older `GTM-n`/`GH-n` forms.
- **Selection**: every numbered board Issue that is not in a closed Project status and whose
  `updatedAt` or an active comment (edited inside the window counts at its edit time) is in the
  window; the migrated body log is a fallback only without a real marker comment.
- **Sheet**: new setting `sheet_target` (default `week`): the run writes the week's own sheet
  (`2026_43W`), read as it stands when present and created empty at the end when missing, never
  seeded from an older week (source `_report_sheet_name`, "do not seed"). That is how the current
  workbook is kept (2026_42W and 2026_43W, `#n` keys). A new sheet gets its whole header row
  first, `Comments` included. `temp` keeps the older scratch sheet as a way back. The plan and
  the sheet state carry `target_sheet`, so the plan stays the whole instruction.
- **Key cell link**: the real run keeps the `=HYPERLINK()` formula (COM rule 4); the preview's
  openpyxl writer sets a real cell hyperlink and keeps the cell's fill, border and alignment.
- **Assignee**: Issue assignees by profile name, falling back to the login (the query now reads
  `name`); an Issue with none falls back to the Project field `SDE Assignee` (first non-empty of
  `assignee_fields`), and `assignee_source` records `issue`, `project_field` or `none`. The
  fallback names count in the mail too. This reverses the owner decisions of 2026-10-03 and
  2026-10-05 ("no fallback") by the owner's own request of 2026-10-26.
- **Instruments**: Production splits on the source's separators `[,;/&+]` plus the full-width
  comma (was commas only), which is what makes the target mail's 23 instrument-tickets.
- **Mail layout**: the owner's target (title, `本週有留言的 N / M 張`, the ticket-count callout,
  tickets per member, the pie titled "N instrument-tickets from M tickets" with `name / count
  (pct%)` labels, the stacked member bars with legend and x axis "instrument-tickets") was already
  rendered; the pie title and axis now always name instrument-tickets and each bar ends with its
  total.
- **Query**: field values read 100 per item (source 80, AEP was 50).

Time zone (an intentional difference, toward the source's own rule): a day is a Taiwan-time day.
`rules.report_day` converts a timestamp to UTC+8 before taking its date, in the board window,
comment selection, `M/D:` headers and the mail's activity count. The source compares GitHub's UTC
timestamps by their UTC date, contradicting its own rule ("what a Taipei team means by this week —
do not fix it to UTC") and its own `startTime`/`endTime`, whose dates are Taipei days. Now a named
week and the same days given as `startTime`/`endTime` select the same comments; a comment on
Monday 07:00 Taipei counts in the new week. Jira's `+0800` timestamps are unchanged by this.

Kept different on purpose:

- Several Issue assignees count once each in the mail (the source counts the joined string as one
  member); recorded 2026-10-03.
- New rows still need marker content in the window and rows already in the sheet are always
  refreshed, where the source pre-filters on any comment in the window; the result is the same
  set of written rows on 2026_43W (16).
- In Progress fill `#F8AD3E` (configurable) against the source's `#FCE4D6`.
- 100 assignees with a refusal when truncated (source 10); threads over 100 comments are named;
  an Issue the token cannot read is refused. Both page items by cursor and neither reads archived
  items; draft cards and pull requests are skipped by both.
- The project is found by number (host settings), not by title.

Preview: `python -m capabilities.weekly_report.preview --week <YYYY_NNW> --out <dir>` (real mode:
the host's `host.json`, the same client, credential mapping and planning steps as the Workflow,
read-only) or `--fixture` (synthetic, no credential). It writes only `<dir>`: `email.html` and
`effort-chart.png` from the mail step's own `compose_draft`, `workbook-preview.xlsx` (a copy of the
configured workbook written by `apply_plan` through `integrations.excel_openpyxl`), `plan.json`.
Checked once read-only on 2026-10-26 for 2026_43W: 19 / 22 tickets, 23 instrument-tickets, member
counts 5-4-4-2-2-1-1 and 16 rows, matching the owner's target picture and the sheet Hermes wrote.

Not changed: the Workflow manifest (its description and progress title still say "scratch sheet";
changing them is a manifest version bump, left for a separate slice), the Outlook writer, the
COM writer.

Rejected: keeping `GTM-n` keys (the Issues filed on GitHub have none, and the workbook is already
keyed `#n`); `owner/repo#n` for every key (the workbook and the source use `#n`); matching older
`GTM-n` rows by `jira_key` in the scratch sheet (the week's own sheet makes it unnecessary, and a
re-key through the COM writer is a larger change); writing the preview workbook with Excel (the
preview must not need Excel or touch an open workbook).

## 2026-10-26 — Multi-agent Gate 0 approved (ADR-MA1–MA5)

- **Decision (owner, 2026-10-26):** Gate 0 of `docs/proposals/MULTI_AGENT_PHASE0_REVIEW.md` is approved with
  the review's recommended defaults (「其他建議執行」), one addition, and a target of about one week for
  Phase 0.5 plus V1.
- **Open questions, as decided:**
  1. Verified work keeps going directly to `main`, with no PRs.
  2. Phase 0.5 (G5 cross-domain negative suite, P0-2 idempotent side-effect retries, G4 bookkeeping) comes first.
  3. Extend `AgentProfile`; no new AgentDefinition kind.
  4. CLI-backend parents (Claude Code / Codex / Copilot) do not delegate in V1. They receive PUBLIC data only,
     and the Host's guards, approvals and claim check do not run inside their loops. A later option is an MCP
     delegate tool whose sub-agent still runs in the Host.
  5. At most 3 sub-agents per turn, with token logging; no hard cost cap until a baseline exists.
  6. Sub-agent writes still need the person's confirmation.
  7. Hermes profiles are not in V1.
  8. New telemetry run kind `agent_delegation`, in Phase 2.
  9. `engineering.json` ships as a new version.
  10. ADRs are recorded here on approval.
- **ADR-MA1:** the parent delegates through the `agent__delegate` host tool; there is no up-front strategy router.
- **ADR-MA2:** extend `AgentProfile` with a model-policy reference and per-instance limits; instances are ephemeral.
- **ADR-MA3:** sub-agents use the session's model; an alias allowlist inside the approved Gateway comes later;
  multi-gateway is deferred.
- **ADR-MA4:** sub-agents act as the parent actor; the effective permission is parent grants ∩ profile allowlist ∩
  delegated tools, and it fails closed. Agent identity is deferred.
- **ADR-MA5:**
  - minimal context; artifacts go to the parent session ledger;
  - depth 1, ≤3 sub-agents per turn, the same guards;
  - no direct questions to the person (rule 18);
  - not persisted, and restarts are guarded (rule 19);
  - results pass G1–G4 and the claim check.
- **Addition (owner asked why there is no parallelism):** read-only sub-agents may run concurrently (≤3). Writes
  stay serialized by the Bridge exclusive lock, because Excel, Outlook and instruments allow one writer at a time.
  The Workflow engine stays sequential.
- **Deferred:** the ranker (no quality data yet), multi-gateway routing, cross-Bridge scheduling.

## 2026-10-27 — A side effect happens at most once per turn (P0-2, multi-agent Phase 0.5 part B)

- **Decision:** `Gateway.converse` keeps an in-memory, per-turn record of side-effecting calls that succeeded
  (`src/agent/turn_effects.py`), keyed by a SHA-256 digest of the tool name plus its canonical JSON arguments (the
  same identity as the repetition guard's `_call_key`). The record is held in a `ContextVar`: the Host check's retry
  pass (`checked_turn`) and any conversation or Workflow run nested under the same turn (a V1 delegated sub-run)
  share it; an outer turn opens it and drops it when the turn ends. A repeat of a recorded call is not executed: the
  model gets the earlier `ConversationToolExecution` with `replayed: true` and the note 「這個動作在本回合已執行過，
  未重複執行」. `Gateway.execute_workflow` inside a turn and without an engine idempotency key does the same for the
  same Workflow, manifest, arguments and actor. AGENTS.md rule 21.
- **What counts as side-effecting:** a Workflow run; a capability whose `CapabilitySpec.side_effect` is not `read`;
  a `HostTool` whose new optional `side_effect` says so (the business-card tools now carry their spec's). Only real
  success is recorded: failed, refused (`permission_denied`), `awaiting_approval` and form-only outcomes run again
  when asked, so the existing failure and approval handling applies. Reads are untouched.
- **Telemetry:** counts only — `tool.replayed` (`tool_id`, `loop_index`, `replayed`) and `side_effects_recorded` /
  `side_effects_replayed` on the turn's `run.completed`; never arguments.
- **Restart and resume:** the record is memory-only and lives exactly as long as the turn; rule 19 already refuses a
  restart while a turn is in progress, so a turn never straddles one. `Gateway.resume` is not a Skill route (the
  model cannot call it) and keeps the journal's durable "continued once" guard. Runs outside a turn (forms,
  schedules, remote jobs) keep the engine's idempotency keys and are unaffected. Telegram and Agent Web both reach
  the loop through `Gateway.converse`. A replayed Workflow call carries the run it replays, so
  `LocalAgent.converse` records each run id once.
- **Rejected:** feeding the first pass's tool results into the retry prompt only (the model may still call again);
  a durable, cross-turn cache (a person asking again in a new turn means it); keying by tool name only (different
  arguments are different actions); guarding every Host tool by default (many are reads or person-pressed cards).
- **Open:** `browser__operate`, `desktop__operate` and MCP tools declare no `side_effect` yet, so they are not
  guarded: identical GUI actions are also used to poll a window, and MCP tools carry no side-effect metadata. Decide
  per tool before V1 delegation offers them to a sub-agent.

## 2026-10-27 — Multi-agent V1 core delegation (implementation choices)

- **Context:** Gate 0 (2026-10-26, ADR-MA1–MA5 plus read-only parallelism). Contract: `docs/CONTRACTS.md`
  "Multi-agent delegation (V1)". Code: `src/agent/delegation.py`, `src/agent/delegation_scope.py`, the sub-run in
  `Gateway.converse`, `validate_profile` / `delegation_target` in `src/host_runtime/profiles.py`,
  `delegation_catalog` in `src/host_runtime/host.py`. Tests: `tests/test_delegation.py`.
- **Flag in `host.json`** (`multi_agent.enabled`, default false), read at build time like every other host setting;
  off leaves the tool list, profile validation, telemetry and `/api/activity` exactly as before. Rejected: an Agent
  Web settings store (a UI for it is another agent's slice; one place to look is simpler for V1).
- **Targets without an active profile.** Profile activation needs Shared Platform authorization, so an owner-mode
  host (no platform) could never have `may_delegate_to`. Decision: an installed profile that validates is a target
  **only when the person's own message names it** (`namespace/name` or `name`); the active profile's
  `may_delegate_to` entries are offered to the model with `description` and `selector_hint`. In owner mode a
  target needs no selection (the owner holds every installed asset, as `LocalPolicy` owner mode already says);
  its Skills and Knowledge must be installed. Rejected: offering every installed profile to the model (a ranker by
  another name); refusing delegation on owner-mode hosts (no way to try it on the owner's machine).
- **Strict activation with the flag on:** every `may_delegate_to` target must validate
  (`profile_delegation_target_unavailable`), like a missing Skill already fails a profile. A target's own
  `may_delegate_to` is ignored (depth 1). `RoutingOutcome` still refuses `kind: agent` (ADR-MA1): delegation is a
  tool call, so the routing refusal did not need lifting.
- **Effective tools** come from the Gateway's own Skill tool catalog (`Gateway.skill_tools`, the loop's catalog
  factored out unchanged): Skill in the profile ∩ capability in the profile and authorized for the parent actor by
  `LocalPolicy.authorize` ∩ vault in the profile's `knowledge` ∩ the requested subset. A Workflow tool is offered
  when every step capability passes the same test and is never read-only. **No Host tools for sub-agents in V1**:
  GUI and MCP tools have no `side_effect` yet (P0-2 open item), and forms, cards, memory and attach are
  person-facing (rule 18). An empty `knowledge` means no vault tool (fail closed, as the active-profile filter).
- **Minimal context:** the sub-run is `Gateway.converse` with only the objective (and listed artifacts as names,
  run summaries and the first 4,000 characters of text files — never a path) and a Host-written role. The request
  keeps the parent's actor, namespace, channel and **session id**, so an owner-mode write's approval request lands in
  the parent conversation's approvals (Agent Web, Telegram buttons) without a new path; `in_sub_run()` keeps the
  session list, memory, persona, forms, proposals, the conversation observer and the parent's live progress out.
- **`needs_input` by text marker** (`NEEDS_INPUT: <question>` as the first line), mapped to a failed Host outcome
  (`delegation_needs_input`) so the parent's claim check cannot count it as done. Rejected: a special Host tool for
  the sub-agent (more surface for the same result in V1).
- **G1 through the parent:** a sub-run answer that failed its own checks keeps its text and note; its Host data
  carries `delegation_verdict: not_validated` and a `harness_key` (profile + objective digest), and
  `harness_handoff.unverified` now keys repairs by `harness_key` when present, so another delegation's success does
  not clear the note. A read-only delegation counts as a read for the "lasting change" claim check.
- **Parallelism** is in the Gateway loop, not the Workflow engine: before running a reply's calls, the calls whose
  `HostTool.parallel` predicate says so (read-only delegations) start together (`asyncio.create_task` with
  `contextvars.copy_context()`, a semaphore of 3); the loop still applies the guards in call order and records
  results in call order. A delegation with any write-capable tool is not prefetched, so it runs alone in order;
  its writes are serialized by the Bridge exclusive lock as before.
- **Time:** the sub-run's `ConversationLimits` carry the profile's tool cap (never above the Host's) and its time
  limit (at least the contract's 60 s for the loop's own check), and `asyncio.wait_for` stops it at the exact
  `time_limit_s`, bounded by the parent turn's remaining time. A stop at the deadline cancels the in-flight await;
  a model call already sent finishes in its thread and is discarded. No cancel UI in V1.
- **Telemetry:** run kind `agent_delegation` (child of the parent turn's run through the existing `parent_run_id`),
  tokens per delegation both in the run totals and on the result (`Gateway` notes each sub-run response's usage).
- **Artifacts:** a sub-run's Workflow runs are recorded in the parent session's ledger by the delegation itself
  (the parent's `finish_turn` only sees the parent's own tool list); the parent turn's task summary follows the
  existing rules (the delegation counts as one tool).
- **Examples:** `agents/engineering-0.2.0.json` (new version with `may_delegate_to`; `engineering.json` 0.1.0
  untouched) and `agents/examples/knowledge-researcher.json` (read-only; not installed or offered until copied
  into `assets/agents/`, and its `knowledge` must name the vaults).
- **Not done in V1:** `max_retries` is not read (the conversation check's single retry applies); sub-agent runs
  are not added to the Agent's local run history (`state.record_run`), only to the session ledger; no cancel
  button; Agent Web / Telegram presentation and benchmarks are another agent's slices.

## 2026-10-27 — Multi-agent V1: what the person sees, the switch and the baseline benchmark

- **Context:** Gate 0 (2026-10-26) and the V1 core ("Multi-agent V1 core delegation"). This slice is the
  person-facing side and the review's §12 baseline. Contract: `docs/CONTRACTS.md` "Multi-agent delegation (V1)" →
  "Delegation progress lines, 委派紀錄 and the Settings switch". Tests: `tests/test_multi_agent_ui.py`,
  `tests/test_multi_agent_benchmark.py`.
- **Progress source:** a hook in `turn_progress.py`, not a new event stream. `delegation_started` returns a
  `SubAgentProgress` (a `TurnProgress`) that the sub-run sets as its `TURN_PROGRESS`, so the Gateway's existing
  progress calls count on the sub-agent's line with no new reporting path. Rejected: reading telemetry events for
  the live view (the progress board is memory-only and per session; telemetry is counts for Atlas, not a UI feed);
  a separate per-delegation callback API (a second path for the same tool counts).
- **The objective on the line** is the one exception to "progress shows names and numbers only": the person needs
  to tell parallel sub-agents of the same profile apart. Bounded: 60 characters, one line, credential-shaped text
  cut out, shown only to the turn's own actor (the progress route's owner check) and in that person's Telegram
  chat. Tool arguments, results and answers stay out.
- **委派紀錄 is stored on the answer** (`ConversationMessage.delegations`, ≤ 6, summaries ≤ 280 characters), built
  from the tool's host data read as JSON, so the view never imports the core module and a record it cannot read is
  skipped. Refusals are left out (no sub-agent ran). A sub-agent's files are resolved through the session ledger
  for that session and actor and listed on the answer, so the existing path-confined viewer opens them; no new
  file route. Rejected: re-reading the ledger when the page renders (later turns change it; the record should say
  what this answer used).
- **Settings switch** writes `host.json` `multi_agent.enabled` and reports saved vs running: the core reads the
  flag when the Agent starts, so the switch never pretends to apply at once and never changes the running
  configuration. A Host whose contract lacks the field refuses to save (`multi_agent_unsupported`).
- **Benchmark `benchmarks/multi_agent_v1`:** the fake mode drives the product's own Gateway loop,
  `DelegationService`, Bridge policy, Workflow engine, data policy and session ledger with a scripted model and
  mock handlers, and reuses coding_v1 T15/T16 validators and business_workflow_lab data. It proves plumbing and
  measurements, not a model's judgement; the live mode (the owner, never CI) measures that. The Bridge-safety
  scenario uses a new mock CMP180-like instrument that refuses every address but `MOCK::CMP180`. No thresholds
  until the live baseline (review §12).

## 2026-10-27 — graphify code graph for Claude Code sessions

- **Decision:** Claude Code sessions in this repository use a local graphify code graph (`graphify-out/`)
  to find code before grepping or reading source. The owner chose to wire it into the shared `CLAUDE.md`
  (section `## graphify`) and the committed `.claude/settings.json` PreToolUse hooks, because others will
  develop here too.
- **The graph is local, never committed.** `graphify-out/` is git-ignored. Each developer builds it with
  `graphify extract . --code-only` (AST only: no model, no API key, no document or spreadsheet conversion)
  and keeps it current with `graphify hook install` (post-commit rebuild). Rejected: committing
  `graph.json` (rewritten whole on every build, so every branch conflicts on it); building with documents
  (it converts spreadsheets and fixtures into `graphify-out/converted/`, which the code question does not
  need and which must never reach a commit).
- **Hooks call `graphify` from `PATH`**, not an absolute install path, so the committed settings work on
  every machine. A machine without graphify sees the hook fail without blocking the tool call.
- **Personal Claude Code permissions moved to `.claude/settings.local.json`** (git-ignored), so the shared
  `.claude/settings.json` carries only the hooks.
- **Not done here:** Codex reads `AGENTS.md`, not `CLAUDE.md`; `graphify codex install` would add the same
  rule there if Codex sessions should use the graph too.

## 2026-10-27 — BI Knowledge Case B next; RS_Knowledge may go live

- **Case B is the next BI slice** (owner: 「BI的部份要先做多表格報告」). Knowledge Strategy v1.3 §4.7 Case B:
  multi-table Markdown / Excel reports with advanced mapping (`explode`, `derive`, `compose`, `exclude_names`,
  `name_aliases`), role split Account ≠ Competitor ≠ Ecosystem, alias merging (VE-05, VE-06). This lifts the
  v1.3 §7 gate for Case B only; Cases C–E stay waiting. Rejected for now: Case E (slides → graph) first.
- **The BI flow needs guided steps like the Wiki's** (owner: the BI strategy has no organizing steps as clear as
  the LLM Wiki's). Case B's spec includes the Agent Web steps a maintainer follows, not only the import engine.
- **RS_Knowledge may go live at any time** (owner: 「RS_Knowledge隨時都可以上線」). The open steps stay as recorded
  in `docs/TASKS.md`: one adopt pass over its legacy-format Raw (as for the rs-k copy on 2026-10-12) and
  `host.json` pointing the project vault at it. The adopt pass writes into the real vault, so it runs with the
  owner present, after a backup, and after checking `/api/activity` before the Agent Web restart.

## 2026-10-27 — BI ingest: the owner's proposal becomes the plan

- **The owner's 「AEP BI 知識庫建立與 AI Ingest Proposal」 is the BI plan**, specified in
  `docs/phases/BI_INGEST.md`. It supersedes `docs/phases/BI_CASE_B.md`: Case B's multi-table recipes become the
  rule path, and role conflicts are decided by the person in review (earlier pass as the default) instead of a
  silent drop. This also brings LLM extraction (v1.3 Case E's core) forward; the v1.3 §7 gate is lifted for
  this plan. Cases C and D stay waiting.
- **Dataset schema upgrade now, not later** (owner: 「目前還在開發中尚未啟用，為什麼不做，我想現在做」). This
  replaces "a dataset's schema is chosen at creation and never changed" (2026-10-21): a dataset may move to
  another version of the same schema id after an impact preview. Additive changes rewrite nothing, removed
  fields keep their values (hidden), renames only through declared migrations, breaking changes are refused.
  A different schema id is still a new dataset. Local `bi.schema/v1.1` versions are allowed when they keep
  every shipped type and field (superset only), so an extended BI schema keeps the Dashboard and `bi__query`.
  Rejected: copying cards into a new dataset on every schema change (loses history and the owner's edits).
- **The two AI sessions call the model with no tools** (pattern of the Knowledge Skill assistant): structured
  suggestions validated by code, applied by the person. Rejected: running them through the chat Gateway with
  a tool allowlist (larger change, and source text could reach tools).
- **The ingest method is a versioned file per dataset, not a registry Skill**, so Session B can revise and
  revert freely. Publishing a method as an AEP Skill uses the existing approval flow later.
- **Trial runs and review live in `staging.sqlite`**; only commit writes `bi.sqlite`. Commit is one SQLite
  transaction, checks each matched card's version, and its key is the run id. Rejected: per-item commit with a
  failure list (SQLite makes the whole batch atomic, so all-or-nothing is simpler to trust).
- **Model use**: the model already approved in Settings for the source's data class; tests use scripted
  models and real-provider runs are reported separately. **Delivery**: verified phases pushed to `main`, no PRs.

## 2026-10-28 — BI ingest phases 3–6: implementation choices

- **A source's data class gates the model.** Every AI path that sends source text (extraction runs, Session A
  and B excerpts) refuses a source whose classification is not in `models.data_approval.approved_classes`
  (`classification_not_approved`). Rejected: recording the class only (the proposal requires respecting data
  classes and allowed models).
- **Text sources go to the AI path by default**; tables go to the rule path; a recipe forces the rule path.
  Without a model the AI path is refused and nothing starts.
- **Session turns are stored in the dataset's `staging.sqlite`**, beside the runs they compare, so a dataset
  carries its own design history.
- **Method files are simpler than the spec's `llm` block**: instructions, types, recipe, required-field
  checks; chunking, fact policy and matching stay fixed in code for now.
- **A run with failed chunks is `partial`** and can be reviewed and committed; only failed chunks are retried.
- **The rule-path engine and Sessions A/B were built by subagents in worktrees** and cherry-picked after
  review and verification.

## 2026-10-28 — BI vaults

Owner review of the built BI ingest flow and answers the same day; design in `docs/phases/BI_VAULT.md`.

- **A BI knowledge base becomes a vault**: one stated purpose, folders for 11 market segments and a shared
  library (products, competitors, technologies), `VAULT.md`/`vault.json` at the root so the Agent finds it by
  purpose. Cards are stored once per vault and name their segments in fields; folders are views.
- **Collaboration through change files in a shared folder** (owner chose option 1). No VM is available and
  172.25.228.141 is reachable only on the office LAN (not over the company VPN), so it cannot be the server
  everyone writes to. Each maintainer only adds their own change files; each PC rebuilds its SQLite from the
  folder in a total order (Lamport clock, author, seq); a change made from a stale base becomes a proposal.
  Rejected: SQLite in OneDrive (corrupts with two writers, sync locks are not atomic); 141 as server (not
  reachable outside the office); a relay such as Tailscale or Cloudflare Tunnel on the dual-homed 141 (would
  open a path next to the company LAN; needs IT/security first); a personal cloud host (company data);
  SharePoint List (needs an Azure AD app registration); Git (merge conflicts for non-engineers).
- **Every source is converted to Markdown first**, kept and editable as revisions; tables keep the rule path
  by default, the person may switch to AI (owner: follow the recommendation; Markdown editable).
- **A real search index** (SQLite FTS5, trigram) replaces "no extra index" from `BI_INGEST.md` §2.
- **Dashboard split**: AEP serves a coverage API and the segment x technology-area matrix; personal dashboards
  live in Atlas with an 「在 Atlas 開啟」 button (owner: OK for now, wants the button).
- **Permissions last**: no per-folder classification or new permission until the end; for testing the owner
  approves INTERNAL in Settings (option a), the existing data-class gate stays.
- **The 「匯入 CSV」 tab is removed**; 「方法」 is renamed 「擷取 Skill」 with built-ins; Sessions A and B are
  always visible.

## 2026-10-28 — BI vault V4: writes are captured and replayed

Implementation of `docs/phases/BI_VAULT.md` §3–§4 (backend and API, Claude Code).

- **A vault is the dataset `vault-<id>`**, so every existing route works on it unchanged; its local copy is
  `<workspace>/bi/vaults/<id>/`, and `vaults` and the `vault-` prefix are reserved for new datasets.
- **Every write is captured and replayed.** The store's write methods run unchanged on the local database in a
  transaction that is always rolled back; the rows they added or changed become one change file, which is
  then applied like any other. The local database is therefore only ever a function of the change files, and
  the non-vault path is untouched (one branch in `BiStore._db`). Rejected: rewriting each write method to
  emit operations (six methods duplicated, easy to drift); committing locally and writing the file beside it
  (the author's PC would hold uuid card ids and local proposal ids no other PC has).
- **Deterministic ids**: a vault card's id is a hash of type and key; proposals are named across PCs by a
  `pkey` kept in `vault_pkeys`. A conflict compares the field's value with the change's `base` (the value it
  was made from), not the card version, so edits of different fields never conflict.
- **Rebuild in place** (delete all rows and replay, one transaction) instead of replacing the file, so a
  reader holding the file open on Windows does not break it.

## 2026-10-28 — BI vaults V1, V5, V6: implementation choices

- **The 「匯入 CSV」 tab is removed from the page, its backend kept**: `/api/bi/import/*` still serves the demo
  load and the build result's undo. Its browser tests were moved to 「建立與匯入」 or removed with the feature.
- **Built-in extraction Skills are not files**: 「AI 擷取」 and 「表格規則」 are the shipped defaults; talking to
  Session B about a built-in saves a copy first, so a built-in never changes. 「表格規則」 has nothing for AI to
  adjust until a recipe is pasted (its automatic column mapping is code).
- **The Atlas address is a per-browser preference**, not a Host setting: each person runs their own Atlas.
- **Coverage is computed, never stored**: from the cards and a matrix (vault's `vault.json` block, else the
  dataset's `coverage.json`, else the shipped owner chart). Cards are never guessed into a cell; unplaced cards
  and unknown values are counted. The two placement fields come from a schema version made through Session A,
  not from a change to the shipped schema (which would alter every BI dataset's Dashboard and tests).
- **`bi__query` lists the PC's vaults with their purpose in its description** (per turn), and a query on a vault
  syncs it first. Rejected: a separate "which vault" tool (an extra model call per question).
- **Snapshots do not carry evidence yet**: the reader validates exact keys, so adding one breaks older PCs.
  Needs a format `/2` with a version window; left to the owner.

## 2026-10-28 — BI vault V2 and V3: implementation choices

- **Markdown revisions are files per source** (`<dataset>/markdown/<source id>/rev-<n>.md`) with their record
  in `staging.sqlite`, close to the vault folder layout of `BI_VAULT.md` §4 so V4 can map them; author and
  note live in the record, not the file name. Rejected: storing the text in SQLite (not a readable file).
- **Converted tables are read back exactly**, not through the phase 3 Markdown cleaning: cells escape `\`,
  `|` and line breaks, so a CSV or Excel cell keeps its text when the rule path reads the Markdown. A Markdown
  report a person wrote keeps the phase 3 reading.
- **Evidence of a table source is now a Markdown line** (`{"table", "line", "column"}`, plus `"sheet"` for
  Excel) because the run reads the Markdown revision it records. Rejected: keeping the original CSV row or
  sheet row (it cannot be traced once a person edits the Markdown).
- **A source that cannot be converted is kept with the reason** and converted again when needed; only a PDF
  without text is refused (`source_no_text`), as the design says. A missing office library is
  `converter_missing`.
- **The search index syncs itself after every `BiStore` write** (a hook at the end of the write transaction)
  and after every Markdown revision, comparing card versions and source revisions; a failure never fails the
  write and shows as `behind`. Rejected: calling it from each API route (easy to miss one, such as undo or a
  schema upgrade). The search route also syncs first, so a dataset from before V3 builds its index on the
  first search. Snippets are computed in Python with `[start, end)` marks rather than FTS5 `snippet()`
  markup, so the page never parses markup.

## 2026-10-29 — Coding at scale: explore-then-edit author, several files, declared checks

Owner request: team members develop chipset-control programs (Qualcomm WMT, a 125 KB driver file) through
AEP; the owner chose to make `coding/change` itself capable (option B). Plan `docs/phases/CODING_AT_SCALE.md`.

- **The author stays the internal Gateway model.** The data rule gives external agents PUBLIC context only and
  driver code is not PUBLIC, so C8 (native Claude Code author) does not apply. Rejected: completing C8 for this
  (would need the owner to relax the data rule).
- **Edits, not whole files.** The model reads through bounded read-only actions (list, outline, read a line
  range, search) and changes files with search/replace edits AEP applies (`harness/edits.py`); `old` must match
  exactly once, a failed batch changes nothing and the reason goes back to the model. A whole-file `content`
  answer is still accepted for the primary file. Rejected: unified-diff patches (models produce bad hunks and
  line numbers drift), native tool calling (the Gateway structured-output path is the one already proven).
- **The `ChangeAuthor` protocol may return a tuple of candidates**; the harness writes each changed one and
  records one `ChangeRecord` per file. E2E-01/03/04 authors still return one candidate and are unchanged.
- **The model chooses what to read; the host caps it**: 400 lines / 30,000 characters per read, outlines cut
  at the same size, 60 search hits, a 200,000-character transcript whose oldest action outputs are elided
  first, `author_max_turns` per attempt. `.git`, `.env`, keys and certificates are never readable. A repair
  starts a fresh exploration with the failure and the diff so far.
- **Line endings and BOM are kept** (a CRLF driver must not become a whole-file diff); a non-UTF-8 or
  mixed-newline file is refused for editing (`author_file_not_utf8`, `author_file_mixed_newlines`).
- **Several declared files**: `more_files` (up to 9), each checked like `file` (writable pattern, never a test).
- **Host-declared checks** (`checks` per repository, at most 5): `python -m <module> <args>` under the
  restricted runner in the worktree, `{files}` expanded; order new tests → checks → suite. Still no general
  shell: the host names the module. `pytest-suite` now runs only the `suite` case (found by the new test: it
  had collected every regression case, so a check's name became a pytest path).
- **Limits in `host.json`**: `author_max_turns` (30), `author_max_output_tokens` (8,000),
  `change_max_processes` (1; raising it lets tests start tools that the firewall rule does not cover).
- **Not changed, for the owner**: the shared credential rule refuses a candidate whose text matches the secret
  pattern, and `password: str` matches, so a driver with such lines cannot be changed (the run stops with
  `author_change_has_credential`).
- Workflow `engineering/coding-change` 1.1.0 (`more_files`), Skill `engineering/coding` 1.9.0.

## 2026-10-29: The WMT suite runs with the framework installed on the development PC (owner)

After the `coding/change` dry run on `rs-wmt-kt101` (`docs/phases/CODING_AT_SCALE.md`, "Dry run on the WMT
repository"):

- **The harness is not changed for the suite.** The chipset development PC installs `rs-wmt` (and what the
  repository pins with it: `rs-wmt-cminstrument`, numpy) plus pylint and mypy into its runner interpreter,
  so `pytest-suite` runs the repository's whole `tests/` folder as it does elsewhere.
- **Rejected: a per-repository suite selection** (`CodingRepository` naming the suite's tests), proposed so
  the runner would not need the framework and a deliberately failing replica test would not block other
  runs. Rejected for now: the PC that develops the driver has the framework anyway.
- **Consequence kept**: the suite is all-or-nothing, so a test that fails on purpose in `tests/` makes every
  run on that repository fail until it passes; replicas are added one stage test at a time.
- **The credential rule is unchanged**; `driver.py`'s `password:` docstring line was reworded in kt101
  (branch `aep/qcom-log-replica`, `8b4d127`) instead.

## 2026-10-29: One market BI vault for every domain (owner)

Context: the owner's manager built five BI knowledge bases by hand (wireless, robotics, aerospace, wireless
module, AIDC), each needing Claude Code to change the schema, ingest, seed and dashboard tools again. The
comparison is in `docs/phases/BI_VAULT.md` §12.

- **Decision**: one market BI vault holds every domain; a card is stored once with `domain` as a list where
  the type allows it; per-domain differences (nodes, segments, chains, aliases, coverage matrix) are vault
  configuration. Separate vaults only for different purposes.
- **Rejected: one vault per domain.** `bi__query` reads one dataset per call chosen from purpose lines, so
  cross-domain questions would miss vaults; shared companies, competitors and nodes would be copied and
  drift (20 shared cards already across the five bases); the manager's schema and ingest are built to merge.
  Fixing that would need cross-vault search, a shared library vault and cross-vault names, more work than
  per-domain configuration.
- **Consequences**: proposed phases V9–V13 in §12 (schema shapes, per-domain `vault.json` configuration,
  extraction Skill evidence rules, built-in analyses, quality checks); V8 permissions become per domain.
  None started.

## 2026-10-29: BI vaults V9–V13, implementation choices

- **Schema v8 ships as `bi.schema/v1.1@2.0.0`, not 1.2.0.** Session A publishes local versions as the next
  minor version (1.2.0, 1.3.0 …); a shipped 1.2.0 would take the place of a PC's own 1.2.0 and change the
  schema of every dataset bound to it without a word. A local file can no longer install over a shipped
  version. Rejected: replacing the shipped 1.1.0 (every existing dataset is bound to it).
- **A bare `bi.schema/v1.1` now means 2.0.0** (the contract already said "newest version"), so a new vault
  starts on v8; unbound datasets (demo) stay on 1.1.0. Tests that assumed the bare id meant 1.1.0 were
  changed to name the version they meant.
- **Widening is a kind change that keeps values** (`enum`/`str` → `list`, `link` → `linklist`, `int` →
  `float`); the upgrade migrates values with history inside the same transaction, so vault capture shares
  it. Other kind changes stay breaking (the test that used `str → list` as its breaking example now uses
  `str → int`).
- **`float` reads plain numbers and one trailing `%`**; 約, ranges and units are refused, as the manager's
  rule keeps the original text instead of a guessed number.
- **The file name names the type before the headers do**: the manager's CSVs use field keys
  (`name,domain,body`), which fit many types; the header guess put `13_competitor.csv` in Opportunity.
- **V10: the domain configuration lives in the dataset's `meta`, not in `vault.json`.** `vault.json` is
  written once by the creating PC and no PC edits another's file (BI_VAULT.md §3); a configuration that
  grows with each new domain must change many times, so it travels as `meta` change files, replayed in order
  like every write, a concurrent save becoming a vault conflict. A segment the schema cannot hold yet is a
  warning, not a refusal, so the configuration can be written before the schema step.
- **V11: the evidence rules are part of the system prompt, not of the method.** The manager wrote them into
  every seed script; a method edited in Session B could lose them, so they cannot be edited. Numbers are also
  checked in code, because a prompt rule is not a guarantee: a fact number not written in its quote becomes
  an inference (amounts in 兆/億 are read so the manager's unit conversion still passes).
- **V12: the manager's sections are offered by type, not by version.** A section appears when the dataset's
  schema has every type it reads, so v4 datasets gain only §20, §26 and §29–§31 and nothing breaks; the
  chains come from the domain configuration, never from a field (his rule). Sample cards (`SAMPLE-…`) are
  left out by default, as in his dashboards; the demo's cards do not use that prefix and are unaffected.
- **V13: quality is read only and general.** The manager's checks named his folders and his AIDC node
  format; here each check reads the schema (link targets, evidence grade, revenue layers) or the domain
  configuration (`node_name_pattern`, a domain's `nodes`), so a new base needs settings, not a script.
  Findings are `issue` (fix) or `warn` (an admitted gap), and nothing is changed by a check.

## 2026-10-29: BI vaults have no permission control; 2.0.0 `segment` takes the chart's segments (owner)

- **No permission control in BI vaults.** V8 (permissions per domain, earlier per folder) is dropped; every
  maintainer of a vault can write every domain. Rejected: per-domain permissions (§12 had proposed them).
- **2.0.0's `segment` allows the market chart's 11 segment ids** (the vault's application folders) beside
  aerospace's five, with the labels as aliases, so AIDC and the other domains place cards in the coverage
  matrix without a schema upgrade. 2.0.0 was changed in place rather than shipping 2.1.0: it was published
  the same day and no vault used it yet. Rejected: a per-domain segment field.

## 2026-10-30: One version mechanism for every knowledge base (owner)

Plan `docs/phases/KNOWLEDGE_REPO.md` (design, for owner review; nothing implemented yet).

- **Wiki and BI knowledge bases are updated the same way: commit, push, revert, tag/publish**, by one person
  or several. They differ only in how a knowledge base is built: its schema and its skills, which both live
  inside the repository. The common engine merges *units* defined by the type (a card field for BI, a page
  section for wiki), so one engine serves both. Rejected: git inside the shared folder (OneDrive corrupts
  `.git`, sources are binary, maintainers are not git users); keeping two mechanisms (two sets of operations
  to learn and code to keep).
- **commit** is local and states its purpose (required); **push** merges own commits into the maintenance
  repository, a unit changed differently on both sides being a conflict a person decides; **revert** restores
  any commit or tag as a new commit, never deleting history; **tag** names a commit and never moves;
  **publish** makes a tag the version the Agent reads, one person's confirm click, never the model.
- **The repository's schema file is authoritative**; a PC whose built-in copy of that version differs
  refuses to open it. Rejected: built-in schemas taking precedence (the folder would not say how its data is
  classified).
- **Skills name their schema version and are not run against another version.** Written classification
  rules (BI domain `notes`) move into skills; structure (segments, chains, aliases) stays configuration.
- **The Agent reads the published version only**; a repository never published is read at its head.
- **Every change goes into a working copy first; any maintainer may revert, tag and publish** (no permission
  control, as for BI vaults 2026-10-29).
- **Both types move now, without compatibility** (no existing users): BI `changes/` and the wiki sandbox,
  in-place push with `.ingest-backup/`, `pushes/` and candidate versions are replaced. Wiki pages are read
  from a rebuilt read-only folder Obsidian can open; editing happens in the working copy. Rejected: keeping
  in-place editing in Obsidian (concurrent edits overwrite each other and bypass commit purposes).

## 2026-10-30: A Telegram conflict is waited out, not the end of the loop (owner)

- HTTP 409 from `getUpdates` (another program polls the same bot) is retryable: the resident loop keeps
  polling with the doubling delay and reports `telegram.problem = "telegram_conflict"` in the settings,
  which the page explains. Found live: a second poller held the bot for a while (no webhook; not
  identified, and not Hermes, which uses another bot), AEP's loop stopped for good on the first 409
  and the bot looked dead with nothing on screen, though the conflict had already ended. Rejected: keep stopping (silent until a person
  reads the code) and stopping the other program (it is the owner's).
- This supersedes the Phase 7 adaptation note "HTTP 409 is `telegram_conflict` and stops the loop".

## 2026-10-30: How the Agent picks up a newly published BI version (R5, Claude Code)

- Settles the open point of `docs/phases/KNOWLEDGE_REPO.md` §7: the Agent picks a new publication up
  **live, at its next question**. `bi__query` syncs the vault (as before), then reads
  `vault.reading_store`: a read-only copy `<workspace>/bi/vaults/<id>/published/bi.sqlite` rebuilt from
  the units at the published commit (the pushed head when never published) whenever that target changes
  (`version.json` marks what was built). No restart and no binding change.
- A separate copy rather than reading `bi.sqlite`: `bi.sqlite` holds this PC's local commits and
  uncommitted edits, which decision 8 keeps away from the Agent. Rejected: computing the published state
  per question (a full rebuild each time), and switching at the Agent's restart (a maintainer would not
  see the effect of 「發佈」 until someone restarts Agent Web).
- When the shared folder is unreachable the Agent answers from the last copy this PC built; a vault never
  built here is refused (`vault_unreachable`).

## 2026-10-30: Skills of a BI vault: which source folder, and what an AI run reads (R3, Claude Code)

- Sources of a BI vault stay in this PC's staging store (R2), so they have no repository path for
  `applies_to` to match. The **person chooses the folder** when starting an AI run (a list of the vault's
  `sources/` folders, `sources` when not chosen). Rejected for now: a model call that classifies the source
  into a folder before extraction (one more model call per source and a guess the person must check anyway)
  and copying sources into the shared folder (a size and confidentiality decision for the owner, R6).
- The **classify skill is not a separate model step**: its text (types and folders) goes into the
  extraction prompt beside the extract skill, after the fixed evidence rules. One call per chunk as before.
- The generated classify skill follows a schema change by itself only while nobody edited it (its text
  equals the generated one); an edited one shows 「需要更新」 (decision 3) instead of being overwritten.
- Domain **notes move on every domain save** in a vault (not only once at conversion), so the domain
  editor, which still has a `notes` key, cannot bring notes back into the configuration; the notes become a
  new skill revision, reviewed and committed like any change. Local ingest methods (Session B, BI ingest
  phase 5) keep working on top of the skills: a method's instructions come before the skills.

## 2026-10-30: Wiring the wiki type (R4): registry, Agent reading, slices (owner)

Owner answers before R4 wiring (`docs/phases/KNOWLEDGE_REPO.md` §10–§12):
- **Registry in the workspace, as BI.** A wiki repository is created, joined or imported through AEP and
  listed in the workspace's knowledge-repository registry; publishing no longer moves folders or rewrites
  `host.json` (`knowledge_pipeline.vaults[].root`, `knowledge[].vault_root`). Maintainers and question
  sets move with it. Rejected: keeping `host.json` as the registry (every publish would still edit it).
- **The Agent reads the published version live**, as BI (decision of the same day for BI): a local
  read-only folder rebuilt from the published commit (the pushed head when never published) with the
  pages, `raw/` restored from `sources/` under its original paths (citations name `raw/...`), and a
  manifest computed from it; picked up at the next question, no restart. Rejected: rebuild on publish and
  switch at restart.
- **Three slices**: R4a backend (registry, import of a copy, ingest and rules writing to the working copy,
  benchmark as a push check, the Agent's read path); R4b page (repository chooser and the 「版本」 area
  replace the sandbox chooser, push, refresh and candidate publish); R4c removal (sandboxes, candidates,
  `knowledge_push`, `knowledge_publish`, their tests).

Engineering choices (Claude Code), fixing the R4 core library before wiring it:
- The wiki `schema` unit holds a reference `wiki.schema@<version>` (file `schemas/wiki.schema@<version>.md`)
  instead of a file path, so the shared skill binding (「需要更新」) compares like with like.
- Wiki skills use the shared skill format (`skills/<name>/rev-<n>-<author>.md`, unit value an object,
  role `ingest`); an imported `SKILL.md` becomes revision 1 with its text as the body.
- Raw files are units `raw:<path under raw/>` → `{"file": "sources/…", "sha256"}`, so the published folder
  restores `raw/` under the names pages cite; originals from `drop/` stay files under `sources/` only.
- **How a wiki repository becomes an Agent tool (owner, later the same day).** A `host.json` Knowledge
  binding names it once, `{"asset": "<namespace>/<name>@<version>", "repo": "<repository id>"}`; the
  identity, its governed manifest (approval, purpose, boundaries, evaluation set) and Agent-profile grants
  stay as they are, and publishing changes only the content behind it, never `host.json`. Rejected:
  offering every registered wiki repository automatically as `knowledge-repo/<id>@1.0.0` (test
  repositories would reach the Agent and existing profile grants would need new names). The catalog keeps
  such a binding as a live entry: its digests are recomputed from the published folder when the version
  changes; an unreachable folder keeps the last version built (the Agent never answers from nothing when
  OneDrive is offline). The legacy candidate publish and refresh refuse a repository binding
  (`knowledge_is_repository`).

## 2026-10-31: The wiki working folder and the benchmark as a push check (R4a, Claude Code)

- **Working folder instead of rewriting the pipeline.** The ingest pipeline (convert, plan, apply, rule
  editor) keeps working on a folder: each wiki repository has `knowledge-repos/<id>/work-view/vault`,
  built from its working units, and `wiki_work.capture` stages what a step changed back as units (pages,
  new Raw as `raw:` units, new `drop/` files as originals, `SKILL.md` edits as skill revisions, a
  `CLAUDE.md` edit as the next schema patch version). Rejected: making every pipeline step write units
  directly (a rewrite of planning and apply with the same result). Raw stays immutable: a changed or
  removed Raw file is reported, never staged.
- **A `CLAUDE.md` edit is a new schema version**, so skills written for the old one show 「需要更新」
  (decision 3) until saved again. This makes the rule editor's schema edits visible in history; it can be
  revisited if it proves noisy.
- **The benchmark is run by the person, checked by the push.** A run asks the model for minutes, so a push
  never starts one. Each run records the digest of the pages it tested; the push check blocks on the
  regressions of the newest finished run for exactly the pages being pushed, and otherwise pushes with the
  note that the content was not tested. Rejected: blocking every untested push (a one-word fix would need
  a full run) and running the benchmark inside push (the request would hang for minutes). A push whose
  content changed by merging someone else's work counts as untested.

## 2026-10-31: The Knowledge tab's steps on a wiki repository (R4b part 1, owner + Claude Code)

- **Intake and question folders are set per PC** (owner answer to "知識庫的「拉資料」來源和測試題目要放哪裡？"):
  each PC sets, per repository, the folder 「拉資料」 pulls originals from and the folder the question sets
  are in (`<workspace>/knowledge-repos/<id>/settings.json`). Uploading files keeps working without an
  intake folder. Questions move into the repository later. Rejected: questions inside the repository now
  (larger slice), and reusing `host.json`'s pipeline vault `drop_root`/`questions_root` (it would bind the
  repository back to `host.json`, against decision "registry in the workspace").
- **Engineering (Claude Code): the pipeline steps open a repository as a sandbox id.** `Sandboxes.open`
  takes `repo.<id>` and returns the repository's working folder with a `SandboxInfo` carrying the
  repository, intake and question folders, so convert, plan, apply, the rule editor, lint, re-ingest and
  the benchmark run on it without being rewritten; merge and the sandbox push refuse it
  (`repository_uses_versions`). R4c replaces `SandboxInfo` when the sandboxes go. Rejected: a second set
  of pipeline capabilities for repositories (every step duplicated until R4c).
- **Engineering (Claude Code): a capture compares with what the folder was built from, not with the
  working units.** Found while wiring: anything that syncs (the Agent reading, a status) can bring
  someone else's change into the working units while the folder still shows the old text, and comparing
  the folder with the working units would stage that old text back. The folder now keeps its built pages
  (`work-view/base/`) and digests (`state.json`); a capture stages only the units the person changed,
  and every rebuild captures first and carries `drop/` and the hidden pipeline records over. Rejected:
  rebuilding on every sync (loses edits in the folder) and refusing to sync while the folder has edits
  (the Agent's reading would stall).
- **Engineering (Claude Code): what a step wrote is staged right after it**, for every step whose
  capability is not read-only (`side_effect`), and before every version operation that reads or moves
  the working units; a person never has to "collect" changes. A question edited in a repository is
  written into this PC's question folder, never into the repository.

## 2026-10-31: Wiki repositories on the Knowledge page (R4b part 2, Claude Code)

- Repositories are listed beside the sandboxes on the same start screen until R4c removes sandboxes, so
  nothing in progress in a sandbox is cut off; the three steps are the same page for both, and for a
  repository step 3's 「版本」 area takes the place of the sandbox push card and the candidate
  merge/publish (design §2: "push there becomes commit and push"). Rejected: a separate repository page
  (two copies of the step UI until R4c).
- The 「版本」 area is the BI one's behaviour (commit with purpose, push, conflicts side by side, history,
  diff, revert, tag, publish after `confirm()`) written for the Knowledge page's own status line and
  buttons; the BI functions are tied to the BI pane's elements and notices. Pulled originals are staged
  files without unit changes, so the area lists staged files and offers a commit of files only.

## 2026-10-31: Session B on a skill of a BI vault (owner request, Claude Code)

The owner asked for editing a skill with the AI. It is the existing Session B (local ingest methods,
`methods.py`) pointed at one skill: same storage (the dataset's `sessions` table, kind `skill`), one model
call per turn with structured output and no tools, code checks with problems fed back, nothing changes
until the person applies. A suggestion may change only the skill's text, folders and card types, and is
checked exactly as a hand-saved skill (`vault.checked_skill`); applying stages the next revision bound to
the vault's current schema, so a 「需要更新」 skill is updated this way and reaches others only by commit and
push. Rejected: letting the model write the skill revision directly (the person decides, design §8), and a
separate session store for vault skills (two conversation formats for one panel pattern).

## 2026-10-31: BI 「建立與匯入」 as three steps (owner request, Claude Code)

The owner found the six-step flow too complex and named three steps plus push: input and convert; schema,
skills and ingest; dashboards, question benchmark and testing, then push. The page now has those three steps;
the five ingest parts (schema and skills, trial, review, write, result) stay as parts of step 2 in a second
row, so their code, checks and stored stage did not change. The 「版本」 area (commit, push, history, publish)
moved from step 1 to step 3, as on the Knowledge page; the vault skills moved to step 2 beside the schema.
The schema part opens without a chosen source (editing the schema or a skill needs none; trial, review and
write still do). Rejected: merging the five parts into one long section (larger change to the run flow, and
the program moves between them after an import and a write), and leaving 「版本」 in step 1 (push is the end
of the flow).

## 2026-10-31: BI step 3 and the skill AI: owner decisions (owner, recorded by Claude Code)

The owner answered the open questions of the three-step BI page:

1. **The skill AI runs with tools, on the Agent's own harness** (`Gateway.converse`). Reason given by the
   owner: without it there is no way to confirm that a suggested rule matches the effect of the knowledge
   base that is finally built and the effect users will later get. Its tools read sources, try a rule in
   staging, compare runs and run the benchmarks; applying a suggestion, committing and pushing stay the
   person's. Rejected: the one-call Session B (it suggests without seeing any effect) and a separate loop in
   the BI module (a second loop, guard set and trace beside the Agent's).
2. **Analyses by AI conversation, with SQL and Python scripts.** The owner's manager's example: simple
   scripts or SQL queries that draw the charts and tables a knowledge expert wants, to establish a
   relationship or phenomenon; the owner wants these made through an AI conversation. Both read-only SQL on
   a copy of the knowledge base and Python scripts are allowed; scripts need a constrained runner (own
   process, time and output limits, no network, no writes outside its scratch folder). Rejected by the owner:
   SQL only.
3. **The BI benchmark tests both** chat answers (questions asked the way a user asks, through the Agent with
   `bi__query`, on the working and on the published version) **and** extracted cards (the extraction scorer
   `capabilities/bi_cards/benchmark.py` on cases kept in the knowledge base).

Order chosen by the owner: benchmarks first (the skill AI's tools need them to verify a suggestion), then the
skill AI on the harness, then AI analyses. Design: `docs/phases/BI_TEST_AND_TOOLS.md`.

## 2026-10-31: The skill AI on the harness, implementation choices (BI T2, Claude Code)

- **Seam.** The skill session keeps its storage, checks and routes; the model call is behind an `asker`
  (`skill_session.Asker`). Agent Web supplies one that runs `Gateway.converse` as a Host sub-run with
  turn-scoped Host tools (`agent.gateway.turn_host_tools`, added for T1); elsewhere (tests, no Agent Web) the
  one call remains. Rejected: a second session kind (two panels and histories for one skill).
- **Models.** The turn uses the Agent's model (it is the Agent harness); trial runs inside it use the
  Knowledge model, as every ingest trial does, so a tried rule behaves as it will in ingest.
- **Draft rules are tried, never staged.** A trial takes `skill_draft`, which stands in for the skill only in
  that run's rules (marked `draft`). Rejected: staging a revision to try it (it would show as an uncommitted
  change and could be pushed by accident).
- **The suggestion is a tool call.** `bi_skill__suggest` is checked like a hand-saved skill and a problem is a
  failed tool result the model fixes in the same turn (the old three attempts become this loop).

## 2026-10-31: AI analyses, implementation choices (BI T3, Claude Code)

- **Python is guarded, not sandboxed.** A script runs in its own `python -I` process, in an empty scratch folder
  holding a copy of the data, with an empty environment, a 30 s limit and capped output; an audit hook refuses
  network, process and native-library modules and events and writes outside the folder. Audit hooks are a
  guard against mistakes and stray model output, not a boundary against a determined attacker (CPython's
  documentation says so): the scripts come from the host's approved model, run only on a copy, and the person
  sees each script with its output. A real boundary (a container or a Windows AppContainer/job object) can
  replace `run_python` later without changing its contract. Memory is not limited on Windows yet.
- **SQL is enforced by SQLite.** A read-only connection on a copy plus an authorizer that allows reading only;
  one statement per call.
- **Charts are drawn by the page** (inline SVG; bar, line, scatter, table), so nothing is loaded from outside
  and a saved analysis is just its code and a chart spec rerun on the current data.
- **Vault only.** Saved analyses are vault units (committed and pushed); a dataset only on this PC has none.
- **Shared harness helper.** `host_runtime/bi_harness.converse` runs every BI sub-run (benchmark questions,
  skill AI, analysis AI) with turn-scoped tools.

## 2026-11-01: The BI page opens on 「建立與匯入」 (owner request, Claude Code)

The owner looked for the three steps and found the toolbar instead. The BI page now opens on 「建立與匯入」 (tab
first); a dataset read from the platform still opens on the Dashboard (it cannot be built). 「新增資料集」, 「安裝
schema」 and 「載入示範資料」 are folded into 「資料集管理」. 「發佈到 Shared Platform」 (the platform copy of a dataset on
this PC) is hidden for a vault, whose changes reach others by commit, push and publish in step 3. Rejected:
removing the platform copy (datasets on one PC still use it).

## 2026-11-01: BI: retire the domain configuration and the coded Dashboard (owner)

The owner agreed (2026-11-01) that a BI knowledge base should have four concepts only: schema (including allowed
values with labels and aliases), skills, cards (including each entity's aliases) and analyses. The domain
configuration (`aep.bi.domains/v1`) is split into the schema and the cards and then removed; the coded Dashboard
sections (`dashboard.py`, `market.py`) become a default analysis pack, removed only after a parity test passes
for every section. Atlas becomes a viewer of the vault's published analyses through a read-only feed
(`aep.bi.analysis_feed/v1`: GET only, loopback, no token, local origins, no code run by a feed request) and
owns only its own layout. Design `docs/phases/BI_ANALYSIS_DASHBOARD.md`; the Atlas side is built by Codex from
`docs/phases/BI_ANALYSIS_DASHBOARD_ATLAS_BRIEF.md`, the two meeting at golden fixture files AEP writes first.
Rejected: keeping the domain configuration beside the schema (two places for one taxonomy), keeping coded
sections beside analyses (three dashboard mechanisms), and Atlas defining its own analyses (two copies of the
numbers).

## 2026-11-01: BI analysis feed, implementation choices (F1, Claude Code)

- **Parameters land with F1.** The feed's golden answers need `params` (`domain`), so analysis `params` and
  `requires` (checking, resolving, binding to SQL and scripts) are built in F1; P1 adds what is left (the page's
  parameter controls, `meta:dashboard` editing, offering by `requires` on the page).
- **SQL on request, scripts never.** The design keeps a tokenless GET from starting code. A read-only SQL
  statement on a read-only copy, under the authorizer and a 10 s limit, is computed on request and cached; a
  script result not cached is queued and answered `409 result_not_ready`. Rejected: computing every parameter
  combination ahead (unbounded), and refusing uncached SQL too (Atlas would wait for nothing).
- **Enum values resolved by AEP.** The feed lists an enum's values (from the published schema), so Atlas needs
  no schema. `values_from` on a `domain` field without allowed values takes the schema's `domains` (2.0.0's
  `domain` fields carry none).
- **Golden answers come from the feed code itself** on a committed fixture vault built reproducibly (fixed
  clock, seeded ids); the manifest `golden/requests.json` gives the order and statuses, so Atlas and the F2
  live-route test replay the same requests. Rejected: hand-written golden files (they drift from the code).

## 2026-11-01: The default analysis pack, implementation choices (P2, Claude Code)

- **Scripts that carry the coded functions verbatim, not SQL.** Each section became a Python analysis whose code
  is a shared prelude (the helpers of `dashboard.py`/`market.py`, cards read through `query()`) plus the
  section's function copied unchanged. Parity is then by construction and checked per section on three
  fixtures (robotics demo v4, the market fixture 2.0.0 with a sample card, the feed fixture vault) for every
  domain, with and without samples, plus a run of every script in the guarded process. Rejected for now:
  rewriting 27 sections in SQL (ordering ties, date and list logic make parity fragile); a person or the
  analysis AI can still rewrite any of them in SQL later, the parity test showing the difference.
- **Card links become names.** A result table holds plain values, so a card cell is its name; the coded
  Dashboard's links to cards are lost in the analysis version (P3 may add links by name).
- **What waits.** The chain sections (A–A3) and the coverage matrix read the domain configuration; they enter
  the pack once the schema carries `chain` and `tech_areas` (D1, D3) and stay coded until then. The quality
  section stays the quality check (`/api/bi/quality`), not an analysis.
- **New vaults start with the pack** (create and convert, in the first commit), so the Dashboard is never empty
  once P3 draws analyses; tests about vault mechanics and the frozen F1 fixture opt out (`default_pack: false`).
- **Found on the way:** a guarded script's non-ASCII output was garbled on Windows (`-I` ignores
  `PYTHONIOENCODING`); the runner now writes UTF-8. The Dashboard's 「分析」 card could interleave two drawings;
  a newer drawing now stops an older one.

## 2026-11-01: The Dashboard as analyses, implementation choices (P3, Claude Code)

- **Analyses become sections in the page's existing shape** (columns, rows, flags from `level`), so the
  Dashboard's badges, strip, tables and phone layout stay one renderer. Card links survive by name: a cell equal
  to exactly one card's name links to that card.
- **Vaults first, local datasets at P5.** The design's Dashboard is the vault's analyses; a dataset only on
  this PC keeps the coded Dashboard until P5 removes it, when it draws the built-in pack through the same
  `board.py` (already written for it). Rejected now: switching local datasets in P3 (the coded sections are
  still the reference the parity tests compare with).
- **Speed.** The page draws 20+ scripts at once: parallel guarded processes (6) and an in-memory cache keyed by
  the database file's state keep a repeat draw instant. The chain sections and quality are still coded here.
- **Parameters at the top.** 領域 and 範例卡 stay the existing controls; any other parameter an analysis declares
  appears beside them and applies to every analysis that declares it.

## 2026-11-01: The schema with technology areas and chains is 3.0.0, not 2.1.0 (D1, Claude Code)

The design names `bi.schema/v1.1@2.1.0`, but Session A makes a local version as the next minor step above every
known version (`schema_versions._next_version`): on a PC with 2.0.0 that is exactly 2.1.0, and the owner had an
open item to add `tech_areas` through Session A. A shipped 2.1.0 with other content would then be refused
beside that PC's or vault's own 2.1.0 (the vault's schema file is authoritative, `schema_mismatch`), stopping
its sync. As V9 chose 2.0.0 so the shipped version never meets a local one, this one is 3.0.0 (fields added
only; a 2.0.0 dataset upgrades without moving a value). The `aliases` field of D2 is in the same version so the
migration (D3) needs one upgrade. Rejected: 2.1.0 as written (collision), 2.0.1 (a patch number for new fields).

## 2026-11-01: The chains and the coverage matrix as analyses, implementation choices (Claude Code)

- **A domain's chains are the schema's chain values its nodes carry.** The domain configuration listed chains
  per domain (a chain with no node still showed a row of zeros); after the migration a chain exists only as an
  allowed value of Node `chain`, so the analysis lists, in the schema's order, the values some Node of the
  domain carries. Labels come from the schema's aliases (the first alias of each value). Shared-node and
  shared-company spans are in the schema's order (the configuration's order before). Parity was checked on a
  vault with a configuration: the coded A–A3 before the migration equal the analyses after it, for every domain,
  with and without sample cards. Rejected: keeping a chain list per domain somewhere (that is the configuration
  the owner retired).
- **The coverage matrix is a long table, all cells, every card.** One row per segment x area with the coded
  report's numbers (cards, types, sourced share, newest, emptiest fields), equal to `coverage.compute` on the
  same cards with the configuration's matrix. Not carried into the analysis: the totals of cards without a
  segment or an area, the unknown values and the per-cell card list (the page's matrix view keeps them until
  P5). No domain parameter, as the coded matrix had none. Rejected: a pivot (segment rows x area columns) that
  would drop every number but the count.
- **The schema reaches a script as filled values**, like the link fields of P2: `SCHEMA_VALUES` is set on
  import from the vault's schema. Rejected: giving scripts the schema at run time (a new runner input for one
  pack) and reading labels from cards (labels are the schema's).

## 2026-11-01: Removing the coded Dashboard, implementation choices (P5, Claude Code)

- **Golden files before deletion.** Before removing `dashboard.py`/`market.py`/`coverage.py`, their answers on
  four fixtures were written to `tests/fixtures/bi_default_pack/golden/` (fixed clock, seeded ids, a rebuild
  compared equal) and the parity tests switched to them (owner instruction 2026-11-01). The files are frozen: a
  deliberate change of an analysis's answer edits its golden file in the same commit with the reason.
- **Every dataset draws analyses.** A dataset only on this PC (and a subscribed copy) draws the built-in pack
  through `board.py`, like a vault; only the quality section stays coded (it is a check, not an analysis). The
  chat on such a dataset runs the same pack analyses (`board.pack_sections`), so the page and the answer agree.
  A benchmark's chosen version of a vault also runs the built-in pack, as it ran the coded sections before
  (a vault's own analyses are read from its published version only).
- **The coverage panel goes; the analysis stays.** The page's matrix grid (cards per cell, a cell's card list,
  totals and unknown values) is removed with `/api/bi/coverage`; the `coverage` analysis carries the per-cell
  numbers. Rejected: keeping the panel on `coverage.py` (a second, coded way to answer the same question, which
  the design removes). A vault's `coverage` block at creation is no longer stored (nothing reads it).
- **Old names keep working in the chat.** `bi__query` maps a coded section name (`trend_coverage`) to its slug,
  so a Skill or a person using the old names is not refused.

## 2026-11-01: Removing the domain configuration, implementation choices (D4, owner answers, Claude Code)

The owner chose (2026-11-01) to move as much of the old configuration as possible automatically and to keep a
slim migration prompt on the page. What D3 did not move, and where it goes now:

- **Value aliases (`enum_aliases`) and the node name rule (`node_name_pattern`)** go into a new local schema
  version made from the dataset's current one (a draft, published, the dataset upgraded; in a vault the schema
  document goes with the commit, so other PCs get it). For the rule, a schema type gained an optional
  `name_pattern`, which the quality check `node_format` reads. Aliases pointing at a value the schema does not
  allow are listed, not moved. Rejected: a shipped schema change (the aliases are one team's vocabulary).
- **Node lists** (`domains[].nodes`, chain `nodes`): their only use was the warning `node_not_listed`. A Node
  card is the list now; listed names without a card are reported, never created, and the warning is gone.
  Rejected: a schema field holding the list (that is the configuration again).
- **Extraction notes** go into the vault's `<domain>-extract` skills (as saving did since R3) or, for a dataset
  only on this PC (no skills), into one `llm` ingest method whose instructions are the default ones plus the
  notes. Difference: a local dataset's AI run uses the notes only when that method is chosen, not on every run.
  Rejected: keeping notes in `meta` (the configuration again).
- **The migration entry point** is a prompt on the Dashboard shown only while a dataset still has an old
  configuration (`domains_left`), with the same preview and confirm as D3; local datasets are written directly.
  The old reader lives in `migrate.py` only. Rejected: migrating on open without a preview (D3's rule is
  preview, then the person confirms).

## 2026-11-01: Voice input for Telegram and Agent Web, owner answers (Voice Phase 1)

The owner answered the three questions the voice input design (`docs/phases/VOICE_INPUT.md`) left open:

- **Speech-to-text runs locally.** Audio is transcribed on the Host PC; no cloud STT API is used, so spoken
  company content never leaves the PC. Rejected: a cloud STT API (better accuracy and no local CPU cost, but the
  audio leaves the PC). The concrete local package and model are still to be approved by the owner before they
  are added as a dependency (new third-party package rule).
- **A voice instruction may start work directly.** Once the person sees the transcript, a voice request for
  coding, a knowledge question or a workflow starts like the same typed text would, with no extra
  voice-specific confirm step. Voice adds no confirmation and removes none: every confirmation or approval the
  text path already has (for example the owner's approval of a workflow run that changes something) still
  applies unchanged. Rejected: always asking the person to confirm the transcript before acting (safer against
  mis-transcription, but slower than typing for every request).
- **Only the transcript is kept.** The audio is deleted after transcription, including when transcription
  fails; the transcript is stored where the equivalent typed text would be. Rejected: keeping the audio (allows
  re-transcription and benchmarks, but stores recordings of people's voices) and deleting both (loses the record
  of what the person asked).

## 2026-11-01: Voice input, remaining design choices (Voice Phase 1, owner accepted the recommendations)

The owner accepted every recommendation in `docs/phases/VOICE_INPUT.md` §7.2:

- **STT package: `faster-whisper` with Whisper small int8**, large-v3-turbo as a configurable upgrade, in an
  optional `voice` extra so a host without voice installs nothing new. Rejected: `sherpa-onnx` + SenseVoice-Small
  (faster, but the model licence needs review and output is Simplified Chinese) and `pywhispercpp` (smaller,
  less active binding project).
- **A spoken reply never confirms an open card.** A spoken 「好」 does not approve an already shown confirmation
  card; the person taps the button. A spoken 「取消」 cancels (it only removes a side effect) and 「修改」 opens
  editing. This keeps an existing confirmation from being passed by a mis-transcription; it adds no new step.
  Rejected: treating spoken words like typed ones at a card, and ignoring voice entirely while a card is open.
- **A separate transcript record is kept** under `voice/transcripts/` for traceability, purged like task result
  summaries (default 30 days), besides the sent text in the conversation history. Rejected: conversation history
  only.
- **Telegram media:** `voice` messages always; `audio` files only within the same limits; `video_note` refused.
  Rejected: `voice` only.
- **Traditional Chinese output** through OpenCC `s2twp` (`opencc`, Apache-2.0) plus a Traditional initial prompt.
  Rejected: initial prompt only (less reliable).
- **Limits:** 180 s and 10 MB per message on both channels; the Agent Web recorder stops itself at the limit.
- **Test fixtures** are generated with Windows' built-in TTS voices and committed. Rejected: eSpeak NG (less
  natural) and generating fixtures at test time (not reproducible on CI).
- **Model delivery:** an owner-approved model package (files plus sha256 pinned in `host.json`) installed into
  the host data directory; the host never downloads a model by itself. Rejected: asking IT to allow Hugging Face
  URLs through the proxy.
- **Voice is off by default** and enabled per host by the owner (the Personal Agent PC running the Telegram
  ingress).
- **Fake Bot API test seam:** `api_base` stays HTTPS-only; tests redirect through an injected `Transport`.
  Rejected: allowing `http://127.0.0.1` in the production validator.

## 2026-11-01: BI: charts inline in the chat; Dashboards from the analysis AI or an Atlas import (owner, Claude Code)

Owner decisions relayed by the BI orchestrator; design in `docs/phases/BI_CHAT_CHARTS_AND_DASHBOARD_SOURCES.md`.

- **A chart in the general AI chat is a self-contained HTML file shown inline** in the existing chat file
  viewer (sandboxed iframe, `FILE_VIEW_CSP`, no network), drawn by the BI Dashboard tab's own renderer moved
  into one shared constant (`host_runtime/bi_chart_html.py`). Rejected: a link to Atlas opened in the agent
  browser (the agent browser is driven by the agent, not the person; Atlas has no deep link to a panel and
  answers with `X-Frame-Options: DENY`, so it cannot be framed); a third-party charting package (not without
  the owner's say; the existing DOM/SVG renderer covers table, bar, line and scatter).
- **The chart spec is the feed's** (`{type: table|bar|line|scatter, x?, y?, series?}`); a result without one
  gets a bar for exactly one label and one number column, else a table. Rejected: a richer chat-only spec.
- **Saving a chat chart as an analysis is a `propose_change` kind (`bi_analysis`), web only**: the AI
  proposes, the owner applies in Agent Web, the apply only stages `analysis:<slug>`; commit, push and publish
  stay manual. Rejected: a Bridge capability with `approval_required` (meant for capability runs, not for a
  change to this PC's state with a fingerprint); saving directly from the chat; allowing the apply from
  Telegram.
- **A vault's Dashboard comes from the analysis AI (several analyses plus an order, one apply) or from an
  Atlas dashboard import that takes only the order** (panels of this vault sorted by `layout.y`, `layout.x`;
  the first occurrence of each slug kept, later duplicates listed); `hidden` = the vault's analyses not in the
  order; unmatched panels are listed, never invented; a dry run is confirmed before anything is staged.
  Rejected: importing Atlas positions or sizes (Atlas layouts are personal,
  `BI_ANALYSIS_DASHBOARD.md` §8); importing panel parameters or titles; deleting analyses missing from the
  import (they are hidden).
- **The general chat gets no ad-hoc SQL tool.** Rejected for now: letting `bi__query` run model-written SQL
  (new charts are made in the analysis AI, or proposed through `bi_analysis` and run only on approval).
- **Addendum (owner, 2026-11-01): the general chat supports guarded read-only ad-hoc SQL** (C1b), reversing the
  bullet above. SQL only (never a script), through `bi__query` (same capability, `CapabilityInvocation`, grants
  and audit; read, no approval), on the published data `bi__query` already reads (never working or unpublished
  data), guarded by the existing `analyses.run_sql` (read-only copy, read-only authorizer, deadline), with the
  analyses' 10 s limit and a 200-row cap marked `truncated`, charted like C1; nothing is saved (saving is C3,
  with approval). Rejected: a second SQL guard; running on the working copy; scripts from the chat.

## 2026-11-02: Asking a vault from the general chat (owner goal, Claude Code)

Owner goal relayed by the BI orchestrator; design in `docs/phases/BI_VAULT_ASKING.md`. Choices inside it:

- **The host writes the citation for a vault's answer** (vault and version, one line, only when the answer does not
  already name them), as it already does for subscribed datasets. Rejected: relying on the model to repeat
  `scope_note`, since then a cited answer depends on the model.
- **Binding a wiki repository to the Agent is a `propose_change` kind, `knowledge_binding`, web only**; the page's
  button and the chat's model reach the same card, and the person's Apply is the approval. Apply writes the manifest
  first and then the binding, after a backup, and takes effect at the next restart. Rejected: a direct write from the
  button (no before/after, no stale check); registering into the running catalog (the query capability may not exist
  until a restart when the host started with no binding).
- **A second vault is allowed and is not reported as "not askable"**: the conversation's tool route offers every
  vault; the card and the page state what changes (the direct route, `/wiki-query`, `aep_knowledge_ask` staying on the
  first binding). Rejected: blocking a second binding.
- **A never-published vault keeps being answered from the pushed head**, marked as such (`KNOWLEDGE_REPO.md`
  decision 8). "Unpublished" here means local work and anything pushed after the published tag.
- **Whether `aep_knowledge_ask` covers BI is not decided**: the architecture does not answer it and it widens a data
  boundary the owner set on 2026-10-12. Options in the design §5; nothing implemented.
- **No V4 migration tool** (owner): `market-bi` is rebuilt from raw sources with the owner present (R6).

## 2026-11-02: External agents ask BI through a separate tool, `aep_bi_query` (owner, relayed by the BI orchestrator)

Answers V3 of `docs/phases/BI_VAULT_ASKING.md` (§5).

- **Option B: a new MCP tool `aep_bi_query`.** The owner widens the 2026-10-12 external-agent data boundary to BI cards
  for this tool. The widening applies only while the owner has it turned on: `host.json` `assistant_bi_query`, off by
  default, set in Settings > Coding agents. The assistant MCP had no per-tool switch; the orchestrator chose adding this
  one over gating only on the BI Skill and the grant (the boundary would widen at merge wherever BI chat works) and over
  a separate MCP server (a new endpoint and installer changes for all three coding agents). A stdio client still lists
  the tool while off and is refused on the call; forwarding `tools/list` is left out of this version.
  Rejected: leaving the assistant tools wiki-only (external agents could not ask BI); routing BI through
  `aep_knowledge_ask` (breaks what `validated` means, and adds a routing guess inside a tool).
- **Defaults (orchestrator):** published version only (pushed head, labelled, when never published); saved analyses and
  built-in queries only, no ad-hoc SQL over MCP in this version; the assistant-MCP token and grant pattern; the same
  host-written source line in the result.
- **Decision 8 stays (owner):** a never-published vault is answered from its pushed head, labelled.
- **Accepted (owner):** `propose_change` kind `knowledge_binding`, including unbind.

## 2026-11-02: The Atlas Dashboard import also takes a file (owner, relayed by the BI orchestrator)

The Knowledge page's Atlas import (K2) must also accept a dashboard file the person chooses, so it works without Atlas
running. Same contract and rules: dry run with a preview and token, confirm, only `meta:dashboard` staged, duplicates and
unmatched panels listed. Strict JSON, a size limit, never run or stored, the rest of the file ignored and never given to a
model. Reading from Atlas by name stays. Choice inside it: a confirm sends the text again rather than the server keeping
a copy between the two requests, so nothing is stored. Rejected: uploading to a temporary file on the server.

## 2026-11-02: A BI vault's originals go into the shared folder (owner, relayed by the BI orchestrator)

R6's D2, open since 2026-10-30. The originals go into the repository's `sources/` (`KNOWLEDGE_REPO.md` §11), so a colleague
who joins can read them. **Not built yet, and R6 waits for it**: today they stay in the local `staging.sqlite` of the PC
that added them, and `bi-build-flow`'s B2 copies them only into the new vault's local staging. Found in the scope reading,
for whoever builds it: the engine already carries files (`stage_file`, the commit's `files`, `_copy_in`, "waiting"; the
wiki type uses them); `_stored_sha` does not catch an `OSError` from reading a file, so an unreadable cloud-only file can
fail a sync; `/api/bi/sources` takes base64 under an 8 MiB body, about 6 MiB per file; evidence rows hold a `source_id` that
only means something on the PC that made it; a file deleted from the folder leaves its commit waiting for good. Still the
owner's: the per-file limit, whether `CONFIDENTIAL` and `RESTRICTED` sources may be pushed (BI vaults have no permission
control, owner 2026-10-29), and how a file pushed by mistake is removed.

D3 (how the five bases are merged) stays open: the owner is asked to confirm base by base, one commit per base.

## 2026-11-02: Owner's answers on a BI vault's originals (relayed by the BI orchestrator)

Design: `docs/phases/BI_SOURCES_IN_REPOSITORY.md`. Not built yet.

- **O1. The per-file limit is set after measuring the real sizes** (R6 pre-check: the total and the largest file). The work
  on files over about 6 MiB waits for that number.
- **O2. Every classification may be pushed, `CONFIDENTIAL` and `RESTRICTED` included; no push refusal by classification.**
  The owner's choice against the worker's recommendation to refuse both. The reason as given: the owner accepts that anyone
  with folder access can read every original permanently. Rejected: refusing them at push.
- **O3. A withdrawal record is built**, for a file pushed by mistake. It does not remove OneDrive's or SharePoint's own
  versions, copies outside AEP, or what commits already hold; the design §5 lists this, and its questions go to the owner.
  Rejected: rebuilding the vault as the only remedy.
- **O4. Every PC keeps all originals on the device; the page warns on cloud-only files; no lazy read.** Rejected: reading a
  file only when it is needed (more engine work, and a chat question could wait on a download).

## 2026-11-02: R6's decisions and the withdrawal questions (owner: "follow the recommendations", relayed by the BI orchestrator)

Runbook `docs/runbooks/R6_MARKET_BI.md`; design `docs/phases/BI_SOURCES_IN_REPOSITORY.md` §5.

- **D1. The new vault's id is `market-intel`.** Rejected: keeping `market-bi`, which needs removing the old local entry and
  data by hand first.
- **D3. Base by base through the page, one commit per base, conflicts settled in review.** Rejected: bringing back the
  2026-10-29 one-off merge script.
- **D4. Import `%LOCALAPPDATA%\AEP\rs-k-v1.0.3` as a test copy; do not bind it to the Agent until the owner has compared
  answers.**
- **D5. The first tag is `2026q4-r6`.**
- **Withdrawal Q1. Excerpts and values staying in immutable commits is accepted**; the page names rebuilding the vault
  without that file as the way to remove everything AEP can reach.
- **Withdrawal Q2. Candidates not yet written are removed at sync; run records stay with their excerpts blanked.**

Still open with the owner: Q3 (SharePoint's retention, from IT; the page states no period until one is known), the four base
paths, and the sizes for the per-file limit (O1).

## 2026-11-02: BI: the chat embeds Atlas; the AI edits existing panels; AEP never writes Atlas dashboards (owner, Claude Code)

Owner decisions relayed by the BI orchestrator; design in `docs/phases/BI_CHAT_EMBED_AND_PANEL_EDIT.md`. Amends
2026-11-01 "BI: charts inline in the chat; Dashboards from the analysis AI or an Atlas import"; that entry stands
as the record of its day.

- **A general AI chat embeds real Atlas panels or dashboards (iframe)**, and falls back to the AEP chart (C2 HTML)
  with a note when Atlas is not running. This reverses "not an Atlas link" for the case where Atlas answers; Atlas's
  new embed routes replace the 2026-11-01 obstacle (`X-Frame-Options: DENY`). Rejected: the C2 HTML only.
- **The AI may change an existing analysis's content directly**: data source, computation rules (SQL, or a guarded
  script where analyses allow it), parameters and display. On the Knowledge page a "dashboard" is a single panel, so
  no layout is involved. Changes are staged after the owner's approval in Agent Web; push and publish stay manual.
  This lifts C3's and K1's refusal of existing slugs for edits. Rejected: new analyses only.
- **AEP never writes Atlas dashboards**; Atlas layouts stay personal (unchanged).
- **Chat edits are a new `propose_change` kind, `bi_analysis_edit`, web only** (Claude Code): the fields that change,
  a Now/After card with the whole code, the working unit as the fingerprint. Rejected: a flag on `bi_analysis`.
- **A script proposed from the general chat runs only after Apply** (Claude Code, within the owner's decision): the
  chat reads untrusted text and `run_python` is not a boundary against a determined attacker, so the card shows the
  script unrun. Rejected: running it to fill the card (no approval before code runs); keeping scripts out of chat
  edits (the owner's decision covers scripts). C1b ("never a script") stands for ad-hoc queries and C3 for new
  analyses.
- **The analysis AI's edits are checked against a base digest** at apply: a change meanwhile is refused rather than
  overwritten, and a proposal on a saved slug is always shown as an edit. Rejected: last write wins (T3 until now).

## 2026-11-02: BI: how the chat frames Atlas (Claude Code, within the owner's decision; contract `0aff59f`)

Addendum to the same day's "BI: the chat embeds Atlas". Follows Atlas's `docs/AEP_EMBED_CONTRACT.md`.

- **`referrerpolicy="origin"` and `sandbox="allow-scripts allow-same-origin"`**, as the contract requires. Rejected:
  `no-referrer` (Atlas answers 403 on `localhost`) and the file viewer's `allow-scripts` alone (an opaque origin cannot
  load Atlas). The Referer carries only the origin, so Agent Web's token in its address does not reach Atlas (tested).
- **A separate tool, `bi__atlas_show`**, taking a slug or a name and never a URL. Rejected: a `bi__query` option (it
  would mix a Host-only effect into a capability's input, and Telegram and the benchmark's reading tool share that
  input).
- **Asked server-side on every render**, since a frame's load event cannot tell a refused frame from a loaded one and
  a stored answer can outlive Atlas. Rejected: asking once when the tool runs.
- **The page frames loopback addresses only, and never its own origin.** Rejected: any address the preference holds
  (a same-origin frame with these sandbox flags could remove its sandbox).

## 2026-11-02: The BI build flow, end to end (owner goal; implementation choices, Claude Code)

Owner goal relayed by the BI orchestrator; design in `docs/phases/BI_BUILD_FLOW.md`. Owner decisions: real models
are allowed for the final live acceptance, only in a temp workspace with its own Agent Web; "sources on one PC" stays
an open R6 question and is not changed here. The choices below are the implementer's:

- **Converting a dataset to a vault copies its sources** (files, Markdown revisions, classification) into the vault's
  local staging on this PC. Without it, upload → Markdown → convert leaves steps 2 and 3 with nothing to read. Nothing
  reaches the shared folder, so R6 stays open. Rejected: asking the person to upload again; moving the sources (the
  dataset must stay as it was); copying runs and sessions (they refer to the dataset's own cards and drafts).
- **Session A moves to the harness as T2 and T3 did, read-only.** Rejected: more context in the one model call (it
  still could not try its draft). The one-call path stays where no harness exists.
- **`bi_skill__benchmark` compares the working copy with a scratch copy holding the draft's trial candidates**,
  because a draft skill changes only what is extracted next. The scratch copy is deleted after the call, and the result
  goes to the model only: it never satisfies the push check. Rejected: running T1 unchanged (the working cards do not
  depend on the draft, so it would show no effect); saving a T1 report (it could unlock a push on a run that did not
  test the pushed units).
- **Benchmark questions from AI are a session kind `questions`, applied per ticked question**, and a `must` term that
  no working card or saved analysis result contains is refused back to the model. Rejected: staging on proposal
  (nothing changes before the person applies); allowing unsupported terms (a question nothing can pass).

## 2026-11-02 — The owner's own Telegram conversations are stored and readable in Agent Web

Owner decisions of 2026-11-02, relayed by the BI orchestrator. Design: `docs/phases/TELEGRAM_HISTORY.md`. This amends
the position recorded in the entry of 2026-10-25 "A session remembers what it produced", where Telegram chat history
was memory only. That history is still what the model receives; the stored record is a separate copy for reading.

- **Stored:** the owner's own Telegram conversations, durably, from now on, with no backfill. The owner is the sender
  whose mapped actor equals the Host's actor (`device.registered_by`). Messages from other allowed senders are not
  stored.
- **`/new` only starts a new conversation.** It does not delete stored records, and for the owner it no longer deletes
  the chat's attached files, because the records list them. This amends the entry of 2026-10-08 ("`/new` clears that
  history and deletes those files") for the owner's chat only; other senders' `/new` is unchanged.
- **Delete happens in Agent Web**, the same way a conversation is deleted today, and it reaches attachments: the files
  the record lists are removed, as Agent Web's delete removes a conversation's files.
- **Read-only in Agent Web:** a Telegram conversation cannot be continued there, and `/api/conversations/turn` and the
  other changing routes refuse it with `conversation_read_only`.
- **The model does not change:** the in-memory cap of 12 stays and nothing is reloaded after a restart.
- **Roll-over, not loss:** a new record per local day, at the 100-message cap and on `/new`, so nothing is silently
  dropped.
- **Stored records feed nothing else in this version.** Agent Web chats feed experience cases, skill suggestions,
  preference last-use and the memory overview. Telegram records are left out of all four by the default of
  `LocalState.conversations`, and rating is refused, so none reaches the feedback upload.
- **Rejected:** reloading stored messages into the model (changes its behaviour); dropping old messages at the cap as
  Agent Web does (silent loss in a long-lived chat); SQLite FTS for search (needs a migration and a tokenizer that
  handles Chinese, where `LIKE` matches any substring); `chat_hash` as the id (its salt is per process); a plain hash
  of the chat id (few enough ids to try them all), so the id uses a per-host random key.
## 2026-11-03: A BI vault's originals: no size limit, and access is IT's (owner, relayed by the BI orchestrator)

Replaces O1 and narrows O2 of 2026-11-02; design `docs/phases/BI_SOURCES_IN_REPOSITORY.md`.

- **No per-file or total size limit.** The size check and `meta:source_max_bytes` are removed. Files larger than the base64
  upload can still be added: a raw-body upload route, written to disk as it arrives (worker's choice). Rejected: a local-path
  route (a new way to name files on this PC, and the person would type a path instead of picking a file); raising the JSON
  limit (still holds the whole file in memory, twice with base64).
- **Access principle, in the owner's words: don't add file permission controls in AEP. Company IT decides through
  SharePoint permissions; whoever has access can open files. Keep things simple.** So no classification gates and no new
  access checks. The existing check before an AI run stays: it is about what a model may be sent.
- **Q3.** The owner says files stay available as long as permission exists. That does not say how long deleted files are kept,
  so the withdrawal page states no period.

## 2026-11-03: R6's sources (owner, relayed by the BI orchestrator)

The five bases are `files\Aerospace-BI-KB`, `files\BI_Vault_Example`, `files\Wireless-Module-BI-KB-SAMPLE`, `files\aidc-bi-kb` and
`files\robotics_kb_sample` under the AEP main checkout (git-ignored, never committed), plus the two AIDC reports
`aidc-compute.md` and `aidc-power_cooling.md` in the old `market-bi\applications`, read only, copied out, never moved. The
`rs-k` copy is `%LOCALAPPDATA%\AEP\rs-k-v1.0.3`; the wiki target is `OneDrive - Rohde & Schwarz\Wiki_Knowledge`. The old `market-bi`
folder itself holds only those two reports and 52 change files, not the bases. The per-base list of what goes in is in the
runbook §3, for the owner to review at the session.

## 2026-11-03: The card-page importer, and samples (owner, relayed by the BI orchestrator)

Design `docs/phases/BI_CARD_PAGE_IMPORT.md`.

- **A built-in importer for Obsidian card pages**: frontmatter maps to schema fields as a CSV's columns do; no model; the same preview,
  apply and commit path. The page is the evidence, and unknown fields and invalid values are listed, never invented or dropped silently.
  Rejected: AI extraction over the pages (it re-reads structured data, with cost and guesses); a by-hand export to CSV outside AEP. Choices
  inside it: a strict small frontmatter reader rather than a YAML dependency; a `.csv` in the same request reads as CSV import does, so
  `tools/samples` takes the same path; one `commit_run` for a whole request, so a base makes one commit of cards.
- **`SAMPLE-` pages and `BI_Vault_Example/tools/samples` are imported and marked, not left out.** The mark is the existing card field
  `synthetic`. The host writes a line under an answer with samples in it, so it does not rest on the model. The default pack still drops
  only `SAMPLE-` names, so a marked card without that name counts in a built-in analysis, and the line says it may. Rejected: a new field;
  the default pack dropping every marked card (all demo cards are marked and `FICTIONAL` matches 「待查證」, so it empties the Dashboard: 90 of
  robotics' 104 seed cards would vanish).
- **Accepted as stated (owner):** S6's raw-body upload, with the converter still reading a file whole once; withdrawal has no undo;
  withdrawal does not clear AI session conversations; `check_classification` before an AI run stays, because it governs what a model
  may be sent, not file access.

## 2026-11-03: Sample names and the R6 import order (owner, relayed by the BI orchestrator)

- **Rows ticked as samples get the `SAMPLE-` name on import**, never twice, so the default pack leaves them out unless `include_sample`. A link from
  one such row to another follows the rename; one that cannot resolve is listed in the preview. Rejected: narrowing what `FICTIONAL` marks; leaving them
  out of analyses by another rule.
- **R6's order:** AIDC and aerospace, seeds then pages, with same-named cards merging and conflicts settled in review; robotics, pages only (100
  cards), its seed CSVs not imported; wireless module and wireless example, pages, and the example's 3 sample CSVs ticked.

- **The card-page import merges** (orchestrator, carrying out D3, 2026-11-03). A combined dry run had found that an import overwrites every value not set by a
  person: 49 scalars overwritten and 42 lists losing items. In this path, seed CSVs included: an empty value is filled, lists are joined, a differing scalar becomes
  a proposal, and a derived field (`updated`) raises none. A card keeps its sample mark; a row marked differently only proposes. Rejected: the same rule for every
  import (changes the existing CSV and run paths); keeping the overwrite. The combined run then gave 641 cards and 31 proposals, runbook §3.
- **Q3 is closed** (owner): the page states no retention period.

## 2026-11-03: A list of domains on three more types: schema 4.0.0 (owner, relayed by the BI orchestrator)

`Application.domain`, `Trend.domain` and `CustomerProduct.domain` become lists in a new shipped schema, so a card can belong to several domains. Before R6.

- **4.0.0**, not 3.1.0: a Session A version made from 3.0.0 is 3.1.0 (as decision 2026-11-01, D1). A bare `bi.schema/v1.1` now means 4.0.0 for new datasets and vaults.
- **The allowed values stay**, so the default pack's `values_from: Application.domain` does not move. **The default `wireless` goes**, as on `Node.domain` since 2.0.0: readers already
  take a missing domain as wireless. Rejected: dropping the allowed values as `Node.domain` did (the pack's parameter would then read the schema's domains, and a mistyped value would go in).
- **Existing data:** an enum becoming a list is a listed widening, so a dataset or vault upgrades through the existing upgrade path, by a person, each value a one-item list. Nothing upgrades by itself.
- **Feed goldens and Atlas are untouched:** the goldens are pinned to `bi.schema/v1.1@2.0.0`; `test_bi_feed_fixtures` still rebuilds them byte for byte.
- **What the combined dry run showed:** the 12 `domain` proposals were not cards in two domains. Those seeds name no domain, so the old default met the page's value. They are now fills. So the
  default was the cause, more than the shape.

## 2026-11-03 — BI works on a host with a model and no wiki Knowledge asset

Owner, 2026-11-03: anyone with access to a vault can use it, and not everyone binds a wiki knowledge base.

- **Decision:** when no Knowledge query handler is installed, BI takes the host's routing client and alias
  (`gateway.router.model`, `model_alias`) in `web_ai_runtime`. AI ingest, retry, Session A and B, the skill assistant and
  bench extraction all follow, and `/api/bi/ai` opens the page's gates. Where a handler is installed it is still used, so
  nothing changes on a host that binds a wiki asset.
- **Approval:** the fallback accepts only an `ApprovedModelClient`, the wrapper `build_router` makes with
  `binding.data_approval`; an unwrapped client gives `model_unavailable`. `check_classification` is unchanged.
- **Rejected:** building a second client for BI from `ModelClients` (a second place that must remember the wrapper);
  binding an empty Knowledge asset on install (it would turn on Knowledge features with nothing behind them).

## 2026-11-03 — New installs approve INTERNAL for the model by default (owner, directly)

- **Decision:** `deploy/windows-preview/gateway-default.json` approves `UNCLASSIFIED` and `INTERNAL`, so internal data is sent
  to the model service by default on a new install. The owner confirmed this directly and does not want it asked again;
  they will raise any change themselves.
- **Why:** sources default to `INTERNAL`, so a new install refused AI ingest with `classification_not_approved` until someone
  found the setting. The owner wants a colleague's install to work after setup.
- **Scope:** new installs only. `install.ps1` merges the file's `models` only when `host.json` has none, and `update.ps1` runs
  `install.ps1`, so an existing host keeps its approval. `CONFIDENTIAL` and `RESTRICTED` stay unapproved, and
  `check_classification` still refuses them.
- **Rejected:** keeping `UNCLASSIFIED` with a page explaining where to add `INTERNAL` (every colleague would have to find it).

## 2026-11-03: The BI card model (owner, relayed by the BI orchestrator)

Design: `docs/phases/BI_CARD_MODEL.md`; source: `docs/proposals/AEP_BI_Card_Database_Proposal.md` v1.2, which the owner's decisions override where they differ. Phase 1 before R6.

**The owner's decisions:** a card id is the hash at first creation and never changes; a rename op keeps it and makes the old name an alias; links are stored by id. Commit units stay the truth and `bi.sqlite` a rebuilt per-PC index; `cards` and `fields` keep their shape and the Atlas feed contract does not change. Relations and their evidence are units, except that those derived from link fields are rebuilt and default to unreviewed; only AI-inferred ones need per-item review. All card changes go through ingest: re-run a skill revision over a scope and confirm only differing values, or add a correction note as a source; the direct field-edit route is retired. Card Markdown is generated, read-only and never read back. New folder layout with per-application sources, skills, tools and an immutable profile; definitions live only in the merged schema. Per-card summaries and per-category explanations; missing-value states; references with `stance` and `reference_id`. No new permissions.

**Decided in the design, for the owner to overrule:**

- **Card Markdown is written at publish, by the publishing PC, into `cards/`, changed files only.** Rejected: at every push (shows unpublished content, and every author overwrites the same files, so OneDrive conflict copies become routine); per-tag folders (strictly only-add, but about 640 more files per tag, and Obsidian shows every old card). Cost: `cards/` is the one exception to only-add, safe because nothing reads it back, and the next publish repairs it.
- **A link stored by id renders the target's current name; a link stored as text renders as written,** even when it resolves through an alias. Rejected: rendering resolved text under the canonical name, which would change feed goldens and old analyses.
- **A former name stays reserved.** A new card with it hashes to the same id, so it is that card. Rejected: a salted id, since two PCs would disagree.
- **A card's applications are derived from its evidence's source paths,** so no unit and no conflict. A card with none never gets a computed `not_applicable`.
- **`published/<tag>.sqlite` is only written in Phase 1;** readers keep rebuilding from units. It narrows `BI_VAULT.md`'s no-SQLite rule, which was about files several PCs write.
- **The direct route goes; `store.set_field` stays internal,** for proposal accept and the domain migration. A correction note writes kind `human`, so a person can still make a card `trusted`, now with evidence.
- **The generated classify skill goes in `library/skills/`,** since it spans applications and the layout had no home for it.

## 2026-11-04: Application folders are per market (owner, relayed by the BI orchestrator)

`aidc`, `aerospace`, `robotics`, `wireless`; the 11 segments stay as `segment` values on cards. The list stays data, per vault. Rejected: the 11 segments as folders, since none of the 434 card pages names one, so R6 would have sorted them by hand.

Library entries have an application's shape (owner, 2026-11-04): `library/<products|technologies|competitors>/{sources/, skills/, tools/, profile/}`, the list data too. `classify` stays at `library/skills/`, so `skills` cannot be an entry name. Unit keys use `library/<entry>`, so an application of the same name cannot collide.

## 2026-11-04: `not_applicable` only when stated, never derived from a profile

**Owner decision.** A field a profile omits is unknown. It is `not_applicable` only when a profile lists it (`not_applicable: [field]`, with an optional reason) or a correction note states it. `used_fields` stays for what the AI is asked. **Why:** a profile says what one expert asks for, not what cannot apply: derivation marked 181 fields on market-intel, and earlier 2,066, as 不適用 where the truth was 未知, which the model would then state as fact. `MODEL_VERSION` rises to 8, so existing vaults rebuild with no commit changed. **Rejected:** deriving only for types the profile lists (the previous rule, still wrong on what an expert merely left out).

## 2026-11-04: A model's supply link matches by its two ends; identical requests repeat (owner, relayed by the BI orchestrator)

Measured in `docs/phases/BI_EXTRACTION_VARIANCE.md`: gpt-5.5 gives different cards from identical bytes, with no way to fix it (`temperature` must be 1; a seed does not make it repeat).

- **`SupplyLink` from a model matches an existing card by supplier and customer,** not by the product phrase in its name. A seed keeps its key, so no schema or key change. A differing product is a proposal. Several cards on a pair, or several candidates of a run for one pair, are for a person; nothing merges silently. Consequence: two real products of one pair need a person's explicit 「留這一張」 or new card. Rejected: a `RevenueFact` key from company, period and layer, which made a chunk less stable because the model's `period` varies.
- **An identical request reuses its answer,** per PC, with `fresh` to ask anyway. Consequence: a re-run repeats until the prompt changes, including a mistake it made; and it does not make a first run complete. The key holds the model's alias, not the endpoint's model, so changing what an alias points at needs `fresh`.
- **A card with no domain takes its application's, marked inference,** on imports and through `fill-domains`. A library folder gives none. Mixed `domain` storage is the schema's: `enum` on 5 types, `list` on 16. Not a bug.
- **Rejected for now: sending only the known names a chunk mentions.** It steadied supply links on one chunk but halved revenue facts there and made same-named `Account` cards.
## 2026-11-04 — `bi__query` walks relations and returns passages (BI card model Phase 3-a)

From the BI orchestrator's brief for Phase 3-a; design `docs/phases/BI_CARD_MODEL.md` §3.3.

- **A relation's status decides how it may be said.** `claim` in the result: `fact` only for `confirmed` or a link a card's
  field holds; a path is as sure as its weakest step. The rule travels in `scope_note`, not only in the Skill, because a
  host may hold an older Skill text.
- **Passages obey the data approval.** A source's text reaches a model only in an approved class, as
  `check_classification` requires for AI runs. The brief added no ACL; this is that existing rule on a new way to reach the
  text, not a new permission. Withheld chunks are counted, so a gap is not read as absence. Rejected: returning all
  passages (a RESTRICTED source would go to the model through a search).
- **Passages follow the version the answer reads.** A vault answers from its published version, so its passages come only
  from the sources in that commit. Rejected: the dataset's own index, which holds this PC's unpushed sources.
- **Card search stays a substring scan.** Only passages use the index; changing card matching (all words, ranking) would
  change existing answers days before a release.
- **Not done:** reading `published/<tag>.sqlite`, on the Phase 3 list; not in this brief, and readers keep rebuilding from units.
## 2026-11-04: A card's evidence review is stored on the evidence row

Phase 2-c needs a person's judgement of a reference on a card, and `BI_CARD_MODEL.md` §3 only has `assessment` on `relation_evidence`. **Decision:** `evidence` gains one optional `assessment` column, and an `evidence:` row may hold the key; old rows stay valid and `MODEL_VERSION` rises to 6. The review travels as a note on the correction path. **Rejected:** a new `review:` unit (proposal §5 asks not to add tables and units for this, and the row is where the judgement belongs); pseudo-relations in `relation_evidence` for a card's field (would show up as relations).
## 2026-11-04: A BI tool's output is a new source

**Decision.** A home's tool (P2-a) writes CSV or Markdown, kept as new sources in the raw source's folder with its classification and `derived_from`. Withdrawing the raw source withdraws them. The AI of a skill session may draft a tool and try an approved draft; only a person approves code, per revision and PC by its hash, and saves a revision.

**Why.** The owner's rule is that output reaches cards only through preview and review, and the source path already gives that, along with evidence, sharing, classification checks and withdrawal.

**Rejected.** Writing the output as a Markdown revision of the raw source: it fits no CSV, and it would replace what the source's own converter or a person wrote. Letting the AI run its own draft unapproved, as analyses do: the owner asked for approval before a new revision's first run, and a tool reads raw sources. The guard is not a boundary against a determined attacker, so the code must be read first.
## 2026-11-04: Schema fit is kept on the AI run (Phase 2-b)

Each item's action and a person's decision on it are kept with the run, per PC, as candidates are. The proposal's §8.1 F allows it and no new table is needed. Consequence: another PC does not see a pending item until it reaches a profile proposal or a schema version. Approved `dictionary_change` and `propose_type` register nothing; a person takes them to Session A, since the existing proposal flow only adds fields. Rejected for now: fit units shared in the vault, and auto-drafting a schema version from an approval.

## 2026-11-04: Schema fit stays in, at about 40-50% more output tokens

On the two densest chunks of `compute.md`, three runs each, real model, 32,000 output limit. Without asking for items, output means were 16,275 and 12,877 (highest 18,151); with items 22,439 and 19,056 (highest 23,370, 73% of the limit, no truncation). Input and output together rose 20-22%. So it neither reaches the limit nor doubles the cost, the orchestrator's two conditions for leaving it out. Three runs per arm is few: run-to-run spread in an arm is up to about 6,800 tokens.

121 items: no `propose_type`, `extend_schema` or `dictionary_change`. 44 are `needs_clarification`, 41 of them added by the check rather than said by the model, which is review work a person will meet; not tuned here. Rejected: leaving Phase 2-b out of the release, and a per-run switch, which nobody asked for.

## 2026-11-04: Schema fit is a per-run tick, default off (orchestrator)

Measured always on, a dense chunk gave about 7 questions, 36% of its items `needs_clarification`, 41 of 44 added by the check. Too much review for colleagues on Friday. A run asks only with `check_fit: true`, from a tick in the run form, in a vault; it is stored on the run, so a resumed run keeps it. Off, the prompt is as before Phase 2-b, so kept answers are still reused. Rejected: leaving Phase 2-b out, since the owner can still use it, and tuning the check before the release.

## 2026-11-04: `bi__query` text is words, with the nearest cards when none holds them all

`text` was one string in one field, so every question-like query came back empty: 60 of 60 first queries on two real questions. The model then retried with fewer words, or went to SQL, and once gave a neighbouring card's figure; two bench turns said "no data" outright. After: 60 of 60 first queries held the answer, 1 tool call against 3.03, half the time, 60 of 60 passed against 59. Question words such as 營收 are on no card, so requiring all of them still returns nothing: hence the nearest cards, at least two words held, with a note that they may not be the answer. Only in `bi__query`; the page's card list stays strict. Rejected: telling the model to use short words only, which leaves the empty first query, and search over the FTS index, which holds source text and not card fields.

## 2026-11-04: Long paths take Windows' long form only when they need it

A wiki repository keeps people's file names, and `work/files` and the reading view sit under a long workspace path. `LongPathsEnabled` needs an admin and colleagues' PCs will not have it. Paths of 240 characters or more use `\\?\`; shorter ones are unchanged, so nothing else sees a new form, except the Agent's reading view, which is always in the long form so its pages are not silently unseen. Rejected: shortening file names, since pages cite `raw/<name>`, and moving the workspace.

## 2026-11-05 — Chat's Atlas: a kept copy of a dashboard's panels, and the port with the turn

From worker V's acceptance, relayed by the BI orchestrator.

- **A per-PC copy of a dashboard's AEP panels** (vault, slug, params, read time), so a stopped Atlas can still draw charts for a dashboard asked about for the first time in a conversation. The answer says it is the last read and that Atlas decides the layout. No copy: the explanation, nothing guessed. Rejected: keeping the whole document (AEP draws no layout from it, and a copy of Atlas's data would drift).
- **The port comes with the turn**, not a host setting. The page already holds the address per browser and frames Atlas with it, so one person's chat and frame always agree, with no new setting to keep in step. Only a port travels, so the host can reach nothing but `127.0.0.1`. A non-loopback address sends none, and the default port stands. Rejected: a host-level setting (a second place for the same address; two browsers could disagree with it).
- **A dashboard's result says what the answer holds**: framed or not, charts drawn, panels not shown and why, so the model cannot say 「已在這裡顯示」 for a board it could not read.

## 2026-11-05 — The BI Knowledge page is redesigned to be simple, and this outranks the 11-05 date

Owner, 2026-11-05, relayed by the BI orchestrator, after trying the page and finding it too hard to use. Design and slices: `docs/phases/BI_PAGE_SIMPLE.md`.

- **The rule, verbatim:** 「ui請以簡單為主，善用table，menu/comobox」.
- **The whole redesign is done before release, even if the date slips.** It outranks the release date of 2026-11-05 21:00. Scope is not cut to meet a date.
- **The main path is only the owner's flow:** step 1 input and convert; step 2 schema and ingest; step 3 testing. The top section and step 1's knowledge base block are duplicates and go away as separate blocks.
- **Moved, not deleted:** what the flow does not name stays reachable under 進階. No backend route is removed. Create and join a vault, tool approval, proposals, correction notes, evidence review, push, tag and publish stay reachable, because the Agent and colleagues read only published versions.
- **A subscribed copy keeps a way in and a way out.** The select moves into step 1, so the build tab can no longer be hidden for a read-only dataset, or someone on a subscribed copy could not choose another. Rejected: a second select for reading (a mirror again).
- **The bench gate is not weakened by a simpler share step.** It stays in `repo.push`. A push with no test run is allowed today and stays allowed with its note, unless the owner changes that.

## 2026-11-05 — The BI page redesign: three answers from the owner

Owner, through the BI orchestrator, on `docs/phases/BI_PAGE_SIMPLE.md` §7. All three as recommended.

- **`kn-pane-pipeline` is out of scope.** The Knowledge page opens on the BI tab when this PC has a BI dataset or vault.
- **One-step share:** the page proposes a date as the tag name, and it stays editable.
- **A push with no test run stays allowed,** with a visible note. The bench gate still blocks a push when a finished run on the same content regressed.

## 2026-11-05 — BI page: a filter is always in sight, and a list opens beside itself

Owner's bugs, relayed by the BI orchestrator: no Signal card could be found though 23 exist; 「按"看/改"沒反應」; a card's abstract could not be found.

- **The card list starts on every domain.** It filtered by a domain nobody chose, defaulting to robotics, and S1 had moved that control under 進階, so market-intel showed 99 of 760 cards. A 領域 combobox now sits beside 類型 and 搜尋, with 全部領域 by default, and the count says how many of how many.
- **The Dashboard keeps one domain.** Its analyses take a single `domain`, and an empty one means robotics in the route, so 全部 would claim something it does not do. The combobox and 含 SAMPLE sit on the Dashboard tab, in sight. Rejected: a 全部 option there.
- **A list and what it opens sit side by side at one height, each scrolling on its own** (`.bi-split`): cards and their detail, sources and their Markdown. 看／改 was out of view below a long table, and a failed load was reported at the top of the page. Both now show in the pane. Stacked on a phone, the page goes to the pane.
- **The sources table follows the 領域 chosen,** which also keeps deciding the folder a new file goes to. 「不指定資料夾」 shows every source.
- **摘要, 用途, 範圍 come first on a card.** With no summary it says 「沒有摘要」; nothing stands in for it.


## 2026-11-05: Empty reading fields are filled by a run over each card's own text

The owner's rules: through ingest, only the card's own source text, fill only, reviewed. A run of its own, one call per card, whose candidates go through the existing review, merge and commit. Headings and evidence notes reach the model, since removing them made a card's unconfirmed supply link read as fact. Quotes are checked word for word in code. Rejected: another AI ingest of each page, whose full extraction would raise proposals on fields nobody asked about; and page import calling a model, which is what keeps it free and predictable. `scope` waits for the owner: a third of its values were true but no scope.


## 2026-11-05: Agent Web records write requests, without what they say

Four uncommitted changes appeared on the real `market-intel` on 2026-11-04 at 21:25 and nobody could be found: Agent Web logged no requests, by design, since a request carries the team's own words. The owner said yes to a record of writes only: time, method, path without query, status, `User-Agent`, `Referer` without query, the client's address, and an `X-AEP-Client` label. Rejected: bodies or query strings, which would undo why `log_message` is silent; reads, which are many and change nothing; a label as identity, since any process with the token can send any label. It is a queue and one thread, so a slow or unwritable log costs a line and never a request. It cannot answer who: it can answer which client said what, and when.

## 2026-11-05: The BI page has a working domain, and it is a home

The owner: 「我們要支援多人開發一個vault，所以這個頁面不是應該要選擇要編輯的domain，例如aidc，之後的修改，就依選擇的domain來做後續的ingest和testing」. Design: `docs/phases/BI_PAGE_SIMPLE.md` §9.

- **The working domain is a home (`aidc`, `library/products`), per person and per PC,** in one combobox above the stepper. A home with a schema domain of its name also sets the Dashboard's domain, by the existing `homes.domain_of_folder`. Rejected: choosing a schema domain, because `mobile` has no folder and a library entry has no domain, and a domain owns no sources or skills.
- **A person can look with no domain and cannot add with none.** 全部領域 replaces 「不指定資料夾」 and is the first-visit default. Rejected: defaulting to a domain, which could put a file in the wrong folder; removing the no-domain view, which is how a whole-vault bench and old root sources stay reachable.
- **A question gets an optional `home`; absent means the whole vault.** A working domain runs its own questions and the untagged ones. Rejected: using the question set's name as the domain, since a set name cannot hold `library/products` and a set is the team's own grouping.
- **The bench gate takes each question's newest verdict across every finished run on the same content.** Reading only the newest run would let a domain's run hide another domain's regression. A person in one domain is still blocked by a regression in another, and the page shows it before they press push, because the push carries the whole vault. Rejected: a gate per domain, which would weaken it.
- **Commit and push stay whole-vault.** The page says which homes a commit touches. Rejected: committing part of the changes by domain, which changes the repository model. The owner has not asked for that, and it is what publishing or blocking domains separately would need.

## 2026-11-05 — A start waits out a busy state file, and a second click joins the start under way

The owner's click after a reboot ended in 「Agent Web stopped while starting (exit code 2)」, `state_unavailable`; the next start worked. Orchestrator's brief, same day.

**What was found.** `SqliteLocalState` opens with `timeout=0` and takes `BEGIN IMMEDIATE` on every open, so any other connection holding the file is an immediate refusal, reported the same as a broken file. A held lock reproduces it in about 20 ms. The first start's log was last written at 14:58:57, 155 s after it began, while a second `web` started at 14:57:48 was printing its address at 14:59:00, so both were opening at about the same time: `open` starts another server if none answers yet. That is the likely holder, not a proven one: the log kept no more. `mcp` and `assistant-mcp` are ruled out: they return before `build_runtime` and never open this file.

**Decided.**
- `timeout=0` stays. It is deliberate (`031e7627`, "a second writer is refused rather than waited for"), and a running host's writes keep that answer.
- Only opening at start waits: up to 30 s for a busy file (`LocalStateBusy`, still code `unavailable` to everyone else), then `state_busy`. A broken file or another device's fails at once. Rejected: a global busy timeout, which would make every write of a running host able to stall.
- A second `open` joins a start under way (`agent-web-start.json`) rather than starting another server. Two servers starting together would otherwise now both pass the state file and meet on the port.
- The page stops promising 10–30 s: measured here 72 s and more than 155 s on a loaded PC after a reboot. Its wait goes from 180 s to 300 s, which amends the 2026-10-16 decision, since 155 s plus the 30 s wait would pass 180 s.


## 2026-11-05: Accepting a proposal moves the citations with the value

The owner's decision: a card's value and its citations must match. Before, accepting a proposal left the replaced value's citation on the field and on the card page's 參考來源, and dropped the proposal's own, so a card could cite text it no longer held.

**Decided.** On accepting, the proposal's evidence becomes the field's, and the field's evidence goes to that change's history row, `old_evidence`, readable with the old value on the card's 歷史. A proposal with no evidence leaves the field with none, and the page says so before the press. Rejecting changes nothing.

**Carried by units, so another PC rebuilds the same.** The `evidence:` unit is replaced, or gone when there is none; the field unit's `history` gains `old_evidence`, a list, `[]` when nothing moved. `MODEL_VERSION` goes to 10: a local `bi.sqlite` rebuilds once, since a PC on older code built commits from a newer one without the column. Old commits have no such key and read as before; so do pending proposals.

**Other writes, by the same rule.** Bulk accept: as one by one. A correction note: it broke the rule, adding its evidence beside the replaced value's, so it now replaces, and undoing the note restores the old evidence. A rename and the migration in `migrate.py` are unchanged: a rename's citation says where the card came from, and the migration only adds to `aliases` and `chain`. A push conflict: choosing a field's side also chooses its evidence's, since they are separate units; a person can still choose otherwise on the evidence's own row.

**A card keeps its home.** `card_app_folders` also counts `old_evidence`'s sources: replacing a value does not move a card out of a home.

**Known limits.**
- A push conflict where only the field conflicts, because the other side changed it without touching evidence (a rename's name field, a migration): choosing theirs still pushes my evidence unit.
- Evidence review works on the field's current evidence: a moved row's reviews stay readable in `old_evidence`, and it cannot be reviewed further.

**Rejected.** Keeping both on the field with a mark on the old one: every reader of `evidence` (the card page, the review, the chat) would need to learn the mark, and a miss cites text the card no longer holds. Deriving old evidence from the commit's `evidence:` change: it ties history to which commit touched which unit, where the field's own `history` already travels.

- **Commit and push stay whole-vault for now.** The page says which homes a commit touches. Rejected: committing part of the changes by domain, which changes the repository model. The owner has not asked for that, and it is what publishing or blocking domains separately would need.

## 2026-11-05: A person can create a BI domain, with no schema version

The owner: 「需要讓使用者可以create domain」, 「新增domain時，需要可以按照規則生成相對應的檔案folder結構」. Design: `docs/phases/BI_PAGE_SIMPLE.md` §10.

- **A created home is one unit, `meta:home:<id>`, and its domain widens the vault's schema when read.** Cards of it can carry the domain, and no skill turns 需要更新. Rejected: a new schema version per domain, since a draft, a publish and 需要更新 on every edited skill would disturb everyone for one person's folder; a home with no card domain, whose cards would silently lose it; appending to `meta:vault_segments`, where two people adding different homes would conflict.
- **The folders come from the unit, with no placeholder file.** Each PC makes them on push and sync through the one definition, `homes.HOME_FOLDERS`. Rejected: a placeholder, which would need excluding everywhere sources, skills and tools are listed.
- **The list of homes is built from units only.** An empty folder makes no home, so `library/skill-review` stays out. Accepted cost: a PC on an older AEP drops a created domain from its cards, with the existing warning.

## 2026-11-05: A repository's status keeps its scan of the commit files

The BI build tab took 14-17 s to show its source table on `market-intel`, and most of that was `Repository.scan` reading and checking 46 commit files, twice per status. `status` and `history` now use a scan kept while `_commits_stamp` is unchanged, the same names, sizes and times a sync already trusts to say nothing arrived. This is in the engine, so wiki repositories get it too.

- **Only for what reads and hands nothing on.** `state_at`, `log` and `sync` still read the files, because a caller may change the values they return, and a kept scan must not be what it changes. Rejected: keeping every scan, with a deep copy per call, which costs about what it saves.
- **A scan with a bad or half-arrived file is not kept,** since its next read may differ with the stamp unchanged.
- **One scan per folder stays in memory** in Agent Web, tens of MB on a large repository (estimated, not measured). Accepted.

## 2026-11-05: A run's commit that replaces a value follows the same rule

The owner, through the orchestrator: a rules run, or 改用新值 in review, that replaces a value replaces its citations, and the old go to history with the old value. **Only for a replaced value:** where a value stays and another source adds to it, evidence appends, as for one card reached from two domains. A list that only grows counts as staying (`store._only_adds`).

**Undo.** A replaced value comes back with what it rested on. New here: undoing a run also takes what that run cited on fields it filled or only added to, which it left behind before, except on a field changed since. A row is the run's by `run_id` and the import's time, so an earlier accepted proposal from the same run stays.

**A conflict proposal** now carries the lost value's evidence, from its commit (`vault.materialize`), derived at each rebuild and not a unit.

**Known, not changed.** A candidate whose values are all the same as the card's is `unchanged` and is not written, so a second source that only repeats a value adds no citation. It adds one only when that candidate writes something else too. Whether it should is the owner's to say.

## 2026-11-05 — Schema changes merge when they do not overlap, and only touched skills are flagged

Owner, relayed by the BI orchestrator. Design: `docs/phases/BI_CARD_MODEL.md` §4.3.

**Decided.** One unit per compatible change, on top of the version the `schema` unit names, read as `<base>+<digest>`. Overlap stays for a person.

**Rejected: a three-way merge on sync.** `apply_ops` is pure and every op carries only the hash of its base, so it would need the base document, file reads inside the replay, a merged file that no commit names, and a hook in the generic engine. Units give the same result with the engine as it is: order independence comes from a set of keys, and same key with another value is already a conflict.

**Rejected: a digest in every version.** It would change every ref and the feed goldens' shape. A number from the content for real new versions is enough: `5.1.<patch>`. Two contents can collide only at 1 in about a million, and then `path_taken` refuses the push.

**Also decided.**
- `+<12 hex>` is added to `catalog.VERSION_RE`: a schema's identity must include its content, since "the same id@version with other content" is `schema_conflict`.
- `_same_schema` compares base refs, so a colleague's addition no longer invalidates a run under review. An addition can make no candidate wrong.
- `meta:schema_history` is not written for additions: no version moved, and two PCs' lists would conflict.
- An unedited generated classify is read current at run time rather than regenerated. Two PCs regenerating it for their own additions conflicted on the skill.
- `MODEL_VERSION` stays: what a rebuild makes changes only for a vault with these units, and those did not exist before.

**Accepted limits.** An older AEP refuses a vault with these units at sync. The platform's 2026-10-22 reader refuses a snapshot whose schema carries `+`. A later version taking in a change counts as possibly breaking for that type's skills: what the change said is no longer known.

## 2026-11-05 — One owner for a created domain in the schema

Two designs landed on the same day: `meta:home:<id>` widening the registry when read (`catalog.with_home_domains`), and `schema_change:domain:<name>`. `market-intel` holds neither, in any of its 45 commits (checked read-only), so no vault needs both read.

**Decided.** `meta:home:<id>` stays and keeps `{label, domain}`, because the folder and label need it. `schema_merge.changes_of` reads that domain into what the vault reads; `with_home_domains`, `BiStore.home_domains` and the `schema_change:domain` unit are gone. A bare domain in a draft, with no home, is a new version.

**Why not keep the widening:** `reg.domains` said more than `reg.document`, under one ref, so one id@version could mean two things. A snapshot carries the document and not `meta:home`, so a reader's copy would not have known the domain.

**Why not keep the unit:** a home needs its unit anyway, so a create would write two units that must agree, and an AEP older than this refuses `schema_change:` units at sync. `meta:` it accepts.

**Cost.** A created domain makes what the vault reads `<version>+<digest>`, so a snapshot of it is refused by the platform's 2026-10-22 reader until that is redeployed. A new domain flags no skill, even one whose text names it.

**A source that only repeats a value** adds its citation: decided in the entry below.

## 2026-11-05: A source that repeats a value adds its citation, and leaves the card's version alone

The owner: 「證具, raw data連結就append上去」. A candidate whose values all match the card used to be `unchanged` and was not written, so the second source of a fact left no trace.

**Decided.** Such a candidate stays `unchanged`, with `citations` naming the fields whose value it repeats and does not cite yet. It shows as 新增出處 in review; accepted, it writes only the evidence. Undo removes it.

**The card's version does not move, nor `updated`.** Nothing the card says changed. A raised version would make every other run and open review of that card stale (`cards_changed`) for a citation. A vault derives its version from field changes, so raising it locally would not survive a rebuild anyway.

**Not twice.** A row's identity on a field is its `reference_id`, the source and the place in it. A source read again adds nothing, and is not offered as 新增出處. A different place in the same source is a different citation.

**2026-11-06 concurrency clarification (owner via BI orchestrator).** Concurrent additions of the same reference keep one row, independent of arrival order: later `reference_at` wins for submission-fallback timestamps, then canonical row JSON breaks ties. Rows without an explicit id use the same source-and-locator id function. The field's distinct references still union; this does not change a replacement or an evidence review into an append.

**A replay that lost the field.** Field and evidence are separate units, so a commit could lose the field and still apply its evidence, and the winning value showed a citation of text it does not hold. `vault._evidence_read` now reads the evidence as it stood before that commit, as long as no later commit changed it. The unit itself stays as it was, on every PC: this is how the card reads it. The lost value's citation comes back with it if the conflict is accepted.

## 2026-11-05: Each BI domain owns its questions, and each has its own person

The owner: 「每個領域也要有各自的benchmark 問題和dashboard」, 「這是一個多人合作的平台，但為了不彼此干擾，每一個domain會有專人來處理」. Design: `docs/phases/BI_PAGE_SIMPLE.md` §11. This replaces the same day's decision that a working domain runs its own questions and the untagged ones.

- **專人 is a working arrangement, not access control.** AEP adds no file permissions; IT decides through SharePoint. No owner field blocks anyone, and there is no login check.
- **A question belongs to one domain; an untagged one is waiting for a domain** and runs in no domain's test, only in the overview's. Rejected: running untagged questions in every domain, which puts market-intel's 12 in front of everyone and is what the owner objected to.
- **全部領域 is a read-only overview.** Rejected: letting it add a question with no owner, which would make more of what is being assigned away.

## 2026-11-05: 14 demonstration cards marked as samples, through a CSV import

The owner decided to mark 14 cards of `market-intel` whose pages say fictional or demonstration, 13 and then one the wider check found, with the marks in `card:` units so every PC rebuilds them. No new route: the CSV import already applies `FICTIONAL` to a row and keeps a mark once set, and on a row with no changed value it moves nothing else. Rejected: a dedicated mark route, not needed for this; the page import, which by design never changes a mark; and renaming them `SAMPLE-`, which would change their keys, links and identities. Consequence: these 14 are `synthetic` without the prefix, 21 such cards in all.

## 2026-11-05: The BI page leads with the vault, then the working domain

The owner: 「第一件事情是選擇vault，或者是新增一個vault，接著再選domain」. Design: `docs/phases/BI_PAGE_SIMPLE.md` §13.

- **One row above every tab,** since the vault is what the whole page reads. Rejected: keeping the vault in step 1, which is what the owner found backwards.
- **The working domain decides the Dashboard's domain, and only starts the card tab's filter.** Rejected: hiding the card filter too, since a person often needs to look across domains there; two filters that could silently disagree on the Dashboard, where one panel set has one domain.
- **Sticky on a desktop only.** On a phone the stacked row would cover the page.

## 2026-11-05: A sample mark can be cleared, and 「待查證」 no longer sets one

Seven real cards, such as `WiFi-7`, were marked as samples only because a field said 「(待查證)」, which says a value needs checking, not that a card is made up; 29 real cards link to marked cards. The owner confirmed the seven are real. A mark was one way until now. `POST /api/bi/cards/<id>/unmark` clears it with a reason, kept on the `card:` unit as `mark_cleared` and in a small table, since history is otherwise derived from `field:` units and a card's mark is not one. Rejected: a pseudo field for the mark, which schema and pages would have to hide, and clearing through an import, where a row saying nothing cannot mean "real". A `SAMPLE-` name cannot be cleared this way: it would stay left out by name while claiming to be real, so such a card is renamed first. The rule for the default pack is unchanged and follows later.


## 2026-11-05: Each BI domain has its own Dashboard, on the analyses they share

The owner: 「每個領域也要有各自的benchmark 問題和dashboard」. Design: `docs/phases/BI_PAGE_SIMPLE.md` §12.

- **A home's Dashboard is its own unit, `meta:dashboard:<home>`; `meta:dashboard` stays the vault's.** Old commits, published snapshots, the feed and Atlas read what they read, and the feed goldens need no change. Rejected: nesting homes inside `meta:dashboard`, where two domains' people would conflict on one unit and the feed's reader would have to change.
- **An analysis is shared and a Dashboard chooses,** since an analysis that takes `domain` already gives each its own numbers. Rejected: a copy per domain, which would drift.
- **A domain's starts empty.** The vault's still shows everything not hidden.
- **A panel that does not read `domain` is labelled 全庫資料.** Declaring the parameter is not enough: the code must read it.
- **Published readers see no per-domain Dashboard:** the feed stays the vault's. Rejected for now: a per-domain feed, which is a contract change for Atlas.
- **Assigning what exists is a dry run, then one step on an approved list.** Nothing is written until a person approves, and it stages changes for their commit.

## 2026-11-06: A BI push is held back by what it touches, and 定案 settles a field

The owner: 「這是一個多人合作的平台，但為了不彼此干擾，每一個domain會有專人來處理」, and on 定案, confirmed through the orchestrator: after a meeting, the person responsible settles a field. Design: `docs/phases/BI_PAGE_SIMPLE.md` §14. This replaces the same week's decision that a person in one domain is blocked by a regression in another, which the owner's sentence overrides.

- **A regression blocks a push only in the domains it touches;** elsewhere it is a note. What cannot be placed soundly blocks, as before. Accepted cost: an aidc push can break a wireless answer that reads an aidc card, and nobody is stopped until wireless is tested.
- **A test counts per domain:** its units and the shared ones. Rejected: the whole-vault digest, under which any colleague's push voids everyone's run.
- **定案 is an ordinary change with a reason,** built on `set_field`, closing proposals, and `resolve`. Not a Git force push: commits are immutable. No access control. Rejected: a new unit kind for final values, since the field's own history already holds who and why.
- **Commit stays whole for now,** though `only` makes limiting it cheap. The owner has not asked, and the warning covers it.
- **The owner's rule for a card two domains reach is recorded, not built:** it needs a merge rule in the engine's conflict path. Findings in §14.

## 2026-11-06: One unit name sits at one level for a company

Acceptance walk of the business cards (orchestrator, for the colleague release): the printed
光學事業處 was read as the 事業群 on one card and as the 處 on a colleague's, and the org chart
showed 光學事業處 > 光學事業處 > 研發部. The orchestrator asked that one name not occupy two levels
for one company, existing duplicates fixed when a card updates. Rule in
`docs/phases/BUSINESS_CARDS.md` §2 (Host checks on a reading).

- **The name's own level word decides first** (…事業群 → business group, …處 → division, the
  mapping the spec and the Skill already give), then the company's majority, a tie the first
  stored person's level. Rejected: always the majority, which makes the first misreading the
  company's rule; and always the name, which cannot place English or unmarked names.
- **Only when the company has the name at both levels.** A name read at one level stays where
  it was read: nothing contradicts it.
- **Stored people are re-placed inside the card's change** with their value's source kept, so
  undo of that card reverts it. A value the person set is never moved (the rule that only new
  evidence touches the person's values), and a level holding another name is never overwritten.
  Rejected: a one-time migration, which would not catch the next card read the other way.
- **The chart also drops a unit nested in itself**, so a store not yet re-placed draws right.
- **Chart file names use local time**, as the page does (a UTC stamp named the previous day in
  the Taipei morning).

## 2026-11-06: A reload keeps Agent Web open; the token stays in the tab

A reload (F5) gave 「Open the address this command printed.」: the page takes `?token=` out of the address and the server lets the page in only with it. Colleagues had to reopen from the shortcut.

**Decided.** The page keeps this run's token in its tab's `sessionStorage`. An address with no token gets `RELOAD_PAGE`, a short page with no secret, which reads the tab's copy, removes it, and opens the address with it. The page then keeps it again. A token from an earlier run is refused once, and the copy is gone, so it is not tried again. A new tab, a bookmark or another run still needs the shortcut.

**What the token guards, checked.**
- **Another local user:** `sessionStorage` is per browser profile and tab, so they cannot read it. The address without the token gives them a page with no secret, and every API still needs the `Authorization` header.
- **A website (CSRF):** nothing is sent automatically, there is no cookie, and its scripts cannot read another origin's `sessionStorage`. No preflight is answered.
- **DNS rebinding:** the `Host` check is unchanged, so a rebound name is refused before any of this.
- **The in-chat HTML viewer:** an opaque-origin sandbox (`FILE_VIEW_CSP`, no `allow-same-origin`), so it cannot read the tab's storage.
- **The token itself:** it still changes every run, and `sessionStorage` goes when the tab closes.

**Rejected.** An `HttpOnly; SameSite=Strict` cookie for this run's token: a cookie is sent by the browser on its own, so every GET route would need a second check against CSRF, and the decision of 2026-10-08 already turned down a cookie.

## 2026-11-06: The skill AI has a budget per turn and always leaves something to read

Acceptance F16 (orchestrator, for the colleague release): one message in 和 AI 新增規則 ran 25 minutes
and 9 trials, ended with 「模型沒有回應（turn_time_limit）」 and no suggestion, while the person's
sentence had already been saved as revision 1. Spec: `docs/phases/BI_TEST_AND_TOOLS.md` §4.

- **3 trials within 6 minutes, turn limit 10 minutes.** Trials are what takes minutes; counting them
  bounds the turn better than the tool-call cap. Rejected: only a shorter wall clock, which cuts the
  model off before it can suggest.
- **Out of budget, the last draft that tried well comes back as the suggestion,** marked in its
  limits as not finally checked by the AI. Rejected: an error with the drafts hidden in the log.
- **Stop codes become Chinese sentences with what to do** in the shared session record, so every
  BI session kind gets them; the code stays in `error.cause`.
- **A new rule lives in its session until applied** (`new` in the session body). Rejected: saving a
  placeholder revision, which is a rule nobody approved.
- **Not changed:** the schema and questions AIs (15 minutes, 40 tool calls, no trial cap or
  fallback) and the analysis AI (10 minutes, 30 calls) have the same shape; left for a decision.

## 2026-11-06: An empty card_types means the domain profile's types, else the defaults

Acceptance F17 (orchestrator): the skill form said 「只產生這些卡片類型（留空＝不限）」, but empty meant
Signal, Technology and Application, so a rule about customers and supply links did nothing until the
types were typed. Spec: `docs/phases/BI_TEST_AND_TOOLS.md` §4.

- **Empty falls back to the domain's profile types when it has a profile, otherwise to the
  defaults.** This is what runs already did; it is now one function and said on the page. Rejected:
  empty = every schema type, which matches the old words but makes every run ask for all twelve
  types (slower, noisier review) and changes every existing rule's output at once.
- **The page says what a run produces** in the list and live in the form, and the label says what
  empty means. Rejected: only rewording the label, which still hides the profile's effect.
- **The skill AI must give `card_types` when its text names types a run would not make;** the
  check names them. Types the profile leaves out are not demanded, since the rule cannot add them.

## 2026-11-06: One model call has its own timeout, and a down model service is said at once

Acceptance F16/F20 (orchestrator): with the company model backend down, one call held a BI AI
turn 6 and 10 minutes whatever its budget (a turn's clock is checked only between calls; the
client's timeout was a fixed 600 s), and a chat turn took about 4 minutes to say 「The configured
model could not answer this turn.」 with no cause or 重試.

- **`models.call_timeout_seconds` (default 180) for the conversation:** chat turns and the BI AI
  sessions on the harness. **`models.batch_timeout_seconds` (default 600) for the drafting
  clients:** Knowledge answers and ingest, Workflow drafts and BI card extraction runs, whose
  one call may write a long answer; trial runs inside a BI AI turn use the conversation's client
  and its 180 s (orchestrator). Both in host.json,
  10–3600. The router gets its own clients; the drafting switch follows the models the page
  approves on the router's. Rejected: one timeout for both, which either cuts extraction or
  leaves chat hanging 10 minutes.
- **A model call's 5xx is explained before anything else, in Chinese,** naming that the model
  service is not answering, with 重試; a timeout says how long it waited. The minutes of a 503
  are spent inside the gateway (LiteLLM), not in AEP: AEP asks at most twice (stub test), and one
  call measured 359 s before its 503. LiteLLM's retries live in the owner's gateway repository;
  not changed here (the orchestrator tells the owner).
- **The newest failed chat answer gets a 重試 button** (the same question again; attached files
  are not sent again), and a failed BI AI turn too.
- **Send waiting after a reload says why** (the conversation backends' sign-in check).

## 2026-11-06: 建議 schema is its own press, and a version reads as 「5.0 加 N 項新增」

Acceptance findings F5, F6 and F8 on step 2a. The owner's flow: 「根據新增的資料來建議是否要在schema新增類別，做法可以讓使用者按一個button，系統給出建議」. Design: `docs/phases/BI_PAGE_SIMPLE.md` S2; contract `docs/CONTRACTS.md`, "BI schema drafts and dataset upgrade".

- **The suggestion asks the schema-fit question alone, on its own path** (`schema_suggest`), with `schema_fit`'s rules and checks. It reads the domain's sources no ingest read, or the one picked in step 1, and works whatever extraction method the ingest will use. Rejected: running it as an ingest run with the fit tick, which writes candidates, costs the extraction, and is skipped by a custom method.
- **Every row has a quote found in the source.** What the model could not quote is counted and left out; a type or field the schema has becomes a question. 「不用改」 is a valid answer, shown as one.
- **A field or allowed value is added through draft, publish and upgrade,** which a vault already turns into units on its version (`schema_merge`). The draft is removed afterwards. Rejected: staging `schema_change:` units directly, a second way in beside the one that checks and renumbers. A type, a synonym or an enum field with no values goes to the AI panel with the row written: they need a definition a person agrees.
- **A version is shown as 「5.0」 or 「5.0 加 N 項新增」, never its digest,** and the notice after an upgrade says whether it was additions or a new version.
- **預覽升級 offers only versions newer than the base that keep the vault's additions,** and the server refuses a move that would drop them (`schema_drops_additions`), unless the version was published from a draft of the current schema, which is a person's own removal. Rejected: refusing every move back, which plain datasets use by design.
- **The draft on the main path is a table of its changes,** with the AI to edit it and 套用到資料集; its JSON, revisions and trial stay under 進階.
- **`bi-b-fit` stays under 進階** for now; S2 planned to remove it once this button exists. That waits for the owner.



## 2026-11-06: Acceptance fixes F9, F10, F12, F19 (BI orchestrator)

- **F9. Every list of homes reads the units, uncommitted ones too.** The folders a rule may apply to came from the shared folder on disk, so a domain created and not yet pushed was missing and 和 AI 新增規則 fell back to aerospace. They now add each home's sources folder from the units; the select starts on the working domain, and under 全部領域 a person must pick one. Rejected: an empty choice meaning every source, which is how a rule silently lands in the wrong place.
- **F10. A new card from a reading run takes its source folder's domain, and the model's stays as a proposal.** This replaces the 2026-11-04 R6 rule (commit `7653aeee`, `docs/CONTRACTS.md` "AI runs, from the first R6 run") under which a domain the model gave, if the schema knew it, beat the folder's. Measured: a source in a created domain's folder resolves to that domain at run time, so the wrong domain came from the model's guess winning, not from `homes.domain_of_folder`. The model's value goes to the field's `alternatives`, which a run's commit already writes as a pending proposal with its evidence, also on a new card; so a wireless fact in a marine source still reaches wireless's person. Rejected: adding it to a list-valued `domain`, which would put the card in a domain nobody chose, and the owner's rule for shared cards is not built; dropping it, which loses what the source says. Existing cards are not re-domained. A run already in review keeps its candidates: run it again.
- **F12. Commit and push are reachable from the status line under the top row,** from any tab: 「還沒 commit 的改動 N 個」 and 「你還沒 push 的 commit N 個」 are links to 版本 in step 3. No new place for 版本.
- **F19. An import commits its own units and what they cannot go without.** Its own: what the import staged, read from the pending changes before and after it. What they need, of what else waits: a created home whose domain its cards carry, and a schema addition (type, field, allowed value) they use, since a colleague given the cards without them reads values their schema lacks. A skill, a question, a label, an unused addition and the rest stay for the person's own commit and purpose. Sources added still commit first in their own 「加入來源」 commit, all of them, as before: an import's evidence needs its source, and a source added but not imported is labelled as what it is. Rejected: one commit of everything under the import's purpose (the finding).

## 2026-11-06: The BI script guard stays on whatever a script reaches

A finding before release: on a PC with numpy (the release bundle carries it), the tool runner's pre-import of openpyxl loaded numpy and so ctypes, and a tool's `import ctypes` then came from `sys.modules` with no audit event. Measured with real attempts (`tests/test_bi_guard_attacks.py`): ctypes still refused `ctypes.dlopen` and `ctypes.dlsym`, but a ctypes Union of a pointer and an address wrote process memory with no event. Wider, and with or without numpy, in tools and analyses alike: a script could switch the guard off in one line (`__main__._ready = False`, a frame's `f_globals`, `gc.get_objects()`), empty its lists, or replace a builtin or `ntpath` function it called, and then write outside its folder or open a socket.

The design of 2026-10-31 stays: guarded, not sandboxed, and a person reading the code (a tool by its hash) is the real control. Within it:

- **The guard is a closure installed right before the script,** keeping its own copies of the lists, builtins and functions it calls; no flag, and nothing left in `__main__`. Rejected: deleting modules from `sys.modules`, since attribute paths (`numpy.ctypeslib.ctypes`) still reach them.
- **It refuses to start when a module it denies is already loaded** (except `_winapi`, which shutil imports on Windows and whose process calls raise events it refuses). The tool runner keeps numpy out of its pre-imports, so openpyxl reads without it. Rejected: loading openpyxl lazily inside the hook's rules, which would let a tool's own import pull numpy in under different rules.
- **Frames, the garbage collector and tracing are refused** (`sys._getframe`, `gc.get_objects`, `sys.settrace`, …).
- **On Windows the write check resolves paths through `nt`'s own functions,** captured at install; `os.path.realpath` is Python that reads its module's globals at each call.
- **What it still cannot close:** a determined script may find a CPython flaw, and it can read any file the user can. The page's approval step and the user guide (6.8.3) now say what approving means. A real boundary (AppContainer or a job object) remains the later replacement.

## 2026-11-06: The shortcut waits for a start as long as its server runs

On the owner's PC a server took 5.5 minutes to listen after a reboot (building the runtime and
Agent Web come before the port is bound). The shortcut reported 「Agent Web did not answer within
300 seconds」 at 15:17:32 and the server came up at 15:18:04 with nothing waiting for it.

- **A start is waited for, and joined, while its server process runs,** up to 15 minutes
  (`launcher.MAX_START_SECONDS`); 300 s stays the point where the page says it is slow.
  Rejected: a longer fixed deadline only, which still fails a start that is alive and late.
- **A record whose server runs but answers slowly is waited for,** never dropped and replaced:
  a 3 s check on a loaded PC must not start a second server.
- **Nothing is started while something listens on the port,** and `aep-host web --port N` exits
  at once (code 3) when the port is taken, before the minutes of building the runtime.


## 2026-11-06 — BI 分享: the page sequences it, the route only reads (acceptance F13-F15)

- **One 分享 step runs commit, push, tag and publish through their existing routes**, in order, stopping at the first failure. A new route reads what a share would carry. Rejected: one server route doing all four (it would duplicate the push gate's path and hide which step failed).
- **One confirm, on the page, before the four steps;** no extra confirm for a regression in another domain (the owner). A regression in a domain the share touches disables the button with the reason; `repo.push` still blocks it.
- **Tag name: today's local date, `-2`, `-3` when taken,** editable. A name taken between loading and pressing stops at the tag step; the next load proposes the next suffix.
- **`confirm()` leaves the BI page** for an inline confirm the tests can press. The wiki side's nine stay for now, listed in `docs/phases/BI_PAGE_SIMPLE.md` S6.

## 2026-11-06 — BI test results: an old comparison says so (acceptance F24)

- **A result is 舊結果 when the published version's commit changed since the run, or the content it tested changed.** Publishing the same commit under another tag changes nothing the run compared, so it stays current. A report from before runs recorded the version is old when a publish came after it started.
- **Display only: the push check is unchanged.** A regression found against an older published version still blocks a push that touches its domain, as the owner's rule in §14 says; the page marks it 舊結果 and offers 重新跑測試. Rejected: voiding verdicts in the gate on a publish (a colleague's publish would silently unblock a regression).

## 2026-11-06: The BI first view, for someone creating a vault and someone joining one (acceptance F1-F4, F21-F23)

- **F1. Knowledge opens on BI when the wiki pipeline is not configured or holds nothing,** unless the person last chose the other tab. A PC installed from `deploy/windows-preview/` has no `knowledge_pipeline` in `host.json`, and opened on "not configured".
- **F2, F21. With no dataset, the page is the top row only:** 新增知識庫 and 加入, both the lead, one line and a small 載入示範資料 link; the select, the tabs and the steps wait. 新增資料集 stays under 進階.
- **F3. The vault form checks the folder as typed and offers this PC's OneDrive folders** (`GET /api/bi/vaults/folder-check`). No 瀏覽: the page is a browser page, and a dialog the server opens on the desktop cannot be tested and could open behind the window or on a PC nobody is at. Rejected for now, not ruled out.
- **F4. The schema version is under 進階, defaulting to the newest; a name with no letters asks for an id** instead of making `vault-xxxxxx`. The step bar sticks under the top row instead of sliding half under it.
- **F22. The working domains are the homes something is in** (a source, a card's domain, a question, a skill, a tool, a profile, a Dashboard) **and the ones created,** not the vault's default list: a vault holding only 海事 listed eight. The profile list is the same list. Naming an unused default home in 新增領域 takes it up rather than answering that it exists. After joining or creating, one domain is chosen, several are asked for, none points at 新增領域. Accepted: a vault made with the defaults lists nothing until something is put in a domain.
- **F23. Withdrawing a colleague's source says whose it is and that it is for everyone.** No access control and no block, per the standing rule.


## 2026-11-06: Same-card readings stay first; evidence appends and time takes the later date

Owner: 「關於同一張卡，概述應該不會變，證具, raw data連結就append上去，時間也是取合集」. Chosen before release, confirmed through the BI orchestrator.

- `summary`, `usage`, `scope` are fill-only for imports and runs. A differing later value becomes a pending proposal with its own evidence; explicit human corrections, accepting a proposal and 定案 still replace. Concurrent empty-field writes settle in the existing `(clock, author, seq)` replay order, never folder arrival order.
- BI owns one optional repository-type operation projection, shared by push, sync, historical state, history and sharing. Wiki keeps its existing policy. Evidence additions union by `reference_id` (source and locator for old rows), choosing the later reference time and then canonical JSON for duplicates; field replacement keeps the existing move-to-history rule. `updated` takes the later date.
- New BI evidence operations carry optional `bi_evidence` context: the prior evidence list and hashes of the field value before and after. Without this, a base hash alone cannot prove an append. Old commits remain readable; an ambiguous old evidence race remains a conflict. Reject silent guesses, changing immutable commits, or applying a blanket list union to replacements.
- Older AEP rejects the extra operation key; all colleagues must use this release. BI replay policy version 1 forces one repository replay; card model 12 forces one materialization. No source files or real vaults are changed by development tests.
- The same file imported into two homes (`source:` folder conflict) remains separate work, not part of this field-evidence policy.


## 2026-11-06: Quiet chunk readings and chronological BI timestamps

Release verification on 3167044b found two regressions from the same-card slice.

- Within one extraction run, two inferred summary/usage/scope readings from chunks of the same source keep the first reading and retain the other as an alternative with evidence, without a value_conflict warning. Normal chunking is not a conflicting factual claim. Ordinary fields and sourced (fact) summaries still warn. Dropping the alternative or suppressing all value warnings was rejected.
- Latest time means the later instant, comparing ISO dates/timestamps in UTC, never lexicographic timestamp text. Date-only/naive values compare in UTC consistently on every PC. Undated legacy strings sort before valid timestamps. Equal-time evidence/updated-field units retain their canonical tie-break; derived card.updated keeps the incoming history timestamp representation on equality, preserving the pre-existing history format.
- The coverage golden difference was four latest-update cells only: aidc-computing/high-speed-io and aidc-power/{rf,power-generic-io,emc}. 2026-11-01T01:00:00+00:00 had become 2026-11-01T09:00:00+08:00, the same instant, because string max chose commit.created over history.at. Counts, source coverage and missing-field lists did not change. Fix the comparison, not the analysis or its golden; feed and default-pack goldens remain unchanged.
- Replay policy 2 and card model 13 replace the buggy timestamp projection/materialization once; commit records remain immutable. Tests first reproduced four timezone failures, then cover both arrival orders and equal-time history formatting.

## 2026-11-07 — Keep release failures from echoing child-process output

Windows pytest writes a test's node ID into `PYTEST_CURRENT_TEST`; using a 100,000-character
adversarial JSON input as the generated parameter ID exceeded Windows' environment-variable
limit. Its OS-error traceback also rendered the inherited environment. Keep the full input
and strict rejection assertions, but assign each Atlas-file case a short explicit ID.

The release runner now reports the failed command and exit code without copying child stdout
or stderr into `ReleaseError`. The former last-25-lines tail could include credentials even
when the release code never printed an environment mapping directly. Name-based or pattern
redaction was rejected: inherited values and traceback representations need not have a
recognizable secret name or syntax. Successful command output remains available internally
for revision discovery and packaging; failure still stops the release. Synthetic-output
regressions verify both behaviors. The sign-in test's existing environment containment check
also computes a boolean before asserting, so a failure cannot print its serialized environment;
the condition is unchanged. This changes diagnostics, not assertion strictness, runtime
authorization or the contents of a release.

## 2026-11-07 — Widen filtered BI searches and expose bounded matched body excerpts

The SOP calibration question had an answer only in a CustomerProduct body. A SupplyLink hit
was insufficient, and even an unfiltered search omitted every body from its card output.
On a fictional SOP workspace copy, direct type-specific and unfiltered queries reproduced
this omission. Body was excluded since the original card UI/query implementation (136c5cca);
no separate documented privacy rationale was found. Keep that whole-body exclusion, and add
only an excerpt needed for a text match under the host's data approval.

- A text search with type/domain/field/value filters counts exact word-matching cards excluded
  by those filters in the same authorized dataset/version. scope_note groups other types and
  other domains, with a same-text retry instruction. Counts do not return extra cards, fields,
  links, evidence or passages, and do not broaden the result automatically. The existing word
  matcher and nearest-match behavior remain in charge; no cross-dataset search.
- A returned card whose current body contains a query word may have body_snippet:
  field=body, text up to 300 characters around the first match, source=kind:ref. Ellipses mark
  cuts; the card's existing citation and trusted/synthetic fields remain. No text query, no
  body match, or no approved class: no snippet. Related cards do not gain whole bodies.
- Body source IDs must resolve to approved source classes; unknown IDs withhold the excerpt.
  Imported filename matches also use known source classes (all classes on duplicate names must
  be approved). Curated/imported text without source classification conservatively defaults to
  INTERNAL. Source identity/class is a single metadata projection, without per-source revision
  lookups. Chosen-version harness tools inherit the installed tool's host approval, not model
  input; the selected store still supplies all text and counts. Raw passages keep their prior
  approval/version restrictions, including no raw passages for chosen-version benchmarks.
- Tool description and Skill guidance require removing entity_type, then other restricting
  filters as indicated, before claiming the knowledge base has no answer. A count is a hint,
  never evidence. Benchmark-question guidance includes looking for a calibration cycle on
  another card type, using only terms actually read there.

Returning every matching type's rows automatically or returning complete bodies was rejected
because it increases context and can bypass the person's filters/size expectations. Inventing
an answer from counts or weakening benchmark must terms was also rejected. No persisted model
or commit format changes; feed goldens remain byte-identical.


## 2026-11-07 — Keep rename collision identity stable within one clock second

Windows CI run 42311321089 exposed two card creations in one timestamp second: sorting by the raw timestamp then card id gave the canonical name to a newer card. Rebuild compares creation instants in UTC and breaks equal-instant ties by the existing deterministic commit replay position that first introduced the card, then card id (including two cards introduced by one commit). Different textual UTC offsets cannot change the winner. Legacy metadata without replay positions keeps the date/id fallback. Reject adding sleeps, changing ids or weakening the two-PC assertion. Commit files stay immutable; projection MODEL_VERSION advances 13 to 14 so cached views rebuild once. This changes collision projection, not unit formats or wiki policy.

The same CI run crossed UTC midnight. Business-card tests that cached date.today at collection mislabeled same-day signatures as newer after the edit day advanced. Those tests use a fixed local edit day and clock; the source-date rule (strictly after the day of the person's change) is unchanged. A process UTC probe advancing the edit day reproduced both original failures. Do not change product chronology to satisfy a stale test date.


## 2026-11-07 — Preserve vault arrival feedback and control CI race boundaries

Creating or joining a vault must keep its success message after automatic working-domain initialization. Automatic domain selection calls the existing handler directly; it does not emit a synthetic change interpreted as the person's next action. Missing/multiple-domain guidance appends to that success. A browser regression waits for arrival initialization to finish before checking the notice; it failed before this fix.

The share browser test arranges a real duplicate tag at the confirmed POST/tag boundary, instead of racing background tag suggestions. Its original side-effect order/failure assertions stay strict. Version navigation waits for the original visibility predicate and retains its focus assertions; controlled response ordering and CPU throttling did not reproduce the CI rectangle failure, so no unproven product scroll change is made. Windows CI error annotations explicitly emit UTF8, tested under cp1252; changing test messages to ASCII was rejected.

## 2026-11-09 — Read SOP attachments at chat ingress, preserving source evidence

The owner approved direct PDF/XLSX/DOCX use for SOP-to-Workflow authoring and
preserving numbered reply headings. Extend the existing session-owned attachment
store with a local read-only preview adapter, not another Knowledge ingestion or
authoring runtime. PDF previews include page text, embedded pictures and HTTP(S)
hyperlinks. Word reuses the Office body/table/picture extractor and adds document
hyperlink targets. Excel previews retain sheet names, row numbers and formula
expressions. Originals, source paths and existing session isolation survive;
bounded/truncated/failed extraction is explicit. Host guidance identifies the
already-parsed evidence and asks the drafter to prefill supplied values.

Reject asking people to paste their SOP manually, using a binary text reader as
the normal document path, and treating an attachment preview as a new Knowledge
source. The existing approved Office dependencies supply the parsers; the
Windows offline bundle now requires python-docx and lxml as well as its existing
PDF/Pillow/Excel wheels. No new library, model provider, execution permission or
publication authority is added. Legacy .doc/.xls remain unsupported.

The Markdown renderer preserves each explicit ordered-list start value, including
lists separated by bullets/paragraphs. It keeps the existing safe DOM rendering.
Do not infer new numbering when the source itself restarts at 1.

Real-model attachment acceptance distinguishes a persisted draft, input-contract
validation, fixture-tested Excel code and authenticated C4C execution. A draft is
not proof that unvisited web controls work. Details and remaining live acceptance
are in docs/evaluations/CHAT_DOCUMENT_ATTACHMENTS_2026-11-09.md.

### Owner clarification: C4C SOP TWD rate remains pending

The owner explicitly rejected interpreting the SOP's "TWD1 = TWD0.02712085" as
1 TWD = 0.02712085 EUR: "不是，匯率先保留待確認" (2026-11-09). Keep original TWD
amounts and flag their conversion as pending; do not substitute a guessed or
current online rate, count them as EUR zero, or include them in converted EUR
totals. A future explicit rate may resolve the pending rows. The SOP's explicit
USD-to-EUR rule is unaffected. This is a business clarification for the private
test candidate, not a platform-wide FX default.

### Later owner correction: confirm the SOP's TWD-to-EUR rate

Later in the same 2026-11-09 conversation, the owner changed the answer to yes:
"草稿測試暫按『1 TWD = 0.02712085 EUR』計算；這是你要的匯率嗎？ => 這個改成是".
This supersedes the pending-rate clarification above. The private C4C Workflow
may now prefill 0.02712085 EUR per TWD with provenance from this explicit owner
confirmation. It is not an inferred correction or a platform-wide exchange rate.

### C4C live replay uses UI tables and explicit readiness (2026-11-09)

The owner's authenticated C4C view has no Export/Spreadsheet control; its SOP
instructs copying the table into Excel. Use the Browser capability to read every
visible page, then restricted local Python to write Excel, without SAP HTTP
endpoints, application internals or order edits. Reject the draft's unverified
Export button and US number/date assumptions. Observed dates are DD.MM.YYYY and
amounts use decimal comma and thousands dot.

SAP requires trusted pointer press/release. Add that primitive to the existing
Browser runner, after origin/read-mode checks, rather than a SAP-specific
runtime or DOM click workaround. Add optional split headers, bounded pagination,
stable rows and declared unique key columns to the existing typed action contract.
Frozen ID cells can update after other columns; accepting only a changed row is
insufficient. Await visible loading/completion markers with a bounded wait_for,
rather than guessing a fixed delay or treating retained old tables as results.

Keep unmapped Owners as explicit exceptions with their original rows and EUR
amounts; do not infer departments or silently omit their monthly totals. Real
business data, test manifests and output stay in private local task directories.
Source verification uses a separate runtime and the installed restricted,
network-blocked Python interpreter; it does not update/restart the resident Host.

### Preserve execution truth and resident authoring state (2026-11-09)

The owner requested resolution of all five gaps in the SOP Workflow autonomy
diagnosis. Keep the existing Bridge, Workflow engine and owner approval paths;
add typed local failure diagnostics, bounded Browser observation, durable
actor/session inputs and requirements, exact-revision trial verification and
bounded Agent repair continuation. Reject installing a planned revision merely
because a previous revision ran or an old Excel exists. Preserve legacy unplanned
authoring behavior; SOP authoring activates the persisted task gate.

Procedure assertion paths describe technical evidence and may need rebinding
after discovery or step insertion. Preserve requirement IDs/descriptions/check
IDs, disallow clearing existing coverage, and invalidate both verified digests
and in-flight trial tokens whenever bindings change. Immutable technical paths
were rejected because they prevent correcting an initially malformed binding;
silently dropping requirements was also rejected. Independent Agent-only live
acceptance still decides business completeness.

Repairs reuse normal Agent admission and authorization, offer a restricted tool
set and never install/approve themselves. Code-only tests and a Codex-authored
C4C manifest are not evidence that the resident Agent can author this task.
Keep actual owner documents, browser records and workbooks private. Deployment
of the resident Host remains distinct from source verification and requires
checking active interactions first.

### Compose multiple Workflow outputs with an atomic read tool (2026-11-09)

Live SOP authoring produced a preparation step and Browser step, but its report
received only Browser data and hardcoded the earlier parameters. Add the local
read-only `data/merge` building block so each input uses existing typed Workflow
bindings. Reject conflicting values rather than silently overwrite owner input.
Keep numeric equality but distinguish JSON booleans from numbers. This avoids
expanding the shared input union, hidden runner context or dependence on private
runner parameter files. Existing knowledge-pipeline Merge types remain distinct
through explicit Host import aliases. Schema/real Workflow/Host-policy cases
precede rollout; actual Agent selection remains part of live acceptance.

### Keep bounded actual trial history during SOP repair (2026-11-10)

Live AEP revisions revisited earlier failed navigation after those attempts
left the short conversation window. Retain a bounded actor/session history
of actual current-token trials in the existing authoring task, including only
failure metadata and declared Browser action/target prefixes. Do not store
fill values, open URLs, scripts or result rows. Limit it to ten records and
12 KB, trimming oldest records. Show it as technical evidence in repair, with
no automatic backfill, new authority, budget reset or hard ban on a previously
failed procedure (a transient condition may change). Last-failure-only memory
was rejected because it permits cycling; a broad procedure recorder or new
workflow engine was rejected as unnecessary for this bounded continuity fix.

### Reveal content without blindly toggling it (2026-11-10)

Live failure evidence showed a date fill after Advanced Search had been closed
by an unconditional click. Extend the existing Browser primitive with explicit
`ensure_visible(target, trigger)`: observe first, skip an unnecessary click,
otherwise native-click once and verify desired content within a shared bound.
Keep origin/read policy, permissions, ordinary clicks and business proof gates.
This is a focused implementation of the approved repeatability repairs; a
general Workflow condition or browser recorder would be broader than needed.

### Keep declared full-collection obligations through repair (2026-11-10)

Actual native revision27 removed pagination after a failure and weak original
assertions still reported complete coverage. Preserve real paginated collection
declarations as sticky actor/session task obligations, keyed to the Browser
output collection with source digest. Removal/rename/replan/candidate changes
cannot silently discharge them. Allow incomplete prototypes, refuse verified
and installation readiness until matching complete extraction is restored.
An unrelated dummy pagination or model complete=true is insufficient.
Architecture review approves this narrow stop boundary. Alternative full-file
export needs deterministic current-run count/provenance evidence in a later
contract; mere nonempty download was rejected as proof. Language-specific SOP
heuristics and forcing locators/step indices immutable were rejected. Legacy
empty defaults stay compatible; do not fabricate old declarations. This closes
the observed regression, not every possible weak initial requirement plan.

### Make fresh-page reset explicit (2026-11-10)

A real Edge experiment showed open/hash navigation retained the old loader and
modal while readyState was complete; native trial state likewise kept Date
popup fields at the Home URL. Expose explicit reload rather than silently
changing open or authorizing about:blank. Require a fresh main loader and its
completed document under one deadline, same tab/profile/viewport and origin
checks. Execute mode is required; no form confirmation is auto-accepted. A
new browser process, arbitrary script or workflow-engine branch was rejected
as broader than needed. This adds a deterministic entry reset, not business
success evidence. Existing architecture review and owner five-gap authorization
cover the narrow primitive; full verification still applies.

### Serialize BI dashboard intents within their original domain (2026-11-10)

Full autonomy verification exposed an existing lost dashboard update. A real
Browser test held the first save response body; clicking a second old-DOM
panel posted a stale full order and removed the first panel. Queue intents
per vault/domain, reread current server layout when executing, then await the
write body and refresh. Capture the original scope and retain render-generation
guards across switches; prior errors must not poison later intentions. All
add/hide/show/move actions use current layout, with visible-order neighbors for
moves while preserving hidden membership. Artificial test waits were rejected
because they hide a real user-visible lost write. A separate current-overview
guard prevents stale pre-homes row handlers from selecting queries in read-only
overview; null clears remain valid. Controlled red/green Browser regressions
precede these narrow fixes; no server API/permissions or new feature is added.

### Revalidate targets after native hover (2026-11-10)

A trusted-event local fixture showed entry events first arrived with a pressed
button when click_at omitted pointer movement. Keep raw click_at stable and
add an internal optional hover before ScriptRunner activation. Re-resolve the
same locator, origin and hit test after movement, sharing the original deadline;
a moving target may be observed again, but the eventual press cannot replay.
Architecture and independent read-only reviews found no blocker. No public
action/permission or app-specific selector is added. Forced DOM clicks and
blindly retrying a press were rejected. This fixes proven local input fidelity;
it has not been established as the cause of C4C's navigation failure.

### Preserve truthful repair messages at the conversation window (2026-11-10)

Actual native approved trials35/36 saved their repair candidates and approvals
but then crashed saving a one-assistant continuation at the100-message cap.
Three causal regressions cover full-window single append,99-message paired
append and the real decide_approval repair path. Admit only one/two-message
rollover preserving the exact retained suffix, cap, owner and timestamp guards.
Fabricating a user's request to make a pair and retrying the already-completed
trial/model side effects were rejected. This narrow storage admission repairs
existing Host continuation semantics; it does not introduce a new message role.

### Preserve verified Workflow code with scoped patches (2026-11-10)

Real native AEP Browser repairs replaced entire candidates and corrupted an
already verified downstream Excel script. Add one shared native/MCP typed
existing-value patch API, admitted by candidate digest and ownership/session.
Unmentioned canonical fields, identity/version, defaults and scripts remain
unchanged; patch skips draft reassembly and recent-input rebinding. Same-session
owned JSON attachments can supply exact reference values without model retyping;
no arbitrary filesystem path is accepted. Keep attachment root/size limits.

Automatic repair uses patches only on the actual failed step inputs established
by matching trial digest/run/capability diagnostics. This applies generically to
all capabilities, preserving failed-Python repair; incomplete successful trials
without a trustworthy failed step stop with structured needs_input. Whole
replacement during automatic repair and guessed failed scopes were rejected.
Explicit user turns may restore another step from an owned reference.

A private standard-library OS advisory candidate lock and revision+digest CAS
protect concurrent writes and no-op patch proof invalidation. Installation holds
the same admission across fresh proof checks, publication, grants and status;
otherwise a patch could make an installation report failed after it had happened.
Legacy full replacements guarantee overlap protection only: they have no client
base digest to identify stale documents arriving after a patch completes. A broad
breaking full-draft contract change and a snapshot subsystem were deferred.
Exact current-digest verification and separate installation approval still apply.

### Keep actual trial inputs during automatic repair (2026-11-10)

Native QA changed dates, rates and mapping and correctly failed on stale Browser
rows. The continuation then proposed arguments={} and silently selected formal
defaults. Preserve the previous actual effective arguments through a deterministic
Host routing helper, not another model reminder. Reuse existing token-recorded
trial arguments, exact actor/session/candidate/run/prior-digest corroboration and
actual approved-write evidence. Structural history IDs only fail closed; history
text never grants permission/proof. Empty/omitted arguments inherit; a matching
subset retains all other inputs, and a contradiction refuses. Read/card paths keep
their existing approval semantics; a new write trial still needs normal approval.
No state field, default change, budget reset or successful side-effect replay.

### Reject mixed initial paginated observations (2026-11-10)

A local causal fixture proves the initial read could sample old final-page rows
then new1/1 paginator values and return them together. Bracket rows with paginator
observations and reuse the existing settle interval to accept a stable whole
snapshot under one retry/sleep deadline. Retain strict stable non-start, max-page,
key, truncation and origin refusals and dispatch no UI action for this check.
This is a consistency check, not evidence that the application's query completed;
Workflow readiness still needs actual page evidence. Existing blocking CDP calls
keep their transport timeout, so this is not a new strict per-command time cap.
### Wait for fresh query transport before collecting rows (2026-11-10)

Actual C4C acceptance showed stable old rows could survive a new Go click and pass
DOM settling checks. Add one generic Browser `click_wait_network` action: arm a
bounded private observer immediately before one native trusted click, then require
fresh successful scoped main-frame same-origin XHR/Fetch completion and quiet.
Use Chromium CDP monotonic timestamps with verified common TimeTicks origin,
never Python wall time. Retain bounded metadata only, with no response bodies,
headers, full URLs or query strings. Lost, malformed, overflowing or out-of-scope
evidence refuses; no click replay or JavaScript click fallback. Existing origin,
policy and action deadline checks remain. Old pre-arm failed/cancelled requests
end their pending state but cannot certify fresh completion.

Stable DOM alone and longer sleeps were rejected because actual formal revision58
returned the previous28 rows while the new760-row query was still completing.
Transport completion does not prove business query identity or rendered content;
independent source count/date/mapping/FX/workbook reconciliation remains required.
Native revision59 passed changed-input28 and formal760 independently after AEP
selected the new action itself. No site-specific route or business code enters
the shared Browser runtime.

### Require Skill-first evidence and owner consent for harness changes (2026-11-10)

The owner instructed: before every harness modification, establish that changing
the Skill cannot improve the behavior and obtain the owner's consent. Adopt this
as AGENTS rule22, architecture guidance, the shared planning/architecture skills
and CLAUDE entry point. Examine Skill selection/content first; provide an actual
evaluation or causal impossibility argument, minimal code/behavior scope and
regressions, then ask before editing. General task approval is insufficient;
scope expansion needs fresh consent. Harness classification follows behavior
(routing/context/state/model-tool dispatch/retries/verification/permissions), not
filenames. Rejected: adding SOP-specific recovery branches to the harness or
claiming that calling a change a bug fix exempts it from approval.

#### Scoped consent: Knowledge/authoring isolation regression

After the specific negative cross-turn behavior was explained, the owner asked
"可以把會影響knowledge asking的部份改掉嗎". This authorizes only repairing the
unrelated-question intake/state/completion interference, retaining actual workflow
trial, approval and verification gates; it does not authorize other harness work.

Skill alternative/evidence: `TaskStore.observe` changes saved question/budget
before routing and model/Skill execution; a test that calls observe without any
model reproduces the mutation. The persistent completion hook can also append an
unfinished-workflow warning after an otherwise identical correct model answer.
Skill instructions can guide the answer/procedure, but cannot prevent those
deterministic pre/post-model mutations or truthfully manufacture missing trial
proof. Therefore a narrowly scoped isolation correction is necessary. New failing
tests preserve callback-disabled baseline and explicit authoring/continuation
gates. Knowledge retrieval/citation code is unchanged. Do not attribute the older
Knowledge intent matcher misrouting to this regression without separate evidence.


The final isolation audit also reproduced the same pre-routing state mutation
for supported direct Knowledge commands and named/inferred Knowledge routes.
Within the owner's existing intake/state isolation consent, Web now records
input history first and defers task reopening to the already selected work
branches; exact existing Knowledge capability targets, named/inferred queries
and /wiki-query retain pending state. No new parser, intent selector, Knowledge
retrieval behavior, permissions or business branch was added. /run retains work
resumption. Other wiki work slash commands now preserve pending authoring state;
their workflow dispatch is unchanged. Rejected alternative: another lexical
command classifier or deleting persistent authoring proof/context entirely.
Final focused171 tests and independent full-slice review passed before starting
the final normal6587-case suite (knowledge-isolation-verified prefix).

Skill-first novice evaluation: the generic SOP development Skill was installed
on the owner's explicit ok using normal approval. Telemetry skill.selected
confirms sop_workflow was actually offered/selected (11 of11 tools, rule provider),
so the three subsequent C4C navigation failures are not attributed merely to
a missing Skill. This does not prove Skills cannot improve navigation: prepare
a narrow SAP C4C navigation/fresh-start procedure Skill instead of changing the
harness. No further C4C retry expansion or business runtime branch is authorized.

#### Domain Skill activation and delivered isolation (2026-11-11)

The owner explicitly approved C4C Skill install card
ap-20261110-184948-7b7722 in this conversation. The normal approval API installed
engineering/sap-c4c-workflow-navigation1.0.1 (c4c_navigation), candidate
sk-20261110-155444-ab60a7 revision2, digest
8b8439bbbd3dc5d102d36cdda71490f6e524046a1c3e12811908379807ed1b48.
The reviewed procedure teaches layered C4C menu/workcenter discovery and source
completeness checks, without business scripts, company records or new grants.
After a fresh idle/interactions guard, the installed service restarted to load
this and the generic SOP Skill. This approval is for that exact Skill, not a
harness modification or final Workflow installation. New novice evaluation uses
the exact original prompt/files; telemetry confirms both Skills were selected.

Model selection and the separately authorized Knowledge isolation were delivered
as commits8cde171f/47f28a6b through the official offline bundle and clean canary.
All559 runtime Python source bytes matched the tested revision in the resident.
Live UI exposed14 Claude Code and8 Codex IDs without inference; a real pending
synthetic workflow question remained byteexact across a factual Knowledge query.
The final full suite initially had6572pass/5fail/10skip; all4 failing modules
rechecked unchanged78pass. Original causes remain partly unproven, so do not
describe the initial suite as clean or weaken assertions to certify delivery.

Skill-selected round3 subsequently completed3failed full trials. AEP independently
authored wf-20261110-191957-9353bc and repaired wait targets twice; failures were
Sales Orders wait, bare All wait, and an obscured navigation click (specific
occluder not established). No Excel acceptance, no final Workflow installation,
no root technical coaching or harness change. Stop at the existing bound.
This still does not prove a Skill alternative impossible: prepare1.0.2 requiring
same-contract wait-predicate preflight and safe actionability diagnosis. Check
passed and normal creator submission produced revision3/digeste99b639a...;
install card ap-20261110-193334-b00427 awaits separate owner approval under
aep-skill-creator step5. Approval of1.0.1 does not authorize new content. Retain
1.0.1 until then; do not restart or run an unapproved Skill revision.

The owner then explicitly instructed「現在是測試，請直接同意使用」for the pending
1.0.2 card. Normal approval API approved ap-20261110-193334-b00427 for exact
digeste99b639afcc8af2c572e781e20f5b7ea87b85e442641098615c271c2c11029f9.
A fresh idle/PID/config guard preceded installed-service restart; installed
source/config remained unchanged and inventory confirmed1.0.2 loaded alongside
generic SOP1.0.0. This is Skill test authorization, not consent to modify harness
or install an unverified final Workflow. New novice round4 uses original prompt
and files; three previous failed drafts were archived then removed through normal
APIs, and generated .aep-run source was archived while reports were preserved.

Round4 environment evidence: actual selected1.0.2/generic SOP guidance, workbook
read succeeded, but original C4C entry produced SAP OpenID then SAML2 errors.
The entry URL was byteexact identical to the previous successful round. A natural
followup reused the owner's automatic-SSO fact, then explicitly requested one
fresh entry reopen. AEP actually called open+inspect_dom; the page still reported
CX_SAML20_ASSERTION: The assertion has already been consumed. This establishes
an authentication blockage in the current browser, not a proven server-side root
cause or a passed/failed1.0.2 navigation evaluation. No login configuration was
changed or safety bypass attempted. Preserve needs_input/authentication_required
and the plan; stop rather than repeating the same login attempt or modifying
harness. Own driver60833 closed; resident idle. Resume after SSO access recovers.
