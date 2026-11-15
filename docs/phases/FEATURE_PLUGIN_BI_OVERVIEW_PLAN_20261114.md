# Next slice: BI overview plugin, with existing BI preserved

Status2026-11-15: owner explicitly approved only H1/H4 with
「同意僅 H1／H4 並繼續」 in response to the exact scope question. Consent is
recorded in DECISIONS before harness edits. Exclusions and expansion gate remain.
Branch: `phase-plugins/bi-facade-20261114`, from `a0496ae0`.

## Goal and honest boundary

Deliver a separately installable BI overview page using real existing local BI
dataset metadata: dataset count, available card counts, schema, update time,
subscription/read-only state and honest unavailable/rebuild-needed statuses.
This is the first adapter step toward BI extraction, not the complete BI plugin.
Existing BI import/edit/dashboard/query functionality stays in its original Host.
No new model tool or change to Knowledge asking is needed for an overview page.

The existing interactive BI GUI and its processing/services cannot yet move to
the Slice1 worker contract. This slice does not promise that installing the
overview removes the core's dependency on BI; full extraction remains later work.

## Source-first strategy and evidence

Use **ADAPT** for the metadata reader and **PRESERVE** the authoritative BI
services and repositories. No rewrite of card ingestion, query or evidence logic.

- `src/capabilities/bi_cards/manifest.py:15,36-105`: the installed BI Skill
  provides citation, modality, published-version and scope guidance.
- `src/host_runtime/assets.py:28,94`: BI Skill is shipped by the Host.
- `src/host_runtime/bi_cards_tools.py:172-191`: Skill switch and installed query
  capability control the current conversation tools. Keep them unchanged.
- `src/agent/skills.py:91-114`: Skill fields cannot add worker context variables,
  HTTP contribution types or change capability registration.
- `src/common/plugins.py:245,394,502-503`: current worker/data contract has no
  explicit existing-BI data location; page routes need zero required inputs.
- `src/plugins/process.py:159-175`: worker receives the staged package and its
  own data folder. The worker inherits OS identity/environment; this is a missing
  declared context, not an OS filesystem isolation guarantee.
- `src/plugins/manager.py:474-505`: all declared capabilities currently receive
  Bridge registrations. A UI-only data service needs a separate contribution
  choice to preserve the model's offered tools and established BI citation path.

The causal Skill alternative fails at these static boundaries: improving the
selected BI procedure cannot add a process variable or alter the registration
loop. There is a smaller alternative: derive the workspace by walking three
parents from AEP_PLUGIN_DATA_ROOT. That works with today's layout and needs no
harness change; H1 is not technically necessary just to find today's folder.
It is rejected for the supported plugin interface because it couples the plugin
to an undeclared parent layout, leaves its BI dependency absent from the manifest/
install record and fails if the data-root layout changes. Skill guidance can
teach that workaround but cannot add a stable Host binding or serialized dependency
to the closed manifest. H1 proposes that supported binding; this tradeoff belongs
in the consent request rather than a claim of technical impossibility.

**Do not reuse BiStore in a second concurrent worker.** Its constructor calls
`vault.ensure_current` (`store.py:575-579`), which can sync/rebuild; published reads
also refresh caches (`vault.py:1833-1845,3003-3018`). Repository RLocks only protect
within one process (`knowledge/repo/repository.py`). The overview reader must not
sync, rebuild or import those services. It reads bounded metadata and reports
unavailability; a read must not become a second BI writer.

## Alternatives assessed

1. **Recommended: independent read-only overview adapter.** Small H1/H4 extension,
   useful installed page, existing BI and asking untouched. Limited to metadata.
2. **In-process facade around all BI seams.** Preserves current writer/lock owner,
   but changes Host/Web/Telegram/asset wiring and does not yet deliver an independent
   plugin. Defer unless later extraction evidence makes it necessary.
3. **Full worker + executable GUI extraction now.** Requires single ownership of
   every BI read/write, model/data context, uploads, tasks, repository type and
   separate-origin UI. Too large for this slice; not authorized by Slice1 consent.

## Preparation that does not change the harness

- New `tests/test_bi_facade_characterization.py`: pin existing dataset API metadata,
  UI entry and the current read/rebuild behavior using synthetic workspaces only.
- New `feature_plugins/bi_overview/worker/aep_plugin_bi_overview/reader.py` and
  `__init__.py`: stdlib metadata reader with explicit `bi_root` argument. No Host
  imports, model call, BI service call, sync/rebuild, schema upgrade or source write.
