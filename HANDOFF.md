# Handoff

Date: 2026-10-01 (Asia/Taipei)
Branch: `codex/web-sync-action`
Base: `origin/main` at merge commit `c70a687` (PR #147)
PR: https://github.com/dragon0816/agentic-engineering-platform/pull/149

## Goal

Complete Productization 1 slice 3 by exposing the existing verified,
all-or-nothing shared-platform synchronization as an explicit Personal Agent
Web action. Preserve catalog discovery as read-only and show typed state from
immediately before and after the attempt.

## Completed

- Added closed `PlatformSyncRequest` and typed Web projection/result contracts.
  They carry catalog, authorization and installed facts separately, plus the
  existing five-state reachability result, without credentials or artifact
  bytes.
- Refactored `AgentWeb.platform` to build the typed projection under the
  existing one-at-a-time lock.
- Added `AgentWeb.synchronize`, which calls the existing
  `PlatformClient.synchronize` path. No installer, selection or authorization
  logic was added to the Web layer.
- Added authenticated loopback `POST /api/platform/sync`. It accepts only the
  closed empty request, so the browser cannot submit an actor, asset selection
  or installation instruction.
- Added a deliberate **Synchronize selected assets** button. Opening the Shared
  Platform tab still performs only the read-only catalog request; the page
  renders typed success/refusal state and the returned after-snapshot.
- Added real-socket integration coverage for success, no configured platform,
  an unreachable platform, a local grants conflict, invalid request shape,
  bearer authorization, Host-header protection and the no-auto-sync page rule.
- Updated Architecture, Contracts, Roadmap, Tasks and the active Productization
  specification after the implementation passed verification.

## In Progress

- PR #149 is open. Exact-head GitHub Platform verification is pending.

## Remaining

1. Wait for PR #149 exact-head CI and fix any failure caused by this slice.
2. Owner review and merge after CI is green.
3. Productization 1 slice 4: add a generic Workflow launch form driven by the
   installed Workflow contract and the existing Agent/Gateway path.
4. Then add grounded Knowledge asking and durable Registry storage, in that
   order.
5. Before generalized marketplace installation, define separate installer
   contracts for Agent Add-ons, Bridge Extensions and independent Applications.

## Architecture decisions made

- **ADAPT** the in-repository `PlatformClient.synchronize` implementation.
  Source repositories contain no competing Personal Agent Web synchronization
  path, so there is nothing to migrate or rewrite.
- The Web endpoint is an ingress and projection only. Whole-reply verification,
  conflict detection, atomic writes and inventory recording remain owned by
  `PlatformClient` and local state.
- The action takes no asset identity because member selection belongs to the
  separate member-authenticated platform entry point. Synchronization applies
  the platform's complete current decision bundle.
- Published, authorized, installed and executable remain independent states.
  Synchronization changes the middle two only; execution continues through
  Agent/Gateway/Workflow/Bridge policy.
- One lock covers the before snapshot, synchronization and after snapshot so a
  concurrent Web ask or refresh cannot interleave with the local write.

## Verification

Supported target: Windows, Python 3.12 only. No Ubuntu run was performed.
Browser automation was not run; HTTP behavior was exercised over real loopback
sockets.

```text
Focused Web/transport/contracts suite:
python -m pytest tests/test_agent_web.py tests/test_platform_transport.py
  tests/test_contracts.py -q --basetemp=<repo>/.scratch/...
72 passed, 1 skipped

Final Web slice suite:
python -m pytest tests/test_agent_web.py -q --basetemp=<repo>/.scratch/...
22 passed

Full suite (browser test excluded per owner instruction):
python -m pytest --ignore=tests/test_browser.py -q --basetemp=<repo>/.scratch/...
1384 passed, 4 skipped in 49.94s

python -m ruff check .
All checks passed!

python -m ruff format --check .
302 files already formatted

python -m mypy src tests
Success: no issues found in 236 source files

python -m pip check
No broken requirements found.

python -m build --outdir <repo>/.scratch/dist-web-sync
Successfully built sdist and wheel.

Wheel content smoke:
host_runtime/contracts.py, host_runtime/web.py and host_runtime/web_page.py are
present, and the packaged page contains /api/platform/sync.

git diff --check
PASS
```

The four full-suite skips are existing Windows environment conditions:
symlink/link privileges, IPv6 loopback and directory links. Test caches and
temporary files were directed to the repository's writable `.scratch` area.

## Known issues

- The shared-platform reference stores remain in memory and lose state on
  restart; durable Registry storage is slice 6.
- The Web action synchronizes all current selections as one verified bundle;
  selecting/revoking individual Workflows remains in the separate Member Portal.
- A successful sync installs assets and decisions but does not grant local
  capability permission. The operator must still supply the applicable Bridge
  policy grants.
- The page reports completion after the synchronous request returns; progress
  streaming is deferred to the generic Workflow launch slice.

## Next Recommended Action

After this PR merges, implement Productization 1 slice 4 as a generic Workflow
launch form. Derive the form from the installed Workflow input contract, submit
through the normal Agent/Gateway path, and show progress, result and trace
identifiers without adding workflow-specific code to the page.
