# Handoff

Date: 2026-10-01 (Asia/Taipei)
Branch: `codex/durable-platform-registry`
Base: `origin/main` at merge commit `779c08d` (PR #153)
PR: https://github.com/dragon0816/agentic-engineering-platform/pull/155

## Goal

Complete Productization 1 slice 6 by making the Shared Platform package catalog
and artifact store survive process restart without changing Registry,
synchronization or Bridge execution contracts.

## Completed

- Introduced the provider-neutral `PackageRegistry` boundary already consumed
  by authorization and control-plane services.
- Added `SqliteRegistry`, which stores validated `PublishedAssetPackage` JSON
  by exact `namespace + name + version` and artifact bytes by reference.
- Artifact SHA-256 is verified before an atomic package/artifact transaction;
  duplicate exact versions remain rejected after restart.
- Added schema versioning and fail-closed errors for unsupported schemas,
  corrupt records and unavailable storage. The CLI reports these as unusable
  configuration rather than starting or printing a traceback.
- Added optional absolute `registry_path` configuration. The deployable example
  uses it; omitting it retains the in-memory backend for inert tests.
- Proved that existing catalog discovery and synchronization consume reopened
  durable records through their unchanged contracts.
- Kept credentials, invitation proofs, member sessions, device selections,
  remote jobs, grants and all Bridge/local execution state outside the catalog.
- Updated Architecture, Contracts, Roadmap, Tasks, Phase 7 notes, the active
  Productization specification and deployment guide after validation.

## In Progress

- PR #155 is open. Exact-head GitHub Platform verification must pass before the
  owner-authorized automatic merge.

## Remaining

1. Wait for PR #155 exact-head Windows/Python 3.12 verification and merge it
   automatically when green.
2. Read Product Vision, acceptance tests, Roadmap and Tasks from merged `main`
   to name Productization stages 2 and 3. No stage-2/3 specification currently
   exists, so add the smallest architecture/acceptance slice before
   implementation rather than inventing a parallel platform.
3. Begin the first stage-2 vertical proof and stop before stage 3 unless its
   predecessor has a reproducible green path.

## Architecture decisions made

- **ADAPT** the existing in-memory package interface behind `PackageRegistry`;
  do not replace service, HTTP, member, authorization or Bridge wire contracts.
- Persist package metadata and the bytes synchronization needs in the same
  SQLite transaction. Metadata-only durability would make discovery survive
  while making installation fail after restart.
- Treat the Registry as the control-plane catalog only. Enrollment, runtime
  authorization, sessions, jobs and execution have different lifecycles and
  remain out of this bounded store.
- Refuse unknown database schemas and invalid stored contracts. There is no
  implicit migration or partial fallback to ambiguous data.

## Verification

Supported target: Windows, Python 3.12 only. No Ubuntu run was performed.
Browser automation was excluded per owner direction.

```text
Focused Registry/platform/transport suite:
python -m pytest tests/test_registry_sqlite.py tests/test_shared_platform_app.py
  tests/test_platform_transport.py -q
33 passed, 1 skipped

Full supported suite:
python -m pytest --ignore=tests/test_browser.py -q
1402 passed, 4 skipped in 54.14s

python -m ruff check .
All checks passed!

python -m ruff format --check .
304 files already formatted

python -m mypy
Success: no issues found in 238 source files

python -m pip check
No broken requirements found.

python -m build --outdir <repo>/.scratch/build-durable-registry
Successfully built sdist and wheel.

git diff --check
PASS
```

The four skips are existing Windows environment conditions: symlink/link
privileges, IPv6 loopback and directory links.

## Known issues

- SQLite now makes only packages and artifacts durable. A platform restart
  still loses enrollment, access tokens, member sessions, invitations, device
  selections and remote jobs.
- There is no Registry administration/publishing UI in this slice.
- SQLite schema upgrades intentionally fail closed; a future schema change
  needs an explicit, tested migration.

## Next Recommended Action

After PR #155 merges, inspect the merged product documents and create the next
bounded productization specification. Based on the current product direction,
the likely next user outcome is installing additional shared capability types
from Personal Agent Web, but the exact stage boundary and acceptance scenario
must be grounded in repository source-of-truth documents first.
