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
   its completed prefix. Keep the original key pointing to the original run.

The reference store checks linear progress, immutable intent and completed results,
revision compare-and-swap, owner isolation and atomic key/continuation relationships.
It is a trusted internal persistence boundary, not an authentication or policy server.
Only a future authorized coordinator may call its write methods. Its recovery_plan
is metadata-only evidence and grants no permission to dispatch.

Checkpoint persistence is correctness-critical and fails closed; it must not use
the best-effort progress/log reporting hook. Existing reporting remains best-effort.

## Store outcomes and fault acceptance

`create` returns the existing run for the same scoped key/fingerprint; changed
fingerprint is `key_conflict`. The caller must derive the fingerprint from exact
workflow, arguments and all non-trace RequestContext fields, as the current engine
does; it is not accepted from an untrusted submission. No key means a new run.
`replace` requires the expected revision; successful updates increment it once.
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
