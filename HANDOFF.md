# Handoff

Date: 2026-10-01 (Asia/Taipei)
Branch: `codex/extension-staging`
Base: `origin/main` at merge commit `aa5093c` (PR #166)
PR: pending

## Goal

Productization 3 slice 2: verify and atomically stage a signed, compatible,
path-safe offline Bridge Extension package without installing or executing it.

## Completed

- PR #166 passed exact-head Windows/Python 3.12 CI and auto-merged. Agent
  Add-ons, Bridge Extensions and independent Applications now have separate
  contracts.
- Added a closed `PortableExtensionPackage`: exact published manifest,
  `requirements.lock`, direct offline wheels, per-file SHA-256, canonical
  content SHA-256 and a 64-byte Ed25519 signature.
- Added public `TrustedPublisherKey` and `ExtensionTrustPolicy` contracts with
  unique key identifiers and explicit revocation. The package signature key
  must match the manifest publisher key.
- Added an injected `ExtensionSignatureVerifier` protocol with no permissive
  default. Unknown/revoked keys, invalid signatures and incompatible packages
  fail closed before filesystem mutation.
- Added atomic identity-derived staging. It writes a short sibling temporary
  directory, reopens the package and verifies every written digest before
  rename. Existing exact versions are never replaced.
- Package paths reject absolute paths, drive paths, traversal, backslashes and
  publisher scripts. Staging creates no environment and performs no install,
  import, activation, advertisement, grant or execution.
- Focused tests cover valid staging, exact bytes, path safety, trust/revocation,
  signature failure, compatibility, digest drift, cleanup and replacement
  refusal.

## In Progress

- Complete full verification, open the slice 2 PR, wait for exact-head CI and
  auto-merge when green.

## Remaining

1. Slice 3: activate an approved staged version through one external JSON-lines
   subprocess, advertise only healthy declared capabilities and record crash/
   rollback evidence.
2. Slice 4: add read-only Application catalog discovery.
3. Slice 5: add extension lifecycle and Application projections to Personal
   Agent Web with the applicable human gates.

## Architecture decisions made

- Signature verification is a required injected Ed25519 boundary. Tests use a
  deterministic verifier double; production code cannot silently accept it.
- The first package format is Windows/Python 3.12 offline wheels plus a lock
  file. Staging does not run pip.
- Trust and revocation are local policy, separate from Registry publication.
- The host derives the directory from scoped identity; package content cannot
  select a filesystem destination.

## Verification

Supported target: Windows, Python 3.12 only. No Ubuntu or browser automation.

```text
Focused extension suite:
13 passed

python -m pytest --ignore=tests/test_browser.py -q
1434 passed, 4 skipped in 58.99s

python -m ruff check .
All checks passed!

python -m ruff format --check .
319 files already formatted

python -m mypy
Success: no issues found in 251 source files

python -m pip check
No broken requirements found.

python -m build --no-isolation --outdir <repo>/.scratch/build-p3-staging
Successfully built sdist and wheel; both include `extensions/package.py`.

git diff --check
PASS
```

## Known issues

- A concrete cryptographic provider/trust-store loader is intentionally outside
  the provider-neutral staging service. Callers must inject the verifier and
  trusted public keys.
- Staged packages are inert and cannot yet be activated; that is slice 3.

## Next Recommended Action

Complete verification and merge this slice, then add the bounded external
runner and explicit activation approval without importing publisher code.
