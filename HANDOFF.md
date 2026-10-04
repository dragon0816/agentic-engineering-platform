# Handoff

Date: 2026-10-04 (Asia/Taipei). Branch: main. Current goal: give the owner a truthful six-layer harness inventory and a first evidence/knowledge-gap matrix for five R&S product families across five target markets. The 25-cell matrix is a discovery tool, not a product-fit recommendation.

## Completed in this slice

- Follow-up startup diagnosis: the owner's reported Web traceback was an
  uncaught `VaultError` during Knowledge catalog construction. The current
  preview `host.json` binding points to `C:\Users\Chi_L\AppData\Local\AEP\rs-k`,
  whose required `index.md`, `log.md`, `raw` and `wiki` now exist. The same
  config passes `aep-host status` on this host. The exact earlier cause was not
  reproduced; do not claim a persistent missing Vault or change the original.
  Host construction now converts `VaultError` to a `knowledge_invalid` error
  naming the configured Vault path. Regression test covers a missing index.
- Added a read-only Knowledge Bridge capability, knowledge-query/market-matrix@1.0.0, and a versioned company-agent/market-alignment@1.0.0 Skill. Agent Web routes the matching natural-language request to that capability when a Knowledge Vault is installed. No model is required for the deterministic scan. The Bridge requires the exact knowledge-query.ask grant and knowledge-grounding-policy.
- The capability scans staged Raw Markdown and returns all 25 cells in stable order, each with an evidence level, source/section/excerpt when available, and explicit follow-up knowledge gaps. Every cell has market_fit_verified=false; a lexical co-mention is never represented as proven suitability.
- Wrote the six-layer inventory at docs/HARNESS_6_LAYER_STATUS.md and the design at docs/superpowers/specs/2026-10-04-market-alignment-matrix-design.md. Updated docs/CONTRACTS.md, docs/DECISIONS.md and docs/TASKS.md.
- In the owner's preview Host workspace, installed the new Skill manifest and added the new read-only capability grant using the same scope as Knowledge Ask. A backup of the prior grants.json is next to that file. No key, secret, Gateway setting or production workbook was changed.
- Direct runtime invocation with the owner's staged RS_Knowledge succeeded: 25 cells, 15 nearby lexical mentions, 10 separate-passage leads. Local report: .scratch/rs-product-market-matrix-2026-10-04.md. Raw source excerpts can contain COMPANY CONFIDENTIAL markings despite the owner's Vault-wide public classification, so the report remains ignored and was not committed. No product/option fit was asserted.

## Verification

- Full non-browser test selection: 1,738 passed, 5 environment skips, 26 browser deselections.
- The follow-up Vault-path regression test and two targeted matrix tests passed
  (3 passed). The first full non-browser run had one intermittent Windows
  `sync_workspace_unwritable` failure in the unrelated Knowledge Marketplace
  fixture; that test passed alone. The clean full rerun passed: 1,739 passed,
  5 environment skips, 26 browser deselections. Full Ruff, strict mypy on
  207 source files and a non-isolated wheel build passed.
- Ruff on src and tests, strict mypy on src, git diff --check and non-isolated wheel build passed. The isolated build could not download setuptools because this shell's network is restricted; non-isolated wheel build succeeded using the installed build tools.
- Live Web browser click test was not run. The currently running Web process on port 53582 still has old Python modules loaded; restart it from the owner's existing PowerShell session to load this slice. This Codex shell cannot see LITELLM_MASTER_KEY, although the owner has set it previously; do not repeatedly ask for it or restart a new process from this shell and inadvertently break Gateway chat.

## Open and next action

- The scanner returns retrieval leads, sometimes a converted figure or table-of-contents passage. A reviewer should pick one cell and confirm application, market standard, product/option specifications and customer evidence. The next Knowledge harness slice should then add an explicit evidence-sufficiency result, bounded re-retrieval and an independent claim check for that cell. Generalize routing policy only after this vertical slice is validated.
- General Skill-owned planning and a six-layer autonomous Knowledge loop remain incomplete; see docs/HARNESS_6_LAYER_STATUS.md.
- Previous Workflow 11 chart/Issue-assignee source-parity work is in commit abc49dc. The remaining live comparison is an isolated workbook copy and an unsent Outlook draft against the owner's reference. Workflow 7 remains paused; Workflow 10/13 real-source parity is also open. Laya comparison is prepared offline but no full model inference has run on this host.
- After deployment, stop the old Web process and launch aep-host web --config <preview host.json> --open in the already-working PowerShell, then ask for the five-by-five product/market evidence matrix. Do not run a second Web instance without preserving the existing Gateway credential environment.
