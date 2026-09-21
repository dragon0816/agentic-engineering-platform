# Workflow checkpoint contract — Phase 3 slice 9

Status: contract/reference-model slice, approved scope 2026-09-21. No disk backend
or WorkflowEngine integration is included. The running platform remains in-memory.

## Requirement and plan

Define single-Bridge, single-writer restart evidence for manual recovery. Preserve
the current workflow/Bridge policy path and ResumePolicy. Add serializable contracts
in `common/checkpoints.py`, a store protocol and bounded in-memory reference model
in `workflow/checkpoints.py`, then validation and fault-window tests. Run the full
verification baseline, commit, open a PR and leave a reproducible handoff.

Architecture check: this is private execution-plane state, never a Registry asset,
an execution grant, a model route, or an n8n-specific runtime. No automatic recovery,
multi-worker leases, federation, production database, transport or secret resolver.

## Retained data and compatibility

RunCheckpoint v1 retains run ID, actor/namespace ownership, trace, exact manifest
snapshot, runtime compatibility identifier, intent fingerprint, ordered step
evidence, revision, and parent/continuation links. A stored manifest is provenance,
not authority: a future recovery coordinator must compare it and runtime compatibility
against installed definitions, revalidate input/output schemas and dependencies,
and obtain current authorization at preflight and each Bridge dispatch.

Arguments and completed results use PayloadRef (opaque local ID, SHA-256 and
contract identifier); no inline data, exception text, messages or credentials.
The host must store validated, secret-free payloads under owner access controls,
verify their digest and schema on retrieval, and refuse recovery if missing,
corrupt, incompatible or disallowed. A reference does not grant access. SecretRef
requirements in the manifest remain unresolved metadata. Arbitrary secret detection
is not claimed: even opaque identifiers must not be populated with credentials.

No TTL or silent eviction is defined in v1. At capacity, reject new runs. Retain
idempotency mappings and continuation links for the store lifetime; no deletion API
exists. A durable backend must retain these across restarts. Payload cleanup and
key expiration/tombstones need a separately specified policy before deployment;
deleting history must never silently make a used key executable again.
The memory reference defaults to 50 total records (including continuations), with
a configurable positive capacity. This is independent of the existing engine's
history/key limits; wiring or changing those limits is not part of this slice.

## State and write ordering

1. Complete static preflight and payload preparation before creating a record.
   Atomically create the run and its optional actor/namespace-scoped key binding.
2. Durably acknowledge `started` for the next step **before** Bridge dispatch.
   A failed or ambiguous acknowledgment forbids dispatch until state is inspected.
3. Validate the output and commit its protected payload before acknowledging
   `completed` with a result reference. Only then may the next step start.
4. At restart, `started` means `uncertain`, even if dispatch might not have happened.
   `completed` is reusable evidence; `never_started` has no recorded dispatch.
   A crash after the effect but before completion acknowledgment cannot be made
   exactly-once by this store. No step, including a read, resumes automatically.
5. The future coordinator marks an abandoned running record `suspended` only after
   it has exclusive ownership and knows the old process is dead. Caller-wait timeout
   is not abandonment and must not finalize the durable run.
6. An explicit resume uses the existing ResumePolicy and current authorization.
   Atomically reserve the parent's one continuation and create the child, preserving
   its completed prefix **and the first unresolved step's evidence**: a `started`
   (uncertain) parent step stays `started` in the child until the child itself
   re-acknowledges it, so a crash before that acknowledgment still classifies the
   step as uncertain without walking the parent chain. Keep the original key
   pointing to the original run.
7. `recovery_plan` reports a `running` record as `running` (its process may be
   alive) and only a `suspended` record as `needs_input`; `succeeded` is terminal.

The reference store checks linear progress, immutable intent and completed results,
revision compare-and-swap, owner isolation and atomic key/continuation relationships.
It is a trusted internal persistence boundary, not an authentication or policy server.
Only a future authorized coordinator may call its write methods. Its recovery_plan
is metadata-only evidence and grants no permission to dispatch.

