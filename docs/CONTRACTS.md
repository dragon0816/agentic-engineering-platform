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
`telegram_unreachable`, `telegram_error`, `telegram_conflict` for HTTP 409 (retryable since
2026-10-30: `run` waits it out with the doubling delay and keeps it in `TelegramIngress.problem`,
shown by the settings as `telegram.problem` while the loop runs, so AEP takes the bot back once
the other program stops),
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
`state_busy`, `state_unavailable`) and the path at fault, never its contents. At start, a
state file another connection holds is waited for up to 30 s, then is `state_busy`; a file that
is broken or another device's is `state_unavailable` at once. Once running, a second writer is
still refused rather than waited for. A membership
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
`may_delegate_to` entry is refused (`profile_delegation_unsupported`) unless
`multi_agent.enabled`; then each target must validate ("Multi-agent delegation (V1)"). A successful activation
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

A side effect happens at most once per turn (P0-2, 2026-10-27). `Gateway.converse`
opens an in-memory per-turn record (`agent/turn_effects.py`), shared by the Host
check's retry pass and by any conversation or Workflow run nested under the same
turn (a delegated sub-run). A call is side-effecting when it runs a Workflow, when
its capability's `CapabilitySpec.side_effect` is not `read`, or when its
`HostTool.side_effect` (optional, `None` by default: not guarded) says so. Only a
call that really succeeded is recorded, keyed by a digest of the tool name and
its canonical arguments: a failed, refused or `awaiting_approval` call, or a
Workflow tool that only offered its form, runs again when asked. A repeat is not
executed; its `ConversationToolExecution` is the recorded one with
`replayed: true` (the field defaults to `false`), and the model's observation
adds `host_note` 「這個動作在本回合已執行過，未重複執行」. `Gateway.execute_workflow`
inside a turn and without an engine idempotency key applies the same rule to
the same Workflow, manifest, arguments and actor. Telemetry gets counts only: a
`tool.replayed` point event (`tool_id`, `loop_index`, `replayed`) and
`side_effects_recorded` / `side_effects_replayed` on the turn's `run.completed`.

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

**Credential variable names (2026-10-24).** The Bridge token (`shared_platform_token`) and the
Personal Agent code (`platform_member_login`) are saved for the Windows user, and read back,
under the variable host.json `credentials` maps the secret to
(`shared_platform.token_variable(config)` for the token); without a mapping the legacy names
`AEP_SHARED_PLATFORM_TOKEN` / `AEP_PLATFORM_MEMBER_LOGIN` are used and mapped on enrolment.
`deploy/windows-preview/install.ps1` maps both for an install outside the default folder
(`%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0`) to `<legacy name>_<SUFFIX>`, where
`SUFFIX` is the first 8 hexadecimal digits (upper case) of SHA-256 over the UTF-8 of the
lower-cased full install path without a trailing `\`; an existing mapping is never changed and
the default install gets none. `shared_platform_settings()["token_variable"]` reports the mapped
name. Two installs of one Windows user therefore never share a credential variable.

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

Since 2026-10-26 a row also carries the Issue's `repository` and `number` and
`issue_assignee_names` (profile name, else login, parallel to the logins). The
weekly report keys a `ReportItem` by its GitHub Issue (`ReportKey`: `#123`, or
`owner/repo#123` outside the board's main repository; `GTM-n` still loads) and
carries `repository`, `number`, an optional `jira_key` and `assignee_source`
(`issue`, `project_field` for the `SDE Assignee` fallback, or `none`).
`SheetState` and `WeeklyReportPlan` carry `target_sheet`, the week's own sheet
by default (`WeeklyReportSettings.sheet_target`); None means the scratch sheet.

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
  - A person changes a value with a correction note: see "BI card model: editing". `POST /api/bi/cards/<id>/field` is gone (2026-11-04, 404 `route_unknown`).
  - `GET /api/bi/cards/<id>/history?dataset=` → `{"history": [{"field", "old", "new",
    "source": {"kind", "ref"}, "at", "by", "reason"}]}`.
  - Unknown dataset (2026-10-24): `GET /api/bi/cards`, `cards/<id>`, `cards/<id>/history`,
    `dashboard` and `schema` (with `dataset`) for a name that is neither an own dataset nor a
    subscribed `<ns>/<name>` answer 404 `{"ok": false, "code": "dataset_unknown", "message"}`,
    as `bi__query` does. `demo` (named or by default) before anything is loaded still reads as an
    empty dataset (200), and `GET /api/bi/schema` without `dataset` is the shipped schema.
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
  `bi.schema/` prefix is reserved, except for compatible local versions: see "BI schema drafts and dataset upgrade"), `version` (`MAJOR.MINOR.PATCH`), `title`, `types` (1–50). Each
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
  `bi.sqlite`, chosen at creation; since 2026-10-27 it changes only through a dataset upgrade to another
  version of the same schema id ("BI schema drafts and dataset upgrade"). A dataset without the row (created before
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

## BI ingest runs (BI ingest phase 1, owner 2026-10-27)

Design: `docs/phases/BI_INGEST.md` §4 and §8. Code: `src/capabilities/bi_cards/staging.py` (sources,
runs, candidates), `src/capabilities/bi_cards/runs.py` (rule-path run, review, commit), `store.py`
(`commit_run`, evidence, proposals), routes in `src/host_runtime/bi_cards_api.py`. Tests:
`tests/test_bi_ingest_runs.py`. Additive: the Case A `/api/bi/import/*` routes are unchanged.

- **Staging store** `<workspace>/bi/<dataset>/staging.sqlite`, created by the first source or run.
  Trial, extraction and review write only here and to `<dataset>/sources/`; `bi.sqlite` is written only
  by commit (and by the existing Case A routes and edits). A subscribed dataset refuses every write
  (409 `dataset_read_only`).
- **Sources.** `POST /api/bi/sources {"dataset", "name", "text" | "content_base64", "media_type":
  str | null, "classification": "INTERNAL" (default) | "UNCLASSIFIED" | "CONFIDENTIAL" | "RESTRICTED"}`
  → `{"ok": true, "source": {"id", "name", "sha256", "media_type", "size", "origin": "upload",
  "classification", "at", "by", "parse": "table" | "text" | "unsupported"}}`. The bytes are kept at
  `<dataset>/sources/<sha256><ext>`; the same bytes are stored once (the same record is returned with
  `"already": true`). `name` is a file name without folders (1–200 characters). Errors: 400
  `source_missing`, `source_name_invalid`, `source_base64_invalid`, `classification_invalid`.
  `GET /api/bi/sources?dataset=` → `{"sources": [...]}` newest first.
- **Runs.** `POST /api/bi/runs {"dataset", "kind": "trial" | "ingest", "source_id", "entity_type":
  str | null, "mapping": obj | null}` → `{"ok": true, "run": <run>}`. Phase 1 runs the rule path on a
  CSV/TSV source synchronously; the run ends in `review`. A source that is not a table is 400
  `source_not_table`; an unknown source 404 `source_unknown`. `<run>` = `{"id", "kind", "status":
  "review" | "committed" | "cancelled" | "failed", "method_ref": null, "schema_ref", "model": null,
  "source_ids", "by", "at", "finished", "summary": {"candidates", "create", "update", "skip",
  "accepted", "rejected", "pending", "errors", "warnings"}, "error": null, "commit": null |
  {"import_id", "created", "updated", "unchanged", "proposals", "at", "by"}}`.
  `GET /api/bi/runs?dataset=` → `{"runs": [<run>...]}` newest first (at most 100).
  `GET /api/bi/runs/<id>?dataset=` → `{"run": <run>, "candidates": [<candidate>...]}`; unknown 404
  `run_unknown`.
- **Candidate** = `{"id", "entity_type", "canonical_key", "name", "match": "new" | "existing" |
  "ambiguous", "match_ids": [card id], "action": "create" | "update" | "unchanged" | "skip", "review":
  "pending" | "accepted" | "rejected", "base_version": int | null, "fields": [{"field", "value",
  "basis": "fact" | "inference" | "unknown" | "human", "evidence": [{"source_id", "locator": {"row",
  "column"} | {"line_start", "line_end"} | ..., "excerpt"}], "current": value | null, "change": "add"
  | "change" | "same" | "human_kept"}], "errors": [{"code", "message", "field": str | null}],
  "warnings": [{"code", "message"}], "edits": [{"field", "old", "new", "by", "at"}]}`. Error codes:
  `required_missing` (a new card without a required field), `name_missing`, `match_unresolved` (an
  `ambiguous` candidate with no choice). `match: "ambiguous"` = no card with the same key, but cards of
  the type whose key matches ignoring spaces, punctuation and case. Locators come from the parser,
  never from a model. A rule-path field is `basis: "fact"` with its CSV cell as excerpt.
- **Review.** `POST /api/bi/runs/<id>/candidates/<cid> {"dataset", "review": "accepted" | "rejected"
  | "pending" | null, "fields": {name: value} | null, "match": {"action": "create" | "update" |
  "skip", "card_id": str | null} | null}` → `{"ok": true, "candidate": <candidate>, "run": <run>}`.
  An edited field is normalised as a card edit (`value_invalid` on a bad value), becomes `basis:
  "human"`, and is recorded in `edits`. Accepting a candidate with errors is 400 `candidate_invalid`
  (with `errors`). A run not in `review` is 409 `run_closed`.
- **Recheck.** `POST /api/bi/runs/<id>/recheck {"dataset"}` recomputes match, `base_version`,
  `current`, `change` and errors of every candidate against the store now (reviews and edits kept;
  a candidate whose diff changed goes back to `pending`) → `{"ok": true, "run", "candidates",
  "changed": [cid]}`.
- **Commit.** `POST /api/bi/runs/<id>/commit {"dataset"}` writes the accepted candidates whose action
  is `create` or `update`, in one SQLite transaction, as one import (`imports.run_id` = the run id)
  → `{"ok": true, "run": <run>, "import_id", "applied": {"created", "updated", "unchanged",
  "proposals"}, "skipped": int, "pending": int, "index": {"status": "not_applicable", "message":
  "BI 卡片寫入後即可查詢，沒有額外索引"}}` (since BI vault V3 `index` is the search index state, see "BI
  search index"). Before writing, each matched card's `version` must equal
  the candidate's `base_version`, and a `create` candidate's key must still be free; otherwise nothing
  is written: 409 `cards_changed` with `"cards": [{"candidate_id", "card_id", "name", "expected",
  "current"}]` (recheck, review again, commit again). Refusals: 409 `run_trial` (a trial run), 400
  `candidates_invalid` (an accepted candidate has errors), 400 `nothing_accepted`. A run already
  committed answers 200 with its first result and `"already": true` and writes nothing (also when the
  reply was lost after the write: `imports.run_id` is checked). Written fields have `kind: "import"`
  and `ref: "run:<run id>/<candidate id>"`; a person's value is kept and becomes a proposal as in
  Case A. Undo is `POST /api/bi/import/undo` with the `import_id`.
  `POST /api/bi/runs/<id>/cancel {"dataset"}` → `{"ok": true, "run"}` (status `cancelled`; 409
  `run_closed` after commit).
- **Evidence** (`bi.sqlite` table `evidence`: card, field, run, source id and name, locator,
  excerpt, basis, at). `GET /api/bi/cards/<id>` adds `"evidence": [{"field", "run_id", "source_id",
  "source_name", "locator", "excerpt", "basis", "at"}]` (newest first) and an `"id"` on each proposal.
- **Proposals.** `POST /api/bi/cards/<id>/proposals/<pid> {"dataset", "action": "accept" | "reject",
  "base_version", "reason"}` → `{"ok": true, "version"}`. Accept writes the proposed value as the
  person's (`stale_edit` 409 when the card moved on, `reason_required` for a
  `judgement` field) and closes the field's pending proposals; reject marks only that proposal
  `rejected` and does not change the card version. Unknown or closed: 404 `proposal_unknown`.

## BI schema drafts and dataset upgrade (BI ingest phase 2, owner 2026-10-27)

Design: `docs/phases/BI_INGEST.md` §5. Code: `src/capabilities/bi_cards/schema_versions.py`, `catalog.py`
(`bi_problems`, `migrations`), `store.py` (`upgrade_schema`, `change_marker`), routes in
`src/host_runtime/bi_cards_api.py`. Tests: `tests/test_bi_schema_versions.py`. This replaces "a dataset's
schema is chosen at creation and never changed" (owner 2026-10-27): a dataset may move to another version of
**the same schema id**; a different id is still a new dataset.

- **Local BI versions.** A `bi.schema/*` id now installs only as `bi.schema/v1.1` with a version newer than
  `1.1.0` that keeps every shipped type, its naming, every shipped field with the same `kind`, `class` and
  `link_to`, every shipped enum value and every shipped domain; it may add types, fields, enum values,
  aliases and domains. It may use the shipped forms `kind: "virtual"` and a link without `link_to`. Anything
  else is 400 `schema_bi_not_compatible` with `errors` (each missing or changed item). It is a BI schema:
  Dashboard, `bi__query`, and sharing (a subscriber installs it through the same check).
- **`migrations`** (optional top-level key of any schema file): `{"renames": {"<Type>.<old field>": "<new
  field>"}}`; the new field must be in the type, the old one must not.
- **Drafts.** `<workspace>/bi/schema-drafts/<12 hex>/draft.json` and `rev-<n>.json` (immutable).
  - `POST /api/bi/schema-drafts {"base": "<id>@<version>" | "<id>", "title"}` → `{"ok": true, <draft view>}`;
    revision 1 is the base document with `version` set to the next minor version above every known version.
  - `<draft view>` = `{"draft": {"id", "title", "base_ref", "schema_id", "by", "at", "revisions": [{"rev",
    "at", "by", "note", "source": "base" | "edit" | "ai" | "revert", "valid", "copied_from"?}], "published":
    [{"rev", "ref", "at", "by"}]}, "revision", "document", "errors": [{"path", "message"}], "diff": [<change>]}`
    (`diff` is against the base).
  - `<change>` = `{"type", "field": str | null, "change": "type_added" | "type_removed" | "naming" | "label" |
    "field_added" | "field_removed" | "renamed" | "kind" | "class" | "required" | "enum_added" |
    "enum_removed" | "link_to" | "aliases", "detail", "breaking": bool}`. Breaking: `type_removed`,
    `naming`, `field_removed`, `kind`, `enum_removed`, `link_to`.
  - `GET /api/bi/schema-drafts` → `{"drafts": [{"id", "title", "base_ref", "schema_id", "revisions", "valid",
    "updated", "published"}]}` newest first. `GET /api/bi/schema-drafts/<id>` (latest) and
    `GET /api/bi/schema-drafts/<id>/revisions/<n>` → `<draft view>`. `GET /api/bi/schema-drafts/<id>/diff?
    from=<n> | base&to=<n>` → `{"diff": [...]}`.
  - `POST /api/bi/schema-drafts/<id>/revisions {"document" | "json_text", "note", "source": "edit" | "ai"}` →
    a new revision (`<draft view>`); an invalid document is saved with its `errors`. Refusals: 400
    `schema_json_invalid`, `document_missing`, `schema_too_large`, `schema_id_changed` (a draft keeps its id).
  - `POST /api/bi/schema-drafts/<id>/revert {"rev"}` → a new revision copying `rev` (`copied_from`).
  - `POST /api/bi/schema-drafts/<id>/publish {"rev": n | null}` (latest by default) → `{"ok": true, "id",
    "version", "ref", "already", "draft"}` through `catalog.install` (same refusals: `schema_invalid`,
    `schema_bi_not_compatible`, 409 `schema_version_exists`), plus 409 `schema_version_not_newer`.
  - Unknown: 404 `draft_unknown`, `revision_unknown`.
- **Dataset upgrade.**
  - `POST /api/bi/datasets/<name>/schema/preview {"to"}` → `{"ok": true, "from", "to", "diff",
    "types": [{"type", "cards", "hidden": [{"field", "cards"}], "renamed": [{"from", "to", "cards"}],
    "retired": [{"card_id", "name", "field", "value"}], "required_missing": [{"field", "cards"}]}],
    "blocked": [{"code": "type_removed" | "naming_changed" | "kind_changed", "message"}], "totals":
    {"hidden", "retired", "renamed", "required_missing"}, "preview_token"}`. Writes nothing.
  - `POST /api/bi/datasets/<name>/schema/apply {"to", "preview_token"}` → `{"ok": true, "from", "to",
    "moved", ...the preview's impact}`. One transaction. 409 `preview_stale` when the cards changed since the
    preview (or the binding did); 409 `schema_upgrade_breaking` with `blocked` when anything is blocked.
  - Refusals of both: 400 `schema_id_different`, `schema_same`; 404 `schema_unknown`, `dataset_unknown`;
    409 `dataset_read_only`.
  - Effects: `meta.schema` becomes `to`; `meta.schema_history` gains `{"from", "to", "by", "at", "moved",
    ...totals}`. A declared rename moves the value with its source unchanged, adds two history rows
    (`kind: "migration"`, `ref: "schema:<to>"`) and bumps the card version; a card that already has the new
    field keeps both. Nothing else is written: a removed field's value stays, a retired enum value stays.
  - A value whose field the current schema lacks is **retired**: `GET /api/bi/cards/<id>` shows it with
    `"retired": true` (every field entry now has `retired`), and it is not searched (`/api/bi/cards?q=`,
    `bi__query`) or shared (snapshots leave it out). Moving back to a version that has the field shows it
    again.
  - A run made before the upgrade cannot be reviewed, rechecked or committed: 409 `schema_changed` (run
    again).
  - **Readable and safe (acceptance F6, 2026-11-06).** The preview adds `"additive": bool`: in a vault, only
    additions, which become `schema_change:` units and take no version. The apply adds `"schema": <schema
    state>`. A vault refuses both with 400 `schema_drops_additions` when `to` lacks an addition its units hold,
    unless `to` was published from a draft whose `base_ref` is the vault's current ref (a person's own new
    version). A plain dataset may still move back.
  - `<schema state>` = `{"ref", "label", "additions": [str], "upgrades": [{"ref", "label"}]}`. `label` reads
    `5.0` or `5.0 加 N 項新增`, never the digest; `upgrades` are the versions newer than the base that the
    dataset may move to. `GET /api/bi/schema?dataset=` adds `label`, `additions` and `upgrades`.
  - A draft view adds `"additive": bool` (its diff from the base is only additions).
- **建議 schema (acceptance F5, `BI_PAGE_SIMPLE.md` S2).** `src/capabilities/bi_cards/schema_suggest.py`.
  The schema-fit question alone, over chosen sources, on a press; writes no card. The latest per dataset is
  kept in `<dataset dir>/schema-suggest.json`.
  - `POST /api/bi/schema-suggest {"dataset", "source_ids": [...], "only_new": bool}` → `{"ok": true,
    "suggestion": <suggestion>}` with `status: "running"`; the model is asked in the background. `only_new`
    leaves out sources an ingest run read. At most 10 sources (`left_out` counts the rest). Refusals: 400
    `suggest_no_sources`, `model_unavailable`, `classification_not_approved`; 409 `suggest_running`,
    `dataset_read_only`.
  - `GET /api/bi/schema-suggest?dataset=` → `{"suggestion": <suggestion> | null}`.
  - `<suggestion>` = `{"id", "status": "running" | "done" | "failed", "at", "by", "schema", "model",
    "sources": [{"id", "name"}], "left_out", "done", "seconds", "answers": {"asked", "reused",
    "input_tokens", "output_tokens"}, "items": [<row>], "fits", "unquoted", "failures": [{"source", "lines",
    "message"}]}`. `fits` counts items that fit the schema as it is; `unquoted` counts items whose quote is not
    in the source, which are never rows. No rows on `done` is the answer 「不用改」.
  - `<row>` = `{"id", "kind": "extend_schema" | "dictionary_change" | "propose_type" |
    "needs_clarification", "what", "proposal", "summary", "reason", "questions", "quote", "locator",
    "source_id", "source", "places", "applies": bool, "status": "proposed" | "applied" | "rejected"}`. A type
    the schema has, or a field it has, is `needs_clarification` with a question (`schema_fit`). `applies`: a
    new field, or a new allowed value with no `maps_to`, that leaves a valid schema.
  - `POST /api/bi/schema-suggest/apply {"dataset", "id", "row"}` → `{"ok": true, "suggestion", "schema":
    <schema state>}`. A vault only: a draft from the current schema with the row, publish, preview and apply;
    the vault turns it into units on the version; the draft is removed. Nothing is committed. Refusals: 400
    `suggest_apply_vault_only`, `suggest_not_direct`, `suggest_invalid`, `suggest_field_exists`,
    `suggest_not_enum`, `suggest_value_exists`, `suggest_row_unknown`; 409 `suggest_stale`,
    `suggest_row_decided`.
  - `POST /api/bi/schema-suggest/reject {"dataset", "id", "row", "reason"}` → `{"ok": true, "suggestion"}`.

## BI schema 2.0, new kinds and widening (BI vault V9, owner 2026-10-29)

Design: `docs/phases/BI_VAULT.md` §12; decision `docs/DECISIONS.md` 2026-10-29 "BI vault V9". Code:
`src/capabilities/bi_cards/schema.py` (`shipped`, `WIDENINGS`, `widen_value`, `type_in_filename`, float and
allowed-list normalising), `catalog.py`, `schema_versions.py` (`widened`, `_widenings`), `store.py`
(`upgrade_schema(widenings=...)`), `scripts/build_bi_schema_v2.py`. Tests: `tests/test_bi_schema_v2.py`.
Additive to "BI cards API and capability" and "BI schema drafts and dataset upgrade".

