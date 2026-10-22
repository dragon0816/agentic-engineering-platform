# Foundation contracts (0.1)

All boundary models reject unknown fields, validate defaults, and serialize with
Pydantic `model_dump_json` / `model_validate_json`. Metadata is frozen; Registry
ingress revalidates and stores serialized snapshots so caller mutations cannot alter
registered assets. Pydantic is a validation dependency, not a provider contract.

## Hermes validation lifecycle

`ValidationRequest` is a serializable, non-secret request for a bounded remote
validation run. It pins an exact scoped capability, 40-character package commit,
build and test profile; it also names the Bridge/actor and declared grants,
model-routing and Knowledge prerequisites. These fields are preflight assertions,
not grants or runtime configuration. At least one unique acceptance criterion is
required, and Codex repair/Hermes retest limits are explicit bounded integers.

`OwnerDecision` records a named business/policy decision with evidence. Its
approval does not modify a grant, model route or Knowledge integration; Hermes
re-runs the same preflight before continuing. The GitHub transport is documented
in `docs/archive/hermes-validation-lifecycle.md` and uses versioned JSON payloads rather
than executing Issue text.

## Local Codex Telegram coordination

`TelegramControlConfig` binds one dedicated Coding Agent bot to an exact
repository, owner numeric user id, Validation Agent numeric bot id and shared numeric chat
id. Its credential is a `SecretRef`; the bot token is resolved from the execution
environment for each Bot API call and is absent from the serializable contract.
Owner, Hermes and chat identity have separate meanings. An entirely absent
four-value configuration disables the optional channel. A partial configuration
is invalid but cannot stop the GitHub worker.

`ValidationControlEvent` is a closed `aep-agent-coordination/v1` notification with an
exact repository, request id, target SHA, bounded event id and `hop=0`.
Only the configured bot, reporting `is_bot=true` in the configured chat, may
supply one. Validation-result events name an Issue, which the receiver reads
from GitHub before acknowledging it,
persists the Bot API offset and a bounded event-id set, and emits at most one
`aep-agent-coordination-ack/v1` with `hop=1`. Acknowledgements are terminal and
cannot become new events. Unknown fields, arbitrary text, other chats and other
senders have no execution effect.

A `mechanism_blocked`, `mechanism_update` or `mechanism_resolved` event instead
carries one closed `MechanismProblem`: code, summary, expected and observed
mechanism behavior, bounded evidence references and the requested response type.
It does not need a GitHub Issue because it cannot authorize implementation work.
The Coding Bot persists the last 20 mechanism records and returns a deterministic
next state: coding-agent review, continue coordination or resume validation. If
the unresolved blocker code is exactly `MODEL_ROUTING_NOT_CONFIGURED`, a bounded
handler emits one `MechanismGuidance` with schema
`aep-agent-coordination-guidance/v1`, action
`provision_profile_model_routing`, next action
`retry_same_validation_request` and `hop=1`. The event id is durably deduplicated,
including blockers retained by a pre-handler worker. The action means the
Validation Agent may provision only the credential-free model fixture declared by
its already allowlisted profile and retry the same request. It is not a model
grant or arbitrary configuration authority. Unknown codes remain review-only.
If review finds an implementation change is required, the Validation Agent
creates the typed GitHub Issue before code changes begin. Telegram prose never
becomes a Codex prompt.

The owner may issue only `/status` or `/status <issue-number>`. The command reads
GitHub queue/Issue state and never changes labels, comments, branches or PRs.
`aep-telegram-worker-event/v1` reports `running`, `waiting_evidence`, `failed` or
`completed` on a best-effort basis. Telegram is an immediate coordination layer;
`codex-local-request/v1`, GitHub comments and labels remain the durable authority.
No Telegram message starts Codex directly, provides a shell command or grants
merge authority.

## Phase 7 enrollment boundary

`Invitation` is non-secret metadata for one named actor. A host validates the
out-of-band invitation proof before calling the reference registry; no password,
token or session is represented. `PlatformUser` and `BridgeDevice` have independent
active/disabled lifecycle. `BridgeBinding` grants use of one Bridge only, while
`BridgeExecutionSubject` makes actor and device explicit on new work.

`company_workstation` requires a dedicated Windows user, corporate resource scope,
single-user local boundary and one active platform member. `shared_test_workstation`
requires a shared Windows user, external-only scope, cooperative workspace and one
interactive slot. Since slice 2j it too has exactly one active platform member: a
virtual member of its own, which the employees who need its instruments reach
through an ingress. Cooperative workspace is organizational separation, not
confidentiality from users of the same OS account.

`InMemoryEnrollmentRegistry` demonstrates invitation acceptance, device enrollment,
membership and use-time checks. It is not an authentication server, RBAC server,
session store, installer or durable database. Enrollment never grants a capability,
resolves a SecretRef or authorizes a side effect.

- `AssetIdentity`: namespace/name/full SemVer tuple, exact and case-sensitive.
  Namespace and name use lowercase slugs. Versions include prerelease/build metadata;
  no implicit latest-version resolution. Owner and visibility are independent fields.
- `AssetMetadata`: identity, owner, contributors, lifecycle, provenance, package
  dependencies, compatibility, separate business review and technical policy,
  evaluation/validation references, and optional deprecation/replacement metadata.
  Review records are descriptive claims, not verified signatures or permission grants.
- `ExecutionDependencies`: local capability names, central services with explicit
  required flags, and required `central_required`, equal to whether any service is
  required. Local execution may still require a central service. No resolver exists.
- `SecretRef`: symbolic name only. No values, credentials or backend configuration.
  Closed schemas reject secret-bearing extra fields; Registry assets recursively reject
  common credential assignments, bearer tokens and private-key markers in text.
  This is practical validation, not a guarantee of detecting arbitrary secrets hidden
  in prose. Callers must never submit secrets; errors should not be logged with inputs.
- `TaskManifest` and `WorkflowManifest`: metadata plus execution requirements,
  schema references and scoped capability/step identities. No embedded scripts.
- `CapabilitySpec`: scoped identity, input/output contract references and explicit
  read/write/execute/external_side_effect classification with policy requirements.
- `RequestContext`, `RouteDecision`, `CapabilityResult`, `WorkflowRun`,
  `ApprovalRequest`: traced typed boundary messages. Runtime execution authorization
  is a separate default-deny `ExecutionAuthorization`, never inferred from publication.
- `KnowledgeSource`: immutable source reference/checksum and page/slide provenance.
- `AgentProfile`: governed profile with allowed capabilities, Skills, Knowledge,
  delegation extension points, policy constraints and bounded model requirements.
  Only an engineering profile is supplied; no runtime loop or specialist is built.
- Model requests/responses use logical aliases, typed messages, tool calls and image
  references. Generation, selection and streaming are protocols without adapters.
- Evaluation cases declare requests, expected routes and forbidden side effects.
- Bridge registration advertises installed Tasks/capabilities and local resources;
  it neither downloads assets nor authorizes or executes them.

`TaskRegistry` stores validated/published Task manifests and supports exact get and
explicit discovery filters. The in-memory adapter only exposes published records to
discovery, rejects duplicate identities, and returns stable ordering. Visibility is
filter metadata, **not access enforcement**: this fixture must not be exposed as a
multi-user service. Authentication, review verification, transition workflows, RBAC,
availability checks and compatibility resolution are deferred.

`DeterministicRouter.resolve` returns a known route or `None`; callers must try it
before model selection. It has no model dependency. A route is intent, not authority.
No source command parser or runtime is migrated in Phase 1.

## Phase 2 installed routing and execution boundaries

- `AttachmentRef` adds optional opaque file context to `RequestContext`. No path
  resolution, upload or automatic attachment inclusion in model prompts occurs.
- `SkillManifest` holds governed procedure text, command bindings, ordered keyword
  rules and an explicit default. `SkillRegistry` accepts host-installed manifests;
  one alias per namespace selects an exact version. Regex rules are trusted install
  configuration, not arbitrary untrusted Registry/model input. They require review
  for excessive matching cost; no regex sandbox is provided.
- `CommandRouter.match/resolve` applies source dot-command/keyword precedence;
  `direct` uses the named Skill's rules/default. `RequestRouter.route` uses at most
  one `ModelClient.generate` on unmatched text and validates the proposed target
  against the installed catalog. Workflow results are route intent; the Phase 3
  Gateway dispatches them to the workflow engine. A route has no authority to execute.
- `InstalledCapabilities.register` binds a reviewed `CapabilitySpec`, async handler,
  input/output model classes and explicit dependencies. No module loading or code
  supplied by a Registry asset is accepted. This is an execution-plane catalog,
  separate from the Team Platform's `InMemoryTaskRegistry`.
- `LocalPolicy` uses trusted host-configured actor/asset `CapabilityGrant` records.
  Permission and policy references must cover the capability's declared requirements;
  required execution approval needs a separate host approval reference. The host
  authenticates the context actor; this in-process policy is not an authentication
  server, signed approval verifier or security boundary against hostile Python code.
  Grants must never be parsed from tool arguments, model output or published metadata.
- `BridgeExecutor.execute` revalidates invocation context, enforces policy, checks
  declared local/central availability, then validates typed inputs and invokes the
  handler. Missing secrets fail as unavailable (no resolver). Host-supplied service
  availability is a snapshot, not an active probe. There are no automatic retries.
  Async timeout uses cooperative cancellation; it cannot undo a side effect or
  preempt blocking/suppressed-cancellation code. The one shipped production handler
  (`filesystem/read-file`) therefore offloads its blocking filesystem I/O to a worker
  thread and confines reads to a host-configured root; any future production handler
  must do the equivalent.
- `ExecutionEvent` stores trace/target/status/error code only, never arguments,
  attachment content, provider errors or returned data. Results retain caller traces.
- `MCPAdapter` wraps a host-supplied `MCPClient` with bounded discovery and explicit
  per-tool binding. Wire transport/session/auth configuration remains outside platform
  contracts. `MCPTool.input_schema` is remote metadata; the host selects reviewed local
  model classes for validation rather than executing or trusting remote schemas.
  Callbacks run only through authorized Bridge dispatch. Client errors are sanitized.

All changes are additive to Phase 1. Source fidelity and intentional security changes
are documented in `PHASE_2_MIGRATION.md`; production source paths remain active.

## Phase 3 workflow inputs

`InstalledWorkflows` installs exact scoped versions, independently of Registry
publication. `WorkflowEngine` dispatches ordered steps through `BridgeExecutor`;
each step retains input/output validation, dependencies and execution authorization.
`Gateway.handle` uses this same engine for deterministic and model-selected routes.

`WorkflowManifest.steps` accepts either an existing `AssetIdentity` (all run
arguments passed through) or a `WorkflowStep` with `capability` and required
`inputs`. Explicit inputs replace, rather than merge with, the run arguments;
`inputs: {}` sends no fields. Input names are capability input field names.
Each value is a discriminated reference:

```json
{
  "capability": {"namespace": "sample", "name": "count", "version": "1.0.0"},
  "inputs": {
    "count": {"source": "step", "step_index": 0, "path": ["count"]}
  }
}
```

This step consumes `data.count` from step 0 of the current run. Only earlier
successful steps may be referenced. To select run arguments instead, use
`{"source": "run", "path": ["items", 0, "count"]}`. Strings are exact object
keys (dots/slashes have no special meaning); nonnegative strict integers are
zero-based array indices. Empty or omitted `path` selects the whole source.
JSON null is present data and still must satisfy the target capability contract.
Literal values, expressions, cross-run references and secret resolution are not
supported; ordinary configuration values belong in run arguments.

All run references are checked before starting any step. Missing keys, out-of-range
indices or wrong container types return `needs_input/workflow_input_missing` with
no stored run. Missing output paths stop the running workflow with that code;
prior completed steps/results remain, and the unresolved step is not dispatched.
Wrong selected value types still return the Bridge's `failed/invalid_input`.
No later step runs after failure. `needs_input` is a terminal state for this run,
not resumability or permission to automatically retry prior side effects.

Run arguments, installed manifests and returned snapshots have separate ownership;
selected values are copied. Logs contain no input paths, arguments, result payloads
or exception text. Run snapshots contain validated outputs and require the same
caller access controls as capability results. Caller-wait timeout semantics remain
unchanged: execution continues and the eventual result replaces the timeout state.
History remains in memory (50 runs), with bounded logs (5000 lines plus marker).

## Phase 3 retry and duplicate-submission boundaries

`WorkflowStep.retry` is a `RetryPolicy`: `max_attempts` (strict integer 1–3,
default 1) and fixed `delay_ms` (strict integer 0–10000, default 100). Legacy
identity-only steps always run once. The engine preflights any multi-attempt plan
against host-installed `CapabilitySpec.side_effect`; only `read` is eligible.
Write/execute/external-side-effect plans fail `unavailable/unsafe_retry` before
starting a run. A published workflow cannot assert its own retry safety.

A trusted handler may raise `TransientCapabilityError`. The Bridge sanitizes it
to `failed/transient_failure`, with `Failure.retryable=true` only for reads.
The engine retries only this failure, within the declared limit. Unknown errors,
timeouts (including potentially still-running offloaded work), invalid input/output,
policy denial, missing dependencies and needs-input never retry. The Bridge itself
still invokes handlers once per call. Every attempt repeats authorization and
validation with a separate copy of the same selected inputs. Successful prior
steps are never repeated; output references see only each step's terminal result.
`WorkflowRunSnapshot.attempts` contains typed `StepAttempt` metadata (zero-based
step index, one-based attempt, status, optional failure code), never payloads.

`WorkflowEngine.execute(..., idempotency_key=...)` optionally suppresses duplicate
submissions. Keys are 1–128 ASCII letters/digits or `_.:-`, scoped by requesting
actor and namespace **within one engine instance on one event loop**. Same key
reuses the same in-flight or finished run if exact workflow identity, arguments
and non-trace RequestContext match. Object key order is ignored; other differences
fail `needs_input/idempotency_conflict` without execution. The returned run and
results retain the original trace. A key is not a permission grant: replay checks
current authorization for all workflow capabilities before/after waiting. Denied
replay returns no cached data. The host must authenticate actors as before.

Keys are reserved before execution without an intervening await. Preflight
rejections do not consume keys. Failures/cancellation and history eviction never
release a key, since earlier steps or interrupted handlers may have caused effects.
The table retains up to 50 entries for the engine lifetime; a new keyed submission
at capacity fails `unavailable/idempotency_capacity`. Existing keys still work,
and unkeyed submissions remain independent new runs. There is no expiry or silent
eviction. Data fingerprints and keys are not logged. Caller-wait timeouts leave the
original run alive; a duplicate may join it with its own wait timeout.

`Gateway.handle(..., workflow_idempotency_key=...)` forwards this host/caller
option for workflow routes. It is never taken from model arguments or asset
metadata. Supplying it to a direct capability route fails
`unavailable/idempotency_not_supported` without dispatch; unresolved routes remain
unexecuted. Gateway routing itself is not cached; changed model-selected intent
conflicts rather than starting different work under the same workflow key.

This is bounded in-memory duplicate suppression, **not durable exactly-once
execution** or backend idempotency. Restarting/replacing the engine loses keys;
using a new/no key intentionally permits a new execution. No automatic workflow
retry, side-effecting retry, crash recovery, cross-process coordination, persistent
storage or production idempotency backend is provided. Do not silently restart an
engine to clear capacity for a retried external request.

## Phase 3 bounded resumption

`WorkflowEngine.inspect(run_id)` returns a `ResumePlan` for a retained run (None
for unknown or evicted runs): one `StepStateRecord` per declared step, in order,
classified from recorded evidence only. `completed` is a terminal success whose
result is retained. `never_started` means no handler ran: the Bridge records
`CapabilityResult.handler_invoked` (and `StepAttempt.handler_invoked`) the moment
it invokes a handler, so a step whose every attempt was rejected before that
point (authorization, input validation, dependency or installation checks) or
that the engine never dispatched (`workflow_input_missing`) had no effect.
Everything else is `uncertain`: any attempt invoked the handler without a
terminal success (`handler_error`, `transient_failure`, `timeout`,
`invalid_output`, a later denial after an earlier attempt ran), or the run was
interrupted at that step (`workflow_aborted`, `workflow_error`). A live run
reports `status: running` with its in-flight step `uncertain` and no code; the
caller-wait overlay is not evidence. Records carry indices and codes, never
payloads. `next_step` is the first non-completed step, or None when nothing
remains. `inspect(context, run_id)` requires the requesting context: runs owned
by another actor/namespace are indistinguishable from unknown ones (None).

`WorkflowEngine.resume(context, run_id, policy=ResumePolicy(...))` continues a
**finished** run as a new run from `next_step`, sharing history, log and
caller-wait timeout semantics with `execute`. Completed steps are never repeated;
their recorded results feed later `StepInput` references. The original run is
immutable history and the new `WorkflowRun.resumed_from` names it, so resumed
runs can be resumed again. `ResumePolicy.uncertain` is a trusted caller/host
option, never model output or manifest metadata: `reject` (default) returns
`needs_input/uncertain_side_effect`; `replay_read_only` replays the uncertain
step only when its host-installed capability is classified `read`;
`replay_side_effects` explicitly accepts a possible duplicate side effect.

Resumption grants nothing. Runs owned by another actor/namespace return None
like unknown or evicted runs; the retained manifest that drove the run is
reused and must still be installed; the workflow's pre-flight checks rerun,
including `StepInput` references into completed results; every remaining step is
re-authorized by `LocalPolicy` before a run record exists and again at dispatch;
and a running (`run_active`) or complete (`run_complete`) run cannot be resumed.
A run can be continued once: a second resume of the same original fails
`needs_input/already_resumed` (resume its continuation instead), so a retried
host call cannot re-execute never-started side effects. Pre-flight rejections
create no run record. Idempotency keys are neither consulted nor consumed by
resumption; a keyed re-submission still returns the original run. This is
in-memory resumption within one engine instance — no durable step state, crash
recovery, persistence or Gateway trigger is provided.

## Phase 3 Gateway run control

`Gateway.inspect(request, run_id)` and `Gateway.resume(request, run_id,
policy=ResumePolicy(...), workflow_timeout_seconds=...)` are the host-facing
entry points for run control, so CLI, Agent runtime and a future n8n adapter
continue runs through the same Gateway and engine contracts as routed workflows.
`Gateway.suspend(request, run_id, confirmation)` and
`Gateway.retire(request, run_id)` complete the set. Each returns
a `RunControlResult` (`action`, `run_id`, `source`, `plan` for inspect, suspend
and retire, `workflow` snapshot for resume, `suspended_by` when the durable record
carries a confirmation); `source: unknown` with no payload means the run is
unknown to this caller, exactly as the engine reports it.
`RunControlResult.run_id` always echoes the requested
id; a successful resume's continuation has its own id in `workflow.run.run_id`
(with `resumed_from` naming the original), and that continuation is what to
inspect or resume next. `source` says which evidence answered: `memory` is this
process's run history, `journal` is the durable record that outlives it, and
`unknown` means the run is unknown to this caller — missing, evicted, never
journalled or owned by another actor, all indistinguishable on purpose.
`inspect` answers from the durable record whenever it exists — it alone knows
whether a run was suspended or already continued — and from this process's
history otherwise, so a run that predates a restart is still reachable. `suspend` records a person's
`SuspensionConfirmation` against the durable record and is only meaningful for a
journalled run; a run that is alive here or already suspended raises the
engine's own closed code rather than a vocabulary invented at this layer.
`resume` continues a journalled run through recovery — so its continuation is
journalled too and the durable "continued once" guard holds — and any other run
in memory. `retire` removes durable history that is no longer executing (a succeeded run,
or a suspended run, continued or not) and reports the plan of what went; the store's
closed code says why anything else is refused, and a retired idempotency key can
never execute again (`key_retired`). `inspect`, `suspend` and `retire` are synchronous and do their
durable I/O on the calling thread, so a host already inside an event loop should call
them through `asyncio.to_thread`; `resume` is asynchronous like `execute` and
offloads that I/O itself.

The Gateway adds no authority and parses nothing: ownership, pre-flight checks
and per-step re-authorization stay in the engine, and `ResumePolicy` is a
host/caller option that is never derived from the request message or a model.
Run control is not a Skill route: `Gateway.handle` cannot inspect or resume a
run, a model proposing such a route fails closed like any other invalid
proposal, and routed workflow arguments are ordinary step inputs. `run_id` is a
`RunId` (the same `Symbol` shape the engine generates, shared from
`common/execution.py` for CLI/n8n adapters): a mistyped but well-formed id is
unknown, not an error, while malformed input fails validation loudly.

## Phase 3 progress streaming

`WorkflowEngine.watch(context, run_id)` and `Gateway.watch(request, run_id)`
return an async iterator of `RunProgress` events for the run's owner, or None when
the run is unknown to this caller (missing, evicted or owned by another actor).
A live run yields a `snapshot` of its current state, then `step_started` /
`step_finished` per remaining step and finally `finished` with the terminal
status and code; the stream then ends. A finished run yields exactly one
`snapshot` with its terminal status and code. There is no event for launch: a
watcher can only attach once a run id exists, and the initial snapshot covers
everything before it attached.

Events carry `sequence`, `run_id`, `workflow`, `event`, `status`,
`completed_steps`, optional `step_index` and `code`, and `lagged`. `sequence`
advances once per delivered state change; snapshots and rejections describe
existing state and reuse the current value. Events never carry arguments,
payloads or exception text, and a live run is always `running` (the caller-wait
timeout overlay is not evidence).

Reporting never changes a run's outcome. Each watcher has a bounded queue
(`WorkflowEngine(watch_queue_size=256)` by default, minimum 2); when it is full,
new events are dropped and the next delivered event has `lagged: true`, meaning
the consumer should re-`inspect` rather than trust continuity. The terminal
event always arrives (older queued events are dropped to make room), so a
consumer cannot hang. At most 16 watchers per run; a further `watch` returns a
single `rejected/watch_capacity` event. The returned `ProgressStream` is an
async iterator with `aclose()`; ending it, closing it or dropping it — even
before the first iteration — releases its slot. Streams are
in-memory and end with the run; there is no persistence, replay history,
transport or dashboard. `Gateway.watch` validates the `RunId` shape like
`inspect`/`resume`: malformed ids fail loudly, well-formed typos are unknown.
## Phase 3 optional n8n adapter

`Gateway.execute_workflow(context, workflow, arguments, ...)` is the exact-target
host entry point; routed workflows use it too. It forwards to the existing engine
without message parsing, model calls or authority changes. Timeout and idempotency
options match routed workflow execution. It returns WorkflowRunSnapshot directly.

The offline `integrations.n8n` adapter (`N8nAdapter`, `N8nSubmission`,
`N8nWorkflowBinding`) was removed on 2026-10-17: AEP does not integrate n8n.
## Checkpoint persistence boundary (Phase 3 slice 9)

`common.checkpoints` defines owner-scoped RunCheckpoint/StepCheckpoint v1 and
PayloadRef. `workflow.checkpoints.CheckpointStore` defines atomic create, revision
replacement and continuation reservation; MemoryCheckpointStore is only an
isolated bounded reference model, not the engine's storage backend.
See [Workflow checkpoints](WORKFLOW_CHECKPOINTS.md) for ordering, retention,
manual recovery and failure contracts. No existing runtime gains restart durability.

`SqliteCheckpointStore` (`workflow.checkpoints_sqlite`) is the durable
single-writer backend for that protocol: one local SQLite file per Bridge, one
transaction per write acknowledged only after commit, `unavailable` for a known
non-commit and `commit_unknown` when the acknowledgment was lost (read back
before proceeding), a refused rather than waiting second writer, and evidence,
keys, links and capacity that survive a restart. The shared transition rules in
`workflow.checkpoints` keep it and the memory model identical in behavior.

`PayloadStore` (`workflow.payloads`) is the storage half of that boundary.
`put` stores a record of owner, contract and payload and returns the
`PayloadRef` a checkpoint records: `ref_id` is `payload-<digest of the record>`,
`sha256` is the digest of the payload value. `get` returns the payload only when
the identifier is one this store issues, the bytes still hash to it, the owner
recorded inside the file is the requesting owner, the payload hashes to
`ref.sha256` and the contract matches — otherwise `invalid_transition`,
`unavailable` or `missing`, never a guess. `FilePayloadStore` writes atomically,
rewrites a file that no longer hashes to its name, and deletes nothing.

`RunJournal` (`workflow.journal`) is the optional durable half of
`WorkflowEngine`: `begin`/`step_started`/`step_completed` implement the
write-ahead ordering (a step is never dispatched without an acknowledged
`started`, and never recorded complete before its payload is committed), while
`inspect_journal`, `suspend` and `recover` on the engine expose manual restart
recovery. `SuspensionConfirmation` records a person's explicit claim that the
owning process stopped; the operator and note are written into the checkpoint,
which requires them for every suspended record, and nothing probes processes or
takes leases. Recovery requires the stored manifest to still be installed and
identical, restores the completed prefix from verified payloads, and
re-authorizes every remaining step. On a journalled engine the in-memory
`resume()` is refused (`use_recovery`), because the durable "continued once"
guard is reserved by `recover()` alone.

## Knowledge vault (Phase 4, slice 1)

`knowledge.vault` is the safety model every later knowledge slice writes
through. The layout is a contract: `drop/` and `raw/` are immutable
(`immutable_area`); writes are confined to the `wiki/` area and to exactly the
files `index.md`, `log.md` and `decisions.md` (`outside_writable` otherwise —
`index.md.bak` is not `index.md`); a path with `..`, a drive letter or nothing
at all is `escapes_vault`. `Vault.write` runs the same layout check on the
*resolved* location too, so a link inside `wiki/` that points at `raw/` is
refused as `immutable_area`, and a directory target is `unwritable_target`.
`Vault.read` refuses to leave the vault as well. Every overwrite is backed up
under `.ingest-backup/<stamp>/<path>` first; a stamp is one path component
(anything else is a `ValueError` before any write), and an automatic stamp
carries microseconds so two applies never share one.

`WritePlan` is what one ingest proposes: `source` (a `KnowledgeSource`, the
provenance the `wiki/sources/` page must carry as `source_id:` and
`source_sha256:` frontmatter lines), whole-page `pages` (`create`/`update`,
never a diff), `index_entries` per section, a `log_body` and `contradictions`.
`check_plan` returns closed `PlanProblem` codes — `no_pages`,
`no_sources_page`, `missing_provenance`, `outside_wiki`, `escapes_vault`,
`duplicate_path`, `empty_content`, `path_in_wikilink` — and `Vault.check_against`
adds the rules that depend on the vault's state: `unwritable_target` (with the
refusal code as detail), `create_exists` for a `create` that would replace a
page, `update_missing` for an `update` of a page that is not there. Any problem
rejects the plan whole, before anything is written.
Before validation, `repair_wikilinks` fixes the two unambiguous link mistakes
(a path becomes the bare page name; `[[A / B]]` becomes `[[A]] / [[B]]`) and
`ensure_conflicts_visible` writes a reported contradiction onto an entity or
concept page as a `⚠️` block, so it is seen where a reader meets the claim.

`Vault.apply(plan, mode="dry_run"|"apply", today=, stamp=)` returns a
`VaultOutcome`: `written` (what was, or would be, written — `index.md` only
when there are entries), `backed_up`, `repairs`, `conflict_marker_added` and
`problems`. A dry run — the default — writes nothing and lists exactly what an
apply would write; a rejected plan writes nothing in either mode, and the
contract refuses an outcome that claims otherwise. An apply is whole or not at
all: what every target held before is kept in memory, and a write that fails
part-way puts it all back and raises `write_failed`. Nothing in this module
calls a model.

## Drop → Raw (Phase 4, slice 2)

`knowledge.raw` turns an original under `drop/` into a Raw Markdown file that
carries its own provenance. **Identity is the content**: `source_for(bytes,
original_ref)` derives the `sha256` and a `source_id` (`src-<16 hex>`) from the
bytes, so the same original dropped under two names is one source and a
changed original is a new one; the path-keyed dedup of the source tooling is
not migrated.

`RawSection` is one extracted unit — `kind` `text` / `table` / `image`, its
text, optional `page` and `slide`, and an `image_ref` under `raw/` exactly for
images (an image may also carry a description in `text`). `RawDocument` is a
document-level `KnowledgeSource` whose `raw_ref` names the file (no page or
slide at document level — sections carry those), the `extractor` that produced
it, `created`, and at least one section. `render` writes the file: provenance
as frontmatter (`source_id`, `source_sha256`, `original_ref`, `raw_ref`,
`extractor`, `created`) and each section behind a numbered
`<!-- raw-section N kind=… page=… slide=… image=… -->` marker; `parse` reads it
back and the two round-trip exactly for any text: a body line that would read
as a marker is escaped with a backslash on the way out and unescaped on the
way in, and every line ending is `\n` (CRLF and lone CR are normalized on
entry, and the file is written with `\n` on every platform). An image
reference is normalized and carries no whitespace. A Raw written for an
original that drifted also records `supersedes: <source_id>`, so the chain of
versions is in the files themselves.

`Vault.write_raw(rel, content)` is the only way the platform writes under
`raw/`: it creates exclusively (`open("x")`) and never replaces (`raw_exists`,
even under concurrent writers), refuses anything outside `raw/` (`outside_raw`)
and a resolved location that leaves it. Raw is immutable
in the only sense a pipeline can honour — write once, never change. `drop/` is
read through `Vault.read_original` (`outside_drop`, `missing_original`) and
never written.

`DropIntake(vault, extractors).intake(drop_rel, mode, today)` returns an
`IntakeOutcome` whose `status` is closed: `written` (a new Raw file at the path
derived from the drop path), `duplicate` (the content is already in Raw —
nothing written, the existing `raw_ref` and source reported), `drifted` (the
same `original_ref` is in Raw with other content — the old Raw stays, the new
one is written beside it as `<stem>--<8 hex>.md`, and `supersedes` names the
old source — the *latest* one, found by following `supersedes` links, however
many times it drifted), `unsupported` (no extractor for the suffix),
`undecodable`, `empty` or `unrepresentable` (the extractor produced something
the contracts refuse — a closed status, never an escaping exception). Paths are
canonical (`drop/./d.txt` is `drop/d.txt`), so equivalent spellings are one
identity. Dry run is the default and reports exactly what an apply writes —
including the hash-suffixed name, which is escalated past any file already
there. The contract refuses an outcome whose payload does not match its
status. `intake_all` runs a batch over one index scan, and a dry-run batch sees
its own would-be writes. Extraction
is behind the `Extractor` protocol (`name`, `suffixes`, `extract(bytes)`);
`PlainTextExtractor` and `MarkdownExtractor` (which drops the original's own
frontmatter) ship with no new dependency. `RawIndex.scan` reads only the head
of each Raw file (`Vault.read_head`, stopped at the closing `---`) and skips
any file without this provenance or whose head cannot be decoded, so an
existing vault's content — in any encoding — is never a reason to fail, nor
rewritten.

## Office extraction (Phase 4, slice 3)

`knowledge.office` adds `PdfExtractor` (`.pdf`), `PptxExtractor` (`.pptx`) and
`DocxExtractor` (`.docx`) behind the `Extractor` protocol, as the optional
extra `office`. The protocol gained an `AssetSink`: `extract(data, assets)`
hands image bytes to `assets.put(data, suffix)` and receives the `image_ref`
to carry; an extractor never writes. `StagedAssets` is the intake's sink — it
names each asset by content under the Raw document's own directory
(`raw/notes/hello.md` keeps its images under `raw/notes/hello/assets/`), and
the intake lists those refs in `written` and writes them only on apply through
`Vault.write_raw_bytes`, which creates exclusively, treats the same bytes at
the same name as a no-op and refuses different bytes (`raw_exists`).

Sections keep their relationships: PDF text and images per `page`; PPTX text
frames, tables and pictures per `slide` in shape order, descending into groups
and including pictures placed in placeholders, then the slide's speaker notes
as one more text section on that slide whose first line is `Speaker notes:`
(none when the notes are empty; added 2026-10-19 as extractor `pptx.v2`, Raw
written by `pptx.v1` is not rewritten); DOCX paragraphs (headings
become Markdown `#`), tables and inline pictures in body order — content
controls (`w:sdt`) included, and pictures inside table cells following their
table — with no page. `table_markdown` renders a GitHub-style table with cells
flattened to one line and pipes escaped.

Two error rules. A corrupt or unreadable *original* is `undecodable`, mapped
from the parsers' documented error types (their base classes plus the
standard-library errors broken streams raise) with the cause chained. An
unreadable *image* inside a readable original — a filter pypdf cannot decode,
a linked rather than embedded picture — is skipped, not fatal: the text is
still evidence. Known limitations: PDF tables arrive as text in reading
order, a skipped image leaves no trace
in the Raw file, and images are stored as the library provides them (pypdf
converts raw image streams to PNG, which needs its `image` extra — declared).

## Image description (Phase 4, slice 4)

`knowledge.describe.ImageDescriber(model, alias=, prompt=, max_output_tokens=,
max_bytes=)` describes one image per request through `models.contracts.
ModelClient`: a `ModelRequest` with `ModelRequirements(vision=True)` and a
single user `ModelMessage` whose `images` holds the picture as a `data:` URI
(`data_uri(bytes, media_type)`), so any adapter can consume it without file
access. Every outcome is an `ImageDescription` with a closed `status`:
`described` (with `text`), `too_large`, `unsupported_type` (only PNG, JPEG,
GIF and WebP are sent), `model_failed` (with the model's `Failure` — an
adapter that raises becomes a retryable `model_error`), `empty_answer` or
`missing_bytes`; the contract ties `text` to `described` and `failure` to
`model_failed`. Results are memoised by the image's content for the
describer's lifetime.

