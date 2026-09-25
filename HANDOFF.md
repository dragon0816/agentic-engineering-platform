# Handoff — E2E-04 PR #101 open; exact-head CI and merge pending

Updated: 2026-09-25 (Asia/Taipei).
Branch: `codex/e2e-04-software-evolution`.
Base: `main` at `8ab7157544f0ce26954e2718f4c8e422f3f08ac5`.
Pull request: #101, https://github.com/dragon0816/agentic-engineering-platform/pull/101

Progress across all phases remains in `docs/TASKS.md`. This file contains the
current stopping point and constraints needed to continue without chat history.

## Completed

- Implemented the E2E-04 software continuous-evolution green path with a local
  fixture repository and no external Git writes.
- Added exact-version `SoftwareManifest`, external repository, interface and
  release contracts. The Share Platform stores metadata and evidence only; it
  does not copy software source code.
- Added `SoftwareFailureReport` and `SoftwareImprovementRequest`. Issue capture
  derives the responsible owner and exact repository/revision from the catalog.
- Kept business approval, Bridge execution authorization, technical policy,
  source review, merge, release and publication as separate transitions.
- Added a pre-change reproduction gate. An unreproduced issue cannot enter the
  Coding Harness, and a broken baseline regression prevents candidate creation.
- Reused the E2E-03 `CodingHarness` for bounded repository modification and
  validation. A failed acceptance case or repository regression blocks the
  review artifact and release readiness.
- Added an inert source-control adapter that produces an exact, digest-bound
  pull-request candidate without contacting GitHub/GitLab or performing a Git
  write. The Harness cannot merge, release or republish software.
- Added explicit human source-review, merge, release and owner-republication
  records. The new published version retains the prior exact version as its
  rollback target and binds release evidence.
- Added Bridge capabilities for issue capture (`read`) and approved change
  preparation (`write`). Publishing software metadata does not install the
  capability or authorize its execution on a Bridge.
- Added four automated E2E tests covering the green path, unreproduced failures,
  regression failures, source-code exclusion and secret-value rejection.
- Updated architecture, contracts, roadmap, task status, README and the E2E-04
  phase record after the implementation had passed verification.

## In Progress

- The implementation and documentation are committed and pushed in PR #101.
  GitHub Actions verification of the final PR head and merge remain.

## Remaining

- Require the exact PR #101 head to pass the Windows/Python 3.12 verification
  job, then merge without altering the validated head.
- E2E-01 physical DUT/chipset engineering is the next and final gate in the
  approved product sequence. Do not start it until E2E-04 is merged and its
  reproducible green path is recorded.
- E2E-01 will require an enrolled company computer for real DUT/vendor-tool
  evidence. CI must remain inert.

## Architecture and migration decisions

- **REUSE** the resident `LocalAgent`, Gateway, Bridge, installed capability and
  local-policy path; E2E-04 introduces no parallel runtime.
- **REUSE** the E2E-03 `CodingHarness`, validator boundary, bounded repair loop,
  change set and validation evidence.
- **ADAPT** the E2E-05 exact-version catalog, improvement-request, approval,
  evidence and rollback concepts to external software repositories.
- **ADD** only Software metadata/contracts, a local installed-repository
  adapter, pre-change reproduction, an inert pull-request candidate and typed
  human review/merge/release/republish transitions.
- **DO NOT MIGRATE** a source-repository implementation for this slice. No
  overlapping source capability was needed to satisfy the acceptance scenario.
- Software source remains in the external repository identified by provider,
  locator and revision. The Share Platform represents ownership, version,
  interface, compatibility and release evidence.
- Reproduction must happen before mutation. The exact reported case must fail
  with the reported observed output while the existing regression set remains
  green; otherwise development is refused.
- Pull-request candidates are immutable, exact-change artifacts bound to the
  Harness validation digest. They are not proof of human review, merge, release
  or publication.
- Human source review, merge authority, release authority and asset-owner
  republishing remain explicit. No automated transition implies the next one.
- This gate is an inert local proof. Production repository checkout, hosted
  GitHub/GitLab PR APIs, branch protection, CI callbacks, release automation and
  production Registry persistence remain outside its scope.

## Exact verification commands and results

Local Windows/Python 3.12:

```text
.venv\Scripts\python.exe -m pytest tests\test_product_e2e_04.py -q -p no:cacheprovider --basetemp .scratch\pytest-e2e04-final
4 passed in 0.32s

.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp .scratch\pytest-e2e04-full
1300 passed, 4 skipped in 70.17s

.venv\Scripts\python.exe -m ruff check .
All checks passed

.venv\Scripts\python.exe -m ruff format --check .
252 files already formatted

.venv\Scripts\python.exe -m mypy
Success: no issues found in 203 source files

.venv\Scripts\python.exe -m build --no-isolation --outdir .scratch\build-e2e04
Successfully built sdist and wheel

.venv\Scripts\python.exe -m pip check
No broken requirements found

git diff --check
passed
```

The four skips are existing host-dependent cases: two Windows link privilege
checks, IPv6 loopback availability and a directory-link privilege check. No
Ubuntu or Python 3.11 validation was run, per owner instruction.

## Known issues

- The source-control adapter is inert; no live GitHub/GitLab PR, merge or
  release operation is part of the product E2E proof.
- The installed repository is a trusted, host-configured local fixture. Remote
  clone/fetch, credential handling and multi-tenant workspace allocation are
  not implemented.
- Routing and model responses are deterministic/scripted acceptance fixtures;
  no live model/provider is used as acceptance evidence.
- The Software catalog and lifecycle records are in memory; production
  Registry/database persistence is outside this gate.
- `.claude/` is user-owned local state. Do not commit, modify or remove it.

## Next Recommended Action

Wait for PR #101's exact head to pass the Windows/Python 3.12 verification job,
then merge that head and update this handoff with the merge and CI evidence. The
following development phase is E2E-01; begin with its architecture/requirements
gate and preserve inert CI while planning real validation on an enrolled
company PC.