Checkpoint persistence is correctness-critical and fails closed; it must not use
the best-effort progress/log reporting hook. Existing reporting remains best-effort.

## Store outcomes and fault acceptance

`create` returns the existing run for the same scoped key when the fingerprint
**and** the intent fields (manifest, runtime contract, arguments reference) match;
anything else is `key_conflict`. The caller must derive the fingerprint from exact
workflow, arguments and all non-trace RequestContext fields, as the current engine
does; it is not accepted from an untrusted submission. No key means a new run.
Run identifiers are scoped by owner: one owner can neither observe nor block
another owner's identifiers. `replace` is a compare-and-swap on the expected
revision; successful updates increment the stored revision once.
`continue_run` atomically updates parent and creates child; repeated reservation is
`already_continued` and the owner can inspect the existing link.

CheckpointStoreError carries only a closed code (conflict, missing, capacity,
invalid_transition, key_conflict, already_continued, unavailable, commit_unknown).
Unavailable means known no commit; commit_unknown means read back before proceeding.
After any ambiguous outcome, never repeat a capability or choose a new run/key as
an automatic fallback. There are no automatic store retries in this slice.

Tests cover JSON version/shape validation; invalid step order; no inline payloads;
owner isolation; stale writers; immutable success/intent; key conflicts and capacity;
atomic continuation; failure before start persistence; effect before completion
persistence; lost commit acknowledgment; and metadata-only recovery classification.
Memory tests simulate these windows; they do not prove filesystem crash durability.

Next slice: choose and review a local payload/storage backend, implement actual
transaction durability and restart tests, then wire the existing engine to this
boundary with fresh policy checks. Do not treat this reference model as deployment.

## SQLite backend (slice 10)

`workflow.checkpoints_sqlite.SqliteCheckpointStore(path, capacity=50)` is the
first durable backend: one local SQLite file per Bridge, standard library only,
single process and single owning thread. The path is host configuration and must
never point inside the project tree. The transition rules are the shared
functions in `workflow.checkpoints`, so the memory reference model and the SQLite
backend pass the same contract suite and cannot drift.

Each `create`, `replace` and `continue_run` is one `BEGIN IMMEDIATE` … `COMMIT`
transaction with `synchronous=FULL`; the call returns only after `COMMIT`
returned. Outcomes:

- `unavailable`: known not committed — the transaction could not start (for
  example a second writer holds the file), the file is closed, the schema version
  is unknown, a stored record no longer decodes, a statement failed before commit
  and was rolled back, or `COMMIT` itself reported `SQLITE_BUSY`/`SQLITE_LOCKED`.
  The same write may be retried by the coordinator; nothing was recorded.
- `commit_unknown`: `COMMIT` raised anything else (I/O class), so the write may
  or may not have reached the file. Read the record back from a fresh handle
  before deciding anything; never repeat a capability or pick a new run/key as
  a fallback.

Whatever happens inside a write — including an undecodable record or an
interrupt — the transaction is rolled back before the error propagates, so a
single failure can never wedge the connection or the file. A failed open closes
its handle. The primary key and a unique partial index on the idempotency key
are enforced by the database, not only by the application. The store is a
context manager; `close()` is idempotent.

Reads run outside transactions and are owner-scoped like the memory model.
Records store the checkpoint JSON plus indexed owner/run/key columns; they hold
evidence and `PayloadRef`s only. Capacity counts every persisted record,
including continuations, after a restart. A file whose `schema_version` is not
`1` refuses to open. There is still no TTL, eviction, deletion, payload storage,
engine wiring or automatic recovery.

## Payload storage (slice 11)

`workflow.payloads.FilePayloadStore(root, max_bytes=1_000_000)` is what a
`PayloadRef` points at: the validated, secret-free JSON a recovery coordinator
needs back — a run's arguments and each completed step's result. It lives beside
the checkpoint file, under the host's own access controls, and is the storage
half of the boundary whose evidence half is `RunCheckpoint`.

