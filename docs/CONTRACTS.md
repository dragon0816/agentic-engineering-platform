# Foundation contracts (0.1)

All boundary models reject unknown fields, validate defaults, and serialize with
Pydantic `model_dump_json` / `model_validate_json`. Metadata is frozen; Registry
ingress revalidates and stores serialized snapshots so caller mutations cannot alter
registered assets. Pydantic is a validation dependency, not a provider contract.

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
