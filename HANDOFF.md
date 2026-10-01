# Handoff

Date: 2026-10-01 (Asia/Taipei)
Branch: `codex/addon-version-rollback`
Base: `origin/main` at merge commit `0e3137a` (PR #163)
PR: pending

## Goal

Productization 2 slice 5: provide an atomic exact-version update and rollback
path without deleting verified prior packages or mixing installation with
execution authorization.

## Completed

- PR #163 passed exact-head Windows/Python 3.12 CI and auto-merged; inert exact
  Agent profiles can now be selected, synchronized and explicitly activated.
- Added closed `MemberReplaceRequest` and `MemberReplacementReply` contracts.
  Requests name one Bridge, current exact identity and replacement exact
  identity; actor, kind, policy and decision time remain trusted platform state.
- Added an atomic authorization-registry replace operation. It validates active
  ownership, same asset family/kind, publication and entitlement before
  revoking the current selection and activating the replacement.
- Added `POST /v1/member/replace` and made the generic member catalog show
  `Switch` when another exact version in the same family is currently selected.
- Retained prior verified package bytes and inventory rows. Sync installs a
  missing new exact version; rollback synchronizes only authorization and reuses
  the prior local version with no download or rewrite.
- Added a real HTTP E2E proving v1 execution, v2 switch/install/execution,
  v1 rollback with zero installation, retained v1/v2 files and unchanged
  capability grants. Failure cases prove no partial selection mutation.

## In Progress

- Open the slice 5 PR, wait for exact-head Windows/Python 3.12 CI and auto-merge
  when green.

## Remaining

1. After merge, mark Productization 2 complete and record its combined exit
   evidence.
2. Begin Productization 3 slice 1: category and compatibility contracts for
   Agent Add-ons, Bridge Extensions and independent Applications.
3. Continue Productization 3 with inert extension staging before any executable
   extension runner.

## Architecture decisions made

- **REUSE/ADAPT** existing select/revoke, append-only local inventory and sync.
  Version replacement is one new atomic member operation, not another package
  manager.
- Removal means explicit revocation of active use. Local verified bytes remain
  inert so rollback evidence is not destroyed.
- A replacement must keep namespace/name/kind and change only exact version.
- Rollback is an ordinary authorized replacement in reverse. Local state never
  overrides or invents platform authorization.
- Capability grants are derived separately and remain unchanged by Add-on
  update, rollback or revoke.

## Verification

Supported target: Windows, Python 3.12 only. No Ubuntu or browser automation.

```text
Focused lifecycle/member suite:
23 passed

Full supported suite:
python -m pytest --ignore=tests/test_browser.py -q
1421 passed, 4 skipped in 59.02s

python -m ruff check .
All checks passed!

python -m ruff format --check .
313 files already formatted

python -m mypy
Success: no issues found in 245 source files

python -m pip check
No broken requirements found.

python -m build --no-isolation --outdir <repo>/.scratch/build-version-lifecycle
Successfully built sdist and wheel.

git diff --check
PASS
```

The four skips are existing Windows environment conditions: symlink/link
privileges, IPv6 loopback and directory links.

## Known issues

- Physical package garbage collection is intentionally absent. An unselected
  exact version is inert local rollback material, not active authority.
- Productization 3 executable Bridge Extensions still require their declared
  trust, isolation, activation and health contracts before runtime loading.

## Next Recommended Action

Open and merge this verified slice. Then mark Productization 2 complete and
start Productization 3 with category/compatibility contracts and inert package
staging only. Do not load publisher code into the Agent or Bridge process.
