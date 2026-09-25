# Foundation contracts (0.1)

All boundary models reject unknown fields, validate defaults, and serialize with
Pydantic `model_dump_json` / `model_validate_json`. Metadata is frozen; Registry
ingress revalidates and stores serialized snapshots so caller mutations cannot alter
registered assets. Pydantic is a validation dependency, not a provider contract.

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

Optional `integrations.n8n` is imported only by hosts that need it:

- `N8nWorkflowBinding`: trusted stable binding id and exact scoped workflow version.
- `N8nSubmission`: closed operation id plus JSON argument map. Context, target,
  timeout, credentials, permissions and resume policy are not payload fields.
- `N8nAdapter.submit`: validates the submission and derives an idempotency key from
  binding id and operation id, then calls Gateway.execute_workflow with unchanged
  arguments and separately authenticated host context. Hashing keeps the key within
  the engine's bounds; it is not authorization. No adapter cache/retry is added.
- `inspect`/`watch`: reuse Gateway run-control contracts and additionally filter
  by bound workflow. Owner/namespace checks remain in the engine; other owners and
  other workflows receive no plan/stream. No adapter resume method is exposed.

Operation id stability is the caller's responsibility. A fresh trace on redelivery
is allowed; other context, target or argument changes conflict. Engine-lifetime
deduplication, retained-key capacity, caller-timeout overlays and progress lag/close
semantics all remain unchanged. No n8n SDK, HTTP server, credentials, production
instance or notification transport is introduced. See
`integrations/n8n/README.md` for offline host wiring and source status differences.
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
and including pictures placed in placeholders; DOCX paragraphs (headings
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
order, PPTX speaker notes are not extracted, a skipped image leaves no trace
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
packages)` records decisions and refuses the ones a member may not make:
`actor_not_admitted` for a device they are not bound to, `asset_not_published`
and `kind_mismatch` against the Registry, `tool_not_advertised` for a
capability the device does not say it has, `approval_required` for a tool
whose own `CapabilitySpec` requires one, `approver_not_member` when the
approver is not an active platform member, `tool_not_grantable` for a
capability that declares no policy reference and so cannot be granted to
anybody, `decision_in_future` for a decision no bundle could carry,
`duplicate_selection`, and `selection_missing` on revocation. `grants(bridge_id)` derives the device's
`CapabilityGrant`s through `grant_from(spec, selection)`: the permissions and
policy references are the capability's own declaration and the approval is the
member's, so a decision about which tools never becomes a decision about what
they may do. Grants are per actor, and a machine has one member, so a device's
grants are that member's; on a shared test workstation they are the virtual
member's. The approver is checked against the platform's members rather than
the device's, because one member per machine would otherwise leave
`approved_by` able to name only the member giving the approval.

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

## Shared-platform transport (Phase 7, slice 2i)

`common.sync` is the wire between a Bridge and the shared platform: six
operations (`probe`, `advertise`, `sync`, `report`, `poll`, `settle`), each a
closed request and reply. `ProbeReply` is the `AuthenticatedActor` the token
produced, which must name a device, plus the platform's clock. `SyncRequest`
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
name, and an optional `ssl.SSLContext` that wraps the socket. It serves the
in-memory references; a durable platform store is a later slice.

`host_runtime.contracts.PlatformBinding` is how a host names its platform:
`base_url` (an origin: https, or http on loopback only, with no path, query,
fragment or credential), `token_id`, the `SecretRef` of the token's secret and a timeout; `CompanyHostConfiguration.platform` is
optional and a host without it works locally. `HostLayout` moved to the
contracts module and is still importable from `host_runtime.host`.

`host_runtime.sync.PlatformClient` is the Bridge's side. `_call` resolves the
secret per call through the resolver and classifies every reply into a
`Reachability`: `answered`; `unreachable` (a transport fault, a 5xx, a reply
that is not a `WireFailure` — an intermediary's bare 401 included), always
retryable; `withdrawn`; `rejected` (`authentication_failed`: this host's
configuration is wrong); `refused` (anything else declined). Only `answered`
changes anything on the Bridge. `probe`, `advertise` and `report` change
nothing locally; the credential is resolved per call through
`models.wire.authorized`, under the rule every HTTP adapter shares. `synchronize(layout, state)` refuses before calling when
`grants.json` exists (`sync_grants_conflict`), then applies a reply in this
order: `verify_installation` over the whole plan against the SQLite
inventory; each artifact parsed as the manifest its kind names and carrying
the identity its package claims (`sync_asset_invalid`); each file it would
write compared with any hand-placed asset of the same identity, a conflict
unless the bytes are identical (`sync_asset_conflict`); then the manifests
written atomically as `<namespace>__<name>__<version>.json`, the inventory
recorded in one transaction, and `authorization.json` replaced atomically. A
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
