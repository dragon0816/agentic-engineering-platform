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