What is stored is a record of owner, contract and payload, and the digest of
that whole record is the storage identity. `put(owner, contract, payload)`
canonicalises the value (sorted keys, no NaN/Infinity), writes the record to
`root/<actor>/<namespace>/payload-<record digest>.json` and returns the
reference to record: `ref_id` is `payload-<record digest>`, `sha256` is the
digest of the payload value itself, `contract` is the declared contract. The
same owner, contract and payload always produce the same reference and file, so
writing twice is idempotent; the same value under two contracts, or for two
owners, is two records and stays readable. Writes are atomic (temporary file,
`fsync`, `os.replace`, then a best-effort directory `fsync`), so a crash or a
failed write never leaves a partial payload, and an existing file that no longer
hashes to its name is rewritten rather than reported as fine.

`get(owner, ref)` returns the payload only when everything agrees:

- `ref_id` must be `payload-` followed by 64 lowercase hex characters, checked
  before any path is built, so a reference can never name a file of its own
  choosing (`invalid_transition`);
- the stored bytes must hash to that identity — tampering, truncation or a
  swapped file is `unavailable`;
- the owner recorded *inside* the file must equal the requesting owner
  (`missing`), so a case-folding filesystem cannot fold ownership with it;
- the payload must still hash to `ref.sha256` (`unavailable`) and the stored
  contract must equal `ref.contract` (`invalid_transition`).

A reference to something that was never stored is `missing`. Payload
directories are per owner as well, but the record — not the location — is what
decides.

Limits and omissions: a payload above `max_bytes` is `capacity` and an
unserializable value is `invalid_transition`, both before anything is written.
There is no deletion API, TTL or eviction — a retained checkpoint may reference
its payloads for as long as it exists — and no encryption, secret resolution,
access control or engine wiring. Storing a credential in a payload remains
forbidden by the same rule that forbids it in a checkpoint.

## Engine recovery (slice 12)

`WorkflowEngine(..., journal=RunJournal(checkpoints, payloads))` turns the
contracts above into behavior on the real execution path. Without a journal the
engine is unchanged: in memory only, exactly as before.

Write-ahead ordering, as specified in "State and write ordering":

1. `begin` commits the run arguments as a payload and creates the run record
   **before** anything executes. A store that cannot acknowledge the run means
   no run at all (`unavailable/checkpoint_<code>`, no run record in memory).
2. Before each step, `started` is acknowledged. If that write fails or is
   ambiguous the step is **not dispatched**, and the run fails
   `checkpoint_<code>`; the evidence still reads `never_started`, which is true.
3. After a step succeeds, its result payload is committed and only then is the
   step recorded `completed`. If either write fails the step already ran, so the
   evidence stays `started` — uncertain, which is also true.
4. A run whose every step is completed *is* succeeded, so the final step's
   completion and the terminal marker are one write, never two.

Recovery is manual, as approved. `inspect_journal(context, run_id)` returns the
durable evidence for a run this process may know nothing about.
`suspend(context, run_id, SuspensionConfirmation(...))` records a person's
explicit claim that the owning process is gone — `process_confirmed_stopped`
must be exactly `True`, the operator is recorded, and the platform never infers
any of it. A run still executing in this engine is refused: a caller-wait
timeout is not abandonment.

`recover(context, run_id, policy)` continues a **suspended** run, in this
process or a later one. The stored manifest is provenance: the same version must
still be installed and identical, or recovery refuses with `manifest_changed`.
The completed prefix is restored from verified payloads and never re-run,
pre-flight runs again, every remaining step is authorized again *now*, and an
uncertain step is replayed only as the `ResumePolicy` allows. The continuation
is a new run whose `resumed_from` names the original, reserved atomically
through `continue_run`.

An idempotency key that already names a durable run conflicts rather than
starting a second one, even in a process whose in-memory key table is empty.
