# Handoff

Date: 2026-10-01 (Asia/Taipei)
Branch: `codex/application-catalog`
Base: `origin/main` at merge commit `bd7964b` (PR #171)
PR: pending

## Goal

Productization 3 slice 4: provide authenticated, entitlement-filtered read-only
discovery of independent Applications without treating them as Agent/Bridge
packages.

## Completed

- PR #171 passed exact-head Windows/Python 3.12 CI and auto-merged; explicitly
  approved staged extensions can now run through the bounded external runner.
- Added `ApplicationCatalog`, retaining exact published Application versions
  and refusing duplicate identities.
- Added `ApplicationCatalogRequest` with optional namespace and
  `ApplicationCatalogReply` containing only external Software projections.
- Added `MemberService.application_catalog`. It authenticates the direct member
  session, derives actor/groups from platform-owned enrollment and applies
  normal visibility/owner entitlement. The request carries no actor/group,
  repository, Bridge or entitlement claim.
- Added `/v1/member/applications`. Discovery needs no Bridge binding and exposes
  no Application select/install/activate operation.
- Shared platform state now owns the Application catalog and supplies it to the
  separate member entry point.
- Real HTTP tests prove organization visibility, private exclusion, namespace
  filtering, session authentication, no package/install/selection fields and
  no device grant mutation.

## In Progress

- Complete full verification, open the slice 4 PR, wait for exact-head CI and
  auto-merge when green.

## Remaining

1. Slice 5: present independent Applications and Bridge Extension lifecycle in
   Personal Agent Web, preserving the applicable human gates.
2. Complete Productization 3 exit verification and documentation.

## Architecture decisions made

- Applications are external Software and therefore member-scoped rather than
  device-selected. Discovery neither requires nor modifies a Bridge.
- Application visibility uses the same platform-owned membership entitlement
  semantics as other governed assets.
- Repository locator and integration URLs appear only after entitlement and do
  not become execution authority.

## Verification

Supported target: Windows, Python 3.12 only. No Ubuntu or browser automation.

```text
Focused member/Application/shared-platform HTTP suite:
19 passed

Targeted mypy:
Success: no issues found in 5 source files

python -m pytest --ignore=tests/test_browser.py -q
1446 passed, 4 skipped in 60.24s

python -m ruff check .
All checks passed!

python -m ruff format --check .
322 files already formatted

python -m mypy
Success: no issues found in 254 source files

python -m pip check
No broken requirements found.

python -m build --no-isolation --outdir <repo>/.scratch/build-p3-apps
Successfully built sdist and wheel.

git diff --check
PASS
```

## Known issues

- Application entries are in-memory in the reference composition. Durable
  Application/Software storage can use the same catalog abstraction later;
  this slice does not expand the Package Registry schema.
- The member HTML page remains Agent Add-on-only until slice 5; the new route is
  already available to that UI.

## Next Recommended Action

Complete verification and merge this slice, then add lifecycle/read-only
marketplace sections to Personal Agent Web without merging category semantics.
