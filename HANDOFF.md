# Handoff

Date: 2026-10-01 (Asia/Taipei)
Branch: `codex/knowledge-marketplace-activation`
Base: `origin/main` at merge commit `4a7a88d` (PR #159)
PR: pending

## Goal

Productization 2 slice 3: let a member select exact shared Knowledge, install
its portable package and use it from Personal Agent Web after host rebuild.

## Completed

- PR #159 passed exact-head CI and auto-merged; portable Knowledge package
  contracts and atomic local installation are on main.
- Added `knowledge` to the member-selectable and synchronization-installable
  Agent Add-on kinds. Member requests still contain only Bridge and exact asset
  identity; the Registry derives kind.
- Extended Bridge sync to require exact agreement between Registry governance
  metadata and the manifest inside the portable artifact, derive a versioned
  local Vault path, install the package and write the local manifest.
- Existing local manifest/Vault pairs are revalidated for crash recovery;
  mismatches and publisher-chosen paths are refused as conflicts.
- Host rebuild derives active Knowledge bindings from the synchronized
  authorization and accepts them only at the identity-derived local path.
- Personal Agent Web lists selected installed Knowledge without exposing local
  paths and uses the existing exact knowledge query capability.
- Moved platform-derived grant construction after configured built-in handlers
  are registered, so model-backed selected capabilities can receive only their
  already-declared policy grant.
- Added a real HTTP E2E across member portal, control-plane sync, package
  install, host rebuild and Personal Agent Web grounded answer. The control
  plane is stopped before the answer, proving local-first operation.

## In Progress

- Open the slice 3 PR, wait for exact-head CI and auto-merge when green.

## Remaining

1. Productization 2 slice 4: validated Agent profile package plus explicit
   local activation that narrows Skills, Knowledge, capabilities and model
   requirements without adding delegation.
2. Slice 5: explicit update/removal and rollback, preserving one prior usable
   exact version and keeping capability authorization separate.
3. Close Productization 2 with a reproducible Personal Agent Web add-on proof.
4. Begin Productization 3 category contracts only after that exit passes.

## Architecture decisions made

- **REUSE/ADAPT** member selection, `DeviceAuthorization`, package sync,
  `KnowledgeCatalog` and Personal Agent Web. No second marketplace or query
  runtime was introduced.
- Knowledge selection is installation state, never a model or capability
  grant. A separate model binding and `knowledge-query/ask@1.0.0` capability
  selection remain mandatory.
- Registry metadata must match the portable manifest so entitlement and local
  behavior cannot describe different governance.
- Synchronized Knowledge is bound only from an exact identity-derived path;
  explicit operator-owned local Knowledge bindings remain supported.

## Verification

Supported target: Windows, Python 3.12 only. No Ubuntu or browser automation.

```text
Focused member/platform/Knowledge/Personal Web suite:
109 passed, 1 skipped

Full supported suite:
python -m pytest --ignore=tests/test_browser.py -q
1417 passed, 4 skipped in 56.52s

python -m ruff check .
All checks passed!

python -m ruff format --check .
310 files already formatted

python -m mypy
Success: no issues found in 242 source files

python -m pip check
No broken requirements found.

python -m build --no-isolation --outdir <repo>/.scratch/build-knowledge-marketplace
Successfully built sdist and wheel.

git diff --check
PASS
```

The four skips are existing Windows environment conditions: symlink/link
privileges, IPv6 loopback and directory links.

## Known issues

- Agent profiles are still Registry metadata only and cannot yet be installed
  or made active; that is the next slice.
- Version removal/rollback is not yet represented by a synchronization plan;
  sync still only adds missing exact versions.

## Next Recommended Action

Open and merge this verified slice. Then define a closed inert Agent-profile
package, validate every referenced Skill/Knowledge/capability/model requirement
against what the host already has, and persist one explicit active profile.
Do not add specialist delegation or executable plug-in loading.