`describe_sections(sections, assets, trace_id=)` gives every image section
without text one attempt and returns the updated sections — each described
one carrying `described_by=<alias>`, rendered as `described=<alias>` in its
section marker, so a model's words are never mistaken for the source's — and
the descriptions. `DropIntake(vault, extractors, describer=)` calls it on
apply, after the undescribed document has been validated (so an
unrepresentable one costs no tokens) and before the Raw file is written — Raw
is write-once, so this is the only moment a description can become part of
the document. A drifted original first reuses the descriptions its superseded
Raw holds for identical pictures. The `IntakeOutcome` carries `descriptions`
and `images_to_describe` (distinct images still without text); a dry run
counts and asks nothing. A `model_failed` description stops the write: the
status is `description_failed`, nothing is written, and a later apply retries.
Every other failure writes the document without that image's text.

## Ingest planning (Phase 4, slice 5)

`knowledge.planning.IngestPlanner(model, vault, alias=, conventions=,
max_output_tokens=, condense_over=, chunk_chars=)` turns one `RawDocument`
into a `PlanningOutcome`. `plan(document, today=, decisions=)` runs two passes
through `ModelClient`, each a `ModelRequest` with a system message (the
conventions) and a user message, `ModelRequirements(structured_output=True)`
and an `output_contract` (`knowledge.ingest-relevance.v1`, then
`knowledge.ingest-plan.v1`); a long source is first condensed chunk by chunk
with plain-text requests and the result cached through `Vault.cache_write` /
`cache_read` under `.ingest-cache/<key>.md`, confined to that directory and
keyed (`IngestPlanner.cache_key`) by a hash of the rendered source text, the
chunk size, the prompt and the model alias — everything the condensed text
depends on. A part that comes back empty is a retryable `condense_empty`
failure and nothing is cached.

The answer is read from `structured_output`, or extracted as JSON from fences
or prose (`extract_json`), validated loosely as an `IngestProposal` and then
strictly as a `WritePlan` with the document's `KnowledgeSource`; each page's
`action` is decided by whether the vault holds it (the model is not asked);
a contradiction that only says "none" or "n/a" is dropped; the sources page
is repaired to carry the provenance lines (`ensure_provenance`, tolerant of
CRLF and odd path spellings) and the plan is validated by a vault dry run. `PlanningOutcome.status` is closed:
`planned` (a plan the vault accepted), `invalid` (the plan and its
`problems`), `model_failed` (the `Failure`; an adapter that raises becomes a
retryable `model_error`) or `unparseable`; `relevant`, `condensed` and
`cache_hit` say what happened, on every status. The planner writes nothing
but the cache; the caller applies the plan through `Vault.apply`. Empty
conventions are refused at construction. `Vault.wiki_pages` lists files
only and skips a link that leaves the vault. `source_text(document)` is the
text the model reads: sections in order, each image as
`[image on page N: description]` or `(no description)`.

## Static lint (Phase 4, slice 6)

`knowledge.lint.scan(vault)` returns a `LintReport` computed by reading alone,
and nothing a page contains aborts it: `pages` and `types` (from the `type:`
frontmatter, `(untyped)` otherwise; `head_fields` reads frontmatter leniently,
so lists, blank lines and comments are skipped, not errors),
`orphans` (no inbound link; `wiki/overview.md` and `index.md` are entry points),
`dangling` (`DanglingLink(target, count)`, ranked by references, ties in
first-seen order), `path_links` (`PathLink(page, link)` — a link with a path,
or a `.md` that names a wiki page; `[[CLAUDE.md]]` may name a root file and is
left alone), `missing_frontmatter`, `broken_source_path` (a legacy
`source_path:` that no longer resolves), `unknown_source_id` (a `source_id:`
the Raw index does not know, malformed ones included), `pending_sources` (Raw
files no `wiki/sources/` page carries by `source_id`; a superseded Raw is not
pending), `open_conflicts` (`OpenConflict(page, line, text)` for every `⚠️`
line, a bare marker reported as `(marker without text)`) and `unreadable`
(a link that leaves the vault, or bytes that are not UTF-8). An empty `[[ ]]`
links nowhere and is ignored. `report.clean` is true when every list is
empty.
`page_name` strips only `.md`, never a page's own dots. Nothing in this module
calls a model.

`fix_links(vault, report, stamp=)` rewrites exactly the flagged links to bare
page names, case-corrected to an existing page and keeping any `|alias` or
`#anchor`, through `Vault.write` with a backup under the stamp; only the
flagged pages are read, and it returns the pages it changed. `Vault.write`
and `append` now write `\n` on every platform, so a repair never rewrites a
page's line endings. `raw/` and `drop/` are never written.

## Conflicts and decisions (Phase 4, slice 7)

`knowledge.conflicts.Decision(topic, keep=, reject=, reason=, pages=)` — one of
`keep`, `reject` or `reason` required — is appended to `decisions.md` by
`append_decision(vault, decision, today=)` as `## [date] topic` with `- keep:`,
`- reject:`, `- reason:` and `- pages: [[…]]` lines; the header is written
once and the file is never rewritten. `decisions_text(vault)` is what
`IngestPlanner.plan(decisions=…)` receives: the file's text, or
`(no settled decisions)`.

`open_conflicts(vault)` returns the lint's `OpenConflict` for every `⚠️` line.
`clear_conflicts(vault, page, lines, stamp=)` removes the marker lines of one
page in one write — one backup of the original — and returns the line numbers
removed; a line that does not match the marker rule or has moved is left
alone, and the page keeps its own line endings (`line_ending`).
`clear_conflict` is the one-line form. `resolve(vault, decision, clear=,
today=, stamp=)` refuses a malformed clear list before writing anything,
records the decision, then clears per page and returns a `Resolution` with
`cleared` and `missed`. `NO_DECISIONS` is `knowledge.planning`'s, shared.

`knowledge.lint.ManualEdits` (`first_run`, `since`, `edited`, `added`,
`removed`) is computed into `LintReport.manual_edits` from the pages `scan`
already read. `record_state(vault, today=)` stores every page's hash in
`.ingest-state.json` (`Vault.state_write` / `state_read`, its own file, `{}`
when absent or corrupt); `note_written(vault, written, today=)` refreshes
only the pages the tool just wrote — a host calls it after an apply with the
outcome's `written`, so the tool's writes are not reported as a person's while
a later change to the same page still is; `manual_edits(vault)` compares. An
odd state (blank keys, wrong types) is a first run, never a failure.

## Query with provenance (Phase 4, slice 8)

`knowledge.query.retrieve(vault, question, k=)` returns up to `k` `Passage`s
(`text`, `citation`, `score`) ranked by BM25 over every section with text of
every current Raw (a version another Raw `supersedes` is left out) and every
Wiki paragraph after its frontmatter (`knowledge.lint.body_of`, CRLF
tolerated), ties broken by corpus order so the same question always returns
the same passages. `tokens` lowercases words, splits a word that mixes
scripts so its Latin part stands alone, and turns a CJK run into its
characters, its overlapping bigrams and (beyond two characters) the run.
`cited_numbers(text)` reads `[2]`, `[1, 3]` and `[1-3]`. A `Citation` has `kind` `raw` (the
`KnowledgeSource`, `raw_ref`, `section`, `page`/`slide` when known) or `wiki`
(`wiki_page`, and `source` when the page's `source_id` names a Raw in the
index).

`QueryEngine(vault, model=None, alias=None, prompt=, max_output_tokens=)`
`.ask(question, k=, trace=)` returns an `Answer` (`question`, `status`,
`passages`, `text`, `synthesized_by`, `failure`). Statuses: `retrieved`
(passages, no model), `answered` (text whose every citation names a retrieved
passage), `unanswered` (the text cites nothing — the model saying the passages
do not answer, its sentence kept), `uncited` (refused: a citation outside
`1..len(passages)`), `model_failed` (the `Failure`; an adapter that raises
becomes a retryable `model_error` through `knowledge.modelcalls.
failure_from_exception`, shared with description and planning) and `no_match`
(a blank question included). Synthesis is one `ModelRequest` with the numbered
passages and the question, under the given trace or one derived from the
question and the engine's request count; the model is told to cite every
claim and say so when the passages do not answer.

## Migration adapter (Phase 4, slice 9)