- New `tests/test_bi_overview_reader.py`: parity on supported synthetic databases,
  honest missing/corrupt/outdated status, bounded output with truncation indicators,
  source byte preservation and no import of the authoritative BI service in worker.
- BI normally uses rollback journals, not WAL. Open only file URIs with mode=ro
  and query_only, never immutable=1 or a plain path. Execute all metadata queries
  for one database in one read transaction with a bounded busy timeout. Refuse
  hot-journal/WAL cases, report busy locks, and create nothing for a missing DB.
  Outdated vault user_version reports rebuild-needed without rebuilding. This
  provides per-dataset consistency, not a transaction across every dataset.
- No manifest/package claims until the required harness contract is approved and
  implemented; no new tools, routes or running Host behavior from this preparation.

## H1/H4 harness scope approved2026-11-15

### H1: explicit existing-BI context declaration

Add optional `PluginData.reads` declaration for the existing `bi` area, default
empty. For a declaring plugin, pass `AEP_PLUGIN_READ_BI=<workspace>/bi` on initial
start and lazy restart. Preserve ordinary environment, existing data locations,
package integrity and workspace-owned path checks. Handle missing data honestly;
installation must not create/migrate a BI repository or database.

This is context/compatibility metadata, not an IT/AEP data-access grant, filesystem
sandbox or new install approval. No token, model credentials or model-data approval
classes are passed. No BI/Wiki asking is moved to the worker.

### H4: distinguish UI service contributions from Agent tools

Add a backwards-compatible capability contribution option (proposed
`expose_as_tool`, default true). A false value is valid only for a read service
declared by a page route. Keep it available to the authenticated namespaced page
API, but do not add it to the Bridge/model tool inventory. Existing plugin tools
retain exactly their current default registration and successful-effect behavior.

This separates contribution types; it does not impose execution grants, turn
approvals, IT requirements or disable a previously installed Agent tool.
CapabilitySpec.policy (including approval_required/required_permissions), grants,
ToolAccess's existing meaning and TurnEffects remain unchanged. The service is
absent from registered capabilities and therefore from ToolAccess; existing tools
are still registered and executed as before. Converting an earlier tool contribution
to a page service requires a normal version update and the existing busy guard.

### Exact prospective implementation files

- `src/common/plugins.py`: only H1/H4 typed fields, cross-validation and compatible
  wire serialization. Existing v1 package digests must remain valid; adding default
  fields must not silently change canonical hashes of previously built packages.
  Explicit digest rule: omit only the newly added keys data.reads when empty and
  capability.expose_as_tool when true; preserve every pre-existing default field.
  Do not use exclude_defaults=True. Nondefault new values remain in the digest.
  Before changing the schema, commit a synthetic golden v1 package, its digest,
  staged bytes and ledger. Verify old parse/install/restore still become active
  with the identical digest. A Slice1 Host has a closed schema and will reject
  new-field packages as plugin_package_invalid before an API-range check; state
  this limit honestly. New packages will declare a new minimum Plugin API minor
  version; the core version constant and feature-range tests are in this file.
- `src/plugins/manager.py`: context plumbing and selective tool registration/
  unregistration, including restore/update/rollback/call_read paths.
- `src/plugins/process.py`: declared context on initial start and restart only.
- New BI plugin worker, manifest/builder and example package under feature_plugins
  and examples; associated schema/manager/process/Web/integration tests.
  Plugin source is included explicitly in the sdist (MANIFEST.in packaging-only
  change), not imported into the core wheel or auto-installed/deployed by default.
- Existing generic renderer/proxy should be reusable unchanged. Any new page
  input/write route, arbitrary link, executable UI or unrelated call-site change
  is outside this scope and requires a new proposal, not an opportunistic edit.

Do not change `host_runtime/host.py`, `web.py`, `web_page.py`, Telegram,
`bi_cards_tools`, `bi_cards_api`, `assistant_tools`, existing BI Skill/procedure,
Knowledge/model/data policy, repository engine, current BI storage or core API
behavior. If implementation evidence requires one of these, stop and rescope.

## Acceptance after consent

1. Old v1 package bytes/digests still parse, install, restore and operate unchanged.
2. H1 is present only as declared Host context; no stale inherited binding on a
   different plugin/restart. No new IT/installation approval or environment filter.
   Test a parent env containing AEP_PLUGIN_READ_BI: remove that reserved binding
   for non-declaring workers and set the actual Host binding for declaring ones.
   This affects only that platform-owned context key, not ordinary environment.
