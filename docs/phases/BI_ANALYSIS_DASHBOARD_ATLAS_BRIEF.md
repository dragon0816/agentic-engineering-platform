# Brief for the Atlas side: the AEP BI dashboard

For: the coding agent (Codex) working in the Atlas repository
`C:/Users/Chi_L/Documents/claude/atlas-analysis-dashboard`. Owner request 2026-11-01. Design and contract:
`C:/Users/Chi_L/Documents/ChatGPT/agentic-engineering-platform/docs/phases/BI_ANALYSIS_DASHBOARD.md` §5 (feed) and
§6 (integration tests). Read them first. Treat the AEP repository as **read-only**: never edit, commit or run
installs there; you only read its contract, golden files and fixture server.

## Goal

An **AEP BI** application in Atlas that shows a BI knowledge base's analyses from a local AEP. In AEP, an
analysis is a saved question with SQL or a script and a chart spec, kept in a vault and edited there (often by
an AI conversation). Atlas is a viewer: it lists the vaults, renders each analysis's result as a panel,
offers its parameters, and lets the person arrange panels in their own Atlas dashboard. Atlas never writes to
AEP and never changes an analysis.

## What AEP provides

- Feed `aep.bi.analysis_feed/v1` (design §5): `GET /api/v1/bi/health`, `/vaults`,
  `/vaults/{id}/analyses`, `/vaults/{id}/analyses/{slug}/result?<param>=<value>`. GET only, loopback, no
  token; cross-origin allowed for local page origins only (as the AEP telemetry reads you already consume).
  Only the vault's **published** version is served. A script result not computed yet answers
  `409 result_not_ready` (show a waiting state and retry later, not an error). Errors are `{"ok": false,
  "code", "message"}`.
- Golden files `tests/fixtures/bi_feed/golden/*.json` in the AEP repo (task F1 on the AEP side lands them
  first; until then build against the examples in design §5).
- Fixture server `python scripts/bi_feed_server.py --port 53611` (AEP task F3) that prints `ready <url>`.
  Run it with AEP's own interpreter (`<AEP>/.venv/Scripts/python`), from the AEP repo directory.

## Tasks

1. **A1 Provider.** Follow the existing AEP integration (`web/src/platform/aep/`, `docs/AEP_TELEMETRY_INTEGRATION.md`):
   a dedicated provider for the BI feed with bounded reads, cancellation, the 8 MiB limit, offline and stale
   states (keep the last data when AEP stops), the 409 waiting state with a bounded retry, and parameter
   changes that refetch. Validate responses against the contract; unknown additive keys are kept, not errors.
   Unit tests against **vendored copies** of the golden files in `web/tests/fixtures/aep_bi/`.
2. **A2 Application.** `applications/aep_bi/` (like `aep_harness`): a vault picker, one panel per analysis
   in the feed's `order`, chart mapping `table`→table, `bar`→bar, `line`→line, `scatter`→scatter (x/y/series
   from the chart spec), parameter controls from `params` (enum values, bool, date), and badges from a `level`
   column (`gap`, `warning`). Panels may be moved and resized and the layout saved as a personal dashboard
   (Atlas's own storage). Add `npm run check:aep-bi -- --aep <AEP repo>`: it fails when the vendored golden files
   differ from AEP's.
3. **I1 End-to-end** (with the AEP fixture server, design §6.4): one command, with `AEP_REPO` set, starts the
   fixture server and Atlas, opens **AEP BI** headless and checks: vault list; every analysis panel shows the
   golden numbers; a parameter change refetches; `result_not_ready` shows waiting; stopping AEP shows offline
   with the last data kept; a non-local `Origin` is refused by AEP. Screenshots into Atlas's scratch folder.
   Document the command in Atlas's `docs/LOCAL_DEVELOPMENT.md` and `docs/VALIDATION.md`.

## Done when

`npm test`, `npm run build`, the server tests and the drift check pass; I1 passes against the fixture server;
Atlas's `docs/TASKS.md`, `docs/DECISIONS.md` and `docs/HANDOFF.md` record the work, following Atlas's own rules.
Report contract questions instead of guessing: a change to the feed is made on the AEP side first (golden files
updated), then vendored.
