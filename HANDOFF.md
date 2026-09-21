# Handoff — Phase 3 protected payload storage (slice 11)

Updated: 2026-09-21 (Asia/Taipei).
Branch: `phase-3/payload-storage`, based on `main` at `fac59f1` (PR #17 merged).

## Goal

Phase 3 slice 11 under the owner-approved scope (recorded in
`docs/phases/PHASE_3_WORKFLOW.md`, slice 11): a content-addressed local store
for what a `PayloadRef` points at — beside the checkpoint file, schema validated
before writing, digest and contract verified on reading, owner-isolated
directories — with no secrets, no TTL/deletion and no engine wiring. Normative
plan: `docs/WORKFLOW_CHECKPOINTS.md` ("Payload storage"); source decision:
`docs/PHASE_3_MIGRATION.md` (slice 11).

## Completed

- `workflow/payloads.py`: `PayloadStore` protocol and `FilePayloadStore(root,
  max_bytes=1_000_000)`. `put` canonicalises the value (sorted keys, ASCII, no
  NaN/Infinity), stores it at
  `root/<actor>/<namespace>/payload-<sha256>.json` and returns the `PayloadRef`
  a checkpoint records; equal values share one file, so repeated writes are
  idempotent. Writes are atomic (temp file, `fsync`, `os.replace`) and a failed
  write leaves nothing behind.
- `get` returns the payload only when the reference's own parts agree
  (`ref_id == payload-<sha256>`, else `invalid_transition`), the stored bytes
  hash to `ref.sha256` (else `unavailable`) and the stored contract matches
  (else `invalid_transition`); an unstored reference is `missing`. The file name
  derives from the validated digest alone, never from caller text, so a
  reference cannot name a path.
- Oversized payloads are `capacity` and unserializable values are
  `invalid_transition`, both before anything is written. One owner's reference
  cannot read another owner's payload.
- 23 tests (`tests/test_payloads.py`): round trips for every JSON shape,
  contract preservation, deduplication and idempotent writes, the same value
  under two contracts, owner isolation including case-folding filesystems,
  unknown and malformed references, tampered/truncated/swapped/NaN files,
  self-healing writes, disagreeing references, limits, invalid owner/contract,
  failed writes, restart and the exact stored record shape.
- PR #18 opened; pre-merge review applied: the storage identity is now the
  digest of the whole record (owner, contract, payload), so the same value
  under two contracts no longer collides into one unreadable reference; the
  owner inside the record is checked on every read, so a case-folding
  filesystem cannot fold ownership; `get` verifies the raw bytes before parsing
  and rejects NaN/Infinity literals, so a corrupt file can no longer raise a
  bare `ValueError`; `put` rewrites a file that no longer hashes to its name
  instead of reporting success forever; and the directory is fsynced after the
  rename where the platform supports it.
- Docs: phase spec slice 11 (approved scope) and sequence, checkpoint plan
  "Payload storage" section, `docs/CONTRACTS.md`, migration slice-11 decision,
  README.

## In Progress

- Opening the review PR for this branch; review and CI results are recorded on
  the PR once available.

## Remaining

- Review and merge the payload storage PR after the posted review.
- Next Phase 3 slice (needs explicit scope): engine recovery — `WorkflowEngine`
  writing checkpoints on the real execution path (write-ahead `started` before
  dispatch, `completed` only after the payload is committed) and manual restart
  recovery through the existing Gateway/Bridge policy path with fresh
  authorization. This first needs the coordinator ownership semantics of
  `docs/WORKFLOW_CHECKPOINTS.md` item 5: who may mark an abandoned `running`
  record `suspended`, and how they establish that the old process is gone.
- Earlier deferred reviews remain: bounded Bridge event history, SkillRegistry
  parse cost, MCP installation round trips, Review `not_required` semantics,
  generic top-level package names, repeated RequestContext validation.

## Architecture decisions made

- The digest is the identity: a payload is stored under its own SHA-256 and
  verified again on every read, so recovery can never be fed something the run
  did not produce. Deduplication is a consequence, not a goal.
- The reference decides what is acceptable; the file never gets a vote. A
  mismatch is a distinct closed code, never a best guess or a silent read.
- `PayloadRef.ref_id` is `payload-<digest of the stored record>`: a digest may
  start with a digit and `Symbol` may not, and deriving the file name from a
  validated digest makes path traversal impossible by construction. `sha256`
  remains the digest of the payload value itself.
- Ownership is evidence, not a location: the owner is inside the record and is
  checked on read, so the store does not depend on filesystem case semantics.
- Payload evidence stays small (1 MB default). Attachments and run artefacts are
  not payloads; the source's own 4 KB step-result summary cap informed the
  modest default.
- No deletion, TTL, eviction, encryption, secret resolution or access control:
  directory permissions are the host's responsibility, and a retained checkpoint
  may reference its payloads for as long as it exists.

## Exact verification commands and results

Windows, Python 3.12.14, repository root:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 419 tests (396 prior + 23 payload)
.venv/Scripts/python.exe -m ruff check .
# PASS
.venv/Scripts/python.exe -m ruff format --check .
# PASS
.venv/Scripts/python.exe -m mypy
# PASS: 56 source/test files
.venv/Scripts/python.exe -m pip check
# PASS
.venv/Scripts/python.exe -m build
# PASS: sdist and wheel; the payload store ships in the sdist
git diff --check
# PASS
```

Payload files live under pytest's temporary directory. No production service,
database server, transport, model, job or n8n instance was invoked. Local pytest
uses `-p no:cacheprovider` because of temporary-directory ACLs on this machine;
CI runs ordinary pytest.

## Known issues / limitations

- Nothing in the running platform writes or reads payloads yet; this is the
  storage half of a boundary whose engine wiring is a later slice.
- No encryption at rest and no access control beyond per-owner directories;
  a host that shares a directory across owners breaks the isolation this store
  assumes.
- Digest verification detects tampering on read, but a host that can rewrite
  both the payload and the checkpoint can still present a consistent lie; the
  store is not an integrity authority against its own operator.

## Next Recommended Action

Open the PR for `phase-3/payload-storage` against `main`, run the review, apply
confirmed findings and let the owner merge. Then scope engine recovery with the
owner, starting with the coordinator ownership question above.
