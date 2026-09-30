# Handoff

Date: 2026-10-01 (Asia/Taipei)
Branch: `codex/portable-knowledge-package`
Base: `origin/main` at merge commit `cfec50d` (PR #157)
PR: pending

## Goal

Productization 2 slice 2: define and prove a portable, path-safe Knowledge
package before Knowledge joins member selection and Bridge synchronization.

## Completed

- PR #157 passed exact-head Windows/Python 3.12 CI and auto-merged as
  `cfec50d`; exact Skill selection, sync and Personal Agent use are on main.
- Added `PortableKnowledgePackage` and `KnowledgePackageFile` contracts for one
  exact published Knowledge version.
- Package content is limited to governed Raw/Wiki content plus index, log and
  settled decisions. `drop/` originals and local ingest state are excluded.
- Portable manifests use `package://vault`; installation derives the local
  absolute Vault path instead of trusting publisher input.
- Added builder and staged atomic installer with file and aggregate digest
  verification before exposure. Existing exact versions are never replaced.
- Added rejection coverage for traversal, absolute/Windows paths,
  noncanonical paths, unowned content, missing files, identity/digest drift and
  recognizable embedded credentials.
- Updated Architecture, Contracts, Tasks and the Productization 2 phase spec
  after the tests passed.

## In Progress

- Open the slice 2 PR, wait for exact-head Platform verification and auto-merge
  when green.

## Remaining

1. Productization 2 slice 3: admit exact Knowledge selection, synchronize its
   portable package into a host-derived versioned Vault, derive an active local
   binding and prove grounded Personal Agent Web asking after host rebuild.
2. Slice 4: portable validated Agent profile and explicit local activation.
3. Slice 5: explicit version update/removal and rollback to a usable prior
   exact version.
4. Begin Productization 3 only after the Productization 2 exit path passes.

## Architecture decisions made

- **REUSE/ADAPT** `KnowledgeManifest`, Vault digests/provenance and the existing
  package artifact boundary. No alternate Knowledge runtime was introduced.
- A portable manifest carries a symbolic path. Only the Bridge may bind an
  installed package to an absolute local Vault root.
- Raw evidence and Wiki Markdown travel; source originals in `drop/` do not.
  This preserves query provenance without redistributing source files whose
  rights and size are not represented by the current contract.
- Packages are inert JSON/base64 data. They contain no scripts, imports,
  post-install commands, grants, model credentials or execution approval.

## Verification

Supported target: Windows, Python 3.12 only. No Ubuntu or browser automation.

```text
Focused Knowledge package/evolution/query/Vault suite:
41 passed, 1 skipped

Full supported suite:
python -m pytest --ignore=tests/test_browser.py -q
1415 passed, 4 skipped in 55.37s

python -m ruff check .
All checks passed!

python -m ruff format --check .
309 files already formatted

python -m mypy
Success: no issues found in 241 source files

python -m pip check
No broken requirements found.

python -m build --no-isolation --outdir <repo>/.scratch/build-knowledge-package
Successfully built sdist and wheel.

git diff --check
PASS
```

The four skips are existing Windows environment conditions: symlink/link
privileges, IPv6 loopback and directory links.

## Known issues

- The package contract and local atomic installer are complete, but member
  activation and platform synchronization intentionally remain slice 3.
- The current aggregate Knowledge digest excludes binary files below
  `raw/**/assets/` while `raw_sha256` covers them; both established digests are
  verified and the package preserves those files.

## Next Recommended Action

Open and merge this verified slice, then extend the trusted member selection
and platform sync contracts to `knowledge`. Install its portable artifact into
`workspace/assets/knowledge-vaults/<namespace>/<name>/<version>`, persist only
the host-derived local manifest, rebuild the host, and drive the real Personal
Agent Web grounded query path.
