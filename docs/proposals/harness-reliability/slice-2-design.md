# Slice 2 — worker ownership after timeout

The owner selected durable operation tracking and exclusion until execution ends,
reusing existing state storage (2026-11-18). This replaces the pending direction
question in slice-1-results.md.

## Requirements and contract

Bridge timeout/cancellation does not terminate a synchronous worker. Neither a
deadline, a restarted host nor an absent PID proves that side effects stopped.
Claim the resource atomically before dispatch; only the worker acknowledges its
terminal observation. Keep unknown outcomes claimed until explicit reconciliation.
Failed persistence acknowledgments must prevent new dispatch or retain exclusion.

Use the existing SqliteLocalState database, schema 7, and existing
SuspensionConfirmation operator contract. Store operation IDs, hashed canonical
resource keys, actor/capability/trace identities, timestamps, status and closed
codes. Do not store arguments, paths, output or credentials. In-memory library
Bridge instances share claims only when given the same store. Company runtime
binds Bridge to its existing durable state. No additional authorization service.

Initial integration covers coding.run_python and CodingHarness task workers.
They share one canonical workspace key, so different coding capabilities cannot
overlap in the same workspace. Different roots, parent/child overlaps, unrelated
capabilities and hosts using separate databases are not globally coordinated.
This is exclusion, not process termination or exactly-once execution. Direct
low-level library calls without a Bridge context are outside this boundary.

## Verification and rollout

Exercise two SQLite connections/Bridges, timeout, actual worker completion,
independent resources, durable reopen, unknown process result, claim/finish
acknowledgment failures and explicit stopped confirmation. Verify migration from
schema 6 preserves existing rows. No timer or automatic retry releases a claim.

Old binaries reject schema 7 rather than silently ignoring unresolved claims.
Before rollout back up a quiescent database. Rollback must retain/reconcile active
claims; never delete the table or restore an older snapshot while workers may run.
No production host/database is migrated by this development work.