3. Page service health/call_read work without Bridge registration; other tools
   register normally. Disable/uninstall remove only owned contributions.
   Assert absence in both InstalledCapabilities and ToolAccess; preserve namespace
   ownership despite no registry entry. Cover tool-to-page version update, busy,
   failed update rollback and restore with the original tool set unchanged.
4. A real synthetic BI dataset appears on the installed overview page. No source
   file changes or repository rebuilds; unavailable data is labelled honestly.
5. Installed overview does not change model tool names, existing BI entry/API,
   sources, version citations or answers. Same445 Knowledge cases and an installed-
   plugin coexistence case match. No real-model quality guarantee is inferred.
6. Focused tests, uncached Ruff/format, configured mypy, appropriate full regression,
   build and independent Claude review. Preserve original CI failures and boundaries.

Repository backup/restore is deferred to the later extraction/data-movement slice;
it is not an additional requirement or mutation performed by this metadata page.

## Which data each number represents

Ordinary local datasets report their current local bi.sqlite, matching the seven
core dataset-list fields. Vault rows report the local working projection under
bi/vaults/<id>, not the published view used to answer questions. A projection at
the expected database version can still lag unapplied repository changes; label
it as local projection/freshness unknown, never as a verified published answer.
The reader never follows or displays an external vault registry path.

Subscribed rows resolve only the version named by the local subscription record;
no version or a missing copy is unavailable, not zero. The reader does not fetch,
advance or rebuild subscriptions. Platform latest/status details not available
without the BI service are omitted, rather than inventing parity. The overview
table labels count origin and availability; no grand total is presented as
complete while any row is unavailable or truncated. Its metadata is not a new
source for answering business questions. Full BI answers/citations remain on the
existing published-version/query path.

Domain preparation also lists registered vaults with missing projections and
invalid folder/registration statuses that the normal dataset API may skip or
reject. These are explicit diagnostic rows, not a claim of exact whole-list
equality; parity applies to supported ready rows and their stated seven fields.

## Previous CI, separate from next-stage evidence

CI43537708699 at `3c6a76b7` ended failure: 2 failed,6897 passed,74 skipped;
BI version-link viewport assertion and weekly-report draft status assertion.
Artifact upload also hit GitHub storage quota. Ruff reported one import-order
error in `tests/plugin_fixture_helpers.py`, reproduced locally with `--no-cache`
after the new plugins package existed. Fixed that helper ordering only; uncached
global Ruff/format pass. No claim that either original CI test failure is repaired
or caused by the upcoming BI adapter, and no assertion weakened to hide failures.

## Preparation verified; harness consent still pending

Final frozen preparation run: 28 passed in50.01s (5 characterization,19 reader,
4 golden compatibility). Uncached Ruff/format pass, configured mypy plus reader
1144 source files pass. Reader final delta independently reviewed with no new
Critical/Important. Runtime source under src/ is byte/source-equivalent to
 a0496ae0;46 Knowledge source hashes unchanged. No new445-case execution, full
suite or plugin packaging claimed in this preparation. Exact evidence and hashes:
FEATURE_PLUGIN_BI_PREPARATION_20261114.json.

The first characterization run had4 passes/1 test-prefix mistake; corrected to
VAULT_PREFIX from the production contract. Golden fixtures derive from an actual
v1 install and were created before any new schema fields. The manifest/package/
worker entry and H1/H4 core changes are not implemented. Owner scope question is
pending; elapsed time or reviewer READY is not owner consent.

Golden JSON snapshots are pinned with -text attributes (native CRLF preserved);
a fresh checkout-index with core.autocrlf=true reproduced exact package and staged
workspace hashes. No snapshot regeneration or changed golden expectations.

Owner explicitly approved the presented H1/H4 scope on2026-11-15. Contract-first
implementation has begun; earlier preparation/pending statements above record
the previous checkpoint, not a continuing approval requirement. No scope expansion.

## Final H1/H4 acceptance (2026-11-15)

Approved implementation completed. Original full7029 passed16 skipped, zero
failures, no reruns. Same445 Knowledge cases/46source hashes unchanged; build/
pipcheck/wheel580source match/isolated imports and sdist package checks passed.
Fresh independent review0Critical/Important; local-copy label clarified. See
FEATURE_PLUGIN_BI_ACCEPTANCE_20261115.md and JSON for evidence and limits.
Preparation/pending statements above are historical checkpoints, not current
approval requirements. No full BI/Wiki extraction or resident/main update.
