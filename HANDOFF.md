# Handoff

Date: 2026-10-01 (Asia/Taipei)
Branch: `codex/extension-application-contracts`
Base: `origin/main` at merge commit `487a4a9` (PR #165)
PR: pending

## Goal

Productization 3 slice 1: establish closed, provider-neutral categories for
out-of-process Bridge Extensions and independent Applications before any
publisher code can be staged or executed.

## Completed

- Productization 2 is complete. PR #165 passed exact-head Windows/Python 3.12
  CI and auto-merged; version switching and rollback retain verified inactive
  package bytes without changing capability grants.
- Added `BridgeExtensionManifest` with exact Windows/Python/ABI/protocol
  compatibility, a dedicated-process entry point, typed capabilities, bounded
  health/crash/rollback policy and a public Ed25519 publisher-key reference.
- Published extensions require approved technical policy, policy references
  and validation evidence. Duplicate capabilities and protocol mismatches are
  rejected.
- Added `bridge_extension` to Registry package kinds while keeping it outside
  `MemberCatalogEntry`; extension publication remains separate from Agent
  Add-on selection, activation and capability authorization.
- Added `ApplicationCatalogEntry` and `ApplicationProjection` over a published
  `SoftwareManifest`. Applications expose only declared HTTPS/loopback API,
  MCP, UI or exact Workflow integration metadata and never become Agent/Bridge
  packages.
- Recorded Productization 3 runtime decisions: one dedicated subprocess per
  exact version, JSON-lines IPC, Ed25519 trust/revocation, offline Windows
  Python 3.12 wheelhouses, separate activation approval, bounded health/crash
  policy and retention of at least two verified versions.

## In Progress

- Finish full verification, open the slice 1 PR, wait for exact-head CI and
  auto-merge when green.

## Remaining

1. Productization 3 slice 2: verify and atomically stage signed, compatible,
   path-safe offline extension packages without importing or executing code.
2. Slice 3: activate an approved staged version through the bounded external
   runner, advertise only healthy declared capabilities and retain rollback
   evidence.
3. Slice 4: add read-only independent Application catalog discovery.
4. Slice 5: add extension lifecycle and Application projections to Personal
   Agent Web with the applicable human gates.

## Architecture decisions made

- Agent Add-ons, Bridge Extensions and Applications have distinct lifecycle
  and installation boundaries even when one marketplace presents them.
- Registry publication, package staging, activation approval, capability
  advertisement and execution authorization remain separate decisions.
- Publisher code never runs in the Agent or Bridge core process.
- An Application remains external governed Software; its marketplace entry is
  discovery/integration metadata rather than an executable package.
- No production side effect or external-system write is introduced by this
  slice.

## Verification

Supported target: Windows, Python 3.12 only. No Ubuntu or browser automation.

```text
Focused contract suite:
47 passed

python -m pytest --ignore=tests/test_browser.py -q
1426 passed, 4 skipped in 59.37s

python -m mypy
Success: no issues found in 249 source files

python -m ruff check .
All checks passed!

python -m ruff format --check .
317 files already formatted

python -m pip check
No broken requirements found.

python -m build --no-isolation --outdir <repo>/.scratch/build-p3-contracts
Successfully built sdist and wheel; both include the new modules.

git diff --check
PASS
```

## Known issues

- Signature bytes, trust-store resolution, staging and activation are
  intentionally absent until slice 2; a manifest cannot execute anything.
- Windows process isolation is a bounded subprocess boundary, not a claim of
  OS sandbox equivalence. The Bridge still enforces capability policy.

## Next Recommended Action

Complete verification and merge this slice, then implement inert signed
extension staging. Do not import or launch publisher code in slice 2.