`knowledge.migrate.adopt(vault, mode="dry_run", today=, stamp=, readopt=())`
returns an `AdoptionReport`: `raw_adopted` (`AdoptedRaw(raw_ref, source)` —
legacy Raw files entered into the ledger by content hash, `source_for_legacy`
deriving a `KnowledgeSource` whose `original_ref` and `raw_ref` are the file
itself), `raw_readopted` (drifted files named in `readopt`, recorded at their
current hash), `raw_drifted` (`DriftedRaw(raw_ref, recorded_sha256,
current_sha256)`), `raw_missing` (ledger records whose file is gone, dropped
from the ledger on apply so a new file at that path is new), `raw_skipped`
(`SkippedRaw(raw_ref, reason)` with `reason` `undecodable`, `empty`,
`duplicate` — the same bytes as a Raw already known, the first path winning
— or `invalid_provenance` — a head that claims this platform's provenance
but does not validate, neither typed nor legacy), `pages_migrated`
(`MigratedPage(page, source)` — `source_path:` sources pages given the
provenance lines), `pages_unresolved` (`UnresolvedPage(page, source_path)`),
`pages_unwritable` (`UnwritablePage(page, code)` — resolves, but the vault
would refuse the write, checked by `Vault.check_writable` before anything is
written), `pages_skipped` (frontmatter never closes, or a link that leaves
the vault) and `written`, exactly what an apply writes: the pages, then the
ledger. `snapshot` is set only on an apply that wrote. An apply writes all of
its files or none: what each held before is put back if any write fails, and
the failure is raised as `write_failed`. A stamp names one apply: a second
apply under a stamp that already wrote is refused as `write_failed` before
anything is written. A page is written by `Vault.write` (backup under the
stamp, the page's own line endings kept); the ledger by `Vault.ledger_write`.
`raw/` is never written. `legacy_raw` lists the Raw files without provenance
frontmatter (`knowledge.raw.looks_typed` tells a damaged typed head apart).

The ledger `.ingest-adopted.json` (`Vault.ledger_read` / `ledger_write`, `{}`
when absent or corrupt) maps a Raw path to `{source_id, sha256, adopted}`.
`RawIndex.scan(vault, ledger=True)` adds a `RawEntry(adopted=True, created=
<adopted date>)` for each ledger file whose bytes still hash to `sha256`; a
changed file is left out until re-adopted. `knowledge.raw.load_document(vault,
entry)` returns the `RawDocument` behind any entry — parsed for a typed file,
built by `adopted_document` for a legacy one (extractor `adopted.v1`, one text
section per paragraph, the note's own frontmatter left out by
`strip_frontmatter`); `ValueError` for what cannot be read as a document.
Query cites an adopted file's paragraphs by section number; lint counts an
adopted file among `pending_sources` until a sources page carries its id.

`snapshot(vault, stamp=, label="")` copies the generated half (`wiki/`,
`index.md`, `log.md`, `decisions.md`, `.ingest-state.json`,
`.ingest-adopted.json`) to `.ingest-snapshot/<stamp[-label]>` and returns the
name; an existing name is `write_failed`, a name with a separator is a
`ValueError`. Links are copied as links, never followed, so nothing outside
the vault is duplicated into it. `snapshots(vault)` lists them.
`restore(vault, name, stamp=)` snapshots the current state as
`<stamp>-before-restore`, then replaces the generated half with the named
snapshot (files absent from it are removed); a missing snapshot is
`missing_original`, and a managed directory that is itself a link is
`unwritable_target` before anything is touched. `raw/` and `drop/` are never
part of a snapshot or a restore.

## Model catalog and selection (Phase 5, slice 1)

`models.catalog.ModelCapabilities` declares what one endpoint can do:
`reasoning` (the `Reasoning` literal shared with `ModelRequirements`, so the
two cannot drift), `tool_calling`, `structured_output`, `streaming`, `vision`,
`local` and `max_context_tokens`. It mirrors `ModelRequirements` with two
deliberate differences: `local` states where the model runs, against a
request's `local_only`, and `max_context_tokens` is a ceiling against the
request's `min_context_tokens` floor. The ceiling is **required**, because a
context window cannot be guessed: a silent default would make an endpoint
either unselectable or a liar. `unmet(requirements)` returns every field that
cannot be met, in one canonical order (`reasoning`, the four flags,
`local_only`, `min_context_tokens`); `satisfies` is `unmet` being empty.
`reasoning` compares as an order, so a stronger endpoint still qualifies; each
flag is an implication, so declaring more than asked is fine. Every field of
`ModelRequirements` has a rule here, pinned by a test so a field added there
cannot be silently ignored by selection.

`ModelEndpoint` binds a stable `alias` to a `provider`, the provider's own
`model` id, its `capabilities`, an optional `base_url` and an optional
`credential`. A `base_url` is http or https (the scheme compares
case-insensitively), names a host, contains no whitespace and carries no
userinfo, so `https://user:token@host` is refused. The credential is a
`SecretRef`, a name only. `ModelEndpoint` is a `RegistryContract`, so
recognizable credential material is refused in any field, including a
`?api_key=` smuggled into the URL: no contract in this layer ever carries a
token. `ModelRoute` binds a purpose such as `default` to one alias.

`ModelCatalog(endpoints, routes)` implements the `ModelSelector` protocol.
`select(requirements)` returns the first alias in catalog order whose
capabilities satisfy the requirements, so the same question always selects the
same alias; nothing satisfying them is a `Failure` (`no_model_for_requirements`,
not retryable) naming how many endpoints were considered, the endpoint that
came closest (fewest unmet fields, ties by catalog order) and what that one
lacked, so the message describes a real candidate rather than a union no
single endpoint was blocked by. `select_route(name)` returns that route's alias
or a `Failure` (`unknown_route`). `endpoint(alias)` looks one up. Selection
calls no model, reads no file and opens no socket.

A catalog is validated where it is built: at least one endpoint, no duplicate
alias, no duplicate route name and no route naming an unknown alias, so a
misconfigured catalog fails at construction rather than at the first request.
It is plain serializable data (`model_validate` / `model_dump_json`), so a host
may keep it in any format; the platform chooses no file, format or environment
variable.

## OpenAI-compatible adapter (Phase 5, slice 2)

`models.openai_compatible.OpenAICompatible(endpoint, credential=None,
transport=None, timeout_s=600.0)` implements `ModelClient` for any endpoint
speaking the OpenAI chat-completions format. `ModelEndpoint.base_url` is the
API root and `/chat/completions` is appended; an endpoint without one, or a
non-positive timeout, is a `ValueError` at construction, because neither is a
runtime condition. `credential` is a zero-argument callable resolved on every
request, never captured, since the internal token is rewritten on a schedule;
no credential is passed when it is `None`.

`generate` sends `model`, `messages` and a token limit under
`max_tokens_field` (`max_tokens` by default, `max_completion_tokens` for a
provider that has dropped the older name), plus
`response_format: {"type": "json_object"}` when the request declares an
`output_contract`. The contract's name is a platform identifier and is never
sent. A message with `images` becomes content parts (`text` then `image_url`),
so Phase 4's `data:` URIs work unchanged; a `tool_call_id` is carried through.
The reply always fills `text`, and `structured_output` only when an
`output_contract` was declared and the text parses strictly as JSON; lenient
salvage stays with the caller. `input_tokens` and `output_tokens` come from
`usage.prompt_tokens` and `usage.completion_tokens`, with anything else there
ignored. `trace` and `model_alias` are echoed from the request: a provider's
own `model` field is an echo of what the client asked for, so it is never
treated as evidence of what served the request.

`stream` yields one `text` event per non-empty content delta, then `done` at
`[DONE]` or at the end of the stream. Lines are reassembled across chunk
boundaries. A chunk carrying no `choices`, a comment line and an unparseable
payload are all skipped rather than failing: the internal gateway opens with a
usage-only chunk, which is the fact the source had to patch LiteLLM to
survive. A call whose requirements do not declare `streaming` is refused with
a single `failed` event before anything is sent.

Failure codes, all non-escaping: `model_timeout` and `model_unreachable`
(retryable), `credential_unavailable` (retryable, because the token is
rewritten on a schedule and the endpoint was never asked),
`model_http_error` (retryable for 408, 429 and any 5xx), `provider_error` (a
2xx body carrying `error` rather than an answer, in a reply or mid-stream),
`model_unparseable` (a body that is not JSON, carries no choices, or in a
stream carries no server-sent events at all), `model_error` (anything else
raised, reported as
retryable because a custom transport may raise its own transient types),
`streaming_not_declared` and `tools_not_supported`. Tools are refused because
`ModelTool.input_contract` names a platform contract and rendering it as a
provider schema needs a registry that does not exist yet; a replayed exchange
carrying `tool_calls` on its messages is refused the same way rather than sent
as an invalid conversation. Every message is truncated to 500 characters and
passed through `SECRET_PATTERN` redaction, so an upstream that echoes an
`Authorization` header cannot print a token.

An endpoint that declares a `credential` and is given no resolver is a
`ValueError` at construction, beside the `base_url` and timeout checks, rather
than anonymous calls and a 401 later.

`Transport` is the injected HTTP surface: `send(url, body, headers, timeout_s)`
returns a `Reply` with `status`, `chunks()` and `close()`. A non-2xx status is
an answer, not an exception. Arguments are plain values rather than a contract,
so an `Authorization` header never lands in something serializable. The
default `UrllibTransport` uses the standard library through an opener that
**refuses redirects**: urllib would copy every header, `Authorization`
included, to wherever a 3xx points and drop the POST body on the way, so a
redirect is reported as the status it is. The platform's install stays
`pydantic` alone and no test opens a socket.

## Shared adapter rules and the Ollama adapter (Phase 5, slice 3)

`models.wire` is what every HTTP model adapter shares, so a second provider is
its wire format and nothing else. It holds the `Transport` protocol
(`send(url, body, headers, timeout_s) -> Reply`, whose arguments are plain
values so an `Authorization` header never enters something serializable), the
`Reply` protocol (`status`, `chunks()`, `close()`), `UrllibTransport` with its
redirect-refusing opener, `transport_failure` and `status_failure`, `redacted`
and `describe`, `authorized` (per-request credential resolution, with
`credential_unavailable` when the resolver raises), `checked_base` (the
construction-time refusals: no base url, a non-positive timeout, or an
endpoint declaring a credential with no resolver), `provider_error` (a 2xx
body that carries a refusal instead of an answer, which is how Ollama reports
a missing model and how either wire format must report a failure once a
stream's status has been sent; not retryable, because the provider understood
and declined), `unsupported` (tools in either shape), `undeclared_streaming`,
`structured` (strict JSON only when an `output_contract` was declared),
`lines`, `token_count`, and the
`failed_response`/`failed_event`/`answered` builders. `answered` is where the
platform's alias, rather than a provider's echoed `model`, is put on a reply.

`models.ollama.Ollama(endpoint, credential=None, transport=None,
timeout_s=600.0)` implements `ModelClient` against Ollama's native
`/api/chat`. `base_url` is the server root, such as `http://localhost:11434`.
`generate` sends `model`, `messages`, `stream: false` (Ollama streams by
default), `options.num_predict` from `max_output_tokens`, and `format: "json"`
for a declared `output_contract`. A message's `images` are sent as bare base64:
a `data:` URI is stripped to its payload, and any other reference is refused
as `image_not_inline` before the call, because Ollama embeds bytes rather than
fetching a URL. Usage is read from `prompt_eval_count` and `eval_count`.

`stream` reads newline-delimited JSON objects: one `text` event per non-empty
`message.content`, stopping at the object whose `done` is true, then `done`.
Blank and half-written lines are skipped, lines are reassembled across chunk
boundaries, and a 2xx body containing no JSON object is `model_unparseable`.
A body or a streaming object carrying `error` is `provider_error`, so a
refusal never reads as an empty success and the server's own explanation
survives. Failure codes are the shared ones plus `image_not_inline`. Locality
is not enforced: `local` is a catalog claim, and a host may run Ollama
elsewhere.

## Credentials and client construction (Phase 5, slice 4)

`models.credentials.CredentialResolver` is the boundary AGENTS rule 17
describes: `resolve(ref: SecretRef) -> str`, supplied by the execution
environment. Raising is how a resolver reports failure, which both adapters
turn into `credential_unavailable` rather than letting it escape. Nothing in
this module is a `Contract`, because a contract is serializable, validated and
loggable, which is everything a secret value must not be.

`credential_for(endpoint, resolver)` returns the zero-argument callable the
adapters take: `None` when the endpoint declares no credential, a `ValueError`
when it declares one and no resolver was supplied, and otherwise a closure
that calls the resolver **on every request**, so a rotated token is picked up
without rebuilding the client.

`EnvironmentCredentials(names, environ=None)` maps each `SecretRef` name to an
environment variable name, stated by the host: there is no prefix convention
and no default, so a secret nobody mapped is never guessed at. A resolved
value is stripped, because a token read from a file almost always carries a
trailing newline that would make an unusable header. It is development-grade;
a production deployment supplies its own resolver over a real store.
`StaticCredentials(values)` is the same shape for a host that already holds
its secrets, and for tests.

Both raise `CredentialMisconfigured` (a `LookupError`) for a secret nothing is
mapped to, a missing value or a blank one. `wire.authorized` reports that as
`credential_unavailable` with `retryable=False`, because such a secret will
never appear however often it is asked for, while any other resolver error
stays retryable: a token being rewritten on a schedule is readable a moment
later.

`models.clients.ModelClients(catalog, resolver=None, transport=None,
timeout_s=600.0, providers=None)` builds the right `ModelClient` for an alias.
`for_alias(alias)` returns a client or a `Failure`; `for_route(name)` and
`for_requirements(requirements)` return `(alias, client)` or a `Failure`, the
last being the whole chain from what a caller needs to something that can
answer it. `providers` maps a provider symbol to a `ClientBuilder`
and is merged over the built-in `openai_compatible` and `ollama`, so a host
can register its own provider without changing core runtime code, and can
override a built-in by reusing its key. `options` carries per-alias keyword
arguments for the adapter, such as `{"company_reasoning": {"max_tokens_field":
"max_completion_tokens"}}`: these are wire details of one endpoint that the
shared contract deliberately does not describe, so they belong to host wiring.
An option naming no endpoint is a `ValueError` where the wiring is written.

Failure codes: `unknown_alias`, `unknown_provider`,
`endpoint_misconfigured` for the construction-time refusals (no base url, a
non-positive timeout, a declared credential with no resolver, an option the
provider does not take) and `provider_build_failed` for anything else a
host-registered builder raises, alongside the
catalog's own `no_model_for_requirements` and `unknown_route`, which travel
through unchanged. A built client is cached per alias, so a host may call this
per request without rebuilding a transport each time.

## Model observability and the worked example (Phase 5, slice 5)

`ModelResponse.duration_ms` and `ModelStreamEvent.duration_ms` report how long
the provider took, in milliseconds, so evaluation can compare aliases on
latency as well as on quality and usage. `None` means nothing was measured,
which is not the same as a call that took no time: a refusal made before any
request must not be averaged in as an instant answer.

Both adapters measure with `wire.Elapsed`, on a monotonic clock so a clock
adjustment cannot produce a negative latency, starting **after** the payload
is serialized so the two adapters measure the same span and a large image is
charged to neither provider. A stream adds `wire.Waited`, which counts only
the time spent blocked on the source: a stream is read as its caller
iterates, so measuring to the last event would charge the provider for a
harness that renders slowly, and a model sending many small deltas would rank
as the slow one. The terminal event (`done` or `failed`) carries the total;
the text deltas are not each timed.

`models.proof` is a copyable host path, not a default. `SAMPLE_CATALOG` is
plain data in the shape a host keeps in YAML or JSON, declaring a credential
as a `SecretRef` name so the whole catalog is safe to commit. `clients_from(
data, resolver=, transport=)` validates it and returns `ModelClients`.
`ask(clients, requirements=, prompt=, trace=, max_output_tokens=)` returns a
`ModelResponse` or a `Failure`: a `Failure` from `ask` is a routing problem
(or `invalid_request` for a caller's own mistake, such as a blank prompt),
one on the response is a provider problem, and neither becomes an exception.

## Evaluation harness (Phase 6, slice 1)

`common.evaluation.EvaluationCase` gains an optional `expected_route`: a case
that is not a routed request has none. Discovery and Bridge advertisement are
control-plane concerns with no route to take, and requiring one there could be
satisfied only by copying the case's own words back into the observation.

`ObservedRun` records what actually happened when a case was exercised:
`decision`, `origin` (mirroring `agent.routing.RoutingOutcome`), `model_calls`,
`side_effects`, `status`, `completed_steps`, `discovered`, `lifecycle`,
`advertised`, `installed` and `failure`, plus `observable` and `dispatched`.
Every field is evidence a grader can check, never a flag claiming that an
assertion holds, because grading a claim checks nothing.

`observable` names the side effects the run was capable of detecting, and
`dispatched` names every capability the Bridge was asked to run whether or not
it was installed, authorized or reached. An effect counts as caused when the
handler ran, including when it then failed; a dispatch refused before the
handler was reached caused nothing. Together they make absence of an
effect mean something: `no_execution` fails when `execute` was not observable,
and the always-on forbidden check fails for any forbidden effect the run could
not have seen. A harness that was not looking no longer reports a clean run. `advertised` and `installed` hold `AssetIdentity` values rather
than names, because a capability named `sample.inspect` carries an identity
named `inspect`; and `lifecycle` is what was registered rather than what a
query returned, since discovery already drops anything unpublished and reading
it back from there would be a check that cannot fail.

A `Grader` takes `(case, observed)` and returns `None` when satisfied or a
reason when not, so a failure always says why. `GRADERS` registers one per
assertion name the repository's cases declare: `no_model_call`, `no_execution`,
`exact_scoped_target`, `deterministic_trigger`, `fail_closed`,
`workflow_succeeds`, `scoped_identity`, `published_discovery` and
`bridge_advertisement`.

A prohibition is an assertion whose grader fails when the forbidden thing is
found, so the Roadmap's `Forbidden` list needs no second mechanism beside
`assertions`. `ObservedRun.declared_steps` is how many steps the triggered
workflow declares, `ObservedRun.ran` is what the Bridge actually reached a
handler for as opposed to every dispatch attempted, and
`ObservedRun.unapproved` is the capabilities declaring an irreversible effect
that were *dispatched* with no approval behind them. All come from what the
platform already produces: the manifest, the Bridge's events and the policy's
grants. The four prohibitions:

- `mandatory_steps_completed` — a skipped mandatory test is a declared step
  that did not finish.
- `stayed_in_namespace` — touching an unrelated repository is *running* a
  capability outside the namespace the request named. A dispatch the policy
  refused reached nothing and so modified nothing.
- `no_unapproved_irreversible_effect` — overwriting a released tag is an
  `external_side_effect` nobody approved. Only irreversible capabilities
  count, since a low-risk one legitimately carries no approval; and every
  dispatch counts, not only what ran, because the policy refuses such a
  dispatch today and reading only what ran would leave this unable to fail
  while the platform works and silent about the moment it stops. It also
  fails when an irreversible effect was not observable at all.
- `no_credential_in_evidence` — the repository's own `SECRET_PATTERN` over
  the evidence, rendered field by field with quotes stripped, because a token
  usually arrives inside a JSON string where the quote sits exactly where a
  prose pattern expects the separator.

`grade(case, observed, graders=)` returns a `CaseResult` (`case_id`, `passed`,
`grades`, `unknown_assertions`, and `reasons()`). The expected route is checked
when the case names one, and a mismatch names the target reached rather than
only its kind, because a wrong target of the right kind is the common mistake.
The forbidden side effects are always checked, and an assertion with no grader
is reported in `unknown_assertions` and **fails the case**: a harness that
ignores what it does not understand reports a perfect score and is believed.

Each grader checks something that can actually fail. `scoped_identity` checks
that what was found stayed inside the namespace that was asked about, since
`AssetIdentity` already guarantees the three parts are present;
`published_discovery` requires every registered lifecycle to be `published`
rather than merely containing it; `bridge_advertisement` compares identities
and, for a discovery case, requires every discovered task to appear among the
Bridge's installed tasks; and `fail_closed` consults the case's own forbidden
list, so a permitted read is not read as failing open.

`CaseRunner` is the protocol that turns a case into an `ObservedRun`, and
`run_cases(cases, runner, graders=)` grades a directory through one. How a
case is exercised stays outside the contract it is graded against, so a host
supplies the wiring; `tests/evaluation_runner.py` is the repository's, sending
every routed case through one real `Gateway` and reading effects from the
Bridge's own `events`. A case that issues no request, such as the registry
proof, observes nothing and therefore forbids nothing: the harness will not
grade an effect it could not have seen, so such a case carries its meaning in
its assertions instead.

`load_cases(directory)` reads every `.json` file, accepting one case or a list,
in a stable order, refusing a duplicate `case_id` where the cases are loaded.
`report(results)` returns one line per case with the reason under every
failure, so a CI log says what broke rather than that something did.

## Model-involving evaluation (Phase 6, slice 4)

The first three slices grade a deterministic platform, where one run is
proof. A model is not deterministic, so its evaluation is a separate class of
test and is kept out of the CI gate.

`model_selected_route` is the `agent` category's grader: the route was reached
with origin `model` **and** a model really was asked. It is the mirror of
`deterministic_trigger` and `no_model_call`, so a deterministic case that
asserts it fails, and so does an observation claiming a model chose while
never calling one.

`ObservedRun` carries `duration_ms`, `input_tokens` and `output_tokens` from
the Phase 5 response, so an alias can be ranked on cost and speed rather than
only on being right.

`compare_aliases(case, aliases, run, repeat=3, graders=)` runs one case once
per alias per repetition and returns a `ModelEvaluation`: `measured` with one
`AliasTrial` per alias and no `detail`, or `skipped` with the reason in
`detail`; the contract refuses each without the other. An empty alias list is
**skipped, never passed**. A repeated alias is refused for the reason
`load_cases` refuses a repeated id. `repeat` below two raises: one cell is not
a measurement when the thing measured is not deterministic, which the source
repository's benchmark states outright. A `run` that raises is recorded as a
failed attempt with the exception named and redacted, not the end of the
comparison: a measurement of unreliability that aborted on the first
unreliable call could not report the alias it was built to find.

An `AliasTrial` holds at least two `Attempt`s, enforced on the contract so
stored attempts cannot be reassembled into a one-cell reliability of 1.0.
Each attempt records whether it passed, its `duration_ms`, its tokens and the
reasons it failed. The trial exposes `passes`, `reliability` (passes over
attempts), `unmeasured` (attempts with no duration, usually refused before any
call), `mean_duration_ms` over the measured attempts, and `total_duration_ms`
only when every attempt was measured, because a total over some of them would
read as faster exactly when the alias failed to answer. Nothing in this layer contacts a provider: the comparison takes
a `run` callable, so a host supplies live clients and the repository's tests
supply Phase 5 adapters over an injected transport.

## Trace capture with redaction (Phase 6, slice 5)

`ObservedRun` is evidence read while grading. `common.trace.ExecutionTrace`
is the record read afterwards, by a person or a later evaluation, so it has
three duties the evidence does not: it joins to the request that produced it,
it keeps the order things happened in, and it is safe to store.

`ExecutionTrace.build(trace, observed, dispatches, approved=)` takes the
request's `TraceIdentifiers`, the observation, and the Bridge's events for that
request. An event carrying another request's identifiers is refused with
`ValueError` rather than filed. The record holds `events` in order (a `route`
event first, one `dispatch` event per Bridge event with its identity, status
and code, and an `outcome` event last), the route and its `origin`,
`dispatched`, `ran`, `approved` (dispatched identities whose grant carried an
approval reference), `unapproved`, the workflow `status`, `completed_steps` and
`declared_steps`, `model_calls`, `duration_ms`, `input_tokens`,
`output_tokens`, the redacted `failure`, and `redactions`, how many secrets
were removed on the way in. `TraceEvent`s carry identities, statuses and codes
and never a payload. The outcome event's status is the workflow's when one
ran, else the last dispatch's, else `unresolved` for a routing failure, else
`nothing_ran`.

`redact(value, label=)` returns a copy of any JSON-shaped value with every
credential replaced by `common.assets.REDACTED` (`[redacted]`), and the
count. Three rules, in order: a field whose name matches `SECRET_FIELD`
(`password`, `api_key`, `access_token`, `secret_value`) loses its whole value
whatever its shape, nested mapping included; a `SECRET_PATTERN` match inside a
string is cut out so the rest of a message survives; and a string that still
scans as a credential beside its field name (JSON inside a message, whose
quotes hide the match from a substitution) is replaced whole. Redacting the
output again changes nothing and counts nothing. The scan is
`common.evaluation.labelled`, the same one the `no_credential_in_evidence`
grader uses, and a label that names a secret is inherited by everything
beneath it, so what redaction removes and what the grader refuses are decided
by one rule.

`SECRET_PATTERN` itself spans the whole secret rather than locating its start:
a quoted value with spaces is matched to its closing quote, and a private key
block to its `END` line or the end of the text. It refuses to match
`REDACTED`, so the one pattern detects a credential and reads its own
replacement as clean, in the trace, the evidence grader, the model adapters'
error redaction and the registry's rejection of embedded secrets alike.

`carries_credential(value)` is that scan applied to anything. The
`ExecutionTrace` validator runs it on the whole record and refuses a trace
that carries credential material, whether built by the platform or assembled
from stored parts. It also refuses events not numbered from zero without gaps,
a record that does not open with the route and close with the outcome, a
`dispatched` list that does not match the dispatch events in order, `ran`,
`approved` or `unapproved` naming an identity that was never dispatched, and
an identity both approved and unapproved.

`common.trace` depends on `common.evaluation`, never the reverse, and reads
Bridge events through a `DispatchRecord` protocol so that `common` does not
import `workflow`.

## Company host technical preview (Phase 7, slice 2a)

`host_runtime.contracts.CompanyHostConfiguration` is closed, frozen and restricted
to the approved company-workstation `BridgeDevice` profile. It contains only the
device identity/profile and an absolute Windows workspace path. Credential-shaped
content and unknown fields are refused; invitation proof, sessions, permissions,
capability grants and secret values have no representation.

The Windows installer derives the default `bridge_id` as
`bridge-<normalized-windows-computer-name>` and accepts an explicit override for a
name collision. This is stable device metadata only. The later authenticated
enrollment host must still establish device identity and reject duplicate IDs.

`HostDoctorReport` contains four explicit `DoctorCheck`s: operating system, exact
Python minor, device profile and workspace. `ready` means those local prerequisites
passed. It says nothing about control-plane connectivity, enrollment, authorization
or production capability availability, which are listed as limitations.

`EnrollmentRequest` joins the configured device to an empty `BridgeRegistration`
with matching Bridge/owner identity and trace identifiers. It is inspectable input
for a later authenticated host call. It is neither an authentication credential nor
an authorization decision, and publication/discovery still grants no execution.

The offline bundle's `manifest.json` records schema version, bundle name, Git source
revision, Python minor, platform and each payload's relative path, byte size and
SHA-256 digest. The manifest is checked before install; it deliberately excludes
runtime configuration and state.

## Local-first distribution and remote control (Phase 7, slice 2b)

`PublishedAssetPackage` wraps the existing governed `AssetMetadata` with an asset
kind. It accepts only `published` metadata with an exact `PackageMetadata` artifact
reference and SHA-256. `InstallationPlan` selects non-duplicate exact versions for
one actor and Bridge. Neither contract contains an execution authorization.

`InMemoryLocalInventory.apply` takes an installation plan and already-retrieved byte
payloads. It verifies every digest before changing one inventory entry, then records
`InstalledAsset` identity, kind, source artifact/digest and installing actor. It does
not import or execute the bytes. This reference demonstrates that installed state is
local and remains available without a Registry connection.

`BridgeStateSnapshot` is explicitly authoritative at the Bridge and carries its
device, observation time, installed inventory and compact local run summaries.
`BridgeStatusProjection` keeps that snapshot plus the central receipt time and an
`online` or `stale` connectivity label. The reference control plane derives staleness
from elapsed time and never rewrites a local run status.

`RemoteWorkflowJob` accepts only `shared_platform` or `telegram` ingress, an exact
Workflow identity, actor, Bridge, arguments, trace and matching allowed
`ExecutionAuthorization`. It has no arbitrary command/shell field and refuses secret
fields or values. `InMemoryRemoteControl` also requires device admission: a company
workstation admits only its registered owner, while a shared test workstation admits
the virtual member it runs as. Telegram identity mapping occurs before this contract and cannot
bypass the same membership and policy path. Polling returns bounded queued records;
cancellation is a request state and does not claim a running side effect stopped.

## Resident local Agent and durable local state (Phase 7, slice 2d)

`common.local_agent.BridgeMembership` is the Bridge computer's own copy of who
may use it: its `BridgeDevice` and the `BridgeBinding`s for that device. It
refuses a binding for another device, a repeated actor, more than one active
binding whatever the device's kind, and on a company workstation an active
binding that is not the registering owner, so the local rule cannot drift from
the control plane's. `member()` answers which member this machine runs as. It
grants use of the device and nothing else. `LocalAgentRequest` is one request
from any ingress (`local`, `shared_platform`, `telegram`): actor, Bridge,
namespace, message, trace and optional session, closed and refusing credential
material. Its `on_behalf_of` records the member who asked when that is not the
member who runs; it is recorded and never consulted, because admission, grants
and entitlement all read the acting member. A remote job is the existing
`RemoteWorkflowJob`.

`common.enrollment.admit_device(device, actor=, bridge_id=)` is the device
half of admission, written once: the request names this device, the device is
active, and on a company workstation the actor is its registered owner
(`device_identity_mismatch`, `device_disabled`, `company_owner_required`). The
control plane's `InMemoryRemoteControl.submit` and the Bridge's `LocalAgent`
both call it; whether the actor is bound is each caller's question, answered
from the membership record it holds.

`host_runtime.agent.LocalAgent` admits before it routes, by that rule plus the
device's own bindings (`actor_not_bound`), on every ingress. A refusal is a
`LocalAgentOutcome` carrying only its code; the contract refuses a refusal that
also reports a decision, a result or a run. An admitted message goes through
the existing `Gateway` as a `RequestContext` whose channel is the ingress, so
deterministic routing, Bridge policy and the workflow engine apply unchanged.
An admitted `RemoteWorkflowJob` runs its exact workflow through
`Gateway.execute_workflow` with no routing and no model, with the job id as
the idempotency key, so a job delivered twice joins the run it already started.
The engine answers for what is installed here; its pre-flight rejection comes
back as a workflow result without a run. The job's `ExecutionAuthorization` is
the control plane's decision; the Bridge policy still decides every step.

Every workflow run the engine actually starts is recorded as a
`LocalRunSummary` under the actor who asked, and the outcome's `run` names the
same run as its workflow result. A run that outlives the caller's wait is
recorded as it stands and settled to its final state in the background;
`LocalAgent.settled()` waits for that. A record that could not be written is
reported as `unrecorded` with the `LocalStateError` code, never raised over
the workflow's result; the contract refuses `run` and `unrecorded` together.
`LocalAgent.snapshot(observed_at)` is the authoritative `BridgeStateSnapshot`
for the control plane to project.

`host_runtime.state.SqliteLocalState` is that record on one local SQLite file:
one process, one writer, every write one `BEGIN IMMEDIATE` transaction that is
rolled back whole if any rule refuses, reads under the same lock so they never
observe an open transaction, following `workflow.checkpoints_sqlite`.
`unavailable` means known not committed; `commit_unknown` means the
acknowledgment was lost and the caller must read back. The file records the
Bridge it belongs to on first open and refuses another device's identifier.
`install` applies `common.distribution.verify_installation`, the one
installation rule now shared with `InMemoryLocalInventory`: the plan names this
Bridge, every artifact is present and matches its digest, nothing is installed
twice, and the whole plan is checked before one row changes. `record_run` keeps
a run's actor fixed (`run_owner_fixed`), refuses an update older than the
stored one (`run_update_stale`) and stores timestamps in UTC so listing order
is chronological whatever offset the clock carried. `LocalStateError` carries
a code and nothing else; no path, record or SQLite message is echoed. Nothing
here authenticates, downloads, polls or opens a socket.

## Telegram ingress (Phase 7, slice 2e)

`channels.telegram.TelegramIngressConfig` is host configuration for one bot
serving one Bridge: the token as a `SecretRef` named `credential`, the
`bridge_id`, the `namespace` requests are routed in, `senders` (numeric
Telegram ids mapped to platform actors, one to one), a long-poll timeout and
the https origin of the Bot API. It refuses a duplicate sender or actor, a
non-https origin or one carrying a token, and any credential material in the
record. `actor_for(sender_id)` is `None` for a sender not in the map, so an
empty map admits nobody. The shape of a Telegram bot token
(`<8-10 digits>:<35 token characters>`) is now an alternative of
`SECRET_PATTERN`, and `bot_token` a `SECRET_FIELD` name, so the registry, the
evidence grader, the trace and the model adapters refuse or redact it too.

`TelegramIngress(config, agent, resolver, transport=)` serves the `LocalAgent`
of the configured device and refuses another. `poll_once()` calls
`getUpdates` over `models.wire.Transport`, resolving the token through the
host's `CredentialResolver` on every call, using it in the URL and holding it
nowhere. It returns a `TelegramPollResult`: `deliveries`, or a `Failure`
(`telegram_credential_unavailable`, `telegram_timeout`,
`telegram_unreachable`, `telegram_error`, `telegram_conflict` for HTTP 409,
`telegram_http_error`, `telegram_bad_reply`) with the token already redacted,
in which case the offset stays where it was. The failure rules are
`models.wire.transport_failure` and `status_failure`, now parametrized by a
code prefix so every HTTP adapter shares one rule (a 408 or 429 is retryable;
a 5xx is retryable; a 401 is not), and `models.wire.redacted` redacts before
it trims so a credential straddling the cut cannot survive as a fragment.
`run(stop)` loops `poll_once` until asked to stop; it returns on any failure
that is not retryable (a conflict, a revoked token, a credential the host
cannot produce) and waits out a retryable one with a doubling delay capped at
sixty seconds.

`TelegramDelivery` is what became of one update: `unmapped_sender` (refused
before the text is looked at, and not answered, so `reply` is None),
`unsupported_content` (no text, empty text, or text the request contract
refused for credential material), `answered` (`/help`, `/start`, `/status` in
any spelling Telegram sends, handled locally without a run), `refused` (the
Agent's membership refusal, with its `LocalAgentOutcome`), `routed` (the
Agent's outcome) or `failed` (handling raised; `failure` names the error,
redacted, and the sender is told the request could not be handled). The
contract requires an outcome exactly for `refused` and `routed`, `refused`
exactly when the outcome carries a refusal, `failure` exactly for `failed`,
and no reply exactly for `unmapped_sender`. `replied` records whether the
reply could be sent; a failed reply is never raised over the outcome. Every
update id in a batch is confirmed by advancing the offset after the batch was
handled, and an id handled in this process is not handled again if
redelivered. `/status` reads the Agent's snapshot off the event loop.

`command_to_message` turns `/skill command rest` into the platform's
`skill.command rest` form (a trailing `@botname` is dropped) so a slash command
reaches the deterministic router without a model; `/skill` alone is the bare
word and other text is passed as written. Requests carry
`ingress="telegram"`, the mapped actor, the configured Bridge and namespace, a
trace named `telegram-<update_id>` and a session named for the chat. Replies
are plain text in pieces of at most 4000 characters, name identities, statuses
and codes, never a payload, and pass through the shared redaction without the
error helper's truncation (`scrub`). `api_base` is normalized without a
trailing slash.

## Company host runtime (Phase 7, slice 2f)

`host_runtime.host.HostLayout` names every file a company host reads, all
under one `workspace_root`: `membership.json`, `grants.json`,
`assets/skills/`, `assets/workflows/`, `telegram.json` and `state.sqlite`.
`HostLayout.under(root)` derives them, so the installer and the operator agree
without a second configuration file.

`CompanyHostConfiguration` gains `namespace` (which namespace this host's work
addresses, with no default because the platform does not guess) and
`credentials`, a tuple of `CredentialBinding` naming which environment
variable holds the value for a declared `SecretRef`. Both halves of a binding
are names; the value is never written down. The schema version is unchanged
because a file without either field is still valid and means exactly that.
`workspace_root` must be absolute, as a Windows path or as an absolute path of
the running platform, so a host file written on the company computer stays
valid wherever it is inspected.

`build_runtime(config, layout=, resolver=)` returns a `HostRuntime` holding
the `LocalAgent`, the `SqliteLocalState` and the optional `TelegramIngress`;
closing it closes the state file. It raises `HostError` with a closed code
(`membership_missing`, `membership_invalid`, `membership_mismatch`,
`grants_invalid`, `asset_invalid`, `telegram_invalid`, `credential_unmapped`,
`state_unavailable`) and the path at fault, never its contents. A membership
record that describes another device is refused rather than reconciled.

`build_gateway` registers the one capability handler this package ships
(`filesystem/read-file`, rooted at the workspace) and nothing else: a manifest
naming another capability is installed but its steps fail closed, because
installing a manifest does not install code. Routing is deterministic only, so
an unrecognized message is `needs_input`. A grants file is optional and its
absence means default deny.

`DoctorCheck` gains the names `membership`, `assets` and `state` and the
status `pending`, for what a host has not been given yet as opposed to what is
broken. `HostDoctorReport.status` remains this machine's preflight, so a host
that is merely not enrolled is not reported as a broken installation;
`runtime` is `ready` when this Bridge knows who may use it and nothing it
needs is broken, and a state file that does not exist yet is not an obstacle
because the Agent creates it. `host_report(config, layout)` combines the
device preflight with those checks and writes nothing: the state file is
opened only if it exists, and then read-only.

`SqliteLocalState` gains `cursor(channel)` and `advance_cursor(channel,
position)` on a `channel_cursor` table, refusing to rewind (`cursor_rewind`).
The schema version is 2 and a version-1 file is migrated on a writing open,
because every change so far has been an added table that each open creates.
`SqliteLocalState(path, bridge_id=, read_only=True)` opens an existing file
through a `mode=ro` connection: it creates nothing, migrates nothing, refuses
every write with `unavailable`, and still insists the file belongs to this
device and carries a schema this code understands. Any SQLite error on open,
including a corrupt file, is `LocalStateError("unavailable")` rather than an
exception from the driver.

`TelegramIngress.offset()` reads that cursor instead of memory, so a restart
resumes where the last confirmed batch ended; a cursor that cannot be read is
`telegram_cursor_unavailable` and no poll happens, and one that cannot be
advanced is `telegram_cursor_unconfirmed` beside the deliveries that were
handled. Both are retryable, because the usual cause is another process
holding the file for a moment.

## Member-decided asset authorization (Phase 7, slice 2g)

`common.authorization.DeviceAssetSelection` is one member's decision that one
device may run one asset for them: `bridge_id`, `actor`, `kind` (`workflow`,
`skill` or `capability`), `asset`, `decided_at`, `status`, and for a tool an
`approval_ref` with the `approved_by` who gave it. It names no permission and
no policy reference, and the closed schema gives nowhere to write one: a
member chooses **which** assets, never what they are allowed to do, so a
decision cannot widen itself. An approval belongs only to a tool, and always
names who gave it.

`DeviceAuthorization` is every decision in force for one device at one moment:
`bridge_id`, `issued_at` and the selections. It refuses a decision for another
device, a revoked decision (what is in force is what is present), two
decisions by one member about one asset, and a decision newer than the
authorization carrying it. `for_actor`, `installable` (Workflows and Skills),
`tools` (capabilities) and `allows(kind, asset)` read it.

`control_plane.authorization.InMemoryAuthorizationRegistry(enrollment,
packages, storage=...)` records decisions and refuses the ones a member may not make:
`actor_not_admitted` for a device they are not bound to, `asset_not_published`
and `kind_mismatch` against the Registry, `tool_not_advertised` for a
capability the device does not say it has, `approval_required` for a tool
whose own `CapabilitySpec` requires one, `approver_not_member` when the
approver is not an active platform member, `tool_not_grantable` for a
capability that declares no policy reference and so cannot be granted to
anybody, `decision_in_future` for a decision no bundle could carry,
`duplicate_selection`, `asset_deprecated` for a version its name's owner
deprecated (in `select` and `replace`), and `selection_missing` on
revocation. Selecting a Workflow, Skill, Knowledge or Agent version revokes
any other active version of the same `namespace/name` the member chose on
that device, in the same storage transaction (one active version per member,
device and name, 2026-10-07); capability selections are not versions of an
Add-on and are unaffected. `available` leaves deprecated versions out.
`grants(bridge_id)` derives the device's
`CapabilityGrant`s through `grant_from(spec, selection)`: the permissions and
policy references are the capability's own declaration and the approval is the
member's, so a decision about which tools never becomes a decision about what
they may do. Grants are per actor, and a machine has one member, so a device's
grants are that member's; on a shared test workstation they are the virtual
member's. The approver is checked against the platform's members rather than
the device's, because one member per machine would otherwise leave
`approved_by` able to name only the member giving the approval.

The storage argument is optional so isolated tests and in-process references
keep the same contract. A durable Shared Platform loads every validated
`DeviceAssetSelection` from the allowlisted `authorization_selections` SQLite
table. Select and revoke persist the replacement record before changing the
in-process view. Exact-version replacement writes the revoked prior version and
active replacement in one transaction, preserving its all-or-nothing contract
across process restarts. Persisting a selection still creates no grant; grants
continue to be derived from the device's current capability advertisement.

A company host reads `authorization.json` from its workspace when it is there.
`build_gateway` then installs only the Workflows and Skills the members chose,
and derives the policy grants from its tool selections against the
`CapabilitySpec` it actually installed: each plane derives from the
declaration it holds, so neither trusts the other's arithmetic, and a tool
that is not installed here grants nothing. `grants.json` remains the way to
configure a host with no control plane; both files at once is
`authorization_conflict`, a bundle for another device is
`authorization_mismatch`, an unreadable one is `authorization_invalid`, and
a tool this host cannot grant is `authorization_ungrantable`. `DoctorCheck`
gains the name `authorization`, reporting those states before a command
fails on them, and the `assets` count is taken after the selection filter.

## Identity-derived entitlement (Phase 7, slice 2h)

`Invitation.groups` and `PlatformUser.groups` record which teams,
organizations or services accepting an invitation makes an actor a member of.
The platform has no company directory, so the invitation is where membership
comes from and the accepted user is where it is kept. Both default to none, so
an invitation that grants no membership still makes a platform user and every
record written before this slice stays valid. `InMemoryEnrollmentRegistry.user`
reads it back.

`common.identity.AuthenticatedActor` is what an entry point produces once it
has decided who someone is: the `actor`, the `method` it used, when it happened
and when it stops being true. It carries no credential and no group, because a
membership claim travelling with a request is one that whoever sends it can
widen; groups are read from the platform's own record instead. The contract
refuses an expiry that is not after the authentication, and `valid_at(now)`
answers whether it still holds. The `method` is a name the platform records
without interpreting: how a member proves who they are belongs to the entry
point, and an evidence trail needs the name of it either way.

`common.identity.entitled(metadata, actor, groups)` decides whether one member
may use one published asset. Nothing unpublished is usable. The owner may
always use what it owns, whether the owner is that actor or a group they
belong to, and so may a recorded contributor; beyond that, `public` and
`organization` are for any member of the platform, and nothing else is for
anybody else. That decides `team` and `private` together: for a group-owned
asset they come to the same answer, the owning group and nobody else, because
the owning group is the team. A user-owned asset marked `team` names no team
to check, so it stays with its owner.

`entitled(..., access)` also takes the name's `common.identity.NameAccess`
record (owner decision 2026-10-15): `namespace`, `name`, optional `visibility`
(replaces every version's declared visibility), `members` and `groups` (unique;
may use it whatever the visibility), `updated_by`, `updated_at`. A record for
another name is a `ValueError`. The record never takes the asset away from its
owner or a contributor. `control_plane.distribution.entitled_in(packages,
metadata, actor, groups)` looks the record up; `available`, `select`, `replace`,
the Bridge `catalog`, the administrator's extension catalog and ownership
visibility all use it.

`InMemoryAuthorizationRegistry.select(identity, selection)` and
`revoke(identity, bridge_id, asset)` require an authenticated actor whose
session is still valid (`session_expired`) and who is the member the decision
belongs to (`actor_mismatch`): a member decides as themselves. A Workflow or
Skill the actor is not entitled to is `asset_not_entitled`, and the groups
come from the platform's record of that user. `available(identity)` is the
list a member chooses from: the published Workflows and Skills they may use.
It is guarded like a decision, because a list of what somebody may use is
itself something only they should see: a valid session, a member the platform
knows (`actor_unknown`) and has not disabled (`actor_disabled`), and only the
kinds a decision can name.

Entitlement is checked when a decision is made, not when a run happens. An
authorization records what was decided, so a member whose entitlement is
withdrawn keeps their device's existing bundle until the control plane issues
a new one.

## Bridge access tokens (Phase 7, slice 2b)

`common.identity.BridgeAccessGrant` is the platform's record of one access
token: `token_id`, the `actor` and `bridge_id` it was issued for, a
`fingerprint` of the secret, `issued_at`, an optional `expires_at` that must
be after it, and `status`. Binding a member to a device is what justifies one,
so a grant always names both; since slice 2j a machine has one member, so a
machine holds one token. The secret is not in it.

`common.identity.IssuedAccessToken` is the one moment the secret exists
outside the Bridge: the grant and the value, returned once by issuing.
Deliberately not a `Contract`, for the reason `models.credentials` gives: a
contract is serializable, validated and loggable, which is everything a secret
must not be. Its `repr` names the token and redacts the value, and it has no
other attributes to put one in.

`control_plane.identity.InMemoryAccessTokens.issue(requested_by, actor,
bridge_id, issued_at=, expires_at=, secret=)` issues only for a member the
platform currently admits on that device (`actor_not_admitted`), only for a
caller who is that member or may administer the device (`token_forbidden`),
and one usable token per pair (`duplicate_token`); a token that has expired is
spent and no longer in the way. It generates the secret with `secrets.token_urlsafe`
and refuses a supplied one below 32 characters (`weak_secret`), because the
fingerprint comparison is sound only for a value nobody can guess;
`fingerprint` is a plain SHA-256, which is enough for 32 random bytes and
would not be for a password.

`authenticate(token_id, secret, now=, session=)` verifies the secret before it
says anything about the token's state, comparing with `hmac.compare_digest`
against a fingerprint that matches nothing when the token is unknown: an
unknown `token_id` and a wrong secret are both `authentication_failed`, so
somebody who holds neither cannot learn that a token exists. Once the secret
matched, the holder is told which of `token_revoked`, `token_expired` or
`binding_withdrawn` applies; the last covers a withdrawn binding, a disabled
member and a disabled device alike. A `token_id` that is not even the shape of
one is answered like any other unknown token rather than raising. Success is an
`AuthenticatedActor` naming the member and the `bridge_id` the token was issued
for, whose `method` is `bridge-access-token` and whose session ends no later
than the token does; an entry point where somebody signs in directly leaves
the device absent.

`grants_for(bridge_id, now=)` lists the tokens a device can currently be used
with, excluding the spent ones, with no secret in any of them.
`revoke(requested_by, token_id)` and `revoke_for(requested_by, actor,
bridge_id)` take them back under the same caller rule as issuing, and
`InMemoryEnrollmentRegistry.unbind` withdraws the binding that justified them
(`binding_missing` when there is none, `binding_forbidden` for a caller who may
not administer that device). A withdrawn binding is history rather than a bar:
`bind` refuses only a binding that is still active, so a member taken off a
device can be put back on it. `may_administer(actor, bridge_id)` is that one
rule, asked by everything that acts on a device's records.

## Member Agent Add-on selection (Productization 1 slice 2a; Productization 2 slice 1)

`MemberCatalogRequest`, `MemberSelectRequest` and `MemberRevokeRequest` name a
Bridge and, for a mutation, an exact asset identity. Their closed schemas have
no actor, groups, permission, policy, approval or decision-time field. The
member entry point supplies actor and time from its authenticated session and
derives `workflow`, `skill`, `knowledge` or `agent` from the exact Registry package. A request cannot
claim or change kind. `MemberCatalogReply` contains entitled published
Workflows, Skills, Knowledge and Agent-profile versions with a separate `selected` fact; it
neither carries artifact bytes nor changes installation or execution
authorization. Other published kinds are excluded until they have a compatible
validated installer.

## Agent profile activation (Productization 2, slice 4)

An `AgentProfile` is distributed as its own closed JSON artifact. Registry
metadata and the metadata inside the artifact must agree exactly after the
outer package reference is removed. Synchronization installs the profile under
an identity-derived filename and records it in local inventory; this is inert
installation and grants no capability or model access.

`AgentProfileActivationRequest` carries only one scoped profile identity.
Actor, Bridge, authorization, installed paths and model configuration are
trusted host state. Activation requires the exact profile selection, a
published installed profile, every referenced Skill and Knowledge version to be
selected and installed, every allowed capability to be separately selected,
and the configured routing endpoint to satisfy `model_requirements`. Any
`may_delegate_to` entry is refused in this milestone. A successful activation
atomically writes `ActiveAgentProfile` and reports that host restart is needed.

On rebuild, the active profile filters the existing Skill registry, Knowledge
catalog and derived capability grants. It cannot add a manifest, handler,
selection, grant or model endpoint. No active-profile file preserves the
existing single-Agent behavior for locally managed hosts.

## Agent Add-on version replacement (Productization 2, slice 5)

`MemberReplaceRequest` names the bound Bridge, current exact identity and
replacement exact identity. The closed contract requires distinct versions in
one namespace/name family and contains no actor, kind, permission, path,
approval or policy. The authenticated Registry derives the kind, verifies the
current active selection, publication, entitlement and same kind, then commits
the revoke/select pair together. `MemberReplacementReply` carries the revoked
previous selection and active replacement.

No validation failure mutates either selection. Bridge synchronization remains
append-only for verified package bytes: it installs a missing replacement and
writes the new authorization, while a retained previous version is ignored by
runtime filtering. Replacing back to that previous exact identity therefore
updates authorization without downloading or rewriting its package. Explicit
`MemberRevokeRequest` removes active use; physical retention protects rollback
and never implies authorization.

`InMemoryMemberSessions.issue(identity)` is a trusted-host call made after an
external sign-in adapter has produced a current `AuthenticatedActor`. It
refuses an identity carrying a Bridge id or the `bridge-access-token` method.
The platform stores `MemberSessionGrant`, which contains a SHA-256 fingerprint
of a random secret and never its value; `IssuedMemberSession` is deliberately
not serializable and redacts its repr. Authentication gives unknown ids and
wrong secrets the same `authentication_failed` answer and reports an expired
session without extending it.

`MemberService.catalog/select/revoke` authenticates that independent session,
requires the actor to be bound to the named Bridge and delegates entitlement
and selection invariants to `InMemoryAuthorizationRegistry`. The HTTP entry
point is `POST /v1/member/catalog`, `/select` and `/revoke` with its own member
bearer credential. It never accepts a Bridge credential. Its generic page can
receive a short-lived session in a URL fragment from a trusted sign-in host,
removes the fragment immediately and keeps the value in memory only. Plain
HTTP is restricted to loopback; a network-exposed member portal requires TLS.
No production sign-in provider or durable session store is supplied by this
reference slice.

## Invitation member sign-in (Productization 1, slice 2b)

`InvitationProofGrant` is the secret-free platform record for the out-of-band
proof associated with one pending `Invitation`: invitation id, named actor,
SHA-256 fingerprint, issue/expiry time and `active`, `redeemed` or `revoked`
state. The invitation remains ordinary membership metadata and gains no secret
field. `IssuedInvitationProof` is deliberately not a serializable contract;
its repr redacts the one generated secret.

`InMemoryInvitationSignIn.invite` is the trusted invitation-issuer adapter. It
validates the high-entropy proof and expiry before asking the existing
enrollment registry to issue the metadata, so an invalid proof leaves no
invitation behind. `accept` checks an unknown id against a non-matching
fingerprint and returns the same `authentication_failed` as a wrong proof. A
matched proof may report that it expired, was revoked or was already used.
Successful redemption accepts the invitation as its named actor, marks the
proof used and gives a direct `invitation-proof` identity to
`InMemoryMemberSessions`; the member session cannot outlive the proof.

`POST /v1/member/sign-in` accepts the proof only in the `Invitation`
authorization scheme and requires an empty body, so a request cannot claim an
actor, membership, Bridge, policy or permission. Success returns the opaque
short-lived member bearer under `Cache-Control: no-store`. The invitation link
puts the proof in the URL fragment; the page removes that fragment before
redemption, retains the returned member bearer in memory and uses the existing
catalog/select/revoke endpoints. The Bridge bearer scheme is rejected. Sign-in
creates no Bridge binding, device selection, installation or execution grant.

## Shared Platform process composition (Productization 1, slice 2c)

`control_plane.app.SharedPlatformState` groups the reference enrollment,
Bridge-token, package, authorization, remote-control, artifact and member-session
stores. `SharedPlatformApplication` builds `ControlPlaneService` and
`MemberService` over those exact instances and owns one `ControlPlaneServer`
plus one `MemberPortalServer`. Starting or stopping the application acts on
both listeners; the transports remain separate even though the state is shared.

`SharedPlatformConfiguration` is closed, serializable and secret-free. It names
unique administrators, listener/port settings, optional local certificate and
private-key **paths**, and `BootstrapInvitation` metadata with a bounded
lifetime. It carries no proof, token, session or key value. A non-loopback
listener requires both TLS paths and fixed control/member ports must differ.
`application_from_config` generates proofs only after the configuration is
valid. `aep-platform serve` requires an explicit invitation output file when
bootstrap invitations exist and creates that file without overwriting one.

`host_runtime.contracts.PlatformBinding.member_portal_url` is an optional
credential-free origin. It applies the same origin shape and non-loopback HTTPS
rules as `base_url`; it is not used by `PlatformClient`. `AgentWeb.platform`
projects it solely as navigation metadata for the browser.

Certificate trust (2026-10-16, `docs/phases/BRIDGE_ENROLLMENT.md` "TLS and
certificate pinning"): `PlatformBinding` and `PlatformPublishBinding` take an
optional `certificate_sha256` (normalized to upper-case colon-separated hex; any
SHA-256 hex form is accepted) or an optional `ca_file` (PEM path), never both.
`PlatformClient`, `MemberPortalPublisher` and `shared_platform.check_bridge`
build their HTTPS handler with `common.certificates.https_handler`: pinned
(handshake, compare, close before sending on a mismatch), CA file, or the default
verified context. A certificate failure is `Failure(code="certificate_untrusted",
retryable=False)` with reachability `unreachable` from `PlatformClient`, and
`PublishError("certificate_untrusted")` from the publisher. Agent Web
`POST /api/settings/shared-platform/certificate` (page token; body
`member_portal_url`, `base_url`) replies `certificates[]` (`url`, `fingerprint`,
`pem` — public certificate only, `trusted_by_system`), `fingerprint`, `pem`,
`trusted_by_system`, `pinned`, `matches_pin`, or `ok: false` with
`certificate_needs_https`, `certificate_unreachable`, `certificate_mismatch`;
`POST /api/settings/shared-platform` accepts `certificate_sha256` (a fingerprint,
or empty to forget; absent keeps the pin; `certificate_pin_invalid`), and its
settings reply carries `certificate_sha256` and `ca_file`.

## Personal Agent Web synchronization (Productization 1, slice 3)

`PlatformProjection` is the typed local Web view of a shared catalog: platform
configuration/reachability, credential-free Member Portal navigation, published
package metadata including its declared categories, synchronized device decisions
and installed flags. Categories are display/filter metadata and grant no entitlement.
Published, authorized and installed remain independent facts and none is an
execution permission.

`PlatformSyncRequest` is a closed empty contract. It cannot select an asset,
claim an actor or carry installation instructions. `POST /api/platform/sync`
requires the loopback Web bearer and this exact empty request, then invokes the
existing `PlatformClient.synchronize` under the Web adapter's one-at-a-time
lock. `PlatformSyncResult` contains the existing five-state reachability result,
typed failure details when it was not answered, identities installed by that
attempt, the active selection count and complete `before`/`after`
`PlatformProjection` values. It carries no credential, artifact bytes or
execution grant. `GET /api/platform` never invokes synchronization.

## Personal Agent Web Workflow launch (Productization 1, slice 4)

`WorkflowLaunchRequest` names one exact `AssetIdentity`, one JSON-object
argument map and an `IdempotencyKey`. It has no actor, Bridge, authorization,
route or model field and rejects embedded secret material. The Web adapter
supplies host identity and a fresh trace to `LocalWorkflowRequest`.

`LocalWorkflowRequest` is the provider-neutral exact local execution boundary.
It is accepted only with `ingress=local`; `LocalAgent.execute_workflow` performs
normal membership/device admission, calls `Gateway.execute_workflow` without
model routing, records a real run and leaves Workflow preflight and every step's
authorization to the existing engine and Bridge policy. Reusing an idempotency
key with the same intent returns the same run. The Web response uses the
existing `LocalAgentOutcome`, so refusal, Workflow status, result, run record and
trace identifiers keep their established meanings.

The installed-asset projection exposes the manifest's `input_contract` and
`output_contract`. These are names, not field schemas. The current generic form
therefore accepts one JSON object and never invents field definitions.

## Personal Agent Web Knowledge asking (Productization 1, slice 5)

`KnowledgeAskRequest` contains one exact Knowledge `AssetIdentity` and one
question. It has no actor, Bridge, route, model, Vault path or authorization
field and rejects embedded credential material. The Web adapter supplies the
running host's actor and Bridge plus a fresh trace, then builds the established
`KnowledgeQueryRequest` as arguments to an exact `LocalCapabilityRequest` for
`knowledge-query/ask@1.0.0`.

`LocalAgent.execute_capability` performs membership/device admission and the
existing Bridge still enforces the capability grant. The existing
`KnowledgeQueryHandler` resolves the exact configured `KnowledgeManifest` and
local `Vault`, runs deterministic retrieval plus the configured model, and
returns the existing `KnowledgeAnswerRecord`. Personal Agent Web preserves its
answer, cited passages, Raw source provenance and trace identifiers. Installed
Knowledge discovery is the intersection of validated local manifests and exact
host bindings; it exposes identity, domain, owner and visibility but never the
local `vault_root`.

Each exact `KnowledgeHostBinding` also accepts the owner-editable
`privacy: "private" | "public"` setting; omission means private. It labels
that Vault independently of other bindings. It does not change the Knowledge
capability grant or the content of a conversation.

## Personal Agent Web model settings (Productization 4, slices 1–2)

`ModelSettingsUpdateRequest` is the explicit local-operator write boundary for
one routing endpoint. It contains a provider, stable alias, model id, base URL,
declared capabilities and optional paired `credential_secret` /
`credential_environment` names. It has no credential-value field, is closed to
extra fields and is converted into the existing `ModelBinding`, `ModelCatalog`,
`ModelEndpoint`, `SecretRef` and `CredentialBinding` contracts.

`POST /api/settings/model` has the same loopback Host-header and per-process
bearer guards as every Personal Agent Web action. The adapter reloads the
current config, replaces only the previous model endpoint's credential
bindings, validates the complete `CompanyHostConfiguration`, and atomically
replaces the configured file. Invalid input changes nothing. Success requires
a host restart and never changes the already-running runtime.

`GET /api/readiness` and `GET /api/settings` are non-secret projections. They
perform no endpoint probe and expose only configuration/readiness facts,
installed counts and whether the named environment variable has a non-empty
value. Installed Knowledge may remain configured while no routing model is
available; in that state deterministic capabilities and the setup interface
start, while `knowledge-query/ask` is not registered.

`ConversationCreateRequest` is closed and empty; the host supplies actor,
session id and timestamps. `ConversationTurnRequest` carries only a session id
and message and rejects embedded credential material. `ConversationRecord`
contains one host actor, a bounded chronological tuple of user/assistant
`ConversationMessage` values, status and assistant trace evidence. Conversation
rows live only in the Bridge's SQLite local state, survive restart, and are
filtered by the running actor. A saved update must preserve the complete stored
prefix, actor and monotonic update time.

The conversation Web adapter passes the stable session id into the existing
`LocalAgentRequest`. It does not turn transcript text into identity,
authorization, model configuration or execution permission. Listing, selecting
and refreshing conversation history perform no Agent call.

## Personal Agent bounded tool loop (Productization 4, slice 4)

`Gateway.converse` projects each command from the current namespace's installed
`SkillManifest` as one provider-neutral `ModelTool`. Its provider name is the
stable `<skill alias>__<command>` pair and maps only to the command's exact
manifest target. The approved `platform.command-arguments.v1` provider schema
carries a JSON object; the installed capability or Workflow remains the source
of truth for its real input validation.

The OpenAI-compatible adapter renders those tools and round-trips assistant
`ModelToolCall` plus `tool` result messages. Unknown symbolic input contracts
fail before transport. Ollama continues to return `tools_not_supported` until
its own wire format is implemented; provider behavior does not leak into the
Agent contract.

`GatewayConversationResult` contains terminal status, human-readable text,
model-turn count, trace and a bounded tuple of `ConversationToolExecution`
evidence. The loop permits five model turns and four tool calls, carries at
most twelve prior user/assistant messages of 4,000 characters each, and limits
one tool observation to 16,000 characters. Unknown tool names are returned to
the model as a refusal without dispatch; repeated calls end as
`tool_loop_limit`. Multiple simultaneous calls are refused because this first
implementation preserves deterministic ordering.

Every resolved capability call uses `BridgeExecutor.execute`; every resolved
Workflow uses `WorkflowEngine.execute`. Local Agent admission occurs before the
loop, Bridge policy is evaluated for every call, and Workflow results are
written through the existing local-run evidence path. Installed/published
status and model text grant no authority. A known deterministic command keeps
the existing non-model route.

## Personal Agent contribution drafts (Productization 4, slice 5)

`ContributionDraftCreateRequest` is the closed browser input. It either names
one exact installed `AssetIdentity` to improve, or proposes a new Skill or
Workflow by kind and slug. It carries a source conversation, summary, expected
and actual behavior, and one to ten acceptance criteria. It has no actor,
namespace, owner, lifecycle, review or publication field.

The Host resolves an improvement against installed Skill, Workflow and
Knowledge manifests and copies the manifest kind and owner. For a new proposal
it supplies the configured namespace and current actor as the draft owner. Up
to twenty recent `ConversationExcerpt` values are copied into the resulting
`ContributionDraft`, retaining message ids, text, roles and assistant trace
identifiers as immutable evidence.

Every record has lifecycle `draft`, `publishable=false`, and separate pending
`BusinessApproval` and `TechnicalPolicy`. It is stored in the Bridge-local
SQLite state and listed only for the running actor. Creation performs no Agent
execution, external write, manifest creation, installation or publication.

## Durable shared Registry (Productization 1, slice 6)

`PackageRegistry` is the control-plane catalog boundary used by authorization,
catalog discovery, installation planning and synchronization. Both the
in-memory reference and `SqliteRegistry` implement `publish`, `discover`,
exact-identity `get` and `plan`; the existing services and Bridge wire do not
depend on storage-specific behavior.

`SqliteRegistry` stores the canonical validated `PublishedAssetPackage` JSON
under its exact `namespace + name + version` identity and artifact bytes under
their declared reference. When bytes are supplied, their SHA-256 digest is
verified before one transaction commits package and artifact. Duplicate exact
versions remain duplicates after restart. A schema version mismatch, invalid
stored package or unavailable database fails closed.

`SharedPlatformConfiguration.registry_path` is optional for inert tests and
must be absolute when set. The deployable example sets it and exposes the
Registry's artifact mapping to the unchanged synchronization service.
`SqliteRegistry` itself contains no credentials, invitation proofs, member
sessions, device selections, remote jobs, execution grants or Bridge/local
execution state. `SharedPlatformState.durable` uses separate allowlisted JSON
tables in the same database for identity, browser login and authorization
selection records; Registry package and artifact semantics remain independent.

## Asset name ownership and versions (2026-10-07)

Owner decisions and plan: `docs/phases/ASSET_OWNERSHIP.md`.

`common.ownership.AssetNameOwnership` is the record for one name:
`namespace`, `name`, `owner` (`common.assets.Owner`), `co_editors` (unique
member actor ids; a user owner is never also listed) and `deprecations`.
`VersionDeprecation` is `version`, `reason`, optional `replacement` (another
version of the same name) and `deprecated_by`. `manages(actor, groups)` is
true for the owner or a member of an owning group (`common.identity.owns`,
the same rule `entitled` uses); `may_publish` adds the co-editors.
`version_key` is SemVer 2.0.0 precedence (build metadata ignored);
`next_version(versions, change)` increases the highest version at
`patch`/`minor`/`major`, and a name with no versions starts at `1.0.0`;
`above_all(version, versions)` is the manual-version rule.

`PackageRegistry` adds:

- `publish_as(package, *, publisher, groups, change=None)` (SQLite also takes
  `artifact`), the member publish. `admit_member_version` applies, in the same
  transaction as the insert: the first publish of a name must declare the
  publisher or one of their groups as owner; a later one needs `may_publish`
  (`publisher_not_authorized`) and must declare the record's owner
  (`owner_mismatch`); with `change` the version must equal the assigned one
  (`version_not_assigned`), otherwise it must be above every existing version
  (`version_not_above_highest`); `duplicate_package` as before.
- `publish(package)` stays the platform's own path (preview seed,
  migration). It creates the record from the package's owner on a name's
  first publish, refuses `owner_mismatch` against an existing record, and does
  not order versions, so a historical catalog can be imported as it was.
- `ownership(namespace, name)` and `save_ownership(updated, *, previous)`, a
  compare-and-set that refuses `ownership_changed` when the stored record is
  no longer `previous`, and `name_missing`.
- `access(namespace, name)` and `save_access(access)` (2026-10-15): the
  name's `NameAccess` record, replaced whole; `name_missing` for a name with
  no versions. `SqliteRegistry` keeps it in an additive `name_access` table
  (`schema_version` stays `1`).

A package's artifact carries its own version, so the platform never
renumbers a built package. `control_plane.ownership.AssetOwnershipService`
offers `next_version`, `publish` and `publish_next(..., change, build)`,
which asks for the assigned identity, calls `build(identity)` for the package
and bytes, publishes, and asks again (up to three times) if another publisher
took that version first. The same service gives the owner `add_co_editor`,
`remove_co_editor`, `transfer` and `deprecate`, refusing `not_name_owner`,
`co_editor_unknown` / `co_editor_exists` / `co_editor_missing`,
`owner_unchanged`, `new_owner_unknown` (a user owner must be an active
member), `version_missing` and `version_deprecated`. A member reads a record
only when they may publish the name or use one of its versions; anyone else
gets `name_missing`. Identity comes from a valid `AuthenticatedActor` and
groups from the platform's own member record.

`SqliteRegistry` keeps records in a `name_owners` table. The table is
additive and `schema_version` stays `1`, so the previous code still opens a
database this code wrote. Opening a database derives a record for every name
without one from the owner declared by that name's earliest version (lowest
SemVer precedence), and a publish does the same inside its transaction for a
name the previous code published meanwhile.

The member portal (`/v1/member/assets/...`) exposes `ownership`,
`next-version`, `co-editors/add`, `co-editors/remove`, `transfer` and
`deprecate` with `AssetNameRequest`, `AssetNextVersionRequest`,
`AssetCoEditorRequest`, `AssetTransferRequest` and `AssetDeprecateRequest`;
replies are `AssetOwnershipReply` or `AssetNextVersionReply`. Requests carry
no actor.

### Member publish with a review queue (2026-10-15)

`docs/phases/MEMBER_PUBLISH.md`. A submission is not a package (a
`PublishedAssetPackage` is published by definition), so the queue keeps its own
`common.member.AssetSubmission`: id, kind (`skill` / `workflow`), the assigned
identity, submitter, change level, optional note, artifact sha256, risk and
required permissions, the owner and visibility it will be published with
(optional; absent on records from before 2026-10-15), status (`pending` / `approved` / `rejected` /
`withdrawn`), reviewer, reason and times. A decision names its reviewer and
time; a rejection gives its reason.

`control_plane.submissions.SubmissionService`:
- `submit` parses the manifest as `WorkflowManifest` or `SkillManifest`, refuses
  a member who may not publish the name, and refuses a Skill whose Workflow
  targets are neither published nor pending from the same member
  (`missing_dependency`). It assigns the next version above published and
  pending ones. The owner is the name's recorded owner; for a new name it is
  the team or organization the manifest declares when the submitter belongs
  to it (their platform groups), otherwise the submitter. The visibility is
  the request's `visibility` or else the manifest's. It sets
  `lifecycle: published` and resets both reviews to pending, keeping only
  the author's risk, permissions and policy refs. It appends a
  `member-submission` provenance entry, then stores the re-serialized
  manifest, at most 192 KiB (`artifact_too_large`).
- `approve` refuses the submitter (`self_review_refused`). It writes the
  reviewer and evidence `submission:<id>; ...` into both reviews and builds
  the package from the approved manifest's bytes. It then publishes through
  `AssetOwnershipService.publish_reviewed`, as the submitter with their
  current groups, under the same Registry rules. A version no longer above
  the highest is `version_superseded`.
- `reject` needs a reason. `withdraw` is the submitter's own. A decision is
  conditional on the status still being pending.

`SubmissionStore` shares the Registry's SQLite file (`submissions` table) or
lives in memory without one.

Member portal operations:
- `assets/submit` (`AssetSubmitRequest`: kind, change, note, optional
  `visibility` `private|team|organization|public`, manifest);
- `assets/submissions`;
- `assets/submissions/withdraw`;
- administrator only: `admin/submissions/list|get|approve|reject`.

New codes: `manifest_invalid` 400, `artifact_too_large` 413,
`missing_dependency` / `submission_not_pending` / `version_superseded` 409,
`submission_missing` 404, `self_review_refused` 403.

Who can use a published name (2026-10-15):
- `assets/access` (`AssetAccessListRequest`: `scope` `mine` | `all`) returns
  `AssetAccessListReply` of `AssetAccessEntry` (namespace, name, kind, owner,
  versions, `declared_visibility` of the highest version, effective
  `visibility`, `access` record). `mine` is the names the member manages;
  `all` is for a platform administrator (`not_name_owner` 403 otherwise).
- `assets/access/update` (`AssetAccessUpdateRequest`: namespace, name,
  `visibility` or null, `members`, `groups`) replaces the record; only the
  owner, a member of an owning team or a platform administrator
  (`not_name_owner` 403); an unknown member is `access_member_unknown` 400.
  Selections already made are not withdrawn.

A `ValidationError` on a name field (`actor`, `groups`, `members`,
`co_editor`) answers `invalid_request` with `reason` `account_invalid` or
`group_invalid` and a `message` stating the rule; the value is never echoed.

`logins/issue-agent` issues a `Personal Agent` login for the signed-in member
and returns its bearer once. The Agent trades it at `session` for one-hour
sessions and never sends it to the Bridge API.

`logins/revoke` (2026-10-19) {`login_id`} ends one of the signed-in member's own
active logins: 200 {`login_id`, `status: revoked`}. Another member's login, an
unknown id and an ended login all answer 404 {`code: login_missing`}; a body
other than exactly `login_id` answers 400 `invalid_request`. Agent Web uses it
for the code it replaced on renewal and for the browser login of its own
password sign-in; a platform without the route answers 404 `invalid_request`.

Agent Web (2026-10-19, `docs/phases/PASSWORD_SIGN_IN.md`):
`POST /api/settings/shared-platform/sign-in` {`member_portal_url`, `base_url`,
`account`, `password`} answers the Shared platform settings plus `signed_in: true`,
or {`ok: false`, `code`, `message`} (`authentication_failed`, `password_missing`,
`account_invalid`, `device_owner_mismatch`, `bad_reply`, a platform code). The
settings (`GET /api/settings/shared-platform`) add `agent_code` {`state`: `none` |
`unknown` | `valid` | `renew_soon` | `expired`, `login_id`, `expires_at`,
`estimated`, `source`, `renewals`, `unrevoked`} and `bridge_token` {`expires_at`,
`days_left`, `remind` (under 14 days), `expired`}. Never a secret.

### Bridge self-enrollment (2026-10-15)

`docs/phases/BRIDGE_ENROLLMENT.md`. Member portal operations:
- `bridges/enroll` (`common.member.BridgeEnrollRequest`: `device` and
  `advertisement`, the same shape as the Agent's `EnrollmentRequest`). The device
  and the advertisement must name the signed-in member (`device_owner_mismatch`
  403), and the device must be a `company_workstation` (`administrator_required`
  403). A disabled member gets `actor_disabled`, a disabled device
  `device_disabled` 409, a device bound to another member `device_in_use` 409.
  `MemberService.enroll_bridge` registers the device, or reuses one this member
  registered (refreshing its advertisement), binds the member as `device_admin`
  unless already bound, revokes the pair's tokens and issues one for
  `BRIDGE_TOKEN_LIFETIME` (90 days). The reply is the only place the secret
  appears: `bridge_id`, `token_id`, `secret`, `issued_at`, `expires_at`.
- administrator only: `admin/bridges/list` (`AdminBridgeListReply` of
  `AdminBridgeEntry`: device, members, last enrolled, token expiry) and
  `admin/bridges/disable` (`AdminBridgeRequest`), which disables the device and
  revokes its working tokens. `InMemoryEnrollmentRegistry.devices()` and
  `InMemoryAccessTokens.history_for(bridge_id)` support the list.

Agent side: `host_runtime.shared_platform` (URL checks with the
`PlatformBinding` / `PlatformPublishBinding` rules, host.json rewrite with a
backup, `AEP_SHARED_PLATFORM_TOKEN` for the `shared_platform_token` secret,
`EnrollmentRecord` in `workspace/shared-platform.json`, no secret) and
`AgentWeb.shared_platform_settings` / `update_shared_platform` behind
`/api/settings/shared-platform`. `MemberPortalPublisher.me()` and `.enroll()`
call the portal. `PlatformProjection` carries `bridge_id` and `assets_only`.

### Platform overview and member administration (2026-10-15)

`docs/phases/PLATFORM_OVERVIEW.md`. Administrator-only member portal operations
(`not_administrator` 403 for anyone else, `authentication_failed` 401 without a
session); no reply carries a token value or fingerprint, an invitation proof, a
session or a login:
- `admin/overview` (body `{}`; `control_plane.overview.AdminOverviewReply`):
  `generated_at`; `counts` (`OverviewCounts`: Bridges active/disabled, members
  active/disabled, pending invitations, per kind `names` and `versions` for
  `skill`, `workflow`, `knowledge`, `agent`, `bridge_extension`, Application
  names and versions, submissions per status); `bridges` (`AdminBridgeEntry`);
  `assets` (`OverviewAsset`: every published name of those kinds, regardless of
  entitlement, with owner, co-editors, latest version, all versions,
  deprecations, declared and effective visibility, the `NameAccess` record,
  distinct Bridges that selected any version, `published_at` of the latest
  version when it was approved through review, pending submissions);
  `submissions` (every `AssetSubmission`, newest first); `applications`
  (`ApplicationProjection`); `members` (`OverviewMember`: role, groups, status,
  invitation state `accepted`/`pending`/`expired`/`revoked`, invited by,
  invitation expiry, bound Bridges, last role/group change).
- `admin/members/update` (`AdminMemberUpdateRequest`: `actor`, `role`,
  `groups`, replacing both) -> `AdminMemberReply`. Audited as a
  `common.enrollment.PlatformUserChange` in the additive `identity_user_changes`
  table. Demoting the last active `platform_admin` is `last_administrator` 409;
  an unknown member is `actor_unknown`.

`AdminBridgeEntry` gained `last_seen_at`, `last_seen_operation` (the last Bridge
API call a token proved, recorded by `control_plane.activity.BridgeActivity` in
`ControlPlaneService`, kept durable in the additive `bridge_activity` table at
most once a minute per Bridge) and `selections` (add-on selections in force).
`AssetAccessEntry` gained `co_editors`. A platform administrator may now also
manage co-editors, transfer and deprecation of any name (`AssetOwnershipService.
_managed`); publishing stays with the owner, owning team and co-editors.

### Asset content (2026-10-15)

Member portal operation `assets/manifest` (member session), stable for the
portal and Agent Web:
- request `common.member.AssetManifestRequest`: `asset` (exact
  `namespace/name@version`);
- reply `common.member.AssetManifestReply` (`schema_version` `"1"`): `package`
  (the `PublishedAssetPackage`), `manifest` (the published artifact parsed as a
  JSON object, or null when it is not one), `artifact_sha256`, `artifact_size`,
  `owner` and `co_editors` (the name's current record), `versions` (the
  versions of the name the caller may use, lowest first), `visibility`
  (effective), `deprecation` (`VersionDeprecation` or null), `published_at`
  (approval time when it came through review, else null).
- A version that is not published, or is not shared with the caller
  (`entitled_in`, which applies the name's access record), is
  `asset_not_published` 404; a platform administrator reads every version. An
  artifact above `MAX_MANIFEST_BYTES` (512 KiB) is `artifact_too_large` 413.
  Manifests carry secret references by name only; submission already refuses
  embedded secrets.

### Browser sign-in ticket (2026-10-15)

Member portal operations for one-click sign-in from Agent Web
(`docs/phases/PLATFORM_OVERVIEW.md`):
- `browser-ticket`: member session, body `{}`; reply `ticket` (`id:secret`,
  single use) and `expires_at` (at most 60 seconds). `actor_disabled` for a
  disabled member.
- `sign-in/ticket`: `Authorization: Ticket id:secret`, empty body; reply
  `session`, `login`, `expires_at` as `sign-in/password`. Refusals
  `authentication_failed` 401, `ticket_used` 409, `ticket_expired` 401,
  `actor_disabled` 403. Only accepted at that exact path, never from a query.
- Agent Web: `POST /api/platform/portal-link` (`tab`?, `asset`?) answers `ok`,
  `signed_in`, `url` (`<portal>/#ticket=...&bridge=...&tab=...&asset=...`, or
  the plain portal with `code` and `message`); `POST
  /api/platform/asset-content` (`kind`, `asset`) answers `ok` and `content`
  (the `AssetManifestReply`), or `code` and `message`.

### Action card and change proposal (2026-10-15)

One card for every "the Agent asks, the person decides" moment
(`docs/phases/AI_PROPOSED_CHANGES.md`, next `docs/phases/AGENT_MODE_BACKENDS.md`):
- `common.action_cards.ActionCard`: `card_id` (`[a-z]{2}-[0-9a-f]{12}`; `cp-` change
  proposals), `kind` (the deciding handler), `title`, `rows` (`label`, `before`,
  `after`; only changing fields), `preview` (a body shown as written), `reason`,
  `effects`, `buttons` (`action` `[a-z_]{1,24}` sent to the server, `label` shown,
  `style` primary/secondary/danger; distinct actions), `status` (`pending` keeps the
  buttons live), `status_label`, `outcome`, `outcome_ok`, `link` (`view`, `anchor`,
  `capability_kind`, `asset`), `expires_at`, `web_only`, `message` (the turn's answer
  text). Never a secret value.
- A host tool returns a card under `data.action_card`; the Gateway ends the turn with
  `message`. `ConversationMessage.action_card` keeps the last drawn card on the answer;
  a decision redraws it (`LocalState.set_message_card`) and appends
  `[card <id>] <status>: <outcome>` to that answer's `tool_summary`.
- Agent Web: `GET /api/cards` (open cards, any channel; not draft install cards `dr-`,
  which wait on their answer and in Capabilities > Drafts), `GET /api/cards?card_id=`,
  `POST /api/cards/decide` (`card_id`, `action`) answers `ok`, `code`, `message`,
  `card`. Codes: `card_unknown`, `card_action_unknown`, `proposal_<status>`,
  `proposal_stale`, `web_only`, `applied`, `apply_failed`, `cancelled`.
- Telegram: callback data `card:<card_id>:<action>` (at most 64 bytes); owner only.
- Server record: `host_runtime.card_store.PendingRecord` (`card_id`, `status`,
  `created_at`, `expires_at`, `decided_at`) extended per handler;
  `ChangeProposal` adds `kind`, `values`, `rows`, `reason`, `effects`, `link`,
  `session_id`, `actor`, `channel`, `fingerprint` (SHA-256 of the current settings it
  was based on), `telegram_ok`, `task_id`, `outcome`, `outcome_ok`.
- Model tool `propose_change` (`host.change-proposal.v1`): `kind` (laya,
  shared_platform, model, telegram, workflow_settings, capability, platform_add,
  publish), `values` (only what changes), `reason`. A refusal is a failed host outcome
  `proposal_refused` with a message naming fields, never values.

### Agent mode (approval cards for coding-agent backends) (2026-10-15)

`docs/phases/AGENT_MODE_BACKENDS.md`. Reuses "Action card and change proposal":
- Card ids `pm-` (permission, first mail read, Knowledge write; `ActionCard.kind`
  `agent_permission`) and `ml-` (an email to send; `agent_mail`). Buttons: `allow`,
  `allow_session` ("Allow this folder for this conversation", "Allow <program> for this
  conversation", "Allow for this conversation"), `deny`; mail `send`, `keep_draft`,
  `cancel`. Statuses `pending`, `allowed`, `allowed_session`, `denied`, `expired`
  (= Deny after 10 minutes); mail `sent`, `kept`, `cancelled`, `failed`, `expired`
  (= kept as a draft). `web_only` is always true; Telegram gets `web_only`.
  Decision codes: the new status, `permission_<status>` / `mail_<status>` for a card
  already decided, `card_action_unknown`, `card_unknown`, `web_only`.
- Server records: `host_runtime.agent_mode.AgentCard(PendingRecord)` (`kind`,
  `session_id`, `run_id`, `backend`, `tool`, `request_kind` read/write/command/network/
  other, `title`, `paths`, `command`, `folder`, `preview`, `reason`, `scope` (what
  "for this conversation" remembers), `task_id`, `outcome`, `outcome_ok`, `channel`) in
  `workspace/agent-mode/cards.json`; `host_runtime.agent_mail.MailCard` (`entry_id`,
  `fingerprint` of to/cc/subject/attachment names, `to`, `cc`, `subject`, `body`,
  `attachments`, ...) in `workspace/agent-mode/mail-cards.json`. Commands, paths and
  previews are stored with credential-shaped text redacted.
- `ConversationMessage.action_cards`: the cards an agent-mode turn showed, as decided
  (at most 60), plus one `[card <id>] <title>: <status>` line per card in the answer's
  `tool_summary`.
- Settings `host_runtime.agent_mode_settings.AgentModeSettings`: `claude_code`,
  `codex` (always refused), `copilot` (bool, default false), `default_root`, `mail`
  (`integrations.outlook_mail.MailScope`: `folders`, `max_days` 1-365, `excluded_senders`
  (address or `@domain`), `excluded_folders`). Per conversation `SessionAgentState`:
  `folder`, `read_folders` (at most 20), `grants` (`read_folders`, `write_folders`,
  `programs`, `tools`), `mail_read`.
- Routes: `GET /api/agent-mode`, `POST /api/agent-mode/settings`,
  `GET /api/agent-mode/session?session_id=`, `POST /api/agent-mode/session`
  (`session_id`, `folder`, `read_folders`), `GET /api/cards?session_id=`.
- MCP `POST /mcp/agent` (server `aep-agent`), bearer = the running turn's own random
  token only. Tools: `permission` (Claude Code only; `{tool_name, input, tool_use_id}`
  -> text `{"behavior": "allow", "updatedInput": ...}` or `{"behavior": "deny",
  "message": ...}`), `outlook_search`, `outlook_read`, `outlook_draft`,
  `knowledge_sandboxes`, `knowledge_step`, `knowledge_run_questions`,
  `knowledge_questions_status`. No tool sends mail.
- Capabilities `outlook.search` / `outlook.read` (`outlook.search.input.v1`: `query`,
  `sender`, `folder`, `days`, `limit` <= 50; `outlook.read.input.v1`: `message_id`),
  side effect `read`, refusal codes `folder_unknown`, `message_unknown`, `mail_failed`,
  `library_missing`, `outlook_missing`.

### Draft install card (2026-10-16)

Reuses "Action card and change proposal" (`docs/DECISIONS.md` 2026-10-16 "A conversation that
drafts a Workflow or Skill shows its install card"):
- Card ids `dr-`, `ActionCard.kind` `draft_install`. Buttons `install` (primary), `try`
  ("Run once to try"; Agent Web only, read-only Workflows whose required run fields have
  defaults), `not_now`. Statuses `pending`, `installed`, `not_now`, `superseded` (a newer
  card for the same draft), `stale` (the draft changed or is gone), `failed`, `expired`
  (30 days). Decision codes: `installed`, `tried`, `not_now`, `draft_<status>` for a closed
  card, `draft_stale`, `try_unavailable`, `try_needs_values`, `install_failed`,
  `card_action_unknown`, `card_unknown`. A decision reply adds `session_id` and, after a
  Workflow install, `workflow_form` (a run form offer with `origin` `install`).
- Server record `host_runtime.draft_cards.DraftCard(PendingRecord)`: `session_id`,
  `candidate_id`, `asset` workflow/skill, `revision`, `digest`, `name`, `title`, `channel`,
  `source`, `read_only`, `tryable`, `tried`, `tried_ok`, `approval_id`, `asked_by` (the
  agent's install request it answers), `outcome`, `outcome_ok`; in
  `workspace/authoring/draft-cards.json`.
- Turn end: `AgentWeb.draft_turn_cards(session_id, since, channel, message)` adds the cards
  to the answer's `action_cards` and one `[card <id>] <title>: <status>` line to its
  `tool_summary`; replaced cards are redrawn in place. `LocalState.set_message_card(...,
  workflow_form=)` finds a card in `action_card` or `action_cards`.
- `/mcp/authoring` accepts a running turn's own token (agent-mode run token, or the
  `copilot_agent` turn token passed as `LocalConversationBackends.complete(...,
  authoring_token=)`); `ExternalAuthoring(..., session_id=)` then puts that conversation on
  drafts (`ChatCandidate.session_id`, new `SkillCandidate.session_id`) and install requests,
  never on run requests.

### Revising an installed Workflow (2026-10-19)

`docs/phases/WORKFLOW_REVISION.md`; decision `docs/DECISIONS.md` 2026-10-19.
- Conversation tools (`host_runtime.chat_authoring`):
  - `authoring__get_workflow` (`host.authoring.get.v1`): `candidate_id` (a draft) or `workflow`
    (installed: `namespace/name@version`, `name@version`, `namespace/name`, `name` = highest
    installed version), optional `offset`. Installed body: `workflow`, `owner` (`type:id`),
    `visibility`, `lifecycle`, `description`, `parameters`, `steps`, `checks`,
    `progress_steps`, `occupies_machine`, `secret_names`, `origin: installed`, `digest`, `next`.
    Draft body as before plus `checks` and `revision_of`. Over `MAX_VIEW_CHARS` (20,000) JSON
    characters: `workflow`, `truncated`, `total_chars`, `offset`, `next_offset`, `json_text`,
    `notice`. Codes `workflow_unknown` (with close readable names), `workflow_ambiguous`,
    `workflow_reference_invalid`, `workflow_missing`, `candidate_unknown`.
  - `authoring__revise_workflow` (`host.authoring.revise.v1`): `workflow`, optional `title`.
    Data `candidate_id`, `workflow`, `revision_of`, `base_digest`, `forked`, `continued`, `next`,
    `note` when forked; `member_of_team`, `membership_source` (`platform`, `platform_cache`,
    `declared`) and `note_membership` when kept in place as a team member (2026-10-19).
    Failure `workflow_invalid` with `problems`.
  - `authoring__show_capability_source` (`host.authoring.capability_source.v1`): `capability`,
    optional `file`, `offset`. Data `ok`, `package`, `read_only: true`, `how_to_change`, and
    `files` [{`file`, `chars`}] or `file`, `source`, `total_chars`, `offset`, `next_offset`,
    `truncated`, `notice`. Codes `capability_package_unknown`, `capability_file_refused`.
- `ChatCandidate.base_digest` (optional); a revision's `source` is
  `revision:<namespace/name@version>` and stays so through later edits. `member_team` and
  `membership_source` (optional, 2026-10-19) record a team member's in-place revision.
- Team membership (2026-10-19, `host_runtime.team_membership`): `TeamMembership` {`teams`,
  `source` (`platform` | `platform_cache` | `declared` | `none`), `account`, `checked_at`};
  workspace files `team-membership.json` {`declared_teams`: up to 20 `Symbol`s} and
  `team-membership-cache.json` (a `TeamMembership`). Source: the existing Member Portal
  `POST /v1/member/me` (`MemberIdentityReply.groups`, only the signed-in member's own) via
  `MemberPortalPublisher.membership()`. Agent Web `GET /api/settings/teams` and
  `POST /api/settings/teams` {`declared_teams`: list or comma-separated text} answer
  {`ok`, `declared_teams`, `teams`, `source`, `account`, `checked_at`} or {`ok: false`, `code`
  (`teams_invalid`, `teams_unavailable`), `message`}; page token required, never a credential.
- Draft card preview: "Revision of <ns/name> <a> → <b>" (then "Revision as a member of team
  <id> (<where>)" for a team member) or "Fork of <identity> as <identity>",
  "Changes:" lines, "Installing it keeps <identity> installed and its run history."
- External (`host_runtime.mcp_server`, `aep-host assets`): `aep_show_installed_workflow`
  {`workflow`, `offset`} / `show-installed-workflow --workflow [--offset]`;
  `aep_revise_workflow` {`workflow`, `title`} / `revise-workflow --workflow [--title]`. Only
  Workflows owned by the Host's owner with a `chat-candidate:` validation reference; otherwise
  `{ok: false, code: workflow_withheld, next}`.

### Business cards and org chart (2026-10-20)

`docs/phases/BUSINESS_CARDS.md`; decision `docs/DECISIONS.md` 2026-10-20.
- Capabilities `business-cards/<name>@1.0.0` (`capabilities.business_cards.handlers`), contracts
  `business-cards.<name>.input.v1` / `.output.v1`, policy ref `personal-contacts-policy`, risk
  `low`, permission `business-cards.<name>`. Store per actor: the `contacts/org` space of the
  actor's Memory Service, `<workspace>/memory/<actor-key>/memory.sqlite` (accumulated memory M1,
  below); before M1 `<workspace>/business-cards/<actor-key>/cards.db` (`actor_key`), moved once.
  - Writes (`side_effect: write`, `approval_required: true`, confirmed standing by the Host):
    `add-card` (`AddCardRequest`: card fields, `uncertain` [field names],
    `romanised_name_printed`, `other_text` (printed text not placed in a field; scanned only for
    the 統一編號, not stored; 2026-10-20 re-test), `image_path`, `card_date`) → `AddResult`
    {`person_id`, `name`, `company`, `outcome` (`created` | `updated` | `unchanged`), `existed`,
    `matched_by` (`image` | `email` | `name_company` | `romanised_name`), `changes` [{`field`,
    `label`, `old`, `new`}], `kept` [{`field`, `label`, `current`, `offered`, `reason`
    (`user_set` | `older_evidence` | `uncertain` | `email_differs` | `less_complete` |
    `lower_trust` (M1: a lower trust class than the stored value's, e.g. C4C after a card))}],
    `uncertain`, `needs_confirmation` [field names], `to_confirm` [{`field`, `label`,
    `stored`}], `dropped` [{`field`, `label`, `value`, `reason` (`not_on_card`)}],
    `email_differs` ({`stored`, `read`} or null), `proposals` [`ProposalView`], `match`
    (`MatchSummary`), `status`, `summary`, `observation_id`, `change_id`}. `label` is the
    field's Chinese name (`contracts.FIELD_LABELS`). `MatchSummary` (third live test
    2026-10-20) {`by` (`image` | `email` | `name_company` | `romanised_name` | `new`),
    `by_label`, `person_id`, `name`, `company`, `lead` (「已對到既有聯絡人 <姓名>（<公司>），依…比對。」
    or 「已新增聯絡人 …」), `changed`, `kept`, `needs_confirmation` [Chinese labels]}.
    `ProposalView` {`proposal_id`, `field`, `label`, `current` (stored now), `proposed`,
    `source`, `source_label`, `observation_id`, `person_id`, `name`, `company`, `created_at`}:
    any automatic reading that differs from a user-set or confirmed value (or another email for
    a matched person) is one open proposal, and a field with an open proposal is in
    `needs_confirmation`. Phone, fax and mobile compare by digits and extension
    (`names.phone_key`).
    `add-from-signature` {`entries`: 1–50 card fields +
    `message_id`, `message_date`, `uncertain`} → {`results`: [`AddResult`]};
    `store-candidates` (2026-10-20 re-test) {`candidate_ids`: 1–50 ids from this conversation's
    latest harvest (`s1`, ...) or [`all`]} → {`results`: [`AddResult`], `stored`,
    `already_stored`, `unknown` [ids]}: stored with source `email_signature`, the candidate's
    message id and date; refused `candidates_expired` when the conversation (`<channel>:<session
    id>`) has none left (one hour after the harvest); `edit-person`
    {`person`, `fields` (optional), `confirm` [field names], `clear` [field names], `accept`
    [field names: take the field's newest open proposal; refused `proposal_unknown` without
    one], `reason`} → {`person_id`, `name`, `changes`, `confirmed`, `already_confirmed`,
    `accepted`, `rejected`, `proposals`, `needs_confirmation`, `to_confirm`, `change_id`}
    (`confirm` rejects the field's open proposals with a `confirm` row; the read value, in
    `fields` or by `accept`, accepts them with a `field` row; undo reopens them);
    `set-status` {`person`, `status` (`left` | `active`), `reason`, `effective_date`} →
    {`person_id`, `name`, `old_status`, `new_status`, `left_at`, `change_id`,
    `old_status_label`, `new_status_label` (在職 / 已離職), `undo_hint`} (no `said_by`
    since 2026-10-20: who is the request's `<actor> via <channel>`, also in history actors,
    `status_set_by` and reporting lines); `set-reporting-line` {`person`, `manager`, `evidence_kind` (`signature` |
    `email_content` | `title_inference` | `user`), `evidence_ref`, `confidence` 0–1,
    `inferred`} and `remove-reporting-line` {`person`, `reason`} → {`person_id`, `name`,
    `manager_id`, `manager`, `evidence_kind`, `inferred`, `replaced`, `removed`, `change_id`};
    `undo` {`change_id`} → {`undone`, `reverted` [history items], `change_id`, `note`
    (what was reverted, no ids)};
    `import-hermes` {} → {`found`, `rows`, `imported`, `already`, `people_created`,
    `people_updated`, `source`}.
  - Reads: `find` {`query`, `status` (`active` | `left` | `any`), `limit` ≤ 100} and `list`
    {`company`, `source` (`card` | `email_signature` | `user` | `import` | ""), `status`,
    `limit` ≤ 200} → {`people`: [`PersonView`], `total`, `company` (the stored company the
    query or `company` named, else "")}; `history` {`person`, `limit`} →
    {`person`, `history` [{`change_id`, `at`, `actor`, `kind`, `field`, `old`, `new`,
    `reason`, `source`, `at_local` (Asia/Taipei, `YYYY-MM-DD HH:MM`), `kind_label`,
    `field_label`, `source_label`, `old_display`, `new_display`}], `observations`
    [{`observation_id`, `source`, `source_date`, `source_ref`, `uncertain`, `source_label`}],
    `proposals` [`ProposalView`]}; `proposals` {`person` (optional), `limit` ≤ 200} →
    {`proposals` [`ProposalView`], `total`, `note`};
    `org-chart` {`company`, `include_left`, `format` (`png` default | `html` | `both`),
    `harvest_first` (M2, default false)} →
    {`company`, `people`, `left_shown`, `left_omitted`, `lines_evidenced`, `lines_inferred`,
    `format`, `png_path` ("" for html), `html_path` ("" for png), `legend_path`,
    `legend_markdown`, `note`, `attach` [{`path`, `media_type` (`image/png`, `text/html`,
    `text/markdown`), `filename`}], `harvest` (M2: the harvest result, or null), `harvest_note`
    (why the harvest was skipped)}; the HTML is one self-contained page (inline CSS, script
    and JSON data with `<`, `>`, `&` escaped; no network) built from the same rows, always
    with the people who left (toggled, shown by default only with `include_left`);
    `harvest-signatures` {`domain` or `company` (M2: the stored company's mail domains), `days`
    (capped at the mail scope's `max_days`), `limit` ≤ 40, `folder`, `full` (M2: reset the sync
    state, read the full scope)} → {`scanned`, `from_domain`, `with_signature`, `candidates` [card fields +
    `candidate_id`, `message_id`, `message_date`, `uncertain`, `existing_person_id`,
    `would_change`], `note`, `skipped` [{`code`, `count`}], `skipped_note`, `expires_at`,
    `without_signature`, `same_sender`, `unreadable_signature`, `scan_note` (led by the window,
    「從 10/19 之後的新信：掃描 5 封，1 封有簽名檔，4 封沒有簽名檔。」), and M2: `already_seen`,
    `over_limit`, `truncated`, `domains` [{`domain`, `source`, `mode` (`first` | `incremental` |
    `reset` | `extractor`), `since`, `synced_to`, `note`}]}; the candidates are kept in the
    actor's store for this conversation (table `candidates`; fields, message id and date only)
    until `expires_at` or the next harvest that finds someone. Refusal `company_has_no_domain`.
  - A company in `org-chart`, `list` and `find` resolves against the stored companies: the name
    without legal suffixes, then an alias (a capitalised 2–6 letter short name such as `WNC`, or
    an email / website domain other than a public mail service), then an unambiguous part of a
    name; the result names the canonical spelling (decision 2026-10-20 "How a company query
    finds the company").
  - `PersonRef` {`person_id` | `name` (local or romanised) + optional `company`}. Card fields:
    `name`, `romanised_name`, `company`, `company_tax_id`, `business_group`, `division`,
    `department`, `title`, `honorific`, `phone`, `ext`, `mobile`, `fax`, `email`, `address`,
    `website`, `notes`. `PersonView` adds `needs_confirmation`, `status_label`,
    `updated_at_local`. History kinds include `confirm` and `unconfirm` (its undo). Labels:
    `contracts.SOURCE_LABELS`, `STATUS_LABELS`, `KIND_LABELS`, `MATCH_LABELS`.
  - Refusal codes: `person_unknown`, `person_ambiguous`, `person_unspecified`,
    `card_without_name`, `line_to_self`, `line_cycle`, `change_unknown`,
    `change_already_undone`, `undo_conflict`, `company_has_no_contacts`,
    `chart_renderer_missing`, `import_unreadable`, `model_not_configured`, `model_unavailable`,
    `candidates_expired`, `proposal_unknown`, and the mail codes of `outlook.search` /
    `outlook.read`.
  - Signature model call: structured output `business-cards.signature.v1`
    {`people`: [{`i`, card fields except `email`/`notes`, `uncertain`}]}, ≤ 10 blocks per call.
- `LocalPolicy.confirm_writes(spec)` / `confirmed_writes`: a host-declared standing
  confirmation for a low-risk `write` (anything else raises); `confirmation_needed` is false for
  those capabilities. Grants still apply.
- Conversation tools (`host_runtime.business_cards_tools`, `host.cards__<op>.v1`, offered while
  some version of `engineering/business-cards` is switched on): `cards__add_card`,
  `cards__store_candidates`, `cards__add_from_signature`, `cards__edit_person`, `cards__find`,
  `cards__list`,
  `cards__history`, `cards__proposals`, `cards__set_status`, `cards__set_reporting_line`,
  `cards__remove_reporting_line`, `cards__undo`, `cards__org_chart`,
  `cards__harvest_signatures`, `cards__import_hermes`; each dispatches with `origin: model`,
  after dropping identity keys (`said_by`, `set_by`, `actor`, `recorded_by`, `confirmed_by`) from
  the model's arguments. A succeeded call's data also carries `field_labels` (field name →
  Chinese label). A failed call's `failure.message` is `<Chinese sentence>（<code>）` plus
  `: <Bridge message>` when the Bridge gave a specific one (`FAILURE_TEXT`).
- Files in Agent Web chat (owner 2026-10-20): `GET /api/conversations/file?session_id&path`
  (page token) serves a file listed on one of that conversation's messages (an answer's
  tool files or the person's attachments) that lies in the workspace: images as themselves,
  `.md` as `text/markdown`, other text (HTML included) as `text/plain; charset=utf-8`, anything
  else as `application/octet-stream`. `GET /api/conversations/view-link?session_id&path` (page
  token) → {`ok`, `url`: `/view/file?nonce=<random>`, `expires_in` (900 s)} for a listed
  `.html`/`.htm` file, else 404 {`ok`: false, `code`: `file_unknown`}. `GET /view/file?nonce=`
  (no token; the nonce lets in that one file while it is still listed) serves it as
  `text/html` with `Content-Security-Policy: default-src 'none'; script-src 'unsafe-inline';
  style-src 'unsafe-inline'; img-src data:; font-src data:; form-action 'none'; base-uri
  'none'; frame-ancestors 'self'; sandbox allow-scripts` (`web.FILE_VIEW_CSP`),
  `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: no-referrer`; unknown or expired → 404. The
  page frames it with `sandbox="allow-scripts"` (never `allow-same-origin`).
  `business_cards_tools.chart_files` kinds: `image` (PNG), `html`, `text`; the legend rides on
  the first `image` or `html` entry. Telegram sends an `.html` chart with `sendDocument`
  (`text/html`, caption `HTML_CHART_CAPTION`).
- COM (`integrations.com.apartment()`, 2026-10-20 re-test): `OutlookComMailbox`, `OutlookComDraft`
  and `OutlookComDraftSender` take `connect` (how to get Outlook on the calling thread; default
  `Dispatch`) beside `dispatch`, initialise COM around each call and map every COM failure to
  their codes (`mail_failed`, `draft_failed`, `send_failed`).
- Skill `engineering/business-cards@1.0.0` (alias `cards`, no commands), in
  `host_runtime.assets.shipped()`.
- Agent Web: a Gateway answer that drew a chart carries `files` and stores them on the assistant
  message's `attachments` [{`filename`, `kind` (`image` | `text`), `path`}];
  `GET /api/conversations/file?session_id=&path=` (page token) serves only a file listed on that
  conversation's answers and inside the workspace (`image/png`, `text/markdown`), else 404.
- Telegram: `TelegramDelivery.photos` and `documents` (paths); after the text reply each photo is
  sent with `sendPhoto` (multipart `chat_id`, `caption` = the chart note, `photo`), then each
  document with `sendDocument` (`chat_id`, `document`). The text carries the legend without its
  table (`business_cards_tools.with_legend(short=True)`).
- CLI: `aep-host cards import --config <host.json> [--from <cards.db>] [--actor <name>]`.

### Memory spaces and the Memory Service (accumulated memory M1, 2026-10-20)

`docs/phases/ACCUMULATED_MEMORY.md` §11; decision `docs/DECISIONS.md` 2026-10-20 "Accumulated
memory M1". Contracts in `common.memory`; service in `memory.service`, `memory.merge`,
`memory.registry`; Host registry in `host_runtime.memory_spaces`.

- **Manifest section** (`SkillManifest.memory_spaces`, `WorkflowManifest.memory_spaces`;
  optional, at most 16, omitted from the serialized manifest when empty so older bytes and
  digests are unchanged): `MemorySpaceDeclaration` {`space` (`<domain>/<name>`, lower case, 2–3
  segments, e.g. `contacts/org`), `role` (`manager` | `contributor` | `reader`; each includes the
  next), `kinds` [`entities` | `sync_state` | `preferences` | `facts` | `notes`], `sensitivity`
  (`PUBLIC` | `INTERNAL` | `CONFIDENTIAL` | `RESTRICTED`), `retention` (`until_deleted` |
  `P<n>D` | `P<n>M` | `P<n>Y`), `schema_ref`, `merge_rules` (versioned refs `a.b.c.v1`)}. A
  manager declares all of kinds, sensitivity, retention, schema_ref and merge_rules; a
  contributor or reader declares none of the last four. One declaration per space per manifest.
  A space has one manager: a second asset declaring itself manager is refused by Shared
  Platform sync (`asset_conflict`), by switching it on in Agent Web
  (`memory_space_has_a_manager`), and left out of the Host's registry.
- **Merge rules** (data the manager ships; stored as JSON in the space's registry row):
  `MergeRules` {`rules_id`, `trust` {source kind → `user_stated` | `document` |
  `system_record` | `inferred`} (must map `user` to `user_stated`; any other kind is refused),
  `default` / `fields` {field → `FieldMergeRule` {`policy` (`newest_evidence` | `precedence`),
  `precedence` (trust classes, highest first), `lower_conflict` (`propose` | `keep`),
  `user_conflict` (`propose` | `propose_if_newer` | `take_if_newer`: only new evidence counts
  against the person's value; it proposes, or is taken unless uncertain)}}, `undated` (source
  kinds without an evidence date, e.g. `card`: new only when `novel`, an identity never observed
  for the entity), `external_ids` (systems kept for
  matching only), `relations` [{`relation`, `solid_evidence` [source kinds]}], `auto_merge`
  {`identities` (e.g. `email`), `mapped_external_ids`}}. `memory.merge.decide` returns
  `Decision` {`action` (`take` | `keep` | `propose`), `reason` (`empty` | `same` | `user_set` |
  `lower_trust` | `uncertain` | `older_evidence` | `match_only` | `seen_evidence` |
  `new_evidence`)}; `decide(..., novel=)`; `resolve` folds observations
  into current values and conflicts; `auto_merge` returns {`entity_id`, `by`, `ask`,
  `candidates`}.
- **Storage**: `<workspace>/memory/<actor-key>/memory.sqlite` per actor (`memory_path`).
  `meta`, `spaces` {`space`, `manager` (`namespace/name`), `table_prefix`, `declaration_json`,
  `rules_json`}; shared tables, each row with `space`: `observations` {`observation_id`,
  `entity_id`, `claim` (`fields` | `status` | `relation`), `source_kind`, `trust`,
  `source_date`, `source_ref`, `fields_json`, `uncertain_json`, `recorded_at`, `recorded_by`,
  `contributor`, `change_id`, `retracted_by`} (append-only: triggers refuse DELETE and any UPDATE
  but setting `retracted_by` once), `field_sources` {`entity_id`, `field`, `source_kind`,
  `source_date`, `observation_id`, `origin` (`human` | `tool` | `import` | `agent` |
  `migration`), `set_by`, `set_at`, `reason`} (ADR-K11), `history` {`history_id`, `change_id`,
  `at`, `actor`, `entity_id`, `kind`, `field`, `old`, `new`, `reason`, `source`, `extra_json`},
  `undone` {`change_id`, `undone_by`}, `proposals` {`proposal_id`, `entity_id`, `field`,
  `current`, `proposed`, `source_kind`, `observation_id`, `created_at`, `state` (`open` |
  `accepted` | `rejected` | `dismissed`), `decided_at`, `decided_by`}, `external_ids`
  {`system`, `external_id`, `entity_id`, `created_at`, `created_by`}. A manager's own tables are
  named `<space with _>__<name>` (`contacts_org__people`).
- **API** (`memory.service`): `MemoryService(path, registry)` / `.for_actor(workspace, actor,
  registry)` registers every managed space the registry has rules for;
  `register_space(declaration, manager=, rules=)`; `spaces()`; `space(space, asset=)` →
  `MemorySpace` (refusals: `memory_space_not_declared`, `memory_space_unknown`).
  `MemorySpace.transaction()` → `SpaceTx`; one-shot helpers `add_observation`, `observations`,
  `resolve`, `history`, `proposals`, `undo`, `map_external_id`, `entity_for_external_id`.
  `SpaceTx` (role-checked: read = reader, write = contributor, own tables and provenance =
  manager; `memory_read_not_declared`, `memory_write_not_declared`, `memory_manager_only`):
  `add_observation(entity_id, fields, source_kind=, source_date=, recorded_by=, source_ref=,
  uncertain=, change_id=, claim=)` (`memory_source_unknown`), `observations(...)`,
  `retract`, `provenance` / `field_provenance`, `set_provenance`, `drop_provenance`,
  `provenance_extra` / `restore_provenance` (for undo), `decide`, `resolve`, `solid(relation,
  evidence_kind)`, `record`, `history`, `changed_since`, `undo(change_id, actor=, handlers=)`
  (`change_unknown`, `change_already_undone`; `proposal` rows dismissed generically, the
  person's statements in the change retracted), `propose`, `proposals`, `set_proposal_state`,
  `reopen`, `forget_entity`, `map_external_id` (`external_id_taken`), `entity_for_external_id`,
  `external_ids`, `auto_merge`, `table(name)`, `con` (manager only). `recorded_by` / `actor` /
  `set_by` are always the Host's `<actor> via <channel>`.
- **Sync state** (accumulated memory M2, `ACCUMULATED_MEMORY.md` §12): for a space whose manager
  declares the `sync_state` kind (otherwise `memory_kind_not_declared`). Tables `sync_state`
  {`space`, `source` (e.g. `mail:Inbox`), `key` (e.g. `wnc.com.tw`), `last_message_date` (ISO
  UTC), `last_message_ids_json` (at most `MAX_SYNC_IDS` = 500, newest first), `extractor_version`,
  `updated_at`, `updated_by`} keyed by (`space`, `source`, `key`), and `sync_history`
  {`history_id`, `space`, `source`, `key`, `action` (`advance` | `reset` | `restore`), `at`,
  `actor`, `reason`, `old_json`, `new_json`}. Contracts `common.memory.SyncState`,
  `SyncHistoryEntry`. `SpaceTx` (and one-shot `MemorySpace`) methods: `sync_state(source, key)`,
  `sync_states(source=)` (reader); `advance_sync(source, key, last_message_date=, message_ids=,
  extractor_version=, actor=, reason=)` (contributor; only forward, `sync_state_backwards`;
  another extractor version needs a reset first, `sync_extractor_changed`; `sync_date_invalid`;
  ids join the earlier ones on the same or a later date); `reset_sync(source, key, actor=,
  reason=)` (the row goes, its old value is kept in history); `restore_sync(history_id, actor=)`
  (puts back the state one history row replaced; `sync_history_unknown`); `sync_history(source=,
  key=, limit=)`. Per actor like every table (one file per actor).
- **`contacts/org`** (`capabilities.business_cards.space`): manager
  `engineering/business-cards`, kinds `entities` and `sync_state` (M2), `CONFIDENTIAL`, `until_deleted`,
  `contacts.org.person.v1`, `contacts.org.merge.v2` (company by precedence, card over C4C;
  title / department / division / business group by newest evidence; owner 2026-10-20: the
  person's value is touched only by new evidence (`undated` `card` and `import` by image
  novelty, signatures by sent date after the day of the change), which updates title,
  department, division, business group, honorific, phone, ext, mobile, fax and address
  (`take_if_newer`) and proposes for the email, the company and the rest (`propose_if_newer`);
  a one-time cleanup dismisses old-evidence proposals, history kind `proposal_rule`, undone as
  `proposal_reopen`; `c4c_account` / `c4c_contact` match only; reporting lines
  solid only on `user`, `signature` or `email_content`; auto-merge on an identical email or a
  mapped external id).
- **Migration** (`capabilities.business_cards.migration`): on the first open, verified byte
  copy `cards.db.bak-<UTC stamp>` beside `cards.db`, then one transaction copying every row with
  its id, read back and compared, then the marker `migrated:contacts/org` in `meta`. Refusals:
  `memory_backup_failed`, `memory_migration_failed`, `memory_migration_mismatch`,
  `memory_migration_target_not_empty`, `memory_legacy_changed` (the old store changed after the
  migration).
- **Preferences and notes** (accumulated memory M3, `ACCUMULATED_MEMORY.md` §14; decision
  2026-10-21). Two spaces the Host manages (`memory.personal`, manager asset `host/memory`,
  declared before any manifest via `MemoryRegistry.from_manifests(first=)`; no installed asset can
  manage them): `personal/preferences` (kind `preferences`, `personal.preference.v1`,
  `personal.preferences.v1`) and `personal/notes` (kind `notes`, `personal.note.v1`,
  `personal.notes.v1`), both `CONFIDENTIAL`, `until_deleted`, per actor. A Skill or Workflow
  reads notes by declaring `{"space": "personal/notes", "role": "reader"}` (`memory.personal.
  NOTES_READ`; the business-cards Skill does) and calling `memory.notes.for_reader(service,
  asset, refs)` (`memory_read_not_declared`). Preferences are read by the Host only.
  - `memory.preferences.Preferences(service)`: table `personal_preferences__items`
    {`preference_id` (`p-<10 hex>`), `scope` (`skill:<ns>/<name>` | `space:<space>`,
    `preference_scope_invalid`), `scope_label`, `text` (normalised, ≤ 300), `subject`,
    `polarity` (`positive` | `negative`), `status` (`active` | `removed` | `replaced`),
    `created_by`, `created_at`, `updated_at`, `source_session`, `source_message`, `proposed_by`,
    `replaced_by`}. `check(scope, text, given_subject)` → `Check` {`duplicates`, `conflicts`}
    (same scope, same subject: equal or `difflib` ratio ≥ 0.8 of `subject(text)`, or equal
    normalised given subjects; same polarity = duplicate, opposite = conflict).
    `save(scope, text, actor=, scope_label=, given_subject=, source_session=, source_message=,
    proposed_by=, replace=, keep_conflicts=)` → (`Preference`, change id); an open conflict
    raises `PreferenceConflict` (`preference_conflict`, `.conflicts`); `replace` marks those
    `replaced` in the same change. `remove`, `listed(scope=, include_inactive=)`,
    `active(scopes)`, `get`, `history`, `undo(change_id, actor=)` (history kinds
    `preference_add` / `preference_replace` / `preference_remove`; `undo_conflict` when a later
    change touched the same row, via `SpaceTx.changed_after`).
  - `memory.notes.Notes(service)`: table `personal_notes__items` {`note_id` (`n-<10 hex>`),
    `text` (Markdown, ≤ 20,000), `tags_json` (≤ 8), `entities_json` (≤ 12 refs
    `<space>:<kind>:<id>`, `note_entity_invalid`), `source_kind` (`answer` | `selection` |
    `agent_proposal`), `source_session`, `source_message`, `excerpt_json` ({`start`, `end`} in
    the stored answer), `status` (`active` | `deleted`), `created_by`, `created_at`,
    `updated_by`, `updated_at`}. `save`, `update(note_id, text=, tags=, entities=)`, `delete`,
    `undo` (kinds `note_add` / `note_update` / `note_delete`), `get`, `listed`,
    `from_source(session, message, text)`, `search(text=, tag=, entity=, since=, until=,
    limit≤20)` (Asia/Taipei days, `note_date_invalid`), `linked(refs)`. `notes_asked(message)`:
    the deterministic trigger `NOTES_ASKED`.
  - Conversation (`host_runtime.personal_memory`): `Gateway.turn_memory`
    (`TurnMemoryProvider`: request, the Skills whose tools the pass offers → `TurnMemory`
    {`guidance`, `preferences_used`, `tools`}); the result's `preferences_used` (≤ 40 ids) is on
    `GatewayConversationResult` and the stored answer (`ConversationMessage.preferences_used`).
    Model tools: `memory__propose_preference` {`rule`, `skill`, `subject`?} and
    `memory__propose_note` {`text`, `tags`?, `entities`?} (only with a session; the note tool at
    most once per conversation, a Telegram chat per day: `note_already_proposed`), and
    `notes__search` {`query`, `tag`, `entity`, `since`, `until`, `limit`} → {`notes` [note +
    `cite` `[筆記 <note_id>]`], `count`, `note`}, offered only when a Skill in use declares a
    notes read or `notes_asked` matches. No tool saves. The proposals never back a lasting-change
    claim (`conversation_harness.PROPOSAL_ONLY_TOOLS`).
  - Cards: `MemoryCard` records (`mm-` ids, 24 h, `<workspace>/memory/memory-cards.json`) drawn
    as `ActionCard` kind `memory_preference` | `memory_note` with `ends_turn` false (new
    `ActionCard` field, default true: the Gateway ends a turn only on a card that ends it).
    Buttons `save` / `decline`; a conflict at save turns the card into `replace` / `keep_both`
    / `decline` with a row per conflicting preference (before = it, after = the new one).
    Statuses `pending` → `saved` | `declined` | `duplicate` | `expired` | `failed`.
  - Agent Web routes: `POST /api/memory/notes/save` {`session_id`, `message_id`,
    `selection`?} → {`ok`, `already`, `note`, `change_id`, `message`} (`conversation_unknown`,
    `message_unknown`, `selection_not_in_answer`); `GET /api/memory/notes`,
    `GET /api/memory/preferences`; `POST /api/memory/delete` {`kind`: `note` | `preference`,
    `id`}; `POST /api/memory/undo` {`kind`, `change_id`}. All answer 200 with `ok`/`code`.
  - Org chart HTML: each person in the page data has `notes` [{`id`, `text` (≤ 140), `date`}]
    from notes linked to `contacts/org:person:<person_id>` (newest 5), shown as 「相關筆記」.
- **Memory page** (accumulated memory M4, `ACCUMULATED_MEMORY.md` §15; decision 2026-10-21).
  `host_runtime.memory_page.MemoryPage` (`AgentWeb.memory_page`): Agent Web routes behind the page
  token, for `web.runtime.actor` only (another actor's ids name nothing); every change is recorded
  as `<actor> via web`; no model tool reaches them. All answer 200 with `ok` and, on refusal,
  `code` and a Chinese `message`.
  - `GET /api/memory/overview` → {`ok`, `actor`, `proposals` [{`space`, `space_label`,
    `proposal_id`, `entity_id`, `entity_label`, `field`, `field_label`, `current`, `proposed`,
    `source`, `source_label`, `evidence_date`, `evidence_ref`, `created_at`, `created_at_local`,
    `actions` (`keep`, `accept`), `person_id`}], `preferences` [{`scope`, `label`, `items`
    [preference + `created_at_local`, `updated_at_local`, `used_count`, `used` (≤ 5
    {`session_id`, `message_id`, `title`, `at`, `at_local`})]}], `notes` {`notes` [note +
    `created_at_local`, `updated_at_local`], `tags`, `entities` {ref: label}}, `spaces`
    [{`space`, `label`, `manager`, `manager_label`, `manager_state` (`on` | `off` | `host` |
    `missing`), `orphan`, `kinds`, `kind_labels`, `sensitivity`, `sensitivity_label`,
    `retention`, `retention_label`, `counts` [{`name`, `label`, `count`}], `observations`,
    `open_proposals`, `sync_states`, `last_updated`, `last_updated_local`, `view` (`people` |
    ``)}], `sync` [{`space`, `space_label`, `source`, `key`, `state` ({`last_message_date`,
    `last_message_date_local`, `extractor_version`, `updated_at`, `updated_at_local`,
    `updated_by`} | null), `latest` ({`history_id`, `action`, `at_local`, `actor`} | null),
    `can_reset`, `can_restore`}], `records` {`conversations` {`count`, `max_messages`,
    `retention_label`}, `runs` {`days`, `max_mb`}, `experience` {`retention_days`}},
    `deletions` [{`deletion_id`, `space`, `label`, `at`, `at_local`, `actor`, `reason`,
    `counts`}]}. With `?only=<section>[,<section>…]` (`proposals`, `preferences`, `notes`,
    `spaces`, `sync`, `records`, `deletions`, `health`) only those sections are answered, beside
    `ok` and `actor` (B3: the page reloads what an action changed); unknown names are ignored,
    none known means all.
  - `GET /api/memory/people?q=&status=any|active|left` → {`people` [{`person_id`, `name`,
    `romanised_name`, `company`, `department`, `title`, `email`, `status`, `status_label`,
    `open_proposals`, `updated_at_local`}] (≤ 200), `total`}; `GET /api/memory/person?person_id=`
    → the business-cards `HistoryResult` (`person_unknown`).
  - `GET /api/memory/export?space=` → {`filename`, `data` {`format`
    `aep-memory-space-export/1`, `space`, `manager`, `exported_at`, `declaration`, `rules`,
    `tables` {own table suffix: rows}, `shared` {shared table: the space's rows}}}
    (`memory_space_unknown`); `GET /api/memory/notes/export?ids=a,b` (all active notes when
    none) → {`count`, `filename` `notes-<YYYYMMDD-HHMM>.md`, `markdown`}.
  - `POST /api/memory/proposals/decide` {`space`, `proposal_id`, `action` `keep` | `accept`} →
    {`change_id`, `undo`, `message`}. `contacts/org` fields go through `CardStore.edit`
    (`keep` = `confirm=[field]`, `accept` = the proposal's value as the person's); other spaces
    take `keep` only (state `rejected`, history kind `proposal_rejected`;
    `proposal_accept_unsupported`). `proposal_unknown`, `proposal_closed`,
    `proposal_action_unknown`. `POST /api/memory/proposals/undo` {`space` `contacts/org`,
    `change_id`} (`CardStore.undo`).
  - `POST /api/memory/preferences/edit` {`id`, `text`, `resolve`? `replace` | `keep_both`,
    `replace`? [ids]} → {`preference`, `change_id`} via `Preferences.edit(preference_id, text,
    actor=, replace=, keep_conflicts=)` (same id; history kind `preference_edit`, undone back to
    the old words; `preference_duplicate`, `preference_unchanged`, `preference_unknown`,
    `preference_conflict` with `conflicts` [{`preference_id`, `text`}]).
  - `POST /api/memory/notes/edit` {`id`, `text`?, `tags`? [..], `entities`? [refs]} → {`change_id`}
    (`Notes.update`; `note_unknown`, `note_entity_invalid`, `note_tags_invalid`). Delete and undo
    use M3's `/api/memory/delete` and `/api/memory/undo`.
  - `POST /api/memory/sync/reset` {`space`, `source`, `key`} (`sync_unknown`,
    `memory_kind_not_declared`); `POST /api/memory/sync/restore` {`space`, `source`, `key`}
    restores the latest history row when it is a reset (`sync_history_unknown`,
    `sync_nothing_to_restore`).
  - `POST /api/memory/space/delete` {`space`, `confirm` (= `space`)} → {`counts`, `message`}
    (`space_delete_unconfirmed`, `memory_space_unknown`).
  - `memory.service.MemoryService` (the person's own management, Host routes only): `owned(space)`
    (the space with the manager's reach), `overview()`, `open_proposals(limit=)`,
    `proposal(space, id)`, `sync_overview()`, `export_space(space)`, `delete_space(space, actor=,
    reason=)` → counts per table (one transaction: the space's own tables emptied and its rows
    removed from `SHARED_TABLES`, observations included with the append-only trigger dropped and
    re-created inside the transaction; the space stays registered; not undoable),
    `deletions(limit=)`. Table `space_deletions` {`deletion_id`, `space`, `at`, `actor`,
    `reason`, `counts_json`}: never content.
  - `host_runtime.memory_spaces.manager_states(layout)` → {`<ns>/<name>`: `on` | `off`} of
    installed managers; a space whose manager is neither (nor `host/memory`) is an orphan.
- **Memory quality** (accumulated memory M5, `ACCUMULATED_MEMORY.md` §16; decision 2026-10-21).
  - `common.memory.FreshnessRule` {`kind` `entities` | `sync_state`, `after` (`P<n>M` | `P<n>D`),
    `entity`?, `question` (with `{name}`, required for `entities`), `status` [..]};
    `MergeRules.freshness` (≤ 8, default none). `contacts/org`: `entities` person `P12M`
    「{name} 是否仍在職？」 status `active`; `sync_state` `P30D`. Rules id unchanged.
  - `memory.health.run_check(service, *, preferences, last_used (None = unknown), entities
    {space: EntitySource}, manager_state(manager) → host|on|off|missing, ask (scope, rules) →
    [(id, id, why)] | None, now?, settings?)` → `HealthReport` {`check_id`, `at`, `enabled`, `found`
    {kind: n}, `opened`, `still_open`, `gone`, `model` `used` | `not_needed` | `unavailable` |
    `failed` | `off`, `model_calls`, `skipped`}. Reads only; writes `health_findings` and
    `meta.health_last_run` (counts). Kinds `duplicate`, `stale`, `contradiction`, `unused`,
    `orphan`, `stale_sync`. Table `health_findings` {`finding_id` `h-…`, `space`, `kind`, `key`,
    `subject_json`, `state` `open` | `dismissed` | `resolved` | `gone`, `check_id`, `created_at`,
    `updated_at`, `decided_at`, `decided_by`, `action`; unique (`space`, `kind`, `key`)}, one of
    `SHARED_TABLES`. Bounds: `MAX_SCOPES = 5`, `MAX_RULES_PER_SCOPE = 12`; asked only for a scope
    with ≥ 2 active preferences; pairs the M3 check finds are dropped.
  - Settings `meta.health_settings` {`enabled` (bool, default true), `freshness_months` (0–120,
    0 = the rule's), `unused_days` (1–3650, default 90)}; `save_settings` changes only the keys
    sent and keeps unknown ones (`health_settings_invalid`). `meta.actor` names the database's
    actor (written by `MemoryService.for_actor`); `MemoryService.set_meta(key, value)`.
  - Contacts: `CardStore.last_seen(statuses)`, `duplicates()` (`same_email` |
    `same_name_company`, older first), `confirm_active(ref, actor=, reason=)` (a `user` `status`
    observation, history `still_active`), `merge_people(keep, drop, actor=, reason=)` → change id
    (fills `keep`'s empty fields, moves lines, dismisses `drop`'s proposals, deletes `drop`'s row;
    history `merged_away` keeps the row; `CardStore.undo` restores it; `merge_same_person`,
    `person_unknown`). Preferences: `mark_used(ids, at=)`, `last_used()` (table
    `personal_preferences__uses`: id, last time, count).
  - `host_runtime.memory_health.MemoryHealth` (`AgentWeb.memory_health`): `run(actor, now=)`,
    `run_all(now=)` → `HealthSummary` {`at`, `actors`, `checked`, `switched_off`, `failed`, `found`,
    `opened`, `open`, `gone`, `model_calls`, `model` {use: actors}}; the contradiction question is
    `structured_call` on `review_model(runtime)` with `output_contract`
    `memory_health_contradictions`, `max_output_tokens` 500, reply {`pairs` [{`a`, `b`, `why`}]} (≤ 5).
    Telemetry: run kind `memory_health`, event `memory.health_checked` with counts only.
  - Routes (page token, signed-in actor): `POST /api/memory/health/run` → {`counts`, `message`}
    (`health_off`); `POST /api/memory/health/decide` {`finding_id`, `action`} → {`message`,
    `undo`? {`kind` `contacts` | `preference`, `change_id`, `finding_id`}} (`finding_unknown`, `finding_closed`,
    `finding_action_unknown`; actions: duplicate `merge` | `dismiss`; stale `still_active` |
    `left`; contradiction `remove_a` | `remove_b` | `keep_both`; unused `remove` | `keep`; orphan
    `keep`; stale_sync `dismiss`); `POST /api/memory/health/undo` (that `undo` object) → {`reverted`,
    `reopened`, `message`}: the store's undo of the change, then a `resolved` finding is `open`
    again at once (#233; `finding_unknown`, `change_unknown`, `undo_conflict`);
    `POST /api/memory/health/settings` {`enabled`?,
    `freshness_months`?, `unused_days`?} → {`settings`}. The overview adds `health` {`settings`,
    `rule_periods`, `last_run`, `findings` [{`finding_id`, `kind`, `kind_label`, `space`, `title`,
    `pairs` [[label, value]], `links` [{`label`, `person_id` | `tab`+`id`}], `actions` [{`action`,
    `label`, `style`}], `created_at_local`}], `kind_labels`}.
  - Nightly: `AgentWeb.nightly_tick(now=)` after 02:00 local, once a night (experience meta
    `last_memory_health`): the health check of every actor, then the experience review as before.
    `ReviewReport.memory_health` (`HealthSummary`, counts only) in `review-*.json` / `.md`
    (`## Memory health`); a night without a review writes `memory_health_report` alone.
  - 「為什麼」: `ConversationMessage.memory_used` (answers only, ≤ 40 refs
    `<space>:<kind>:<id>`: `contacts/org:person:<id>`, `contacts/org:sync:<domain>`,
    `personal/notes:note:<id>`); the Agent Web reply JSON has `memory_used`.
    `host_runtime.memory_why.memory_used_in(tools, answer)`; `GET /api/memory/why?session_id=&
    message_id=` → {`items` [{`kind` `preference` | `person` | `sync` | `note`, `id`, `label`,
    `detail`, `gone`, `tab`}]} (`message_unknown`). Telegram `/why` → the chat's last answer
    (`MemoryWhy.text`), or 「上一則回答沒有用到你的偏好或記憶。」.

## Shared-platform transport (Phase 7, slice 2i)

`common.sync` is the wire between a Bridge and the shared platform: seven
operations (`probe`, `catalog`, `advertise`, `sync`, `report`, `poll`, `settle`), each a
closed request and reply. `ProbeReply` is the `AuthenticatedActor` the token
produced, which must name a device, plus the platform's clock. `CatalogRequest`
has optional namespace and asset-kind filters; `CatalogReply` contains unique
`PublishedAssetPackage` metadata only. The platform reads groups from its own
membership record and applies `entitled`, so a request cannot widen discovery.
Catalog discovery carries no artifact bytes and creates no selection,
installation plan or execution permission. `SyncRequest`
lists what the Bridge has installed; `SyncReply` carries the device's
`DeviceAuthorization`, an `InstallationPlan` for what the Bridge lacks and an
`ArtifactPayload` (base64 in both directions) for exactly each planned
package: a plan without its bytes and bytes without a plan are both refused.
`SettleRequest` names one of `ran`, `rejected`, `cancelled` and carries a
`LocalRunSummary` exactly when it ran. `WireFailure` is a code and whether to
try again; nothing a Bridge sent is ever echoed. `WITHDRAWN` names the three
codes that mean revoked (`token_revoked`, `token_expired`, `binding_withdrawn`),
told only to a Bridge that proved its secret.

`RemoteJobRecord` gains the final states `ran`, `rejected`, `cancelled` and a
`run` present exactly when it ran, naming the job's actor, `on_behalf_of` and
workflow; `open` is whether the Bridge has yet to settle it.
`RemoteWorkflowJob` gains `on_behalf_of` with the meaning it has everywhere
since slice 2j, and `LocalAgent.execute` records it; its `job_id` is held to
the shape of an `IdempotencyKey`, because that is what the Bridge runs it under. `InMemoryRemoteControl`
gains `job(job_id)` and `settle(bridge_id, job_id, disposition=, run=)`, which
only the job's own device may call, once (`job_bridge_mismatch`, `job_settled`,
`job_run_mismatch`); `poll` no longer offers a settled job and `cancel` refuses
one. `InMemoryEnrollmentRegistry.advertise(bridge_id, registration)` replaces
what a device says it can run, under the same identity rule as enrolling.

`control_plane.service.ControlPlaneService` is the platform's side,
transport-agnostic and locked for concurrent callers. Every operation takes a
token id and secret, decides who is asking through
`InMemoryAccessTokens.authenticate`, and acts only on the device the token was
issued for; a payload naming another device is `device_mismatch`. A report
is received no earlier than it was observed: a Bridge clock up to
`CLOCK_SKEW` (five minutes) ahead of the platform's is still reporting now,
and one further ahead is `invalid_request`. `handle`
dispatches by operation name for a transport and answers `unknown_operation`
and `invalid_request` for anything that is not one. `synchronize` plans each wanted
asset once however many selections name it, so a decision left behind by a
member since unbound never breaks the device's sync. The body is validated in
`handle` and only there: a contract the service fails to build while
answering is the platform's own inconsistency and reaches the Bridge as
`internal_error` (retryable), never as `invalid_request`. `STATUS_FOR` is the
HTTP status each code deserves. `control_plane.http.ControlPlaneServer` is
that service on a standard-library `ThreadingHTTPServer`: `POST
/v1/<operation>` with `Authorization: Bearer <token_id>:<secret>`, a 4 MiB
body limit refused before reading, a chunked body refused, one request per
connection (`Connection: close`, so a refused body is never parsed as the next
request; a refusal sent *before* the body was read then swallows what the
client already sent, briefly and boundedly, because a socket closed with
unread data is reset rather than finished and a reset discards the refusal
itself), an unauthenticated `GET /v1/health`, no request logging, no software
name, and an optional `ssl.SSLContext` that wraps the socket. Its package and
artifact dependencies may be the in-memory reference or the durable Registry
defined above; transport behavior is identical.

`host_runtime.contracts.PlatformBinding` is how a host names its platform:
`base_url` (an origin: https, or http on loopback only, with no path, query,
fragment or credential), optional `member_portal_url` navigation metadata,
`token_id`, the `SecretRef` of the token's secret and a timeout; `CompanyHostConfiguration.platform` is
optional and a host without it works locally. `HostLayout` moved to the
contracts module and is still importable from `host_runtime.host`.

`host_runtime.sync.PlatformClient` is the Bridge's side. `_call` resolves the
secret per call through the resolver and classifies every reply into a
`Reachability`: `answered`; `unreachable` (a transport fault, a 5xx, a reply
that is not a `WireFailure` — an intermediary's bare 401 included), always
retryable; `withdrawn`; `rejected` (`authentication_failed`: this host's
configuration is wrong); `refused` (anything else declined). Only `answered`
changes anything on the Bridge. `probe`, `catalog`, `advertise` and `report` change
nothing locally; the credential is resolved per call through
`models.wire.authorized`, under the rule every HTTP adapter shares. `synchronize(layout, state)`
applies a reply in this order: `verify_installation` over the whole plan against the SQLite
inventory; each artifact parsed as the manifest its kind names and carrying
the identity its package claims (`sync_asset_invalid`); each file it would
write compared with any hand-placed asset of the same identity, a conflict
unless the bytes are identical (`sync_asset_conflict`); then the manifests
written atomically as `<namespace>__<name>__<version>.json`, the inventory
recorded in one transaction, and `authorization.json` replaced atomically.
When `grants.json` exists the sync is assets-only (owner decision (a),
2026-10-15): everything above happens except that the bundle is written to
`platform-selections.json` (`HostLayout.platform_selections`, display only,
never loaded as an authorization) instead of `authorization.json`, and
`SyncOutcome.assets_only` is true. The host therefore never holds two answers
about what may run. (Before 2026-10-15 this case was refused as
`sync_grants_conflict`.) A
refusal before the first write leaves the workspace untouched; when the
bundle, the one write after the inventory is recorded, fails, the outcome is
`refused` with `installed` naming what was recorded (`SyncRefused.installed`).
`poll_jobs(agent)` runs each open job through `LocalAgent.execute` and settles
it — `ran` with the run (built from the engine's result when the local record
failed; a run that outlives the wait is waited for until it ends first),
`rejected` for a refusal or a pre-flight rejection, `cancelled` for a job the
platform had asked to stop unless `WorkflowEngine.submitted` says this Bridge
already ran it, in which case `ran` — then reports the snapshot after a batch
that did something and otherwise once a minute (`REPORT_EVERY_SECONDS`), read
off the event loop. A settle the platform declined for one job is recorded on
the delivery and the batch goes on; a settle answered `withdrawn` or
`rejected` stops the rest of the batch. A settle that could not be delivered
leaves the job open at the platform, and the idempotency key keeps it from
running twice. `run_jobs(agent, stop, interval_s=)` loops with the Telegram
ingress's rule: a poll answered `withdrawn`, `rejected` or `refused`, or a
settle answered `withdrawn` or `rejected`, ends it and is returned;
`unreachable` is waited out with a doubling delay up to five minutes. The
client takes `workflow_timeout_seconds` for how long a polled job is waited on
before the Agent reports it still running. `advertisement(agent, trace_id)`
is the `BridgeRegistration` a host sends: the capabilities its policy could
ever dispatch.

`workflow.engine.WorkflowEngine.submitted(actor, namespace, idempotency_key)`
is the run an idempotency key already names, or None: what a caller asks
before saying a job it may have started never ran.

`aep-host` gains `probe`, `sync` (which then advertises and reports, best
effort) and `jobs [--once] [--interval]`; `doctor` gains a `platform` check
read from the configuration alone (`pending` without a platform, `failed`
when the secret's name is unmapped, `passed` otherwise). Every unreachable
answer is printed as exactly that, never as a revocation.

## Workflow 11: the weekly report up to its plan (Phase 7, slice 3a)

*As built today (note 2026-10-16):* the weekly report no longer reads Jira. Its live
source is a GitHub Projects board (`github/search-project`); see "Workflow 11's second
source: the GitHub Projects client (Phase 7, slice 5)" below. This section records the
slice 3a contracts as they were first built.

`capabilities.weekly_report.rules` is the pinned Host Bridge's
`_weekly_rules` ported pure: `parse_week_name`, `week_number`/`week_name` in
the `iso`, `us` and `iso-1` styles, `week_range`, `week_range_for_name`,
`jql_updated_clause` (exclusive upper bound), `compose_jql` (the `ORDER BY`
stays last), `column_letter`, `column_for_header` (case-insensitive, `Sales`
and `Salse` alike), `latest_weekly_sheet` (by `(year, week)`, strictly
`before` the week reported), `adf_to_text`/`comment_body_text`,
`extract_marker_blocks` with `DEFAULT_MARKER_SYNONYMS` and
`build_marker_pattern` (a header is a short line, not prose),
`merge_marker_blocks` (per day, canonical order, newest day first),
`select_comments_in_window`/`extract_week_blocks` (inclusive, in the
timestamp's own offset, undated comments kept), `format_comment_block` (one
`M/D:` header per comment date, newest first), `should_prepend` (the dedupe
guard) and `issue_to_row` (never the `Comments` column). The source's own
tests are the port's oracle.

`capabilities.weekly_report.contracts`: `WeeklyReportSettings` is the host's
non-secret configuration with the source's defaults (workbook, scratch sheet,
week style and suffix, project and statuses or a base `jql`, page size and
cap, marker synonyms, bullet, look-back, the five colours and the border);
`WeeklyReportRequest` is what a run asks for, as fields or as the words after
a command (`2026_31W since=… until=… max=N`; a field given directly wins, a
word naming a field twice is refused), and refuses a week that is not a
sheet name where the source fell back to today's; `resolve_window` refuses a
window that ends before it starts and a week the calendar has not got; `ReportingWindow` is the
week resolved (window, comment window, stamp date, composed JQL, cap);
`JiraIssue`/`JiraComment` are an issue reduced to the report's fields with
its comments flattened to text; `SheetState` is the scratch sheet as it
stands (or the seed sheet when absent) with `Key -> Comments`, the seed and a
`digest` of the scratch sheet's rows; `WeeklyReportPlan` is every row and
cell operation decided before anything is touched — `rows`, `new_keys`,
`updated_keys`, `comment_operations` (text, markers, line count), `remarks`
(blocks already present that only need their colour back), `skipped` with
reasons, `highlight_keys`, the sorted `issue_keys`, `capped` (the search
stopped at the cap, which the preview says in capitals), `sheet_digest` and
the rendered `preview` — with its consistency enforced by the contract.
`week_suffix` is `W` or empty, the two spellings the parser reads; a marker
vocabulary names at least one marker.

`capabilities.weekly_report.plan.resolve_window` and `build_plan` are the
source's window resolution and `build_plan`: a ticket the sheet has never
seen earns a row only with marker content this week, a row already there is
always refreshed, and the tint names exactly the rows that gained content,
already hold this week's content, or arrived this week.

`integrations.jira.JiraConnection` (https site root, `cloud` with an email or
`server`, the token a `SecretRef`, timeout, retries, page size) and
`JiraClient(connection, resolver, transport=, sleep=)`: Basic `email:token`
or Bearer built per call and held nowhere; `request` with bounded retries on
429/5xx honouring `Retry-After` up to sixty seconds and no body ever echoed; `search_issues`/
`iter_issues` token-paged on Cloud with a remembered fall-back to offset
paging when a site answers the probe 404 or 410 (an empty body is
`jira_bad_reply`, never a fall-back), offset-paged on Server, under the
cap and reading every page while the site's `total` says more remain;
`comments` page by page; `myself`; `browse_url`. Every failure is a
`JiraError` with `jira_credential`, `jira_auth`, `jira_http`,
`jira_unavailable` or `jira_bad_reply`. `models.wire.MethodTransport` is the
transport it takes (`request(method, url, body, headers, timeout)`), which
`UrllibTransport` now implements beside `send`.

`integrations.excel` reads a workbook's bytes with `openpyxl` (`office`
extra), never Excel and never a write: `sheet_names`, `read_rows` (row 1 the
headers, every cell as text), `read_chosen_sheet` (the names and one sheet's
rows from a single open), `require_library`; failures are
`WorkbookError` codes (`library_missing`, `workbook_missing`,
`workbook_unreadable`, `sheet_missing`) with nothing echoed.

`capabilities.weekly_report.handlers` are the four read capabilities:
`weekly-report/resolve-window` (`ResolveWindowInput.request`),
`jira/search` (`JiraSearchInput.jql`, `max_issues`; `JiraSearchOutput.issues`
normalized through `rules.issue_to_row`, threads the search truncated
re-fetched, `capped` only when a result past the cap existed),
`excel/read-scratch-sheet` (`ReadScratchSheetInput.week` → `SheetState`; a
sheet whose header row names no `Key` and `Comments` is refused, not planned
as empty) and
`weekly-report/plan` (`PlanInput.window`, `issues`, `sheet` →
`WeeklyReportPlan`). A Jira outage is raised as `TransientCapabilityError`;
every other failure is raised and fails the step, so a run never claims
success it did not earn. `capabilities.weekly_report.manifest` ships the
Skill `weekly` (`preview`) and the Workflow
`engineering/jira-weekly-report-preview` over those four steps, which the
Workflow names in `dependencies.local_capabilities` so a host lacking one
refuses the run before its first step; `host_runtime.assets.export_assets`
writes them as JSON under `skills/` and `workflows/`.

The host: `HostIntegrations` (`jira`, `weekly_report`) on
`CompanyHostConfiguration.integrations`; `build_integrations` installs the
four capabilities from it (the Jira token's name must be mapped, like every
other secret); `build_runtime(..., jira_transport=)` lets a test inject the
wire; `doctor` gains an `integrations` check that reads the configuration,
the library and the workbook's presence without contacting anything;
`aep-host export-assets --out <dir>` writes the shipped manifests.
`CompanyHostConfiguration.capability_timeout_seconds` (default 600) is how
long one step may run on this host: the platform's thirty seconds suits a
file read and not a Jira search with a throttle waited out. A step that
outlives it fails as `timeout`; the thread it ran on finishes on its own, so
the cap is a report, not a stop. `workflow_wait_seconds` (default 900, never
shorter) is how long a caller waits before the Agent reports a run still
running; `LocalAgent(workflow_wait_seconds=)` applies it on every ingress.
The `integrations` check fails when the weekly report is configured without
a Jira site.

## Workflow 11: writing the plan into the workbook (Phase 7, slice 3b)

`integrations.excel_writer` is the writing vocabulary, typed: `Fill` (a
`colour` of None clears, which is not white — Excel reports an unfilled cell
as white and only `ColorIndex = xlNone` means no fill), `FontColour`,
`Border`, `Hyperlink` (whose `formula` is an `=HYPERLINK()`, never a COM
Hyperlink object, because those leak references and keep Excel alive),
`TextRun` for a rich cell and `UpsertResult` (what was inserted and updated,
and where each key landed). `WorkbookWriter` is the protocol the executor
speaks: `backup`, `ensure_sheet`, `upsert`, `fills`, `format`, `cell_text`,
`rich_prepend`, `set_rich`, `close`. `hyperlink_formula`, `column_letter`,
`header_index` (case-insensitive, `header_missing` when absent) and
`plain_key` (a key cell already holding our formula reads back as the bare
key) are its pure helpers. `workbook_is_open` is a filesystem check, not a
COM one, because it has to be answerable without opening the file;
`stage_workbook` and `unstage_workbook` copy the workbook somewhere no sync
client is watching and put it back once, retrying a lock for thirty seconds.
`WorkbookWriteError` codes are `library_missing`, `excel_missing`,
`save_failed`, `workbook_missing`, `workbook_open`, `workbook_unwritable`,
`sheet_missing`, `header_missing` and `write_failed`, and nothing else
travels. The first two
are different absences: `library_missing` is this installation without the
Excel bridge, `excel_missing` is a machine without Excel. `require_com`
tells them apart with `progid_is_registered`, which reads the registry and
starts nothing, because the preview bundle always carries the bridge and an
importable `win32com` therefore says nothing about Excel. It reads the
registry directly rather than asking the bridge: the bridge's module is a
shim over a DLL, and on a host where that shim is unhappy every question
asked through it fails alike, which would make "Excel is not installed" the
answer to a question about something else.

`ExcelComWriter` is the one adapter and the only thing that knows about COM
(`pywin32`, the `windows` extra, imported lazily). It opens a private Excel
with events and screen updating off, because a team workbook may carry macros
and `Workbook_Open` would otherwise run inside a job nobody is watching; the
pinned source Bridge does the same and is the parity baseline. It saves and
releases separately: `Save` then `Close(SaveChanges=False)`, so a failed save
is `save_failed` rather than something swallowed with the release, which is
best effort. The save retries a lock for as long as the copy back does,
because everything past it discards the run's work: the workbook is released
either way, since an invisible Excel holding a file the member cannot see is
worse than the failure. The executor lets that one refusal through its own cleanup,
because a report that was not saved must not be copied back as though it
were. It carries the source's
`_excel_upsert` rules: the last data row comes from the used range because
hidden rows count, only managed headers are ever written so the hand-kept
`Comments` column survives, and header matching is case-insensitive.
**The suite never exercises it**: there is no Excel in CI, so every test
drives a recording writer as the source's own tests did, and the adapter is
unproven until the owner runs it — recorded in `docs/TASKS.md` beside the
model adapters, which carry the same caveat.

`capabilities.weekly_report.apply.apply_plan(plan, settings, writer,
staging_root=)` executes a plan in the source's order, which is the order
that makes the marks mean what they say: back up, stage, verify, ensure the
scratch sheet, upsert, **retire last week's marks across the whole sheet**
(the `Comments` column to the tail colour, the `Key` column's fill cleared,
and only the `Status` cells holding exactly this job's pink — the member's
own colours are read and left alone), tint what gained content, border and
pink what is new, recolour the blocks already present, link every key, then
prepend each block in red with a black tail. A block the writer reports as
already at the top is recoloured instead, because the reset has just turned
it black. A comment cell that cannot be written is recorded and the week's
report goes on, as the source did.

`ApplyRefused` is a `CapabilityRefused` whose code the member sees on the
failed step: `sheet_changed` (the plan carries the scratch sheet's digest as
it stood, and a sheet somebody has changed since — or one somebody has since
*made*, when the plan was made without one — is refused, not written),
`header_missing`, `workbook_missing`, `workbook_open`, and
`write_back_failed`, which says the report was written and saved and only the
copy back failed, so the finished workbook is the staged one. The guard runs
before anything is copied or backed up, so a refused run leaves nothing
behind. A run that does not
finish closes without saving, leaves the real workbook exactly as it was and
names the staged copy. `WeeklyReportApplied` is the evidence: the digests
before and after, the backup's path, the staged path, every count the source
reported and each `FailedComment`; `evidence_lines(applied, plan)` is what
the parity gate reads.

`WeeklyReportPlan` gains `scratch_present`, `seed_sheet`, `browse_base`
(taken from the issues themselves) and `sheet_headers` so a writer needs
nothing but the plan, and `WeeklyReportSettings` gains `local_staging`. The
column letters come from `sheet_headers`, the member's own header row, so the
write lands where the preview said it would even on a sheet whose layout
differs from the column contract. The managed headers are the columns the
job writes and **never `Comments`**: a writer sets every managed header from
the record it is given, the record has no comments, and naming the column
would blank the hand-kept log on every planned row.
`capabilities.weekly_report.handlers.APPLY_SPEC` is the first capability in
this repository with a side effect: `write`, `approval_required`, so the
Bridge policy refuses it unless the member's decision carries an
`approval_ref`. The Workflow `engineering/jira-weekly-report` is the
preview's four steps plus apply; `jira-weekly-report-preview` is unchanged,
so a member can still be given the dry run alone, and the `weekly` Skill
gains `apply` beside `preview`, which stays the default.

`capabilities.runtime.CapabilityRefused(code)` is new and general: a handler
refusing what it was asked to do with a code of its own, which
`BridgeExecutor` puts on the failure. The handler's *message* still never
travels — it may quote the input or the data it reached — but the reason now
does.

`workflow.dispatch.BridgeExecutor` now validates a step's inputs strictly
against JSON (`model_validate_json(json.dumps(arguments), strict=True)`)
rather than strictly in Python: a step's arguments are what an earlier
step's output serialized to, so a list is a tuple and an ISO string is a
date, while `"1"` is still not an integer. A handler that raises
`ValueError` is refusing what it was given, and the step fails as
`invalid_input` rather than `handler_error`; its text still never travels.


## Workflow 10: the chipset report's rules (Phase 7, slice 4a)

`capabilities.chipset_report.ruleset` is everything the report knows that is
not code, typed. The source kept it as an unvalidated dictionary read from
`config/chipset-map.json`, with every lookup carrying its own inline default,
so a misspelt key reverted to that default in silence. `ChipsetRuleset` is
closed: `split` (the separators, the noise, filler and role words, the
quantity suffix and the two switches that drop undecided chipsets), `vendors`
(the output order, the literal vendor words and the model-number prefixes),
`chipset_aliases`, `technology` (the canonical values, the keywords, the
generation labels and the model rules), `brand` and `mfg`, `priority`,
`status`, `dri` and `output` (the display choices, the colours and the
watched columns).

`load_ruleset` reads the file the team already has, in its own spelling. It
forgives two kinds of key and nothing else: documentation, which that file
uses for its reasoning, and the four keys the source read nowhere, which are
named in `IGNORED`. `RulesetError` codes are `ruleset_missing`,
`ruleset_unreadable`, `ruleset_not_an_object`, `section_not_an_object`,
`rules_not_a_list`, `rule_not_an_object`, `unknown_key`, `ruleset_invalid`
and `pattern_invalid`, and each carries `where`: the key that was not
understood, never what was in it. A ruleset is hundreds of lines long, and
bisecting one by hand is the failure that detail exists to prevent. An empty
watch list means the usual two columns rather than none of them, as the
source read it.
`compile_rules` turns a ruleset into `Rules`, which is what every rule takes,
so no pattern is compiled per cell.

`capabilities.chipset_report.rules` is the transformation, pure: nothing
reads a file, a clock or the environment, and the date a run stamps arrives
as an argument, because a plan has to be the same plan when it is applied.
`SourceRow.from_record` reads a project row by column name through
`header_key`, which folds case, spacing and punctuation but never spelling.
`split_chipsets` turns a free-text cell into `ChipsetToken`s;
`resolve_technologies` answers from one source and says which; `aggregate`
merges by chipset and technology, counting an opportunity once across fiscal
years, and returns what it dropped rather than leaving it on a function
attribute; `match_against_existing` reports `tracked`, `tracked-other-tech`,
`partial` or `new`; `render_row` writes one record keyed by the sheet's own
headers plus ten audit columns; `transform` runs the whole of it and returns
`TransformResult`, which carries the records, the dropped chipsets and the
counts.

The defects preserved from the source are marked **preserved** where they
live, and the five fixed are listed in `docs/PHASE_7_MIGRATION.md`,
"Workflow 10". Nothing here writes a workbook.


## Workflow 11's second source: the GitHub Projects client (Phase 7, slice 5)

`integrations.github_project` reads the board that replaced Jira.
`GitHubProjectConnection` says which board and which secret opens it, never
the secret itself: the owner, whether it is a user's board or an
organization's, the project number, the API address, the page sizes and the
timeout. `GitHubProjectClient` resolves the secret through the host's
`CredentialResolver` on every call, holds it nowhere, follows the board's
pages, and honours a throttle up to a minute before giving up on it.

`ProjectItem` is one row of the board: the board's own identifier, the issue
key as `owner/repo#number`, the title, the URL, the state, when it was last
updated, the field values by name, the comment thread, and whether that
thread was longer than the client asked for. `ProjectComment` is when a
comment was written, by whom, and its body.

`GitHubError` codes are `github_credential`, `github_auth`, `github_http`,
`github_unavailable`, `github_bad_reply`, `github_scope_missing`,
`github_not_found`, `github_rate_limited`, `github_project_missing` and
`github_issue_unreadable`. GitHub answers a query it would not run with
`200` and a typed error, so the kind is in the body and the status says
nothing; `REFUSAL_CODES` maps the kinds it names. Only the code travels to
whoever asked, so it carries the meaning: "the reply was bad" and "this token
has no project access" are otherwise the same sentence, and only one of them
tells somebody what to do. A throttle is `github_rate_limited`, which the
capability raises as transient beside an outage. The last is this source's own trap: reading the
board and reading the issues on it are two different permissions, and GitHub
answers a token that holds only the first by omitting the content rather than
refusing. Every row would then arrive with no title and no comments, which
reads exactly like a week in which nobody wrote anything, so it is a refusal
here. A query GitHub partly refused comes back as `200` with an `errors`
block, so the body decides and not the status.

## E2E-02 SOP acceptance and Workflow validation

`DraftWorkflowRequest` keeps the written SOP, target namespace/name and exact
`required_capabilities` together without turning the acceptance requirement
back into prose. Required identities are scoped, versioned and unique. They do
not grant permission; they let the deterministic reviewer reject a candidate
that silently omits an outcome the user required. `WorkflowDraft.request`
echoes the accepted request so the ingress can prove what reached the drafter.

`WorkflowFixture` is representative run arguments plus an independently chosen
expected final output. `WorkflowAcceptanceRequest` keeps that fixture separate
from the drafting request, and both reject embedded secret values through the
normal contract boundary.

`WorkflowValidationEvidence` records the request trace, exact manifest SHA-256,
run identifier, completed step count, ordered capability dispatches, expected
and observed outputs, and a typed pass/fail code. A pass has no failure code and
must identify the run that produced it. The evidence is created by
`PersonalWorkflowAuthor`, not by the model: it executes the draft in a
throwaway Workflow inventory through the existing Gateway, engine, Bridge and
policy. The draft is never added to the host inventory by validation.

`publish_validated_workflow` is a pure lifecycle transition. It requires an
approved `BusinessApproval` and passing evidence bound to the exact manifest
digest. It does not install, register, distribute or authorize the result, and
it does not change `TechnicalPolicy`. This preserves all three separations:
validation from model confidence, business approval from technical policy, and
publication from execution permission.

## E2E-03 bounded Coding Harness

`CodingHarnessRequest` is the trusted run envelope. `WorkspaceSnapshot` names
an absolute root and its SHA-256 content revision. `allowed_paths` and
`allowed_commands` are explicit allowlists; at least one `new` and one
`regression` `ValidationCase` are required. `HarnessBudget` bounds repair
attempts and validator calls. `skill_versions` records the exact procedures
assembled for the run. All request, candidate, validator and result payloads
reuse the platform credential-content rejection rule.

`HarnessPlan` is created before mutation and names each intended path and each
validator. It grants no access: runtime allowlists remain authoritative.
`CandidateChange` carries one proposed file. `ChangeRecord` is the separate
actual change set with before/after digests and a reviewable unified patch.

`CommandOutcome` contains a pass or typed `ValidationFailure` values with the
case, code, expected output and observed output. The Harness feeds that object
to the provider-neutral `ChangeAuthor.repair` boundary and stops when its repair
or command budget is exhausted. Only an installed `DeclaredCommands` handler
can validate; a model statement and an undeclared command cannot complete a run.

`CodingHarnessResult` echoes the immutable workspace snapshot and trace, keeps
the plan separate from actual changes, records command outcomes and ordered
events, identifies the final artifact by path and digest, and carries Skill
versions. `validated` requires a final passing command and an artifact.
Non-success requires a typed failure and no artifact. `committed` and
`published` are fixed false because those transitions are outside the Harness.

## E2E-05 governed Knowledge evolution

`KnowledgeManifest` is the versioned catalog record for one local vault. It
combines normal asset governance with domain, exact vault reference, immutable
Raw digest, decisions digest, complete Knowledge content digest and ordered
evaluation case identities. A published manifest requires domain approval,
validation evidence and matching `knowledge-case:<id>` evaluation references.

`KnowledgeQueryRequest` selects an exact scoped version. `KnowledgeAnswerRecord`
binds that version and request trace to the complete answer and exact cited
passages. Every sentence must contain a citation and every cited passage must be
Raw evidence; a Wiki-only claim cannot become a grounded answer.

`KnowledgeImprovementRequest` retains the exact answer, trace and cited evidence
that prompted the feedback, plus expected information, deterministic
reproduction and acceptance criteria. It begins with pending development
approval. `authorize_improvement` represents maintainer triage and does not
modify the published vault.

`KnowledgeCandidateRequest` is the input to the Bridge-installed candidate
workspace writer. It names the exact base version, approved improvement, new
version, absolute target root, typed `WritePlan`, new and regression cases, and
stable write stamp. The candidate preserves namespace/name, changes version,
has unique case identities, and cannot embed credential material.

`KnowledgeCandidate` is always draft or validated. `KnowledgeValidationEvidence`
binds its exact content digest, Raw digest before/after and one result for every
ordered case. A pass requires byte-identical Raw and all new and regression
cases to return grounded answers containing required facts and excluding
forbidden facts. Content drift or evidence from another candidate cannot be
approved or published.

`approve_candidate` records the separate domain-owner business decision only
after passing validation. `publish_candidate` then creates the published
manifest and its validation/evaluation references; neither function installs a
capability or grants execution permission. `KnowledgeCatalog` admits only exact,
published and digest-matching versions and retains earlier versions for rollback.

## Bridge Extension and Application categories (Productization 3, slice 1)

`BridgeExtensionManifest` is governed Registry metadata for publisher code that
may add local Bridge capabilities. It fixes the supported Windows, Python and
ABI boundary; names an out-of-process module and versioned JSON-lines protocol;
declares unique typed `CapabilitySpec` values; and carries bounded startup,
request, crash and rollback policy. A published manifest requires technical
approval, policy references and validation evidence. `PublisherKeyRef` names a
public Ed25519 trust-root identity only and never contains a private key.

`PublishedAssetPackage.kind` can identify a `bridge_extension`, but
`MemberCatalogEntry` continues to reject it because Agent Add-on selection is
not extension activation. Staging, local activation approval, healthy runtime
advertisement and capability authorization remain separate later boundaries.

`ApplicationCatalogEntry` projects one published `SoftwareManifest` as an
independent Application. Its named integrations are HTTPS or loopback Web/API/
MCP endpoints whose callable interface must be declared by the Software asset,
or one exact Workflow identity. `ApplicationProjection` exposes discovery and
integration metadata only; it has no extension process, install package or
Bridge activation field.

`PortableExtensionPackage` is the inert staging envelope. It contains the exact
published `BridgeExtensionManifest`, canonical `requirements.lock` and
`wheels/*.whl` files, per-file SHA-256, a canonical content SHA-256 and
`ExtensionSignature`. The signature key must equal the manifest's public
`PublisherKeyRef`. `ExtensionTrustPolicy` contains explicit public keys and
revocation state; `ExtensionSignatureVerifier` is injected and has no unsafe
default. `stage_extension_package` checks all boundaries, derives an exact
identity path and atomically exposes `StagedExtension`. The result says only
`staged`; it carries no activation, health, grant or execution claim.

`ExtensionActivationApproval` is trusted device-local input that binds one
exact staged version to actor, device kind/id and approved technical-policy
reference. `ExtensionRequest` and `ExtensionResponse` are closed correlated
`aep-extension-jsonl/v1` messages for health, invoke and shutdown. A healthy
response declares exactly the signed manifest's ordered capability identities.

`ExtensionManager` admits no advertisement before successful health. Its
`ExtensionActivationRecord` distinguishes active, refused, unhealthy,
rolled-back and disabled state. Failed upgrade preserves the previous session;
process failure removes advertisement, enforces the manifest crash window and
may restart the retained approved version. `SubprocessExtensionFactory`
prepares only the staged wheels using offline/no-dependency pip and launches a
fixed isolated interpreter/module vector without a shell or credential-bearing
environment. Advertisement remains separate from `LocalPolicy` authorization.

`ApplicationCatalog` registers exact `ApplicationCatalogEntry` versions and
refuses duplicate identity. `ApplicationCatalogRequest` contains only an
optional namespace; `MemberService.application_catalog` derives the actor and
groups from its authenticated member session and applies normal asset
entitlement. `ApplicationCatalogReply` contains read-only projections and no
Bridge id, package, selected, installed or active field. The member HTTP route
is `/v1/member/applications`; it has no corresponding mutation route.

`ExtensionLifecycleSnapshot` is the secret-free, atomic local evidence file
written by `ExtensionManager`. It retains the latest
`ExtensionActivationRecord` for each exact version while ensuring at most one
current active/rolled-back version. A failed upgrade records the candidate as
unhealthy and the retained version as rolled back. It contains no activation
approval, signer private key, credential or execution grant.

`ExtensionLifecycleProjection` is the Personal Agent Web view produced only by
joining a valid identity-derived staged package with that optional local
evidence. Without runtime evidence a valid package is `staged`. It shows the
publisher key id, declared capability identities and applicable human gate,
but is not accepted by any activation endpoint. The direct-member page consumes
`ApplicationCatalogReply` separately and renders only declared external Web UI
links; API, MCP and Workflow integration metadata remains descriptive.

## Portable Knowledge package (Productization 2, slice 2)

`PortableKnowledgePackage` carries one exact published `KnowledgeManifest` and
its governed Vault content. Its manifest uses `package://vault`, never a local
filesystem path. `KnowledgePackageFile` admits canonical relative POSIX paths
only: the three root governance files, any immutable `raw/` evidence and
Markdown under `wiki/`. It refuses absolute paths, drive-qualified paths,
backslashes, traversal, `drop/`, ingest state/cache files, duplicate paths,
file digest mismatch and recognizable credential material.

The package requires `index.md`, `log.md`, `decisions.md`, at least one Raw
file and at least one Wiki page. Its identity must equal the manifest identity;
the Raw, decisions and complete Knowledge digests must match the manifest
before installation. `package_knowledge` also proves the source Vault has not
drifted. `install_knowledge_package` validates the complete serialized package,
writes a sibling staging directory, reopens it through `Vault`, rechecks all
aggregate digests and atomically exposes the target directory. The returned
local manifest replaces only `vault_ref` with the host-derived absolute path.
An existing exact version is never replaced.

An active `DeviceAssetSelection(kind="knowledge")` joins Workflow and Skill in
`DeviceAuthorization.installable`; it remains distinct from a capability tool
selection. `PlatformClient` requires Registry metadata (other than the outer
artifact reference) to exactly match the portable manifest, derives
`assets/knowledge-vaults/<namespace>/<name>/<version>`, installs the Vault and
writes the local manifest containing only that host-derived path. A preexisting
path or mismatching manifest/Vault is `asset_conflict`.

On host rebuild, `build_knowledge_catalog` combines explicit trusted local
bindings with active synchronized Knowledge selections. A synchronized
manifest must point at its identity-derived directory. The query handler is
registered before platform-selected capability grants are derived; Knowledge
selection itself adds no grant. A configured routing model and a separate
`knowledge-query/ask@1.0.0` capability selection/grant remain required.

## E2E-04 governed Software evolution

`SoftwareManifest` is Registry metadata, not a source archive. It combines the
normal scoped identity/owner/visibility/lifecycle/compatibility fields with an
`ExternalRepository` provider, locator and exact revision, typed
`SoftwareInterface` values and `SoftwareRelease` evidence. Published Software
requires business approval, validation and evaluation references. The release
revision must equal the repository revision.

`SoftwareFailureReport` carries the exact target version and trace, expected and
actual behavior, evidence, representative input, expected and observed output,
reproduction environment and acceptance criteria. It contains no repository or
owner field. `capture_improvement` resolves those from the exact catalog entry
and creates a pending `SoftwareImprovementRequest`; user input cannot redirect
development to another repository.

`SoftwareDevelopmentRequest` carries only the improvement request. The
Bridge-installed handler cross-checks its owner/repository against the catalog
and uses trusted `InstalledRepository` configuration for the local root, path
allowlist, validator, regression corpus and Skill versions. Owner triage and
Bridge execution approval are both required and remain independent.

`SoftwareDevelopmentResult.reproduction` is the declared validator outcome on
the unchanged published revision. It must contain the reported failing case and
the recorded observed output before the `CodingHarness` can run. A passing
baseline yields `unreproduced`; a broken baseline or Harness regression yields
`failed`. Neither state can contain a PR artifact.

`PullRequestCandidate` binds the exact trace, Software version, repository,
Harness change set and validation digest. Its `external_write`, `merged` and
`released` fields are fixed false. The CI `InertSourceControlAdapter` only keeps
these artifacts in memory.

`PullRequestReview`, `MergeRecord` and `ReleaseRecord` are explicit human-owned
transitions. A rejected review cannot produce merge evidence. Merge evidence
binds the reviewed candidate digest, old and new repository revisions and human
review; release evidence binds the new Software identity to that merge.
`publish_software` requires another owner approval, preserves technical policy,
and creates a new manifest whose `previous_version` remains registered for
rollback. None of these contracts installs an executable capability or creates
a Bridge grant.

## E2E-01 DUT and instrument engineering

`DutTarget` and `InstrumentTarget` identify the exact local resources involved,
including DUT vendor/model/firmware and optional instrument model/firmware.
Their `resource_id` values must also be advertised by the executing Bridge.
`DutCommand` holds a named, typed JSON argument object and rejects credential
material.

`DutValidationRequest` binds a Bridge, 64-character workspace revision, exact
versioned Skill, target, optional instrument, ordered unique commands and one or
more deterministic acceptance criteria. `MeasurementLimit` has a unit and
finite minimum and/or maximum. `ExpectedState` compares one observed state
field to a typed JSON value. The request is invalid without at least one limit
or expected state.

Each adapter returns one `DutObservation` per command. `DutValidationService`
constructs `ValidatorOutcome` values by comparing measurements, units and final
state itself. `DutValidationEvidence` requires aligned commands/observations and
derives its pass/fail status from all outcomes. An adapter mode of `simulator`
or `recording` can only produce `simulated` evidence; `physical` is the sole
source of `production_like` evidence.

`DutDevelopmentRequest` combines an existing `CodingHarnessRequest` with the
simulator request. Both must name the same starting workspace revision and the
Harness must declare the exact Skill version. `DutDevelopmentResult` can report
`simulated_validated` only when both the Harness and independent simulator pass,
and its physical gate is always false.

`DutPhysicalValidationRequest` is dispatched as the high-risk
`dut-engineering/validate-physical@1.0.0` capability. `DutHostBinding` supplies
the exact installed Skill, local target/instrument identities, availability,
an absolute fixed driver command and an explicit physical enable switch. The
company-host service applies device admission and checks registration, Skill,
resource and execution-mode identity before invoking the adapter.

`PhysicalDriverConfiguration` rejects relative executables and credential-like
fixed arguments. `SubprocessDutAdapter` runs the fixed argument vector with no
shell and exchanges JSON over standard input/output. It does not decide whether
a measurement passed.

`DutChangeReview` is the separate human business decision. An approved review
requires passing production-like evidence and therefore cannot be constructed
from CI simulation, a recording or an out-of-limit physical run. Review approval
does not itself publish a Skill or grant future execution permission.

## Personal Agent identity, conversation and script tools

`Invitation.role` and `PlatformUser.role` separate ordinary members from
`platform_admin`. Invitation proofs are single-use. `MemberLoginGrant` is a
revocable, durable browser credential that mints short `MemberSessionGrant`
values; only its opaque bearer is kept in browser local storage. Identity,
invitation, login and session records may share `SqliteIdentityStorage` without
putting a bearer secret in SQLite.

`ConversationRecord.backend` selects the configured Gateway or one restricted
local CLI adapter. Local adapters accept the bounded transcript over stdin,
run in an isolated working directory with a fixed argument vector and reduced
environment, and return text only. They do not register or dispatch a Bridge
capability. Slash commands are parsed before any conversation backend.

`ConversationBackendStatus` separates `selectable` from `available` and reports
authentication as `ready`, `required`, `pending`, `unavailable` or
`not_applicable`. A configured Gateway remains selectable when its external
`SecretRef` mapping is not ready; the turn still fails closed until the
credential resolves. Local CLI authentication is an explicit loopback Web
action accepting only a closed backend name. It launches the corresponding
fixed official login vector (`codex login`, `claude auth login` or
`copilot login`) without a shell in the isolated backend directory and a
reduced environment. Login output, account data and credentials are not
returned to the Web API. Selecting or authenticating a backend grants no
Bridge capability or tool permission.

`ScriptToolManifest` binds one published and approved exact asset identity to a
package-relative `.py` or `.ps1` entrypoint, SHA-256, timeout, dependencies,
secret references and an `execute` `CapabilitySpec`. The metadata and runtime
technical policies must match. The Bridge verifies the file before registration
and again before each invocation, uses a fixed noninteractive interpreter with
no shell, exchanges JSON through stdin/stdout and still applies normal local
policy and approval checks. `SkillManifest.script_tools` contains references
for documentation only and grants no execution authority.

# Numeric Workflow command aliases (2026-10-02)

`WorkflowManifest.run_alias` is an optional integer from 1 through 9999.
Older manifests omit it. Agent Web resolves `/run <number>` and
`/run workflow <number>` only when exactly one installed manifest in the
current namespace declares the number. A zero or multiple-match result
returns `needs_input`; no version is guessed. Resolution produces the exact
`AssetIdentity`, which is then submitted through normal resident-Agent
admission and Bridge authorization. The shipped weekly-report preview alone
declares alias 11; its workbook apply and mail Workflows do not.

# Workflow runtime form fields (2026-10-02)

`WorkflowManifest.parameters` is optional so older installed Workflows retain
their JSON argument editor. Each declared field has a unique name, visible
label, `runtime` or `static` scope, and one of `text`, `date`, `integer`,
`boolean` or `select` kinds. A select declares distinct options; integer
bounds apply only to integers. Credential-shaped names are invalid: secrets
remain `SecretRef` requirements, never form values or shared asset content.

Agent Web projects only runtime fields into its Workflow run form. It validates
the submitted object against the exact installed manifest before resident
Agent dispatch: undeclared names, static settings, missing required values,
wrong JSON types, invalid dates, select values and out-of-bound integers are
rejected. This is input validation, not an execution grant; the exact
Workflow still passes local admission and Bridge policy. The shipped weekly
report Workflows declare optional week, start/end date, issue cap and advanced
command text fields. Their deterministic capability request contract remains
the final domain validator, including week-name and date-window rules.

Static field definitions are reserved in the manifest contract for a later
per-install settings slice. This change does not edit `host.json`, create a
static settings editor, or generate Telegram controls.

# Workflow forms v2 (2026-10-15)

`WorkflowParameter.allow_other` (default false, `select` only, not with
`multiple`) makes the choices suggestions: any nonempty text is valid, the
Agent tool schema has no `enum`, and the engine does not consult the field's
`choices_source` at run time. A `choices_source` placeholder may name a
`scope: static` setting; it is bound from the install's settings and is never
waited for. `fn:folder_files?folder={x}&accept=.a,.b` is a built-in read-only
function returning the bare names of regular files directly in that absolute
folder. A choice function that fails or times out yields no list.

`kind: upload` values are absolute paths of files in the host's upload store
(`<workspace>/workflow-uploads/<set>/<field>/<name>`), written only by
`POST /api/workflow-uploads` (Agent Web, base64 JSON: `workflow`, `field`,
`upload_set`, `filename`, `data`) or a Telegram flow's document replies.
Limits: 25 MB a file, 20 files a field, the field's `accept` extensions,
sanitized names. `WorkflowEngine` rejects a run whose upload value is not a file
in the store with `workflow_upload_outside_store` (needs_input).

Identity presets: `POST /api/workflow-identity` (`workflow`) returns the
calling member's last `group: identity` values for that Workflow name, kept in
`<workspace>/identity-presets.json` after a validated, dispatched run.

`engineering/rs-wmt-package-release@1.0.0` chains `release-package/prepare`,
`release-package/commit` (step inputs `branch`, `fingerprint` from step 0) and
`release-package/push` (`branch`, `commit` from step 1, `push` from the run).
`PushStepInput` gains `push: bool = true`; with `push` false, or an empty
`commit` (nothing committed in this run), the step returns `pushed=false` with a
`skipped` reason and touches nothing. The release request gains
`testPlanUploads`, `configurationUploads` and `overlayUploads`, accepted only
inside the upload store the host gives the prepare handler. The preview
Workflow no longer declares alias `13`; Workflows are started by name. See
`docs/phases/WORKFLOW_FORMS_V2.md`.

# Workflow 7 read-only Project preview (2026-10-02)

`engineering/github-team-tickets-preview@1.0.0` has numeric alias `7` and
one `team_tickets.preview` read step. Its request has bounded `max_items` and
`comment_count` runtime fields. The Host uses its existing configured GitHub
Project credential reference; the Workflow contains no token or workbook
path. `TeamTicketsPreview` returns source-order managed column values for
Task and Issues, a `capped` indicator, exact keys with incomplete comment
threads, and names of fields the GitHub source could not supply. Jira
Resolution is always absent. The capability still requires local
`github.read` permission and `github-read-policy`; manifest installation,
numeric resolution and Skill routing do not grant either.

# Source Workflow migration parity (2026-10-03)

For every future migration from `dragon0816/rs_workflow_system`, the original
job and Workflow are the **behavioral baseline**. Before implementation, the
migration record must identify the source repository revision and exact files.
If local source additions are not committed, record their SHA-256 digests and
the observed output fixture instead of presenting the repository commit as
covering those files. The baseline includes input and configuration fields,
static and runtime defaults, issue selection, output content and formatting,
side effects, idempotency, dry-run behavior, and failure/partial-result rules.

Each migrated Workflow must have source-derived regression fixtures or
comparison runs before replacing behavior. The AEP adapter may change
transport, authentication, data-source wiring and authorization boundaries,
but it must preserve user-visible behavior. Every difference must be listed
with the reason, expected effect, owner decision when behavior changes, and a
test proving the new rule. A simplified reimplementation is not parity merely
because it produces a successful run. Installation and approval remain
separate from execution, and source repositories remain read-only.

For new migrations, evaluate direct reuse or a thin wrapper around the pinned
Python/PowerShell job before porting its business logic. The wrapper may map
the job's static and runtime parameters to AEP's typed form, resolve Host-owned
paths/secrets, and invoke it through the Bridge's exact capability identity.
The source's n8n trigger JSON is historical reference only; no n8n development
is required or scheduled for this migration. A Host
grant for an owner-approved local effect is durable and specific: an Outlook
draft grant permits saving an unsent draft but never sending mail; a configured
Excel write grant permits only the declared workbook operation. Missing grants
are a Host configuration defect to repair, not a reason to replace the proven
job or claim that a draft is a message send. See the owner correction recorded
in `docs/DECISIONS.md` on 2026-10-03.

Workflow 11's initial pinned Jira source is
`rs_workflow_system@896046e8fe2170d21f9213e56e5ce2f93c05ba43`.
Its later local `host-bridge/jobs/github_weekly_email.py` adapter is not in
that commit; the inspected file's SHA-256 is
`62c5220c8757f3596e55757d438e64efa03466e5bf5e5010326d821f08bf458d`.
The owner's existing Outlook draft titled
`SDE Weekly Report 2026_40W (2026-09-28 - 2026-10-04)` is an additional
visible-output fixture. The AEP version now preserves the requested subject,
recipients, activity count, member/instrument/account figures and new Excel
format rules. Its mail image now adapts the source's composite pie and stacked
member bars using the same Issue-assignee and comma-split Project Production
series as the HTML totals. The workbook Assignee cell uses the GitHub Issue
assignees, while the Key hyperlink uses that Issue URL; an empty Issue
assignee connection is not replaced by the Project's free-text field. The
source's `Other` bucket is intentionally omitted at the owner's request, so
each Production name remains visible. Do not claim full mail or workbook
parity until a live source-draft comparison and saved workbook-copy check pass.

# Local Agent schedule foundation (2026-10-03)

`ScheduleDefinition` names one owner and one exact installed `workflow` or
`agent_task` identity, plus bounded JSON runtime inputs and a daily or weekly
local HH:MM recurrence in an IANA timezone. It contains no credential, grant,
approval, arbitrary command or model-selected target. `ScheduleRecord` holds
the current active/paused state and next UTC due time; `initial_status` is
only the creation default. A nonexistent local time during a daylight-saving
change is skipped. A repeated local time runs once at its first occurrence.

`SqliteScheduleStore` is a Host-owned, device-bound SQLite store separate from
conversation and Workflow checkpoint data. One committed transaction claims
each due occurrence and advances its next due time. The claim carries a stable
idempotency key derived from schedule ID and UTC due time, and remains pending
across restarts until a worker records a terminal result. Repeated claims at
the same time return nothing; contradictory terminal outcomes are refused.
Pausing creates no backlog; resuming computes the next occurrence from the
resume time. A worker must reconcile outstanding claims with the existing
run ledger before retrying to avoid repeating a side effect. Claiming does
not execute anything or confer permission.

Execution wiring, a Host lifecycle worker, create/pause/resume/history UI or
CLI, and a choice of first-release target kinds remain subsequent slices.
When wired, each claimed target must pass resident Agent membership admission,
exact installed-asset lookup, Workflow/Task policy, Bridge grants and any
effect-specific approval. No scheduled send, write or draft may bypass them.
The paragraph above is superseded by the following section.

# Scheduled tasks v1 (2026-10-04)

The owner decided on 2026-10-04: no n8n; both Workflows and Agent Tasks are
targets; Agent Web screens are in the first release; an opt-in loop runs in
the long-running Host process; `read` may run unattended, `write`/`execute`
need both grants, `external_side_effect` always needs per-run approval; missed
runs are caught up once within a bounded window. See `docs/DECISIONS.md`.

**Execution grant.** `ScheduleExecutionGrant` names the owner, one
`schedule_id`, the exact `target_kind`/`target`, `max_side_effect`, a
`policy_ref`, `approved_by` (must equal the owner), `approved_at` and an
optional later `expires_at`. Only the owner creates one, through
`aep-host schedules grant` or Agent Web; the Host supplies owner, approver,
time and policy reference (`owner-schedule-grant`). It never comes from a
schedule definition, asset or model. Granting again revokes the previous
grant; `ScheduleGrantRecord` keeps revoked grants with `revoked_by` and
`revoked_at` for audit. A saved schedule is not permission.

**Per-occurrence decision.** `ScheduleGrantAuthorizer.decide` returns a
`ScheduleDecision` with a code. It refuses `schedule_grant_missing`,
`schedule_grant_expired`, `schedule_grant_mismatch`, `workflow_not_installed`,
`task_not_installed`, `capability_not_installed`,
`schedule_effect_above_grant` (the highest `side_effect` among every
capability the target can reach exceeds the grant) and `bridge_grant_missing`
(the Bridge `LocalPolicy` would not authorize one of those capabilities for
the owner). When everything holds and the target can reach an
`external_side_effect`, it returns `run_approval_required`. The worker
enforces that last rule itself for any authorizer. Admission, Workflow
preflight and Bridge policy still run at dispatch. Workflow runtime inputs are
validated against declared parameters at creation and again at dispatch
(`workflow_parameters_invalid`).

**Run states.** `ScheduledRun.status` adds `awaiting_approval`; it also
records the evaluated `side_effect`. `claimed` may have dispatched and blocks
later occurrences of its schedule. `awaiting_approval` dispatched nothing and
does not block; claiming a newer occurrence settles it as
`needs_input/run_approval_superseded`. Approving turns it back into a
`claimed` occurrence before dispatch, recording a `ScheduleOperatorDecision`,
then every check above runs again with the per-run approval present. Denying
settles it as `needs_input/run_approval_denied`. Resolving a stuck `claimed`
occurrence records who decided, when, an optional note and one outcome:
`succeeded`, `failed` or `not_run` (stored as
`succeeded/operator_resolved_succeeded`, `failed/operator_resolved_failed` or
`needs_input/operator_resolved_not_run`). Resolution dispatches nothing and
releases the schedule. Notes reject credential material.

**Catch-up once.** `claim_due(catch_up=...)` claims only the latest
occurrence that is due; earlier missed occurrences are skipped. When that
latest occurrence is older than the window (`schedules.catch_up_hours`,
default 24, 1-336), nothing runs and it is recorded as
`unavailable/schedule_missed`. Claims are never replayed across restarts.

**Store.** `schedules.sqlite` schema version 2 adds `schedule_grants` and
`schedule_decisions`. A version 1 file is migrated in place; a newer version
is refused as `unavailable`. Connections wait up to five seconds on a busy
file because the loop, Agent Web and a CLI tick may share it.

**Agent Task targets.** An installed Agent Task is an `AgentTaskTemplate`
in `<workspace>/assets/agent-tasks/*.json`: exact identity, description and
the `TaskContract` fields (objective, task type, classification, Skills,
allowed/prohibited capabilities, expected outputs, checks, constraints). It
has no actor, trace, grant or runtime parameters. An identity installed twice
is not installed. Per occurrence the Host builds a `TaskContract` for the
bound member with a unique task ID and artifact references and runs it
through `LocalAgent.run_task`, the same admission, `GatewayTaskExecutor`
scope and data-policy, Bridge policy and completion validation as
`aep-host run-task`. Scheduled Agent Tasks take no runtime inputs. Their
effect class is the highest among allowed capabilities, which the executor
limits to `read`. There is no Registry asset kind or installer for Agent
Tasks yet.

**Trigger.** `aep-host schedules tick` runs one poll (for Windows Task
Scheduler via `deploy/windows-preview/schedule-tick.ps1`, or recovery).
`ScheduleLoop` polls immediately, then every `schedules.poll_seconds`
(default 30), in the `aep-host web` process only when `--schedules` or
`schedules.resident_loop` is set; `aep-host schedules run` runs the same loop
without a page. Building a Host or `AgentWeb` never starts it. Each poll and
each approval holds Agent Web's one-request-at-a-time lock. Stopping waits
for the poll in progress; an interrupted run stays an open claim.

**Controls.** `ScheduleControl` serves the CLI (`create`, `list`, `pause`,
`resume`, `history`, `grant`, `revoke`, `pending`, `approve`, `deny`,
`resolve`, `tick`, `run`) and Agent Web (`GET /api/schedules`,
`GET /api/schedules/history`, `POST /api/schedules/{create,pause,resume,
grant,revoke,approve,deny,resolve}`). The routes use Agent Web's loopback,
`Host` header and Bearer token guards and refuse a non-loopback `Origin`.
Browser bodies cannot name an owner, approver or policy; resolution requires
`confirm: true`. The Schedules panel renders host values as text nodes only.

# Workflow 10 Host preview and guarded apply (2026-10-03)

`HostIntegrations.chipset_report` holds the source workbook paths and sheets,
fiscal-year labels, target workbook, managed sheet/header row, temp sheet and
rules-file path as **static** Host configuration. Runtime input may reduce the
row cap but cannot supply a file path or ruleset. Paths must be absolute and
the managed `Chipset_requirement` sheet cannot be selected as the temp sheet.
No secret is stored in an asset. The pinned source and the validation gap are
recorded in `docs/WORKFLOW_10_HOST.md`.

`engineering/sales-to-chipset-preview@1.0.0` has alias `10` and invokes a
`read` capability requiring `chipset-report.read`. Its output includes exact
target/temp digests, source summaries and snapshot changes, projected rows,
match and drop counts and row-level dropped evidence. Preview does not change
the workbook or source baseline. `engineering/sales-to-chipset@1.0.0` then
passes that typed plan to a separate `write` capability with `excel.write`,
medium risk and explicit approval. Apply refuses changed target/temp content,
an open workbook or changed non-temp sheets/macros, writes a staged copy and
copies back only after verification. A snapshot baseline is saved after the
verified copyback; a baseline-save error is reported as a warning without
misstating the workbook result. Asset installation confers no execution grant.

# Workflow 13 local preview (2026-10-03)

`HostIntegrations.release_package` names an existing checkout and inbox using
absolute paths. `engineering/release-package-preview@1.0.0` has alias `13`;
the exact read capability requires `release-package.read` and returns the
projected version, `release.yaml`, pinned requirements, selected file digests
and changed paths. It rejects a checkout that is absent or on a different
branch. The original parameter names are accepted through a typed request;
runtime upload sets and automatic version lookup are not yet enabled. The
source contract and explicit gaps are in `docs/WORKFLOW_13_SOURCE_CONTRACT.md`.
No preview result authorizes Git commit, push or release publication.
`engineering/release-package-apply-isolated@1.0.0` is a separate, no-alias
write Workflow. It is registered only with explicit
`HostIntegrations.isolated_release_apply` settings naming a marked allowed
root and a no-remote Git checkout beneath it. It requires the exact local
capability grant and an approval reference. It prepares local package files
under a checkout lock and reports `prepared=true`, `committed=false`,
`pushed=false`. It has no Git command, network, commit or push path. This
isolated preparation is testable migration evidence, not a release action.

# Product/market Knowledge evidence matrix (2026-10-04)

`knowledge-query/market-matrix@1.0.0` is a read-only Bridge capability for one
exact installed Knowledge asset. It takes only an `AssetIdentity`; the Host
resolves the Vault, actor and Bridge from trusted configuration. It needs an
exact Host grant with `knowledge-query.ask` and `knowledge-grounding-policy`.
It does not require a model or a LiteLLM credential. Installing the companion
`company-agent/market-alignment@1.0.0` Skill does not grant execution.

The v1 output has exactly 25 cells in the canonical five product-family by
five-market order. A cell contains one of `nearby_mention` (Raw product and
market aliases within 350 characters), `separate_passages` (distinct product
and market evidence without a nearby match), or `no_raw_match`. Evidence names
the immutable Raw source identity, file, section, optional page/slide and a
bounded verbatim excerpt. A cell also lists three knowledge gaps: market
application/standard, product and option specifications, and independent
customer/use-case validation. `market_fit_verified` is always false in v1.
These lexical discovery labels cannot authorize a recommendation. Existing
`knowledge-query/ask@1.0.0` and its grounded answer contract are unchanged.

# Workflows 06 / 06b parity: loan replies (2026-10-20)

Source baseline: `dragon0816/rs_workflow_system@896046e8fe2170d21f9213e56e5ce2f93c05ba43`,
committed files (SHA-256 of the working copy, identical to the commit):
`host-bridge/jobs/_loan_queue.py` 5d818baa6d7f629d728bbcd29c803ee396c76d767211c8010d05ac18e7601b33,
`_loan_rules.py` f94ce39f224663e72a116758fb163d4aa3601869cfaaf7d31ec8db58126c745c,
`_loan_templates.py` f6ba083eabd28433afc4caed6d876a608ea8e2ff9553163577ea147df5098a7c,
`loan_process.py` ea07cfc230c76d04b2877a46cf09182fbfecd19b232bcb14ac379870fb40a933,
`loan_scan.py` 5f7961091c92ebce546b4670d61195288858c5cb682f2ecaddb1f76b932ac734;
tests `test_loan_process.py` f2b8c7cbfe889b4ae90f4457d01ce6d02afbe8fb240fbff076429acb9d8b7473,
`test_loan_queue.py` 7919bfbe8a6c240cf19759f205bfc0819789ad27bb19b1a1d300b24e95458ca2,
`test_loan_rules.py` aae376e2302329c8a280283fd6b5cac80d12ec94f5484d86e81995bdc9237ec3,
`test_loan_scan_start.py` f6171b74802d0dcbc820be5d68b06288974b47a4201720da10e1e3213f3a43d6,
`test_loan_templates.py` 647654ac3765b92aaf9d1265bb03fc42f7aceec1ced6f16e45b8e6557c45abe4. Uncommitted installation files
`config/loan-templates/*.txt` (the job's `--write-templates` output): blocked-reply
12b3a49da66a419dd9d9c56b69e1180e4aa96d1b06e1bcb9c54d5f5c1b560373, customer-not-found-body
4401dd130c20c6582e8825ac5cef61b9a731ae301570d68900628964d888ce50, customer-not-found-subject
5df6de7fdda841e4cc2cc1b4ddd9d7cf6e6b312118ec11fd34bf8955755164df, failure-body
2c349ed06b204d7bed61d09b7d5ee2b9464f0fe37127e08da346e5a896114dc0, failure-subject
5152bafce46c6b5789d1ce89d7a06ebb7e24cc56152ae0969511415c0045622a, shipping-reply
f35470f5ab2cb88d89797cf94b3c5b88f9ccb7d98820e2f13b64f468e88430f8.

**Contracts.** Producer `engineering/rs-loan-customer-block-scan@1.0.0` (`/run 6`): settings
`mail_folder` (Inbox), `max_messages` (200), `process_from`, `require_sender` (false),
`sender_smtp`, `exclude_categories`; run `dry_run`, `process_from_once`. Steps
`loan/scan-mail@1.0.0` (read; `loan.scan-mail.input.v1` = `ScanStepInput{request}`, output
`LoanScan`) and `loan/enqueue@1.0.0` (write, low risk, approval; output `LoanEnqueued` with
`preview`, `verdict`, `follow_up`). Consumer `engineering/rs-loan-queue-reply@1.0.0`
(`occupies_machine`): settings `alert_recipient`, `template_dir`, `portal_origin`,
`c4c_home_url`, `loan_account`, `close_browsers_after`, `show_browser`, `settle_ms`,
`busy_timeout_ms`, `nav_timeout_ms`; run `dry_run`, `max_items` (1–20), `offer_send` (false).
Steps `loan/look-up@1.0.0` (read), `loan/draft-replies@1.0.0` (write, medium risk, approval),
`loan/offer-send@1.0.0` (write, low risk, approval; output `LoanReplyResult` with `preview`,
`verdict`, `action_cards`). `loan/send-reply@1.0.0` is `external_side_effect`, high risk,
approval; declared, never installed. All under `loan-reply-policy`, permission `loan.<name>`.
Refusal codes: `loan_process_from_invalid`, `loan_mail_unreadable`, `loan_outlook_unavailable`,
`loan_scan_refused`, `loan_browser_unavailable`, `loan_template_invalid`.

**Result keys for the channels** (new, generic): a Workflow's last step may carry `follow_up`
(`{workflow, label, reason}`) and `action_cards` (card ids). Agent Web's form run records the
follow-up as the answer's `workflow_form` (origin `follow_up`) and the cards as its
`action_cards`; Telegram appends the step's `preview`, draws the cards and adds a
`/run namespace/name` button. Neither runs nor sends anything.

**Send cards.** `ls-` + 12 hex; `LoanReplyCard` (borrow number, draft entry id, fingerprint of
to/cc/subject/attachment names, the text shown); actions `send`, `keep_draft`; statuses pending,
sent, kept, expired (24 h), failed; `web_only`. `decide(channel="telegram")` is `web_only`.

**Parity evidence** (`tests/test_loan_reply_parity.py`, `tests/test_loan_*_source.py`):

| Baseline item | Evidence |
|---|---|
| Source tests (141 functions, 162 cases) | vendored; pass against `capabilities.loan_reply`; text equals source + import replacements |
| `rules`, `templates`, `queue` | text equals source + declared replacements |
| Page scripts, selectors, sign-in and C4C reading (`_Page`, `_Edge`, `read_loan_form`, `open_accounts`, `read_delivery_blocks`, constants) | source text, compared |
| Message texts | shipped `loan-templates/*.txt` equal the built-in text and the source installation's files |
| Dry-run plan (scan) | same candidates, skips and counts as source `loan_scan.run(dryRun=True)` on one mailbox (four categories, a rejection, a duplicate, non-loan and undated mail, an excluded category) |
| Normalised queue output (scan) | same queue files (minus timestamps) as the source run |
| Drafts and queue end state (06b) | shipping, blocked, customer not found, fields unreadable, form failed; dry run and real: same reply / draft calls (kind, to, subject, body, attachments, `send: false`), same queue files, same failures and preview bodies as source `loan_process.run` |

Differences (each with a test, listed in `src/capabilities/loan_reply/SOURCE.md`): steps instead
of one run; a dry scan writes no stamp; links only to `portal_origin`; no HTTP Bridge
(`BridgeUnavailable`); notices as HTML drafts with the same text; optional per-message send;
no read-step run lock. Not proven by tests: Outlook COM listing and reply drafting, the browser
on the real portal and C4C, the profile sign-in (owner checklist in
`docs/phases/RS_WORKFLOW_MIGRATION.md`).

## BI cards API and capability (Knowledge Strategy v1.3 Case A, owner 2026-10-21)

Code: `src/capabilities/bi_cards/` (schema registry, store, import, dashboard, capability,
Skill), `src/host_runtime/bi_cards_api.py` (routes), `src/host_runtime/bi_cards_tools.py`
(chat tool). Tests: `tests/test_bi_cards.py`.

- **Schema registry** `bi.schema/v1.1`: `src/capabilities/bi_cards/bi_schema_v1_1.json`,
  generated by `scripts/build_bi_schema_v1_1.py` from the robotics sample's schema v4
  (`tests/fixtures/robotics_kb_sample/tools/bi_schema.py`, read with `ast`, never imported).
  12 types. Each field: `name`, `label` (first Chinese alias), `kind` (`str`, `int`, `bool`,
  `date`, `enum`, `list`, `link`, `linklist`, `virtual`), `class` (`sourced` / `judgement` /
  `derived`, ADR-K11; Trend `market_impact`, `measurement_impact`, `our_fit` are `sourced`),
  `enum`, `aliases` (column aliases), `link_to` (target types; empty = any type), `list`.
  `domain` is a list on Technology, TestSolution, Concept, Account, Ecosystem, Competitor and one
  value on the others (wireless / AIDC / robotics, case-insensitive; unknown values dropped with
  a `domain_unknown` warning; a card without `domain` counts as wireless). Every type also has
  `body` (備註). `id_rules` and `field_classes` are copied from `bi.schema/v1`.
  Application `priority` is **not a field** (#222): `ignored_fields` lists it with the reason
  「優先度由 Skill 依事實判斷，不存資料」. Trend priority is in `computed_fields`
  (`measurement_impact * our_fit`, `stored: false`).
- **Store** `<workspace>/bi/<dataset>/bi.sqlite` (dataset `[A-Za-z0-9_-]{1,40}`, default
  `demo`). Cards keyed by `(entity_type, canonical_key)`; `canonical_key` = the naming field
  (Signal: `<date>-<title>`). Per field: value, source `kind` (`import` / `human` / `fixture`;
  history also has `undo`), `ref` (`<file>#row<n>` or `agent-web:<actor>`), `by`, `at`;
  append-only history. An import never overwrites a `human` value: it adds a pending proposal.
  Reading never creates the database. A card is **trusted** only when a person set
  `confidence: verified` and the card is not synthetic; rows whose text marks example data
  (虛構, 範例, 示範, 待…驗證, 待查證) and every demo card are synthetic (DQ-1).
- **Routes** (Agent Web, loopback, `Authorization: Bearer <page token>`; errors
  `{"ok": false, "code", "message"}` with 4xx; an unknown card, preview or import is 404):
  - `GET /api/bi/schema` → `{"schema_id", "types": [{"name", "label", "fields": [{"name",
    "label", "type", "class", "enum": [...] | null, "link_to": <type> | null, "list": bool}]}]}`
    (`type` is the schema `kind`; `link_to` is the first target type).
  - `GET /api/bi/datasets` → `{"datasets": [{"name", "cards": int, "updated": iso | null}]}`.
  - `POST /api/bi/demo/load {"dataset": "demo"}` → `{"ok": true, "imported": {"created",
    "updated", "unchanged"}}`. Idempotent. Loads the 12 robotics CSVs (104 cards) in the order
    Node → Technology → Trend → Competitor → Ecosystem → Account → Application →
    CustomerProduct → TestSolution → Opportunity → Signal → Concept.
  - `POST /api/bi/import/preview {"dataset", "entity_type": str | null, "filename",
    "csv_text", "mapping": obj | null}` → `{"preview_id", "entity_type", "columns": [{"source",
    "field", "status": "mapped" | "alias" | "unknown" | "ignored", "note"}], "rows": [{"row",
    "canonical_key", "action": "create" | "update" | "unchanged" | "skip", "fields": [{"field",
    "raw", "normalized", "current", "change": "add" | "change" | "same" | "human_kept"}],
    "warnings": [{"code", "message"}]}], "summary": {"create", "update", "unchanged", "skip",
    "warnings"}}`. Writes nothing; the preview is held in memory (the last 50) and is never
    searchable. `row` is the CSV line number (header = 1). Warning codes: `link_missing`,
    `link_type_mismatch`, `type_mismatch`, `domain_unknown`, `priority_ignored`,
    `fictional_not_trusted`, `name_missing`, `row_skipped`. `mapping`: `entity_type`,
    `columns` {header: field}, `defaults` {field: value} (new cards only), `enum_aliases`
    {field: {alias: value}}, `skip_rows` [{"column", "contains": [...]}]. A null `entity_type`
    is guessed from the headers. Not implemented: `explode`, `derive`, `compose`.
  - `POST /api/bi/import/apply {"preview_id", "rows": [int] | null}` → `{"ok": true,
    "import_id", "applied": {"created", "updated", "unchanged", "proposals"}}`.
  - `POST /api/bi/import/undo {"import_id", "dataset"}` → `{"ok": true}`; `dataset` defaults to
    `demo` (addition to the agreed body). A field a person changed after the import keeps the
    person's value; a second undo is `import_already_undone` (400).
  - `GET /api/bi/cards?dataset=&type=&q=&domain=` → `{"cards": [{"id", "entity_type",
    "canonical_key", "name", "review_status": "draft" | "verified", "synthetic", "domain",
    "updated", "fields": int}]}`.
  - `GET /api/bi/cards/<id>?dataset=` → `{"card": {...as listed..., "version"}, "fields":
    [{"field", "label", "value", "class", "source": {"kind", "ref", "at", "by"}, "history":
    int}], "links": [{"field", "target_id": str | null, "target_key", "missing"}],
    "proposals": [{"field", "value", "source": {"kind", "ref", "at"}}]}`.
  - `POST /api/bi/cards/<id>/field {"dataset", "field", "value", "base_version", "reason"}` →
    `{"ok": true, "version"}`, or 409 `{"ok": false, "code": "stale_edit", "message",
    "current", "by", "at", "version"}`. 400 codes: `field_unknown`, `field_derived`,
    `base_version_missing`, `reason_required` (a `judgement` field needs `reason`),
    `value_invalid`. `value` is normalised like an import cell (a list is accepted for a list
    field; empty clears the field). The edit closes the field's pending proposals.
  - `GET /api/bi/cards/<id>/history?dataset=` → `{"history": [{"field", "old", "new",
    "source": {"kind", "ref"}, "at", "by", "reason"}]}`.
  - `GET /api/bi/dashboard?dataset=&domain=robotics` → `{"domain", "sections": [{"id",
    "title", "kind": "table" | "matrix" | "funnel", "columns": [...], "rows": [[...]],
    "flags": [{"row": i, "level": "red" | "warn", "text"}], "note"}]}`. A cell naming a card is
    `{"card_id", "label"}`; `title` starts with the section id. Sections in this order (ids
    from `Dashboard-Robotics.md`): `6` gaps (red 「對手有、我方無」, warn 「全無」; ours =
    TestSolution `vendor` blank), `10` trend → application → solution, `19` demand without
    opportunity, `18` our solutions × active opportunities (not won/lost), `17` funnel by
    `deal_stage`, `14` technologies without a Concept, `16` customer product × ecosystem ×
    trend completeness, `1` trend priority (computed), `2` launch timeline, `4` Node ×
    Technology matrix, `5` recent signals, `6b` competitor coverage matrix, `7` share of
    assumed content, `8` stale (> 90 days), `12` supplier dependency (Account `key_suppliers`
    and CustomerProduct `ecosystem`). Application priority is never shown.
- **Capability** `bi-cards/query@1.0.0` (read, no approval, permission `bi-cards.query`):
  input `dataset`, `entity_type`, `text`, `domain`, `field`, `value`, `follow_links` (true),
  `limit` (1–100, 20); output `dataset`, `total`, `cards` [{`card` ("<type>:<key>"),
  `card_id`, `entity_type`, `name`, `trusted`, `synthetic`, `fields` {name: {`value`, `source`
  ("<kind>:<ref>")}}, `links`}], `scope_note`. Only stored card fields are searched (never
  previews or proposals). Installed when the Skill is installed (on or off); the chat tool
  `bi__query` is offered while the Skill is switched on.
- **Skill** `engineering/bi-knowledge@1.0.0`, shipped switched on (`host_runtime.assets.shipped`,
  so `assets install-bundled` switches it on on an existing PC). Procedure: answer only from
  cards, cite `[卡片 <type>:<key>]`, mark 事實 vs 推論, say 待驗證 for untrusted cards, scope gaps
  as 「在這份資料集中沒有…」, judge priority itself from the facts and say so (#222).

### Per-dataset schemas (owner 2026-10-21: 「只讓資料集換 schema」)

Code: `src/capabilities/bi_cards/catalog.py` (sources, validation, install, resolve),
`store.py` (binding), the routes above. Tests: `tests/test_bi_schemas.py`,
`tests/test_bi_schemas_ui.py`. Every addition below is additive; a request without a dataset or
schema behaves as before.

- **Sources**: the shipped `bi.schema/v1.1` (`version` `1.1.0`, `source: "shipped"`) and installed
  files at `<workspace>/bi/schemas/<schema_id>@<version>.json` (a `/` in the id is a sub-folder;
  `source: "installed"`). A file whose content no longer validates, or whose place does not match
  its id and version, is not offered.
- **Schema file** (JSON, UTF-8, at most 1 MB; the shipped registry's format). Required:
  `schema_id` (lowercase letters, digits, `.` `_` `-`, up to 3 `/`-separated parts; the
  `bi.schema/` prefix is reserved), `version` (`MAJOR.MINOR.PATCH`), `title`, `types` (1–50). Each
  type: `name` (`[A-Za-z][A-Za-z0-9_]*`, unique), `label`, `fields` (1–100). Each field: `name`
  (`[a-z][a-z0-9_]*`, unique in the type), `label`, `kind` (`str`, `int`, `bool`, `date`,
  `enum`, `list`, `link`, `linklist`), `class` (`sourced` / `judgement` / `derived`). Optional:
  field `aliases` (CSV header aliases), `required`, `default`, `enum` (required for `enum`),
  `range` ([min, max], `int` only), `link_to` (target types in this schema; required for
  `link`/`linklist`), `list` (must match the kind); type `naming` (fields forming the card key,
  default `["name"]`), `domain` (`one`/`multi`/`none`, default `none`), `has_confidence`,
  `description`, `code_key`; top-level `description`, `domains`, `enum_aliases` ({field: {alias:
  value}}), `ignored_fields`, `status`, `source`, `id_rules`, `field_classes`, `computed_fields`.
  An unknown key is an error (catches typos). Example (shipped, not installed):
  `src/capabilities/bi_cards/samples/product-spec@1.0.0.json` (「產品規格」: Supplier,
  Component, Product, SpecItem) with four sample CSVs.
- **Immutability**: an installed id@version never changes. Installing the same content again
  (compared as parsed JSON, so formatting does not matter) is a no-op (`"already": true`);
  different content for the same id@version is 409 `schema_version_exists`.
- **Binding**: a dataset is bound to one `<schema_id>@<version>`, stored as `meta.schema` in its
  `bi.sqlite`, chosen at creation and never changed. A dataset without the row (created before
  this) is `bi.schema/v1.1@1.1.0`, and its next write records that; a dataset first written by an
  import or the demo load (not created) is bound the same way. Cards, import, search, detail,
  field edits and history use the dataset's schema. If its schema file is gone: 400
  `schema_missing` (the message names the id@version).
- `GET /api/bi/schemas` → `{"schemas": [{"id", "version", "ref": "<id>@<version>", "title",
  "types": [{"name", "label"}], "source": "shipped" | "installed", "dashboard": bool}]}`, the
  shipped schema first.
- `GET /api/bi/schemas/example` → `{"schema": {"filename", "json_text"}, "csv": [{"entity_type",
  "filename", "text"}]}` (the shipped example, CSVs in import order). Writes nothing.
- `POST /api/bi/schemas/install {"filename", "json_text"}` → `{"ok": true, "id", "version",
  "already": bool}`, or `{"ok": false, "code", "message", "errors": [{"path", "message"}]}`:
  400 `schema_invalid` (every problem, `path` like `types[1]（Component）.fields[3]（supplier）
  .link_to`), `schema_json_invalid` (`path` = the line), `schema_missing_text`,
  `schema_too_large`, `schema_not_json` (filename not `.json`); 409 `schema_version_exists`.
- `POST /api/bi/datasets {"name", "schema": "<id>@<version>" | "<id>"}` (a bare id takes its
  newest version) → `{"ok": true, "dataset": {"name", "cards": 0, "updated": null, "schema",
  "dashboard"}}`. Name: ASCII letters, digits, `-`, `_`, 1–40 characters, not `schemas`, unique
  ignoring case. Errors: 400 `dataset_invalid`; 404 `schema_unknown`; 409 `dataset_exists` (with
  `schema`: the existing binding; a schema cannot be changed).
- `GET /api/bi/datasets` adds `"schema"` and `"dashboard"` (whether the schema is `bi.schema/*`)
  per dataset.
- `GET /api/bi/schema?dataset=<name>` returns that dataset's schema and adds `"version"`, `"ref"`,
  `"title"`, `"bi"` (bool) and `"domains"`; without `dataset` it stays `bi.schema/v1.1`.
- **BI-only**: `GET /api/bi/dashboard` for a dataset whose schema is not `bi.schema/*` answers 200
  with the empty state `{"dashboard": false, "code": "no_dashboard", "message": "這個 schema 沒有
  Dashboard", "schema", "domain": null, "sections": []}`. `POST /api/bi/demo/load` into such a
  dataset is 400 `schema_not_bi`. `bi-cards/query` (chat `bi__query`) refuses it with
  `schema_not_bi`, shown as 「這個資料集用的不是 BI schema…」. The `domain` filter of
  `GET /api/bi/cards` is ignored for a schema without `domains`.

## BI dataset sharing (slice 1, owner 2026-10-22)

Design: `docs/proposals/BI_DATASET_SHARING.md` (§4, §6, §8.5 owner answers, §8.6 trimmed slice 1:
no pinning or rollback, no Marketplace/Overview listing). A BI dataset is published to the Shared
Platform as an immutable snapshot of the new asset kind `bi_dataset`; a colleague selects one exact
version for their Bridge and the Agent installs it as a **read-only** copy. All additions are
additive: nothing existing changes shape.

Code: `src/capabilities/bi_cards/snapshot.py` (format, build, read, install),
`src/control_plane/bi_datasets.py` (publish, status, download, audit),
`src/host_runtime/platform_publish.py` (`MemberPortalPublisher` client methods).

### Snapshot format `aep-bi-dataset-snapshot/1`

A gzip stream (mtime 0, no file name) of one UTF-8 JSON object, written with sorted keys and
compact separators so the same dataset always gives the same bytes:

```json
{
  "format": "aep-bi-dataset-snapshot/1",
  "classification": "INTERNAL",
  "dataset": "demo",
  "schema": {
    "ref": "bi.schema/v1.1@1.1.0", "id": "bi.schema/v1.1", "version": "1.1.0",
    "source": "shipped",
    "sha256": "<sha256 of catalog.canonical(document) as UTF-8>",
    "document": { "...": "the schema JSON itself (installed: the file's content; shipped: bi_schema_v1_1.json)" }
  },
  "cards": [
    {
      "id": "3f2a9c1b0d4e", "entity_type": "Customer", "canonical_key": "acme",
      "name": "ACME", "version": 3, "synthetic": false,
      "created": "2026-10-21T08:00:00+00:00", "updated": "2026-10-21T09:00:00+00:00",
      "created_by_import": "a1b2c3d4e5f6",
      "fields": {
        "region": {"value": "TW", "kind": "import", "ref": "customers.csv#row4",
                   "by": "leo.chi", "at": "2026-10-21T08:00:00+00:00"}
      },
      "history": [
        {"seq": 1, "field": "region", "old": null, "new": "TW", "kind": "import",
         "ref": "customers.csv#row4", "by": "leo.chi", "at": "2026-10-21T08:00:00+00:00",
         "import_id": "a1b2c3d4e5f6", "reason": null, "old_source": null}
      ]
    }
  ],
  "imports": [{"id": "a1b2c3d4e5f6", "filename": "customers.csv", "entity_type": "Customer",
               "at": "2026-10-21T08:00:00+00:00", "by": "leo.chi", "undone": false}],
  "meta": {"source_last_updated": "2026-10-21T09:00:00+00:00",
           "stats": {"cards": 1, "cards_by_type": {"Customer": 1}, "fields": 1,
                     "history": 1, "imports": 1}},
  "digest": "<sha256>",
  "publication": null
}
```

- **Cards** are sorted by `(entity_type, canonical_key)`, history by `seq`, imports by `(at, id)`.
  Field `value` and history `old`/`new` are the stored JSON values; `old_source` is the previous
  source `{kind, ref, by, at}` or `null`.
- **Digest**: SHA-256 (hex) of the canonical JSON (sorted keys, separators `,` `:`, UTF-8,
  `ensure_ascii=False`) of the whole object **without** `digest` and `publication`. It identifies
  the content: the same dataset gives the same digest, and stamping a publication does not change it.
- **`publication`**: `null` in what the owner's Agent builds. The platform stamps it on publish
  (`{"namespace", "name", "version", "base_version": str | null, "published_by", "published_at",
  "note"}`) and re-gzips; that stored artifact's SHA-256 is the package's `PackageMetadata.sha256`.
- **Stripped** (§4.5, owner Q3): pending proposals (the `proposals` table is never read);
  folders in `ref` (the part before `#`, and refs without `#` that contain a path separator), in
  `old_source.ref` and in `imports.filename` (only the file name stays); proposal-only imports
  keep their `imports` row (id, file name, time, `by`, `undone`) so history `import_id` resolves.
- **Actors** (`by`, the actor in an `agent-web:<actor>` ref): mapped through the optional
  `accounts` mapping (local name → platform account); a name with no mapping is kept as it is. On
  a PC whose Agent actor is the platform account (the usual case) nothing changes.
- **Secrets**: every field name and every string (values, history, reasons, refs) is checked with
  `common.assets.SECRET_PATTERN` / `SECRET_FIELD`. A hit fails the build with `secret_found`,
  naming the card (`<entity_type>:<canonical_key>`) and the field, never the value.
- **Limits**: gzip ≤ 20 MiB (`MAX_SNAPSHOT_BYTES`, the platform's limit is configurable), JSON
  ≤ 256 MiB decompressed (`MAX_SNAPSHOT_JSON_BYTES`), ≤ 50 000 cards (`MAX_CARDS`); beyond:
  `artifact_too_large`.

### Python API (`capabilities.bi_cards.snapshot`)

```python
SNAPSHOT_FORMAT = "aep-bi-dataset-snapshot/1"
class SnapshotError(Exception):        # .code, .message, .card: str | None, .field: str | None
def build_snapshot(store: BiStore, *, accounts: Mapping[str, str] | None = None,
                   max_bytes: int = MAX_SNAPSHOT_BYTES) -> bytes
def read_snapshot(data: bytes, *, max_bytes: int = MAX_SNAPSHOT_BYTES) -> Snapshot
def stamp_publication(snapshot: Snapshot, publication: Publication) -> bytes   # platform side
def schema_state(snapshot: Snapshot, workspace: Path) -> SchemaState
def install_schema(snapshot: Snapshot, workspace: Path) -> SchemaState
def install_snapshot(snapshot: Snapshot, dest_dir: Path) -> InstalledSnapshot
```

- `Snapshot` (frozen): `document` (the parsed dict), `digest`, `dataset`, `schema_ref`,
  `schema_id`, `schema_version`, `schema_source` (`shipped`/`installed`), `schema_sha256`,
  `schema_document`, `publication: Publication | None`, `stats`, `cards` (count).
- `Publication` (frozen): `namespace`, `name`, `version`, `base_version`, `published_by`,
  `published_at`, `note`; `.reference` is `<namespace>/<name>@<version>`.
- `read_snapshot` validates strictly (gzip, size, format, every key and type, unique cards, field
  names, schema digest, publication) and checks the digest and secrets; errors:
  `artifact_too_large`, `snapshot_invalid`, `digest_mismatch`, `secret_found`.
- `schema_state`: `shipped` (the shipped schema with the same digest), `present` (installed with
  the same canonical content), `missing` (not installed; `install_schema` installs it into
  `<workspace>/bi/schemas/`), `conflict` (same id@version, different content → `install_schema`
  raises `schema_conflict` and writes nothing), `unavailable` (a shipped id@version this AEP does
  not ship, or with another digest → `schema_unavailable`).
- `install_snapshot(snapshot, dest_dir)`: `dest_dir` must not exist (or be an empty folder),
  else `install_target_exists`. Everything is validated first; the store is built in a temporary
  sibling folder and renamed into place, so on any failure nothing is left at `dest_dir`. It
  writes `dest_dir/bi.sqlite` (the BI store tables with cards, fields, history and imports;
  `proposals` empty; `meta`: `schema`, `snapshot_format`, `snapshot_digest`, `read_only` = `1`,
  and `published_version` when stamped) and `dest_dir/snapshot.json` (the document without
  cards: format, dataset, schema ref/sha256/source, meta, digest, publication). Returns
  `InstalledSnapshot(path, dataset, version, schema_ref, digest, publication)`; `version` is the
  publication's (`None` for an unstamped snapshot). Read-only is enforced by `BiStore` for a
  subscribed dataset (`dataset_read_only`), not by file attributes, so the Agent can replace or
  delete the folder.

### Platform: asset kind `bi_dataset`

- `AssetKind` and `RunnableKind` gain `"bi_dataset"`; `DeviceAuthorization.installable()`
  includes it. It is **not** offered by `available()` / `catalog` of the Member Portal (no
  Marketplace listing in slice 1); the Bridge API `catalog` lists it to entitled members
  (`{"kinds": ["bi_dataset"]}`).
- Package: `kind: "bi_dataset"`, `metadata.identity` `<namespace>/<name>@<version>`, `owner` (the
  team for a new name), `visibility` `team` or `organization`, `provenance[-1]` `{"source":
  "bi-dataset-publish", "author": <publisher>, "revision": <content digest>}`, `package
  {artifact_ref: "registry://<ns>/<name>/<version>", sha256}`, `description` the version note.
- **Versions** (platform-assigned): the first is `1.0.0`; each later one is minor + 1, or major + 1
  when the schema's major version differs from the previous highest version's.
- **Access** (owner Q4): a new name is owned by the publisher's team (`team`, or their only group;
  a member with no group owns it themselves); readers default to `team`; `organization` needs
  `confirm_organization: true`; `public` (and `private`) are refused as `visibility_not_allowed`,
  also by `assets/access/update` for a `bi_dataset` name. Entitlement is the existing `entitled_in`
  (owner team, `NameAccess` members/groups).
- **Selection** (Member Portal `select` / `replace` / `revoke`) accepts `bi_dataset` with the
  existing rules: a non-entitled member gets 403 `asset_not_entitled`.
- **Sync** (Bridge API `sync`): a selected `bi_dataset` is planned and its artifact carried like any
  other package. A selection whose member is **no longer entitled** is not planned (owner Q2: the
  copy stops updating; the Agent keeps it); this is audited as `sync_refused`.

### Member Portal endpoints (POST, `Authorization: Bearer <session>`)

`POST /v1/member/bi-datasets/publish` (own body limit: `max_bi_dataset_bytes` × 4/3 + 64 KiB;
other routes keep 256 KiB):

```json
{"namespace": "engineering", "name": "robotics-bi", "base_version": null,
 "note": "first publish", "readers": "team", "confirm_organization": false,
 "team": null, "snapshot": "<base64 of the gzip snapshot>"}
```

- `base_version` must equal the highest published version (`null` for a new name), else 409
  `version_superseded`. `readers` `null` keeps the previous version's (`team` for a new name).
- The owner, an owning-team member or a co-editor publishes a later version **directly**; the
  **first version of a new name** goes to the admin review queue (owner Q5), as an
  `AssetSubmission` of kind `bi_dataset` approved with `admin/submissions/approve`. While it waits,
  another publish of that name is 409 `review_pending`.
- The platform re-reads the snapshot (`read_snapshot`: digest, strict shape, secret re-check),
  stamps `publication` and stores the stamped bytes.
- Reply 200: `{"status": "published" | "pending_review", "asset": {"namespace", "name",
  "version"}, "sha256": "<stored artifact>", "digest": "<content digest>", "size": int,
  "submission_id": str | null}`.
- Errors: 400 `snapshot_invalid`, 400 `digest_mismatch`, 400 `secret_found` (body adds `card`,
  `field`, `message`; never the value), 413 `artifact_too_large`, 409 `version_superseded`, 409
  `review_pending`, 403 `publisher_not_authorized` (not owner/team/co-editor, or `team` not one of
  the member's groups), 400 `visibility_not_allowed`, 400 `organization_unconfirmed`, 400
  `team_required` (several groups and no `team`), 409 `kind_mismatch` (the name is another kind),
  401 `session_expired`, 400 `invalid_request`.

`POST /v1/member/bi-datasets/status` — the entitlement check (owner Q2):

```json
{"names": [{"namespace": "engineering", "name": "robotics-bi"}]}
```
→ `{"datasets": [{"namespace", "name", "entitled": bool, "latest_version": str | null,
"published_by": str | null, "published_at": str | null, "note": str | null}]}` (1–100 names, in
the request's order). A name the member may not use and an unknown name both answer `entitled:
false` with the other fields `null` (nothing is disclosed). `entitled: false` from an answering
platform means "stop updating, keep the copy"; an unreachable platform means nothing. The same
fact is visible on the Bridge API: a held name absent from `catalog {"kinds": ["bi_dataset"]}`
is no longer entitled (versions are never deleted).

`POST /v1/member/bi-datasets/download {"asset": {"namespace", "name", "version"}}` →
`{"asset", "sha256", "size", "snapshot": "<base64>"}` for an entitled member; 404
`asset_not_published` (unknown, or not `bi_dataset`), 403 `asset_not_entitled`. Audited.

`POST /v1/member/bi-datasets/audit {"namespace", "name"}` → `{"events": [{"at", "event",
"actor", "namespace", "name", "version", "sha256", "size", "base_version", "note",
"bridge_id"}]}`, oldest first, for the name's owner, owning team, co-editors and platform
administrators; others 404 `name_missing`. Events: `submitted`, `approved`, `rejected`,
`published`, `selected`, `replaced`, `revoked`, `synced` (the Bridge a version was delivered to),
`sync_refused`, `downloaded`. Kept in the registry SQLite file (`bi_dataset_audit`) or in memory.

### Agent client (`host_runtime.platform_publish.MemberPortalPublisher`)

```python
def publish_bi_dataset(self, namespace: str, name: str, snapshot: bytes, *, note: str,
                       base_version: str | None, readers: str | None = None,
                       confirm_organization: bool = False, team: str | None = None) -> dict
def bi_dataset_status(self, names: list[tuple[str, str]]) -> list[dict]
def bi_dataset_download(self, asset: dict[str, str]) -> bytes   # checks sha256, else bad_reply
def bi_dataset_audit(self, namespace: str, name: str) -> list[dict]
```

Refusals raise `PublishError(code, status, message)`; `secret_found` carries the platform's
message naming the card and field. `explain(code)` has wording for every code above.

### Configuration

`SharedPlatformConfiguration.max_bi_dataset_bytes` (default 20 MiB, 1 MiB–64 MiB): the largest
stored snapshot (gzip). Deploying needs a platform built from this commit or later; no other
setting.

## Chat composer model choice (owner 2026-10-21)

Code: `src/models/selection.py` (`TURN_MODEL`, `SelectableModelClient`),
`src/host_runtime/conversation_models.py` (`ConversationModels`), routes in
`src/host_runtime/web.py`, composer in `src/host_runtime/web_page.py`. Tests:
`tests/test_conversation_models.py`, `tests/test_conversation_model_ui.py`,
`tests/test_session_model_scope.py` (session scope, 2026-10-22).

- **Which models**: the configured routing endpoint's model (Settings, `host.json` `models`) plus
  what that endpoint lists (`GET <base_url>/models` for `openai_compatible`, `/api/tags` for
  `ollama`), read by `AgentWeb.available_models` with the Host's credential mapping (the token
  never reaches the page). The list is cached 300 s; when it cannot be read, the configured model
  alone is offered (`source: "configured"`, `code` names why).
- `GET /api/conversations/models?session_id=<id>` →
  `{"ok": true, "source": "gateway" | "configured", "code": null | <reason>, "configured": <id>,
  "selected": <id>, "selected_from": "conversation" | "default" | "settings",
  "unavailable": <stored id the Gateway no longer serves> | null,
  "models": [{"id", "label", "status": "Settings default" | "Gateway"}]}`; the configured model
  is first, the others sorted. No model configured: `{"ok": false, "code":
  "model_not_configured", "models": []}`. Names only: no URL, credential or variable name.
- `POST /api/conversations/model {"session_id", "model"}` → `{"ok": true, "selected",
  "configured"}`; 409 with `code` `model_not_approved` (not the configured model and not in the
  Gateway's list, re-read once), `conversation_unknown` or `model_not_configured`.
- **Stored** in `<workspace>/conversation-models.json`: `{"defaults": {actor: model},
  "sessions": {session_id: model}}`. A pick is kept for the conversation and becomes the
  person's default for conversations without their own pick. Deleting a conversation removes
  its entry.
- **Applied** to Gateway-backend turns only, from the next message, without a restart:
  `AgentWeb.conversation_turn` sets `TURN_MODEL` to the conversation's model (None when it is
  the configured one); the router's model is `ApprovedModelClient(SelectableModelClient(...))`,
  so the data approval decides first; the switch then sends the chosen id to the same endpoint
  (same alias, URL, credential, capabilities and options) or refuses a non-approved id with
  `Failure(code="model_not_approved")` without sending anything. The chat shows "The model
  chosen for this conversation is not one the LLM Gateway serves now (model_not_approved)…".
  Requests outside a turn (schedules, Workflow drafting, the Knowledge and other capabilities
  built with the drafting client) keep the configured model. *Superseded in part on 2026-10-22,
  see "Session scope" below.*
- **Session scope (owner 2026-10-22)**: every model call made on behalf of a session uses that
  session's model. `models.selection.session_model(model)` is entered once per turn by
  `AgentWeb.conversation_turn` (Gateway backend) and `TelegramIngress._deliver_guarded`; the host
  builds **one** `SelectableModelClient` for the routing alias, shared by the router and every
  drafting client (Knowledge query, `workflow_author.draft`, business cards, coding change,
  Knowledge pipeline), each wrapped by `ApprovedModelClient`. `asyncio.run`,
  `asyncio.to_thread` and new tasks carry the choice; a plain thread or executor does not and
  must submit with `contextvars.copy_context().run` if it works for the turn.
  `models.selection.settings_model()` marks work with no session, which uses the configured
  model: `ScheduleControl.tick` / `approve`, `AgentWeb.nightly_tick`,
  `AgentWeb.experience_review`; the Knowledge page's jobs run in their own threads and so also
  use it. A CLI-backend session leaves the choice unset.
- **Telegram**: a chat is the session `telegram-chat-<chat id>`; its turn asks for
  `ConversationModels.for_turn(<sender's actor>, <session>)` (the chat's choice, else the
  person's default, else None). `/model` replies with the chat's model and source and a numbered
  list (`✓` on the current one, `· Settings default` on the configured one); `/model <number or
  id>` chooses through `ConversationModels.choose` (also the person's default) or replies
  `Not changed (model_not_approved)…`. Without Agent Web (`cards` unset) the Settings model is
  used and `/model` says so.
- **Which model answered**: `ConversationMessage.model: str | None` (1–200 characters, answers
  only, additive; older records read as None) is the last model id the turn's requests were sent
  to, recorded by `SelectableModelClient` in `TURN_MODELS_USED` after the approval and the
  model check passed; None when no model was asked (a command, a run form), the request was
  refused, or the session uses a CLI backend (its model is the backend's own). The page shows it under the answer as `.answer-model` 「模型：<id>」.
- **Page**: the backend selector (`#conversation-backend`) is in the top bar above the
  conversation, shown only on the chat tab; the composer has `#conversation-model` (label
  "LLM model"), a read-only label when one model is served or a CLI backend is active, and a
  status line; the menu is disabled while a turn of that conversation runs.
