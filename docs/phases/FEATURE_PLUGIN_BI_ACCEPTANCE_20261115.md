# BI overview Plugin API1.1 acceptance

Date: 2026-11-15. Branch: `phase-plugins/bi-facade-20261114`.
Verified implementation: `0daf0b4449da04434733466fc6fd2c55f61c72ab`.
Subsequent changes through `8fdf51e7` were documentation only.

## Result and scope

The approved H1/H4 implementation passes the original full suite, independent
review, real HTTP/browser integration and package/build checks. It delivers
`bi-overview.overview@0.1.0`, an independently installable read-only metadata
overview for Plugin API>=1.1.0,<2.0.0. It is not full BI or LLM Wiki extraction.

H1 supplies declared existing BI context on initial start and worker restart;
undeclaring workers receive no stale reserved binding, while ordinary environment
is preserved. H4 keeps page read services out of Bridge/ToolAccess/model tool
inventories. Existing tool policies, grants, receipts and Knowledge paths remain
unchanged. Only `common/plugins.py`, `plugins/manager.py` and `plugins/process.py`
changed in core. No Host/Web/BI/Wiki/Telegram implementation was modified.

The owner explicitly approved 「同意僅 H1／H4 並繼續」 on 2026-11-15; evidence,
smaller alternatives and exclusions were recorded before implementation in
DECISIONS and `FEATURE_PLUGIN_BI_OVERVIEW_PLAN_20261114.md`.

## Original verification results

| Check | Actual result |
| --- | --- |
| Contract/manifest/frozen-v1 tests | 89 passed |
| Aggregate plugin and BI component tests | 302 passed, 1 privileged-symlink skip |
| Package/browser tests after local-copy label clarification | 20 passed |
| Full suite, original run with no reruns | **7029 passed, 16 skipped, 0 failed, 0 errors**; 1:52:47 |
| Exact Knowledge baseline | All445 cases present, identical passed outcomes; none missing |
| Knowledge source hashes | 46 files unchanged |
| Uncached Ruff / format | Passed; 1524 formatted files |
| Configured mypy plus external worker/builder | Passed; 1151 source files |
| Wheel/sdist build and pip check | Passed; no broken requirements |
| Wheel source and isolated imports | All580 Python files match after newline normalization; API1.1 imports passed |

The16 skips are environment/live-service cases listed in the committed JSON
evidence: unavailable codecs/models/Atlas references, optional real CLI/desktop/
Outlook tests, missing local dependencies/network support and privileged symlinks.
Real junction and headless browser tests ran. All work used synthetic workspaces,
not company BI, C4C, mailbox data or a real paid/company model.

The HTTP coexistence test records model tool names on **every request**, rather
than only the first. Before/after install it verifies identical tool catalogs,
registered identities, Skill inventory, published Wiki fact/version citation,
BI API output and BI source bytes. Uninstall retains BI data. Browser install,
page display of104 synthetic cards, disable and re-enable all passed.

The first full-suite run for this H1/H4 source is green. Do not confuse it with
the older Slice1 full run that had3 failures followed by targeted repairs, or
older CI43537708699 with2 failures and artifact quota trouble. Those historical
results remain recorded; this result does not prove those CI issues fixed or
claim a green CI run for a later pushed revision.

## Compatibility and artifact verification

Old v1 package bytes, content digest, staged files and install ledger remain
unchanged through parse/install/restore. Only the two new fields are omitted at
their defaults; pre-existing serialized defaults remain. An API1.0 closed parser
rejects new-field packages as invalid before its API compatibility check.

Source freeze covered1714 files: zero changes after full; after build only the
generated egg-info SOURCES.txt changed. The wheel contains the generic core API,
not the BI plugin worker. A fresh isolated --target install imported the wheel
without changing the shared editable environment. The sdist contains the plugin
manifest, three worker files, builder, example and exact golden-v1 fixtures.

Example: `examples/plugins/bi-overview.aep-plugin.json`, 37612 bytes, SHA256:
`e471429db4c29f9e0fdadda749148eff1bfcb04544cda80d0479002f3252f423`.
The builder's `--check` passes. It contains source and metadata only, no user data.
Builds under `C:/TEMP/aep-bi-build-20261115` are local code-verification artifacts
built before this final documentation commit, not a deployed Windows release.
Detailed hashes/results: `FEATURE_PLUGIN_BI_ACCEPTANCE_20261115.json`.

## Usage and limits

Use `feature_plugins/bi_overview/README.zh-TW.md`. On an API1.1 Host, install the
example through Plugins and open BI 資料集概覽. No additional AEP/IT install
approval is introduced. Missing, busy, outdated and truncated data are marked
honestly; unknown counts are not zero. Totals describe local copies, not published
answer sources or cross-dataset deduplication. Vault projection freshness is
unknown; external registry paths are never followed. The read budget bounds lock
waits between datasets, not all query/filesystem time. Conservative journal/link
handling and the earlier Slice1 late-refresh/status limitations remain documented.

No full BI editing/dashboard service migration, executable plugin GUI, model-data
change, repository migration, auto-install, main merge, resident update, Gateway
change or shared-venv rebinding was performed. Deterministic tests do not guarantee
all real-model answer quality. Future extraction requires a new concrete scope.
