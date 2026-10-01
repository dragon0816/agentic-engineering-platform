# Handoff

Date: 2026-10-01 (Asia/Taipei)
Branch: `codex/extension-runner`
Base: `origin/main` at merge commit `8e37cbe` (PR #169)
PR: pending

## Goal

Productization 3 slice 3: activate one explicitly approved staged Bridge
Extension outside the Bridge process, advertise only exact healthy declarations
and recover a retained healthy version on failure.

## Completed

- PR #169 passed exact-head Windows/Python 3.12 CI and auto-merged; signed
  extension packages now stage atomically without executing publisher code.
- Added closed correlated `aep-extension-jsonl/v1` health/invoke/shutdown
  requests and healthy/succeeded/refused/failed responses.
- Added `ExtensionActivationApproval`, binding actor, device kind/id, exact
  extension and approved technical-policy reference. A wrong device/policy is
  refused before any process or environment work.
- Added offline isolated-environment preparation after approval. Only verified
  staged wheel files are installed with `--no-index --no-deps`; a package-digest
  marker permits reuse and partial environments are removed.
- Added a fixed Windows subprocess adapter: exact isolated interpreter, `-I`,
  manifest module, no shell, synchronized JSON-lines, minimal non-secret
  environment and manifest timeouts.
- Added `ExtensionManager`: exact health declarations gate all advertisements;
  failed upgrades preserve the prior process, process failure removes the new
  advertisement and can restart the retained approved version, while repeated
  crashes disable reactivation inside the declared window.
- Added real Windows subprocess protocol coverage plus deterministic tests for
  approval, health identity, invoke, failed upgrade, automatic rollback, crash
  limit and offline preparation.

## In Progress

- Complete full verification, open the slice 3 PR, wait for exact-head CI and
  auto-merge when green.

## Remaining

1. Slice 4: add read-only independent Application catalog discovery over
   published Software metadata.
2. Slice 5: add extension lifecycle and Application projections to Personal
   Agent Web with applicable human gates.

## Architecture decisions made

- Extension publication, staging, activation approval, health advertisement
  and `LocalPolicy` execution grant are separate states.
- Environment preparation occurs only after device/policy approval and never
  resolves packages from a network index.
- A new version is health-checked before the previous process is stopped.
- Windows process separation is not claimed as an OS sandbox. Signed publisher
  trust, high-risk technical policy and device-owner/admin approval are still
  mandatory; no host secrets are forwarded in the child environment.

## Verification

Supported target: Windows, Python 3.12 only. No Ubuntu or browser automation.

```text
Focused extension package/runtime suite:
17 passed

Targeted ruff and format:
PASS

Targeted mypy:
Success: no issues found in 5 source files

python -m pytest --ignore=tests/test_browser.py -q
1443 passed, 4 skipped in 60.09s

python -m ruff check .
All checks passed!

python -m ruff format --check .
321 files already formatted

python -m mypy
Success: no issues found in 253 source files

python -m pip check
No broken requirements found.

python -m build --no-isolation --outdir <repo>/.scratch/build-p3-runner
Successfully built sdist and wheel; both include `extensions/runtime.py`.

git diff --check
PASS
```

## Known issues

- The subprocess boundary limits coupling, command construction and secret
  inheritance, but does not provide Windows AppContainer/job-object filesystem
  isolation. Extension activation remains a trusted, explicitly approved admin
  operation.
- Personal Agent Web lifecycle projection is slice 5; this slice provides the
  typed state and runtime service only.

## Next Recommended Action

Complete verification and merge this runner slice. Then expose independent
Applications read-only before adding both categories to Personal Agent Web.
