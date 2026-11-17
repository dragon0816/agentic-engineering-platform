# Low-risk remote integration (2026-11-12)

Status: approved scope; isolated verification in progress.

Owner accepted the staged integration recommendation, then required that
Knowledge asking quality must not regress while preserving usable Workflow
creation. Work from verified snapshot 097b2521 in a managed worktree.

## First slice

Select only remote commits ae1becf3 (safe numeric Outlook diagnostics),
3b3da4d5 (explicit opt-in for live Outlook tests), and c0553d76 (preserve queued
message feedback during backend checks). Preserve existing public failure
contracts, model/tool routing, context, Knowledge evidence/citations, authoring
isolation and approval behavior. No dependency, permission or resident change.

Do not integrate e564e1ad (chat Workflow run persistence) or the historical
267c75e4 release record. The former is a separate harness assessment requiring
scoped owner consent; the latter is not evidence for this integrated version.

## Contract and verification gates

- Outlook failure logging emits fixed stages and numeric HRESULT/scode only;
  no mail content, recipients, paths, exception message or traceback.
- Ordinary test collection does not probe live Outlook. Real mailbox tests
  require AEP_OUTLOOK_TESTS=1; this integration never enables it.
- Queued message status remains visible during backend checks; sending,
  message content and model/tool dispatch are unchanged.
- Run a clean baseline, then the affected Outlook/UI regressions.
- Run the same complete Knowledge-named test set before and after integration,
  including evidence, citations, query rewriting, scope, scenarios and authoring
  isolation. Compare source/model paths as well as pass counts. Deterministic
  tests cannot establish every stochastic real-model answer; retain that limit.
- Run full repository tests, Ruff check/format, mypy, build and pip check using
  the existing verified Python environment and this worktree's src on PYTHONPATH.
  Record original failures; never weaken tests or report reruns as initially green.
- Do not build concurrently with pytest. No live C4C run or resident restart is
  needed: the deployed resident and its approved Workflow remain unchanged.
- Push the verified fast-forward result to c4c-verified-20261112 only. Preserve
  origin/main and the original C4C snapshot history.

## Current evidence

Isolated source import checks passed. Baseline affected tests:
13 passed in 33.50s (chat early-send UI and Outlook draft mock tests).
Knowledge baseline is running; source integration waits for its result.

Knowledge baseline: 445 passed in 294.16s; all baseline gates passed.

## Independent review and original CI results

Read-only review found no Critical or Important issue. Minor limitations retained:
Outlook attachment failures after inline images can retain the coarser previous
stage label; the test collection probe expects repository-root cwd. No production
or test change was made to hide these limitations.

Standard CI43102812296 on exact sourcee69371e6 completed:6556passed/74skipped,
2failed (BI create-domain hold-count and BI version-form spatial assertion).
Ruff/format/mypy/build/pipcheck and both offline-preview install checks passed.
Browser-diagnostic upload failed because GitHub artifact storage quota was hit;
preview uploads were skipped. The original CI is NOT green.

A separate diagnostic-only commit2ffbf543/run43114604977 tested the original two
assertions unchanged, Windows/Python3.12, before097b2521 and aftere69371e6, twice
per ref. Version-form spatial assertion failed on BOTH refs in both passes;
this failure exists on the baseline. Create-domain passed on BOTH refs twice;
the full-run failure was not reproduced, and its cause is not proven. No only-head
failure was observed. Diagnostic artifact uploads also hit the storage quota;
run logs retain results. The diagnostic workflow is not part of delivery code.
No BI production logic/assertion/timeout was changed, no unrelated harness merge.

Local full verification completed on its initial run: 6619 passed, 13 skipped,
0 failures/errors in 8453.20 seconds. Both originally failing CI BI cases passed
locally. All 445 baseline Knowledge case identities and passed outcomes match
the completed full-suite JUnit record; the eight Knowledge/model source paths
remain identical. Evidence: full.log/full.xml and knowledge-after-full.json in
.scratch/low-risk-verification. This is deterministic regression evidence, not
an exhaustive evaluation of stochastic live-model answers. No assertion was
weakened and the original red CI/control outcomes above remain part of delivery.

Fresh committed-source platform wheel built successfully with pip wheel
--no-deps --no-build-isolation. Package source is e69371e6; approved assets and
operator documents form a separately documented local package overlay. See
C4C_WINDOWS_PACKAGE_20261112.md for the package and isolated-install proof.