- **Two shipped versions.** `bi.schema/v1.1@1.1.0` (schema v4, unchanged) and `bi.schema/v1.1@2.0.0`
  (`bi_schema_v2.json`, generated from the manager's schema v8 in `tests/fixtures/bi_schema_v8/`): 21 types
  (adds WinLoss, RoadmapRequest, Pitch, DemoScript, Battlecard, Contact, VisitLog, SupplyLink, RevenueFact),
  domains + mobile, aerospace; Node `domain` is a list; `segment` (CustomerProduct, Ecosystem, Account,
  SupplyLink) allows aerospace's `space`, `gateway`, `ut`, `launch`, `mro` and the market chart's 11 segment ids
  (`cell-phone` … `osat`, the vault's application folders), their labels as `enum_aliases`. `GET /api/bi/schemas` lists both with `source:
  "shipped"`. A bare `bi.schema/v1.1` resolves to the newest version (2.0.0, or a newer local one); a dataset
  with no binding stays `1.1.0`. Local versions are still checked against `1.1.0`. A schema file with a
  shipped `<id>@<version>` installs only when its content is the shipped one (`already: true`), else 409
  `schema_version_exists`. Snapshots of a 2.0.0 dataset carry `source: "shipped"`; a subscriber whose AEP
  ships 2.0.0 uses it as is.
- **`float` kind.** A plain number, thousands separators and one trailing `%` allowed (`11,586`, `59%`);
  `約20`, ranges (`75–80%`) and units are `type_mismatch` and the value stays empty. `range` is allowed on
  `int` and `float` (`[min, max]`, numbers).
- **Allowed values on a list.** A `list` field may have `enum`: each part matches like an enum value (also
  through `enum_aliases`); unknown parts are dropped with `type_mismatch`. A field edit or a candidate edit
  with an unknown part is 400 `value_invalid`.
- **Widening.** `enum → list`, `str → list`, `link → linklist`, `int → float` are not breaking: `bi_problems`
  accepts them (a list without `enum` may replace an enum), a diff `<change>` is `"change": "widened"` with
  `breaking: false`, and a dataset upgrade is not blocked. The preview's `types[]` gain `"widened": [{"field",
  "from", "to", "cards"}]` and `totals` gains `"widened"`. Apply turns each stored value into its list (or
  decimal) form with a `migration` history row (`ref: "schema:<to>"`) and a card version bump, counted in
  `moved`; in a vault this is captured like any write, so every PC gets it. Any other kind change is still
  `kind` / `kind_changed`.
- **Type from the file name.** An import preview without `entity_type` first takes the type a file is named
  after (type name or the v8 `code_key`, loosely: `11_supply_link.csv` → SupplyLink; the longest match
  wins), then guesses from the headers as before.

## BI rule path: recipes and multi-table sources (BI ingest phase 3, owner 2026-10-27)

Design: `docs/phases/BI_INGEST.md` §6 and §11 item 11; engine design `docs/phases/BI_CASE_B.md` §3–§5
(except: a role conflict is decided by the person in review, the earlier pass is the default). Code:
`src/capabilities/bi_cards/readers.py`, `recipes.py`, `runs.py`, `staging.py` (tables `recipes`,
`run_layouts`), routes in `src/host_runtime/bi_cards_api.py`. Tests: `tests/test_bi_rule_path.py`. Additive
to "BI ingest runs": a run without a recipe behaves exactly as in phase 1.

- **Readers.** A source is read into tables `{"index", "title", "columns", "rows": [{"row", "cells"}],
  "locator"}`, numbered from 0 in file order:
  - Markdown (`.md`, `.markdown`): pipe tables whose second line is a separator; `title` = the nearest heading
    above (the file name if none); `row` = the line number; cells lose link targets, bold and code marks, and
    `<br>` becomes 「; 」.
  - Excel (`.xlsx`, `.xlsm`; `openpyxl`, read-only, cached values): one sheet = one table, `title` = the sheet
    name, header = the first non-empty row, `row` = the sheet row; dates become `YYYY-MM-DD`, whole numbers
    lose `.0`. Sources upload as `content_base64`; `.xlsx` sources report `parse: "table"`.
  - CSV/TSV: one table, `title` = the file name, `row` = the record number (header = 1).
  - Anything else with a recipe: 400 `file_type_unsupported`.
- **Recipe** `aep.bi.recipe/v1` (JSON object): `schema_version` (optional, must be `aep.bi.recipe/v1`),
  `name` (1–80 characters), optional `description`, `dataset_schema` (`<id>` or `<id>@<version>`; the id must
  be the dataset's), `name_aliases` ({alias: card name}), `passes` (1–50) of `{"id"
  ([A-Za-z0-9_-]{1,40}, unique), "tables" (default `all`), "entity_type" (a type of the dataset's schema),
  "mapping", "description"?}`.
  - `tables`: `all`; indexes and ranges `0,2-3` (an index the source lacks is a pass warning
    `table_missing`); `has:colA|colB` (any listed column); `sheet:<name>` (the table whose title is `name`).
    A pass that selects nothing has the warning `pass_no_table`.
  - `mapping` keys: Case A's `columns` ({header: field}), `entity_type` (must equal the pass's),
    `enum_aliases`, `defaults` (new cards only), `skip_rows` ([{`column`, `contains`}]) and the advanced keys
    `text_replace` ([{`column`, `pairs`: [[regex, replacement]], `into`?}]), `explode` ([{`column`, `into`,
    `strip_after`?, `set`?}]), `exclude_names` ([name]), `derive` ({target: {`from`: [column], `map`: {regex:
    value}, `all`?}}), `compose` ({target: template with `{column}`}), `name_aliases` (merged over the
    recipe's for this pass).
  - Checks, at save and at every run: an unknown key at any level is 400 `mapping_key_unknown` with
    `pass_id` (null at the top level) and `key` (e.g. `mapping.explod`); everything else is 400
    `recipe_invalid` with `pass_id` and `key`: a missing or repeated pass id, an unknown type, a `columns` or
    `defaults` field the type lacks, a bad selector, a wrong shape, a regex longer than 300 characters or
    that does not compile.
- **Transforms** (per pass, upstream `bi_ingest.py` order): `skip_rows` → `text_replace` → `explode` →
  `exclude_names` → `derive` → `compose`. `explode` splits on `; ； , ， 、 |` and newline outside brackets;
  a trailing `(…)` becomes `__ticker` (four digits) or `__note`; the part is alias-resolved. `derive` fills an
  empty target from the first matching pattern (all, joined with 「、」, when `all`). `compose` drops a line
  whose placeholders are all empty. Then Case A maps and normalises the rows (`columns`, aliases,
  `enum_aliases`, `defaults`); transform targets that are field names map to that field, `__ticker` maps to
  `ticker` when the type has it, other `__` columns are not mapped. `name_aliases` resolve `name`,
  `product_name` and every link target (after dropping a trailing `(…)`, as upstream) before the card key
  is built. Link targets made by any pass of the recipe count as known.
- **Recipes per dataset** (`staging.sqlite` table `recipes`: id, name, version, body, by, at):
  - `POST /api/bi/recipes {"dataset", "recipe"}` → `{"ok": true, "recipe": {"id", "name", "version",
    "recipe" (the checked body), "by", "at", "already"}}`. A new name gets a 12-hex id and version 1; the same
    name gets the next version; the same body as the latest version saves nothing (`already: true`). A
    subscribed dataset: 409 `dataset_read_only`.
  - `GET /api/bi/recipes?dataset=` → `{"recipes": [<latest version of each>]}` newest first.
  - `GET /api/bi/recipes/<id>?dataset=` → `{"recipe": <latest>, "versions": [{"version", "by", "at"}]}`
    newest first; unknown 404 `recipe_unknown`.
- **Runs with a recipe.** `POST /api/bi/runs` also accepts `"recipe": {...}` (inline) or `"recipe_id"` with an
  optional `"recipe_version"` (default: latest; unknown 404 `recipe_unknown` / `recipe_version_unknown`). A
  saved recipe is checked again against the dataset's schema when run. Without either, a CSV/TSV runs as in
  phase 1, a Markdown source stays 400 `source_not_table`, and an Excel source is 400 `recipe_required`.
  - `<run>.method_ref` = `recipe:<id>@<version>` or `recipe:inline`; the run view of a recipe run adds
    `"tables": [{"index", "title", "columns", "rows" (count), "pass_id" (first pass reading it) | null,
    "pass_ids"}]`, `"passes": [{"id", "entity_type", "tables", "rows_read", "rows_out", "columns" (Case A
    column mapping), "warnings", "counts" (the run summary over its candidates, as reviewed now)}]` and
    `"warnings"` (run level: `table_unused` with `table`). Pass warnings: `exploded_row` (`table`, `row`,
    `count`, one per source row split into several), `table_missing`, `pass_no_table`.
  - Candidates add `"pass_id"`. Evidence locators: Markdown `{"table", "line", "column"}`, Excel `{"sheet",
    "row", "column"}`, CSV `{"table", "row", "column"}`; `column` names the source column(s) the value came
    from (several joined with 「、」 for `derive` and `compose`), and the excerpt is their cell text (at most
    500 characters). A default value has no evidence (`basis: "unknown"`).
  - Rows naming the same `(entity_type, canonical_key)`, in one pass or several, are one candidate (its
    `pass_id` is the first): lists are unioned, an empty field is filled, `body` texts are joined, every row's
    cell is kept as evidence, and a different scalar keeps the first value with the warning
    `value_conflict`.
  - Candidate warnings added: `alias_merged` (a name resolved through `name_aliases`, on the merged
    candidate), `role_conflict` (the same resolved name made as another type by an earlier pass: the later
    candidate gets the warning and the default choice skip, `action: "skip"`, `review: "pending"`; the person
    may still choose `match: {"action": "create"}`).
  - Review, recheck, commit, cancel and undo are unchanged; one commit covers every pass, and undoing its
    `import_id` undoes every pass.

## BI AI path: extraction runs (BI ingest phase 4, owner 2026-10-27)

Design: `docs/phases/BI_INGEST.md` §7. Code: `src/capabilities/bi_cards/extract.py` (chunks, request, answer
checks, quote location), `ai_runs.py` (runs, background job, retry), `runs.py` (`evaluate` adds
`value_errors`), routes in `src/host_runtime/bi_cards_api.py` (`web_ai_runtime`). Tests:
`tests/test_bi_extract.py`, `tests/test_bi_ai_runs.py` (scripted model; no provider is called).

- **When.** `POST /api/bi/runs` on a source whose `parse` is `text` (`.txt`, `.md`) and with no `recipe` /
  `recipe_id` starts an AI run (before phase 4 this was 400 `source_not_table`). Extra body keys:
  `instructions` (string, at most 8000 characters; empty = the shipped `DEFAULT_INSTRUCTIONS`, the owner
  proposal §4 card rules), `types` (card type names; default Signal, Technology, Application). Refusals: 400
  `model_unavailable` (no model in Settings; nothing is started; the rule path still works), 400
  `types_invalid`, `instructions_too_long`, `source_not_text`.
- **Data class.** A source reaches the model (AI run, Session A or B excerpt) only when its `classification`
  is in the host's `models.data_approval.approved_classes`; otherwise 400 `classification_not_approved` and
  nothing is sent (added 2026-10-28).
- **The model.** The Knowledge query model and alias when a wiki Knowledge asset is bound; otherwise the host's routing
  client and alias, the same `ApprovedModelClient`, never an unwrapped client (owner 2026-11-03; `web_ai_runtime`). No
  routed model: `model_unavailable`. One call per chunk,
  `structured_output` with output contract `aep.bi.extract.v1`, no tools. The system message holds the rules,
  the schema's types and fields and the instructions; the chunk is in a user message between
  `DATA_FENCE` / `DATA_END` and is never in the system message. Known card names of the types in scope are
  offered for matching. An unusable answer is retried up to 3 times with its problems; then the chunk fails
  `model_output_invalid`; a provider failure is `model_unavailable` for that chunk.
- **Chunks.** Along headings (a heading starts a chunk once a quarter of the limit is used), blank lines and
  whole tables, at most about 6000 characters, never inside a line; line numbers start at 1.
- **Answer checks.** Unknown types (`model_type_unknown`, run warning) and fields (`model_field_unknown`,
  candidate warning) are dropped. Values are normalised as an import cell; one that does not fit is a
  candidate error `value_invalid` with its `field` until the person edits that field. `basis: "fact"` needs a
  `quote` found in the chunk (whitespace and case ignored); its evidence locator `{line_start, line_end}` is
  computed from where it is found; a quote not found makes the value `basis: "unknown"` with warning
  `evidence_not_found`. `basis: "inference"` carries the model's reason as warning `inference`. An Opportunity
  without `account` and `applications` as facts gets `opportunity_unsupported` and `review: "rejected"`.
  Proposals of one card from several chunks merge (lists unioned, evidence kept from each; a different single
  value is `value_conflict`, the first kept).
- **Run.** `status`: `extracting` (background task `bi-ingest` in the task log, so `/api/activity` shows it)
  → `review`, `partial` (some chunks failed; candidates can be reviewed and committed) or `failed` (all
  failed). `method_ref`: `llm:default` or `llm:inline`; `model`: the alias. The run view adds `progress`
  `{done, chunks}`, `failures` `[{chunk, line_start, line_end, code, message, retryable}]`, `warnings`,
  `types`. Review, recheck and commit accept `review` and `partial`; cancel during `extracting` keeps the run
  `cancelled` when the job ends.
- **Retry.** `POST /api/bi/runs/<id>/retry {"dataset"}` on a `partial` or `failed` AI run re-runs only the
  failed chunks in the background; new candidates merge into the stored ones (reviews kept). 409
  `run_closed` when there is nothing to retry; 400 `model_unavailable`.

## BI method sessions (Session B, phase 5)

Design: `docs/phases/BI_INGEST.md` §9.2, §11 item 9. Code: `src/capabilities/bi_cards/methods.py` (methods,
method runs, comparison, Session B), `sessions.py` (durable sessions, one model call per turn, excerpts),
`staging.py` (table `sessions`), `runs.py` / `ai_runs.py` (`method_ref`, `checks`), routes in
`src/host_runtime/bi_cards_api.py`; UI in step 3 of 「建立與匯入」. Tests: `tests/test_bi_methods.py`
(scripted model), `tests/test_bi_sessions_ui.py`. Additive: runs without `method_id` are unchanged.

- **Method** `aep.bi.method/v1`, one folder per method `<workspace>/bi/<dataset>/methods/<12 hex>/` with
  `method.json` (`{"id", "name", "by", "at", "revisions": [{"rev", "at", "by", "note", "source": "base" |
  "edit" | "ai" | "revert", "schema_ref", "copied_from"?}], "rechecks": [{"rev", "schema_ref", "run_id",
  "at"}]}`) and immutable `rev-<n>.json`: `{"format": "aep.bi.method/v1", "name" (1–80), "description"?,
  "schema_ref" (the dataset schema the revision was checked against), "mode": "rules" | "llm", "types",
  "instructions" (llm: at most 8000 characters; empty = the shipped `DEFAULT_INSTRUCTIONS`), "recipe"
  (rules: an `aep.bi.recipe/v1` body, checked as in "BI rule path"; llm: null), "checks": [{"entity_type",
  "require": [field], "message"?}]}`. `types` default: the shipped three (llm) or the recipe's pass types
  (rules). Any other key, an unknown type or field, or a bad recipe is 400 `method_invalid` with `key` (a
  recipe's own refusals keep their codes). A subscribed dataset refuses every write (409
  `dataset_read_only`).
- **Routes.** `POST /api/bi/methods {"dataset", "method"}` → `{"ok": true, <method view>}` (revision 1).
  `POST /api/bi/methods/<id>/revisions {"dataset", "method", "note"}` → a new revision. `POST
  /api/bi/methods/<id>/revert {"dataset", "rev"}` → a new revision copying `rev` as it was, its
  `schema_ref` included (`copied_from`). `GET /api/bi/methods/<id>?dataset=&rev=` → `<method view>` =
  `{"method": <method.json>, "revision", "document", "diff": [{"key", "before", "after"}] (against the
  previous revision), "status": {"schema_ref" (the dataset's now), "revision_schema_ref", "schema_changed",
  "rechecked": <recheck> | null, "message"}}`. `GET /api/bi/methods?dataset=` → `{"methods": [{"id",
  "name", "mode", "revisions", "updated", "status"}]}` newest first. Unknown: 404 `method_unknown`,
  `revision_unknown`.
- **Runs with a method.** `POST /api/bi/runs {"dataset", "kind", "source_id", "method_id", "method_rev"?}`
  runs the revision (latest by default): `rules` through the recipe (as an inline recipe), `llm` through the
  AI path with its instructions and types. `<run>.method_ref` = `method:<id>@<rev>`. A `checks` rule gives
  every candidate of its type that lacks a required field the error `method_check` on that field (kept until
  the person fills the field). Trial runs stay uncommittable (409 `run_trial`).
- **Schema re-check.** A revision whose `schema_ref` differs from the dataset's schema is `schema_changed`
  (「schema 已更新，請重新試跑確認」) unless a trial run of that revision under the current schema has reached
  `review`; such a run is recorded in `rechecks` when the method is next read or run. An ingest run with a
  `schema_changed` revision is 409 `schema_changed`; a trial run is allowed. A revision saved after the
  upgrade is checked against the new schema and is not flagged.
- **Compare.** `GET /api/bi/runs/compare?dataset=&left=<run>&right=<run>` → `{"left": <run>, "right": <run>,
  "added": [<brief>], "removed": [<brief>], "changed": [{"entity_type", "name", "left_id", "right_id",
  "fields": [{"field", "change": "added" | "removed" | "value" | "basis", "before": {"value", "basis"} |
  null, "after": ..., "evidence"}], "warnings_added": [code], "warnings_removed": [code]}], "same": int,
  "counts": {"left" | "right": {"candidates", "warnings" (candidate and run warnings), "inferences" (fields
  with basis inference), "errors"}}}`. Candidates pair by `(entity_type, canonical_key or name)` ignoring
  spaces, punctuation and case. `<brief>` = `{"id", "entity_type", "name", "canonical_key", "fields":
  [{"field", "value", "basis"}], "warnings": [code], "errors", "inferences"}`. Runs of different sources:
  400 `compare_sources_differ`; unknown 404 `run_unknown`. Writes nothing.
- **Sessions** (`staging.sqlite` table `sessions(id, kind, target_ref, body, model, by, at, updated)`; the
  turns survive a restart). `POST /api/bi/sessions {"dataset", "kind": "method", "target": <method id>}` →
  `{"ok": true, "session": <session>}`; `<session>` = `{"id", "kind", "target_ref": "method:<id>", "model",
  "by", "at", "updated", "goal", "source_ids", "turns": [<turn>]}`. `GET /api/bi/sessions?dataset=&target=`
  → `{"sessions"}` newest first; `GET /api/bi/sessions/<id>?dataset=` → `{"session"}` (404
  `session_unknown`). `GET /api/bi/ai` → `{"available", "model": alias | null, "message"}`.
- **A turn.** `POST /api/bi/sessions/<id>/turns {"dataset", "message" (1–4000), "source_ids": [id]
  (at most 5), "run_ids"?: [run id]}` → `{"ok": true, "session"}` with two new turns: `{"role": "user",
  "text", "at", "by"}` and `{"role": "assistant", "at", "model", "attempts", "problems", "sent": {"model",
  "sources": [{"id", "name", "classification", "chars", "of", "truncated"}], "excerpt_chars", "cap": 12000,
  "runs": [run id], "method_rev"}, "suggestion": <suggestion> | null, "error": {"code":
  "model_unavailable" | "model_output_invalid", "message"} | null, "applied": null}`. No model: 400
  `model_unavailable` and nothing is stored. One `ModelClient.generate` per attempt, `structured_output`,
  output contract `aep.bi.method_suggestion.v1`, **no tools**; the system message holds only the rules; the
  method revision, the schema's types, the excerpts (the cap shared by the chosen sources) and the last two
  trial runs of the method (or `run_ids`; candidates with values, bases and warnings, at most 4000
  characters) go in a user message, excerpts and run text between `DATA_FENCE` / `DATA_END`. An answer
  that is not an object, lacks `reply`, has `changes` keys other than `instructions`, `types`, `recipe`,
  `mode`, `checks`, or whose changed method fails the method check is asked again with the problems (3
  attempts), then the turn has `error.code` `model_output_invalid`.
- **`<suggestion>`** `aep.bi.method_suggestion/v1` = `{"format", "reply", "changes": {key: complete new
  value}, "reasons": [str], "limits": [str], "needs_engineering": [str] (what a method cannot express,
  never applied or claimed as working), "result": {"base_rev", "diff": [{"key", "before", "after"}]}}`.
- **Apply.** `POST /api/bi/sessions/<id>/apply {"dataset", "turn": <index of the assistant turn>}` →
  `{"ok": true, "session", <method view>}`: the changes on the latest revision, checked, saved as a new
  revision with `source: "ai"`; the turn gets `applied: {"rev", "at", "by"}`. A second apply is 409
  `suggestion_applied`; a turn without a suggestion 404 `turn_unknown`.

## BI schema sessions (Session A, phase 6)

Design: `docs/phases/BI_INGEST.md` §9.1, §11 item 8. Code: `src/capabilities/bi_cards/schema_session.py`
(operations, Session A), `sessions.py` (shared with Session B), `schema_versions.py` (`draft_registry`,
`draft:` refs), `runs.py` (`registry_for`), routes in `src/host_runtime/bi_cards_api.py`; UI in step 2 of
「建立與匯入」. Tests: `tests/test_bi_schema_session.py` (scripted model), `tests/test_bi_sessions_ui.py`.
Additive to "BI schema drafts and dataset upgrade" and "BI method sessions": publishing and the dataset
upgrade are unchanged and stay separate actions.

- **Session.** `POST /api/bi/sessions {"dataset", "kind": "schema", "target": <draft id>}` → `{"ok": true,
  "session"}` with `target_ref` `schema-draft:<draft id>`, kept in the dataset's staging store (the dataset
  whose sources it reads); unknown draft 404 `draft_unknown`. Reading, listing and the session shape are as
  in "BI method sessions".
- **A turn.** `POST /api/bi/sessions/<id>/turns {"dataset", "message", "goal"?: str (at most 1000; kept on
  the session), "source_ids": [id]}` → `{"ok": true, "session"}`. The user message holds the goal, the
  dataset's card count and schema, the draft's latest revision as a compact list of types and fields
  (kind, class, list, required, enum, `link_to`, aliases) and the excerpts between `DATA_FENCE` /
  `DATA_END` (cap 12000 characters shared by the sources; a workbook is sent as its tables). Output
  contract `aep.bi.schema_suggestion.v1`, no tools, 3 attempts. `sent` = `{"model", "sources", "excerpt_chars",
  "cap", "draft_rev", "goal": bool}`. No model: 400 `model_unavailable`, nothing stored.
- **`<suggestion>`** `aep.bi.schema_suggestion/v1` = `{"format", "reply", "verdict": "reuse" | "extend" |
  "new", "reasons", "assumptions", "missing_information", "changes": [<op>], "examples": [{"entity_type",
  "name", "fields"}] (at most 5), "result": {"base_rev", "diff": [<change>] (`schema_versions.diff`, the
  revision → the result), "errors": [{"path", "message"}] (`catalog.validate` of the result), "problems":
  [str] (operations that could not be applied), "valid": bool}}`.
- **`<op>`**, applied in order to a copy of the revision (the stored revision never changes):
  `{"op": "add_type", "type": {...}}` (a new name), `{"op": "add_field", "type", "field": {...}}` (a new
  name), `{"op": "change_field", "type", "field", "set": {...}}` (any field key except `name`), `{"op":
  "add_enum_value", "type", "field", "value"}`, `{"op": "add_alias", "type", "field", "alias"}` (no
  duplicate), `{"op": "rename_field", "type", "field", "to"}` (also writes `migrations.renames["<Type>.<old>"]
  = "<new>"`). At most 40. An answer without `reply` or a valid `verdict`, or with `changes` not a list, is
  asked again and after 3 attempts the turn has `error.code` `model_output_invalid`; an answer whose
  operations do not apply or whose result is invalid is also asked again with the problems, and after the
  last attempt it is kept as the suggestion with `valid: false`.
- **「套用到草稿」.** `POST /api/bi/sessions/<id>/apply {"dataset", "turn"}` → `{"ok": true, "session",
  <draft view>}`: the operations on the draft's latest revision, saved as a new revision with `source:
  "ai"` and the note naming the session and turn. Not valid there: 409 `suggestion_invalid` with `errors`
  and `problems`, nothing written. 409 `suggestion_applied`, 404 `turn_unknown` as in Session B.
- **「用樣本試跑」.** `POST /api/bi/runs {"dataset", "kind": "trial", "source_id", "draft_id", "draft_rev"?
  (latest by default), ...}` runs any path (Case A CSV, recipe, method, AI) with the draft revision's schema,
  not installed: candidates are built and evaluated against it, `<run>.schema_ref` =
  `draft:<draft id>@rev<n>` (AI-path chunks and retries use the same registry). `kind: "ingest"` with a
  draft: 400 `draft_trial_only`; an invalid revision: 400 `draft_invalid` with `errors`. Such a run cannot be
  committed (409 `run_trial`), and review or recheck answer 409 `schema_changed` (its schema is not the
  dataset's). It does not count as a method re-check. Nothing is installed and `bi.sqlite` is not written.

## BI vaults: folder, change files, sync (BI vaults phase V4, 2026-10-28)

> **Superseded 2026-10-30** by "Knowledge repositories: the BI type (R2)" below: the folder is a
> knowledge repository (`repo.json`, `commits/`), not `vault.json` and `changes/`, and a write is staged
> until a person commits and pushes it. Kept as the record of V4.

Design: `docs/phases/BI_VAULT.md` §3, §4; decision `docs/DECISIONS.md` 2026-10-28 "BI vault V4: writes
are captured and replayed". Code: `src/capabilities/bi_cards/vault.py`, hooks in `store.py`
(`vault_of`, `dataset_dir`, `datasets`, `BiStore._db`), routes in `src/host_runtime/bi_vaults_api.py`.
Tests: `tests/test_bi_vault.py` (two or three PCs as separate workspaces with their own copy of the
folder; a test helper plays OneDrive). Backend and API only; the page comes later.

- **A vault is a dataset.** A vault registered on this PC is the dataset `vault-<vault id>` (fits
  `[A-Za-z0-9_-]{1,40}`; vault id `[a-z0-9]+(-[a-z0-9]+)*`, at most 34 characters). Every existing
  `/api/bi/*` route (cards, edits, proposals, sources, runs, review, commit, undo, schema upgrade)
  takes it as `dataset` unchanged. Its local copy is `<workspace>/bi/vaults/<vault id>/` (`bi.sqlite`,
  `staging.sqlite`, sources, `vault_sync.json`); `vaults` is a reserved dataset name and a new plain
  dataset may not start with `vault-` (400 `dataset_invalid`). The registry
  `<workspace>/bi/vaults/registry.json` = `{"vaults": [{"id", "path", "author", "joined"}]}` is per PC.
  Trial runs, candidates, review and Sessions A and B stay local; only writes to `bi.sqlite` are shared.
- **Folder** `<path>/<vault id>/`: `vault.json` = `{"format": "bi.vault/v1", "id", "title",
  "purpose", "schema": "<id>@<version>", "created", "created_by", "folders": {"applications":
  [{"folder", "label"}], "library": ["products", "competitors", "technologies"]}, "coverage": obj |
  null}`; `VAULT.md` (purpose, when the Agent uses it, folders, how to maintain); folders
  `applications/<segment>/sources/` (default the 11 segments of the owner's chart),
  `library/{products,competitors,technologies}/sources/`, `schemas/` (installed schemas the vault uses,
  as `<schema id with / as __>@<version>.json`, never replaced), `skills/`, `changes/<author>/`. No
  database file is ever written to the folder.
- **Change file** `changes/<author>/<seq>.json`, written once (temporary file + rename, never replaced
  or edited; a PC writes only its own author folder):
  `{"format": "bi.vault.change/v1", "vault", "author", "seq": int, "clock": int, "at", "action":
  "create" | "convert" | "import" | "commit_run" | "edit" | "decide_proposal" | "undo_import" |
  "upgrade_schema" | "change", "run_id": str | null, "ops": [...]}`. `seq` = 1 + the highest of the
  author; `clock` (Lamport) = 1 + the highest clock applied on this PC. Operations, with values as
  JSON values (`null` = no value):
  - `meta {key, base, value}` (schema binding, schema history);
  - `import {id, filename, entity_type, at, by, run_id}`; `import_undone {id}`;
  - `card {type, key, name, synthetic, new, version, delta, created, updated, created_by_import}`;
  - `field {type, key, field, base, value, source: {kind, ref, by, at} | null, history: {kind, ref,
    by, at, import_id, reason, old_source}}`; `base` is the value the change was made from;
  - `propose {pkey, type, key, field, value, kind, ref, at, import_id, status}`; `proposal {pkey,
    status}` (closed by an edit: `superseded`; `rejected`; `withdrawn` by an undo);
  - `evidence {type, key, field, value, run_id, source_id, source_name, locator, excerpt, basis, at}`;
  - `card_delete {type, key}`; `snapshot {...}` (dataset to vault: every card with its id, values,
    history, proposals, evidence, imports and meta).
  A proposal is named across PCs by `pkey` (`<author>/<seq>#p<n>`, `#c<n>` for a conflict,
  `convert:<dataset>#p<id>`).
- **How a write becomes a file.** A write to a vault dataset first syncs, then runs the store's own
  method on the local `bi.sqlite` inside a transaction that is always rolled back; what it changed
  becomes the file's operations, the file is written, and it is applied like any other file. The
  store's refusals (`stale_edit`, `cards_changed`, `run_committed`, `preview_stale`, ...) are unchanged
  and write no file. A write with no effect writes no file. A schema upgrade also copies the new
  schema into `schemas/`.
- **Sync.** Every valid file is applied in the order (clock, author, seq). Card ids are
  `sha256("<type>\0<key>")[:12]` (a converted dataset keeps its ids), so two PCs with the same files
  have identical tables. A new file whose key sorts before one already applied, or an applied file
  that changed or vanished, rebuilds `bi.sqlite` from all files in one transaction. A file that is not
  valid JSON or cannot be read is `incomplete` and retried on every sync; a file that is valid JSON but
  not a change file (wrong name, author or seq not matching its path, missing clock, unknown operation)
  is `bad`, skipped and reported; a file that fails while applying is rolled back alone and recorded
  `failed`. The vault's own tables in `bi.sqlite`: `vault_applied` (file, author, seq, clock, sha256,
  outcome), `vault_pkeys`, `vault_conflicts`.
- **Conflicts** (nothing is dropped silently; all are in `status`):
  - a `field` whose `base` is not the field's value at that point: if the field already holds the new
    value nothing happens; otherwise a **pending proposal** (`ref` `vault:<author>/<seq>#<n>`, kind of
    the change) and a conflict `field` with base, current, value, author and any evidence; decided
    with the existing proposal route;
  - a card created (`new`) whose type and key exist: one card and a conflict `merge`;
  - a file whose `run_id` (or import id) was applied already: not applied, outcome `duplicate_run`
    (`duplicate_import`) and a conflict of that kind;
  - a `meta` whose base differs: not applied, conflict `meta`; a proposal decided twice: the first
    decision stays, conflict `proposal`; an undo that would delete a card still holding values: kept,
    conflict `delete_kept`; a write to a card deleted elsewhere: the card is recreated, `recreated`.
  A card's version moves by the change's `delta` only when one of its values was applied.
- **Routes** (JSON; errors `{"ok": false, "code", "message"}`):
  - `GET /api/bi/vaults` → `{"vaults": [{"id", "dataset", "title", "purpose", "schema", "path",
    "author", "reachable", "cards"}]}`.
  - `POST /api/bi/vaults {"path": <existing parent folder, absolute>, "title", "purpose", "schema",
    "author": str | null, "id": str | null, "segments": [str | {"folder", "label"}] | null,
    "coverage": obj | null}` → `{"ok": true, "vault": {...}, "sync": <sync>}`. Creates
    `<path>/<id>/` (id from the title plus 6 hex when not given), registers it and writes
    `changes/<author>/1.json` with the schema binding. `author` defaults from the person's name.
  - `POST /api/bi/vaults/join {"path": <the vault folder>, "author", "resume": bool}` → as create.
    The same vault at a new path updates the registry. An author folder that already has files is
    409 `author_taken` unless `resume` (the same person on a new PC). Schemas in `schemas/` are
    installed.
  - `POST /api/bi/vaults/<id>/sync {}` → `{"ok": true, "sync": {"applied", "rebuilt", "outcomes":
    {outcome: n}, "conflicts": <new>, "bad": [{"file", "reason"}], "incomplete": [{"file",
    "reason"}], "schema_problems", "files", "at"}}`.
  - `GET /api/bi/vaults/<id>/status` → `{"vault", "reachable", "files", "applied", "behind",
    "skipped": [{"file", "outcome", "detail"}], "conflicts": [{"id", "kind", "file", "card_id",
    "field", "proposal_id", "open", "detail", "at"}], "merges": [...], "bad", "incomplete", "cards",
    "clock", "last_sync"}`. Reads only.
  - `POST /api/bi/vaults/convert {"dataset", "path", "title": default the dataset name, "purpose",
    "author", "id"}` → as create plus `"dataset"`: a new vault bound to the dataset's schema whose
    first file (`action: "convert"`) is one `snapshot`; the dataset itself is not changed.
  - Errors: 400 `path_missing`, `path_invalid`, `title_missing`, `vault_id_invalid`, `author_invalid`,
    `segments_invalid`, `coverage_invalid`, `vault_invalid` (no or a bad `vault.json`),
    `dataset_invalid`; 404 `vault_unknown`, `schema_unknown`, `dataset_unknown`; 409 `vault_exists`,
    `author_taken`, `vault_unreachable` (the folder cannot be read: every write and sync is refused),
    `change_exists`.
- **When it syncs.** Before every write to the vault and on `POST .../sync`; reads do not sync.
  Plain datasets, subscribed datasets and demo are written exactly as before and get no vault tables.

## BI coverage: segment x technology area (BI vaults phase V5, 2026-10-28)

Superseded by P5 (2026-11-01): `/api/bi/coverage`, `coverage.py` and the matrix panel are removed; the
coverage matrix is the pack analysis `coverage` (see "BI chains and coverage matrix as analyses").

`GET /api/bi/coverage?dataset=<name>[&types=A,B]` reads a dataset (own, subscribed or vault) and answers how
its cards cover a matrix (`docs/phases/BI_VAULT.md` §6.2). Read only; 404 `dataset_unknown` for an unknown
dataset, 400 `coverage_matrix_invalid` for a bad matrix.

- **Matrix** `aep.bi.coverage_matrix/v1`: `markets[]` (`id`, `label`, optional `emc`, `segments[]` with `id`,
  `label`, optional `priority`, `aliases`), `areas[]` (`id`, `label`, optional `owner`), `segment_field`
  (default `segments`), `area_field` (default `tech_areas`). Ids are unique; a segment belongs to one market.
  Taken from the vault's `vault.json` `coverage` block, else `<dataset>/coverage.json`, else the shipped
  `capabilities/bi_cards/coverage_matrix.json` (the owner's chart: 5 markets, 11 segments whose ids are the
  vault's default folders, 6 of them priority, 5 areas). `matrix_source` says which.
- **Placement**: a card's `segment_field` and `area_field` values match a segment or area by id, label or alias
  (loosely: no spaces, punctuation or case). A card counts in every segment x area pair it names. Values that
  name nothing are counted in `unknown_values`; cards with no segment or no area in `totals.no_segment` /
  `totals.no_area`. Nothing is guessed.
- **Cells** (`cells[]`, every segment x area in matrix order): `cards`, `types` (count per type),
  `sourced_share` (filled non-derived fields with a source reference or fact evidence / filled fields; null when
  none), `newest` (latest card update), `empty` (up to 5 `{field: "Type.field", cards}` most often empty,
  placement fields excluded), `card_list` (up to 200 `{id, name, type}` to open the cards).
- `schema_missing_fields` lists `segment_field`/`area_field` when no type of the dataset's schema has them (every
  card is then unplaced until a schema version adds them).

## BI domain configuration (BI vault V10, owner 2026-10-29)

Design: `docs/phases/BI_VAULT.md` §12 (one market vault, domains as configuration). Code:
`src/capabilities/bi_cards/domains.py`, `store.py` (`meta_value`, `set_meta_value`), uses in `coverage.py`,
`importer.py`, `ai_runs.py`; routes in `src/host_runtime/bi_cards_api.py`; panel 「領域設定」 under the
coverage matrix. Tests: `tests/test_bi_domains.py`, `tests/test_bi_vault_ui.py`.

- **Document** `aep.bi.domains/v1`, kept in the dataset's `meta` table as `domains` (JSON); in a vault the save
  is a change file (`meta` op), so every PC gets it and two saves from the same revision become a vault
  conflict. Keys: `domains` (required): `[{"id", "label", "segments": [{"id", "label", "priority",
  "aliases"}], "chains": [{"id", "label", "node_pattern" | "nodes"}], "nodes": [<name>]}]`; `areas`: `[{"id",
  "label", "aliases"}]` (required when any domain has segments); `segment_field` (default `segments`),
  `area_field` (default `tech_areas`); `name_aliases` `{alias: canonical name}`; `enum_aliases` `{field:
  {alias: allowed value}}`. AEP adds `format`, `revision`, `updated`, `updated_by`.
- **Checks** (400 `domains_invalid`, naming the problem): a domain id must be one of the schema's domains
  (matched case-insensitively and stored in the schema's spelling); ids `[A-Za-z0-9][A-Za-z0-9_-]{0,39}`,
  unique per list; a segment id in one domain only; a chain needs `node_pattern` (a valid regex, at most 200
  characters) or `nodes`; an `enum_aliases` field must be an enum (or allowed-values list) field of the
  schema and every target an allowed value; at most 256 KB.
- **Warnings** (saved anyway): `field_missing` when no type has `segment_field` / `area_field`;
  `value_not_allowed` when a segment or area id is not an allowed value of that field (add it with Session A).
- `GET /api/bi/domains?dataset=` → `{"dataset", "configured", "revision", "config": <document> | null,
  "warnings": [{"code", "message"}]}`.
- `POST /api/bi/domains {"dataset", "config", "base_revision"}` → `{"ok": true, ...as GET}`; `base_revision` is
  the revision read (0 for the first save). 409 `domains_stale` when it changed since; 400
  `base_revision_missing`; 409 `dataset_read_only` for a subscribed copy.
- **Uses.** Coverage: when any domain has segments, the matrix is one market per domain with its segments and
  the configured areas and fields, `matrix_source: "domains"` (before vault, dataset and shipped). Imports
  (CSV import, recipes and ingest runs through `importer.preview`): the configured `enum_aliases` apply under a
  mapping's own; a card name and every link target are written in their canonical spelling. AI extraction:
  candidates' names and link targets likewise, before merging. `Config.chains_of(node, domain)` gives a node's
  chains (listed, or matched by `node_pattern`; a shared node may be in several) for the analyses (V12).

## BI extraction evidence rules (BI vault V11, owner 2026-10-29)

Design: `docs/phases/BI_VAULT.md` §12. Code: `src/capabilities/bi_cards/extract.py` (`EVIDENCE_RULES`,
`GRADE_RULES`, `written_numbers`, `number_written`), `domains.py` (`notes`, `extraction_notes`), `ai_runs.py`.
Tests: `tests/test_bi_extract_evidence.py`. Additive to "BI AI path: extraction runs".

- **Fixed rules.** Every AI extraction's system message has 「Evidence rules (always apply)」 after the card
  types and before the method's instructions: no value without the source; a number, date, ticker, model or
  part number only when written (a written amount may be restated in the card's unit, quoting the original);
  a range or a partial period leaves the number empty; a date is the source's, never today's; a contradiction
  keeps both statements; no sample or fictional cards. A method (Session B) cannot remove them.
- **Evidence grades.** When a requested type has `evidence_grade` (SupplyLink in 2.0.0) the A–D definitions
  follow: A vendor / official / named confirmation; B credible report or company statement with a named
  source; C product capability or public demo only; D unconfirmed, conflicting or no named source.
- **Domain notes.** A domain in the configuration may have `notes` (text, at most 2,000 characters); every
  domain's notes are appended as 「Domain notes」 after the method's instructions.
- **Numbers are checked.** A candidate's `int` / `float` field with basis `fact` must be written in its quote:
  as written (thousands separators, a trailing `%`) or as an amount in 億 (`1兆1,586億` → 11586, `2.53兆` →
  25300). Otherwise its basis becomes `inference`, its evidence is dropped, and the candidate warns
  `number_not_in_quote`.

## BI market analyses (BI vault V12, owner 2026-10-29)

Design: `docs/phases/BI_VAULT.md` §12. Code: `src/capabilities/bi_cards/market.py`, `dashboard.py`
(`dashboard(..., include_sample)`, `analysis`, `analysis_names`), `capability.py`, `bi_cards_tools.py`, the
Dashboard view (domain picker from the schema, 「含 SAMPLE 示範卡」). Tests: `tests/test_bi_market.py`.
Additive to "BI cards API and capability".

- `GET /api/bi/dashboard?dataset=&domain=&include_sample=1` → `{"domain", "include_sample", "sections"}`.
  `include_sample` (default false) keeps cards named `SAMPLE-…`, which are otherwise left out of every section.
- **Sections**, in order: `A`, `A2`, `A3` (the domain's chains from the domain configuration, V10; only when
  the domain has chains), then §1–§19 as before, then the manager's sections offered when the schema has the
  types they read: `20` trend × ecosystem × customer product (Trend, Ecosystem, CustomerProduct); `21`
  win-loss by competitor and unreviewed closed deals (WinLoss, Opportunity); `22` roadmap gaps by impact ×
  customers (RoadmapRequest); `23` sales enablement (Battlecard, Pitch, DemoScript, Competitor, TestSolution);
  `24` contact: open deals without a visit in 60 days, overdue follow-ups (VisitLog, Opportunity); `25`
  customer product × confirmed (A/B) suppliers × trends (SupplyLink, CustomerProduct, Trend); `26` timing:
  demand before launch without our available solution (CustomerProduct, Trend, TestSolution); `27` evidence
  grade × supply stage and A/B links missing `source` / `source_date` (SupplyLink); `28` revenue layers per
  company and accounts without revenue facts (RevenueFact, Account); `29` integrity of our solution,
  competitor vendor and opportunity links (Opportunity, TestSolution, Competitor); `30` one name in two types;
  `31` link targets with no card yet, with the type the field suggests. Each section is `{"id", "title",
  "kind", "columns", "rows", "flags", "note"}` as before; a card cell is `{"card_id", "label", "cite"}`.
- `bi__query` `analysis` also takes `trend_links`, `win_loss`, `roadmap_gaps`, `enablement`,
  `customer_contact`, `supply_evidence`, `timing_gaps`, `supply_grades`, `revenue_layers`, `chain_integrity`,
  `same_names`, `pending_links`, `chain_summary`, `chain_view`, `chain_overlap` (sample cards left out).
- The domain picker lists the dataset's schema domains (2.0.0: + mobile, aerospace), lower case.

## BI quality checks (BI vault V13, owner 2026-10-29)

Design: `docs/phases/BI_VAULT.md` §12 (the manager's `validate.py`, made general). Code:
`src/capabilities/bi_cards/quality.py`, `store.py` (`fact_excerpts`), `importer.py` (`SAMPLE-` rows are
samples), `dashboard.py` (section `Q`, analysis `quality`), `domains.py` (`node_name_pattern`). Tests:
`tests/test_bi_quality.py`.

- `GET /api/bi/quality?dataset=` → `{"dataset", "checks": [{"id", "title", "level": "issue" | "warn", "count",
  "items": [{"card": {"card_id", "label", "cite"} | null, "message"}]}], "totals": {"issue", "warn"}}` (at most
  200 items per check). Read only.
- **Checks** (`issue` unless noted): `link_unresolved` (a link names no card); `link_wrong_type` (the card it
  names is not of the field's `link_to` types); `same_name` (one name in two types); `sample_not_marked` (a
  `SAMPLE-` card not flagged synthetic); `evidence_source` (an A/B `evidence_grade` without `source`, or
  without `source_date` unless the body says 「來源日期待補」); `number_ungrounded` (an `int` / `float` value
  whose fact excerpts do not write it, 兆/億 amounts read); `revenue_layer` (customer layer without customer,
  another layer with one, or no `source`); `node_format` (a Node name not matching the configuration's
  `node_name_pattern`); `node_not_listed` (`warn`: a Node outside its domain's `nodes` list, when the list is
  given); `product_without_node` (`warn`).
- The Dashboard ends with section `Q` 「資料品質檢查」 (`issue` rows flagged red, `warn` rows warn); `bi__query`
  `analysis: "quality"` returns it.
- An import row whose cell starts with `SAMPLE-` is a sample (`synthetic`), like 虛構 / 範例.
- The domain configuration takes an optional top-level `node_name_pattern` (a regex, at most 200 characters).

## BI source Markdown (BI vault phase V2, owner 2026-10-28)

Design: `docs/phases/BI_VAULT.md` §5. Code: `src/capabilities/bi_cards/convert.py` (conversion),
`source_markdown.py` (current revision, conversion on first need, saving an edit), `staging.py` (tables
`markdown`, `conversions`, column `runs.markdown_rev`), `readers.py` (exact table reading), routes in
`src/host_runtime/bi_cards_api.py`. Tests: `tests/test_bi_source_markdown.py`. Additive to "BI ingest runs".

- **Conversion** (`aep.bi.convert/1`, recorded as each conversion revision's `converter`):
  - CSV/TSV: one pipe table, no heading (header on line 1); blank rows left out.
  - Excel (`.xlsx`, `.xlsm`): per sheet `## <sheet name>`, a blank line and one table (header = the first
    non-empty row, unnamed columns left out, as the phase 3 reader); an empty sheet is the line
    「（這個工作表是空的）」.
  - PDF with a text layer (`pypdf`): per page with text `## 第 <n> 頁` and its text. A PDF with no text on
    any page is refused when added: 400 `source_no_text` (no OCR), nothing is kept.
  - Word `.docx` (`python-docx`): body paragraphs and tables in order; `Title` → `#`, `Heading n` → `n` ×
    `#`, `List*` styles → `- `; a table's first row is its header.
  - PowerPoint `.pptx` (`python-pptx`): per slide `## 投影片 <n>：<title>`, then its text frames (a
    paragraph of level ≥ 1 → `- ` indented by level), tables, and notes under `### 備註`.
  - Markdown (`.md`, `.markdown`) and text (`.txt`): as is (UTF-8, CRLF → LF).
  - Table cells (all formats): `\` → `\\`, `|` → `\|`, a line break → `<br>`; a converted table source is
    read back exactly (the reverse), so a cell keeps its text. A Markdown report keeps the phase 3 reading.
  - A missing library (the `office` extra) is `converter_missing`; an unreadable file `source_parse_failed`;
    a CSV/TSV that is not UTF-8 `source_decode_failed`; another file type `file_type_unsupported`.
- **Sources.** `POST /api/bi/sources` also accepts `.pdf`, `.docx`, `.pptx` (and `.xlsm`, `.markdown`) as
  `content_base64`; the source is converted when added. `<source>` adds `"format": "table" | "document" |
  "text" | null` (null: cannot be converted), `"markdown_rev"` (the current revision, 0 = none) and
  `"convert_error": {"code", "message"} | null`. A conversion failure other than `source_no_text` keeps the
  source with `convert_error` and is tried again when next needed. Documents report `parse: "text"`.
  A source added before V2 is converted on first need (a run, a session sample, the Markdown view, an index
  rebuild); that revision's `by` is the person who added the source.
- **Revisions** are immutable files `<dataset>/markdown/<source id>/rev-<n>.md`; `<revision>` = `{"rev",
  "origin": "conversion" | "edit", "note", "converter": str | null, "sha256", "chars", "lines", "by", "at"}`.
  The original copy under `sources/` is never changed.
  - `GET /api/bi/sources/<id>/markdown?dataset=` → `{"source": <source>, "current_rev", "revision":
    <revision>, "markdown": str, "revisions": [<revision>...]}` (newest first).
  - `GET /api/bi/sources/<id>/markdown/<rev>?dataset=` → the same with `revision` and `markdown` of `rev`.
  - `POST /api/bi/sources/<id>/markdown {"dataset", "markdown", "base_rev", "note"?}` → `{"ok": true,
    "source", "revision", "current_rev", "already"}`. The same text as the current revision saves nothing
    (`already: true`). `base_rev` is the revision the edit was made from (0 for a source that could not be
    converted: the person's text becomes revision 1).
  - Refusals: 404 `source_unknown`, `markdown_rev_unknown`; 400 `markdown_rev_invalid`, `markdown_missing`
    (empty), `markdown_too_large` (over 2,000,000 characters), `base_rev_missing`, `note_too_long` (over
    300), and the conversion errors above; 409 `markdown_stale` with `current_rev` (someone saved first);
    409 `dataset_read_only`.
- **Runs read the current revision.** `<run>` adds `"markdown_rev"` (null for runs before V2). The rule
  path (with or without a recipe) reads the tables of that revision; evidence of a CSV/TSV value is
  `{"table": 0, "line", "column"}` and of an Excel value `{"sheet", "table", "line", "column"}`, where
  `line` is the row's line in that revision (before V2: `{"row", "column"}` / `{"sheet", "row",
  "column"}` of the original file). A Markdown report's locators are unchanged. The AI path sends that
  revision's text, so `{"line_start", "line_end"}` point into it; a retry reads the same revision. Session
  A and B samples are the current Markdown.
- **Path.** `POST /api/bi/runs` takes `"path": "ai" | "rules" | null`. Null: documents and text → AI,
  tables → rules (as before). `"ai"` on a table source runs the AI path on its Markdown (owner 2026-10-28:
  a person may switch a table to 「AI 擷取」); `"rules"` on a document is 400 `source_not_table`; `"ai"`
  with a recipe or another value is 400 `path_invalid`.

## BI search index (BI vault phase V3, owner 2026-10-28)

Design: `docs/phases/BI_VAULT.md` §6.1. Code: `src/capabilities/bi_cards/search_index.py`; the hook in
`store.py` (`BiStore._db` after every write), `staging.py` (a source added) and `source_markdown.py`
(conversion, edit); routes in `src/host_runtime/bi_cards_api.py`. Tests: `tests/test_bi_search_index.py`.

- **File.** `<dataset>/search.sqlite`, separate from `bi.sqlite`; a cache that can be deleted and rebuilt.
  SQLite FTS5 with `tokenize='trigram'` (case-insensitive). Reading a dataset that has nothing creates no
  file.
- **Content.** Cards: name, canonical key and the values (lists joined with 「、」) of the fields the
  dataset's schema has now (a retired field is not indexed). Markdown: the current revision of every source
  that has one, cut along headings and paragraphs into chunks of about 1200 characters, each with
  `source_id`, `rev`, `line_start`, `line_end`.
- **Kept current** after every card write (commit, field edit, accepted proposal, undo, schema upgrade,
  demo load, Case A import): cards whose `version` moved are re-indexed, removed cards dropped, every card
  when the schema ref changed; after every Markdown revision (added source, conversion, edit). A failure to
  update never fails the write; the status then shows `behind`.
- **Status.** `GET /api/bi/index?dataset=` → `{"index": {"exists", "tokenizer": "trigram", "cards",
  "chunks", "sources", "built_at" (last full rebuild) | null, "updated_at" | null, "behind": bool,
  "behind_cards", "behind_sources"}}` (cards or sources whose indexed version/revision differs from now).
- **Rebuild.** `POST /api/bi/index/rebuild {"dataset"}` → `{"ok": true, "index": <status> +
  "not_converted": [{"source_id", "name", "code"}]}`; sources without Markdown are converted first. 404
  `dataset_unknown`; 409 `dataset_read_only` (a subscribed copy builds its index on the first search).
- **Search.** `GET /api/bi/search?dataset=&q=&limit=` (limit 1–100, default 20, per list) → `{"query",
  "terms", "mode": "index" | "scan" | "none", "cards": [{"id", "entity_type", "name", "canonical_key",
  "version", "hits": [{"field" ("name" or a field name), "snippet", "marks"}]}], "passages": [{"source_id",
  "source_name", "rev", "line_start", "line_end", "line" (first line with a match), "snippet", "marks"}],
  "index": <status>}`. `q` is split on spaces (at most 8 words, 200 characters); every word must match in
  the same card or chunk. All words of 3 or more characters use the index (`index`, ranked by bm25); any
  shorter word makes the query scan the indexed rows (`scan`). `snippet` is at most about 160 characters
  (`…` where cut); `marks` are `[start, end)` offsets of every word in it. The index is brought up to date
  before searching. Unknown dataset: 404 `dataset_unknown`.
- `GET /api/bi/cards?q=` (`service.search`) and `bi__query` are unchanged; the commit result's `index`
  (contract "BI ingest runs") is now `{"status": "current" | "behind", "message", ...<status>}`.

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
  not ship → `schema_unavailable`). A shipped schema is matched by id@version, not by digest, so
  an AEP release that ships it is enough.
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
  "bi-dataset-publish", "author": <publisher>, "revision": <published_at, ISO>}`,
  `validation_refs` `["bi-snapshot-digest:<content digest>"]`, `package {artifact_ref:
  "registry://<ns>/<name>/<version>", sha256}`, `description` the version note,
  `technical_policy` `not_required` (data, not executable), `business_approval` approved by the
  reviewer (first version) or `not_required` by the publisher (later versions).
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
  `AssetSubmission` of kind `bi_dataset` approved with `admin/submissions/approve`
  (`admin/submissions/get` shows a summary instead of a manifest: `kind`, `dataset`,
  `classification`, `schema {ref, source}`, `stats`, `digest`, `publication`; no card values).
  While it waits, another publish of that name is 409 `review_pending`. `assets/submit` still
  takes only `skill` and `workflow`.
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
`withdrawn`, `published`, `selected`, `replaced`, `revoked`, `synced` (the Bridge a version was delivered to),
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

### Agent subscriptions (read-only copies, sync, badge, update)

Code: `src/capabilities/bi_cards/subscriptions.py` (install, status), `src/capabilities/bi_cards/
store.py` (read-only mode), `src/host_runtime/bi_subscriptions.py` (routes, catalog check),
`src/host_runtime/sync.py` (the `bi_dataset` installer), `src/capabilities/bi_cards/capability.py`
(`bi__query` source).

**Layout.** A subscribed dataset is named `<namespace>/<name>` (both platform slugs) everywhere a
dataset name is taken (`dataset` of every `/api/bi/*` route and of `bi__query`). It lives at
`<workspace>/bi/subscribed/<namespace>__<name>/`: `subscription.json` (`dataset`, `namespace`,
`name`, `version`, `sha256` of the stored artifact, `digest`, `published_by`, `published_at`,
`note`, `schema`, `installed_at`, `latest: null | {version, description}`, `reachable`,
`stopped`, `stopped_at`, `checked_at`) and `<version>/` written by `install_snapshot`
(`bi.sqlite`, `snapshot.json`). Only the installed version is kept (§8.6). `subscribed` and
`schemas` are reserved local names (400 `dataset_invalid`); `datasets()` never lists them.

**Read only.** `BiStore(workspace, "<ns>/<name>")` opens the installed `bi.sqlite` read only;
every write (`create`, `apply`, `set_field`, `undo_import`, hence the demo load) raises
`dataset_read_only`. The routes `POST /api/bi/import/preview`, `import/undo`, `demo/load` and
`cards/<id>/field` with a subscribed `dataset` answer 409 `{"ok": false, "code":
"dataset_read_only", "message"}` before anything is read.

**Install (the sync).** A `bi_dataset` package in the Bridge API `sync` plan is installed by
`subscriptions.prepare(...)` then `PreparedInstall.commit()`: the artifact SHA-256 equals the
package's, `read_snapshot` accepts it, its `publication` names the same
`<namespace>/<name>@<version>`, and `schema_state` is `shipped`, `present` or `missing` (missing
→ `install_schema` with the snapshot); all of this before the first write. Refusals become the
sync's refusal (`sync_<code>`, nothing written): `artifact_hash_mismatch`, `asset_invalid` (an
unreadable snapshot or another identity), `asset_conflict` (the same version installed with other
bytes), `schema_conflict`, `schema_unavailable`. The same version and digest again is a no-op.
A failure after the first write takes back what was written.

**Status.** Every Agent Web catalog read (Settings, sync) and `GET /api/bi/subscriptions?refresh=1`
asks the Bridge API `catalog {"kinds": ["bi_dataset"]}` when something is subscribed:
- answered, the name listed: `current`, or `update_available` with `latest` when a newer version
  is listed (the badge; nothing is installed);
- answered, the name absent: `stopped_no_access` (owner Q2: the copy is kept and readable, no
  longer updated); it clears if the name is listed again;
- not answered: `offline` (unless stopped); nothing else changes.

Status precedence: `stopped_no_access` > `offline` > `update_available` > `current`.

**Routes** (same guards and error shape as the other `/api/bi/*` routes):

- `GET /api/bi/subscriptions[?refresh=1]` → `{"ok": true, "configured": bool, "subscriptions":
  [<entry>], "connection": "answered" | "unreachable", "available": [{"name", "version",
  "description", "owner"}]}`; `connection` and `available` (entitled names not subscribed, newest
  version each) only with `refresh=1` on a configured platform. Without `refresh` nothing is
  asked of the platform.
- `<entry>`: `{"name": "<ns>/<name>", "subscribed": true, "read_only": true, "version",
  "published_by", "published_at", "note", "schema", "status", "status_text", "latest",
  "latest_note", "stopped_at", "checked_at", "cards", "updated"}`. `status_text`: 已是最新版本 /
  有新版本 / 已停止更新（無權限） / 無法連線平台.
- `POST /api/bi/subscriptions/subscribe {"dataset": "<ns>/<name>"}` and
  `POST /api/bi/subscriptions/update {"dataset"}`: select the newest entitled version for this
  Bridge with the member's Personal Agent login (`select`, which replaces the previous version's
  selection), run the verified sync, answer `{"ok": true, "subscription": <entry>}` (or
  `"already": true` when nothing newer exists). Refusals: 400 `dataset_invalid`; 404
  `subscription_unknown` (update of a name not subscribed); 409 `platform_not_configured`; 503
  `platform_unreachable`; 403 `dataset_no_access` (the copy is kept and marked stopped); 403/409
  `asset_not_entitled`-style codes from `select`; 502 with the sync's code when the selected
  version did not get installed (the old copy is untouched).
- `POST /api/bi/subscriptions/unsubscribe {"dataset"}` (the page confirms first): takes back the
  selection on the platform when it can (`deselected`), removes the local folder and the
  installed-inventory row → `{"ok": true, "removed", "deselected": bool}`; 404
  `subscription_unknown`.
- `GET /api/bi/datasets` adds `"subscribed": false, "read_only": false` to each local dataset and
  lists the subscribed ones after them as `<entry>` plus `"dashboard"`. `POST /api/bi/datasets`'s
  `dataset` gains the same two fields.

**Chat.** `bi__query` takes a subscribed `dataset` (up to 81 characters); its result adds
`source: {"dataset", "version", "published_by", "published_at", "status", "stopped", "latest"}`
(`null` for a local dataset) and the `scope_note` ends with 「資料來源：<ns>/<name> v<version>
（發佈者 <account>）」 plus 「；這份副本已停止更新（無權限）…」 when stopped or 「；平台上有
v<latest>，尚未更新」. A `<ns>/<name>` not subscribed is refused as `dataset_unknown`.
After an answered turn, Agent Web and Telegram append that line (from the result's `source`,
`host_runtime.bi_cards_tools.with_bi_sources`, 2026-10-24) for each subscribed dataset and
version a succeeded `bi__query` call read, once each, unless one line of the answer already
names that dataset and version; an own dataset adds nothing. The
`engineering/bi-knowledge` procedure tells the model to end with that version line and to say
「已停止更新」 when `source.stopped`.

### Configuration

`SharedPlatformConfiguration.max_bi_dataset_bytes` (default 20 MiB, 1 MiB–64 MiB): the largest
stored snapshot (gzip). Deploying needs a platform built from this commit or later; no other
setting.

### Agent publish API (Agent Web)

Code: `src/host_runtime/bi_cards_api.py` ("publishing to the Shared Platform" section,
`publish_route`); page: 「BI 卡片」 → 「發佈到 Shared Platform」. Same guards and error shape as
the other `/api/bi/*` routes (`{"ok": false, "code", "message"}`).

`POST /api/bi/publish`

```json
{"dataset": "demo", "note": "十月更新", "readers": "team", "confirm_organization": false,
 "name": "engineering/demo", "team": null}
```

- `dataset`: an own (local) dataset; a subscribed `<namespace>/<name>` is 409
  `dataset_read_only`. `note` is required (≤ 200 characters). `readers`: `team` (default) or
  `organization`, which needs `confirm_organization: true`; `public` is `visibility_not_allowed`.
- `name` (optional, first publish only): the platform name `<namespace>/<name>`; default
  `<host.json namespace>/<dataset as a slug>`. After the first publish the recorded name is used
  and `name` is ignored. `team` is passed to the platform (for a member of several groups).
- The Agent builds the snapshot (`build_snapshot`), asks `bi_dataset_status` for the newest
  version and sends it as `base_version` with `publish_bi_dataset`.
- 200: `{"ok": true, "dataset", "name": "<ns>/<name>", "version", "status": "published" |
  "pending_review", "at", "readers"}`.
- Refusals (status, code): 400 `note_required`, `readers_invalid`, `visibility_not_allowed`,
  `organization_unconfirmed`, `name_invalid`, `namespace_required`, `dataset_empty`; 400
  `secret_found` with `card` (`<entity_type>:<canonical_key>`) and `field`, never the value; 404
  `dataset_unknown`; 409 `dataset_read_only`, `publishing_not_configured`, `version_superseded`,
  `review_pending`, `kind_mismatch`; 403 `publisher_not_authorized`; 413 `artifact_too_large`;
  503 `platform_unreachable`; other platform codes as 400 with the platform's code. Messages are
  in Traditional Chinese.

`GET /api/bi/publish/status?dataset=<name>` → `{"ok": true, "dataset", "last": null | {"name",
"version", "status": "published" | "pending_review", "at", "readers", "note", "digest",
"submission_id"}, "name": "<recorded or suggested platform name>", "cards", "proposals"
(pending, not shared), "configured": bool}`. The last publish is kept in
`<workspace>/bi/<dataset>/published.json`. While it is `pending_review` the status asks the
platform (`bi_dataset_status`) and marks it `published` once that version is the newest; any
failure leaves it as it is. A subscribed dataset is 409 `dataset_read_only`.

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

## Agent Web activity (`GET /api/activity`, owner 2026-10-25)

Code: `AgentWeb.activity` and the route in `src/host_runtime/web.py`,
`TelegramIngress.activity` in `src/channels/telegram.py`, `TurnProgressBoard.running` in
`src/agent/turn_progress.py`, `activity` / `restart_blockers` in `src/host_runtime/launcher.py`.
Tests: `tests/test_restart_activity.py`. Decision: `docs/DECISIONS.md` 2026-10-25; rule:
`AGENTS.md` 19.

- `GET /api/activity` (loopback, `Authorization: Bearer <page token>`, as every `/api/*` read) →
  `{"ok": true, "busy": <bool>, "items": [...]}`; `busy` is true when `items` is not empty.
- Items, each with `kind` and `started_at` (ISO 8601, UTC, seconds):
  - `{"kind": "task", "started_at", "task": <task kind>}`: a running background task (the
    `status: running` rows of `GET /api/tasks`);
  - `{"kind": "chat_turn", "started_at"}`: an Agent Web conversation turn in progress; with
    `"delegations": <n>` while n delegated sub-agents run under it (multi-agent V1, only when n > 0);
  - `{"kind": "telegram_flow", "started_at", "chat", "workflow": "<namespace>/<name>",
    "stage": "question" | "card"}`: an open Telegram question flow (memory only; expired flows are
    left out);
  - `{"kind": "telegram_turn", "started_at", "chat"}`: a Telegram update being handled now.
- No message content, no names, no chat or sender ids: `chat` is the first 12 hex characters of a
  SHA-256 over a per-process random salt and `<chat>:<sender>`, stable within one Agent Web run.
- `launcher.restart_blockers(address)` (the address file's `address`, with its token) returns one
  line per item, `[]` when idle, and `["activity unknown: …"]` when the route does not answer (Agent
  Web down, or a build without it): a restart helper never reads "unknown" as idle. A restart waits or
  asks while it is not empty; forcing is the operator's explicit choice.

## Boolean choice labels (`true_label` / `false_label`, owner 2026-10-25)

Code: `WorkflowParameter` in `src/common/assets.py`; `boolean_labels`, `boolean_from_label` in
`src/common/workflow_forms.py`; `src/channels/telegram_flow.py`; `booleanControl` in
`src/host_runtime/web_page.py`. Tests: `tests/test_boolean_choice_labels.py`. Decision:
`docs/DECISIONS.md` 2026-10-25 "A yes/no input says what each choice does"; rule: `AGENTS.md` 18.

- `WorkflowParameter.true_label` / `false_label`: optional nonblank text, `kind: boolean` only (any
  other kind is refused), and the two must differ (case and outer spaces ignored). Additive: both
  are omitted from the serialized manifest while unset, so manifests published before them keep
  their bytes and digests.
- The two choices shown for a boolean are `(true_label, false_label)` when declared; otherwise the
  label without a trailing `?` / `？`, and 「不要：」 + that label. No interface shows a bare Yes/No.
- `form_field` (Agent Web, schedule, settings forms) carries the resolved `true_label` and
  `false_label` for every boolean. The Agent tool schema adds `(true: …; false: …)` to the
  description when the labels are declared.
- Telegram: the question's buttons are the two choices, one per row, with callback data `yes` / `no`
  (unchanged); the question's `Default:` line, the prefill note and the card show the choice
  (「- 執行方式：正式執行（寫入週報、起草郵件）（預設）」). A typed answer or edit accepts 是／否／yes／no
  as before and also a choice: the whole label, its head before 「（」 / `(`, or the start (two or
  more characters) of only one of the two; on the card, 「改成<choice>」 or the choice alone changes
  the one switch that has it (none changes when two switches have it).
- Agent Web: a boolean is two radio options in a `role="radiogroup"` (`#<id>-choices`, options
  `#<id>-true` / `#<id>-false`, named by the field's label); a hidden checkbox `#<id>` keeps the
  value, so the submitted run arguments are unchanged.

## Session artifacts and `session__attach_file` (owner 2026-10-25)

Code: `src/host_runtime/session_artifacts.py`; `Gateway.session_context` in `src/agent/gateway.py`;
`TelegramDelivery.attached`, `_record_run`, `_record_turn` in `src/channels/telegram.py`;
`_record_run_outputs`, `_record_turn_outputs` in `src/host_runtime/web.py`. Tests:
`tests/test_session_artifacts.py`. Decision: `docs/DECISIONS.md` 2026-10-25 "A session remembers
what it produced"; rule: `AGENTS.md` 20.

- **Ledger.** One per (session id, actor): `<workspace>/session-artifacts/<sha256 prefix>.json`,
  keeping the last 20 runs and 60 artifacts. A Telegram chat's session is `telegram-chat-<chat id>`
  with the acting member; an Agent Web conversation's is its `session_id` with the page's actor.
- **What a run records.** `SessionRun`: `run_id`, `workflow` (name), `status`, `summary` (the last
  step's `summary` / `preview` / `message` first line, at most 160 characters, else the step count;
  the failure code when it failed), `artifact_ids`. `SessionArtifact`: `artifact_id` (`f<n>`, per
  ledger), `kind` (`image`, `spreadsheet`, `document`, `mail draft`, `file`, by suffix), `filename`,
  the Host-side `path` (empty for a mail draft), `run_id`, `workflow`. Files come from step data
  fields `chart_path`, `png_path`, `html_path`, `output_path` and `attach` / `files` lists of
  `{path}`, only when the file exists inside the workspace; a mail draft from step data with a
  non-empty `entry_id` and `subject` and not `skipped`. A host tool's `attach` list (the org chart)
  is recorded without a run. The same run id is recorded once.
- **History entry.** 「【執行結果】<workflow> · run <id> · <status>」, 「摘要：…」, then 「產出：」 and one
  line per artifact 「- f1 image: effort-chart.png」; no paths, no contents.
- **Each turn's system prompt** (when the request has a session) lists the last 8 runs with their
  artifacts and up to 24 files in all, names only, at most 4,000 characters, with the instruction to
  attach by id and never ask for a path.
- **`session__attach_file`** input `{"artifact_id": "f<n>"}`. Success data: `artifact_id`, `kind`,
  `filename`, `note` (no path). Refusal codes: `attach_no_session` (no session), `artifact_id_invalid`
  (not `f<n>`, e.g. a path), `artifact_unknown` (not recorded for this session and actor),
  `artifact_not_a_file` (a mail draft), `artifact_missing` (gone or outside the workspace). The
  channel resolves the id again with the same check before sending.
- **Delivery.** Telegram: `TelegramDelivery.attached` paths are sent after the reply, photos, and
  documents — `sendPhoto` for `.png` / `.jpg` / `.jpeg`, `sendDocument` otherwise (media type by
  suffix), caption the file name. A run's pictures are `attached` at the end of the run (question
  flow, directly handled commands, runs the model started), then what the attach tool attached, each
  path once. Agent Web: the same files are the answer's `files` / stored `attachments`
  (`{filename, kind, path}`), served only through `/api/conversations/file` (listed on the
  conversation and inside the workspace). Telegram `/new` clears the chat's ledger.

## Task result summaries (owner 2026-10-25)

Code: `src/host_runtime/task_summaries.py`; `SessionArtifacts.finish_run`, `finish_turn` in
`src/host_runtime/session_artifacts.py`; `model_condenser` in `src/host_runtime/host.py`;
`task_summary_note` and the nightly purge in `src/host_runtime/web.py`; routes in
`src/host_runtime/memory_page.py`; `_summary_note` in `src/channels/telegram.py`. Tests:
`tests/test_task_summaries.py`. Decision: `docs/DECISIONS.md` 2026-10-25 "Task result summaries,
kept 30 days"; rule: `AGENTS.md` 20.

- **`TaskSummary`**: `summary_id` (`ts-<12 hex>`), `session_id`, `actor`, `at` (UTC), `task`,
  `status` (`succeeded`, `failed`, `needs_input`, `unavailable`, `answered`), `key_results` (≤ 5,
  ≤ 80 characters each), `artifacts` (`{id, kind, name}`, the ids of `session__attach_file`),
  `follow_ups` (≤ 3), `run_id`.
- **Block** (the reply's end, 3–5 lines): 「結果摘要」, 「- 任務：<task>（<status word>）」, then when
  present 「- 重點：…」, 「- 產出：f1 effort-chart.png（圖）；…」, 「- 後續：…」.
- **System prompt**: the session's latest 5 within retention, one line each
  (`<UTC time> <task> (<status>) — results: … — artifacts: … — follow-ups: …`), after the ledger.
- **Storage**: `<workspace>/session-artifacts/task-summaries.sqlite`, table `task_summaries
  (summary_id TEXT PRIMARY KEY, actor, session_id, at, body JSON)`; settings
  `task-summaries-settings.json` `{retention_days: 1..365}` (absent: 30). `purge()` deletes rows with
  `at` before now − retention and ledger `*.json` files last modified before it.
- **Routes** (Agent Web page token, the page's actor): `GET /api/memory/task-summaries` →
  `{ok, summaries: [TaskSummary + block + at_local], settings}`;
  `POST /api/memory/task-summaries/delete {id}`, `POST /api/memory/task-summaries/settings
  {retention_days}` (refusal `summary_retention_invalid`), `POST /api/memory/task-summaries/note
  {id}` → `{ok, already, note?, change_id?, message}` (refusal `summary_unknown`).
- **Messages**: `ConversationMessage.task_summary_id` (optional, `ts-…`) on the answer that ends
  with a block; the page shows 「結果摘要存成筆記」 under it. Telegram: the button
  `("存成筆記", "sumnote:<id>")` under the reply; a typed 「存成筆記」 (no open flow) saves the chat's
  latest summary; without Agent Web the reply says it is needed.
- **Condensing call**: only when deterministic key results are fewer than two and a step's
  `preview` exists; `ModelRequest` with two messages, `max_output_tokens` 200, input ≤ 3,000
  characters; none without `gateway.router.model`.

## Multi-agent delegation (V1)

Code: `AgentProfile` in `src/agent/contracts.py`; `MultiAgentSettings` in
`src/host_runtime/contracts.py`; `validate_profile`, `delegation_target` in
`src/host_runtime/profiles.py`; `src/agent/delegation.py` (contracts, `DelegationService`, the
`agent__delegate` Host tool); `src/agent/delegation_scope.py` (per-turn state); the sub-run in
`Gateway.converse` (`src/agent/gateway.py`). Tests: `tests/test_delegation.py`. Decisions:
`docs/DECISIONS.md` 2026-10-26 "Multi-agent Gate 0 approved (ADR-MA1–MA5)" and 2026-10-27
"Multi-agent V1 core delegation". Rules: `AGENTS.md` 13, 18, 19, 20, 21.

- **Flag.** `host.json` `multi_agent: {"enabled": false}` (`MultiAgentSettings`, `StrictBool`,
  default `false`; an older file without the field means off). Off is today's behaviour exactly:
  no `agent__delegate` tool, `may_delegate_to` still refused with `profile_delegation_unsupported`,
  no new telemetry, no new fields in `/api/activity`. Changing it needs an Agent Web restart.
- **`AgentProfile` additions** (all optional; every existing profile file stays valid):
  - `model_policy`: `"session"` (default, the only V1 value): a sub-agent uses the session's model
    (`TURN_MODEL`) through the same approved model client. Later values (an alias allowlist inside
    the approved Gateway, ADR-MA3) will be added as new literals; an unknown value makes the
    profile invalid (fail closed).
  - `max_tool_calls`: 1–150, default 20: the sub-run's tool cap (never above the parent turn's).
  - `time_limit_s`: 1–1800, default 300: the sub-run's wall-clock limit (never beyond the parent
    turn's remaining time).
  - `selector_hint`: ≤ 240 characters, optional: what the profile is for, shown to the parent
    model next to `description`.
  - `max_turns` (existing, 1–151, default 8) is now enforced as the sub-run's model-turn limit.
    `max_retries` is not read in V1 (the conversation check's one retry applies).
- **Activation with the flag on.** `may_delegate_to` is accepted; each target must be installed,
  `published`, selected (`authorization.allows("agent", …)`), with every Skill and Knowledge it
  names selected and installed, every capability selected, and the routing endpoint satisfying its
  `model_requirements` — else `profile_delegation_target_unavailable`. A target's own
  `may_delegate_to` is ignored (depth 1). In owner mode (no Shared Platform authorization,
  `local_owner_grants: true`) a delegation target needs no selection: an installed, `published`
  profile whose Skills and Knowledge are installed qualifies (the owner holds every installed
  asset); activating a parent profile still needs authorization, as before.
  `RoutingOutcome` keeps refusing `kind: agent` (ADR-MA1: delegation is a tool call, not a route).
- **When the tool is offered.** Only with the flag on, on the Gateway backend (CLI backends —
  Claude Code, Codex, Copilot — never reach the Gateway loop, so they never get it), to a parent
  turn and never inside a sub-run (depth 1), and only when at least one target is eligible.
  Eligible targets: the active profile's `may_delegate_to` entries that validate (listed to the
  model with `description` and `selector_hint`), and any other installed profile that validates
  when the person's own message names it (`namespace/name` or `name`, case-insensitive; listed by
  name only). There is no ranker.
- **`agent__delegate` input** (`DelegationRequest`, JSON schema offered to the model,
  `additionalProperties: false`):
  - `profile` (required): `namespace/name` or `namespace/name@version`; without a version it must
    match exactly one eligible target (`delegation_profile_ambiguous` otherwise);
  - `objective` (required): 1–4,000 characters, self-contained: the sub-agent sees nothing else
    from the parent conversation;
  - `input_artifact_ids` (optional, ≤ 10): ids from this session's ledger (`f<n>` files, or run
    ids); each must be recorded for this session and actor (`delegation_artifact_unknown`);
  - `tools` (optional, ≤ 40): tool names to narrow the sub-agent to; never widens.
- **Effective tools** = the parent turn's installed Skill tools (the Host's registry, already
  narrowed by an active profile) whose Skill is in the target's `skills`, whose capability is in
  its `allowed_capabilities` and authorized for the parent actor by `LocalPolicy.authorize` (a
  Knowledge vault tool also needs its vault in the target's `knowledge`; a Workflow tool needs every
  step capability allowed and authorized), ∩ `tools` when given. Host tools (authoring, GUI,
  cards, MCP, forms, memory, attach, delegation) are never offered to a sub-agent in V1. A
  sub-agent with no effective tools may still answer from the objective; the claim check applies.
  Read-only: every effective tool is a capability with `side_effect: read` (Workflows are never
  read-only).
- **Sub-run.** `Gateway.converse` with the objective as the only message (plus input artifacts:
  run id, workflow, status and summary; file id, kind and name, and the first 4,000 characters of a
  text file — never a path), `allowed_tools` = effective tools, `max_turns` = the profile's, the
  tool cap and time limit above, the profile's description as role guidance, no persona, no
  memory, no session list, no form or proposal tools. The request keeps the parent's `actor`,
  `namespace`, `channel` and `session_id` (so an approval card lands in the parent conversation)
  and gets `trace.request_id` `<parent request id>.d<n>`. Same guards, same approved model client,
  same claim check and Host-check retry. It shares the parent turn's side-effect record (rule 21).
  The sub-agent never asks the person: when it needs input it answers with a first line
  `NEEDS_INPUT: <question>`.
- **Limits.** Depth 1; at most 3 delegations per parent turn (the 4th is refused,
  `delegation_limit_reached`); a parent turn's time budget covers its sub-runs.
- **Parallelism.** When one model reply carries several `agent__delegate` calls and each one's
  effective tools are all read-only, up to 3 run concurrently (results kept in call order).
  A delegation with any write-capable tool runs alone, in order, and its writes are serialized by
  the Bridge exclusive lock as always. The Workflow engine stays sequential.
- **Time limit and cancellation.** A sub-run stops at its limit (the loop's own check between
  steps, and a hard stop at the deadline): status `failed`, code `delegation_time_limit`. There is
  no cancel button in V1.
- **Writes.** Unchanged policy: in owner mode a model-chosen write becomes an approval request for
  the parent session (Agent Web approvals / Telegram buttons); the delegation reports
  `awaiting_approval` with the approval ids; nothing is written before the person's press.
- **Result** (`DelegationResult`, the tool's host data under `delegation`):
  - `status`: `succeeded` | `needs_input` | `awaiting_approval` | `failed`;
  - `profile`: `namespace/name@version`;
  - `summary`: the sub-agent's answer, Host notes included, capped at 8,000 characters with a
    visible note (G4);
  - `findings`: ≤ 20 strings (≤ 500 characters each), the answer's bullet lines;
  - `question`: set only for `needs_input`;
  - `artifacts`: `{kind: "run" | "file", id, name, status?}` recorded in the parent session ledger;
  - `approvals`: approval ids waiting for the person (only for `awaiting_approval`);
  - `tool_calls`: `{name, status: "succeeded" | "failed" | "awaiting_approval", replayed}` per call;
  - `tokens`: `{input, output, model_calls}` (`input` / `output` null when the provider reported
    none);
  - `read_only`, `validated` (the sub-run's answer passed its Host checks and carries no Host
    note), `host_note` (why not), `elapsed_s`;
  - `failure`: `{code, message}`, present exactly when `status` is `failed`.

  Host outcome mapping: `succeeded` → `succeeded`; `awaiting_approval` → `awaiting_approval`;
  `needs_input` → `failed` with code `delegation_needs_input` (so the parent's answer cannot claim
  it done); `failed` → `failed` with the code. Host data also carries `delegation_verdict`
  (`validated` / `not_validated`) and `harness_key`: a not-validated result keeps its text and the
  parent's final answer gets the Host's G1 note naming it.
- **Refusal codes** (no sub-run started): `delegation_disabled`, `delegation_depth_exceeded`,
  `delegation_limit_reached`, `delegation_arguments_invalid`, `delegation_target_not_allowed`,
  `delegation_target_unavailable`, `delegation_profile_ambiguous`, `delegation_artifact_unknown`,
  `delegation_time_exhausted`. Run failures carry the sub-run's code (`model_unavailable`,
  `tool_loop_limit`, `turn_time_limit`, …) or `delegation_time_limit`.
- **Telemetry** (counts only): run kind `agent_delegation` with `parent_run_id` = the parent
  turn's run; `run.started` attributes `agent`, `delegation_index`, `tools_effective`, `read_only`,
  `time_limit_s`; `run.completed` adds `delegation_status`, `failure_code`, `model_turns`,
  `artifacts`, `validated` and the usual `llm_calls`, `tool_calls`, `input_tokens`,
  `output_tokens`. The parent turn's `run.completed` adds `delegations` and
  `delegations_refused`.
- **Activity.** While a delegation runs, its parent turn's `chat_turn` item in `/api/activity`
  carries `delegations: <running count>`, and the turn's progress snapshot carries
  `delegations_running` (both only when non-zero). Sub-runs are not persisted; rule 19's restart
  check already waits for the turn.

### Delegation progress lines, 委派紀錄 and the Settings switch (V1, person-facing)

Code: `src/agent/turn_progress.py` (`TurnProgress.delegation_started`, `SubAgentProgress`,
`delegation_lines`); `src/host_runtime/delegation_record.py`; `src/host_runtime/multi_agent_switch.py`;
`ConversationMessage.delegations` (`src/host_runtime/conversations.py`); the page
(`src/host_runtime/web_page.py`); Telegram (`src/channels/telegram.py`). Tests:
`tests/test_multi_agent_ui.py`. Additive: a turn without a delegation shows and stores exactly what
it did before.

- **Progress hook** (for the core's `DelegationService`): `TurnProgress.delegation_started(profile_key,
  objective, *, read_only) -> SubAgentProgress` opens one sub-agent line under the running turn. The
  sub-run sets the returned object as `TURN_PROGRESS` (instead of `None`), so its own `set_limits`,
  `tool_started`, `tool_finished` count on its line, never on the parent's (`begin_pass` does not reset
  it: the whole sub-run is counted); `finish(status)` takes a `DelegationResult.status` when it ends. A
  `SubAgentProgress` cannot open a line itself (depth 1). `delegation_changed(±1)` keeps working; the
  snapshot's `delegations_running` is the larger of that counter and the running lines, so a caller
  reporting both is not counted twice.
- **Snapshot** (`/api/conversations/progress`, only to the turn's own actor): `delegations` (absent when
  the turn started none), at most 6, each `{index, profile: "namespace/name", objective, status:
  "running" | "done" | "needs_input" | "awaiting_approval" | "failed", label, read_only, tool_count,
  tool_cap, elapsed_s}`. `objective` is the one deliberate exception to "names and numbers only": the
  first 60 characters of the objective the parent model wrote, on one line, credential-shaped text
  cut out (`SECRET_PATTERN`). Telegram's status message adds `delegation_lines` (one line per
  sub-agent and its objective) under the same throttle (at most one edit per second per chat).
- **委派紀錄** (`delegation_record.records_from`): from the turn's `agent__delegate` executions (host
  data `delegation`, read as JSON); a refusal (the contract's refusal codes: no sub-run) is left out;
  at most 6. Each record: `{profile, status, summary (≤ 280 characters, one line), validated,
  artifacts: [{kind, id, name, status?, path?}], tokens: {input, output, model_calls}, tool_calls
  (count), elapsed_s, failure_code?, question?, host_note?}`. A `file` artifact's `path` is resolved
  through the session ledger for this session and actor only; Agent Web lists those files on the
  answer (`attachments`) so the existing token-checked file viewer opens them. Stored as
  `ConversationMessage.delegations` (≤ 6, assistant messages only; default empty). Telegram appends
  `text_lines(records)` ("委派紀錄", then per sub-agent its status, time, tokens, summary or question,
  and artifact ids) before the task result summary; a long reply follows the existing file fallback.
- **Settings switch**: `GET /api/settings/multi-agent` → `{ok, supported, writable, enabled (saved in
  host.json), running (what the running Agent read at start), restart_needed}`; `POST` `{"enabled":
  bool}` writes `multi_agent.enabled` through `CompanyHostConfiguration` (the rest of host.json
  unchanged) and answers the same shape, or 409 with `multi_agent_settings_invalid`,
  `settings_read_only` (no host.json in this launch mode) or `multi_agent_unsupported` (a contract
  without the field). It never changes the running configuration: the flag applies after a restart.


## Coding change at scale

`coding/change@1.0.0` (Workflow `engineering/coding-change@1.1.0`), `docs/phases/CODING_AT_SCALE.md`.

- Request `coding.change.input.v1` adds `more_files: list[str]` (optional, at most 9): files the run may change
  besides `file`, each refused like `file` (`coding_file_is_a_test`, `coding_file_not_writable`,
  `coding_path_invalid`).
- Host binding `coding` adds `author_max_turns` (4–100, default 30), `author_max_output_tokens` (1,000–64,000,
  default 8,000), `change_max_processes` (1–16, default 1); each repository may add
  `checks: [{"name", "module", "args"}]` (at most 5, unique names), run as `python -m <module> <args>` with
  `{files}` expanded. Commands run in order `pytest-new`, `check-<name>`…, `pytest-suite`; a failed check is
  `check_failed` (or `check_timeout`) with the tool's scrubbed output.
- Author answers (`coding.change-author.v1`), one JSON object per turn: `{"action": "list"|"outline"|"read"|
  "search"|"edit"|"done", ...}`; `edit` carries `edits: [{"path", "old", "new"}]`. A legacy
  `{"content": ...}` replaces the primary file. New stop codes: `author_turns_exhausted`,
  `author_change_has_credential`, `author_file_not_utf8`, `author_file_mixed_newlines`.
- Result unchanged: `diff` covers every changed file; never committed.

## Knowledge repositories: folder, commits, push, revert, tags (R1, 2026-10-30)

Design: `docs/phases/KNOWLEDGE_REPO.md` §4–§7; decision `docs/DECISIONS.md` 2026-10-30 "One version
mechanism for every knowledge base". Code: `src/knowledge/repo/repository.py` (package
`knowledge.repo`). Tests: `tests/test_knowledge_repo.py` (two PCs as two workspaces sharing one folder,
a minimal test type). R1 is the type-agnostic layer only: no type, route or page uses it yet (R2 BI, R4
wiki, R5 routes and page).

- **Types.** A type implements `RepoType`: `name`, `unit_problem(key, value) -> str | None` and
  `check(before, after) -> CheckReport(blocking: list[str], notes: list[str])`, and is added with
  `register_type`. `repo.json` names it; an unknown type is `repo_type_unknown`. The engine reads only
  units: a key (1–300 characters, no control characters) and a JSON value. Reserved keys every type
  shares: `schema` (the current schema version) and `skill:<name>` (a skill's current revision).
- **Folder** `<parent>/<repo id>/` (id `[a-z0-9]+(-[a-z0-9]+)*`, at most 40): `repo.json` =
  `{"format": "aep.knowledge.repo/v1", "id", "title", "purpose", "type", "created", "created_by"}`,
  written once; `REPO.md` (derived, for people); `schemas/`, `skills/`, `sources/` (files, written
  once); `commits/<author>/<seq>.json`; `tags/<name>.json`; `publish/<author>/<seq>.json`. Every record
  is written once (temporary file + rename) and a record path that exists is refused (`record_exists`);
  a PC writes only its own author folders. Author `[a-z0-9]+([._-][a-z0-9]+)*`, at most 40.
- **Per PC** `<workspace>/knowledge-repos/`: `registry.json` = `{"repos": [{"id", "path", "author",
  "type"}]}`; `<repo id>/repo.sqlite` (applied commits in order, units, conflicts, cached file hashes);
  `<repo id>/work/` (`pending.json` = `{"sets": {unit: value | null}, "files": {path: {"sha256",
  "bytes"}}}`, staged files under `files/<path>`, local commits `commits/<n>.json`,
  `resolutions.json`). `create(workspace, parent, repo_id=, title=, purpose=, kind=, author=)` and
  `join(workspace, folder, author=)` register a repository; `Repository(workspace, repo_id)` opens it.
- **Commit** `commits/<author>/<seq>.json`: `{"format": "aep.knowledge.commit/v1", "id", "repo",
  "author", "seq", "clock", "base": commit id | null, "created", "purpose", "kind": "change" | "import"
  | "revert" | "schema", "restores"?: commit id (revert only), "files": [{"path", "sha256", "bytes"}],
  "ops": [{"unit", "value": JSON | null, "base": sha256 | null}]}`. `id` = sha256 of the canonical JSON
  (sorted keys, no spaces, UTF-8) without `id`; an op's `base` = sha256 of the canonical value it
  changed (null: the unit was absent); `value` null removes the unit. `purpose` is required, 1–500
  characters (`purpose_missing`, `purpose_too_long`). A file path is under `schemas/`, `skills/` or
  `sources/`, POSIX, no `..` or hidden parts, at most 240 characters (`path_invalid`); a path that holds
  other content is `path_taken` (files never change).
- **Order and replay.** Commits apply in (clock, author, seq) order. On push, `seq` = 1 + the author's
  highest file and `clock` = 1 + the highest clock of any commit or publish record. An op applies when
  the unit's value hashes to `base` or already equals `value`; otherwise it is an open conflict (the
  same on every PC) and the unit keeps its value; a later commit that sets the unit marks open
  conflicts on it `superseded`. A commit with a missing file waits (`waiting`); one whose file content
  differs is reported (`changed`) and not applied; an invalid one is reported (`bad`, for example "id
  does not match the content"); unreadable JSON is `incomplete` and retried. A new commit with an
  earlier key than the last applied, or an applied commit that changed or vanished, rebuilds the state.
  `sync()` returns `{"applied", "rebuilt", "conflicts", "waiting", "changed", "bad", "incomplete"}`.
- **Working copy.** `stage(unit, value)` (checked by the type, `unit_invalid`), `stage_file(path,
  source)`, `discard()`, `commit(purpose)` (one local commit of every uncommitted change;
  `nothing_to_commit`), `drop_local_commit(n)`. `working_units()` = head + local commits + pending.
- **Push** `push()` → `{"status": "nothing"}`, `{"status": "conflicts", "conflicts": [{"unit", "mine",
  "theirs", "purpose"}]}`, `{"status": "blocked", "blocking", "notes"}` or `{"status": "pushed",
  "commits": [{"id", "seq", "purpose"}], "notes", "sync"}`. It syncs, rebases the local commits unit by
  unit onto the head (a unit changed on both sides differently is a conflict unless `resolve(unit,
  "mine" | "theirs" | "value", value)` decided it), runs the type's `check`, copies files into the
  folder, then writes the commits. Nothing is written on `conflicts` or `blocked`.
- **Revert** `revert(version, purpose)`: version = tag name, commit id or a unique id prefix of 8+
  characters (`version_unknown`); needs no local commits or uncommitted changes (`work_not_clean`);
  writes one local `revert` commit with `restores` that sets every unit differing from that version
  (`nothing_to_revert` when none). History is never rewritten.
- **Tags** `tags/<name>.json` = `{"format": "aep.knowledge.tag/v1", "name", "commit", "by", "at",
  "purpose"}`, name `[a-z0-9]+([.-][a-z0-9]+)*` at most 60 (`tag_invalid`), never moved
  (`tag_exists`); `tag(name, purpose, version=None)` tags the head by default.
- **Publish** `publish(tag)` writes `publish/<author>/<seq>.json` = `{"format":
  "aep.knowledge.publish/v1", "repo", "author", "seq", "clock", "tag", "commit", "at"}` (`tag_unknown`).
  The published version is the newest valid record in (clock, author, seq) order whose tag still names
  its commit; publishing an older tag again withdraws a newer one. Callers make sure a person confirmed
  it; the model never publishes. `published_units()` is what the Agent reads: the published version, or
  the head when never published (or while the published commit has not arrived here).
- **Reading.** `status()` = `{"id", "title", "type", "author", "head", "behind", "ahead",
  "uncommitted", "conflicts", "waiting", "bad", "published", "schema"}`; `units()`, `state_at(commit)`,
  `history(limit)` (newest first: id, file, author, created, purpose, kind, restores, units, files),
  `diff(commit)` (unit, before, after), `conflicts(status)`, `tags()`, `published()`.

## Knowledge repositories: the BI type (R2, 2026-10-30)

Design: `docs/phases/KNOWLEDGE_REPO.md` §3, §5, §8. Code: `src/capabilities/bi_cards/vault.py` (type
`bi`, registered on import), `store.py` (`card_id_for`, the vault hook in `BiStore._db`), routes in
`src/host_runtime/bi_vaults_api.py`. Tests: `tests/test_bi_vault.py` (two PCs, a helper plays OneDrive).
Supersedes "BI vaults: folder, change files, sync (V4)" with no compatibility (owner decision 10): a
V4 folder (`vault.json`, `changes/`) is not read, is left untouched and is skipped in the list; the one
V4 vault in use (`market-bi`) is rebuilt as a repository in slice R6 with the owner present.

- **A vault is a dataset and a repository.** Dataset `vault-<id>` (registry
  `<workspace>/bi/vaults/registry.json`, local `bi.sqlite` under `<workspace>/bi/vaults/<id>/`) and
  repository `<id>` of type `bi` (R1 registry). Every `/api/bi/*` route takes the dataset unchanged.
- **Folder** = the R1 folder: `repo.json` (`type: "bi"`), `REPO.md`, `schemas/<schema id with / as
  __>@<version>.json` (every schema version the vault used, built in or installed; an installed one
  is copied byte for byte, a built-in one as its canonical JSON), the homes (`applications/<application>/`
  and `library/<entry>/`, "BI card model: folder layout" below), `commits/`, `tags/`, `publish/`. A vault
  from before the homes keeps `skills/`, `sources/applications/<segment>/` and `sources/library/<entry>/`.
  No database file is ever written to the folder.
- **Units.** `schema` = `<id>@<version>`; `meta:<key>` (dataset meta: `vault_segments`,
  `vault_coverage`, the domain configuration, ...); `card:<card id>` = `{"type", "key", "name",
  "synthetic"}`; `field:<card id>:<field>` = `{"value", "source": {kind, ref, by, at} | null,
  "history": {kind, ref, by, at, import_id, reason, old_source} | null}`; `evidence:<card id>:<field>`
  = list of evidence rows; `proposal:<key>`; `import:<import id>` = `{"filename", "entity_type", "at",
  "by", "run_id", "undone"}`; `decision:<sha16>` = a person's decision on a replay conflict. Card id =
  `card_id_for(type, key)` = `sha256("<type> <key>")[:12]`, the same on every PC.
- **Writes.** A store write to a vault dataset runs on `bi.sqlite` in a transaction that is always
  rolled back; the units it changed are staged (`stage_many`, one write of the working copy) and
  `bi.sqlite` is rebuilt from head + local commits + uncommitted changes. The store's refusals are
  unchanged and stage nothing. A new import (「確認匯入」) commits at once (kind `import`, purpose
  drafted as `匯入 <files>：<n> 張卡、<m> 個欄位` unless the caller gave one with `vault.purpose()`);
  every other write waits for a person's commit. Field history is derived from the commit log, so it is
  the same on every PC. A field op that lost a replay race becomes a pending proposal of kind
  `conflict` (decided with the proposal route; the decision is the `decision:` unit).
- **Schemas.** Before push and on join/sync every file in `schemas/` is installed; one whose content
  differs from this PC's copy of the same version is 409 `schema_mismatch` (`file`, `reason`): the
  vault's file is authoritative. A built-in version with the same content counts as installed. A
  schema upgrade stages the new `schema` unit and its file.
- **Routes** (errors `{"ok": false, "code", "message"}`):
  - `GET /api/bi/vaults` → `{"vaults": [{"id", "dataset", "title", "purpose", "schema", "path",
    "author", "reachable", "cards"}]}`.
  - `POST /api/bi/vaults {"path", "title", "purpose", "schema", "author", "id"?, "segments"?,
    "coverage"?}` → `{"ok", "vault", "push", "sync"}`: creates the folder and pushes one `schema`
    commit `建立知識庫，使用 schema <ref>`.
  - `POST /api/bi/vaults/join {"path", "author", "resume"}` → as create; an author with commits in
    the folder is 409 `author_taken` unless `resume`.
  - `POST /api/bi/vaults/convert {"dataset", "path", "purpose", "author", ...}` → as create plus
    `"dataset"`: one pushed `import` commit holding every unit of the dataset; the dataset is not
    changed.
  - `GET .../<id>/status` (vault header + R1 `status()` + conflicts), `GET .../<id>/pending` →
    `{"uncommitted": [{"unit", "before", "after"}], "files", "commits"}`, `GET .../<id>/history?limit`
    → `{"commits", "tags", "published"}`, `GET .../<id>/diff?commit=<id>` → `{"changes"}`.
  - `POST .../<id>/sync`, `commit {"purpose"}`, `push`, `resolve {"unit", "choice": "mine" | "theirs"
    | "value", "value"?}`, `discard`, `revert {"version", "purpose"}`, `tag {"name", "purpose",
    "version"?}`, `publish {"tag", "confirm": true}` (400 `confirm_required` otherwise; only a
    person's click sends it, never the model).
  - Errors: R1 codes (`purpose_missing`, `nothing_to_commit`, `version_unknown`, `tag_invalid`, ...)
    as 400; 409 `record_exists`, `path_taken`, `tag_exists`, `work_not_clean`, `schema_mismatch`,
    `author_taken`, `vault_exists`, `vault_unreachable`; 400 `repo_invalid` (not a BI repository).
- **When it syncs.** Before every write, on push and on `POST .../sync`; reads do not sync.

## Knowledge repositories: skills, REPO.md, the wiki type, the BI schema document (R3–R5 cores, 2026-10-30)

Design: `docs/phases/KNOWLEDGE_REPO.md` §3, §8, §9, §11. Library layer only: no route or page calls these
yet (R3 BI wiring, R4 rest, R5). Tests: `tests/test_knowledge_repo_skills.py`,
`tests/test_knowledge_repo_readme.py`, `tests/test_knowledge_repo_wiki.py`, `tests/test_bi_schema_doc.py`.

- **Skills** (`knowledge.repo.skills`, every type). A revision is the file
  `skills/<name>/rev-<n>-<author>.md`, written once: frontmatter (`name`, `revision`, `schema`, `role`,
  `applies_to`: list of folder prefixes, optional `card_types`, `table_recipes`; one `key: value` per
  line, lists and objects as JSON) and the instructions as body. Unit `skill:<name>` = `{"path",
  "revision", "schema", "role", "applies_to", ...}` makes a revision current, so skills are committed,
  merged and reverted like everything else. `stage_skill` writes the next revision and stages the unit;
  `current_skills` lists them with `needs_update` when a skill's `schema` is not the `schema` unit;
  `runnable(name)` refuses such a skill (`skill_needs_update`); `skill_for(source, role)` picks the
  current skill of that role with the longest `applies_to` prefix of the source path.
- **REPO.md** (`knowledge.repo.readme`). `readme_text(repo)` is derived from the pushed commits, tags
  and publish records only (no clock time; the same records give the same text): title, purpose, type,
  schema, skills, published version, tags, recent commits with purposes, and how to maintain.
  `write_readme(repo)` rewrites it; it is the only file in a folder that is ever rewritten and never
  the source of truth.
- **Wiki type `wiki`** (`knowledge.repo.wiki`, registered on import of `knowledge.repo`). Units:
  `page:<path>#(preamble)` = `{"body"}`; `page:<path>#<section key>` = `{"pos", "heading", "body",
  "correction"?: {"reason", "source"}}` (section keys as K3.2: heading text, duplicates `Heading (2)`);
  `front:<path>:<field>` = `{"pos", "text"}`; `front:<path>:(other)`. Pages: `index.md`, `log.md`,
  `decisions.md`, Markdown under `wiki/`; `wiki/paths/` is refused (people only, K3). `check` blocks a
  push that drops a sourced line unless its section carries a correction with reason and source, and
  runs the benchmark callable set with `set_benchmark` (without one the push notes it did not run).
  `stage_page(repo, path, text | None)`, `import_vault(repo, folder)` (pages as units, `raw/` and
  `drop/` under `sources/`, `CLAUDE.md` as the first schema, `skills/*/SKILL.md` as first skill
  revisions; then `commit(purpose, kind="import")`), `materialize(units, target)` writes a state as a
  read-only Obsidian-readable folder. Since R4a (2026-10-30): `schema` = `wiki.schema@<version>`
  (file `schemas/wiki.schema@<version>.md`, copied as `CLAUDE.md`); `skill:<name>` is the shared object
  form (role `ingest`; an imported `SKILL.md`, frontmatter included, is revision 1's body and comes back
  unchanged as `skills/<folder>/SKILL.md`); `raw:<path under raw/>` = `{"file": "sources/…",
  "sha256"}` for each imported Raw file, restored by `materialize` as `raw/<path>` (`drop/` originals
  stay in `sources/` only).
- **BI schema document** (`capabilities.bi_cards.schema_doc.schema_markdown(reg)`): a schema as
  Markdown for people (each type, its fields with kind, label, allowed values, link target and
  required, and the links between types). Pure; meant to sit beside the JSON in `schemas/`.

## Knowledge repositories: the Agent reads the published version, the 「版本」 area (R5, BI, 2026-10-30)

Design: `docs/phases/KNOWLEDGE_REPO.md` §7, §9, §10; decision `docs/DECISIONS.md` 2026-10-30 "How the Agent
picks up a newly published BI version". Code: `src/capabilities/bi_cards/vault.py` (`Vault.reads`,
`refresh_published`, `reading_store`, `unit_label`), `store.py` (`BiStore(..., view=)`), `capability.py`,
the page in `src/host_runtime/web_page.py`. Tests: `tests/test_bi_vault_published.py`,
`tests/test_bi_vault_ui.py`. The wiki side follows R4's wiring.

- **What the Agent reads.** `bi__query` on a vault dataset syncs (as before), then reads
  `vault.reading_store(workspace, dataset)`: `BiStore(workspace, dataset, view=<local>/published)`, a
  read-only store (`read_only`, no `vault_id`) over `published/bi.sqlite`. That database is rebuilt from
  the units of the published commit, or of the pushed head when no publish record is applied here, when
  that target differs from `published/version.json` (`{"tag": str | null, "commit": str | null}`).
  This PC's local commits and uncommitted changes never reach it. The answer's `scope_note` says
  `內容來自發佈版本 <tag>` or that the vault was never published. Unreachable folder: the last copy built
  here, or `vault_unreachable` when there is none. Every other dataset is read as before.
- **Status** `GET /api/bi/vaults/<id>/status` adds `"reads": {"tag", "commit"}` (null when the folder is
  unreachable).
- **Words for units.** `pending` changes, push `conflicts` and `diff` changes carry `label`: a card as
  `<type>「<name>」`, a field as `<card> 的 <field>`, evidence as `<card> 的 <field> 證據`, `meta:domains`
  as 「領域設定」, `schema` as 「schema 版本」.
- **Files written.** `REPO.md` is rewritten (`knowledge.repo.readme.write_readme`) after create, convert,
  a push that wrote commits, a tag and a publish. Staging a schema also stages its readable
  `schemas/<schema id with / as __>@<version>.md` (`schema_doc.schema_markdown`) when the folder has none.
- **Page** (step 1 「知識庫」, a vault chosen): the status line (cards, behind, ahead, uncommitted, last
  sync; waiting files, open replay conflicts and unreadable files as warnings), 「版本」: what the Agent
  reads; uncommitted changes and unpushed commits; Commit (purpose required), 「Push 給大家」,
  「捨棄還沒 commit 的改動」 (confirm); push conflicts side by side with 「用我的」, 「用別人的」 and, for a
  field, 「自己填」 (`resolve` with `value`: my unit with the typed value), then push again; history (30
  newest) with 「看改動」 (diff), 「回到這個版本」 (revert, purpose asked inline, a new local commit), 「加
  tag」 (name asked inline, the commit's purpose as the tag's) and 「發佈 <tag>」 (a `confirm()` click
  sends `confirm: true`); the published tag is marked 「發佈中」.


## Knowledge repositories: skills of a BI vault (R3, BI part, 2026-10-30)

Design `docs/phases/KNOWLEDGE_REPO.md` §8; owner decisions 2 and 3; decision "Skills of a BI vault: which
source folder, and what an AI run reads (R3, Claude Code)". Code: `src/capabilities/bi_cards/vault_skills.py`,
`vault.py` (`skills`, `save_skill`, the capture hook), `ai_runs.py` (`start(..., folder=)`), routes in
`src/host_runtime/bi_vaults_api.py`, the page in `web_page.py`; Session B on a skill
`src/capabilities/bi_cards/skill_session.py` (2026-10-31). Tests: `tests/test_bi_vault_skills.py`,
`tests/test_bi_skill_session.py`, `tests/test_bi_vault_ui.py`. Format, binding and 「需要更新」 are the shared
skills contract above.

- **Classify skill.** Creating or converting a vault stages `library/skills/classify/rev-1-<author>.md`
  (role `classify`, no `applies_to`, frontmatter `generated: "true"`): the schema's card types with labels,
  the vault's applications (`applications/<folder>/sources`) and library entries. After a schema change
  staged on the vault, a classify skill whose text is still the one generated for the old schema gets a new
  generated revision for the new one; an edited one is kept and is 「需要更新」.
- **Domain notes become extract skills.** Whenever `meta:domains` changes in a vault (domain save, convert),
  each domain's non-empty `notes` is staged as skill `<domain id slug>-extract` (role `extract`, `domain`
  in the frontmatter, `applies_to` the sources of the applications matching the domain's segment ids or
  labels, else `applications/<domain id slug>/sources`, plus the same applications' old
  `sources/applications/<folder>` when the vault has a source there; an existing skill keeps its folders
  and card types), and the
  configuration is staged with every `notes` empty. A plain dataset keeps its notes (V11 unchanged).
- **AI run in a vault.** `POST /api/bi/runs` takes `folder` (`sources` by default; anything but a home's
  `sources` folder, or `sources` and what is under it, is `folder_invalid`, 400). The run uses the classify skill and the extract skill of that folder
  (`skill_for`, longest `applies_to` prefix); either one written for another schema version refuses the
  run with `skill_needs_update` (409, `skill`, `skill_schema`, `schema`). Their text follows the fixed
  evidence rules in the system prompt under "The knowledge base's own rules (its domain notes, or in a vault
  its skills)", each headed `Classification|Extraction (skill <name>, revision <n>):`. With no `types`
  given, the extract skill's `card_types` (those in the schema) choose them. The run layout keeps
  `skills: {"folder", "text", "skills": [{"name", "revision", "role"}], "card_types", "schema"}`; a retry
  reads the same text.
- **Routes.** `GET /api/bi/vaults/<id>/skills` → `{"skills": [{name, revision, path, schema, role,
  applies_to, needs_update, card_types, body, generated} | {..., "problem"}], "schema", "folders" (every
  folder under `sources/`, with `sources`), "roles": ["classify", "extract"]}`. `POST
  /api/bi/vaults/<id>/skills` `{name, role (classify|extract), applies_to?, card_types?, body}` stages the
  next revision bound to the vault's current schema (`skill_invalid` 400 for another role, a type the schema
  lacks, a folder outside `sources/`, an empty body or a bad name) → `{"ok", "skill": {name, path, revision,
  schema, role, applies_to}, "status"}`. The person commits and pushes it like any change. The unit's label
  is `skill「<name>」`.
- **Page.** 「版本」 lists the skills (分類／擷取, revision, 「依 schema 產生」, 「需要更新」 with the vault's
  schema), 「修改」 and 「新增擷取規則」 open one form (name, kind, folders, card types, text) saved as a new
  revision; step 3 shows 「來源在知識庫的哪個資料夾」 for a vault and sends it as `folder`. Saving domain
  settings on a vault says the notes moved to the skills.
- **Session B on a skill** (2026-10-31). The sessions of "BI method sessions" with `kind: "skill"`:
  `POST /api/bi/sessions {"dataset": "vault-<id>", "kind": "skill", "target": <skill name>}` → `{"ok",
  "session"}` (`target_ref` `skill:<name>`; `not_a_vault` 400 for another dataset, `skill_unknown` 404).
  `POST /api/bi/sessions/<id>/turns {"dataset", "message", "source_ids"?, "run_ids"?}`: one model call per
  attempt, structured output, no tools, output contract `aep.bi.skill_suggestion.v1`; the system message
  holds only the rules; the schema ref, card types with fields, the source folders, the skill now (name,
  role, revision, schema, applies_to, card_types, body; a 「需要更新」 skill is asked to be brought to the
  current schema), sample excerpts and the dataset's last two trial runs (or `run_ids`) go in a user
  message, excerpts and run text between `DATA_FENCE`/`DATA_END`. `changes` may hold only `body`,
  `applies_to`, `card_types` (complete values); the changed skill is checked as `save_skill` checks it
  (`vault.checked_skill`, nothing written); otherwise asked again (3 attempts), then `model_output_invalid`.
  `<suggestion>` = `{"format": "aep.bi.skill_suggestion/v1", "reply", "changes", "reasons", "limits",
  "needs_engineering", "result": {"base_revision", "diff": [{"key", "before", "after"}]}}`; the assistant
  turn's `sent` has `skill_revision`. `POST /api/bi/sessions/<id>/apply {"dataset", "turn"}` stages the
  changes on the skill as it is now as its next revision (`save_skill`) → `{"ok", "session", "skill",
  "status"}`; the turn gets `applied: {"revision", "at", "by"}` (`suggestion_applied` 409 the second time).
  Page: each skill in 「版本」 has 「和 AI 一起修改」, opening the panel `#bi-b-ska` (target and model lines,
  the conversation, 「套用為新版本」).
- **Not done.** The model choosing a folder (the person chooses), and sources stored in the repository
  folder.

## Knowledge repositories: wiki repositories on this PC (R4a, 2026-10-30)

Owner decisions "Wiring the wiki type (R4)" (`docs/DECISIONS.md` 2026-10-30). Code:
`src/knowledge/wiki_repos.py`, routes `src/host_runtime/knowledge_repos_api.py`. Tests
`tests/test_knowledge_repos_api.py`, `tests/test_knowledge_repo_pipeline.py`, `tests/test_knowledge_repo_ui.py`.
The Knowledge page offers repositories beside sandboxes since R4b part 2; the sandbox, push and candidate
publish paths stay until R4c.

- **Registry.** A wiki repository is registered in the workspace (`<workspace>/knowledge-repos/registry.json`,
  type `wiki`), never in `host.json`.
- **Routes** (token-checked; JSON; errors `{"ok": false, "code", "message", ...}`; `*_unknown` → 404 except
  `commit_unknown`; `repo_exists`, `repo_registered`, `repo_unreachable`, `tag_exists`, `work_not_clean`,
  `path_taken`, `record_exists`, `target_not_materialized` → 409; others 400):
  - `GET /api/knowledge/repos` → `{"repos": [{id, path, author, title?, purpose?, reachable}]}`.
  - `POST /api/knowledge/repos` `{path, title, purpose?, id?, author?}`: a new repository folder
    `<path>/<id>` with the default schema `wiki.schema@1.0.0`, `index.md` (`# <title>`) and `log.md` in one
    `schema` commit, pushed → `{"ok", "repo": {id, title, purpose, path, author}, "push"}`.
  - `POST /api/knowledge/repos/import` `{source, path, title?, purpose?, id?, author?}`: a new repository
    holding the wiki folder `source` as one `import` commit, pushed (`import_vault`; the default schema
    when the folder has no `CLAUDE.md`) → adds `"imported": {pages, originals, raw, schema, skills,
    skipped}`. `source` is only read (`source_not_wiki` without `index.md` or `wiki/`; `path_invalid` when
    the new folder would be inside it).
  - `POST /api/knowledge/repos/join` `{path, author?}` → `{"ok", "repo", "sync"}`.
  - `GET …/<id>/status` → the engine status plus `repo`, `reachable: true`, `reads: {tag, commit}`; an
    unreachable folder → `{"repo": {id, path}, "reachable": false}`. `GET …/<id>/pending`,
    `…/<id>/history?limit=`, `…/<id>/diff?commit=` and `POST …/<id>/sync|commit|push|resolve|discard|
    revert|tag|publish` have the bodies and answers of the BI vault routes (R2, R5), with `label` on
    pending changes, push conflicts and diff changes: `<page> 的「<section>」`, `<page> 的開頭`, `<page> 的
    frontmatter <field>`, `raw/<path>`, `skill「<name>」`, `schema 版本`. `publish` needs `confirm: true`
    (`confirm_required`). `REPO.md` is rewritten after create, import, a push that wrote commits, tag and
    publish.
- **What the Agent reads** (`wiki_repos.reading_folder(workspace, id)`): syncs, then
  `<workspace>/knowledge-repos/<id>/published/vault`, materialized from the published commit (the pushed
  head when never published; never this PC's local commits or uncommitted changes) whenever that target
  differs from `published/version.json` (`{"tag", "commit"}`). The folder is a valid `knowledge.vault.Vault`
  (pages, `raw/`, `CLAUDE.md`, `skills/`, `README-AEP.md`). Unreachable shared folder: the last copy built
  here, else `repo_unreachable`.
- **The Agent's binding** (`KnowledgeHostBinding`): exactly one of `vault_root` (as before) and `repo` (a
  wiki repository id in this workspace's registry). `build_knowledge_catalog` registers a `repo` binding
  with `KnowledgeCatalog.register_live(manifest, source)`, the manifest being the asset's governed one
  from `assets/knowledge`; `source` is `wiki_repos.agent_source(workspace, repo)` → (the reading folder,
  its `version.json` text). `get` rebuilds when that text changes and returns the manifest with
  `vault_ref` and the three digests of the folder; on any failure it keeps the last entry (None before
  the first success: `knowledge_version_not_found`). `manifests()` lists a live entry by its last built
  manifest, or the template before the first `get`, without reading the folder. Agent Web shows the
  location as `knowledge repository <id>`. `knowledge_publish` refuses a `repo` binding
  (`knowledge_is_repository`).
- **Working folder** (`knowledge.wiki_work`, R4a part 3): `open_work(repo)` → `<workspace>/knowledge-repos/<id>/
  work-view/vault`, materialized from the working units (staged files read from the working copy) with an
  empty `drop/`, rebuilt when the working units differ from `work-view/state.json`. `capture(repo)` stages
  the folder's changes and returns `{"pages", "raw", "originals", "skills", "schema", "raw_changed"}`:
  pages (CRLF read as LF; a missing page is removed), new `raw/<path>` → `sources/<folder>/<sha8>-<name>` +
  `raw:<path>`, a changed or removed Raw file only listed in `raw_changed`, new `drop/<path>` →
  `sources/<folder>/<sha8>-<name>` (once per content), `skills/<folder>/SKILL.md` → next revision (role
  `ingest`, current schema, `folder` kept when it is not a valid name), `CLAUDE.md` → schema
  `wiki.schema@x.y.(z+1)`. Hidden files and folders are never staged.
- **Working folder against what it was built from** (R4b part 1): a build also writes the built pages to
  `work-view/base/` and the built Raw digests, skill-body digests and `CLAUDE.md` digest to `state.json`.
  `capture` stages only what differs from that base (for a page, the unit changes from the built page to
  the folder's page that differ from the working units), so a sync that brought someone else's change into
  the working units is never undone; it updates the base, and keeps `state.json`'s `units` only when the
  folder showed the working units before. `open_work` captures before every rebuild; a rebuild carries
  `drop/` and every hidden entry (`.plans/`, `.ingest-state.json`, `.benchmarks/`, `.reingest/` …) into
  the new folder. `reset(repo)` rebuilds without capturing. `wiki_repos` captures before `status`,
  `pending`, `commit`, `push`, `resolve` and `revert`; `discard` drops the staged changes and resets.
- **Per-PC settings** (owner 2026-10-31): `<workspace>/knowledge-repos/<id>/settings.json` `{intake,
  questions, pulled}`; `GET …/<id>/settings` → `{"settings"}`; `POST …/<id>/settings` `{intake?,
  questions?}` (absolute existing folders; empty clears; `path_missing`) → `{"ok", "settings"}`.
- **Pipeline steps on a repository** (R4b part 1): `Sandboxes.open("repo.<id>")` opens `open_work` with a
  `SandboxInfo` whose `repo`, `drop_root` (intake) and `questions_root` are set, `scope` None (every rule
  editable), `base_name` = the id; `record` saves `pulled` in the settings; `list` does not include it;
  `discard` → `repository_not_discarded`; an unknown repository → its `*_unknown` code. `drop-folders` with
  `base: "repo.<id>"` and `pull` read the intake folder (`intake_not_set`); `question-sets` reads the
  question folder (none set → no sets); `rule-write` of `checks/questions/<set>/<file>.md` writes into the
  question folder (`questions_not_set`), never into the repository; `merge` and the sandbox push
  (`/api/knowledge/push/start`) → `repository_uses_versions`. `/api/knowledge/pipeline/call` adds
  `"captured": <capture summary>` after a step whose `side_effect` is not `read` on a repository; a convert
  run captures when it ends. `/api/knowledge/benchmark/start` on a repository runs `wiki_bench.run`
  (`questions_not_set` without a question folder). `GET /api/knowledge/pipeline` adds `"repos"` (the
  listing above) and `"repo_prefix": "repo."`.
- **The Knowledge page** (R4b part 2, `web_page.py`): the start screen lists the repositories («知識庫（有版本
  紀錄）») beside the sandboxes, with a form to import a copy of a wiki folder, create an empty repository or
  join a shared folder (`/api/knowledge/repos`, `/import`, `/join`). An opened repository is the item
  `{sandbox_id: "repo.<id>", base_name: "repo.<id>", repo, scope: null}`, so every step passes `repo.<id>`.
  For a repository: step 1 shows this PC's folders (`#kp-repo-settings`, `…/<id>/settings`) and pulls from
  the intake folder; step 3 shows the 「版本」 area `#kp-ver` (reads, status counts, uncommitted changes with
  labels and staged files, purpose + Commit, Push 給大家 with conflicts to decide and the push notes or
  blocking reasons, discard; history with 看改動, 回到這個版本, 加 tag and 發佈 <tag> after `confirm()`)
  and hides the sandbox push card (`#kp-push-card`), the candidate merge/publish (`#kp-candidate`) and
  Discard sandbox.
- **Benchmark and push check** (`host_runtime.wiki_bench`): `run(workspace, id, ask, sets=, actor=,
  skill=, questions_fallback=)` captures, then runs `knowledge_bench.run_benchmark` with the working folder
  as `sandbox` and the pushed head (materialized at `work-view/head`) as `project`; the report (saved in
  the working folder's `.benchmarks/`) carries `pages_sha256`, the digest of the working pages.
  `gate(workspace, before, after)` is installed by `build_runtime` with `wiki.set_benchmark`: the newest
  `finished` run whose `pages_sha256` equals the pushed pages' digest blocks with `測試退步：<question>
  在 push 前答得對，現在答錯` per regression and notes `測試 <run>：<n>/<total> 題通過（push 前是 …）`;
  with no such run the note is `這次 push 的內容沒有跑過測試（…）` and nothing blocks.

## BI vault benchmarks (BI T1, 2026-10-31)

Design `docs/phases/BI_TEST_AND_TOOLS.md` §3; owner decisions `docs/DECISIONS.md` 2026-10-31 "BI step 3 and the
skill AI: owner decisions". Code `capabilities/bi_cards/vault_checks.py`, `host_runtime/bi_bench.py`; tests
`tests/test_bi_vault_bench.py`, `tests/test_bi_vault_ui.py`.

- **Units** (BI type, committed and pushed like cards; never rows of `bi.sqlite`):
  `check:question:<set>/<slug>` = `{"question", "must": [str], "must_not": [str], "home"?: <home>}` (set and slug `[a-z0-9-]`, at
  most 20 terms of 200 characters; `home` absent means the whole vault's, and an older AEP ignores it); `check:extract:<slug>` = `{"note", "folder": str|null, "expected":
  aep.bi.benchmark.expected/v1}` (refused when `benchmark.check_expected` finds a problem, e.g. a fact whose
  evidence is not in the note). Pending changes label them 「測試題「…」」 and 「擷取測試「…」」.
- `GET /api/bi/vaults/<id>/checks` → `{"questions": [{"unit", "set", "slug", "question", "must", "must_not", "home"}],
  "cases": [{"unit", "slug", "note", "folder", "expected"}], "latest": <report>|null, "standing": {"blocking":
  [str], "notes": [str]}}`. `standing` is the push check's answer for the working copy today, empty while a run is going. `?home=<home>` makes
  `latest` the newest report saying something of it: its own run, or a whole-vault run cut down to its questions and
  cases, or null. `newest` = `{"run_id", "status", "error"}` of the newest run of any kind, or null.
- A bench report records `published`: `{"tag", "commit", "at"}` of the version its 發佈版本 side read, or
  null when the vault was never published (acceptance F24; older reports lack the key). In `GET .../checks`,
  a finished `latest` carries `stale`: `{"stale", "content_changed", "published_changed", "compared",
  "published_now"}`. `published_changed` compares commits, or for an older report whether a publish came after
  it started; `content_changed` compares the working digest (a domain's run: that domain's digest). The push
  check is unchanged.
- `GET /api/bi/vaults/<id>/share` → what one share would carry (`docs/phases/BI_PAGE_SIMPLE.md` S6):
  `{"published": <publish record>|null, "commits": [{"id", "purpose", "author", "created", "pushed", "units",
  "homes"}], "older": int, "uncommitted": int, "uncommitted_homes": [str], "tags": [str], "running": bool,
  "domains": [{"home", "state": "passed"|"regressed"|"untested"|"stale", "questions", "tested", "passed",
  "regressed": [str]}], "standing": {"blocking", "notes"}}`. `commits` are those since the published version,
  pushed or only on this PC (`id` null), newest first, at most 50 (`older` counts the rest); `homes` is what each reaches,
  `*` for the whole vault. `domains` lists each domain with graded questions (`""` for questions of no
  domain) as the push check reads it, `stale` (舊結果) by the same rule as the report's `stale` below; `domains` and `standing` are empty while a run is going. Read only: the
  page sequences commit, push, tag and publish through their own routes, so the push check is unchanged.
- `POST /api/bi/vaults/<id>/checks`: `{"question", "must"?, "must_not"? (list or comma text), "set"? ("main"),
  "slug"?, "home"?}` stages a question (`question_invalid` 400); `{"kind": "case", "slug", "note", "expected",
  "folder"?}` stages a case (`case_invalid` 400); `{"delete": <unit>}` removes one (`check_unknown` 404). Answer
  `{"ok", "unit"?, "questions", "cases"}`.
- `POST /api/bi/vaults/<id>/bench` with optional `{"home"}` starts a run as an Agent Web background task
  (`bi-benchmark`) → `{"ok", "run_id"}`; `bench_empty` 400 (no checks, or none for that home), `home_invalid` 400,
  `bench_running` 400, `bench_unavailable` 400 (no runtime). With `home` it runs that home's checks only; without
  it, all of them, those of no home included.
  `GET /api/bi/vaults/<id>/bench?run=<run id>` → `{"report"}` (`run_unknown` 404).
- **A run.** Each graded question is asked twice through `Gateway.converse` as a Host sub-run
  (`running_sub_run("bi-benchmark")`: no memory, no session), `allowed_tools={"bi__query"}`, a role naming the
  vault dataset; `bi__query` is a turn-scoped Host tool (`agent.gateway.turn_host_tools`) whose
  `QueryHandler(store_for=...)` reads the working database (read-only view of `bi/vaults/<id>/bi.sqlite`) or
  the published one (`vault.reading_store`). Graded by `knowledge.questions.grade`. Each case is added as a
  source of the vault dataset and read by a trial AI run (`folder` picks the extract skill), scored by
  `benchmark.score`; a failing case is reported, the run goes on.
- **Report** `aep.bi.bench_report/v1` in `bi/vaults/<id>/benchmarks/<run id>.json`, saved after every step:
  `{"format", "run_id", "vault_id", "status": running|finished|failed, "started_at", "finished_at", "by",
  "units_sha256" (digest of the working units), "scope" (the home, "" for the whole vault; an older report has none), "not_covered": [unit], "finished_ns", "total" (of what it ran), "ungraded": [unit], "results": [{"unit", "set",
  "question", "working": {"ok", "grade": {"passed", "missing", "forbidden"}, "answer", "calls": [{"arguments", "status", "total"}] (what the model asked of `bi__query` and how many cards came back), "errors": [{"term", "kind": "missing" | "forbidden", "class", "why"}]}, "published": {...}}],
  "cases": [{"unit", "slug", "result"?: <benchmark.score>, "error"?}], "working_score", "published_score",
  "regressions": [unit], "error_classes": {class: count, on the working side}, "extract": <benchmark.summarize without notes>|null, "error"}`. `class` (`capabilities/bi_cards/error_class.py`, 2026-11-05) is `retrieval`, `relation`, `extraction`, `evidence`, `generation` or `unknown`; it never changes pass, fail, a regression or the push check.
- **Push check** (`vault.set_benchmark(partial(bi_bench.gate, workspace))`, set in `build_runtime`): each question's newest
  verdict from a finished run that still counts: the same `units_sha256`, or the same `digests[home]` for its home (`domain_reach`:
  the home's units and the shared ones). A regression blocks if the push touches its home, it has no home, or the push touches
  something shared; otherwise it is a note 「其他領域，不擋這次 push：…」. A report has `"digests": {home: sha256}`; one without counts only
  for identical content. `standing` answers the same for the working copy against the head. Without a counting run: the note
  「這次 push 的內容沒有跑過測試」.
- **定案:** `POST /api/bi/vaults/<id>/finalize` `{"card", "field", "value", "reason"}` → `{"ok", "card", "field", "closed"}`; `reason_required`
  400, `card_unknown` 404. Writes the value as a person's, with 「定案：<reason>」 in its history, closes open proposals on the field, and
  decides a push conflict on it as `mine`. Uncommitted, then ordinary commit and push.
- **Creating a domain** (`docs/phases/BI_PAGE_SIMPLE.md` §10): `POST /api/bi/vaults/<id>/homes` `{"name", "folder"?}`
  stages `meta:home:<id>` = JSON text `{"label", "domain"}` (`domain` empty when the schema has the home's own) and
  makes `applications/<id>/{sources,skills,tools,profile}` in the working copy → `{"ok", "home", "homes"}`. Refused 400:
  `home_name_missing`, `home_name_invalid`, `home_folder_needed` (no Latin letters in the name), `home_folder_invalid`,
  `home_reserved`, `home_exists` (a name, folder, case variant or schema alias of a home). Push and sync make the
  folders in the shared folder from the unit; no file marks them. The domain widens the vault's schema when read
  (`catalog.with_home_domains`); the schema file does not change.
- **A domain's Dashboard** (`docs/phases/BI_PAGE_SIMPLE.md` §12): `meta:dashboard:<home>` = JSON text `{"order", "hidden"}`, as
  `meta:dashboard`, which stays the vault's and the only one the feed reads. `GET .../analyses?home=` answers for that home,
  whose `order` holds only what it chose, and every analysis gains `filters_domain`. `POST .../analyses` `{"dashboard", "home"?}`.
  `GET /api/bi/dashboard?home=` draws it: no data-quality section, and a panel that does not read `domain` has `whole_vault: true`
  and 「（全庫資料）」 on its title. `apply` on an `analysis` session takes optional `"home"`.
- **Assigning what exists:** `GET .../assign-plan` writes nothing → `{"homes", "questions": [{"unit", "question", "home", "suggested",
  "basis"}], "analyses": [{"slug", "title", "on_vault_dashboard", "filters_domain", "suggested": [home], "kind": shared|one_domain|whole_vault,
  "basis"}]}`. `POST .../assign` `{"questions": {unit: home}, "analyses": {slug: [home]}}` stages the list, checked first (`assign_invalid` 400).
- **Working domain** (`docs/phases/BI_PAGE_SIMPLE.md` §9): `GET /api/bi/vaults/<id>/skills` adds `"default_types"` and `"homes":
  [{"home", "label", "folder", "domain": str|null}]`, built from units only: the vault's lists, created homes and homes
  holding a source. An empty folder makes no home. `GET .../pending` adds `"homes": [home]` to each uncommitted
  change, empty for what spans the vault. `POST /api/bi/sessions/<id>/turns` takes optional `"scope": <home>` for
  every kind (`home_invalid` 400): the turn starts with a line naming it. `apply` on a `questions` session takes
  optional `"home"`.
- **Page**: step 3 「題目與擷取測試」 (`#bi-b-bench`): the questions and cases with 刪除, the two add forms, 「跑測試」
  and the latest report (scores, regressions first, both answers, case scores and failed checks).

## BI skill AI on the Agent harness (BI T2, 2026-10-31)

Design `docs/phases/BI_TEST_AND_TOOLS.md` §4. Code `host_runtime/bi_skill_agent.py`; test
`tests/test_bi_skill_agent.py`. Extends "Session B on a skill" (R3 BI part) without changing its routes or
stored session shape.

- `POST /api/bi/sessions/<id>/turns` on a `skill` session in Agent Web runs the turn on the Agent harness:
  `Gateway.converse` as a Host sub-run (`running_sub_run("bi-skill")`), the Agent's model, role guidance with
  the rules, `ConversationLimits(tool_calls=40, time_limit_seconds=900)`, and only these turn-scoped Host
  tools (`turn_host_tools`): `bi_skill__sources`, `bi_skill__read_source {source_id, start?}` (6000
  characters, fenced, data class checked), `bi_skill__try {source_id, folder?, changes?}` (a trial run with the
  draft skill, `ai_runs.start(..., skill_draft=)`: nothing staged, no card written; returns the run id and its
  candidates), `bi_skill__compare {left, right}` (`methods.compare`), `bi_skill__test_cases {changes?}` (the
  vault's extraction cases read with the draft, scored), `bi__query` (the working copy, read-only), and
  `bi_skill__suggest {reply, changes?, reasons?, limits?, needs_engineering?}` (checked as before: unknown
  keys and an invalid skill come back to the model as a failed tool call to fix).
- A turn without a submitted suggestion but with an answer is a reply with no changes. The assistant turn's
  `attempts` counts suggest calls; `sent` adds `"harness": true` and `"tools": [{"name", "ok"}]`.
- Without the Agent Web runtime (`bench.skill_asker_for` absent) the turn is the one model call as before.
- **Draft skill in a trial run.** `vault_skills.run_rules(repo, folder, draft)`: the draft replaces the skill
  of its name, or is the extract skill of a folder it applies to; the run's `skills` list marks it
  `"draft": true`.
- Page: the panel's model line says the Agent handles it with tools; each answer lists the tools used.

## BI analyses by AI conversation (BI T3, 2026-10-31)

Design `docs/phases/BI_TEST_AND_TOOLS.md` §5. Code `capabilities/bi_cards/analyses.py`,
`capabilities/bi_cards/analysis_session.py`, `host_runtime/bi_analysis_agent.py`, `host_runtime/bi_harness.py`;
tests `tests/test_bi_analyses.py`, `tests/test_bi_vault_ui.py`.

- **Running.** Both run on a copy of the vault's working `bi.sqlite` with the view `card_values(card_id,
  entity_type, card, field, value)`. `run_sql`: one statement, read-only connection, an authorizer allowing
  only SELECT/READ/FUNCTION/RECURSIVE, 10 s, at most 2000 rows -> `{"columns", "rows", "truncated"}`.
  `run_python`: `python -I runner.py` in a scratch folder (empty environment, 30 s, output capped); the script
  gets `query(sql)` (rows as dicts) and `DB`, and sets `result` (`{"columns", "rows"}` or a list of dicts) ->
  the table plus `printed`. An audit hook refuses importing network, process and native modules (`socket`,
  `subprocess`, `ctypes`, `_winapi`, `multiprocessing`, `urllib.request`, ...), the events `os.system`,
  `os.exec*`, `os.spawn*`, `subprocess.*`, `socket.*`, `ctypes.*`, and writes, removes or renames outside the
  scratch folder. Failures are `analysis_failed` / `analysis_invalid` (400). Not a security boundary against a
  determined attacker (decision 2026-10-31 "AI analyses, implementation choices").
- **Unit** `analysis:<slug>` = `{"title", "question", "kind": "sql"|"python", "code", "chart": {"type":
  "table"|"bar"|"line"|"scatter", "x"?, "y"?, "series"?}}` (bar, line and scatter need x and y). Labelled
  「分析「<title>」」 in pending changes; committed and pushed like cards.
- `GET /api/bi/vaults/<id>/analyses` -> `{"analyses": [{"unit", "slug", ...}]}`. `POST .../analyses`:
  `{"save": {...}}` runs it once, checks the chart's columns against the result and stages it -> `{"ok", "unit",
  "table", "analyses"}`; `{"run": <slug>}` -> `{"ok", "analysis", "table"}` (`analysis_unknown` 404);
  `{"delete": <unit>}` -> `{"ok", "analyses"}`.
- **Sessions** of kind `analysis` (`POST /api/bi/sessions {"dataset": "vault-<id>", "kind": "analysis",
  "target": "new"|<slug>}`): each turn is a Gateway sub-run (`bi_harness.converse`, profile `bi-analysis`, 30
  tool calls, 600 s) with turn-scoped tools `bi_analysis__sql {sql}`, `bi_analysis__python {code}` (results
  capped at 60 rows for the model) and `bi_analysis__propose {reply?, title, slug, question?, kind, code,
  chart}` (run and checked; a problem is a failed tool result to fix). Without the Agent Web runtime:
  `harness_unavailable` 400. `<suggestion>` = `{"format": "aep.bi.analysis_suggestion/v1", "reply",
  "analysis": {...}|null, "preview": <table, 500 rows>|null, "result"}`; `sent` = `{"model", "harness": true,
  "tools", "analysis"}`. `POST /api/bi/sessions/<id>/apply {"dataset", "turn"}` saves it (`analyses.save`) ->
  `{"ok", "session", "unit", "table", "analyses"}`; the turn gets `applied: {"unit", "at", "by"}`.
- **Page.** Step 3 「分析與圖表」 (`#bi-b-an`): saved analyses with 執行 / 和 AI 一起修改 / 刪除 and the panel
  `#bi-b-ana` (conversation, SQL or script, chart preview, 「存成分析」). The Dashboard's 「分析」 card (`#bi-an-dash`)
  reruns up to 12 saved analyses on the current data. Charts are inline SVG drawn by the page.

## BI analysis feed for Atlas: parameters, fixture and golden answers (F1, 2026-11-01)

Design `docs/phases/BI_ANALYSIS_DASHBOARD.md` §4.1, §5, §6.1. Code `capabilities/bi_cards/analyses.py`
(parameters), `capabilities/bi_cards/feed.py` (the answers); fixture `scripts/bi_feed_fixtures.py`,
`tests/fixtures/bi_feed/`; tests `tests/test_bi_feed_fixtures.py`.

- **Analysis unit, additive keys.** `params`: `{"<name>": {"type": "enum"|"bool"|"date"|"text", "default"?,
  "values"?: [str], "values_from"?: "<Type>.<field>", "label"?}}` (names `[a-z][a-z0-9_]*`, at most 10; an
  enum needs `values` or `values_from`; a date default is `YYYY-MM-DD` or `today`). `requires`: `{"types":
  [...], "fields": ["<Type>.<field>"]}`. Both are stored only when given, so older analyses keep their value.
  An enum's values: its own `values`, else the schema field's allowed values, else (a field named `domain`
  without them) the schema's `domains`; an enum without a default takes the first value. Bound as SQL named
  parameters (`:domain`); a script reads `PARAMS["domain"]`. Wrong or unknown parameters: `param_invalid`.
  `analyses.digest(value)` = first 16 hex of sha256 of the canonical unit value.
- **`meta:dashboard`** (JSON text) `{"order": [slug], "hidden": [slug]}`: the feed's `order` is the listed
  slugs that exist, then the rest by slug, hidden ones left out (they stay in `analyses`).
- **Feed answers** (`feed.answer(workspace, method, path, query, origin) -> (status, body)`), as design §5,
  on the version `Vault.reads()` names: an analysis is listed when its unit is valid and the published schema
  meets `requires`; `params` are listed with enum `values` resolved and the default filled. Results are cached
  under `<vault local>/feed_results/<digest>/<commit[:16]>/<params hash>.json`. A SQL result not cached is
  computed on request; a script result is queued (`feed.enqueue`, run by `feed.drain`) and answered `409
  result_not_ready`. A failed analysis is cached as a failure and answered `409 result_failed`. Additive error
  codes beside the design's: `403 origin_refused`, `405 method_not_allowed`, `404 route_unknown`, `404
  vault_unknown`, `404 analysis_unknown`, `409 not_published` (never pushed), `409 vault_unreadable`.
  `feed.clock` gives `computed_at` (fixed by the fixture server and the contract tests).
- **Fixture and golden answers.** `python scripts/bi_feed_fixtures.py` rebuilds the fictional vault
  `feed-fixture` (35 cards; analyses `node-coverage` SQL table with `level`, `accounts-by-region` SQL bar,
  `tech-updates` script line, each with `domain`; tag `v1` published; a later pushed card and analysis
  `draft-only` that the feed never shows) with a fixed clock and seeded ids, and writes the answers on a fresh PC
  that joined it to `golden/*.json` (two-space JSON, LF) with the requests, statuses and order in
  `golden/requests.json` (`after_queue`: the queue was drained before that request). `--check` fails when a
  rebuild differs byte for byte. `.gitattributes` keeps `tests/fixtures/bi_feed/**` unconverted.

## BI analysis feed for Atlas: the routes in Agent Web (F2, 2026-11-01)

Code `host_runtime/bi_feed_api.py`, wired in `web.py` beside the telemetry reads; test
`tests/test_bi_feed_api.py` (replays `golden/requests.json` over real HTTP and compares every answer).

- `GET /api/v1/bi/*` is answered by `feed.answer` before the token check: no token; the loopback Host guard
  still applies (403); a request with an `Origin` that is not `http(s)://127.0.0.1|localhost|[::1][:port]`
  is `403 origin_refused`; a local origin gets `Access-Control-Allow-Origin: <origin>` and `Vary: Origin`.
  `POST` on the prefix is `405 method_not_allowed` without a token. Headers: `application/json;
  charset=utf-8`, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`.
- **Worker.** One daemon thread (`bi_feed_api.ensure_worker`, started by the first feed request or refresh)
  runs `feed.drain` when `feed.on_queued` fires, after `bi_feed_api.QUEUE_DELAY` seconds (0 in Agent Web).
- **Refresh.** `bi_feed_api.refresh(workspace, vault_id)` queues the published version's default results not
  cached yet (`feed.enqueue_defaults`); called after `POST /api/bi/vaults/join`, `.../sync`, `.../publish` and a
  person's `.../analyses {"run"}`. It never fails the person's request.

## BI analysis feed for Atlas: the fixture server (F3, 2026-11-01)

`python scripts/bi_feed_server.py --port 53611 [--queue-delay 2]` (run with AEP's own `.venv`, from the AEP
repository): a temporary workspace joins a copy of `tests/fixtures/bi_feed/vault/`, `feed.clock` is fixed to the
fixture's `computed_at`, the default results are computed, then it prints `ready
http://127.0.0.1:<port>/api/v1/bi` (flushed) and serves only the feed routes through `bi_feed_api` (any other
path: `404 route_unknown`; non-loopback Host: `403 host_refused`). A new script parameter answers `409
result_not_ready` and its result after `--queue-delay` seconds; every start begins with an empty cache (port 0
picks a free port). Test `tests/test_bi_feed_server.py` runs it as a separate process.

## BI analyses: parameters, requirements and the Dashboard's order on the page (P1, 2026-11-01)

Design `docs/phases/BI_ANALYSIS_DASHBOARD.md` §4.1. Code `analyses.py` (`listing`, `set_dashboard`,
`dashboard_layout`, `order`), `bi_vaults_api.py`, `bi_analysis_agent.py`, `web_page.py`; tests
`tests/test_bi_analysis_params.py`, `tests/test_bi_vault_ui.py`.

- `GET /api/bi/vaults/<id>/analyses` -> `{"analyses": [{"unit", "slug", ...stored value, "inputs": <params
  with enum values resolved from the working schema and the default filled>, "offered": <the schema meets
  requires>}], "order": [slug] (offered, not hidden, the Dashboard's order), "dashboard": {"order", "hidden"}}`.
- `POST .../analyses {"run": <slug>, "params"?: {...}}` -> `{"ok", "analysis", "params": <resolved>, "table"}`
  (`param_invalid` 400). `{"dashboard": {"order": [slug], "hidden": [slug]}}` stages `meta:dashboard` (JSON text,
  labelled 「Dashboard 的順序」 in pending changes) -> `{"ok", ...listing}`; `dashboard_invalid` 400.
  `{"save": {...}}` accepts `params` and `requires` and runs once with the defaults.
- The analysis AI's `bi_analysis__propose` takes optional `params` and `requires` (run with the defaults).
- **Page.** Step 3 「分析與圖表」 lists analyses in the Dashboard's order, each with parameter controls (`select`,
  checkbox, date or text input, `data-param=<name>`; a change reruns it), 上移 / 下移, 在 Dashboard 隱藏 / 顯示,
  and says when the schema does not offer it. The Dashboard's 「分析」 card draws `order` (at most 12) with the same
  controls. Chosen values and the last result are kept per analysis across redraws; a change to the analyses
  redraws the Dashboard card the next time it opens.

## BI analysis packs and the default pack (P2, 2026-11-01)

Design `docs/phases/BI_ANALYSIS_DASHBOARD.md` §4.2–§4.3. Code `capabilities/bi_cards/packs.py`,
`capabilities/bi_cards/pack_default/` (`_prelude.py` and one script per section); tests
`tests/test_bi_default_pack.py`, `tests/test_bi_vault_ui.py`.

- **Pack** `aep.bi.analysis_pack/v1` = `{"format", "id", "title", "version", "analyses": [<analysis unit value
  with "slug">], "report"?}`; every analysis is checked like a saved one (`pack_invalid` 400 for the whole pack).
- **`bi-market-default` 1.0.0**: the 27 sections of `dashboard.py` (§1–§19) and `market.py` (§20–§31,
  `pending_links`) as Python analyses (`code` = the prelude + the section, the coded function moved verbatim),
  `params` `domain` (enum, `values_from: Application.domain`, default `robotics`), `include_sample` (bool,
  false) and, for `stale`, `customer-contact`, `timing-gaps`, `today` (date, default today); `requires.types` =
  the types each section reads. Result table = the section's columns (+ `level` for sections that flag rows:
  `gap` for a red flag, `warning` otherwise); a card cell becomes the card's name. `report.kept` lists what is
  not in the pack: A, A2, A3 (chains, until D1/D3), the coverage matrix (until `tech_areas`), Q (quality stays
  its own check). `pending-links` gets the schema's link fields written into its `LINK_FIELDS` line on import.
- **Routes.** `GET /api/bi/vaults/<id>/packs` -> `{"packs": [{"id", "title", "version", "analyses", "usable":
  [slug], "skipped": [{"slug", "title", "missing"}], "kept"}]}`. `POST .../packs {"import": "bi-market-default"
  or <pack>}` stages the analyses the working schema satisfies (a vault without `meta:dashboard` takes the
  pack's order) -> `{"ok", "staged", "skipped", ...analyses listing}`; `{"export": {"id"?, "title"?,
  "version"?}}` -> `{"ok", "pack"}` (working analyses in the Dashboard's order; `pack_empty` 400).
- **New vaults** (`POST /api/bi/vaults`, `.../convert`) stage the default pack in their first commit unless the
  request says `"default_pack": false`.
- **Page.** Step 3 「分析與圖表」: 匯入預設分析包, 匯入分析包檔案 (JSON), 匯出分析包 (downloads `<id>.json`).
- **Scripts write UTF-8.** The runner reconfigures stdout/stderr to UTF-8 (`python -I` ignores
  `PYTHONIOENCODING`; Windows otherwise garbled every non-ASCII result).

## BI Dashboard tab draws a vault's analyses (P3, 2026-11-01)

Design `docs/phases/BI_ANALYSIS_DASHBOARD.md` §4.3. Code `capabilities/bi_cards/board.py`, `bi_cards_api.py`
(`/api/bi/dashboard`), `web_page.py`; tests `tests/test_bi_board.py`, `tests/test_bi_vault_ui.py`.

- `GET /api/bi/dashboard?dataset=vault-<id>&domain=&include_sample=&param.<name>=...` -> `{"domain",
  "include_sample", "source": "vault", "ordered": true, "params": <parameters some analysis declares beyond
  domain, include_sample and today, enum values resolved>, "summary": {"red", "warn", "stale"}, "sections":
  [<A, A2, A3 when the domain has chains>, <one per analysis in the Dashboard's order>, <Q quality>]}`. An
  analysis section = `{"id": slug, "title", "kind": "table", "chart", "columns" (without `level`), "rows",
  "flags" (from `level`: `gap` -> red 「缺口」, `warning` -> warn 「警告」), "note" (the question, or 「沒有畫出來：…」
  when it failed), "analysis": true, "truncated"}`; a text cell that names exactly one card becomes a link cell
  `{"card_id", "label", "cite"}`. Shared parameters (`domain`, `include_sample`, others given) go to every
  analysis that declares them; `today` is today. The working copy is drawn (like the rest of the page).
- Scripts run in their guarded processes, up to 6 at once; results are cached in memory (600) by (analysis
  digest, database file path/mtime/size, parameters).
- A dataset only on this PC (not a vault) keeps the coded Dashboard until P5.
- **Page.** The Dashboard keeps its own order for a vault (`ordered`), shows extra parameters in
  `#bi-dash-params` (a change redraws), draws bar/line/scatter analyses as charts and tables as before, opens a
  flagged analysis section. The separate 「分析」 card is gone (the Dashboard is the analyses).

## `bi__query` reads a vault's saved analyses (P4, 2026-11-01)

Design `docs/phases/BI_ANALYSIS_DASHBOARD.md` §4.3. Code `capabilities/bi_cards/capability.py`,
`capabilities/bi_cards/board.py` (`published_sections`, `saved_name`), `host_runtime/bi_cards_tools.py`; test
`tests/test_bi_query_analyses.py`.

- `bi-cards.query` input: `analysis` up to 60 characters (a coded name, `all`, or an analysis slug) and
  `params` (object, default `{}`); `domain` also fills a `domain` parameter not given in `params`.
- In a vault (not a benchmark's chosen store): when the published version has the analysis (`name`, or a
  coded name with `_` read as `-`, or `all` = every offered analysis in the Dashboard's order), it is run on
  the published copy with the parameters (an enum value matched without case) and answered as sections like the
  Dashboard's (`id`, `title`, `columns`, `rows`, `flags`, `chart`, `note`, `params`). Otherwise a coded name is
  answered by the coded section until P5; anything else is refused `analysis_unknown`; a wrong parameter
  `param_invalid`; a name that is neither a coded name nor a slug `invalid_input`.
- The tool schema's `analysis` is free text (vault slugs vary) listing the coded names; `params` is new.

## BI schema 3.0.0: technology areas, chains and card aliases (D1, 2026-11-01)

Design `docs/phases/BI_ANALYSIS_DASHBOARD.md` §3 (D1, and the schema part of D2). Generator
`scripts/build_bi_schema_v3.py` -> `src/capabilities/bi_cards/bi_schema_v3.json` (shipped after 2.0.0); test
`tests/test_bi_schema_v3.py`.

- `bi.schema/v1.1@3.0.0` = 2.0.0 plus fields only: `tech_areas` (list; allowed values = the shipped coverage
  matrix's areas `wireless-comm`, `rf`, `high-speed-io`, `power-generic-io`, `emc`; their labels as
  `enum_aliases`) on Account, CustomerProduct, Ecosystem and SupplyLink (the types placed by `segment`);
  `chain` (list; `CMP`, `PWR`, `THM` with 運算鏈 / 電力鏈 / 散熱鏈 as aliases) on Node after `layer`; `aliases`
  (list of other names, no allowed values) after `name` on every type named by `name` (not Signal).
- A bare `bi.schema/v1.1` now means 3.0.0 (new datasets and vaults); a 2.0.0 dataset or vault upgrades without
  moving a value. Session A's next local version is 3.1.0. The F1 fixture stays on 2.0.0.

## BI name matching from the cards' aliases (D2, 2026-11-01)

Design `docs/phases/BI_ANALYSIS_DASHBOARD.md` §3. Code `capabilities/bi_cards/names.py`, `importer.py`,
`ai_runs.py`; test `tests/test_bi_card_aliases.py`.

- `names.from_store(store, configured)` -> `Names`: every card's `aliases` value (schema 3.0.0) -> that card's
  name, compared loosely (`norm_key`), over the domain configuration's `name_aliases` (kept until D4; a card's
  alias wins). An import (card names and link targets) and an AI candidate (name, link fields) are resolved
  through it before keys are built or candidates merged.

## BI domain configuration migration (D3, 2026-11-01)

Extended by D4 (see "BI domain configuration removed (D4)"): the migration now covers local datasets and
every part of the configuration; the 「領域設定」 editor is gone.

Design `docs/phases/BI_ANALYSIS_DASHBOARD.md` §3. Code `capabilities/bi_cards/migrate.py`,
`bi_vaults_api.py`, `web_page.py`; test `tests/test_bi_migrate_domains.py`.

- `POST /api/bi/vaults/<id>/migrate-domains {}` (dry run) -> `{"ok", "dry_run": true, "vault", "schema":
  null|{"from", "to"}, "aliases": [{"card_id", "card", "type", "add": [alias]}], "missing": [{"alias",
  "name"}], "chains": [{"card_id", "node", "chain": [code]}], "dropped_chains": [code], "unknown_areas": [id],
  "removes": "meta:domains", "purpose", "token"}`; `domains_missing` 400 when there is no configuration.
  `{"apply": true, "token"}` -> one change commit 「把領域設定搬進 schema 與卡片」 (local, to push): the schema
  upgraded to the newest `bi.schema/v1.1` when it lacks Node `chain` or `aliases`, each alias added to its card's
  `aliases` (a card found by name, loosely; a missing one listed, never created), Node `chain` set from the old
  patterns and lists (codes the schema allows), `meta:domains` removed -> `{"dry_run": false, ..., "commit"}`; a
  changed vault since the dry run is `preview_stale` 409.
- **Page.** 「領域設定」 of a vault with a configuration: 「預覽：搬進 schema 與卡片」 lists the changes and what is
  not moved, then 「確認搬移（寫入一個 commit）」 or 「取消（不寫入）」.
- The guarded runner's temporary folder is removed with `ignore_cleanup_errors` (a Windows file still held
  briefly no longer fails an analysis).

## BI chains and coverage matrix as analyses (2026-11-01)

Design `docs/phases/BI_ANALYSIS_DASHBOARD.md` §3–§4.3. Code `capabilities/bi_cards/packs.py`,
`pack_default/chain_summary.py`, `chain_view.py`, `chain_overlap.py`, `coverage.py`, `board.py`; tests
`tests/test_bi_pack_chains.py`, `tests/test_bi_default_pack.py`.

- The default pack `bi-market-default` holds 31 analyses: `chain-summary` (A), `chain-view` (A2),
  `chain-overlap` (A3) first, the 27 sections of P2, then `coverage`. Its report lists only Q (quality stays a
  check).
- **Chains.** A Node card's chains are its `chain` values (schema order); a domain's chains are the schema's
  allowed `chain` values some Node of that domain carries; a chain's label is the value's first alias in the
  schema's `enum_aliases.chain` (else the code). Other cards reach a chain through the nodes they name
  (`node`, `nodes`, a Trend's `affected_nodes`), matched by the node card's name or key, without case.
  `requires`: type `Node`, field `Node.chain`; params `domain`, `include_sample`.
- **Coverage matrix.** One row per schema `segment` value x `tech_areas` value (schema order), every card of
  every domain (sample cards too), a card counted in each of its cells; a card value names an entry by value,
  label or alias, loosely. Columns `區段`, `技術領域`, `卡片數`, `類型` (`Type n、...`), `有來源比例` (sourced
  share of the filled own fields: a `ref` or fact evidence), `最新更新`, `最常空白的欄位（前 5）`. No params;
  `requires` fields `CustomerProduct.segment`, `CustomerProduct.tech_areas`.
- **Schema values in a script.** A pack script may hold the line `SCHEMA_VALUES: dict[str, Any] = {...}`;
  `packs.fill(code, registry)` sets it (with `LINK_FIELDS`) on import and when the built-in pack is drawn:
  `{"allowed": {"chain"|"segment"|"tech_areas": [[value, label, *aliases]]}, "fields": {Type: [own field]}}`.
  A schema upgrade after import does not refresh it (re-import the pack), as for `LINK_FIELDS`.
- **Board.** A Dashboard whose analyses include a chain analysis no longer draws the coded A–A3 from a domain
  configuration. Vaults created before this change get the new analyses by importing the pack again.
- **Golden answers.** `tests/fixtures/bi_default_pack/golden/<fixture>.json` (`aep.bi.pack_golden/v1`: `fixture`,
  `today`, `domains`, `made_from`, `results: {slug: {"<domain>|real"|"<domain>|sample"|"*": {"columns",
  "rows"}}}`) hold the coded Dashboard's answers on the fixtures of `tests/bi_pack_fixtures.py` (robotics, market,
  feed, chains; built under the feed fixture's fixed clock and seeded ids). The pack's parity tests compare with
  them, so they outlive the coded sections; `tests/test_bi_pack_golden.py` rebuilt them from the coded sections
  (`AEP_WRITE_PACK_GOLDEN=1` writes) and is removed with those sections in P5. After P5 the files are frozen: a
  deliberate change of an analysis's answer edits the golden file in the same commit, with the reason.

## BI coded Dashboard removed (P5, 2026-11-01)

Design `docs/phases/BI_ANALYSIS_DASHBOARD.md` §4.3. Code `board.py`, `capability.py`, `bi_cards_api.py`,
`bi_cards_tools.py`, `vault.py`, `web_page.py`; tests `tests/test_bi_board.py`, `tests/test_bi_cards.py`,
`tests/test_bi_quality.py`, `tests/test_bi_default_pack.py`, `tests/test_bi_pack_chains.py`.

- **Removed:** `capabilities/bi_cards/dashboard.py`, `market.py`, `coverage.py` (the owner's chart
  `coverage_matrix.json` moved to `scripts/bi_coverage_matrix.json`, only the 3.0.0 generator's input),
  `GET /api/bi/coverage`, the page's 「應用領域 × 技術領域」 panel, and a vault's `coverage` block at creation (no
  longer read; `meta:vault_coverage` of older vaults is ignored). Their tests went with them
  (`test_bi_market.py`, `test_bi_coverage.py`, `test_bi_pack_golden.py`).
- `GET /api/bi/dashboard` of every BI dataset is `board.board`: a vault's own analyses, a dataset only on this PC
  (and a subscribed copy) the built-in pack's analyses its schema satisfies (`"source": "pack"`), then the
  quality section `Q`. Section ids are analysis slugs (`gaps`, ...); nothing is coded but `Q`.
- **`bi__query` `analysis`:** `quality` -> the quality section; a vault -> a saved analysis of its published
  version (as P4); a dataset only on this PC, or a benchmark's chosen version -> `board.pack_sections`: the
  built-in pack's analyses on that store, `all` or one slug; a coded section's old name (`trend_coverage`)
  finds its slug; unknown -> `analysis_unknown`. The tool description lists the pack's slugs, `quality`, `all`.
- The golden answers (`tests/fixtures/bi_default_pack/golden/`) are frozen; they keep the coded sections' answers.

## BI domain configuration removed (D4, 2026-11-01)

Design `docs/phases/BI_ANALYSIS_DASHBOARD.md` §3; owner answers 2026-11-01 (move as much as possible
automatically; keep a slim migration prompt). Code `migrate.py`, `catalog.py`, `schema.py`, `quality.py`,
`importer.py`, `names.py`, `ai_runs.py`, `store.py`, `bi_cards_api.py`, `bi_vaults_api.py`, `web_page.py`; tests
`tests/test_bi_migrate_domains.py` (3), `tests/test_bi_quality.py`, `tests/test_bi_vault_skills.py`,
`tests/test_bi_card_aliases.py`, `tests/test_bi_vault_ui.py`.

- **Removed:** `capabilities/bi_cards/domains.py`, `GET`/`POST /api/bi/domains`, the 「領域設定」 editor, the
  configuration's part in imports (value and name aliases), AI extraction notes and quality checks
  (`node_not_listed` is gone: a Node card is the list). The old document is read only by `migrate.legacy`.
- **Schema:** a type may carry `name_pattern` (a regular expression, at most 200 characters, checked on install);
  quality `node_format` reads the Node type's.
- **Migration**, for a vault (`POST /api/bi/vaults/<id>/migrate-domains`) or a dataset only on this PC
  (`POST /api/bi/migrate-domains {"dataset"}`); `{}` is the dry run, `{"apply": true, "token"}` applies:
  `{"ok", "dry_run", "dataset", "vault", "writes": "commit"|"direct", "schema": null|{"from", "to"},
  "schema_adds": null|{"enum_aliases": {field: {alias: value}}, "name_pattern": str|null}, "aliases",
  "missing", "chains", "dropped_chains", "unknown_areas", "enum_aliases_dropped": [{"field", "alias",
  "value"}], "missing_nodes": [name], "notes": [{"domain", "label"}], "notes_to": null|"skills"|"method",
  "removes", "purpose", "token"}` (+ `"commit"` when applied). Order: upgrade to the newest `bi.schema/v1.1`
  when `aliases`/`chain` are missing and the schema id allows; `schema_adds` as a new local schema version
  (a draft of the current version, published, the dataset upgraded; in a vault the document travels with the
  commit); card aliases and Node chains; notes into `<domain>-extract` skills (vault) or one `llm` ingest method
  「領域判讀規則（從領域設定搬來）」 whose instructions are the default ones plus every domain's notes (local);
  the configuration removed (`meta:domains` unstaged in one commit, or deleted from the local dataset).
- `GET /api/bi/dashboard` adds `"domains_left": bool`; the page shows the prompt 「這個資料集還有舊的領域設定」
  with 「預覽：搬進 schema 與卡片」, the plan, then 「確認搬移（寫入一個 commit）」 or 「確認搬移（寫入）」 / 「取消（不寫入）」.

## BI charts in the chat and the Dashboard's sources (C1, C2, C1b, C3, K1, K2, 2026-11-01)

Design `docs/phases/BI_CHAT_CHARTS_AND_DASHBOARD_SOURCES.md`; decisions `docs/DECISIONS.md` 2026-11-01 "BI:
charts inline in the chat; Dashboards from the analysis AI or an Atlas import" (with the C1b addendum).

- **Chart spec** (feed §5): `{"type": "table"|"bar"|"line"|"scatter", "x"?, "y"?, "series"?}`.
  `analyses.chart_for(spec, columns, rows)`: the spec when `checked_chart` accepts it for the columns, else
  `default_chart`: `{"type": "bar", "x": <label column>, "y": <number column>}` for exactly two columns, one
  all-numbers (no bool) and one not, else `{"type": "table"}`. `bi__query` sections always carry a resolved
  `chart` (C1). Card answers are drawn as a table `name, type, <up to 8 fields>`.
- **Chart page** (C2): each succeeded `bi__query` call of the general chat adds `"chart_file": <file name>` and
  `"attach": [{"path", "filename", "media_type": "text/html"}]` to its tool data; the file is
  `<workspace>/bi-chat-charts/bi-<slug|all|query|cards>-<YYYYmmdd-HHMMSS>-<4 hex>.html`, self-contained (own
  meta CSP `default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:`; data in
  `<script type="application/json" id="bi-chart-data">` = `{"title", "about", "sections": [{"title", "note",
  "chart", "table": {"columns", "rows", "truncated"}}]}` with `& < > U+2028 U+2029` escaped; drawn by
  `bi_chart_html.BI_CHART_JS`, the same source `web_page.PAGE` embeds). Agent Web's answer `files` gains
  `{"filename", "kind": "html", "path"}` per page (`bi_chart_files`), shown through the existing sandboxed viewer.
- **Ad-hoc SQL** (C1b): `bi-cards.query` input `sql` (string, at most 20,000 characters; excludes `analysis`:
  `invalid_input`) and `chart` (object or null). One statement through `analyses.run_sql` on the store the
  chat reads (a vault's published copy), `SQL_SECONDS` = 10, `CHAT_SQL_ROWS` = 200 (`run_sql(max_rows=)`), as one
  section `{"id": "query", "title": "查詢結果", "kind": "table", "chart", "columns", "rows", "flags": [],
  "note": "", "analysis": false, "truncated", "sql"}`; `total` = its rows; `scope_note` 「在這份資料集（…）中查詢」.
  Refusals (codes only): `sql_not_allowed` (the authorizer denied: writes, ATTACH, PRAGMA, …),
  `sql_one_statement`, `timeout`, `sql_failed`; the tool's `FAILURE_TEXT` explains each.
- **Save as analysis** (C3): `propose_change` kind `bi_analysis` (in `KINDS`, not in `TELEGRAM_KINDS`; Apply in
  Telegram answers `web_only`). Values (aliases `dataset` → `vault`): `vault`, `slug`, `title`, `question`,
  `chart`, and exactly one of `sql` or `from_analysis: {vault, slug}` (a published SQL analysis). The plan runs
  it on the working copy; card rows `Knowledge base`, `Analysis`, `Chart`, `SQL`, `Result on the working copy`;
  stored values `{"vault", "slug", "analysis": <unit value + slug>}`; fingerprint = the working unit under the
  slug. Apply = `analyses.save` (staged). Code `host_runtime/bi_chat_save.py`.
- **`requires` the schema lacks** (2026-11-04): `bi_analysis__propose` and `bi_analysis__propose_dashboard` refuse them with `requires_unmet`, a failed tool result naming them. `GET /api/bi/vaults/<id>/analyses` items gain `missing: [str]`; `GET /api/bi/dashboard` gains `not_shown: [{slug, title, missing}]`, shown on the page. A saved analysis or pack is not refused: a pack may hold analyses for other schemas.
- **Dashboard from the analysis AI** (K1): harness tool `bi_analysis__propose_dashboard {reply?, analyses:
  [<as bi_analysis__propose>] (≤ 12), order: [slug]}`. The suggestion
  (`aep.bi.analysis_suggestion/v1`) then has `"analysis": null`, `"dashboard": {"analyses": [<unit value +
  slug>], "order"}`, `"previews": {slug: {"columns", "rows" (≤ 200), "truncated"}}`, `"result": {"diff":
  [{"key": "analysis:<slug>"}..., {"key": "meta:dashboard"}]}`. `POST /api/bi/sessions/<id>/apply` on it answers
  `{"ok", "session", "units": ["analysis:<slug>"..., "meta:dashboard"], "analyses", "order", "dashboard"}`;
  refused before staging anything: `dashboard_invalid` (the order), `analysis_exists` (a proposed slug saved
  meanwhile); `suggestion_applied` (409) the second time.
- **Dashboard order from Atlas** (K2): `GET /api/bi/vaults/<id>/atlas-dashboards?port=` → `{"port", "names"}`;
  `POST /api/bi/vaults/<id>/atlas-import {"name", "port"?}` → `{"ok", "dry_run": true, "dashboard", "order",
  "hidden", "before": {"order", "hidden"}, "panels": [{"id", "slug", "status": "kept"|"duplicate"|
  "unknown_analysis"|"other_vault"|"not_aep"|"not_a_panel"}], "duplicates": [panel id], "unmatched": [panel],
  "token"}`; with `"apply": true, "token"` → the same with `"dry_run": false, "staged": "meta:dashboard",
  "analyses"`. Errors: `atlas_port_invalid`, `atlas_name_missing`, `atlas_unreachable`, `atlas_refused`,
  `atlas_not_found`, `atlas_too_large`, `atlas_invalid`, `atlas_failed`, `atlas_nothing` (400) and
  `preview_stale` (409). Atlas is read `GET http://127.0.0.1:<port>/dashboards[/<name>]`, no Origin, 5 s,
  ≤ 2,000,000 bytes. Atlas's goldens: `tests/fixtures/atlas_dashboard_golden/` (Atlas `49600737`), drift check
  `scripts/check_atlas_dashboard_golden.py --atlas <repo>`.

## BI edits of a saved analysis (P1, P2, P3, 2026-11-02)

Design `docs/phases/BI_CHAT_EMBED_AND_PANEL_EDIT.md`; decisions `docs/DECISIONS.md` 2026-11-02 "BI: the chat embeds
Atlas; the AI edits existing panels; AEP never writes Atlas dashboards".

- **Comparison**: `analyses.CONTENT` = `title, question, kind, code, chart, params, requires`;
  `analyses.content(value)` drops those that are empty; `analyses.changes(before, after)` =
  `[{"field", "before", "after"}]` in that order; an edit's `base` = `analyses.digest(analyses.content(unit))`.
- **Chat edit**: `propose_change` kind `bi_analysis_edit` (in `KINDS`, not in `TELEGRAM_KINDS`; Apply in Telegram
  answers `web_only`). Values (alias `dataset` → `vault`): `vault`, `slug` (saved in the working copy), then only
  what changes: `title`, `question`, `chart` (only its keys given change), `sql` or `script` (the whole code; `kind`
  follows), `params`, `requires` (`{}` clears). Refused back to the model: an unknown slug or vault, both `sql` and `script`, no change,
  SQL that the guard denies, a chart naming columns the result lacks. Card rows `Knowledge base`, then each changed
  field (`Title`, `Question`, `Kind`, `SQL` or `Script`, `Chart`, `Parameters`, `Requires`; Now and After, clipped to
  400 characters ending `…`), then `Result on the working copy` (`<n> rows: <first three>`; Now may be `Does not run
  now: …`; After is `Not run yet: the script runs when you press Apply` for a script the chat wrote). `preview` = a
  unified diff of the code (`--- now`, `+++ after`), empty when the code stays. Stored values, fingerprint and Apply
  as `bi_analysis`.
- **`ChangeProposal.preview`** (string, at most 20,000 characters, default empty; additive): passed to the card's
  existing `preview`. `bi_analysis` fills it with the whole SQL when it is longer than a cell.
- **`bi__query` `analysis=<slug>`** (not `all`): the section gains `definition` `{kind, code, question?, params?,
  requires?}` of the published version.
- **Analysis AI**: harness tool `bi_analysis__read {slug}` → the analysis's `content`. `bi_analysis__propose` and
  `bi_analysis__propose_dashboard` on a saved slug are edits; `question`, `params`, `requires` left out keep their
  value (`{}` clears). In a session on `analysis:<slug>` another slug goes back to the model. The suggestion
  (`aep.bi.analysis_suggestion/v1`, additive) gains `edit: {before: <content>, base, changes, preview: <table of
  the saved version, ≤ 200 rows, or null>}`; absent means new. A dashboard suggestion's `dashboard` gains `edits:
  {slug: {before, base, changes}}`.
- **Apply** (`POST /api/bi/sessions/<id>/apply`), checked before anything is staged: `analysis_stale` (409, the saved
  analysis is no longer `base`, or is gone), `analysis_exists` (400, the suggestion said new and the slug is saved
  now), `analysis_unchanged` (400, one analysis with no changes).

## BI Atlas embeds in the chat (E2, E3, E4, 2026-11-02)

Design `docs/phases/BI_CHAT_EMBED_AND_PANEL_EDIT.md` §4; producer contract Atlas `docs/AEP_EMBED_CONTRACT.md`
(final at `4104c8d`; goldens in `tests/fixtures/atlas_embed_golden/`).

- **Tool** `bi__atlas_show {dataset?, analysis?, params?, dashboard?}`, offered with `bi__query`. Succeeded data:
  `{note, atlas_embed, attach?, columns?, rows?}`, or `{dashboards: [name]}` with no arguments. Failure codes:
  `embed_unavailable` (Telegram), `embed_not_a_vault`, `analysis_unknown`, `param_invalid`, `atlas_not_found`,
  `atlas_unreachable`, and `bi__query`'s others.
- **Answer and stored message**: `atlas_embeds`, at most 6, each `{"kind": "panel", "vault", "slug", "params", "path",
  "title", "fallback"?}` or `{"kind": "dashboard", "name", "path", "title", "fallback"?}`; `fallback` is the `path` of
  one of the message's `attachments` (kind `html`).
- **Route** `GET /api/bi/atlas-embed?port=` → `{"ok": true, "port", "framable"}`; `atlas_port_invalid` (400).

## Voice input: Telegram voice and the Agent Web microphone (owner 2026-11-01)

Design `docs/phases/VOICE_INPUT.md`; decisions `docs/DECISIONS.md` 2026-11-01. Voice is an input adapter: a
recording becomes text on this PC (local faster-whisper, no cloud), the person sees it, and the text then takes
the unchanged typed path with the same confirmations. Code `src/voice/` (`contracts.py`, `stt.py`, `audio.py`,
`service.py`, `transcript.py`, `whisper.py`). Only the transcript is kept; no audio is ever written.

- **host.json `voice`** (`VoiceConfig`, optional; absent or `enabled: false` = voice off, every channel behaves as
  before): `enabled` (false), `provider` `"faster-whisper"`, `model_path` and `model_sha256` (both required when
  enabled; an owner-approved model folder on this PC, never downloaded), `model` (`"whisper-small"`), `compute`
  `int8` | `int8_float32` | `float32` (`int8`), `language` (`"zh"`), `hints` (product terms for the initial
  prompt, at most 200), `max_seconds` 180 (1–600), `max_bytes` 10 MB (at most the Bot API's 20 MB),
  `timeout_seconds` 120 (1–900), `idle_unload_seconds` 600 (0: never unload), `queue` 2 (0–20 waiting behind the
  one running). No secrets. `model_sha256` is `python -m voice.whisper <model folder>`: SHA-256 over every file's
  `relative/path\0<sha256 of content>\n`, in path order. The optional package extra `voice` holds
  `faster-whisper`, `av`, `opencc`; CI does not install it.
- **Injection seam**: `VoiceService(config, provider: SttProvider, store: TranscriptStore, ...)`;
  `TelegramIngress(..., voice=None)` and `AgentWebServer(..., voice=None)`; None is voice off. The host builds one
  service (`voice.whisper.build_voice`) only when `voice.enabled`, shares it between both channels
  (`HostRuntime.voice`) and closes it with the host.
- **STT provider** (`voice/stt.py`): `SttProvider.transcribe(pcm: Pcm16k, *, language, hints) -> SttResult`;
  `Pcm16k(samples)` is mono 16 kHz signed 16-bit little-endian; `SttResult(segments: tuple[Segment(start, end,
  text)], language, duration_seconds, elapsed_seconds, engine, model, model_revision)`, `.text` the joined, trimmed
  segments; failures raise `SttError(code)` with a code below. `FakeSttProvider` answers by PCM SHA-256 (tests).
  `FasterWhisperProvider` loads on first use after the package hash matches (`local_files_only`), decodes with
  beam 5, temperature 0, VAD on, no previous-text conditioning and a Traditional Chinese initial prompt plus the
  hints; `unload()` releases the model.
- **Decoding** (`voice/audio.py`, in memory): bytes over `max_bytes` → `audio_too_large`; a declared type not in
  `audio/ogg`, `audio/webm`, `audio/mpeg`, `audio/mp4`, `audio/m4a`, `audio/x-m4a`, `audio/wav`, `audio/x-wav`
  (parameters ignored) → `audio_unsupported_format`. Then: bytes that are not audio → `audio_decode_failed`;
  16-bit PCM WAV of any rate or channels → standard library (down-mix, resample); other WAV without PyAV →
  `audio_unsupported_format`; a compressed container (OGG, WebM, MP3, MP4, by magic bytes) without PyAV →
  `stt_unavailable`; decoded length over `max_seconds` → `audio_too_long`.
- **Service rules**: one transcription at a time; more than `queue` waiting → `stt_busy`; `timeout_seconds` →
  `stt_timeout`; an engine exception → `stt_failed`; text with no letter or digit → `transcript_empty`; text that
  matches the credential pattern → `transcript_credential` (nothing kept, nothing forwarded); otherwise OpenCC
  `s2twp` (when installed) and trimming. Every call writes one record; `fail(code, ...)` records a failure found
  before any audio (a declared limit, a failed download).
- **Transcript record** `aep.voice.transcript/v1` at
  `<workspace>/voice/transcripts/<sha256(session)[:24]>/<id>.json`, readable only by its actor and session, purged
  after the task-summary retention (default 30 days): `schema`, `id` (`vt-<yyyymmddhhmmss>-<8 hex>`), `channel`
  `telegram` | `web`, `actor`, `session_id`, `created_at`, `audio` (`sha256`, `mime_type`, `bytes`,
  `duration_seconds`; metadata only), `stt` (`provider`, `model`, `model_revision`, `compute`,
  `language_requested`, `language_detected`, `settings`, `elapsed_seconds`), `text_raw`, `text`,
  `post_processing`, `segments`, `status` `ok` | `empty` | `failed`, `error_code`, `used_as` (`turn`, `edited`,
  `sent_text_sha256`). `ok` has text and no code; `empty` is `transcript_empty` without text; `failed` has a code
  and no text. A record never holds a credential or a Bot API URL.
- **Telegram**: `message.voice` and `message.audio` (`TelegramVoice`: `file_id`, `duration`, `mime_type`,
  `file_size`, `file_name`); `video_note` and video stay refused. With voice on, for a mapped sender only: the
  declared duration, size and type are checked before any download (a refusal records the failure); then
  `getFile` and the GET download into memory; 「🎤 轉文字中…」 is sent and edited into 「🎤 你說：「…」」; the
  text (a caption first, then a blank line, then the transcript) continues through the unchanged handling of
  typed text in the same chat session (`telegram-chat-<chat>`), and the record's `used_as.turn` is
  `telegram-update-<update id>`. Refusals are disposition `answered` with the code's reply;
  `transcript_credential` is `unsupported_content` with the typed credential reply. A transcript never acts as
  button data, and a run word (「好」, 「確認執行」, "yes", … with the engine's punctuation trimmed) at an open
  card is refused with `voice_not_confirmation` while the card stays open; spoken 「取消」 and 「修改」 work as
  typed. With voice off a voice message gets the unchanged "Only text messages are accepted here.".
- **`GET /api/voice`** (token): `{"ok": true, "enabled": false}` or `{"ok": true, "enabled": true,
  "max_seconds": n}`; the page shows the microphone only when enabled.
- **`POST /api/voice/transcribe`** (loopback Host, bearer token, JSON body at most 14 MiB; a body up to twice that
  is read and dropped so the 413 reaches the browser): `VoiceTranscribeRequest` `{session_id, mime_type (1–100
  chars), duration_ms (optional, advisory), data (base64, not empty)}`. Answers: 200 `{"ok": true, "transcript":
  {id, text, language, duration_seconds, engine, model, elapsed_seconds}}`; 200 `{"ok": false, "code",
  "message"}` for every error code below (voice off: `voice_disabled`); 503 for `stt_busy`; 400
  `voice_request_invalid` (bad JSON fields, bad base64, empty recording); 404 `conversation_unknown` (not this
  actor's conversation); 401/403 the existing guards. Nothing is sent to the Agent; the transcript only fills the
  message box.
- **Turn link**: `ConversationTurnRequest.voice_transcript: Symbol | None = None`. The turn is always `message`.
  When the id names this actor's transcript in this conversation, `used_as` records the turn, whether `message`
  differs from the transcript and its SHA-256; an unknown or foreign id is ignored and never blocks the turn. A
  turn with a valid transcript id whose message is a run word, while the conversation's last answer offered a run
  form or an action card, is answered `voice_not_confirmation` (`needs_input`); the form's button confirms.
- **Error codes** (`voice.contracts.REPLIES` has each reply, Traditional Chinese except the credential one):
  `voice_disabled`, `audio_too_long`, `audio_too_large`, `audio_unsupported_format`, `audio_decode_failed`,
  `download_failed` (Telegram shows the attachment refusal), `transcript_empty`, `transcript_credential`,
  `stt_unavailable`, `stt_busy`, `stt_timeout`, `stt_failed`, `voice_not_confirmation`. None of them reaches the
  Agent.

## Asking a vault from the general chat (2026-11-02)

Design `docs/phases/BI_VAULT_ASKING.md`. Code: `src/host_runtime/knowledge_binding.py`,
`host_runtime/bi_cards_tools.py`, `host_runtime/knowledge_harness.py`. Tests `tests/test_vault_asking_e2e.py`,
`tests/test_vault_asking_binding.py`.

- **Source line.** `knowledge.repo.repository.source_line(name, {tag, commit})`: `資料來源：知識庫 <name> 發佈版本 <tag>`,
  `資料來源：知識庫 <name>（尚未發佈，已 push 的最新版本 <8 hex>）` or `資料來源：知識庫 <name>（還沒有已 push 的內容）`.
  Added by the host under an answer from a repository binding (`KnowledgeHarness.ask`) and a BI vault
  (`with_bi_sources`, when no line already holds it). `QueryResult.vault`: additive `{dataset, tag, commit}`, a vault's
  answer only. `KnowledgeCatalog.live_version(asset)`: the version text a live entry last read, else None.
- **`GET /api/knowledge/askable`** (token-checked) → `{"ok": true, "repos": [entry], "vaults": [entry], "notes":
  [reason]}`; entry `{kind: wiki|bi, id, title, askable, reads: {tag, commit}|null, reasons: [reason]}`; reason `{code,
  message, fix, blocks}`. Codes: `not_bound`, `restart_pending`, `no_model`, `capability_missing`, `skill_off`,
  `not_granted`, `profile_excludes`, `nothing_pushed`, `unreachable`, `unreadable_format`; not blocking:
  `never_published`, `several_vaults`. It writes nothing to a shared folder.
- **`POST /api/knowledge/askable/propose`** `{repo, action?: bind|unbind, purpose?, boundaries?}` → `{"ok": true,
  "card": <ActionCard>}`, or 409 `proposal_refused` with the reason.
- **`propose_change` kind `knowledge_binding`** (Agent Web only) takes the same values. Apply on bind writes
  `assets/knowledge/<namespace>__<repo>__1.0.0.json` first (`validation_refs` starts `knowledge-repo-binding-`, approved
  by the person who pressed Apply), then appends `{asset, repo}` to `host.json` after a backup
  `host.json.bak-<stamp>-knowledge`; on unbind it removes the binding and leaves the manifest. A manifest this flow did
  not write is never overwritten. It takes effect at the next restart; it never restarts Agent Web.
- **MCP tool `aep_bi_query`** (assistant tools, `POST /mcp`): `{dataset: vault-<id>, analysis?: slug|all|quality,
  params?, entity_type?, text?, field?, value?, domain?, follow_links?, limit?}` → `{ok: true, dataset, total, cards,
  analysis, scope_note, source: <source line>, reads: {tag, commit}}`. Refusals `{ok: false, code}`: `bi_query_off`,
  `sql_not_allowed` (any `sql` argument), `bi_unavailable`, `dataset_missing` and `not_a_vault` (with `vaults:
  [{dataset, title, purpose}]`), and the capability's own (`permission_denied`, `analysis_unknown`, ...).
- **`host.json` `assistant_bi_query`**, bool, default false. `GET /api/coding-agents` adds `bi_query: {enabled}`; `POST
  /api/coding-agents/bi-query {enabled: bool}` (session token) → `{ok, bi_query}`, 409 on `bi_query_request_invalid` or
  `settings_read_only`. Live at once. While off, `/mcp` `tools/list` omits the tool; the stdio bridge's list does not.
- **BI K2 from a file.** `POST /api/bi/vaults/<id>/atlas-import` also takes `{file: <text>, apply?, token?}` in place of
  `{name, port}`. Refusals add `atlas_source_ambiguous` (`file` with `name`); a file that is not strict JSON or not a
  schemaVersion 2 document is `atlas_invalid`, over 2,000,000 bytes `atlas_too_large`.


## The BI build flow: harness sessions and convert's sources (2026-11-02)

Design `docs/phases/BI_BUILD_FLOW.md`. Every tool below exists for one turn only (`turn_host_tools`), reads or tries,
and writes no card, draft or unit; a person's click applies a suggestion.

- **`POST /api/bi/vaults/convert`** answers also `sources: {copied, skipped, error?}`. Sources are copied with the same
  ids, files, Markdown revisions and conversion failures into the vault's local `staging.sqlite`; never to the shared
  folder. `skipped`: the source's file is gone. `error` (the exception's class name): the vault exists, the sources did
  not come along; the person adds them again.
- **Session A** (`aep.bi.schema_suggestion/v1`). `BenchRuntime.schema_asker_for(dataset, draft_id, actor)`; without it
  the turn stays one model call. New verdict `answer` (changes must be empty). `sent` gains `harness: true` and `tools:
  [{name, ok}]`. Tools: `bi_schema__sources`, `bi_schema__read_source`, `bi_schema__cards {type?, limit?}`,
  `bi_schema__try {changes?, samples?, source_id?, folder?, types?}`, `bi_schema__suggest`, `bi__query` (working copy).
  `bi_schema__try` answers `{diff, errors, problems, valid}`, and when valid `impact` (`schema_versions.impact`, when the
  dataset has a `bi.sqlite`), `samples: [{entity_type, name, problems}]` and, with `source_id`, `trial: {run_id, result}`.
  A trial's run keeps the tried schema in its layout as `trial_schema`, under the ref `draft:<id>@rev<base>`.
- **`bi_skill__benchmark {changes?, source_ids?, folder?}`** answers `{questions: [{question, before, after?}], regressions,
  improved, candidates_added, cases, not_tested}`; `before`/`after` are grades with a fenced `answer`. At most 3 sources
  and the first 10 graded questions. `after` reads `BiStore.scratch_copy`: the working cards plus the draft's clean trial
  candidates, in a temporary folder. It is not an `aep.bi.bench_report/v1` and never satisfies the push check.
- **Session kind `questions`**, target `questions:<set>`, vault datasets only (`not_a_vault`); no harness:
  `harness_unavailable`. `BenchRuntime.questions_asker_for(dataset, actor)`. Tools: `bi__query` (working copy),
  `bi_questions__analyses`, `bi_questions__try {question, must?, must_not?}` (grades on working and published),
  `bi_questions__propose {reply, questions?, reasons?}`. Suggestion `aep.bi.questions_suggestion/v1`: `{reply, questions:
  [{unit, question, must, must_not}], reasons, result}`. A proposal is refused back to the model unless it has at most 20
  questions, each valid, graded, not a repeat, and every `must` term found (case-insensitive) in a working card's name or
  field value or a saved analysis's result rows.
- **`POST /api/bi/sessions/<id>/apply`** on a `questions` session takes `{dataset, turn, picks: [index]}`: stages those
  questions, answers `{session, units, questions, cases}`; `picks_invalid`, `picks_empty`, `suggestion_applied`.

## Conversation source and search (Telegram history, owner 2026-11-02)

Design: `docs/phases/TELEGRAM_HISTORY.md`.

- `ConversationRecord.source`: `agent_web` (the default, so older records read unchanged) or `telegram`. A record is
  `telegram` exactly when its session id starts with `tg-`: `tg-<16 hex>-<yyyymmdd>-<8 hex>`, where the first part is
  an opaque id from a per-host key, never the chat id.
- `SqliteLocalState.conversations(actor, limit=, source="agent_web")`: one source, Agent Web by default, so existing
  readers take no Telegram record. Also `latest_conversation(actor, prefix)`, `search_conversations(actor, query, limit=30)`
  and `host_key(name)`.
- A Telegram record is read-only. Turn, attachment, feedback, backend, model, contribution draft, voice and agent
  session routes answer `{"ok": false, "code": "conversation_read_only"}`; the turn and voice routes with HTTP 409.
  Reading, opening a listed file and `/api/conversations/delete` stay available. Delete also removes the files the
  record lists.
- `GET /api/conversations` rows gain `source`, and the list holds the latest 50 of each source.
- `GET /api/conversations/search?q=`: `{"ok": true, "results": [{session_id, title, updated_at, messages, backend,
  source, snippet}]}`, newest first, at most 30, for this actor. `snippet` is empty for a hit in the title only. Blank
  words give no results; over 200 characters gives `{"ok": false, "code": "search_query_too_long"}`.
## A BI vault's originals in the repository (2026-11-03)

Design `docs/phases/BI_SOURCES_IN_REPOSITORY.md`. Code `src/capabilities/bi_cards/vault_sources.py`, `staging.py`,
`src/knowledge/repo/repository.py`. Tests `tests/test_bi_vault_sources.py`, `tests/test_bi_vault_sources_ui.py`.

- **Unit `source:<sha256>`**: `{id, name, folder, file, sha256, bytes, media_type, classification, by, at, markdown: [{rev, file,
  sha256, origin, note, converter, chars, lines, by, at}]}`. Files: `<folder>/<sha8>-<name>`, characters OneDrive refuses replaced
  in the path only; `<folder>/markdown/<sha8>/rev-<n>-<author>.md`. A new vault source's id is the first 12 hex of its sha; a
  converted source keeps its id. Staged on add (`POST /api/bi/sources` takes `folder`); commit puts sources in a commit of their own
  when anything else is staged. Every classification pushes; no size limit.
- **`GET /api/bi/sources`** in a vault adds to each source `shared: local|staged|pushed|cloud_only` and `folder`, and to the reply
  `waiting: [path]`, `withdrawn: [{file, sha256, by, at, reason}]`. On sync a colleague's `Staging` gets rows with `origin: repository`
  reading through to the repository file; reading one that cannot be read is `source_unreadable`.
- **`POST /api/bi/sources/upload?dataset=&name=&classification=&folder=&media_type=`**, raw body: a file of any size, written to disk
  as it arrives → `{ok, source}`. `source_incomplete` when the body is cut short.
- **`POST /api/bi/vaults/<id>/share-source`** `{source_id, folder?}`: stage a source only on this PC.
- **`POST /api/bi/vaults/<id>/withdraw-source`** `{source_id, reason?, confirm: true}` (`confirm_required`, `source_not_pushed`) →
  `{ok, withdrawn: {files, reason, at, left}}`. Record `withdrawn/<author>/<seq>.json`, format `aep.knowledge.withdrawn/v1`,
  `sources/` only. A withdrawn file's commit stays applied; `stage_file` and a push naming it, and adding the same bytes, are
  `source_withdrawn`. Each PC drops its copies at sync, removes open candidates and blanks a written run's excerpts.
- **Engine.** A repository file that cannot be read makes its commit wait, and `file_unreadable` when something relies on it.
  `Repository.commit(..., only=)` commits just the units and files it picks.

## BI card-page import and samples (2026-11-03)

Design `docs/phases/BI_CARD_PAGE_IMPORT.md`. Code `src/capabilities/bi_cards/page_import.py`. Tests `tests/test_bi_card_page_import.py`.

- **`POST /api/bi/import/pages/preview`** `{dataset, pages: [{path, text}], samples?: bool}`, writes nothing → `{ok, preview_id, summary: {create,
  update, unchanged, skip, warnings, pages, samples, problems, skipped}, types: [{entity_type, filename, columns, rows}], problems: [{path,
  line?, code, message}], skipped: [{path, reason}]}`. Codes: `frontmatter_open`, `frontmatter_line`, `frontmatter_list`, `frontmatter_map`,
  `frontmatter_repeat`, `type_unknown`, and CSV's own for a `.csv`.
- **`POST /api/bi/import/pages/apply`** `{preview_id, folder?}` → `{ok, written, sources, import_id?, applied?}`. Each file becomes a source; one run
  and one `commit_run`; one evidence row per value, `locator: {line, key}`, the frontmatter line as `excerpt`.
- **Merge in this path:** each row of `types[].rows` carries `merge: {fill, join, proposal, bookkeeping, human_kept, same}` (field names), `summary.merge` the counts,
  `mark_conflicts: [{entity_type, key, path, card_is_sample, row_is_sample}]` the rows whose sample mark differs from their card. `PlannedRow.propose` names the fields that become
  proposals. Apply answers `cards_changed` when a card moved since the preview.
- **Ticked rows** (`samples: true`) get the `SAMPLE-` name, never twice; links between them follow (`importer.preview` `links_renamed`).
- **`importer.preview`** gains `rows` and `samples`; **`Registry.normalize`** takes a list as its items, without splitting them again.
- **`QueryResult.sample_note`**: the host's line about example data, added under a chat answer by `with_bi_sources`, returned by `aep_bi_query`.

## BI schema 4.0.0 (2026-11-03)

`bi.schema/v1.1@4.0.0` = 3.0.0 with `domain` a list, allowed values kept and no default, on `Application`, `Trend`, `CustomerProduct`; a widening, upgraded in place. A bare `bi.schema/v1.1` means 4.0.0. A
`bi__query` card of those types returns `domain` as a list. The feed's goldens stay pinned to 2.0.0.

## BI card model: storage shape (2026-11-04)

Design: `docs/phases/BI_CARD_MODEL.md` §3. Values and id functions: `capabilities/bi_cards/card_model.py`. Old units stay valid and are never rewritten.

**Schema.** `bi.schema/v1.1@5.0.0` = 4.0.0 plus `summary` (19 types), `usage`, `scope`, `last_confirmed` (derived), `review_due` on all 21, and top-level `relation_types` `[{name, label, from, to}]`. A field may hold `relation_type` (links only; default `has_<field>`) and `used_by`. A bare `bi.schema/v1.1` means 5.0.0. Additions only, so an upgrade is in place. The feed's goldens stay pinned to 2.0.0.

**New units:**

| Unit | Value |
|---|---|
| `state:<card>:<field>` | `{state, reason?, raw?, ref?, by?, at?}`; state is `unknown`, `not_applicable`, `pending_confirmation` or `confirmed_none` |
| `relation:<id>` | `{from, type, to, origin, status, scope?, note?, by?, at?}`; id = `relation_id(from, type, to)`; origin `schema_field`, `ai_inferred`, `registered`; status `unreviewed`, `pending`, `inferred`, `confirmed`, `disputed`, `rejected` |
| `relation_evidence:<id>` | `{relation, basis_card, reference_id, stance, assessment?, by?, at?}`; id = `evidence_link_id(relation, basis_card, reference_id)`; stance `supports`, `refutes`, `context_only` |
| `profile:<application>` | `{revision, author, path, sha256, schema?}` |
| `tool:<application>/<name>` | `{revision, author, path, sha256}` |
| `skill:<application>/<name>` | As `skill:<name>`, which stays readable |

`<application>` in a key is a home's short form: `<id>`, or `library/<entry>` for a library entry, which has an application's shape. `skills` is not a valid entry name: `library/skills/` holds the skill that spans everything.

**Changed units, by added optional parts:** `card:` may hold `former_keys`. A `field:` value, or an item of a list value, may be `{"card": <id>, "name": <name at write>}`, a link by id; `fields.value` always shows it as the card's current name. An `evidence:` row may hold `reference_id`, `stance`, `reference_at`, `reference_time_basis`.

**Rename.** `POST /api/bi/cards/<id>/rename {dataset, name, values?, base_version, reason}` → `{ok, version, id, name}`, vault only (400 `rename_vault_only`). `values` gives the other naming fields of a type named by several. The id stays; the old key joins `former_keys`; the old name joins `aliases` if the type has them. 409 `name_taken` (the name, or a former name, of another card of the type), 409 `stale_edit`, 400 `reason_required`. A push that would give two cards of a type one key is `blocked`. Two that reach the folder unseen: the card created first keeps it, the other's `cards.canonical_key` is `<key>#<id>` with quality check `key_conflict`, until someone renames it. A store write of a former name not resolved first: `name_is_former`.
**Field states (T5).** `schema.missing_state(cell)` reads `n/a`, `na` as `not_applicable` and `tbd`, `待定` as `pending_confirmation` before `Registry.normalize` drops the cell; `""`, `nan`, `none`, `null`, `-`, `—` give none, and the field reads as unknown. `importer.preview` does this for all three importers (CSV, card pages, recipes), so `PlannedRow.states` is `{field: {state, raw?, reason?}}`, a run's candidate holds it as `states`, and a preview cell holds `state`, with `change: "state"` when it would write. A vault's card only: a plain dataset's tables stay empty. A state is never written over a value: the value stays and the row has the warning `state_value_kept`. The same state again writes nothing. A later value clears it, by import or `set_field`; `undo_import` removes the states the import wrote and does not restore one it replaced. If two PCs write a value and a state, both units stay and the value wins: `BiStore.field_states(card_id)` lists only fields with no value. `field_states.origin` is `unit` (the only rows that read back as units), or computed at rebuild: `proposal` (`pending_confirmation`, an empty field with a pending proposal whose value is not null, and no unit state) and `profile` (a field a home's profile lists under a type's `not_applicable`, an item being a name or `{field, reason}`, on a card in that home, with no value and no home using it; a field merely left out reads as unknown). `bi__query` cards gain `field_states`: `{field: {state, reason?, origin}}`; an empty field not listed there is unknown.

**Relations.** A link field that resolves makes a `relations` row at rebuild: type `relation_type` or `has_<field>`, status `unreviewed`, origin `schema_field`, never a unit. `POST /api/bi/vaults/<id>/relations {from, type, to, status, origin?, scope?, note?, evidence?: [{reference_id, basis_card?, stance?}]}` → `{relation_id, staged}` stages a person's decision for their commit: status `confirmed`, `rejected` or `disputed`; origin `registered` (default) or `ai_inferred`. A derived relation takes a status; any other needs a type in the schema's `relation_types`, between its types (404 `relation_type_unknown`, 400 `relation_type_mismatch`); a confirmed AI-inferred one needs evidence (400 `relation_evidence_required`). `GET /api/bi/cards/<id>` gains `relations: [{relation_id, type, direction, other_id, other_name, other_type, status, origin, source_field, scope, note, evidence}]`, without rejected ones.

**AI-inferred relations.** In a vault on a schema with `relation_types`, an AI run asks the model for those types too. One with an unregistered type, no ends, or a quote not in the source is left out with warning `relation_unsupported`. `GET /api/bi/runs/<id>` gains `run.relations: [{id, type, from, to, reason, source_id, locator, excerpt, decision}]`, without any a person already decided. `POST /api/bi/runs/<id>/relations/<rid> {dataset, status}`, status `confirmed` or `rejected`, stages the decision (origin `ai_inferred`, evidence the quote's `reference_id`) for the person's commit. Confirming needs both cards to exist (404 `relation_card_unknown`); not on a trial run (`run_trial`).

**References (T6).** `reference_id` = `card_model.reference_id(source_id, locator)`, so a withdrawal that blanks an excerpt leaves it alone. A new evidence row's unit holds `reference_id`, `stance` (`supports` unless the model said otherwise), `reference_at`, and `reference_time_basis: submission_fallback` only when `reference_at` is the evidence time. `reference_at` is the page's `source_date`, `date` or `updated`, else the card's `source_date` or `date`, else the evidence time. A row written before this model keeps its unit as it was: the table computes its `reference_id` at rebuild and leaves `reference_at` empty, which is how `units_from_db` tells the two apart. `BiStore.evidence` returns all four keys for every row, an old one as `reference_at` = `at`, `submission_fallback`. The extraction prompt asks for `stance` on a fact, an unknown one reads `supports`; the run's review shows a stance other than `supports`.

**Summaries (T7).** The extraction prompt asks for `summary`, `usage` and `scope` on types where they are `judgement` fields. Whatever basis the model gives, a written one is stored as `inference`, with no evidence and no review warning; basis `unknown` or the value `unknown` writes nothing; two chunks' readings keep the first with no `value_conflict`. `Signal` and `VisitLog`, whose `summary` is sourced, are unchanged. `POST /api/bi/vaults/<id>/publish` adds `summary_missing: {total, by_type: {<type>: <cards>}}` when any card of a type having the field lacks a summary; it never blocks, and the key is absent when none does. The page's publish message mentions the total.

**AI runs, from the first R6 run (2026-11-04).** A list an AI run gives that the card already holds, in any order, is `merge: same`: nothing is written or proposed, whoever set the card's list, and its evidence is still kept. A run never writes a list but the union, unless a person chose the new value. A `domain` value outside the schema's `domains` is dropped with a `domain_unknown` warning and never blocks a candidate; other fields' bad values still do. A new card takes its source's domain: the schema's domain named like the source's application, ignoring case (`aidc` is `AIDC`), a created domain included; a library entry, or an application no domain is named after, gives none. It is stored with basis `inference`, and wins over a domain the model gave, which becomes the field's `alternatives` and so a pending proposal on the card when the run is committed (acceptance F10, 2026-11-06; until then the model's known domain stayed). Only runs made after this change have it: a run already in review keeps its old errors, so run it again.

**Same name on another type (R6).** A model's new-card candidate whose name, key or alias equals a name, key or alias of a card of another type holds `same_name: [{id, name, type}]` and a `same_name_other_type` warning naming each. Accepting it is refused with `same_name_unconfirmed` until the review sends `confirm_same_name: true` (`POST /api/bi/runs/<id>/candidates/<c>`), recorded as `same_name_confirmed`; it is never merged. A card of that name appearing later returns an accepted candidate to pending. The page lists these apart, and 「接受所有」 leaves them out. The prompt also names cards of types not asked for whose names the excerpt writes.
**Evidence review (Phase 2-c).** `POST /api/bi/evidence-reviews/preview {dataset, target: card|relation, card, field?, relation?, reference_id?, verdict, stance?, directness?, scope?, date?, same_source?, reason, author?, base_version?}` writes nothing and returns `{statement, before, after, unchanged, folder, text, base_version}`; `.../apply {dataset, text, base_version?}` keeps the note as a source and commits, or answers `{unchanged: true}`. Vault only (400 `review_vault_only`). `base_version` is required for a card (`stale_edit` when it moved). Levels are words: `verdict` `accepted`, `pending`, `rejected`; `directness` `direct`, `indirect`, `insufficient`, `unknown`; `same_source` `independent`, `same_source`, `unknown`; `stance` as above. A review never writes a field. An `evidence:` row, and so the new `evidence.assessment` column, or a `relation_evidence:` unit may hold `assessment: {system?: {reason}, current: {directness, scope, date, same_source, verdict}, history: [{by, author, at, reason, source, before, after}]}`. On a card it also sets the row's `stance` and, for a given date, `reference_at`. On a relation the verdict sets its status (`confirmed`, `pending`, `rejected`) through `decide_relation`, which now takes `pending`; a relation with no reference links to a fixed reference id so its reviews gather. An extracted fact's `reason`, if the model gave one, is kept as `assessment.system.reason`. `GET /api/bi/cards/<id>` gains `field_states`, `rejected_relations`, `references` on each relation, and `assessment` on each `evidence` item.

**New tables in `bi.sqlite`, rebuilt from units:** `relations`, `relation_evidence`, `field_states`, `card_names`, `card_app_folders`; `evidence` gains four columns. `cards` and `fields` keep their shape. **Compatibility:** an AEP older than this refuses a vault holding these units at sync (`unit_problem`).

## BI card model: folder layout (2026-11-04)

Design: `docs/phases/BI_CARD_MODEL.md` §4. Paths: `capabilities/bi_cards/homes.py`; never spell one elsewhere. **These paths are immutable once a vault holds them.**

```
applications/<application>/{sources,skills,tools,profile}/
library/<entry>/{sources,skills,tools,profile}/
library/skills/<name>/rev-<n>-<author>.md      a skill with no home: it spans every home (classify)
<home>/skills/<name>/rev-<n>-<author>.md       unit skill:<short>/<name>
<home>/tools/<name>/rev-<n>-<author>.<ext>     unit tool:<short>/<name>; run per "a home's tools" below
<home>/profile/rev-<n>-<author>.json           unit profile:<short>
```

A **home** is an application or a library entry. Its short form, `<application>` or `library/<entry>`, is what unit keys and `card_app_folders` use. `POST /api/bi/vaults` takes `segments` (default `aidc`, `aerospace`, `robotics`, `wireless`) and `library` (default `products`, `technologies`, `competitors`), kept as `meta:vault_segments` and `meta:vault_library`. `skills` is refused as an entry name (`library_invalid`). Folders are checked by form, not against these lists.

**Engine.** `knowledge.repo.repository.FileLayout` says what a type's files are: `areas`, `new_areas`, `source_hint`, `skill_path_re`, `is_source_path`, `source_folder_problem`, `skill_area`. A type with no `layout` attribute keeps the default, which is exactly the rules from before, so `wiki` is unchanged, including its bare-name `skill:` keys. `path_problem(path, areas=FILE_AREAS)`; `withdraw`, `stage_file`, commit checks and the readme ask the type's layout.

**Old vaults.** A BI commit may still add `skills/…` and `sources/…`, and a source folder may still be `sources`, `sources/<anything>`. New code writes skills to `library/skills/` or a home's folder, also in an old vault. **A source added with no folder still goes to `sources/`**, in no home, in a new vault too: choose an application for what should be in one.

**API.** `GET /api/bi/vaults/<id>/skills` lists a home's skill as `<short>/<name>` and adds `tools`, with `folders` holding each home's `sources`. `POST …/skills` takes that long name, or `name` with `home`; a home's skill with no `applies_to` applies to that home's sources. `POST …/tools` `{home, name, suffix, text}` stages a tool's next revision (`tool_invalid`, 400, when any is bad).
## BI card model: editing (2026-11-04)

Design: `docs/phases/BI_CARD_MODEL.md` §5. Every change to a card goes through ingest. `store.set_field` stays as an internal method for proposal accept and a confirmed migration; no route reaches it directly.

**Correction note.** Markdown with frontmatter `card` (id), `field`, `value` or `state`, `reason`, and optional `author`, `at`. `state` is `not_applicable`, `pending_confirmation` or `confirmed_none`, replaces a value the field has, and is only a note's to give for `confirmed_none`. Read deterministically by `correction.read` with the card page reader, no model. Text with no such frontmatter is an ordinary source, for a normal AI ingest.

- `POST /api/bi/corrections/preview {"dataset", "base_version", "card", "field", "value" | "state", "reason", "author"?}`, or `{"dataset", "base_version", "text"}` for a written note → `{"ok": true, "card", "name", "field", "label", "current", "value", "state", "state_label", "reason", "author", "unchanged", "base_version", "folder", "text"}`. Writes nothing.
- `POST /api/bi/corrections/apply {"dataset", "base_version", "text"}` → `{"ok": true, "version", "source", "import_id"}`, or `{"ok": true, "version", "unchanged": true}` when the field already has that value: no source, no version, no history. The value is written as `human`, its evidence is the note's `value` line with `basis: human`, and `reason` goes in `history`. It is an import of one value, so a vault commits it at once, the note in a source commit of its own, and `POST /api/bi/import/undo` undoes it.
- `value` is normalised like an import cell; a list is accepted for a list field; empty clears the field. 400: `note_invalid`, `state_invalid`, `field_unknown`, `field_derived`, `base_version_missing`, `reason_required` (every note), `value_invalid`. 404 `card_unknown`. 409 `stale_edit` with `current`, `by`, `at`, `version`; 409 `dataset_read_only`.
- A note is kept in the `sources/` of the card's first home, else `library/corrections/sources`.

## BI card model: profile (2026-11-04)

Design: `docs/phases/BI_CARD_MODEL.md` §4.2. Code: `capabilities/bi_cards/profile.py`.

`<home>/profile/rev-<n>-<author>.json` = `{format: "aep.bi.profile/v1", application: <short form>, revision, schema, types: {<type>: {category?, fields: {<field>: {use: required|optional, note?}}}}, proposals: [{type, field, definition, reason, status: proposed|merged|rejected}]}`, written once; `profile:<short form>` names the current one. A type or field not listed is not used there. A field not in the schema, or any other key on a field such as `kind` or `enum`, is `profile_invalid` (400): a definition lives only in a proposal.

**API.** `GET /api/bi/vaults/<id>/profiles` → `{profiles: [{home, ...document}], homes: [{home, label}]}`, `homes` being every application and library entry of the vault. `POST …/profiles` `{home, profile}` stages the next revision, on the vault's current schema, for the person to commit.

**AI run.** A source's folder gives its home (`homes.home_of`), and the run keeps that home's types and notes in `layout.skills.profile`, so a retry reads the same. With no types chosen, the model is asked only for the profile's types; for those, the profile's fields, the type's naming fields, what the schema requires, and `aliases`, `summary`, `usage`, `scope`, with the notes and category explanation. With no profile, the whole schema as before; `GET /api/bi/runs/<id>` then has `run.profile: null` for a vault's run, and the page says so. Validation stays against the merged schema: a schema field or type outside the profile stays a candidate, with `candidate.outside_profile` (field names), `outside_profile_type` and, on the field, `outside_profile: true`. A profile-required field the candidate lacks is a `profile_required_missing` warning on it. An unreadable profile refuses the run (`profile_missing`), so it never silently reads the whole schema.

**Rebuild.** `card_app_folders` = per card, the homes (short form) of the sources of its evidence. `field_states` gains `origin: profile`, `state: not_applicable`, for a field with no value and no other state, on a card that has a home, when every one of its homes has a readable profile and none uses the field. Naming fields, schema-required and derived fields, `aliases`, `summary`, `usage` and `scope` are never computed. `MODEL_VERSION` 4.

**Publish.** `POST …/publish` adds `profile_required_missing: [{home, type, field, cards}]` when the version has any profile. Never a block.
**Re-run and diff.** Design §5.3.

- `POST /api/bi/reruns/preview {"dataset", "sources": [id] | "all": true, "application"?, "skill_revision"?, "start"?, "instructions"?, "types"?}`. In a vault, `all` needs `application` (`<id>` or `library/<entry>`). Without `start: true` → `{"ok": true, "started": false, "count", "sources": [{"id", "name"}]}`: no model call. With it → also `"rerun"`, and one AI run per source begins, kept as a `trial` with method `rerun:<id>`, so it cannot be committed by the run's review and `GET /api/bi/runs` leaves it out. Nothing starts unless all can: `classification_not_approved`, `model_unavailable`. 409 `skill_changed` when `skill_revision` is no longer current. 400 `sources_missing`, `application_missing`.
- `GET /api/bi/reruns/<id>?dataset=` → `{"rerun": {"id", "status": "running" | "ready" | "confirmed", "by", "at", "application", "skill_revision", "runs": [{"run_id", "source", "status", "error", "failures"}], "items": [...], "commit"}}`. An item is `{"id", "entity_type", "canonical_key", "name", "card_id", "base_version", "field", "label", "current", "new", "person_set", "new_card", "source", "skills", "evidence", "problem"}`. The list is made once, when every run has ended, and kept. A value the same as the card's (a list in any order), a value not found, and a new naming value of an existing card are not listed; the same new value from several sources is one item.
- `POST /api/bi/reruns/<id>/confirm {"dataset", "items": [id]}` → `{"ok": true, "commit": {"import_id", "created", "updated", "values", "at", "by"}}`. Only those values are written, through `commit_run`, in one commit with no proposals; a confirmed value replaces a person's. 409 `cards_changed` when a listed card moved, `run_committed` on a second confirm, `run_closed` while running, `schema_changed`. 400 `items_missing`, `item_blocked` (its `problem` is set), `items_conflict` (two new values for one field), `items_incomplete` (a new card without its naming and required fields). 404 `item_unknown`, `rerun_unknown`.

## BI card model: a profile's field proposal (2026-11-04)

Design: `docs/phases/BI_CARD_MODEL.md` §4.3. Code: `capabilities/bi_cards/profile_merge.py`. On the page with the profile (step 2).

`POST /api/bi/vaults/<id>/profile-proposals` `{home, type, field, decision: merge|reject, confirm: true}`, the reviewer's confirmation, answers `{profile, schema, skills_need_update, status}` and stages the profile's next revision with the proposal's `status` set.

- **A new name** goes through `schema_versions` (draft, publish, upgrade) into the vault's next schema version, in the same call, with `used_by: [<home>]`, and the profile lists the field as `optional`.
- **The same name, same definition** (all the proposal's keys but `label`, `name`, `used_by` match): only `used_by` gains the home, in a new version; no new version when it already holds the home.
- **The same name, another definition:** `schema_conflict` (409, `differs` names the keys). Nothing changes and the proposal stays `proposed`, for a person.
- **Reject:** no schema change. A decided proposal is not asked again (`proposal_unknown`, 404). An invalid definition is refused by the schema check and changes nothing. `confirm_required`, `decision_invalid`, 400.

**A written skill bound to the old version needs an update, as after any schema change** (`skills_need_update` lists them); a generated classify skill follows by itself.
## BI card model: what a publish writes (2026-11-04)

Design: `docs/phases/BI_CARD_MODEL.md` §6. `POST /api/bi/vaults/<id>/publish` also returns `"cards": {"behind": false, "written", "removed", "unchanged", "seconds"}`, or `{"behind": true, "problem"}`: a failed view never undoes the publish, and the next one repairs it. `GET /api/bi/vaults/<id>` status adds `cards_view_behind`.

- `cards/<card id>.md`, with `cards/_manifest.json` `{tag, commit, at, by, hashes}` written last. Generated from the version published now, read-only, never read back. Frontmatter: `id`, `type`, `key`, `aliases`, `sample: true` on a sample, `generated: true`. Only pages whose hash differs are written; a removed card's page is deleted. A withdrawn source's excerpts leave the pages at once.
- `published/<tag>.sqlite`, written once. The publish record (`repository.publish(tag, extra)`, the engine knows no BI name) gains `snapshot: {path, sha256}`, or `null` when it could not be written. Readers still rebuild from units.

## BI: deciding pending proposals, and an AI run's folder (2026-11-04)

`GET /api/bi/proposals?dataset=` → `{proposals: [{id, card_id, card_name, entity_type, version, field, label, needs_reason, value, current, current_kind, source: {kind, ref, at}, evidence: [{source_name, excerpt, basis}]}]}`, every pending proposal; `evidence` is what the current value rests on. Decided with `POST /api/bi/cards/<id>/proposals/<pid>`, which now keeps a rejection's `reason`: a `proposal:` or `decision:` unit may hold `reason`, and `proposals` gains that column.

`POST /api/bi/runs` with `folder` in another home than the source's own: 400 `run_folder_mismatch`, since another home's skill and profile would apply. With no `folder`, the source's own.

## BI: an AI run merges onto existing cards (2026-11-04)

An AI run's values meet a card as an import's do (`docs/phases/BI_CARD_PAGE_IMPORT.md` §4); rule and recipe runs are unchanged. Each field of a candidate gains `merge`: `fill`, `join` (the joined list is written), `same`, `proposal` (written as a pending proposal with its evidence, never over the value, also under 「接受所有沒有錯誤的候選卡」), `human_kept`, `bookkeeping` (a derived field: the later value stays), or `take`. `GET /api/bi/runs/<id>` gains `run.merge`, the counts.

`take` is a person's choice: `POST /api/bi/runs/<id>/candidates/<cid> {take_new: {field: true|false}}`, or editing the field. **`confidence` and `evidence_grade` are protected:** on a card that exists, a differing value is always a proposal, and an empty `confidence` is a proposal when the value is `verified` (400 `field_protected` on `take_new`). A value that differs inside one run stays as the field's `alternatives`, shown in the review and written as a proposal; the warning `value_conflict` stays.

A `proposal:` unit may hold `evidence`, and `proposals` gains that column. `GET /api/bi/proposals`: `evidence` is now the proposed value's, `current_evidence` the current value's.

An AI run never writes `confidence: verified`, on a new card or an empty field: `merge` is `capped`, the highest lower level is stored with no evidence, and the claim is a proposal with its evidence.

`GET /api/bi/proposals` items gain `origin` (the source file, else the reference) and `protected`. `POST /api/bi/proposals/decide {dataset, action, reason, field?, origin?, count}` → `{decided, superseded, left_out}` decides every proposal the filters show in one write. A reason is required (400 `reason_required`). `count` is what the person confirmed (409 `proposals_changed`). `confidence` and `evidence_grade` are included only when `field` names them.

## BI: a model's supply link, a repeated answer, a domain from the application (2026-11-04)

**A model's `SupplyLink` matches by supplier and customer** when no card has its exact name; seeds keep their keys and imports are unchanged. One card on that pair: an update, the card keeps its name (`merge: key_kept`), and a differing `product` is a proposal. Several cards: `match: ambiguous`, error `match_unresolved`, a person chooses. Several candidates of a run for one pair: error `pair_repeated` on each without a person's choice, with `pair_repeats` naming the others. `POST /api/bi/runs/<id>/recheck` applies this to a run with no model call.

**An identical request reuses its answer** (`capabilities/bi_cards/answer_cache.py`), per PC in `<dataset>/answer_cache/`, keyed by messages, model alias, output limit and contract; failures and wrong shapes are not kept, and a withdrawn source clears them. `POST /api/bi/runs` takes `fresh: true` to ask anyway. `run.answers`: `{reused, asked, input_tokens, output_tokens}`.

**A domain from the application.** `POST /api/bi/import/pages/preview` takes `folder`: a row with no domain takes that application's, marked `inference`, and merges as any value; a one-domain card that holds one keeps it; a library folder gives none. `POST /api/bi/vaults/<id>/fill-domains {confirm?}` → `{fill, by_domain, left, applied, purpose?}` gives cards with no domain their applications' domains in one commit; without `confirm` it writes nothing.
## BI: clearing a sample mark (2026-11-05)

`POST /api/bi/cards/<id>/unmark {dataset, base_version, reason}` → `{"ok", "id", "synthetic": false}`. A person says the card is real. The `card:` unit goes to `synthetic: false` with `mark_cleared: {at, by, reason}`, committed and pushed like any change, so another PC has it after sync and rebuild; `GET .../history` lists it as field `synthetic`. Values and version do not move. Refused: `reason_required`, `base_version_missing`, `stale_edit` (409), `not_a_sample`, `sample_by_name` when the name starts `SAMPLE-`: rename the card first (`POST .../rename`), since that name keeps the default pack leaving it out and marks it on any import. A later import row that says it is an example marks the card again and removes the record. There is no button: the page does not offer this yet.

`importer.FICTIONAL` no longer matches 「待查證」 or 「待…驗證」. A value saying so stays as written, in the field, and nothing else shows it: no chip, state or quality check reads that word.

## BI: marking a card as a sample, and finding one not marked (2026-11-05)

A card's mark is `synthetic` on its `card:` unit, so it survives a rebuild on any PC. To mark an existing card, `POST /api/bi/import/preview` and `/apply` with a CSV of its naming column(s) and any other column holding a text `importer.FICTIONAL` matches (`虛構`, `範例`, `示範`…): each row must preview `unchanged`, so no value moves. A column the schema lacks is not stored. It stages `card:` and one `import:` unit and commits itself, the purpose naming the file; `POST /api/bi/import/undo` is the way back before a push. A marked card stays marked: this route cannot unmark one, and a page import never changes a mark (`BI_CARD_PAGE_IMPORT.md` §4). The mark does not rename a card: `SAMPLE-` stays what the default pack leaves out by name.

`GET /api/bi/quality`, check `sample_not_marked`: besides a `SAMPLE-` name, an unmarked card whose `body`, or a card page linked by its evidence, says `虛構` or `示範`. A hint for a person, who may find a real card merely using the word. A report's text is many cards' and is not read. Only this route reads pages: the Dashboard's and the chat's copy of the check look at the name and `body`, since on a colleague's PC each page may be a file OneDrive has to fetch.

## Agent Web's record of write requests (2026-11-05)

`<workspace>/logs/agent-web-writes.log`, `host_runtime/write_log.py`. One JSON line per POST, PUT, PATCH or DELETE that reaches Agent Web, refused ones included, in order of their status being known: `at` (when the request was read, local time), `method`, `path`, `status` (0: it ended with no response), `client` (the peer's address), `label` (`X-AEP-Client`), `user_agent`, `referer`. Rotated at about 5 MB, keeping 3 older files as `.1` to `.3`, about 20 MB in all. A line `{"dropped": n}` says how many were lost.

**Never recorded:** bodies, query strings, fragments, cookies, `Authorization`, other headers, the user part of a `Referer`. **Not recorded at all:** reads, so GET and HEAD. `log_message` stays silent, and nothing goes to the console.

**What it does not prove.** `X-AEP-Client`, `User-Agent` and `Referer` are what the client says, and `client` is 127.0.0.1 for everything on this PC. Any process with the token can send any label, or none. A line says a request was made and what it called itself, not who made it. The page sends no `Referer`, and a browser sends no label unless told to, so a person at the page and a script without a label look alike but for `User-Agent`.

**Limits.** A request reaches the file only after its status is known, so a long request in progress when the process stops leaves no line. The writing is a queue and one thread: a request never waits on it, and a log that cannot be written, or a queue of more than 2,000 lines, loses lines and costs no request. Those who label themselves: `tests/bi_page_driver.py`, `aep-assistant-bridge`.

## BI: a run that fills empty reading fields (2026-11-05)

Design and measurements: `docs/phases/BI_SUMMARY_FILL.md`. Code: `capabilities/bi_cards/reading_runs.py`. A page import uses no model, so it leaves `summary` and `usage` empty; a page's body stays a source of its card.

`POST /api/bi/runs {dataset, kind: "trial"|"ingest", reading: true, skip?: [card id, key or name], card_ids?: [card id], fresh?}` starts it, one model call per card, for cards missing `reading_runs.FIELDS` that are not samples and have text of their own: a card page's body and the card's `body` field. Refused: `reading_nothing` when no card qualifies, `reading_invalid`, `model_unavailable`, `classification_not_approved`. The run is an ordinary AI run: `GET /api/bi/runs/<id>`, candidate review and commit as usual, retry for failed cards, with `method_ref` `llm:reading`. A candidate's fields are `basis: inference` with one piece of evidence, its `excerpt` found word for word in the text sent, or the value is dropped with `evidence_not_found`. Each merges as `fill`; a value filled since stays, with the new one a proposal. A run warning `reading_left_empty` says how many cards stayed empty.

`POST /api/bi/import/pages/apply`: a page whose file name is garbled (`page_import.garbled_name`) is kept under its card's name.

## `bi__query`: the words of `text` (2026-11-04)

`text` is words, each on the card in any field, not one string in one field; the card list's `q` too. In `bi__query` only: when no card holds them all and there are at least two words, `cards` are those holding at least two, most first, and `scope_note` says they may not be the answer. With none at all, `scope_note` asks for shorter words before saying "no data".

## `bi__query`: hops and passages (Phase 3-a, 2026-11-04)

Design: `docs/phases/BI_CARD_MODEL.md` Phase 3. Additions to `bi-cards/query@1.0.0`; a call without them answers as before, with the new keys empty.

- **Input** `hops` (0–3, default 0): walk the found cards' relations, both ways, breadth first.
- **Output** `related`: each card reached once, by a shortest path, no found card among them, at most 30; a cycle ends. A card entry as in `cards`, plus `from`, `hops`, `path` and `claim`. A rejected relation is not walked.
- **`path`:** steps of `relation_id`, `type`, `direction` (`out` along the relation, `in` against it), `status`, `origin`, `claim`, `to_name`, `to_type`, and `also` for other relations between the same two cards.
- **`claim`:** `confirmed` and `unreviewed` (a card's field holds it) are `fact`; `inferred`, `pending` and `disputed` are themselves. A path's `claim` is its weakest step. `scope_note` carries the rule, and says when the limit left cards out. With `hops`, a found card also lists its direct `relations`, at most 20.
- **Output** `passages`, with `text`: at most 5, `source_id`, `source_name`, `rev`, `line_start`, `line_end`, `line`, `snippet`. `passages_withheld`: matching chunks of sources whose `classification` is not in the host's `models.data_approval.approved_classes`, counted up to that limit; `scope_note` says so. No approval known: none read.
- **Which version:** a vault's passages come from the version `bi__query` reads: the sources in that commit, at their revision then, listed in `sources.json` beside the published view. A source only on this PC, or withdrawn since, gives none. A subscribed copy has no sources, so none. A benchmark's chosen version reads none.
- `aep_bi_query` takes `hops` and returns `related`, `passages` and `passages_withheld`.
## BI card model: a home's tools in ingest (2026-11-04)

Design: `docs/phases/BI_CARD_MODEL.md` P2-a. Code: `capabilities/bi_cards/tool_runs.py`.

A tool is a Python script stored as an immutable revision. It gets `INPUT` (a copy of the source) and `OUTPUT` (a folder) and writes `.csv` or `.md` files there, at most 20 and 50 MB in all, within 300 s. **Output is only ever new sources**, staged in the raw source's folder with its classification and `derived_from: {source, sha256, tool, revision, tool_sha256}` on the unit; cards come only through the usual preview and review. Withdrawing a source also withdraws what was derived from it.

**Guard.** The `analyses.run_python` guard: own process, `-I`, empty environment; an audit hook refuses network, child processes, native libraries, SQLite and writes outside `OUTPUT`. It can still read files. It guards against mistakes and stray model output; **it is not a boundary against a determined attacker.**

**Approval.** The first run of a revision on a PC needs a person's approval of that code, by its hash, kept per PC in the vault's local folder. A revision with the same code as an approved draft is already approved there.

**API.** `GET /api/bi/vaults/<id>/tools` → `{tools: [{name, revision, author, path, sha256, code, approved}], drafts: [{name, sha256, code, approved, ...}], guard}`. `POST …/tool-approve` `{sha256, confirm: true}`. `POST …/tool-run` `{name, source_id}` → `{sources: [{id, name, already}], printed, tool}`; `tool_needs_approval` (409, with `sha256` and `code_text`), `tool_failed`, `tool_output_invalid`, `tool_not_python`, `tool_missing` (400), `tool_unknown`, `source_unknown` (404).

**Skill AI (Session B).** `bi_skill__draft_tool {home, name, code}` keeps a draft on this PC and stages nothing. `bi_skill__try_tool {sha256, source_id}` runs an approved draft on a source whose classification the model may see, and shows the output without keeping it. The AI cannot approve a tool or save a revision.
## BI schema fit per item (Phase 2, 2026-11-04)

Design: proposal §8.1. Code: `capabilities/bi_cards/schema_fit.py`. In a vault, an AI run started with `check_fit: true` on `POST /api/bi/runs` (default off; 2026-11-04) asks the model how each knowledge item fits the schema. `GET /api/bi/runs/<id>` gains `run.items: [{id, summary, actions, reason, questions, card, target_card?, proposal, source_id, locator, excerpt, schema, status, decided_by?, decided_at?, decision_reason?}]`, kept with the run (per PC, as candidates are; no unit and no table).

`actions` hold `update_card`, `create_card`, `dictionary_change`, `extend_schema`, `propose_type`, `needs_clarification`, and may combine. Update or create comes from the candidate's real action, and each candidate has an item. Nothing is dropped: an unknown action, a quote not in the source, or a `propose_type` lacking any of `unit_boundary`, `why_not_existing`, `why_independent`, `business_use` becomes `needs_clarification` with a question, as does a field definition whose `kind` or `class` the schema does not allow, or any question on a plain update or create. The item keeps `proposal` and `model_actions`, what the model said. Status: `through_candidate` (reviewed as a candidate), `proposed`, `approved`, `rejected`, `needs_clarification`.

`POST /api/bi/runs/<id>/items/<iid> {dataset, status, reason?}`, status `approved`, `rejected` or `needs_clarification`; a reason is required except to approve (400 `reason_required`). 400 `fit_needs_clarification` to approve an item still holding that action, `fit_item_not_reviewed`, `fit_item_decided`, `run_trial`. An approved `extend_schema` adds a proposal to the home's profile, staged for the person's commit, for `POST /api/bi/vaults/<id>/profile-proposals` (400 `fit_home_unknown`, `profile_missing`). An approved `dictionary_change` or `propose_type` registers nothing: a schema version stays Session A's.

## `bi__atlas_show`: a stopped Atlas, what was shown, and which Atlas (2026-11-05)

- **Copy.** Each read of a dashboard from Atlas keeps, per PC, `<workspace>/bi-atlas-dashboards.json`: `{name: {read_at, panels: [{vault, slug, params}]}}`, the newest 50 dashboards, at most 12 panels each. Only references; an Atlas variable in a parameter is left out, so the analysis's default stands.
- **Atlas does not answer.** A named dashboard with a copy gets AEP's charts of it and `atlas_embed.stale_note`: 「Atlas 目前沒開，這是上次讀到的 dashboard，版面以 Atlas 為準（上次讀到：<read_at>）」, which the page shows when it cannot frame Atlas. With no copy, or none of its panels readable: `atlas_unreachable` and the explanation. No name: the copies, with `read_at`.
- **Result of a dashboard.** `atlas_frame` (bool), `charts` (titles on the chart page), `not_shown` ([{vault, slug, code}]) and a `note` saying only what the answer holds.
- **Which Atlas.** `ConversationTurnRequest.atlas_port` (1–65535, optional): the port of the address this browser set; the host reads only `127.0.0.1:<port>`. Absent: 8127. For that turn only.

## BI vault sync with nothing new (2026-11-05)

`POST /api/bi/vaults/<id>/sync`: the answer's `sync` gains `moved`: whether the local database was rebuilt or the version the feed shows changed. A quiet sync reads no commit file (`Repository._commits_stamp`: names, sizes and times; each file a commit names is still checked by stat), rebuilds nothing unless `Repository.fingerprint` (applied and local commits, uncommitted changes, conflicts, withdrawals) or `card_model.MODEL_VERSION` differs from the last build, and queues no feed work. Concurrent `vault.sync` calls for one vault share one run and its answer or failure. The page shows the local copy first and syncs behind it, redrawing only for what came from outside (commits applied, a rebuild from them, or a changed version it reads).


## BI: accepting a proposal moves the citations (2026-11-05)

Decision: `docs/DECISIONS.md` 2026-11-05 "Accepting a proposal moves the citations with the value". Code: `store._write_person_value`, `store._proposal_evidence`, `vault.materialize`. Test: `tests/test_bi_accept_evidence.py`. Adds to "Knowledge repositories: the BI type (R2)".

**Units.**
- `field:<card id>:<field>`: `history` may hold `old_evidence`, a list of evidence rows in the shape of an `evidence:` unit's, `[]` when the change moved nothing. It is absent on any older unit and on a change that does not move evidence.
- `evidence:<card id>:<field>`: after an accept, the accepted proposal's rows. Absent when it had none.

**Local database.** `history.old_evidence` (JSON text, NULL when absent), added by `add_missing_columns`. `card_model.MODEL_VERSION` is 10.

**Routes.**
- `POST /api/bi/cards/<id>/proposals/<n>` with `action: "accept"` and `POST /api/bi/proposals/decide`: as above. The `reject` action changes no field, evidence or history.
- `POST /api/bi/corrections/apply`: the note's evidence replaces the field's; `POST /api/bi/import/undo` restores what `old_evidence` holds.
- `GET /api/bi/cards/<id>/history`: a row may hold `old_evidence`. The key is absent otherwise.
- `POST /api/bi/vaults/<id>/resolve` on a `field:` unit with `mine` or `theirs` also decides its `evidence:` unit.

**A run's commit** (`POST /api/bi/runs/<id>/commit`, `POST /api/bi/import/...`): a value it replaces takes its evidence to `old_evidence`, and the run's own replaces it. A value that stays, or a list that only grows, appends. `POST /api/bi/import/undo` restores `old_evidence` and removes what the run cited, except on a field changed since.

**`GET /api/bi/proposals`:** a `conflict` proposal's `evidence` is the lost value's, from its commit, where it had any.

**A candidate** has `citations`, the fields whose value it repeats from a place not yet cited. With `action: "unchanged"` and `citations` not empty, it is accepted and committed like any other, writes only those `evidence` rows and leaves the card's `version` and `updated`. `summary.citations` counts them, and so does a commit's `applied.citations`.

**The local database reads a lost commit's evidence as it was:** `evidence` may differ from the `evidence:` unit where that commit lost the field. The unit is unchanged.

**Not changed.** The feed and its goldens, and the published snapshot's format.

## BI schema changes that merge (2026-11-05)

Design: `docs/phases/BI_CARD_MODEL.md` §4.3. Code: `capabilities/bi_cards/schema_merge.py`.

- **Units:** `schema_change:{type,field,enum,label,used_by}:...`, values in §4.3. The `schema` unit keeps naming the base version. A created home's domain comes from `meta:home:<id>`.
- **Version text:** `<major>.<minor>.<patch>` or, read by a vault with such units, `<major>.<minor>.<patch>+<12 hex>`. `catalog.base_ref` and `catalog.base_version` strip it; `/api/bi/schemas` does not list derived versions; `store.schema_ref()` returns what the vault reads.
- **`GET /api/bi/vaults/<id>/status`** adds `schema_conflicts`: `[{"kind": "clash"|"race", "unit", "label", "reason", "value", "current"?}]`.
- **`POST /api/bi/vaults/<id>/schema-conflicts`** `{unit, choice}`: `drop` a change, `keep` what stands, `take` the one that lost (`race` only). Staged for the person's commit. `schema_conflict_unknown`, `choice_invalid`.
- **`POST /api/bi/vaults/<id>/push`** answers `blocked` when the commits would make a change clash that was not clashing on the head.
- **`upgrade_preview`** `blocked` adds code `field_used_by`.
- **`GET /api/bi/vaults/<id>/skills`** items add `update_blocks` and `update_reason`. `skill_needs_update` is raised only when `update_blocks` is true. A skill unit may add `schema_seen`. A repository type may provide `skill_binding` and `skill_review`; the wiki type does not, and keeps its rule.


### BI same-card operation merge (2026-11-06)

BI repository types optionally project operations before the common engine applies base checks; wiki does not opt in. Every replay and push must use this one projection. Commit records are immutable; total order remains `(clock, author, seq)`.

A non-human differing `summary`, `usage` or `scope` over a nonempty value produces a stable pending `proposal:` unit, including the incoming evidence. Same readings keep the first provenance. Explicit human changes retain replacement semantics. `field:<id>:updated` selects the later date, with canonical JSON as a deterministic tie breaker. Card history's derived `updated` is monotonically the maximum change date.

A new BI `evidence:` operation may additionally contain `bi_evidence: {before, field, after_field}`: `before` is the prior evidence array or null, whose hash must match `base`; the two other values are nullable SHA256 hashes of the underlying field values. Only additive rows whose field is unchanged are unioned, deduplicated and ordered by `reference_id` (derived from source and locator on old rows). A duplicate reference keeps the later `reference_at` (including submission fallback), then the greater canonical row JSON. A stale addition against a replaced value conflicts. A replacement or evidence review retains ordinary base checking. An old operation with `history.old_evidence` retains replacement handling; absent enough context, it keeps the existing conflict behaviour. No silent guess is permitted.

The extra key is permitted only on BI evidence operations. Old AEP versions reject commits carrying it, so collaborators must upgrade together. Old commits require no rewrite. Replay policy 1 invalidates the local sync cache once; `MODEL_VERSION = 12` rebuilds BI materialization once. Feed fixtures and goldens remain pinned and unchanged.

The replay epoch is persisted in `repo.sqlite` user_version, independently of the optional clean-sync stamp: incomplete or tampered files can invalidate that stamp without triggering another migration replay. Content determinism compares the complete UTF-8 SQL iterdump, including all tables and sqlite_sequence; SQLite file header transaction counters are local and intentionally differ.


BI same-card release correction (2026-11-06): chunk-inferred readings retain alternatives without a conflict warning; sourced facts and ordinary fields still warn. Time maxima compare actual ISO instants in UTC (date-only/naive dates use UTC). A derived card.updated timestamp keeps history's representation on equal instants. Evidence and updated-field unit ties remain canonical and deterministic. Replay policy 2 / card model 13 supersede versions 1 / 12 for this timestamp correction; no commit or golden is rewritten.

## BI query filter hints and matched body snippets (2026-11-07)

`bi-cards/query@1.0.0` / `bi__query` remain read-only and scoped to the selected dataset and
reading version. Additive card output: optional `body_snippet` with `field: "body"`, `text`
(at most 300 characters including cut ellipses), and `source` (`kind:ref`). Only returned cards
whose current, schema-visible body contains a text-query word qualify; full bodies stay absent
from `fields`, and no unrelated or wordless body is emitted. Cite the containing card using
its existing `card` key. Sample/trust flags are unchanged; an excerpt is data, not instructions.

Snippets require host approval: every known body-evidence source class must be approved;
unresolved source IDs withhold it. An import ref naming a staged source uses that source's
class; duplicate names require all their classes. With no source classification, a curated
body defaults to INTERNAL. Unknown/no host approval emits no body excerpt. Chosen-version
harness tools take the installed query handler's approval, never a tool argument. Approved raw
passages and their withholding/version rules are unchanged.

For a nonempty text search restricted by type, domain, field or value, `scope_note` may count
other exact word matches excluded by those filters, grouped in deterministic type/domain
order. Counts cover all matches, independent of `limit`, but add no rows or body snippets.
A card in several domains can contribute to several domain groups while the headline total
counts it once. The note tells the model to retry the same text without restricting filters;
no matches elsewhere means no hint, and unfiltered/wordless searches add no filter hints.
SQL and saved analyses do not run this card-search hint path. Counts are discovery hints, not
citations or proof of an answer. No pending proposal, preview or unpushed/unpublished version
is admitted beyond the version already selected by the query.


### BI rename collision projection (2026-11-07)

When two distinct card units claim one key, creation timestamps are compared as UTC instants. Equal instants use the deterministic replay position that first introduced each card, then card id; two cards in one commit therefore have a stable id tie-break. Unknown legacy replay metadata retains timestamp/id fallback. The winner keeps the key; the other projects key#id until a person renames it. Unit identities and immutable commit contents never change. MODEL_VERSION 14 invalidates the projection cache once; repository wiki behavior is unchanged.

### Browser table pagination and native pointer delivery (2026-11-09)

`WebAction.read_table` accepts an optional `header_table` CSS selector for split
header/body tables, and optional typed `pagination` with `next`, `current`, `total`
WebTargets and `max_pages` (1..200, default 200). Optional `key_columns` (up to ten
column names) declares record identity: keys must exist, be unique within each
page, and not overlap earlier pages. Page labels are integers or `/ N`.
Reading starts at page one, requires each next page to advance and replace rows,
and refuses changed totals, stalled pages, or more than 2,000 aggregate rows.
Each new page must remain unchanged for the runner's settling interval; declared
keys must also advance, so asynchronously refreshed frozen columns are not read
with the previous page's IDs. Stale/overlapping keys time out without partial data.
Failure returns no partial table. Omitted fields preserve single-table behavior.

Native Browser clicks dispatch trusted pointer press/release after the existing
origin and read-mode checks. Hidden copies are excluded from target matching;
multiple visible matches still refuse. Visible role=option controls are eligible
for label matching. Missing/obscured/disabled native click targets have a bounded
wait; unsafe read-mode clicks fail before any pointer event. Existing capability
identity, Bridge authorization and side-effect classification are unchanged.

`wait_for` takes a target and `value`, a regular expression matched against its
whole visible text. Missing targets and nonmatching text are polled within the
Browser timeout; expiry is `web_wait_timeout`. Invalid patterns fail contract
validation. Ambiguous targets and origin refusal are never retried as readiness.
It performs no pointer action and is usable in read mode. Workflows can await a
visible query-completion marker before trusting a retained old table/page count.

### SOP authoring reliability (2026-11-09)

See `docs/phases/SOP_WORKFLOW_AUTONOMY.md` for the acceptance boundary.

- `CapabilityExecutionFailed` retains validated local output with a failed
  Bridge result. Nonzero/timed-out Python and Browser action failures use this
  path; diagnostic data never turns a failed invocation into success. External
  status-only surfaces continue withholding capability data.
- `RunPythonResult.files` contains only new/content-changed outputs. Streaming
  hashes are bounded to 2,000 files, 10,000 directory entries, 1 GiB and ten
  seconds per scan. A pre-scan limit refuses before execution; a post-scan
  limit fails with runner diagnostics and no output claims. `data` optionally
  contains one complete, bounded stdout JSON object; noisy, truncated,
  nonobject or nonfinite output leaves it null. Failed steps cannot satisfy
  Workflow output checks using diagnostic or old files.
- `inspect_dom` is origin-scoped, bounded and read-only. `browser__inspect`
  exposes only scope/offset/limit and constructs that action itself. Failed
  Browser executions identify action index/kind and retain fresh bounded DOM
  evidence when the current origin is permitted. Inspection omits input values
  and redacts credential material; it grants no new origins or execution rights.
- `WorkflowParameter.file_mode` optionally declares input/output. Files reject
  directories and unsupported suffixes; declared input files must exist before
  dispatch. Legacy/output destinations may be new paths. Actual user evidence
  binds declared defaults with actor/session provenance and timestamps; newer
  form answers survive older history and short context windows.
- A planned SOP task persists its requirements, inputs, current trial digest,
  failure, repair count and structured missing-input question. Requirements and
  existing check IDs cannot be removed. Nonempty procedure assertions may be
  rebound after discovery; every plan/candidate change invalidates prior proof
  and in-flight proof tokens. These bindings are technical checks, not a formal
  proof of the SOP's business meaning.
- Installation of a planned candidate requires successful actual execution of
  the exact current candidate plus declared coverage. Business approval remains
  separate. Pending execution approval is a safe waiting state. Completion is
  checked against persisted actor/session state even without new tool calls;
  exhausted checks retain diagnostics and explicitly return unverified input
  state rather than claiming readiness.
- A failed approved/form/card trial resumes the same Agent task at most three
  times. Repair is scoped to its candidate/session and offers only bounded
  observation, authoring and trial tools. It cannot approve itself, install,
  invoke arbitrary code or repeat a successful side effect. A valid current
  pending approval blocks repair; an obsolete approval does not authorize or
  block a different revision. Missing-resource questions must identify their
  input and reuse supplied files; technical selectors/navigation are diagnosed
  by the Agent rather than requested from the person.

`data/merge@1.0.0` is a read-only local composition capability. `left` and
`right` are independently bound JSON objects, each limited to1000 top-level
keys; output `data` is their shallow union (at most2000 keys). Equal duplicate
values are retained, numerically equal1/1.0 are accepted, but booleans and
numbers are distinct, including nested values. Unequal collisions refuse with
`data_merge_conflict` without exposing keys/values. No files, hidden context,
network access or new Workflow input variant is involved. A reporting step can
receive prepared dates/mapping/rates together with Browser rows through normal
step bindings. Real Workflow and actual Host/owner-policy tests cover the path.

Authoring follow-ups (2026-11-10): original SOP attachments are reused only
from the active task's same-actor/session recorded references, with the existing
ownership, root, existence and preview limits. Their source notes/images remain
available beyond the short message window and in a repair turn. They are not
new human answers. Read-only composition and accessible-name resolution do not
grant new execution authority.

Known technical Browser failures (including CSS query scope, target readiness
and pagination) and failed program/output checks carry bounded repair guidance.
They do not mean a person must provide selectors or navigate manually. Origin,
credential, approval and repair-budget boundaries remain stops. Failed trial
state retains at most12 KB of redacted actual failure/action metadata, invalid
control labels/paths and bounded Python output tail; no bulk page, rows, file
contents or field values. Only exact-current successful complete proof clears it.

Pagination current/total must be distinct locators and distinct resolved DOM
elements, checked together in an origin-authorized snapshot on every poll.
Equal numeric values on different elements at the last page are valid. A shared
element fails with `pagination_controls_must_differ`; it cannot establish1/1
completeness. Bounded inspection exposes `state.invalid` as a boolean and
`aria-invalid` metadata without reading the field value.

Actual trial continuity retains at most ten redacted entries/12KB per
actor/session, appended only after current candidate/digest/trial-token checks.
Entries contain actual outcomes and declared Browser action/target prefixes,
not fill values, open URLs, scripts or result rows. A compact advisory prelude
(last three entries/last three target hints, at most4KB) precedes normal task
context inside its existing24k character budget. New owner input preserves
history; it does not fabricate or backfill past trials. Actual proof IDs remain
unchanged while advisory IDs/codes are byte-bounded. Browser failures identify
`pagination.current`, `pagination.total`, `pagination.next` or
`pagination.controls` through `failed_target_field` and the failure message;
unknown wire fields are ignored. The safe field persists through public trial
summaries, repair and subsequent owner context.

`ensure_visible` requires a desired `target` and disclosure `trigger`; only
this action accepts trigger. Unique CSS-visible presence is probed without
reading text/input values. Existing presence returns immediately; only missing
permits one native policy-checked click, followed by presence polling within
one shared deadline. Invalid/ambiguous/origin errors never authorize the click.
Failures identify `ensure_visible.target` or `ensure_visible.trigger` through
the same safe diagnostic contract. History may retain bounded redacted
trigger label/css/kind hints, never fill values. No proof or approval is implied.
`wait_for` with omitted value uses the same presence probe; provided regex
continues to match complete actual text/value with existing semantics.

AuthoringTask.collection_obligations retains real declared paginated Browser
collections across revisions/replans/candidate IDs. Each records capability,
exact save_as and the first actual source manifest digest (after supplied-input
binding). Matching uses capability namespace/name and save_as; selectors and
step positions may be repaired. TaskStore cannot clear or replace earlier
provenance. Coverage requires exactly one declaration/writer of that collection,
and that writer must be a valid paginated read_table. A later read_text,
read_record, inspect_dom or download with the same output cannot overwrite it
and still establish completeness. Missing/renamed/unpaged/dummy/ambiguous
collections keep the prototype unverified and block installation readiness.
Legacy tasks default empty, and only actual current/previous same-session
declarations are captured at draft/revise/trial; approval digests do not invent
historical bodies. This structural guard does not prove actual business table
identity or replace independent acceptance. Alternative exports remain prototype
until an actual deterministic completeness-evidence contract exists.

Task-summary status answered renders as 已回覆, not 完成. A model returning an
answer or awaiting a trial approval does not prove its requested Workflow ran.
Actual succeeded/failed run summaries retain their existing explicit statuses.

Browser native activation may hover before pressing. Hover is internal and
act-authorized; after hover the same target is resolved and hit-tested again
with origin checks under the original deadline. Movement repeats observation,
not activation. After a press starts no retry may replay it. Raw click_at
semantics and read-mode restrictions are preserved. No new public action.

Conversation capped updates admit only one- or two-message appends retaining
the exact corresponding old suffix. This includes100+1,99+2 and existing100+2;
actor, monotonic time, immutable retained content and transactional checks remain.
Host repair records its actual assistant response without fabricating user input.
Browser operate exposes save_as documentation on the real HostTool schema:
inspect_dom/read_table/read_text/read_record/download require an output alias.
Dedicated browser__inspect is preferred for ad-hoc inspection. No validator or
action-default behavior changes are implied by the metadata clarification.

Workflow surgical patch (`host.authoring.patch.v1`, 2026-11-10):
`authoring__patch_workflow` and `aep_patch_workflow` share `WorkflowPatchRequest`.
It requires candidate_id, base_digest (SHA-256), and 1..20 operations. A path is
1..20 exact JSON key/index segments, strict string/nonnegative integer (no bool,
traversal/slash/NUL segments). Only existing values may change: step inputs,
description, or existing parameter/check fields. Identity, version, capability,
policy and whole-step/list replacement are refused. Request JSON is at most256KiB.
`replace` requires value (including explicit null). `copy_reference` instead requires
attachment_id and source_path; it resolves an existing same-session JSON attachment
through AttachmentStore, confined to its stored folder/root, at most1MiB. No copied
content appears in the external result. Unmentioned canonical JSON values and script
strings survive exactly; no normal-draft assembly or supplied-input rebinding occurs.
Native/external results contain candidate id, revision and new digest. Invalid
manifests retain normal validation failures; stale/busy, installed, scope and missing
reference states return structured authoring errors. Installed assets require revise.
Automatic Host continuation forbids full draft replacement and restricts patches to
the one actual failed step.inputs proven by the current candidate digest, run id,
step index and capability. No trustworthy scope means refusal. A successful patch
clears verified_digest and active_trial_token; current trial/approval/install rules
remain. Per-candidate OS locks and compare/save cover overlapping patch and legacy
writers, and install admission through publication. Legacy full-draft submissions
do not carry client base_digest; a stale document first submitted after a committed
patch remains an explicit full replacement. Automatic continuations cannot use that
route. No stronger stale-client guarantee is claimed for legacy replacement.

Automatic continuation inherits the previous actual trial's effective arguments;
omitted/empty arguments do not reapply formal defaults. Explicit matching subsets
retain all other actual values; contradictions return authoring_trial_arguments_conflict.
Missing/stale/foreign/in-flight evidence returns authoring_trial_arguments_unavailable.
No question or new persisted state is added. Cleared-token begin_trial/record_trial
state must agree between candidate and active actor/session task; latest Host history
candidate/run/prior-digest identifiers only corroborate scope (never advisory text,
permissions or trial proof). Write trials also require the matching actual approved
run record. The previous trial digest remains the reference after a patch. Existing
parameter defaults, input origins, repair budgets and approval boundaries remain.


### Atomic fresh-network click observation

`WebAction.do = click_wait_network` extends the existing Browser action union
compatibly and accepts the existing click target only. It requires act mode and
native activation. A script containing it enables private scoped network
observation before navigation/reload. The action fences/arms a fresh CDP epoch
before one press, then requires same-origin/main-frame XHR/Fetch completion and
bounded quiet under its original deadline; timeout/failure/loss is not success.
No new execution grant, stored asset, HTTP client, payload/URL matcher or output
field is introduced. Raw Network headers/body/fullURL/query are never retained
or diagnosed; only bounded necessary protocol metadata is used internally.
This is transport evidence, not a business or DOM correctness proof. Existing
Workflow checks, independent output validation and installation approval remain.


## IT-owned local tool contracts (owner2026-11-12)

ToolAccess catalog returns actual installed versus needs_setup status. describe returns current input/output contracts; invoke returns real execution_status, handler_invoked, result and replayed evidence. Successful side effects share canonical actor/target/normalized-input receipts across aliases and native endpoints for the current turn. Failed/read operations are not memoized. system/run-command executes argv without implicit shell; coding/run-python uses EnvironmentRunner and preserves real failures, output limits and fresh artifact checks. outlook/send-draft takes the draft receipt and is distinct from drafting. Mail body chunks expose body_truncated/next_body_offset; bounded search never asserts full-thread coverage. Installation preserves pending business review and actual verification independently of availability.

The scoped design and regression matrix are in
`phases/IT_OWNED_TOOL_ACCESS_DESIGN_20261112.md`; historical approval requirements
for local tool installation/execution are superseded for this scope. Shared
publication and model/data-routing decisions are unchanged.

## Feature Plugin API v1 (generic Slice 1, 2026-11-14)

`common.plugins` defines closed frozen models; extra fields are invalid.
`PluginManifest` format aep-plugin/1 contains identity, title, description,
core_api (minimum inclusive / below exclusive SemVer), exact requires, optional
runtime, capabilities, routes, pages, assets and data schema version. Plugin id
is namespace.name; Slice1 gives each plugin a dedicated namespace. Names and
identities cannot collide with core or other plugins. No manifest admission
grants, IT approval or mandatory signer list exists.

`PluginCapability` contains CapabilitySpec plus scalar input/output declarations
and optional bounded rows output. `capability_models` constructs closed models
without importing publisher code. Pending policy metadata does not gate dispatch
or imply a review. PluginAsset identifies a digest-matched Skill/Workflow file;
installation uses the existing skill_packs ledger and honest pending metadata.

`PluginPackage` format aep-plugin-package/1 is a JSON/base64 envelope, not ZIP.
Per-file path/size/SHA256 and canonical aggregate digest must match. Limits:
8MiB envelope, 6MiB total raw files, 2MiB per file, 256 files. Canonical paths
are bounded relative worker/ or assets/ paths; traversal, ADS, case collisions,
Windows reserved names and redirected owned paths are refused. Staged files are
rechecked at activation, process restart and Host restore. A hash is consistency,
not a provenance/verified/trusted claim. No signature support is fabricated.

Runtime uses the current interpreter with -I/-u/-B, stdlib/AEP dependencies and
staged worker package path. JSONL uses existing ExtensionRequest/Response with
request correlation, bounded output and serialized per-worker requests. Normal
environment plus AEP_PLUGIN_PACKAGE_FILE and AEP_PLUGIN_DATA_ROOT is passed;
HTTP headers and Web bearer token are not injected. Process crash/timeout is a
failure, never automatic replay of a write. This is not an OS sandbox.

`PluginManagerProtocol`: snapshot, install(payload, PluginOrigin), enable,
disable, uninstall, call_read(PluginReadRequest, timeout_seconds) and
set_busy_probe. Actual PluginManager also restores and closes owned workers.
Origin records authenticated actor/channel/source/turn reference, not approval.
Status states are active/disabled/failed; action and read status is succeeded or
failed with typed failure. Per-turn successful-effect replay is unchanged; no
durable receipt guarantee is added. An unreadable/redirected ledger is reported
unavailable, never as a normal empty installation. Core startup remains usable.

Authenticated Agent Web routes (after existing loopback/bearer validation, with
Origin checks):
- GET /api/plugin-manager/plugins: typed inventory and max_package_bytes.
- POST /api/plugin-manager/install or /update: bounded raw envelope.
- POST /api/plugin-manager/enable|disable|uninstall: exactly {plugin_id}.
- GET /api/plugins/<plugin_id>/<route_id>?version=<exact SemVer>: only that
  active version's declared read capability. No arbitrary URL/port/SQL proxy,
  inbound identity override or forwarded Authorization. Responses must echo
  request_id, plugin_id, version and route_id. Read data is limited to256KiB;
  requests64KiB. Missing credentials401, foreign Origin403, and actual lifecycle
  failures preserve their typed codes/status mapping.

Page contributions are TextBlock, MetricBlock and TableBlock data, rendered by
core-owned DOM text nodes. No plugin script/markup/link/image/frame/action is
executed or auto-fetched. New dynamic page navigation appears after install;
disable/uninstall withdraw only its contributions. Registry refresh is scoped to
that plugin namespace, leaving other Skills/Workflows and Knowledge selection
unchanged. Old assets retire only after commit and recovery preserves previous
on/off locations and user choices. Data schema migration is unsupported in v1;
mismatches return setup/compatibility failures. Data remains on uninstall.

Known nonblocking limit: if the final live registry refresh after old-asset
retirement fails, primary installation remains committed, and obsolete live
entries may persist until safe restart; a separate success warning is not yet
exposed by the frozen v1 action contract. See Slice1 acceptance/usage evidence.

## Feature Plugin API1.1 H1/H4 (2026-11-15)

PluginData.reads: tuple[Literal["bi"], ...] defaults to empty. PluginCapability.
expose_as_tool defaults to true; false requires a read capability referenced by
a declared page route. New features require core_api.minimum>=1.1.0. Only these
two new fields are omitted from serialized data at their defaults; all existing
default fields remain in canonical manifests. Golden v1 fixtures pin raw package,
content digest, staged files and actual install ledger through parse/install/
restore. An old API1.0 closed parser refuses new-field packages as
plugin_package_invalid before compatibility checks; no silent downgrade is implied.

The Host binds AEP_PLUGIN_READ_BI only from its declared BI context on first start
and restart, preserves ordinary environment, and creates no BI data during install.
Page service bindings remain in worker health/call_read but not InstalledCapabilities
or ToolAccess. Tool-to-page updates use the normal version/busy/rollback semantics;
namespace ownership survives even when the plugin registers no Agent tools.
No new policy, grant, per-call approval, model-data or TurnEffects contract is added.
The existing worker protocol and PluginManagerProtocol remain unchanged.
